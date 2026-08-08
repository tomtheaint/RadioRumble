"""How many people can enter a free-for-all.

The answer used to be "a few hundred, and then the page stops working" — not
because scoring was slow but because the whole standings table went down the
websocket every time the log grew. Three thousand callsigns is 1.4MB a time.

So the cap is on what is *sent*, never on who is scored: everybody below it
still holds territory, still counts towards every total, and can still find
themselves.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import radiorumble.config as config
from radiorumble.adif import Qso
from radiorumble.scoring import Scoreboard

WHEN = datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc)


def field(size, per=3):
    """An open event with `size` entrants who have each worked `per` people."""
    contest = config.load()
    contest.compete_as = "open"
    contest.teams = ()
    contest.standings_limit = 15
    contest.__post_init__()
    board = Scoreboard(contest)
    for i in range(size):
        for j in range(per):
            board.add(Qso(station=f"K{i:04d}A", call=f"DX{i}{j}", band="20m",
                          mode="FT8", grid=f"EM{i % 10}{j % 10}", my_grid="EM19",
                          when=WHEN))
    return board


def test_everybody_is_scored_however_many_turn_up():
    board = field(400)
    assert len(board.teams) == 400
    assert board.snapshot(limit=15)["entrants"] == 400


def test_only_the_top_is_sent():
    snapshot = field(400).snapshot(limit=15)
    assert len(snapshot["standings"]) == 15
    assert snapshot["entrants"] == 400


def test_the_payload_stops_growing_with_the_field():
    """The whole point. If this fails, the limit on how many people can enter
    is the size of a websocket frame."""
    small = len(json.dumps(field(50).snapshot(limit=15)))
    large = len(json.dumps(field(800).snapshot(limit=15)))
    # Some growth is honest — the map holds more owners — but not sixteen times.
    assert large < small * 2, f"{small} -> {large} bytes"


def test_a_place_is_a_place_in_the_whole_field(): 
    """Row 400 has to say 400, or the cap turns a leaderboard into a lie."""
    board = field(300)
    rows = board.standings(limit=10, offset=200)
    assert [r["position"] for r in rows] == list(range(201, 211))


def test_anybody_can_be_found_below_the_cut():
    board = field(300)
    rows = board.standings(limit=20, query="K0250A")
    assert rows and rows[0]["abbr"] == "K0250A"
    assert rows[0]["position"] > 0


def test_searching_does_not_renumber_anybody():
    board = field(300)
    everyone = {r["abbr"]: r["position"] for r in board.standings()}
    for row in board.standings(limit=20, query="K02"):
        assert row["position"] == everyone[row["abbr"]]


def test_the_map_only_carries_colours_it_uses():
    """Otherwise the map payload grows with the field too, and capping the
    standings would have moved the problem rather than fixed it."""
    board = field(400)
    payload = board.snapshot(limit=15).get("map")
    if payload is None:
        pytest.skip("this mode has no map")
    assert set(payload["colors"]) == set(payload["owners"].values())
    assert len(payload["colors"]) <= payload["total_states"]


def test_no_limit_sends_everybody():
    """Which is the right answer for a handful of schools."""
    assert len(field(20).snapshot(limit=0)["standings"]) == 20


def test_a_colour_follows_the_callsign_not_the_order_it_arrived():
    """The logs are re-read from scratch whenever anything changes. An entrant
    whose colour moved because a file was rotated cannot be followed on a map."""
    forwards = config.load()
    forwards.compete_as = "open"
    backwards = config.load()
    backwards.compete_as = "open"

    calls = ["K1AAA", "K2BBB", "K3CCC", "K4DDD"]
    first = {c: forwards.admit(c).color for c in calls}
    second = {c: backwards.admit(c).color for c in reversed(calls)}
    assert first == second
