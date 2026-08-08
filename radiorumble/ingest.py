"""Reading the logs without reading anything twice.

The original watcher re-read the last hundred lines every time the file
changed and counted them again, so scores climbed on their own during a
contest. Reading is tracked by byte offset instead: each read starts where the
last one stopped, and only genuinely new bytes are parsed.

Two things make that safe. A record split across two reads is held back until
its ``<eor>`` arrives, and a file that shrinks is treated as a new file — that
is what a logger rotating its output looks like from here, and re-reading from
zero is the only correct response.

What is *derived* from the contacts is rebuilt from scratch each time, because
cross-checking and voiding both reach backwards: a contact scored an hour ago
can become confirmed when the other operator submits their log, and an admin
striking one out has to remove it from every total it fed.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import adif
from .scoring import Scoreboard
from .store import QsoStore
from .verify import CrossCheck

log = logging.getLogger("radiorumble.ingest")

#: Extensions treated as submitted logs when watching a directory.
LOG_SUFFIXES = {".adi", ".adif", ".txt", ".log"}


class LogTailer:
    """Incremental reader for one ADIF file."""

    def __init__(self, path: Path, source: str = "") -> None:
        self.path = Path(path)
        self.source = source or self.path.name
        self.offset = 0
        self.pending = ""      # a record that arrived without its <eor> yet
        self.rotated = False   # set when the file shrank, so callers can reset

    def reset(self) -> None:
        self.offset = 0
        self.pending = ""

    def read_new(self) -> list[adif.Qso]:
        """Parse whatever has been appended since the last call."""
        self.rotated = False
        if not self.path.exists():
            return []

        size = self.path.stat().st_size
        if size < self.offset:
            log.info("%s shrank (%d -> %d bytes); re-reading from the start",
                     self.path.name, self.offset, size)
            self.reset()
            self.rotated = True
        if size == self.offset:
            return []

        with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self.offset)
            chunk = fh.read()
            self.offset = fh.tell()

        complete, self.pending = adif.split_complete(self.pending + chunk)
        return adif.parse(complete, source=self.source) if complete else []


class ContestIngest:
    """Owns the store, the scoreboard, the tailers and the file watcher.

    Everything that mutates shared state goes through :attr:`lock`, because
    watchdog calls back on its own thread while the web layer is serialising a
    snapshot on the event loop's.
    """

    def __init__(self, contest, on_change=None) -> None:
        self.contest = contest
        self.store = QsoStore(voids_path=contest.log_file.parent / "voided.json")
        self.lock = threading.Lock()
        self.on_change = on_change
        self._observer = None
        self._tailers: dict[Path, LogTailer] = {}
        self.scoreboard = Scoreboard(contest)
        self._rebuild()

    # -- the logs ---------------------------------------------------------

    @property
    def watch_dir(self) -> Path:
        """Directory holding the logs — the whole point when cross-checking."""
        return self.contest.log_dir or self.contest.log_file.parent

    def _log_paths(self) -> list[Path]:
        """Every log to read. One file, or a directory of submissions."""
        if self.contest.log_dir:
            if not self.contest.log_dir.exists():
                return []
            return sorted(
                p for p in self.contest.log_dir.iterdir()
                if p.is_file() and p.suffix.lower() in LOG_SUFFIXES
            )
        return [self.contest.log_file]

    def _tailer_for(self, path: Path) -> LogTailer:
        tailer = self._tailers.get(path)
        if tailer is None:
            tailer = LogTailer(path, source=path.name)
            self._tailers[path] = tailer
            log.info("reading %s", path.name)
        return tailer

    # -- scoring ----------------------------------------------------------

    def _rebuild(self) -> None:
        """Rebuild every derived number from the contacts held."""
        board = Scoreboard(self.contest)
        crosscheck = CrossCheck(self.store.qsos, self.contest.match_minutes)
        board.score_store(self.store, crosscheck)
        self.scoreboard = board
        self.crosscheck = crosscheck

    def ingest_now(self) -> int:
        """Read every log, add what is new, and rebuild. Returns new contacts."""
        with self.lock:
            added = 0
            for path in self._log_paths():
                tailer = self._tailer_for(path)
                new = tailer.read_new()
                if tailer.rotated:
                    # The file was rewritten; forget what it used to say.
                    self.store.reset_source(tailer.source)
                added += self.store.extend(new)
            if added:
                self._rebuild()
            return added

    def rescore(self) -> None:
        """Rebuild without re-reading — used after an admin voids a contact."""
        with self.lock:
            self._rebuild()

    def snapshot(self, limit: int = 0) -> dict:
        with self.lock:
            return self.scoreboard.snapshot(limit=limit)

    # -- admin ------------------------------------------------------------

    def void(self, uid: str, reason: str = "") -> bool:
        with self.lock:
            changed = self.store.void(uid, reason)
            if changed:
                self._rebuild()
        return changed

    def restore(self, uid: str) -> bool:
        with self.lock:
            changed = self.store.restore(uid)
            if changed:
                self._rebuild()
        return changed

    def contacts(self, limit: int = 500, team: str = "", status: str = "") -> list[dict]:
        """The contact list an official reviews, newest first."""
        with self.lock:
            rows = []
            for qso in sorted(self.store.qsos,
                              key=lambda q: (q.when is None, q.when), reverse=True):
                owner = self.contest.team_for(qso.station)
                state = self.crosscheck.status(qso)
                voided = self.store.voids.get(qso.uid)
                if team and (not owner or owner.abbr != team):
                    continue
                if status and status != ("voided" if voided else state):
                    continue
                rows.append(
                    {
                        "uid": qso.uid,
                        "station": qso.station,
                        "call": qso.call,
                        "band": qso.band,
                        "mode": qso.mode,
                        "grid": qso.square,
                        "when": qso.when.isoformat() if qso.when else None,
                        "team": owner.abbr if owner else None,
                        "color": owner.color if owner else None,
                        "source": qso.source,
                        "status": "voided" if voided else state,
                        "void_reason": voided or "",
                    }
                )
                if len(rows) >= limit:
                    break
            return rows

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        scored = self.ingest_now()
        log.info("loaded %d contacts from %d log(s)", scored, len(self._log_paths()))

        handler = _ChangeHandler(self)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_dir), recursive=False)
        self._observer.start()
        log.info("watching %s", self.watch_dir)

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None


class _ChangeHandler(FileSystemEventHandler):
    """Filters directory events down to 'a log we care about grew'."""

    def __init__(self, ingest: ContestIngest) -> None:
        self.ingest = ingest

    def _relevant(self, event) -> bool:
        if event.is_directory:
            return False
        # Comparing resolved paths avoids samefile(), which raises when the
        # event refers to a file that has already gone. Editors and loggers
        # write through temporary files constantly, and an exception here used
        # to kill the watcher thread outright.
        targets = {p.resolve() for p in self.ingest._log_paths()}
        for attr in ("src_path", "dest_path"):
            raw = getattr(event, attr, None)
            if not raw:
                continue
            path = Path(raw)
            if path.resolve() in targets:
                return True
            # A brand new submission in the log directory counts too.
            if (self.ingest.contest.log_dir
                    and path.parent.resolve() == self.ingest.contest.log_dir.resolve()
                    and path.suffix.lower() in LOG_SUFFIXES):
                return True
        return False

    def _handle(self, event) -> None:
        if not self._relevant(event):
            return
        try:
            added = self.ingest.ingest_now()
        except Exception:
            # A malformed append must not take the watcher down with it; the
            # next write will be read from the same offset and try again.
            log.exception("failed to ingest a change")
            return
        if added and self.ingest.on_change:
            self.ingest.on_change()

    on_modified = _handle
    on_created = _handle
    on_moved = _handle
