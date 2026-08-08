"""Contest modes — three different games over the same log.

The scoreboard machinery (who is on which team, dupes, the clock, the bands
that count) is identical in all three. What changes is what a contact is
*worth*, and that is all a mode decides:

    classic    points x grid squares. The traditional shape: work more, and
               work more places.
    conquest   a map of the United States. Work a station in a state and your
               school owns it, coloured in your colours until somebody takes
               it back. Score is territory held.
    dx         only contacts outside the United States count, and the score is
               driven by how many countries you reach rather than how many
               contacts you make.

A mode never sees the log or the roster. It is handed a QSO that has already
passed every common rule, and it says what that contact does to a score.
"""
from __future__ import annotations

from datetime import datetime

from . import dxcc, maidenhead
from .adif import Qso

REJECT_NOT_US = "not in a US state"
REJECT_DOMESTIC = "domestic contact, DX only"


class Mode:
    """Base class. The default behaviour is classic scoring."""

    key = "classic"
    label = "Classic"
    #: What the page should draw beside the standings.
    view = "standings"

    def __init__(self, settings: dict | None = None) -> None:
        self.settings = settings or {}

    def extra_reject(self, qso: Qso, team, board) -> str | None:
        """A reason this contact does not score in this mode, if any."""
        return None

    def award(self, qso: Qso, team, score, board) -> None:
        """Credit an accepted contact."""
        raise NotImplementedError

    def score_for(self, score, board) -> int:
        raise NotImplementedError

    def team_extras(self, score, board) -> dict:
        return {}

    def snapshot_extras(self, board) -> dict:
        return {}


class ClassicMode(Mode):
    """Points times grid squares."""

    key = "classic"
    label = "Classic"
    view = "standings"

    def award(self, qso, team, score, board) -> None:
        score.points += board.points_for(qso)
        square = qso.square
        if square:
            score.squares.add(square)
            score.states.update(board.contest.states_for(square))

    def score_for(self, score, board) -> int:
        # Multipliers of zero would hold the first team on the board at nil
        # until it happened to work a station that sent a grid.
        return score.points * max(1, len(score.squares))


class ConquestMode(Mode):
    """Territory. Work a state, own a state.

    A grid square is bigger than a state line — 2 degrees by 1 is roughly 100
    miles by 70 — so a contact into a square that straddles a border stakes a
    claim in every state it touches. That is the honest reading: FT8 exchanges
    a grid square and nothing else, so there is no way to tell which side of
    the line the other station was on.

    Two rules for who holds a state, set by ``claim`` in contest.toml:

        first  whoever gets there first keeps it. Rewards speed, and the map
               stops changing once it fills up.
        most   whoever has the most contacts into it, ties broken by who
               claimed it first. States change hands all afternoon, which is
               the version that behaves like a game.
    """

    key = "conquest"
    label = "Conquest"
    view = "usmap"

    def __init__(self, settings=None) -> None:
        super().__init__(settings)
        self.claim = self.settings.get("claim", "first")
        # "state" is the familiar board; "grid" is 683 squares over the same
        # country, which turns the same game into one about coverage.
        self.territory_kind = self.settings.get("territory", "state")
        # Only means anything on the grid board; the state board is all 51
        # either way.
        self.territory_extent = self.settings.get("extent", "conus")

    def board_map(self, board):
        """The territory board, built once per scoreboard."""
        from .territory import TerritoryMap

        cached = getattr(board, "_territory_map", None)
        # getattr with a default rather than a bare attribute: a test can hand
        # the scoreboard a stand-in board, and asking one to grow a field it
        # has no opinion about is the cache's problem, not the double's.
        if (cached is None or cached.kind != self.territory_kind
                or getattr(cached, "extent", self.territory_extent)
                != self.territory_extent):
            cached = TerritoryMap(self.territory_kind, board.contest.grid_states,
                                  extent=self.territory_extent)
            cached.set_edges(self.settings.get("edges", {}) or {})
            board._territory_map = cached
        return cached

    def extra_reject(self, qso, team, board) -> str | None:
        # A contact that cannot be placed on the board cannot take territory.
        # It is not an error — most of a real log is elsewhere — so it is
        # reported as a reason rather than dropped silently.
        if not self.board_map(board).claimed_by(qso.square):
            return REJECT_NOT_US
        return None

    def award(self, qso, team, score, board) -> None:
        score.points += board.points_for(qso)
        square = qso.square
        score.squares.add(square)

        for state in self.board_map(board).claimed_by(square):
            score.state_contacts[state] += 1
            score.states.add(state)
            self._resolve(state, team, qso.when, board)

    def _resolve(self, state: str, team, when: datetime | None, board) -> None:
        """Decide who holds a state after a contact into it."""
        if state not in board.first_claim:
            board.first_claim[state] = team.abbr

        if self.claim == "first":
            board.owners.setdefault(state, board.first_claim[state])
            return

        # "most": recount, with the first claimant holding on through a tie.
        best, best_count = None, 0
        for abbr, other in board.teams.items():
            count = other.state_contacts.get(state, 0)
            if count > best_count or (
                count == best_count and count > 0 and abbr == board.first_claim[state]
            ):
                best, best_count = abbr, count
        if best:
            board.owners[state] = best

    def score_for(self, score, board) -> int:
        return sum(1 for owner in board.owners.values() if owner == score.team.abbr)

    def team_extras(self, score, board) -> dict:
        held = sorted(s for s, o in board.owners.items() if o == score.team.abbr)
        return {"owned": held, "owned_count": len(held)}

    def snapshot_extras(self, board) -> dict:
        colors = {t.abbr: t.color for t in board.contest.teams}
        return {
            "map": {
                "owners": dict(board.owners),
                "colors": colors,
                "claim_rule": self.claim,
                "territory": self.territory_kind,
                "total_states": self.board_map(board).total,
            }
        }


