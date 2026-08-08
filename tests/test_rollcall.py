"""The roll call: who is expected, and who has actually turned up.

Two questions, and they are different ones. *Are my team checked in?* can only
be answered from a roster, because the operator somebody is looking for is
precisely the one who has never sent anything — the listener knows nothing
about them by definition. *Who else is out there?* is answered by what was
heard.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from radiorumble.config import Match

NOON = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(monkeypatch):
    import app as application

    monkeypatch.setattr(application.listener, "start", lambda: (True, "stub"))
    monkeypatch.setattr(application.ingest, "start", lambda: None)
    monkeypatch.setattr(application.ingest, "stop", lambda: None)
    with TestClient(application.app) as test_client:
        yield test_client, application


# --------------------------------------------------------------- the fixtures

def test_with_no_fixture_list_everybody_is_playing(client):
    """Which is what a one-off event means, and what this app was before there
    was any reason to know otherwise."""
    _c, application = client
    assert application.contest.matches == ()
    assert set(application.contest.playing()) == {t.abbr for t in application.contest.teams}


def test_a_fixture_narrows_the_roll_call_to_the_teams_playing(client, monkeypatch):
    _c, application = client
    monkeypatch.setattr(application.contest, "matches",
                        (Match(teams=("KU", "KSU"), day=date(2026, 9, 12)),))
    assert application.contest.playing(NOON) == ("KSU", "KU")


def test_a_fixture_on_another_day_does_not_count(client, monkeypatch):
    _c, application = client
    monkeypatch.setattr(application.contest, "matches",
                        (Match(teams=("KU",), day=date(2026, 9, 13)),))
    assert application.contest.playing(NOON) == ()


def test_a_window_is_used_when_a_day_is_not_precise_enough(client, monkeypatch):
    _c, application = client
    fixture = Match(teams=("NEB",),
                    start=datetime(2026, 9, 12, 18, 0, tzinfo=timezone.utc),
                    end=datetime(2026, 9, 12, 20, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(application.contest, "matches", (fixture,))
    assert application.contest.playing(NOON) == ()
    assert application.contest.playing(
        datetime(2026, 9, 12, 19, 0, tzinfo=timezone.utc)) == ("NEB",)


def test_the_roll_call_keeps_the_order_the_scoreboard_uses(client, monkeypatch):
    """Fixtures are written in whatever order somebody thought of them; the
    page should not reshuffle the teams because of that."""
    _c, application = client
    monkeypatch.setattr(application.contest, "matches",
                        (Match(teams=("OSU", "KSU")),))
    order = [t.abbr for t in application.contest.teams]
    playing = list(application.contest.playing(NOON))
    assert playing == [a for a in order if a in {"OSU", "KSU"}]


# ------------------------------------------------------------- what is served

def test_an_operator_who_has_never_reported_is_still_listed(client):
    """The whole point. Somebody checking in is looking for the roster entry
    that has no station behind it, and nothing the listener holds can produce
    one."""
    test_client, _app = client
    body = test_client.get("/api/stations").json()

    everyone = [o for t in body["teams"] for o in t["operators"]]
    assert everyone, "the roster should be listed even with nothing heard"
    assert all(o["heard"] is False for o in everyone)
    assert all(o["live"] is False for o in everyone)


def test_a_team_is_connected_when_any_one_of_its_stations_is(client):
    """A school with four operators is on the air if one of them is."""
    test_client, application = client
    team = application.contest.teams[0]
    application.listener.forget()
    application.listener._stations.clear()
    _hear(application, team.callsigns[0])

    body = test_client.get("/api/stations").json()
    row = next(t for t in body["teams"] if t["abbr"] == team.abbr)
    assert row["connected"] is True
    assert row["live_operators"] == 1
    assert next(o for o in row["operators"] if o["call"] == team.callsigns[0])["heard"]


def test_a_station_on_a_roster_is_not_also_listed_as_a_stranger(client):
    """Otherwise every rostered operator appears twice and the second list
    stops meaning "everyone else"."""
    test_client, application = client
    team = application.contest.teams[0]
    application.listener._stations.clear()
    _hear(application, team.callsigns[0])
    _hear(application, "DL1ABC")

    body = test_client.get("/api/stations").json()
    others = [o["call"] for o in body["others"]]
    assert others == ["DL1ABC"]


def test_teams_carry_the_flag_the_page_filters_on(client):
    test_client, _app = client
    body = test_client.get("/api/stations").json()
    assert all("playing" in t for t in body["teams"])
    assert any(t["playing"] for t in body["teams"])


def _hear(application, call):
    """Put one station into the listener without opening a socket."""
    import struct

    def s(text):
        raw = text.encode()
        return struct.pack(">I", len(raw)) + raw

    packet = (struct.pack(">III", 0xADBCCBDA, 3, 1) + s("WSJT-X")
              + struct.pack(">Q", 14_074_000) + s("FT8") + s("") + s("-10")
              + s("FT8") + struct.pack(">?", True) + struct.pack(">?", False)
              + struct.pack(">?", True) + struct.pack(">II", 1500, 1200)
              + s(call) + s("EM19RF") + s(""))
    application.listener._handle(packet, "10.0.0.5", 2237)
