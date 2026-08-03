"""Cross-checking, voiding, chasers, and competing as individuals.

The rules these protect are the ones that decide whether somebody's score
stands, so each test names the claim it is defending.
"""
from datetime import datetime, timedelta, timezone

import pytest

from radiorumble import adif
from radiorumble.config import Contest, Team, split_into_operators
from radiorumble.modes import build
from radiorumble.scoring import REJECT_VOID, Scoreboard
from radiorumble.store import QsoStore
from radiorumble.verify import NIL, UNMATCHED, VERIFIED, CrossCheck

NOW = datetime(2026, 9, 12, 18, 30, tzinfo=timezone.utc)


def make_contest(**overrides):
    defaults = dict(
        name="Test Rumble",
        start=NOW - timedelta(hours=1),
        end=NOW + timedelta(hours=1),
        bands=frozenset({"20m", "40m"}),
        modes=frozenset({"FT8"}),
        qso_points=1,
        dupe_scope="band",
        teams=(
            Team("Kansas State", "KSU", "#512888", ("KE0VUM",), grid="EM19"),
            Team("Kansas", "KU", "#0051BA", ("KD2FMW",), grid="EM28"),
        ),
        log_file=None,
        grid_states={"EM19": ("Kansas",), "EM28": ("Kansas", "Missouri")},
        mode="classic",
        mode_settings={},
    )
    defaults.update(overrides)
    return Contest(**defaults)


def qso(station, call, band="20m", when=NOW, grid="EM19", source=""):
    return adif.Qso(station=station, call=call, band=band, mode="FT8",
                    grid=grid, my_grid="EM19RF", when=when, source=source)


# ===================== cross-checking =====================

def test_a_contact_in_both_logs_is_verified():
    a = qso("KE0VUM", "KD2FMW", source="KE0VUM.adi")
    b = qso("KD2FMW", "KE0VUM", source="KD2FMW.adi")
    assert CrossCheck([a, b]).status(a) == VERIFIED


def test_clocks_may_disagree_a_little():
    """Two loggers record the ends of a sequence that takes about a minute."""
    a = qso("KE0VUM", "KD2FMW", when=NOW)
    b = qso("KD2FMW", "KE0VUM", when=NOW + timedelta(seconds=90))
    assert CrossCheck([a, b], match_minutes=3).status(a) == VERIFIED


def test_clocks_may_not_disagree_a_lot():
    a = qso("KE0VUM", "KD2FMW", when=NOW)
    b = qso("KD2FMW", "KE0VUM", when=NOW + timedelta(minutes=30))
    assert CrossCheck([a, b], match_minutes=3).status(a) == NIL


def test_the_two_ends_must_agree_about_the_band():
    a = qso("KE0VUM", "KD2FMW", band="20m")
    b = qso("KD2FMW", "KE0VUM", band="40m")
    assert CrossCheck([a, b]).status(a) == NIL


def test_a_contact_the_other_log_lacks_is_nil():
    """They submitted a log and this contact is not in it. The one real signal."""
    a = qso("KE0VUM", "KD2FMW")
    theirs = qso("KD2FMW", "W9ZZZ")
    assert CrossCheck([a, theirs]).status(a) == NIL


def test_a_contact_with_a_non_entrant_is_unmatched_not_suspicious():
    """Most of a collegiate log is people who will never submit anything.

    Treating those as suspect would punish a team for working exactly the
    people the contest wants them to work.
    """
    a = qso("KE0VUM", "W9ZZZ")
    assert CrossCheck([a]).status(a) == UNMATCHED


def test_only_stations_that_submitted_can_contradict_anyone():
    check = CrossCheck([qso("KE0VUM", "W9ZZZ")])
    assert check.submitters == {"KE0VUM"}


# ===================== the store =====================

def test_the_same_contact_read_twice_is_only_held_once():
    """A log re-read after a rotation must not double everything."""
    store = QsoStore()
    q = qso("KE0VUM", "W1ABC")
    assert store.extend([q]) == 1
    assert store.extend([q]) == 0
    assert len(store.qsos) == 1


