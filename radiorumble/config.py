"""Contest configuration: the rules, the clock and who is on which team.

Everything that decides a score lives in ``contest.toml`` rather than in code,
because the rules are the part that changes between events. Adding a school
means adding a ``[[teams]]`` block, not editing Python.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from .bonuses import BonusRules

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = BASE_DIR / "contest.toml"
DEFAULT_GRIDS = BASE_DIR / "grid.txt"


@dataclass(frozen=True)
class Match:
    """One fixture: who is playing, and when.

    Optional. With no `[[matches]]` at all every team counts as playing today,
    which is what a one-off event means and what this app was until there was
    a reason to know otherwise. The moment there is a season, the roll call
    has to know which schools are actually expected at the radio this
    afternoon — listing forty teams when four are playing is as useless as
    listing none.
    """

    teams: tuple = ()               # team abbreviations; empty when open
    day: object = None              # the date it is played on
    start: object = None            # a window, when the day is not enough
    end: object = None
    label: str = ""
    #: A free-for-all: no roster, anybody who shows up is in it. Set on its
    #: own, or implied by naming no teams -- a fixture with nobody in it can
    #: only mean everybody.
    open: bool = False

    @property
    def is_open(self) -> bool:
        return self.open or not self.teams

    def on(self, when: datetime) -> bool:
        """Is this fixture happening at that moment?

        A day is the usual answer: an operator checking in at ten to two cares
        that their team plays *today*, not that the clock has started.
        """
        if self.start and self.end:
            return self.start <= when <= self.end
        if self.day is not None:
            return self.day == when.date()
        return True                 # a fixture with no date is always on


@dataclass(frozen=True)
class Team:
    name: str
    abbr: str
    color: str
    callsigns: tuple[str, ...]
    #: Set when a single operator has been split out of a school, so the page
    #: can still show who they are competing for.
    affiliation: str = ""
    #: Shown on the team card. `logo` is a URL or a path under static/ — kept
    #: as a plain string so a club can point at whatever it already has.
    logo: str = ""
    description: str = ""
    gear: str = ""
    #: Who is operating, as opposed to which callsigns they log under. A club
    #: station is one callsign and a dozen people, and the people are the part
    #: worth putting on a scoreboard.
    members: tuple[str, ...] = ()
    website: str = ""
    #: Where the station is. Drawn on the map and the globe so a team can see
    #: what it has and has not reached, which is the whole basis of deciding
    #: which state to chase next.
    grid: str = ""

    @property
    def position(self) -> tuple[float, float] | None:
        from .maidenhead import to_latlon

        return to_latlon(self.grid) if self.grid else None


@dataclass
class Contest:
    name: str
    start: datetime | None
    end: datetime | None
    bands: frozenset[str]
    modes: frozenset[str]
    qso_points: int
    dupe_scope: str            # "band" | "band-mode" | "contest"
    teams: tuple[Team, ...]
    log_file: Path
    grid_states: dict[str, tuple[str, ...]] = field(default_factory=dict)
    mode: str = "classic"      # "classic" | "conquest" | "dx" | "scarcity"
    mode_settings: dict = field(default_factory=dict)
    #: Directory of submitted logs, one file per entrant. When set, this is
    #: what makes cross-checking possible: a contact can only be confirmed
    #: against the other operator's own log.
    log_dir: Path | None = None
    #: The [listener] table, verbatim. The listener reads its own settings so
    #: adding one never means adding a field here.
    listener: dict = field(default_factory=dict)
    #: The fixture list, if there is one. Empty means everybody plays today.
    matches: tuple = ()
    #: "team"     schools against each other.
    #: "operator" every rostered callsign as its own entry — a club running a
    #:            contest among its own members. Still needs a roster.
    #: "open"     a free-for-all. No roster at all: anybody whose log reaches
    #:            us is entered, from the moment it does.
    compete_as: str = "team"
    #: How far apart two logs may place the same contact and still match.
    #: Clocks drift and loggers round differently; FT8 transmissions are 15
    #: seconds, so a couple of minutes is generous without being meaningless.
    match_minutes: int = 3
    #: Scoring modifiers. Every one is optional and they stack.
    bonuses: "BonusRules" = None  # type: ignore[assignment]

    def build_mode(self):
        """The scoring rules for this contest. Imported late to avoid a cycle."""
        from .modes import build

        return build(self.mode, self.mode_settings)

    # -- team lookup ------------------------------------------------------

    def __post_init__(self) -> None:
        self._by_callsign = {
            call.upper(): team for team in self.teams for call in team.callsigns
        }
        if self.bonuses is None:
            from .bonuses import BonusRules

            self.bonuses = BonusRules()

    @property
    def is_open(self) -> bool:
        """A free-for-all: anybody whose log reaches us is competing.

        Distinct from `compete_as = "operator"`, which still needs everyone
        listed in advance. Open events have no roster at all, which is the
        normal shape of a club night or anything advertised on a repeater --
        you find out who entered by seeing who turns up.
        """
        return self.compete_as == "open"

    def fixtures(self, when: datetime | None = None) -> tuple:
        """The matches happening at that moment."""
        moment = when or datetime.now(timezone.utc)
        return tuple(m for m in self.matches if m.on(moment))

    def open_now(self, when: datetime | None = None) -> bool:
        """Is what is happening right now a free-for-all?

        True when the event itself is open, and also when the fixture running
        is -- a season of team matches can still have an open night in it.
        """
        if self.is_open:
            return True
        live = self.fixtures(when)
        return bool(live) and all(m.is_open for m in live)

    def playing(self, when: datetime | None = None) -> tuple:
        """Which teams are expected at the radio.

        All of them when no fixture list has been written, which is what a
        single event means -- and all of them again when the fixture running is
        an open one, because in a free-for-all everybody who has shown up is in
        it by definition.
        """
        if not self.matches:
            return tuple(t.abbr for t in self.teams)
        moment = when or datetime.now(timezone.utc)
        live = self.fixtures(moment)
        if any(m.is_open for m in live):
            return tuple(t.abbr for t in self.teams)
        due = {abbr.upper() for m in live for abbr in m.teams}
        # Ordered as the teams are, not as the fixtures are, so the roll call
        # reads the same way the scoreboard does.
        return tuple(t.abbr for t in self.teams if t.abbr.upper() in due)

    def admit(self, callsign: str) -> "Team | None":
        """Enter a station that just turned up. Only in an open event.

        The entrant is created the first time their log reaches us, which is
        the only moment we could possibly learn they exist. Idempotent, and
        `None` anywhere else -- a rostered event rejecting an unknown station
        is the behaviour that keeps the rest of the world out of the standings.
        """
        call = (callsign or "").upper().strip()
        if not call or not self.is_open:
            return None
        found = self._by_callsign.get(call)
        if found is not None:
            return found
        entrant = Team(
            name=call,
            abbr=call,
            # Cycled rather than random so the same field gets the same
            # colours on a reload, which matters when the map is the
            # scoreboard.
            color=OPERATOR_COLORS[len(self.teams) % len(OPERATOR_COLORS)],
            callsigns=(call,),
        )
        self.teams = tuple(self.teams) + (entrant,)
        self._by_callsign[call] = entrant
        return entrant

    def team_for(self, callsign: str) -> Team | None:
        """Which team a logging station belongs to, or None if unrostered.

        Unrostered stations are dropped rather than given their own row: at a
        collegiate event the log is full of contacts with the rest of the
        world, and every one of those is somebody else's station callsign
        appearing in someone's log.
        """
        return self._by_callsign.get(callsign.upper())

    # -- rules ------------------------------------------------------------

    def in_window(self, when: datetime | None) -> bool:
        """Whether a QSO falls inside the contest period.

        A log with no timestamp counts — some loggers omit time_on — on the
        grounds that refusing to score a contact because of a missing optional
        field is worse than scoring one a minute early.
        """
        if when is None:
            return True
        if self.start and when < self.start:
            return False
        if self.end and when > self.end:
            return False
        return True

    def band_ok(self, band: str) -> bool:
        return not self.bands or band.lower() in self.bands

    def mode_ok(self, mode: str) -> bool:
        return not self.modes or mode.upper() in self.modes

    def states_for(self, square: str) -> tuple[str, ...]:
        """US states a grid square touches. Squares span borders, so this is a list."""
        return self.grid_states.get(square.upper(), ())

    @property
    def status(self) -> str:
        now = datetime.now(timezone.utc)
        if self.start and now < self.start:
            return "pending"
        if self.end and now > self.end:
            return "finished"
        return "running"

    @property
    def seconds_remaining(self) -> int | None:
        if not self.end:
            return None
        return max(0, int((self.end - datetime.now(timezone.utc)).total_seconds()))


def _as_utc(value) -> datetime | None:
    """TOML gives us a date-time; make sure it is timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def load_grid_states(path: Path = DEFAULT_GRIDS) -> dict[str, tuple[str, ...]]:
    """Read grid.txt into {grid square: (state, ...)}.

    The file is one state per line, comma separated. Squares repeat across
    lines because a 4-character square is about 70 by 100 miles and does not
    respect state lines — EM19 is in both Kansas and Missouri — so the mapping
    is one-to-many in that direction.
    """
    mapping: dict[str, list[str]] = {}
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        state, squares = parts[0], parts[1:]
        for square in squares:
            mapping.setdefault(square.upper(), []).append(state)
    return {k: tuple(v) for k, v in mapping.items()}


