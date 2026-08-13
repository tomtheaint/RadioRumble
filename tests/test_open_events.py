"""Free-for-alls: events with no roster at all.

`compete_as = "operator"` was as close as this got, and it still needs
everybody listed in advance. A club night or anything advertised on a repeater
does not work that way — you find out who entered by seeing who turns up, and
the first contact somebody logs is the only moment we could learn they exist.

The unit of competition changes; nothing else does. Every game mode, the
schedule and the roll call all have to mean something when there is no team.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

import radiorumble.config as config
from radiorumble import adif
from radiorumble.config import Match
from radiorumble.scoring import REJECT_UNROSTERED, Scoreboard

NOON = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)

STRANGER = (
    "<call:4>W1AW <gridsquare:4>FN31 <mode:3>FT8 <qso_date:8>20260912 "
    "<time_on:6>160000 <band:3>20m <station_callsign:5>M0XYZ "
    "<my_gridsquare:6>IO91WM <eor>"
)


def _open_contest():
    contest = config.load()
    contest.compete_as = "open"
    contest.teams = config.split_into_operators(contest.teams)
    contest.__post_init__()
    return contest


# ------------------------------------------------------------------ admitting

def test_a_rostered_event_still_keeps_the_world_out():
    """The invariant the standings depend on: at a collegiate event most of
    the log is contacts with people who never entered."""
    board = Scoreboard(config.load())
    assert board.add(adif.parse(STRANGER)[0]) == REJECT_UNROSTERED


def test_an_open_event_enters_whoever_turns_up():
    contest = _open_contest()
    board = Scoreboard(contest)

    assert board.add(adif.parse(STRANGER)[0]) is None
    assert "M0XYZ" in board.teams
    assert board.teams["M0XYZ"].qsos == 1


def test_entering_somebody_twice_is_the_same_entry():
    contest = _open_contest()
    first = contest.admit("M0XYZ")
    assert contest.admit("m0xyz") is first
    assert sum(1 for t in contest.teams if t.abbr == "M0XYZ") == 1


def test_nobody_is_admitted_into_a_rostered_event():
    assert config.load().admit("M0XYZ") is None


def test_a_listed_entrant_keeps_the_name_and_colour_somebody_chose():
    """Listing teams in an open event is still useful: they are
    pre-registered, and everybody else is admitted on arrival."""
    contest = _open_contest()
    known = contest.teams[0]
    assert contest.admit(known.callsigns[0]) is known


def test_admitted_entrants_get_stable_colours():
    """The map is the scoreboard in half these games, so the same field must
    not repaint itself on a reload."""
    one = _open_contest()
    two = _open_contest()
    for call in ("M0XYZ", "DL1ABC", "JA1XYZ"):
        assert one.admit(call).color == two.admit(call).color


# --------------------------------------------------------------- across modes

@pytest.mark.parametrize("mode", ["classic", "conquest", "scarcity", "dx", "connect"])
def test_every_game_mode_scores_an_open_field(mode):
    """A mode is handed an entrant and asked what a contact is worth; it has
    never needed to know whether that entrant is a school or a stranger. This
    pins that it stays true."""
    contest = _open_contest()
    contest.mode = mode
    board = Scoreboard(contest)
    for qso in adif.parse(open("mock_contest_log.txt", encoding="utf-8",
                               errors="replace").read()):
        board.add(qso)

    snapshot = board.snapshot()
    assert snapshot["standings"], f"{mode} scored nobody"
    # More entrants than the five schools, because the strangers are in it too.
    assert len(snapshot["standings"]) > 5
    assert snapshot["contest"]["compete_as"] == "open"


def test_an_open_field_takes_territory_like_a_team_does():
    contest = _open_contest()
    contest.mode = "conquest"
    board = Scoreboard(contest)
    for qso in adif.parse(open("mock_contest_log.txt", encoding="utf-8",
                               errors="replace").read()):
        board.add(qso)

    owners = board.snapshot()["map"]["owners"]
    assert owners
    # Territory is held by callsigns now, not by school abbreviations.
    assert set(owners.values()) & {t.abbr for t in contest.teams}


# ----------------------------------------------------------------- the matches

def test_a_match_naming_nobody_is_a_free_for_all():
    """Because a match with nobody in it can only mean everybody."""
    assert Match(teams=()).is_open is True
    assert Match(teams=("KU",)).is_open is False
    assert Match(teams=("KU",), open=True).is_open is True


def test_an_open_night_puts_every_entrant_on_the_roll_call():
    contest = config.load()
    contest.matches = (Match(teams=(), day=date(2026, 9, 12), label="Open night"),)
    assert contest.open_now(NOON) is True
    assert set(contest.playing(NOON)) == {t.abbr for t in contest.teams}


def test_a_season_can_hold_an_open_night_among_team_matches():
    contest = config.load()
    contest.matches = (
        Match(teams=("KU", "KSU"), day=date(2026, 9, 12)),
        Match(teams=(), day=date(2026, 9, 19), label="Open night"),
    )
    assert contest.open_now(NOON) is False
    assert contest.playing(NOON) == ("KSU", "KU")

    later = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    assert contest.open_now(later) is True
    assert len(contest.playing(later)) == len(contest.teams)


def test_an_open_event_is_open_whatever_the_matches_say():
    contest = _open_contest()
    contest.matches = (Match(teams=("KU",), day=date(2026, 9, 12)),)
    assert contest.open_now(NOON) is True


def test_happening_reports_which_ones_are_running():
    contest = config.load()
    contest.matches = (
        Match(teams=("KU",), day=date(2026, 9, 12), label="Week 1"),
        Match(teams=("NEB",), day=date(2026, 9, 13), label="Week 2"),
    )
    assert [m.label for m in contest.happening(NOON)] == ["Week 1"]
