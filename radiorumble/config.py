"""Contest configuration: the rules, the clock and who is on which team.

Everything that decides a score lives in ``contest.toml`` rather than in code,
because the rules are the part that changes between events. Adding a school
means adding a ``[[teams]]`` block, not editing Python.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = BASE_DIR / "contest.toml"
DEFAULT_GRIDS = BASE_DIR / "grid.txt"


@dataclass(frozen=True)
class Team:
    name: str
    abbr: str
    color: str
    callsigns: tuple[str, ...]


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

    # -- team lookup ------------------------------------------------------

    def __post_init__(self) -> None:
        self._by_callsign = {
            call.upper(): team for team in self.teams for call in team.callsigns
        }

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
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) < 2:
            continue
        state, squares = parts[0], parts[1:]
        for square in squares:
            mapping.setdefault(square.upper(), []).append(state)
    return {k: tuple(v) for k, v in mapping.items()}


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
        )
        for t in data.get("teams", [])
    )

    log_file = Path(contest.get("log_file", "mock_contest_log.txt"))
    if not log_file.is_absolute():
        log_file = BASE_DIR / log_file

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
    )
