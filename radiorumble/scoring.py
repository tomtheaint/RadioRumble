"""Contest scoring.

The scoreboard is an in-memory fold over the QSO stream. Every QSO is offered
to :meth:`Scoreboard.add`, which either accepts it or says why not — and the
"why not" is kept, because at a live event "my last ten contacts didn't count"
is the question that actually gets asked, and an answer of *dupe on 20m* ends
the conversation where a silent drop starts an argument.

Everything here is common to all three contest modes: rosters, the clock,
bands, and what makes two contacts the same contact. What a contact is *worth*
belongs to :mod:`radiorumble.modes`.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .adif import Qso
from .config import Contest, Team
from .modes import Mode
from .verify import NIL, UNMATCHED, VERIFIED, VOIDED

# Why a QSO was not scored. These strings surface in the UI, so they are
# phrased as reasons rather than error codes.
REJECT_UNROSTERED = "station is not on any team roster"
REJECT_WINDOW = "outside the contest window"
REJECT_BAND = "band not used in this contest"
REJECT_MODE = "mode not used in this contest"
REJECT_DUPE = "duplicate contact"
REJECT_VOID = "voided by an official"
REJECT_NIL = "not in the other operator's log"


@dataclass
class TeamScore:
    team: Team
    qsos: int = 0
    points: int = 0
    squares: set[str] = field(default_factory=set)
    states: set[str] = field(default_factory=set)
    entities: set[str] = field(default_factory=set)
    state_contacts: Counter = field(default_factory=Counter)
    continents: Counter = field(default_factory=Counter)
    by_operator: Counter = field(default_factory=Counter)
    by_band: Counter = field(default_factory=Counter)
    by_mode: Counter = field(default_factory=Counter)
    verification: Counter = field(default_factory=Counter)
    last_qso: datetime | None = None

    @property
    def confirmed(self) -> int:
        return self.verification[VERIFIED]

    @property
    def multipliers(self) -> int:
        return len(self.squares)

    def as_dict(self, board) -> dict:
        row = {
            "name": self.team.name,
            "abbr": self.team.abbr,
            "color": self.team.color,
            "qsos": self.qsos,
            "points": self.points,
            "multipliers": self.multipliers,
            "states": len(self.states),
            "score": board.mode.score_for(self, board),
            "operators": [
                {"call": call, "qsos": n} for call, n in self.by_operator.most_common()
            ],
            "bands": dict(self.by_band.most_common()),
            "modes": dict(self.by_mode.most_common()),
            "last_qso": self.last_qso.isoformat() if self.last_qso else None,
            "affiliation": self.team.affiliation,
            "grid": self.team.grid,
            "logo": self.team.logo,
            "description": self.team.description,
            "gear": self.team.gear,
            "members": list(self.team.members),
            "website": self.team.website,
            "verified": self.verification[VERIFIED],
            "nil": self.verification[NIL],
            "unmatched": self.verification[UNMATCHED],
        }
        row.update(board.mode.team_extras(self, board))
        return row


class Scoreboard:
    """Accumulates QSOs into per-team scores. Not thread safe by itself.

    The ingest thread and the web layer both touch this, so callers hold the
    lock in :mod:`radiorumble.ingest` around mutation.
    """

    RECENT_LIMIT = 40

    def __init__(self, contest: Contest, mode: Mode | None = None) -> None:
        self.contest = contest
        self.mode = mode if mode is not None else contest.build_mode()
        self.teams: dict[str, TeamScore] = {
            team.abbr: TeamScore(team=team) for team in contest.teams
        }
        # (station, call, band-or-whatever the dupe scope says) already worked.
        self._worked: dict[str, set[tuple[str, ...]]] = defaultdict(set)
        self.recent: deque = deque(maxlen=self.RECENT_LIMIT)
        self.rejected: Counter = Counter()
        self.total_seen = 0

        # Everyone the teams worked who is not competing. These are the people
        # a collegiate event depends on — nobody scores without somebody to
        # answer — so they get a leaderboard of their own.
        self.chasers: Counter = Counter()
        self.chaser_teams: dict[str, set[str]] = defaultdict(set)
        self.chaser_last: dict[str, datetime] = {}
        self.verification: Counter = Counter()
        self.bonuses_applied: Counter = Counter()
        self.penalties: int = 0
        self.rules = contest.bonuses

        # Mode-owned state. Kept on the board rather than inside the mode so a
        # snapshot is one object and the mode itself stays stateless per QSO.
        self.owners: dict[str, str] = {}       # conquest: state -> team abbr
        self.first_claim: dict[str, str] = {}  # conquest: who got there first
        self.markers: list[dict] = []          # dx: positions for the globe
        self.state_value: dict[str, int] = {}  # scarcity: price paid per state
        self.claim_log: list[dict] = []        # scarcity: the running ticker

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

    def entrant_for(self, qso: Qso):
        """Which entry this contact scores for, admitting a new one if the
        event is open.

        In a rostered event an unknown station is the rest of the world and is
        dropped. In a free-for-all there is no such thing as unknown: the first
        contact somebody logs is how we learn they entered, so the entry is
        created here and kept.
        """
        team = self.contest.team_for(qso.station)
        if team is None:
            team = self.contest.admit(qso.station)
            if team is not None and team.abbr not in self.teams:
                self.teams[team.abbr] = TeamScore(team=team)
        return team

    def check(self, qso: Qso) -> str | None:
        """Return the reason this QSO cannot be scored, or None if it can."""
        team = self.entrant_for(qso)
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
        return self.mode.extra_reject(qso, team, self)

    def points_for(self, qso: Qso, base: int | None = None, skip=()) -> int:
        """What one contact is worth once every active modifier is applied.

        Modes ask for this rather than reading qso_points directly, so a
        bonus switched on in the configuration reaches every game at once.
        """
        from . import dxcc

        base = self.contest.qso_points if base is None else base
        if not self.rules.enabled:
            return base
        is_dx = dxcc.lookup(qso.call)[2]
        points, applied = self.rules.evaluate(qso, base, is_dx, skip=skip)
        for name in applied:
            self.bonuses_applied[name] += 1
        return points

    # -- accumulation -----------------------------------------------------

    def add(self, qso: Qso, status: str = UNMATCHED, void_reason: str = "") -> str | None:
        """Score one QSO. Returns None if accepted, otherwise the reason.

        ``status`` is what the cross-check made of it. It does not decide
        whether the contact counts — most contacts at a collegiate event are
        with people who will never submit a log, and refusing those would
        punish teams for working exactly who the contest wants them to work.
        It is recorded, shown, and left for an official to act on.
        """
        self.total_seen += 1

        if void_reason:
            self.rejected[REJECT_VOID] += 1
            return REJECT_VOID

        # "Not in log" is the one status that can cost a team something, and
        # only when an organiser has asked for it. The penalty is deliberately
        # harsher than losing the contact: guessing at a half-copied callsign
        # should be worse than not logging it at all.
        if status == NIL and self.rules.nil_penalty:
            team = self.entrant_for(qso)
            if team is not None:
                self.teams[team.abbr].points -= self.rules.nil_penalty
                self.teams[team.abbr].verification[NIL] += 1
                self.verification[NIL] += 1
                self.penalties += self.rules.nil_penalty
            self.rejected[REJECT_NIL] += 1
            return REJECT_NIL

        reason = self.check(qso)
        if reason is not None:
            self.rejected[reason] += 1
            return reason

        team = self.entrant_for(qso)
        score = self.teams[team.abbr]
        self._worked[team.abbr].add(self._dupe_key(qso))

        score.qsos += 1
        score.by_operator[qso.station] += 1
        score.by_band[qso.band] += 1
        score.by_mode[qso.mode] += 1
        score.verification[status] += 1
        self.verification[status] += 1
        if qso.when and (score.last_qso is None or qso.when > score.last_qso):
            score.last_qso = qso.when

        # Anyone worked who is not themselves competing is a chaser.
        if self.contest.team_for(qso.call) is None:
            self.chasers[qso.call] += 1
            self.chaser_teams[qso.call].add(team.abbr)
            if qso.when and qso.when > self.chaser_last.get(qso.call, qso.when - timedelta(days=1)):
                self.chaser_last[qso.call] = qso.when

        self.mode.award(qso, team, score, self)

        self.recent.appendleft(
            {
                "uid": qso.uid,
                "team": team.abbr,
                "color": team.color,
                "station": qso.station,
                "call": qso.call,
                "band": qso.band,
                "mode": qso.mode,
                "grid": qso.square,
                "status": status,
                "when": qso.when.isoformat() if qso.when else None,
            }
        )
        return None

    def add_all(self, qsos) -> int:
        """Score a batch, returning how many were accepted."""
        return sum(1 for qso in qsos if self.add(qso) is None)

    def score_store(self, store, crosscheck=None) -> int:
        """Fold an entire store in, in log order, applying voids and status."""
        ordered = sorted(store.qsos, key=lambda q: (q.when is None, q.when))
        accepted = 0
        for qso in ordered:
            status = crosscheck.status(qso) if crosscheck else UNMATCHED
            reason = store.voids.get(qso.uid, "")
            if self.add(qso, status=status, void_reason=reason) is None:
                accepted += 1
        return accepted

    # -- chasers ----------------------------------------------------------

    def chaser_board(self, limit: int = 25) -> list[dict]:
        """Who worked the teams most.

        Ranked by contacts, with the number of different schools reached as
        the tie-break and a flag for anyone who worked every one of them —
        a clean sweep is the thing worth chasing if you are not competing.
        """
        total_teams = len(self.teams)
        rows = []
        for call, count in self.chasers.items():
            reached = self.chaser_teams[call]
            rows.append(
                {
                    "call": call,
                    "qsos": count,
                    "teams": len(reached),
                    "worked": sorted(reached),
                    "sweep": total_teams > 0 and len(reached) == total_teams,
                    "last": self.chaser_last[call].isoformat()
                    if call in self.chaser_last else None,
                }
            )
        rows.sort(key=lambda r: (r["qsos"], r["teams"]), reverse=True)
        for position, row in enumerate(rows[:limit], start=1):
            row["position"] = position
        return rows[:limit]

    # -- output -----------------------------------------------------------

    def standings(self) -> list[dict]:
        """Teams sorted the way a scoreboard is read: leader first."""
        rows = [score.as_dict(self) for score in self.teams.values()]
        rows.sort(key=lambda r: (r["score"], r["qsos"], r["multipliers"]), reverse=True)
        for position, row in enumerate(rows, start=1):
            row["position"] = position
        return rows

    def snapshot(self) -> dict:
        """Everything the scoreboard page needs, in one JSON-ready object."""
        contest = self.contest
        payload = {
            "contest": {
                "name": contest.name,
                "mode": self.mode.key,
                "mode_label": self.mode.label,
                "view": self.mode.view,
                "status": contest.status,
                "start": contest.start.isoformat() if contest.start else None,
                "end": contest.end.isoformat() if contest.end else None,
                "seconds_remaining": contest.seconds_remaining,
                "bands": sorted(contest.bands),
                "modes": sorted(contest.modes),
                "server_time": datetime.now(timezone.utc).isoformat(),
                "compete_as": contest.compete_as,
            },
            "standings": self.standings(),
            "recent": list(self.recent),
            "chasers": self.chaser_board(),
            "homes": [
                {
                    "abbr": t.abbr, "color": t.color, "grid": t.grid,
                    "lat": t.position[0], "lon": t.position[1], "name": t.name,
                }
                for t in contest.teams
                if t.position is not None
            ],
            "totals": {
                "qsos_scored": sum(t.qsos for t in self.teams.values()),
                "qsos_seen": self.total_seen,
                "rejected": dict(self.rejected),
                "verification": dict(self.verification),
                "chasers": len(self.chasers),
            },
        }
        payload.update(self.mode.snapshot_extras(self))
        return payload