def test_a_rewritten_log_can_be_forgotten_and_re_read():
    store = QsoStore()
    store.extend([qso("KE0VUM", "W1ABC", source="a.adi"),
                  qso("KD2FMW", "W2ABC", source="b.adi")])
    store.reset_source("a.adi")
    assert [q.station for q in store.qsos] == ["KD2FMW"]


def test_a_contact_keeps_its_identity_across_a_re_read():
    """Voids are keyed by this, so it cannot depend on position in a file."""
    assert qso("KE0VUM", "W1ABC").uid == qso("KE0VUM", "W1ABC").uid
    assert qso("KE0VUM", "W1ABC").uid != qso("KE0VUM", "W2ABC").uid


def test_voids_survive_a_restart(tmp_path):
    path = tmp_path / "voided.json"
    store = QsoStore(voids_path=path)
    store.void("abc123", "made up")
    assert QsoStore(voids_path=path).voids == {"abc123": "made up"}


def test_a_corrupt_void_file_does_not_stop_the_contest(tmp_path):
    path = tmp_path / "voided.json"
    path.write_text("{not json")
    assert QsoStore(voids_path=path).voids == {}


# ===================== voiding affects the score =====================

def test_a_voided_contact_stops_counting():
    board = Scoreboard(make_contest(), build("classic"))
    store = QsoStore()
    store.extend([qso("KE0VUM", "W1ABC"), qso("KE0VUM", "W2ABC")])
    store.void(store.qsos[0].uid, "unverifiable")

    board.score_store(store, CrossCheck(store.qsos))
    assert board.teams["KSU"].qsos == 1
    assert board.rejected[REJECT_VOID] == 1


def test_an_unverified_contact_still_counts():
    """Verification informs an official; it does not silently rewrite a score."""
    board = Scoreboard(make_contest(), build("classic"))
    store = QsoStore()
    store.extend([qso("KE0VUM", "W1ABC")])
    board.score_store(store, CrossCheck(store.qsos))
    assert board.teams["KSU"].qsos == 1
    assert board.teams["KSU"].verification[UNMATCHED] == 1


# ===================== chasers =====================

def test_non_entrants_are_ranked_by_how_much_they_worked_the_teams():
    board = Scoreboard(make_contest(), build("classic"))
    board.add(qso("KE0VUM", "W9AAA", band="20m"))
    board.add(qso("KE0VUM", "W9AAA", band="40m"))
    board.add(qso("KD2FMW", "W9BBB", band="20m"))
    rows = board.chaser_board()
    assert rows[0]["call"] == "W9AAA"
    assert rows[0]["qsos"] == 2


def test_an_entrant_is_not_listed_as_a_chaser():
    board = Scoreboard(make_contest(), build("classic"))
    board.add(qso("KE0VUM", "KD2FMW"))
    assert [r["call"] for r in board.chaser_board()] == []


def test_working_every_team_is_flagged_as_a_sweep():
    """The thing to chase if you aren't competing."""
    board = Scoreboard(make_contest(), build("classic"))
    board.add(qso("KE0VUM", "W9AAA"))
    board.add(qso("KD2FMW", "W9AAA"))
    (row,) = board.chaser_board()
    assert row["teams"] == 2
    assert row["sweep"] is True


def test_working_some_teams_is_not_a_sweep():
    board = Scoreboard(make_contest(), build("classic"))
    board.add(qso("KE0VUM", "W9AAA"))
    assert board.chaser_board()[0]["sweep"] is False


# ===================== single operators =====================

def test_a_school_splits_into_one_entry_per_operator():
    teams = (Team("Kansas State", "KSU", "#512888", ("KE0VUM", "W0AAA")),)
    solo = split_into_operators(teams)
    assert [t.abbr for t in solo] == ["KE0VUM", "W0AAA"]
    assert all(t.affiliation == "Kansas State" for t in solo)


