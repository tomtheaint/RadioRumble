"""The page that explains the games.

Six games have existed for some time and none of them were reachable: the only
trace anywhere in the UI was a pill naming the current one. Worse, the two
hand-written lists of them -- modes.py's own module docstring and the comment
in contest.toml -- both described three of the six, so even reading the source
carefully would not have told you scarcity, connect and traverse exist.

These tests exist to stop that happening again. The page is assembled from the
mode classes themselves, and the test that matters is the one asserting every
registered mode appears: add a seventh game and it shows up with no page to
edit, or the suite fails.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from radiorumble.db import Database
from radiorumble.modes import MODES


@pytest.fixture
def client(monkeypatch, tmp_path):
    import app as application

    monkeypatch.setattr(application, "db", Database(tmp_path / "app.db"))
    monkeypatch.setattr(application.listener, "start", lambda: (True, "stub"))
    monkeypatch.setattr(application.ingest, "start", lambda: None)
    monkeypatch.setattr(application.ingest, "stop", lambda: None)
    with TestClient(application.app) as test_client:
        yield test_client, application


def test_the_page_is_public(client):
    """It explains the contest to spectators; a password would defeat it."""
    c, _ = client
    assert c.get("/modes").status_code == 200


def test_every_registered_game_is_described(client):
    """The point of building the page from the classes. A seventh game appears
    here on its own, or this fails and says so."""
    c, _ = client
    described = {g["key"] for g in c.get("/api/modes").json()["games"]}
    assert described == set(MODES)


def test_each_game_says_what_it_is_and_how_it_is_won(client):
    c, _ = client
    for g in c.get("/api/modes").json()["games"]:
        assert g["summary"], f"{g['key']} has no summary"
        assert g["objective"], f"{g['key']} has no objective"
        assert g["label"], f"{g['key']} has no label"


def test_the_descriptions_come_from_the_docstrings(client):
    """Rather than a copy in the route, which is what goes stale."""
    c, _ = client
    games = {g["key"]: g for g in c.get("/api/modes").json()["games"]}
    assert "grid squares" in games["classic"]["summary"].lower()
    assert "outside the united states" in games["dx"]["summary"].lower()
    # The multi-paragraph docstrings survive as separate paragraphs.
    assert len(games["conquest"]["detail"]) >= 2


def test_options_are_reported_with_defaults(client):
    c, _ = client
    games = {g["key"]: g for g in c.get("/api/modes").json()["games"]}
    dx_options = {o["name"]: o for o in games["dx"]["options"]}
    assert dx_options["points_per_dx"]["default"] == 3
    assert dx_options["count_domestic"]["default"] is False
    assert all(o["about"] for o in games["dx"]["options"])


def test_the_active_game_shows_what_is_really_set(client):
    """Not the documented default. Somebody reading this wants to know how
    tonight is scored, and contest.toml usually differs from the defaults."""
    c, application = client
    games = {g["key"]: g for g in c.get("/api/modes").json()["games"]}
    live = games[application.contest.mode]
    assert live["active"] and live["default"]
    for name, value in application.contest.mode_settings.items():
        if name in live["settings"]:
            assert live["settings"][name] == value


def test_a_match_naming_a_game_moves_the_active_marker(client):
    """The page should say what is being played, not what is configured."""
    from datetime import date, datetime, timezone
    from radiorumble.config import Match

    c, application = client
    before = application.contest.matches
    other = "dx" if application.contest.mode != "dx" else "classic"
    application.contest.matches = (
        Match(teams=("KU",), day=datetime.now(timezone.utc).date(), mode=other),)
    try:
        body = c.get("/api/modes").json()
        assert body["active"] == other
        games = {g["key"]: g for g in body["games"]}
        assert games[other]["active"]
        assert not games[application.contest.mode]["active"]
        # Still flagged as the contest's default even while another is played.
        assert games[application.contest.mode]["default"]
    finally:
        application.contest.matches = before


def test_the_shared_settings_are_listed(client):
    """The knobs that apply whichever game is running."""
    c, _ = client
    shared = {s["name"] for s in c.get("/api/modes").json()["shared"]}
    assert {"qso_points", "dupe_scope", "bands", "modes", "compete_as"} <= shared


def test_bonuses_are_listed_with_their_values(client):
    c, _ = client
    bonuses = c.get("/api/modes").json()["bonuses"]
    assert "enabled" in bonuses
    if bonuses["enabled"]:
        assert bonuses["items"]
        assert all(b["about"] for b in bonuses["items"])