class DxMode(Mode):
    """Only contacts outside the United States score.

    The multiplier is countries rather than grid squares, so the game is about
    reach: a team that works twenty stations in Germany has one multiplier,
    and a team that works twenty countries has twenty.
    """

    key = "dx"
    label = "DX"
    view = "globe"

    #: Enough markers to show the shape of the afternoon without sending a
    #: megabyte of JSON to a scoreboard on a phone.
    MARKER_LIMIT = 400

    def __init__(self, settings=None) -> None:
        super().__init__(settings)
        self.points_per_dx = int(self.settings.get("points_per_dx", 3))
        self.count_domestic = bool(self.settings.get("count_domestic", False))

    def extra_reject(self, qso, team, board) -> str | None:
        if not self.count_domestic and not dxcc.is_dx(qso.call):
            return REJECT_DOMESTIC
        return None

    def award(self, qso, team, score, board) -> None:
        country, continent, is_dx = dxcc.lookup(qso.call)
        # The DX rate replaces the base rate; bonuses still stack on top.
        base = self.points_per_dx if is_dx else board.contest.qso_points
        score.points += board.points_for(qso, base=base, skip=("DX",))
        if is_dx and country != dxcc.UNKNOWN:
            score.entities.add(country)
        if continent:
            score.continents[continent] += 1

        square = qso.square
        if square:
            score.squares.add(square)

        position = maidenhead.to_latlon(square)
        if position:
            board.markers.append(
                {
                    "lat": position[0],
                    "lon": position[1],
                    "team": team.abbr,
                    "color": team.color,
                    "call": qso.call,
                    "country": country,
                    "grid": square,
                }
            )
            if len(board.markers) > self.MARKER_LIMIT:
                del board.markers[0]

    def score_for(self, score, board) -> int:
        return score.points * max(1, len(score.entities))

    def team_extras(self, score, board) -> dict:
        return {
            "entities": len(score.entities),
            "countries": sorted(score.entities),
            "continents": dict(score.continents.most_common()),
        }

    def snapshot_extras(self, board) -> dict:
        return {"markers": list(board.markers)}


class ScarcityMode(ConquestMode):
    """Conquest, but the last states standing are the valuable ones.

    Every state starts at ``base`` points. Each time one is claimed the
    remaining unclaimed states are worth more, so the map gets harder to
    ignore as it empties: Rhode Island at minute five is worth the same as
    Texas, and at minute fifty it is worth several times as much.

    Points are locked in at the moment of the claim. A state banked early
    keeps its early price — the reward is for going and getting the awkward
    ones while they are still awkward, not for having claimed anything at all.
    """

    key = "scarcity"
    label = "Scarcity"
    view = "usmap"

    def __init__(self, settings=None) -> None:
        super().__init__(settings)
        # Scarcity only makes sense if a state stays claimed; under "most" a
        # state could change hands and its price would be meaningless.
        self.claim = "first"
        self.base = int(self.settings.get("base_points", 10))
        self.step = int(self.settings.get("step_points", 5))

    def _resolve(self, state, team, when, board) -> None:
        if state in board.owners:
            return
        remaining_before = self._total_states(board) - len(board.owners)
        board.first_claim.setdefault(state, team.abbr)
        board.owners[state] = team.abbr
        # Price rises as the board empties. The last state is worth the most.
        claimed = len(board.owners) - 1
        board.state_value[state] = self.base + self.step * claimed
        board.claim_log.append(
            {
                "state": state,
                "team": team.abbr,
                "value": board.state_value[state],
                "remaining": remaining_before - 1,
                "when": when.isoformat() if when else None,
            }
        )

    def _total_states(self, board) -> int:
        return self.board_map(board).total

    def score_for(self, score, board) -> int:
        return sum(
            board.state_value.get(state, self.base)
            for state, owner in board.owners.items()
            if owner == score.team.abbr
        )

    def snapshot_extras(self, board) -> dict:
        extras = super().snapshot_extras(board)
        total = self._total_states(board)
        remaining = total - len(board.owners)
        extras["map"]["values"] = dict(board.state_value)
        extras["map"]["next_value"] = self.base + self.step * len(board.owners)
        extras["map"]["remaining"] = remaining
        extras["scarcity"] = {
            "base": self.base,
            "step": self.step,
            "next_value": self.base + self.step * len(board.owners),
            "remaining": remaining,
            "recent_claims": board.claim_log[-12:][::-1],
        }
        return extras


