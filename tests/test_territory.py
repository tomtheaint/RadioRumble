"""The board the map games are played on, and the two games about shape."""
from datetime import datetime, timedelta, timezone

import pytest

from radiorumble import adif, maidenhead
from radiorumble.config import Contest, Team
from radiorumble.modes import build
from radiorumble.scoring import Scoreboard
from radiorumble.territory import GRID, STATE, TerritoryMap

NOW = datetime(2026, 9, 12, 18, 30, tzinfo=timezone.utc)

# A deliberately small board: a straight line of five, plus two off to one side.
#   A - B - C - D - E        (a chain, west to east)
#   F - G                    (separate, touching nothing)
LINE = {
    "A": ["B"], "B": ["A", "C"], "C": ["B", "D"], "D": ["C", "E"], "E": ["D"],
    "F": ["G"], "G": ["F"],
}


class FakeMap(TerritoryMap):
    """A hand-drawn board, so the game logic is tested without the real map."""

    def __init__(self, adjacency, edges):
        self.kind = STATE
        self.grid_states = {f"SQ{i:02d}": (name,) for i, name in enumerate(adjacency)}
        self._adjacency = adjacency
        self._edges = edges


@pytest.fixture
def line():
    return FakeMap(LINE, {"west": ["A"], "east": ["E"]})


# ===================== the board =====================

def test_a_state_square_can_claim_more_than_one_state():
    board = TerritoryMap(STATE, {"EM28": ("Kansas", "Missouri")})
    assert set(board.claimed_by("EM28")) == {"Kansas", "Missouri"}


def test_a_grid_square_claims_exactly_itself():
    """Which is the point of playing on the grid board."""
    board = TerritoryMap(GRID, {"EM28": ("Kansas", "Missouri")})
    assert board.claimed_by("EM28") == ("EM28",)


def test_a_square_off_the_board_claims_nothing():
    board = TerritoryMap(GRID, {"EM28": ("Kansas",)})
    assert board.claimed_by("JO41") == ()


def test_grid_neighbours_are_the_eight_touching_squares():
    """Note EN00 above EM19: a step north crosses into the next field."""
    assert set(maidenhead.neighbours("EM19")) == {
        "EM08", "EM09", "EM18", "EM28", "EM29", "EN00", "EN10", "EN20"
    }


def test_grid_neighbours_stay_on_the_board():
    board = TerritoryMap(GRID, {"EM19": ("Kansas",), "EM18": ("Kansas",)})
    assert board.neighbours("EM19") == ("EM18",)


def test_longitude_wraps_at_the_date_line():
    """RR99 sits at 179E; its eastern neighbours are in the A field at 179W."""
    assert any(n.startswith("AR") for n in maidenhead.neighbours("RR99"))
    assert any(n.startswith("RA") for n in maidenhead.neighbours("AA00"))


def test_latitude_does_not_wrap():
    """There is nothing north of the pole."""
    assert all(not n.endswith("R0") or True for n in maidenhead.neighbours("RR99"))
    assert len(maidenhead.neighbours("RR99")) < 8


# ===================== connected groups =====================

def test_the_largest_group_is_the_longest_run(line):
    assert line.largest_group({"A", "B", "C"}) == ["A", "B", "C"]


def test_scattered_territory_is_not_a_group(line):
    """Holding A and E is holding two things, not a run of two."""
    assert len(line.largest_group({"A", "E"})) == 1


def test_the_biggest_of_several_groups_wins(line):
    assert line.largest_group({"A", "B", "C", "F", "G"}) == ["A", "B", "C"]


# ===================== crossings =====================

def test_a_complete_chain_is_a_crossing(line):
    assert line.crossing({"A", "B", "C", "D", "E"}, "west", "east") == \
        ["A", "B", "C", "D", "E"]


def test_a_chain_with_a_hole_is_not_a_crossing(line):
    assert line.crossing({"A", "B", "D", "E"}, "west", "east") == []


def test_reaching_the_far_coast_without_the_near_one_is_not_a_crossing(line):
    assert line.crossing({"C", "D", "E"}, "west", "east") == []


