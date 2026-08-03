"""Contest scoring.

The scoreboard is an in-memory fold over the QSO stream. Every QSO is offered
to :meth:`Scoreboard.add`, which either accepts it or says why not — and the
"why not" is kept, because at a live event "my last ten contacts didn't count"
is the question that actually gets asked, and an answer of *dupe on 20m* ends
the conversation where a silent drop starts an argument.

Score follows the shape every contest uses: points times multipliers. Working
more stations raises points; working *new places* raises the multiplier, so a
team that sits on one frequency all afternoon loses to one that moves around.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .adif import Qso
from .config import Contest, Team

# Why a QSO was not scored. These strings surface in the UI, so they are
# phrased as reasons rather than error codes.
REJECT_UNROSTERED = "station is not on any team roster"
REJECT_WINDOW = "outside the contest window"
REJECT_BAND = "band not used in this contest"
REJECT_MODE = "mode not used in this contest"
REJECT_DUPE = "duplicate contact"


@dataclass
class TeamScore:
    team: Team
    qsos: int = 0
    points: int = 0
    squares: set[str] = field(default_factory=set)
    states: set[str] = field(default_factory=set)
    by_operator: Counter = field(default_factory=Counter)
    by_band: Counter = field(default_factory=Counter)
    by_mode: Counter = field(default_factory=Counter)
    last_qso: datetime | None = None

    @property
    def multipliers(self) -> int:
        return len(self.squares)

    @property
    def score(self) -> int:
        """Points times multipliers, with multipliers of zero treated as one.

        Otherwise the first team on the board sits at zero until it happens to
        log a contact carrying a grid square, which reads as a broken
        scoreboard rather than as a rule.
        """
        return self.points * max(1, self.multipliers)

    def as_dict(self) -> dict:
        return {
            "name": self.team.name,
            "abbr": self.team.abbr,
            "color": self.team.color,
            "qsos": self.qsos,
            "points": self.points,
            "multipliers": self.multipliers,
            "states": len(self.states),
            "score": self.score,
            "operators": [
                {"call": call, "qsos": n} for call, n in self.by_operator.most_common()
            ],
            "bands": dict(self.by_band.most_common()),
            "modes": dict(self.by_mode.most_common()),
            "last_qso": self.last_qso.isoformat() if self.last_qso else None,
        }


class Scoreboard:
    """Accumulates QSOs into per-team scores. Not thread safe by itself.

    The ingest thread and the web layer both touch this, so callers hold the
    lock in :mod:`radiorumble.ingest` around mutation.
    """

    RECENT_LIMIT = 40

    def __init__(self, contest: Contest) -> None:
        self.contest = contest
        self.teams: dict[str, TeamScore] = {
            team.abbr: TeamScore(team=team) for team in contest.teams
        }
        # (station, call, band-or-whatever the dupe scope says) already worked.
        self._worked: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        self.recent: deque = deque(maxlen=self.RECENT_LIMIT)
        self.rejected: Counter = Counter()
        self.total_seen = 0

    # -- rules ------------------------------------------------------------

    def _dupe_key(self, qso: Qso) -> tuple[str, ...]:
        """What makes two contacts the same contact.

        Default is per band: working the same station on 20m and again on 40m
        is two contacts, which is what makes moving bands worth doing.
        """
        scope = self.contest.dupe_scope
        if scope == "contest":
            return (qso.station, qso.call)
        if scope == "band-mode":
            return (qso.station, qso.call, qso.band, qso.mode)
        return (qso.station, qso.call, qso.band)

    def check(self, qso: Qso) -> str | None:
        """Return the reason this QSO cannot be scored, or None if it can."""
        team = self.contest.team_for(qso.station)
        if team is None:
            return REJECT_UNROSTERED
        if not self.contest.in_window(qso.when):
            return REJECT_WINDOW
        if not self.contest.band_ok(qso.band):
            return REJECT_BAND
        if not self.contest.mode_ok(qso.mode):
            return REJECT_MODE
        if self._dupe_key(qso) in self._worked[team.abbr]:
            return REJECT_DUPE
        return None

    # -- accumulation -----------------------------------------------------

    def add(self, qso: Qso) -> str | None:
        """Score one QSO. Returns None if accepted, otherwise the reason."""
        self.total_seen += 1
        reason = self.check(qso)
        if reason is not None:
            self.rejected[reason] += 1
            return reason

        team = self.contest.team_for(qso.station)
        score = self.teams[team.abbr]
        self._worked[team.abbr].add(self._dupe_key(qso))

        score.qsos += 1
        score.points += self.contest.qso_points
        score.by_operator[qso.station] += 1
        score.by_band[qso.band] += 1
        score.by_mode[qso.mode] += 1
        if qso.when and (score.last_qso is None or qso.when > score.last_qso):
            score.last_qso = qso.when

        square = qso.square
        if square:
            score.squares.add(square)
            score.states.update(self.contest.states_for(square))

        self.recent.appendleft(
            {
                "team": team.abbr,
                "color": team.color,
                "station": qso.station,
                "call": qso.call,
                "band": qso.band,
                "mode": qso.mode,
                "grid": square,
                "when": qso.when.isoformat() if qso.when else None,
            }
        )
        return None

    def add_all(self, qsos) -> int:
        """Score a batch, returning how many were accepted."""
        return sum(1 for qso in qsos if self.add(qso) is None)

    # -- output -----------------------------------------------------------

    def standings(self) -> list[dict]:
        """Teams sorted the way a scoreboard is read: leader first."""
        ranked = sorted(
            self.teams.values(),
            key=lambda s: (s.score, s.qsos, s.multipliers),
            reverse=True,
        )
        out = []
        for position, score in enumerate(ranked, start=1):
            row = score.as_dict()
            row["position"] = position
            out.append(row)
        return out

    def snapshot(self) -> dict:
        """Everything the scoreboard page needs, in one JSON-ready object."""
        contest = self.contest
        return {
            "contest": {
                "name": contest.name,
                "status": contest.status,
                "start": contest.start.isoformat() if contest.start else None,
                "end": contest.end.isoformat() if contest.end else None,
                "seconds_remaining": contest.seconds_remaining,
                "bands": sorted(contest.bands),
                "modes": sorted(contest.modes),
                "server_time": datetime.now(timezone.utc).isoformat(),
            },
            "standings": self.standings(),
            "recent": list(self.recent),
            "totals": {
                "qsos_scored": sum(t.qsos for t in self.teams.values()),
                "qsos_seen": self.total_seen,
                "rejected": dict(self.rejected),
            },
        }
