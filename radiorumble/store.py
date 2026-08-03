"""Every contact seen, and what an admin has struck out.

Scoring used to be a one-way fold: a contact arrived, it was counted, and it
was forgotten. Two of the things a contest actually needs make that
impossible.

Cross-checking is one. Whether a contact is confirmed depends on a log that
may not have been submitted yet, so a contact scored an hour ago can become
verified — or turn out to be *not in log* — when the other end sends theirs in.

Voiding is the other. An admin striking out a contact has to remove it from
every total it ever contributed to.

So the store keeps the contacts, and the scoreboard is rebuilt from them.
Reading the log files is still incremental — nothing is parsed twice — but
what is *derived* from them is a pure function of the contacts, the voids and
the rules, which means it can never drift out of step with them.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("radiorumble.store")


class QsoStore:
    """Contacts from every log, plus the void list."""

    def __init__(self, voids_path: Path | None = None) -> None:
        self.qsos: list = []
        self.voids: dict[str, str] = {}      # uid -> reason
        self.voids_path = voids_path
        self._seen: set[str] = set()
        if voids_path:
            self.load_voids()

    # -- contacts ---------------------------------------------------------

    def extend(self, qsos) -> int:
        """Add newly read contacts, ignoring ones already held.

        The duplicate guard matters when a log is re-read from the start after
        a rotation: the same contacts come back, and without this they would
        all be added a second time.
        """
        added = 0
        for qso in qsos:
            uid = qso.uid
            if uid in self._seen:
                continue
            self._seen.add(uid)
            self.qsos.append(qso)
            added += 1
        return added

    def reset_source(self, source: str) -> None:
        """Forget everything from one log, so it can be re-read cleanly."""
        self.qsos = [q for q in self.qsos if q.source != source]
        self._seen = {q.uid for q in self.qsos}

    # -- voids ------------------------------------------------------------

    def void(self, uid: str, reason: str = "") -> bool:
        if uid in self.voids:
            return False
        self.voids[uid] = reason or "voided by an official"
        self.save_voids()
        return True

    def restore(self, uid: str) -> bool:
        if uid not in self.voids:
            return False
        del self.voids[uid]
        self.save_voids()
        return True

    def is_void(self, uid: str) -> bool:
        return uid in self.voids

    def load_voids(self) -> None:
        """Voids survive a restart — they are a judgement, not a cache."""
        try:
            if self.voids_path and self.voids_path.exists():
                self.voids = json.loads(self.voids_path.read_text(encoding="utf-8"))
                log.info("loaded %d voided contacts", len(self.voids))
        except (OSError, ValueError):
            log.exception("could not read %s; starting with no voids", self.voids_path)
            self.voids = {}

    def save_voids(self) -> None:
        if not self.voids_path:
            return
        try:
            self.voids_path.write_text(
                json.dumps(self.voids, indent=1, sort_keys=True), encoding="utf-8"
            )
        except OSError:
            log.exception("could not write %s; the void will not survive a restart",
                          self.voids_path)

    def find(self, uid: str):
        for qso in self.qsos:
            if qso.uid == uid:
                return qso
        return None
