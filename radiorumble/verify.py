"""Cross-checking one log against another.

A contact is a claim by one operator that a conversation happened. On its own
it cannot be told apart from an invention. The only real evidence is the other
operator's log saying the same thing, which is why every serious contest asks
both ends to submit and then compares them.

Four states, and the difference between the last two is the one that matters:

    verified    the other station's log has the reciprocal contact
    nil         the other station submitted a log and this contact is *not*
                in it — "not in log", the classic sign of a busted callsign
                or an invented contact
    unmatched   the other station never submitted a log, so there is nothing
                to check against. Neutral: most contacts at a collegiate
                event are with people who will never send anything in
    voided      an admin struck it out by hand

Only *nil* is evidence of anything. Treating unmatched as suspicious would
punish a team for working stations who happen not to be entrants, which is
exactly the behaviour the contest wants to encourage.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

VERIFIED = "verified"
NIL = "nil"
UNMATCHED = "unmatched"
VOIDED = "voided"


class CrossCheck:
    """An index of every contact seen, able to confirm one against another."""

    def __init__(self, qsos, match_minutes: int = 3) -> None:
        self.window = timedelta(minutes=match_minutes)
        # Every station that submitted anything. A station that sent no log
        # cannot contradict anybody.
        self.submitters: set[str] = {q.station for q in qsos}
        # (logger, worked) -> the contacts claimed, so the reciprocal of
        # A-worked-B is looked up directly as (B, A).
        self._index: dict[tuple[str, str], list] = defaultdict(list)
        for qso in qsos:
            self._index[(qso.station, qso.call)].append(qso)

    def status(self, qso) -> str:
        """How well corroborated one contact is."""
        reciprocals = self._index.get((qso.call, qso.station), ())
        for other in reciprocals:
            if self._matches(qso, other):
                return VERIFIED

        # They sent in a log and this contact is not in it.
        if qso.call in self.submitters:
            return NIL
        return UNMATCHED

    def _matches(self, a, b) -> bool:
        """Whether two logs are describing the same contact.

        Band has to agree — a contact is on a band, and two stations cannot
        disagree about which. Time is allowed to drift: clocks are not
        synchronised, loggers round differently, and the two ends record the
        start and end of a sequence that takes the better part of a minute.
        """
        if a.band and b.band and a.band != b.band:
            return False
        if a.when and b.when and abs(a.when - b.when) > self.window:
            return False
        return True

    def summary(self, qsos) -> dict[str, int]:
        counts = {VERIFIED: 0, NIL: 0, UNMATCHED: 0}
        for qso in qsos:
            counts[self.status(qso)] += 1
        return counts
