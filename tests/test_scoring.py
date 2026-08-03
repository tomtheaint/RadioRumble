"""Scoring rules, and the incremental read that feeds them.

Each test names the rule it protects, because these are the things somebody
will argue about at the event.
"""
from datetime import datetime, timedelta, timezone

import pytest

from radiorumble import adif
from radiorumble.config import Contest, Team
from radiorumble.ingest import LogTailer
from radiorumble.scoring import (
    REJECT_BAND,
    REJECT_DUPE,
    REJECT_UNROSTERED,
    REJECT_WINDOW,
    Scoreboard,
)

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
            Team("Kansas State", "KSU", "#512888", ("KE0VUM",)),
            Team("Kansas", "KU", "#0051BA", ("KD2FMW",)),
        ),
        log_file=None,
        grid_states={"EM19": ("Kansas", "Missouri"), "EN12": ("Nebraska",)},
    )
    defaults.update(overrides)
    return Contest(**defaults)


def qso(station="KE0VUM", call="W1ABC", band="20m", mode="FT8", grid="EM19", when=NOW):
    return adif.Qso(
        station=station, call=call, band=band, mode=mode,
        grid=grid, my_grid="EM19RF", when=when,
    )


@pytest.fixture
def board():
    return Scoreboard(make_contest())


# -- who counts ------------------------------------------------------------

def test_a_station_on_no_roster_is_ignored(board):
    """A collegiate log is mostly contacts with the rest of the world."""
    assert board.add(qso(station="W9XYZ")) == REJECT_UNROSTERED
    assert board.teams["KSU"].qsos == 0


def test_a_rostered_station_scores_for_its_school(board):
    assert board.add(qso()) is None
    assert board.teams["KSU"].qsos == 1
    assert board.teams["KU"].qsos == 0


# -- the clock -------------------------------------------------------------

def test_a_contact_before_the_start_does_not_count(board):
    assert board.add(qso(when=NOW - timedelta(hours=2))) == REJECT_WINDOW


def test_a_contact_after_the_end_does_not_count(board):
    assert board.add(qso(when=NOW + timedelta(hours=2))) == REJECT_WINDOW


def test_a_contact_with_no_timestamp_is_given_the_benefit_of_the_doubt(board):
    """Refusing a QSO over a missing optional field is worse than allowing it."""
    assert board.add(qso(when=None)) is None


# -- bands and modes -------------------------------------------------------

def test_a_band_outside_the_contest_does_not_count(board):
    assert board.add(qso(band="6m")) == REJECT_BAND


def test_an_empty_band_list_allows_everything():
    board = Scoreboard(make_contest(bands=frozenset()))
    assert board.add(qso(band="6m")) is None


# -- duplicates ------------------------------------------------------------

def test_working_the_same_station_twice_on_one_band_is_a_dupe(board):
    assert board.add(qso(call="W1ABC", band="20m")) is None
    assert board.add(qso(call="W1ABC", band="20m")) == REJECT_DUPE
    assert board.teams["KSU"].qsos == 1


def test_the_same_station_on_a_different_band_counts_again(board):
    """This is what makes changing bands worth doing."""
    assert board.add(qso(call="W1ABC", band="20m")) is None
    assert board.add(qso(call="W1ABC", band="40m")) is None
    assert board.teams["KSU"].qsos == 2


def test_two_schools_may_each_work_the_same_station():
    """Dupes are per team, not global — otherwise the fastest team blocks the rest."""
    board = Scoreboard(make_contest())
    assert board.add(qso(station="KE0VUM", call="W1ABC")) is None
    assert board.add(qso(station="KD2FMW", call="W1ABC")) is None


def test_contest_dupe_scope_ignores_the_band():
    board = Scoreboard(make_contest(dupe_scope="contest"))
    assert board.add(qso(call="W1ABC", band="20m")) is None
    assert board.add(qso(call="W1ABC", band="40m")) == REJECT_DUPE


# -- multipliers -----------------------------------------------------------

def test_each_new_grid_square_is_a_multiplier(board):
    board.add(qso(call="W1ABC", grid="EM19"))
    board.add(qso(call="W2ABC", grid="EN12"))
    assert board.teams["KSU"].multipliers == 2


def test_the_same_square_twice_is_one_multiplier(board):
    board.add(qso(call="W1ABC", grid="EM19"))
    board.add(qso(call="W2ABC", grid="EM19"))
    assert board.teams["KSU"].multipliers == 1


def test_a_square_spanning_two_states_credits_both(board):
    """Grid squares don't respect state lines; EM19 is Kansas and Missouri."""
    board.add(qso(grid="EM19"))
    assert board.teams["KSU"].states == {"Kansas", "Missouri"}


def test_score_is_points_times_multipliers(board):
    board.add(qso(call="W1ABC", grid="EM19"))
    board.add(qso(call="W2ABC", grid="EN12"))
    assert board.teams["KSU"].points == 2
    assert board.teams["KSU"].score == 4


def test_a_team_with_no_grids_still_scores_its_points(board):
    """Multipliers of zero would otherwise hold the first team at nil."""
    board.add(qso(grid=""))
    assert board.teams["KSU"].score == 1


# -- standings -------------------------------------------------------------

def test_standings_put_the_leader_first(board):
    board.add(qso(station="KD2FMW", call="W1ABC", grid="EM19"))
    board.add(qso(station="KD2FMW", call="W2ABC", grid="EN12"))
    board.add(qso(station="KE0VUM", call="W3ABC", grid="EM19"))
    standings = board.standings()
    assert standings[0]["abbr"] == "KU"
    assert standings[0]["position"] == 1


# -- incremental ingest ----------------------------------------------------

RECORD = (
    "<call:{n}>{call} <gridsquare:4>EM19 <mode:3>FT8 <qso_date:8>20260912 "
    "<time_on:6>183000 <band:3>20m <station_callsign:6>KE0VUM <eor>\n"
)


def record(call):
    return RECORD.format(n=len(call), call=call)


def test_reading_twice_does_not_score_the_same_qso_twice(tmp_path):
    """The original watcher re-read the tail of the file and scores climbed on their own."""
    path = tmp_path / "log.adi"
    path.write_text(record("W1ABC"))
    tailer = LogTailer(path)

    assert len(tailer.read_new()) == 1
    assert tailer.read_new() == []          # nothing appended: nothing new

    with path.open("a") as fh:
        fh.write(record("W2ABC"))
    new = tailer.read_new()
    assert [q.call for q in new] == ["W2ABC"]


def test_a_record_split_across_two_writes_is_scored_once_and_whole(tmp_path):
    path = tmp_path / "log.adi"
    full = record("W1ABC")
    half = len(full) // 2

    path.write_text(full[:half])
    tailer = LogTailer(path)
    assert tailer.read_new() == []          # incomplete: held back

    with path.open("a") as fh:
        fh.write(full[half:])
    new = tailer.read_new()
    assert [q.call for q in new] == ["W1ABC"]


def test_a_truncated_log_is_re_read_from_the_start(tmp_path):
    """A logger rotating its file looks exactly like this."""
    path = tmp_path / "log.adi"
    path.write_text(record("W1ABC") + record("W2ABC"))
    tailer = LogTailer(path)
    assert len(tailer.read_new()) == 2

    path.write_text(record("W3ABC"))        # shorter than before
    assert [q.call for q in tailer.read_new()] == ["W3ABC"]


def test_a_missing_log_file_is_not_an_error(tmp_path):
    """The contest may start before the logger has written anything."""
    assert LogTailer(tmp_path / "not-yet.adi").read_new() == []