class ConnectMode(ConquestMode):
    """Territory only counts when it touches territory you already hold.

    Twelve states scattered across the country are worth nothing here and four
    in a row are worth everything, which turns the game from a scramble for
    whatever answers into something you have to plan. The nearest unclaimed
    state stops being an afterthought and becomes the only thing worth
    chasing.

    Score is the size of the largest unbroken run somebody holds. Reaching
    ``target`` wins it outright; the scoreboard says who got there first.
    """

    key = "connect"
    label = "Connect"
    view = "usmap"

    def __init__(self, settings=None) -> None:
        super().__init__(settings)
        self.target = int(self.settings.get("target", 4))

    def _held(self, board, abbr: str) -> set[str]:
        return {s for s, owner in board.owners.items() if owner == abbr}

    def score_for(self, score, board) -> int:
        held = self._held(board, score.team.abbr)
        if not held:
            return 0
        return len(self.board_map(board).largest_group(held))

    def team_extras(self, score, board) -> dict:
        held = self._held(board, score.team.abbr)
        run = self.board_map(board).largest_group(held) if held else []
        return {
            "owned": sorted(held),
            "owned_count": len(held),
            "run": run,
            "run_length": len(run),
            "complete": len(run) >= self.target,
        }

    def snapshot_extras(self, board) -> dict:
        extras = super().snapshot_extras(board)
        runs = {}
        winners = []
        for abbr in board.teams:
            held = self._held(board, abbr)
            run = self.board_map(board).largest_group(held) if held else []
            runs[abbr] = run
            if len(run) >= self.target:
                winners.append(abbr)
        extras["map"]["runs"] = runs
        extras["connect"] = {"target": self.target, "winners": winners}
        return extras


class TraverseMode(ConquestMode):
    """Cross the country: an unbroken chain of held states, coast to coast.

    ``axis = "east-west"`` runs Pacific to Atlantic, ``"north-south"`` runs the
    Canadian border to the Gulf and Mexico. The shortest possible crossing is
    seven states one way and three the other, so neither is a formality, and
    both reward looking at the map before calling CQ.

    Until somebody completes it the score is the longest chain that still
    reaches back to the starting coast — partial progress towards a crossing,
    rather than a scoreboard of zeroes for most of the afternoon.

    States only. Where a crossing starts and stops is declared per side in
    static/adjacency.json, and a grid-square board has no coasts.
    """

    key = "traverse"
    label = "Traverse"
    view = "usmap"

    AXES = {
        "east-west": ("west", "east"),
        "west-east": ("west", "east"),
        "north-south": ("north", "south"),
        "south-north": ("south", "north"),
    }

    def __init__(self, settings=None) -> None:
        super().__init__(settings)
        self.territory_kind = "state"     # a grid board has no coastline
        self.axis = self.settings.get("axis", "east-west")
        self.start_side, self.end_side = self.AXES.get(self.axis, ("west", "east"))
        # A completed crossing is worth more than any amount of progress.
        self.bonus = int(self.settings.get("crossing_points", 1000))

    def _held(self, board, abbr: str) -> set[str]:
        return {s for s, owner in board.owners.items() if owner == abbr}

    def score_for(self, score, board) -> int:
        held = self._held(board, score.team.abbr)
        if not held:
            return 0
        territory = self.board_map(board)
        crossing = territory.crossing(held, self.start_side, self.end_side)
        if crossing:
            # Shorter crossings are better: a tighter line is a better line.
            return self.bonus - len(crossing)
        return territory.best_progress(held, self.start_side, self.end_side)

    def team_extras(self, score, board) -> dict:
        held = self._held(board, score.team.abbr)
        territory = self.board_map(board)
        crossing = territory.crossing(held, self.start_side, self.end_side) if held else []
        return {
            "owned": sorted(held),
            "owned_count": len(held),
            "crossing": crossing,
            "crossed": bool(crossing),
            "reach": territory.best_progress(held, self.start_side, self.end_side) if held else 0,
        }

    def snapshot_extras(self, board) -> dict:
        extras = super().snapshot_extras(board)
        territory = self.board_map(board)
        crossings = {}
        for abbr in board.teams:
            held = self._held(board, abbr)
            crossings[abbr] = territory.crossing(held, self.start_side, self.end_side) if held else []
        extras["map"]["crossings"] = crossings
        extras["traverse"] = {
            "axis": self.axis,
            "from": list(territory.edge(self.start_side)),
            "to": list(territory.edge(self.end_side)),
            "winners": [a for a, c in crossings.items() if c],
        }
        return extras


MODES: dict[str, type[Mode]] = {
    "classic": ClassicMode,
    "conquest": ConquestMode,
    "dx": DxMode,
    "scarcity": ScarcityMode,
    "connect": ConnectMode,
    "traverse": TraverseMode,
}


def build(key: str, settings: dict | None = None) -> Mode:
    try:
        return MODES[key](settings)
    except KeyError:
        raise SystemExit(
            f"contest.toml: unknown mode {key!r}. Choose one of: "
            + ", ".join(sorted(MODES))
        )
