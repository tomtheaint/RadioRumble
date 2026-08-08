"""What a contact takes, and what is next to what.

The map games all ask the same two questions — *which piece of ground did that
contact claim*, and *which pieces touch it* — so both live here rather than
being repeated in each mode. That is what lets the same game be played over
states or over grid squares by changing one word in the configuration.

States are the coarse, familiar board: 51 pieces, borders everyone can picture,
and a contact often claims two at once because a grid square is bigger than a
state line. Grid squares are the fine board: 683 pieces over the United States,
each unambiguous, and a game on them is far longer and far more about
coverage than about luck.
"""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from . import maidenhead

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_ADJACENCY = BASE_DIR / "static" / "adjacency.json"

STATE = "state"
GRID = "grid"

CONUS = "conus"
ALL = "all"
#  Off the lower 48. Both are states like any other on the state board; on the
#  grid board they are the difference between a board somebody can finish and
#  one where a third of the pieces are Aleutian sea.
OUTLYING = ("Alaska", "Hawaii")


class TerritoryMap:
    """The board a map game is played on."""

    def __init__(self, kind: str, grid_states: dict, adjacency_path: Path = DEFAULT_ADJACENCY,
                 extent: str = CONUS):
        self.kind = kind if kind in (STATE, GRID) else STATE
        self.extent = extent if extent in (CONUS, ALL) else CONUS
        self.grid_states = grid_states
        self._adjacency: dict[str, list[str]] = {}
        self._edges: dict[str, list[str]] = {}
        if self.kind == STATE:
            self._load_adjacency(adjacency_path)
        #  Which squares are pieces. Alaska is 207 of the 683 that touch the
        #  country -- 30% of the board, nearly all of it water nobody will work
        #  in a two-hour contest -- so the default board is the lower 48 and
        #  the whole thing is opt-in. It only narrows the *board*: a contact
        #  into Alaska still scores, it just doesn't take a square.
        self._in_play = self._squares_in_play()

    def _squares_in_play(self) -> dict:
        if self.kind != GRID or self.extent == ALL:
            return self.grid_states
        return {square: states for square, states in self.grid_states.items()
                if any(state not in OUTLYING for state in states)}

    def _load_adjacency(self, path: Path) -> None:
        if not path.exists():
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        self._adjacency = data.get("neighbours", {})
        self._edges = data.get("edges", {})

    # -- the board --------------------------------------------------------

    def claimed_by(self, square: str) -> tuple[str, ...]:
        """Which territories a contact into this grid square takes.

        On the state board this is one-to-many: a square straddling a border
        stakes a claim in every state it touches, because FT8 sends a grid and
        nothing else and there is no honest way to narrow it down. On the grid
        board it is exactly one, which is the point of playing there.
        """
        if not square:
            return ()
        if self.kind == GRID:
            # Only squares that touch the country are part of the board;
            # otherwise a contact with Germany would claim territory.
            return (square,) if square in self._in_play else ()
        return tuple(self.grid_states.get(square, ()))

    def neighbours(self, territory: str) -> tuple[str, ...]:
        if self.kind == GRID:
            return tuple(n for n in maidenhead.neighbours(territory)
                         if n in self._in_play)
        return tuple(self._adjacency.get(territory, ()))

    def all_territories(self) -> set[str]:
        if self.kind == GRID:
            return set(self._in_play)
        return {s for states in self.grid_states.values() for s in states}

    @property
    def total(self) -> int:
        return len(self.all_territories())

    def geometry(self) -> list[dict]:
        """Where each piece of the board is, for something that has to draw it.

        Only the grid board needs this. States are drawn from their outlines,
        which the page already has; a grid square is a 2-by-1 degree rectangle
        and its position follows from its name, so sending the centre is
        enough and the corners are the client's arithmetic.

        `region` is which of the three panels a square belongs in. The map
        draws Alaska and Hawaii as insets, because at true scale Alaska is
        half the picture -- so a square off Anchorage has to be told apart
        from one over Kansas or it lands in the sea near Oregon.
        """
        if self.kind != GRID:
            return []
        out = []
        for square in sorted(self._in_play):
            position = maidenhead.to_latlon(square)
            if position is None:
                continue
            states = self._in_play.get(square, ())
            if "Alaska" in states:
                region = "Alaska"
            elif "Hawaii" in states:
                region = "Hawaii"
            else:
                region = "conus"
            out.append({"name": square, "lat": position[0], "lon": position[1],
                        "region": region, "states": list(states)})
        return out

    def edge(self, side: str) -> tuple[str, ...]:
        """States along one side of the country. Empty on the grid board."""
        return tuple(self._edges.get(side, ()))

    def set_edges(self, edges: dict) -> None:
        """Let a contest redefine where a crossing starts and stops."""
        for side, names in edges.items():
            if names:
                self._edges[side] = list(names)

    # -- questions the games ask ------------------------------------------

    def largest_group(self, owned: set[str]) -> list[str]:
        """The biggest run of touching territories somebody holds.

        This is the whole of connect mode: holding twelve scattered states is
        worth nothing, and holding four in a row is worth everything.
        """
        best: list[str] = []
        unseen = set(owned)
        while unseen:
            start = unseen.pop()
            group = [start]
            queue = deque([start])
            while queue:
                current = queue.popleft()
                for neighbour in self.neighbours(current):
                    if neighbour in unseen:
                        unseen.discard(neighbour)
                        group.append(neighbour)
                        queue.append(neighbour)
            if len(group) > len(best):
                best = group
        return sorted(best)

    def crossing(self, owned: set[str], start_side: str, end_side: str) -> list[str]:
        """The shortest unbroken chain of held territories from one side to the other.

        Empty if there isn't one yet. Returned as a path so the map can draw
        the line somebody actually completed.
        """
        starts = [s for s in self.edge(start_side) if s in owned]
        goals = {s for s in self.edge(end_side) if s in owned}
        if not starts or not goals:
            return []

        seen = set(starts)
        queue = deque((s, [s]) for s in starts)
        while queue:
            current, path = queue.popleft()
            if current in goals:
                return path
            for neighbour in self.neighbours(current):
                if neighbour in owned and neighbour not in seen:
                    seen.add(neighbour)
                    queue.append((neighbour, path + [neighbour]))
        return []

    def best_progress(self, owned: set[str], start_side: str, end_side: str) -> int:
        """How far towards a crossing somebody has got, as a chain length.

        Before anyone completes a crossing there still has to be something to
        show on the scoreboard, and "longest chain reaching back to the coast"
        is the honest measure of it.
        """
        starts = [s for s in self.edge(start_side) if s in owned]
        if not starts:
            return 0
        seen = set(starts)
        queue = deque((s, 1) for s in starts)
        best = 1
        while queue:
            current, depth = queue.popleft()
            best = max(best, depth)
            for neighbour in self.neighbours(current):
                if neighbour in owned and neighbour not in seen:
                    seen.add(neighbour)
                    queue.append((neighbour, depth + 1))
        return best