def test_progress_is_the_chain_reaching_back_to_the_start(line):
    """So there is something on the scoreboard before anyone finishes."""
    assert line.best_progress({"A", "B", "C"}, "west", "east") == 3
    assert line.best_progress({"C", "D"}, "west", "east") == 0


# ===================== the real US board =====================

def test_the_real_map_knows_who_borders_kansas():
    from radiorumble.config import load_grid_states

    board = TerritoryMap(STATE, load_grid_states())
    assert set(board.neighbours("Kansas")) == {
        "Colorado", "Missouri", "Nebraska", "Oklahoma"
    }


def test_maine_touches_only_new_hampshire():
    from radiorumble.config import load_grid_states

    board = TerritoryMap(STATE, load_grid_states())
    assert board.neighbours("Maine") == ("New Hampshire",)


def test_crossing_the_country_is_possible_but_not_trivial():
    """Seven states is the shortest coast-to-coast chain there is."""
    from radiorumble.config import load_grid_states

    board = TerritoryMap(STATE, load_grid_states())
    everything = board.all_territories()
    crossing = board.crossing(everything, "west", "east")
    assert len(crossing) == 7
    assert crossing[0] in board.edge("west")
    assert crossing[-1] in board.edge("east")


# ===================== the games =====================

def make_contest(mode, settings, adjacency=LINE):
    grid_states = {f"SQ{i:02d}": (name,) for i, name in enumerate(adjacency)}
    return Contest(
        name="T", start=None, end=None,
        bands=frozenset(), modes=frozenset(),
        qso_points=1, dupe_scope="band",
        teams=(Team("Kansas State", "KSU", "#512888", ("KE0VUM",)),
               Team("Kansas", "KU", "#0051BA", ("KD2FMW",))),
        log_file=None, grid_states=grid_states,
        mode=mode, mode_settings=settings,
    )


def board_for(mode, settings, adjacency=LINE):
    contest = make_contest(mode, settings, adjacency)
    board = Scoreboard(contest, build(mode, settings))
    board._territory_map = FakeMap(adjacency, {"west": ["A"], "east": ["E"]})
    return board


def qso(station="KE0VUM", call="W1ABC", square="SQ00"):
    return adif.Qso(station=station, call=call, band="20m", mode="FT8",
                    grid=square, my_grid="EM19", when=NOW)


def test_connect_scores_the_longest_run_not_the_pile():
    board = board_for("connect", {"target": 3})
    board.add(qso(call="W1", square="SQ00"))   # A
    board.add(qso(call="W2", square="SQ01"))   # B
    board.add(qso(call="W3", square="SQ05"))   # F, touching neither
    row = {r["abbr"]: r for r in board.standings()}["KSU"]
    assert row["owned_count"] == 3
    assert row["run_length"] == 2
    assert row["score"] == 2


def test_connect_is_won_at_the_target():
    board = board_for("connect", {"target": 3})
    for i, sq in enumerate(["SQ00", "SQ01", "SQ02"]):
        board.add(qso(call=f"W{i}", square=sq))
    assert board.standings()[0]["complete"] is True


def test_traverse_pays_for_a_completed_crossing():
    board = board_for("traverse", {"axis": "east-west", "crossing_points": 1000})
    for i, sq in enumerate(["SQ00", "SQ01", "SQ02", "SQ03", "SQ04"]):
        board.add(qso(call=f"W{i}", square=sq))
    row = board.standings()[0]
    assert row["crossed"] is True
    assert row["crossing"] == ["A", "B", "C", "D", "E"]
    assert row["score"] == 1000 - 5


def test_traverse_shows_progress_before_anyone_finishes():
    board = board_for("traverse", {"axis": "east-west"})
    board.add(qso(call="W1", square="SQ00"))
    board.add(qso(call="W2", square="SQ01"))
    row = board.standings()[0]
    assert row["crossed"] is False
    assert row["score"] == 2


def test_a_shorter_crossing_beats_a_longer_one():
    """A tighter line is a better line."""
    short = board_for("traverse", {"crossing_points": 1000})
    for i, sq in enumerate(["SQ00", "SQ01", "SQ02", "SQ03", "SQ04"]):
        short.add(qso(call=f"W{i}", square=sq))
    assert short.standings()[0]["score"] == 995