def test_operators_from_one_school_get_different_colours():
    """Two dots the same colour on a map are two dots you cannot tell apart."""
    teams = (Team("Kansas State", "KSU", "#512888", ("KE0VUM", "W0AAA")),)
    solo = split_into_operators(teams)
    assert solo[0].color != solo[1].color


def test_a_one_operator_school_keeps_its_own_colours():
    teams = (Team("Kansas State", "KSU", "#512888", ("KE0VUM",)),)
    (solo,) = split_into_operators(teams)
    assert solo.color == "#512888"


def test_operators_inherit_the_school_location():
    teams = (Team("Kansas State", "KSU", "#512888", ("KE0VUM", "W0AAA"), grid="EM19"),)
    assert all(t.grid == "EM19" for t in split_into_operators(teams))


def test_individuals_compete_against_each_other():
    contest = make_contest(teams=split_into_operators(make_contest().teams))
    board = Scoreboard(contest, build("classic"))
    board.add(qso("KE0VUM", "W1ABC"))
    assert board.teams["KE0VUM"].qsos == 1
    assert "KSU" not in board.teams


# ===================== team locations =====================

def test_a_team_grid_becomes_a_position_on_the_map():
    team = Team("Kansas State", "KSU", "#512888", ("KE0VUM",), grid="EM19")
    assert team.position == (39.5, -97.0)


def test_a_team_with_no_grid_is_simply_not_drawn():
    assert Team("X", "X", "#fff", ("W1A",)).position is None


def test_the_snapshot_carries_every_known_home():
    board = Scoreboard(make_contest(), build("classic"))
    homes = {h["abbr"]: h["grid"] for h in board.snapshot()["homes"]}
    assert homes == {"KSU": "EM19", "KU": "EM28"}


# ===================== scarcity =====================

def test_states_get_more_valuable_as_the_map_empties():
    grid_states = {f"E{n:02d}": (f"State{n}",) for n in range(10)}
    contest = make_contest(mode="scarcity", grid_states=grid_states)
    board = Scoreboard(contest, build("scarcity", {"base_points": 10, "step_points": 5}))

    board.add(qso("KE0VUM", "W1ABC", grid="E00"))
    board.add(qso("KE0VUM", "W2ABC", grid="E01"))
    assert board.state_value["State0"] == 10
    assert board.state_value["State1"] == 15


def test_a_state_banked_early_keeps_its_early_price():
    """The reward is for taking awkward states while they are still awkward."""
    grid_states = {f"E{n:02d}": (f"State{n}",) for n in range(5)}
    contest = make_contest(mode="scarcity", grid_states=grid_states)
    board = Scoreboard(contest, build("scarcity", {"base_points": 10, "step_points": 5}))

    board.add(qso("KE0VUM", "W1ABC", grid="E00"))
    first = board.state_value["State0"]
    for i, g in enumerate(["E01", "E02", "E03"], start=2):
        board.add(qso("KD2FMW", f"W{i}ABC", grid=g))
    assert board.state_value["State0"] == first


def test_scarcity_score_is_what_each_state_cost():
    grid_states = {f"E{n:02d}": (f"State{n}",) for n in range(5)}
    contest = make_contest(mode="scarcity", grid_states=grid_states)
    board = Scoreboard(contest, build("scarcity", {"base_points": 10, "step_points": 5}))
    board.add(qso("KE0VUM", "W1ABC", grid="E00"))   # worth 10
    board.add(qso("KE0VUM", "W2ABC", grid="E01"))   # worth 15
    assert board.mode.score_for(board.teams["KSU"], board) == 25


def test_scarcity_never_lets_a_state_change_hands():
    """A price locked in at the claim is meaningless if the state can be taken."""
    grid_states = {"E00": ("State0",)}
    contest = make_contest(mode="scarcity", grid_states=grid_states)
    board = Scoreboard(contest, build("scarcity", {}))
    board.add(qso("KE0VUM", "W1ABC", grid="E00"))
    board.add(qso("KD2FMW", "W2ABC", grid="E00"))
    board.add(qso("KD2FMW", "W3ABC", grid="E00"))
    assert board.owners["State0"] == "KSU"