# Used when a school is split into individual operators, so each entry is
# still tellable apart on a map. Chosen to stay distinct on a dark background.
OPERATOR_COLORS = (
    "#4da3ff", "#3fd07f", "#ffc857", "#ff7a59", "#a371f7", "#ff5ea8",
    "#2dd4bf", "#c0d13a", "#8ab4ff", "#f0883e", "#7ee787", "#d2a8ff",
)


def split_into_operators(teams: tuple[Team, ...]) -> tuple[Team, ...]:
    """One entry per callsign instead of one per school.

    For a club running a contest among its own members, or an event thrown
    open to anyone: the machinery is identical, only the unit of competition
    changes. A school with a single operator keeps its own colours, because
    there is nothing to tell apart.
    """
    out: list[Team] = []
    index = 0
    for team in teams:
        solo = len(team.callsigns) == 1
        for call in team.callsigns:
            out.append(
                Team(
                    name=call,
                    abbr=call,
                    color=team.color if solo else OPERATOR_COLORS[index % len(OPERATOR_COLORS)],
                    callsigns=(call,),
                    affiliation=team.name,
                    grid=team.grid,
                    logo=team.logo,
                    gear=team.gear,
                    website=team.website,
                )
            )
            index += 1
    return tuple(out)


def _as_datetime(value):
    """tomllib hands back a date, a datetime, or a string. Any of them is a
    reasonable thing for somebody to have typed."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _load_matches(raw) -> tuple:
    if not isinstance(raw, list):
        return ()
    out = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        teams = tuple(str(t).upper() for t in entry.get("teams", []) if str(t).strip())
        wide = bool(entry.get("open", False)) or not teams
        day = entry.get("date")
        if isinstance(day, datetime):
            day = day.date()
        elif isinstance(day, str):
            moment = _as_datetime(day)
            day = moment.date() if moment else None
        elif not isinstance(day, date):
            day = None
        out.append(Match(teams=teams, day=day, open=wide,
                         start=_as_datetime(entry.get("start")),
                         end=_as_datetime(entry.get("end")),
                         label=str(entry.get("label", ""))))
    return tuple(out)


def load(path: Path = DEFAULT_CONFIG) -> Contest:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)

    contest = data.get("contest", {})
    teams = tuple(
        Team(
            name=t["name"],
            abbr=t.get("abbr", t["name"][:4].upper()),
            color=t.get("color", "#666666"),
            callsigns=tuple(c.upper() for c in t.get("callsigns", [])),
            grid=str(t.get("grid", "")).upper(),
            logo=t.get("logo", ""),
            description=t.get("description", ""),
            gear=t.get("gear", ""),
            members=tuple(t.get("members", [])),
            website=t.get("website", ""),
        )
        for t in data.get("teams", [])
    )

    compete_as = os.environ.get("RR_COMPETE_AS") or contest.get("compete_as", "team")
    if compete_as == "operator":
        teams = split_into_operators(teams)
    elif compete_as == "open":
        # Anyone listed is a pre-registered entrant with a name and colours
        # somebody chose; everybody else is admitted when their log arrives.
        # Splitting keeps the unit of competition one callsign either way.
        teams = split_into_operators(teams)

    log_file = Path(contest.get("log_file", "mock_contest_log.txt"))
    if not log_file.is_absolute():
        log_file = BASE_DIR / log_file

    log_dir = contest.get("log_dir")
    if log_dir:
        log_dir = Path(log_dir)
        if not log_dir.is_absolute():
            log_dir = BASE_DIR / log_dir

    # Mode settings live in their own table, so [conquest] and [dx] can each
    # carry options without colliding. RR_MODE overrides the file, which is
    # how you show all three games at a demo without editing anything.
    mode = os.environ.get("RR_MODE") or contest.get("mode", "classic")
    mode_settings = data.get(mode, {}) if isinstance(data.get(mode), dict) else {}

    return Contest(
        name=contest.get("name", "Radio Rumble"),
        start=_as_utc(contest.get("start")),
        end=_as_utc(contest.get("end")),
        bands=frozenset(b.lower() for b in contest.get("bands", [])),
        modes=frozenset(m.upper() for m in contest.get("modes", [])),
        qso_points=int(contest.get("qso_points", 1)),
        dupe_scope=contest.get("dupe_scope", "band"),
        teams=teams,
        log_file=log_file,
        grid_states=load_grid_states(),
        mode=mode,
        mode_settings=mode_settings,
        log_dir=log_dir or None,
        listener=data.get("listener", {}) if isinstance(data.get("listener"), dict) else {},
        matches=_load_matches(data.get("matches")),
        compete_as=compete_as,
        match_minutes=int(contest.get("match_minutes", 3)),
        bonuses=BonusRules.from_config(data.get("bonuses")),
    )
