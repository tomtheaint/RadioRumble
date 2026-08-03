"""Reading the log without reading it twice.

The original watcher re-read the last hundred lines every time the file
changed and counted them again, so scores climbed on their own during a
contest. This tracks a byte offset instead: each read starts where the last
one stopped, and only genuinely new bytes are parsed.

Two things make that safe in practice. A record split across two reads is held
back until its ``<eor>`` arrives, and a file that shrinks is treated as a new
file — that is what a logger rotating or rewriting its ADIF output looks like
from here, and re-reading from zero is the only correct response.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from . import adif
from .scoring import Scoreboard

log = logging.getLogger("radiorumble.ingest")


class LogTailer:
    """Incremental reader for one ADIF file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.offset = 0
        self.pending = ""      # a record that arrived without its <eor> yet

    def reset(self) -> None:
        self.offset = 0
        self.pending = ""

    def read_new(self) -> list[adif.Qso]:
        """Parse whatever has been appended since the last call."""
        if not self.path.exists():
            return []

        size = self.path.stat().st_size
        if size < self.offset:
            # Truncated or replaced: everything we knew about is gone.
            log.info("%s shrank (%d -> %d bytes); re-reading from the start",
                     self.path.name, self.offset, size)
            self.reset()
        if size == self.offset:
            return []

        with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(self.offset)
            chunk = fh.read()
            self.offset = fh.tell()

        complete, self.pending = adif.split_complete(self.pending + chunk)
        return adif.parse(complete) if complete else []


class ContestIngest:
    """Owns the scoreboard, the tailer and the file watcher.

    Everything that mutates the scoreboard goes through :attr:`lock`, because
    watchdog calls back on its own thread while the web layer is serialising a
    snapshot on the event loop's.
    """

    def __init__(self, scoreboard: Scoreboard, on_change=None) -> None:
        self.scoreboard = scoreboard
        self.tailer = LogTailer(scoreboard.contest.log_file)
        self.lock = threading.Lock()
        self.on_change = on_change
        self._observer: Observer | None = None

    def ingest_now(self) -> int:
        """Read and score whatever is new. Returns the number of new QSOs scored."""
        with self.lock:
            qsos = self.tailer.read_new()
            if not qsos:
                return 0
            return self.scoreboard.add_all(qsos)

    def snapshot(self) -> dict:
        with self.lock:
            return self.scoreboard.snapshot()

    def start(self) -> None:
        """Load the existing log, then watch its directory for appends."""
        scored = self.ingest_now()
        log.info("loaded %d scoring QSOs from %s", scored, self.tailer.path)

        handler = _ChangeHandler(self)
        directory = self.tailer.path.parent
        self._observer = Observer()
        self._observer.schedule(handler, str(directory), recursive=False)
        self._observer.start()
        log.info("watching %s for changes to %s", directory, self.tailer.path.name)

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None


class _ChangeHandler(FileSystemEventHandler):
    """Filters directory events down to 'our log file grew'."""

    def __init__(self, ingest: ContestIngest) -> None:
        self.ingest = ingest
        # Resolve once. Comparing resolved paths avoids samefile(), which
        # raises when the event refers to a file that has already gone —
        # editors and loggers write through temporary files constantly, and
        # an exception here used to kill the watcher thread outright.
        self._target = ingest.tailer.path.resolve()

    def _is_target(self, event) -> bool:
        if event.is_directory:
            return False
        for attr in ("src_path", "dest_path"):
            raw = getattr(event, attr, None)
            if raw and Path(raw).resolve() == self._target:
                return True
        return False

    def _handle(self, event) -> None:
        if not self._is_target(event):
            return
        try:
            added = self.ingest.ingest_now()
        except Exception:
            # A malformed append must not take the watcher down with it; the
            # next write will be read from the same offset and try again.
            log.exception("failed to ingest changes to %s", self._target.name)
            return
        if added and self.ingest.on_change:
            self.ingest.on_change()

    # Loggers append (modified), some rewrite (created), WSJT-X's ADIF write
    # can land as a move from a temp file. All three mean "look again".
    on_modified = _handle
    on_created = _handle
    on_moved = _handle
