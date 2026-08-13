"""The schedule: what is on, what is next, and who may change it.

Match scheduling existed before this -- the model, the rules, `playing()` --
but only as something you got by hand-editing contest.toml, with no page to
see it on and no way to add one. These cover the half that was missing, and
the join between the two halves: a match from the file and a match from the
form have to behave identically once loaded, or the roll call means different
things depending on where its matches came from.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from radiorumble import matches as matchlib
from radiorumble.config import Match
from radiorumble.db import Database

NOON = datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "t.db")


@pytest.fixture
def client(monkeypatch, tmp_path):
    import app as application

    fresh = Database(tmp_path / "app.db")
    monkeypatch.setattr(application, "db", fresh)
    monkeypatch.setattr(application.listener, "start", lambda: (True, "stub"))
    monkeypatch.setattr(application.ingest, "start", lambda: None)
    monkeypatch.setattr(application.ingest, "stop", lambda: None)
    # The contest is a module-level object shared by every test in the process,
    # so put its schedule back the way it was found.
    before = application.contest.matches
    matchlib.apply(application.contest, fresh)
    with TestClient(application.app) as test_client:
        test_client.post("/api/auth/setup", json={"password": "rumble2026"})
        yield test_client, application
    application.contest.matches = before


# ------------------------------------------------------------------ the model

def test_a_day_match_begins_at_midnight_utc():
    """Not a plausible-looking evening hour. The match does not carry a time,
    and inventing one would be a fact the page made up."""
    m = Match(teams=("KU",), day=date(2026, 9, 12))
    assert m.begins() == datetime(2026, 9, 12, tzinfo=timezone.utc)


def test_a_dateless_match_is_always_on_and_never_upcoming():
    m = Match(teams=("KU",))
    assert m.on(NOON)
    assert not m.over(NOON)
    assert m.begins() is None


def test_over_is_not_the_same_as_not_on():
    """A match next week is neither. Without that distinction a season's
    worth of played matches sits at the top of the list forever."""
    later = Match(teams=("KU",), day=date(2026, 9, 19))
    assert not later.on(NOON)
    assert not later.over(NOON)

    done = Match(teams=("KU",), day=date(2026, 9, 5))
    assert not done.on(NOON)
    assert done.over(NOON)


def test_upcoming_is_soonest_first(db):
    from radiorumble import config
    contest = config.load()
    contest.matches = (
        Match(teams=("C",), day=date(2026, 10, 1), label="third"),
        Match(teams=("A",), day=date(2026, 9, 14), label="first"),
        Match(teams=("B",), day=date(2026, 9, 20), label="second"),
    )
    assert [m.label for m in contest.upcoming(NOON)] == ["first", "second", "third"]


def test_past_is_most_recent_first():
    from radiorumble import config
    contest = config.load()
    contest.matches = (
        Match(teams=("A",), day=date(2026, 9, 1), label="older"),
        Match(teams=("B",), day=date(2026, 9, 10), label="newer"),
    )
    assert [m.label for m in contest.past(NOON)] == ["newer", "older"]


# ------------------------------------------------------------------- storage

def test_a_stored_match_reads_back_the_same(db):
    db.add_match(label="Week 1", teams=["KU", "KSU"], day=date(2026, 9, 12))
    (m,) = matchlib.stored_matches(db)
    assert m.label == "Week 1"
    assert m.teams == ("KU", "KSU")
    assert m.day == date(2026, 9, 12)
    assert not m.is_open


def test_naming_no_teams_means_an_open_night(db):
    """The same rule the TOML loader applies. A match with nobody in it can
    only mean everybody, whichever way it was written."""
    db.add_match(label="Open", teams=[], day=date(2026, 9, 26))
    (m,) = matchlib.stored_matches(db)
    assert m.is_open


def test_teams_are_upper_cased_on_the_way_in(db):
    db.add_match(teams=["ku", "ksu"], day=date(2026, 9, 12))
    (m,) = matchlib.stored_matches(db)
    assert m.teams == ("KU", "KSU")


def test_a_naive_timestamp_is_read_as_utc(db):
    """Every clock in this app is UTC. A bare timestamp meaning local time
    would be a different match depending on which machine wrote it."""
    db.conn.execute(
        "INSERT INTO matches (label, teams, day, start_at, end_at, is_open, created_at) "
        "VALUES ('x', '[\"KU\"]', NULL, '2026-09-12T18:00:00', '2026-09-12T20:00:00', 0, 'now')")
    db.conn.commit()
    (m,) = matchlib.stored_matches(db)
    assert m.start.tzinfo is not None
    assert m.start == datetime(2026, 9, 12, 18, tzinfo=timezone.utc)


def test_file_and_stored_matches_merge(db):
    from radiorumble import config
    contest = config.load()
    contest.matches = (Match(teams=("NEB",), day=date(2026, 9, 12), label="from the file"),)
    db.add_match(label="from the form", teams=["KU"], day=date(2026, 9, 12))

    matchlib.apply(contest, db)
    assert {m.label for m in contest.matches} == {"from the file", "from the form"}


def test_applying_twice_does_not_duplicate(db):
    """`apply` runs again after every add and delete."""
    from radiorumble import config
    contest = config.load()
    contest.matches = (Match(teams=("NEB",), day=date(2026, 9, 12)),)
    db.add_match(teams=["KU"], day=date(2026, 9, 12))
    matchlib.apply(contest, db)
    matchlib.apply(contest, db)
    matchlib.apply(contest, db)
    assert len(contest.matches) == 2


# ---------------------------------------------------------------- the routes

def test_the_list_is_public(client):
    c, _ = client
    c.post("/api/auth/logout")
    assert c.get("/api/matches").status_code == 200


def test_adding_one_requires_signing_in(client):
    c, _ = client
    c.post("/api/auth/logout")
    r = c.post("/api/matches", json={"teams": ["KU"], "day": "2026-09-12"})
    assert r.status_code == 403


def test_add_then_it_appears(client):
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:2]
    r = c.post("/api/matches", json={"label": "Week 1", "teams": teams, "day": "2026-09-12"})
    assert r.status_code == 201

    body = c.get("/api/matches").json()
    labels = [f["label"] for f in body["now"] + body["upcoming"] + body["past"]]
    assert "Week 1" in labels


def test_a_match_with_no_date_is_refused(client):
    """It would be permanently on, hiding every other match. A hand-written
    TOML file may say that deliberately; a form submission almost never does."""
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:1]
    r = c.post("/api/matches", json={"label": "whenever", "teams": teams})
    assert r.status_code == 400
    assert "date" in r.json()["detail"].lower()


def test_an_end_before_the_start_is_refused(client):
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:1]
    r = c.post("/api/matches", json={
        "teams": teams,
        "start": "2026-09-12T20:00:00+00:00",
        "end": "2026-09-12T18:00:00+00:00",
    })
    assert r.status_code == 400


def test_an_unknown_team_is_refused_by_name(client):
    """Teams come from contest.toml. Silently accepting one that does not exist
    would produce a match nobody is ever expected at."""
    c, _ = client
    r = c.post("/api/matches", json={"teams": ["NOTATEAM"], "day": "2026-09-12"})
    assert r.status_code == 400
    assert "NOTATEAM" in r.json()["detail"]


def test_delete_removes_it(client):
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:1]
    made = c.post("/api/matches", json={"teams": teams, "day": "2026-09-12"}).json()

    assert c.delete(f"/api/matches/{made['id']}").status_code == 200
    body = c.get("/api/matches").json()
    assert all(f["id"] != made["id"]
               for f in body["now"] + body["upcoming"] + body["past"])


def test_deleting_something_that_is_not_there_says_where_matches_live(client):
    c, _ = client
    r = c.delete("/api/matches/9999")
    assert r.status_code == 404
    assert "contest.toml" in r.json()["detail"]


def test_a_toml_match_is_not_deletable_from_the_page(client):
    """It has no id, so the page renders no delete button for it."""
    c, application = client
    application.contest.matches = (
        Match(teams=("KU",), day=date(2026, 9, 12), label="from the file"),)
    body = c.get("/api/matches").json()
    everything = body["now"] + body["upcoming"] + body["past"]
    from_file = [f for f in everything if f["label"] == "from the file"]
    assert from_file and from_file[0]["editable"] is False
    assert from_file[0]["id"] is None


def test_an_empty_list_says_so_rather_than_looking_broken(client):
    """No matches is the normal state of a fresh install and it means
    something -- every team counts as playing."""
    c, application = client
    application.contest.matches = ()
    assert c.get("/api/matches").json()["any"] is False


def test_adding_a_match_changes_who_is_expected(client):
    """The whole point of the feature: the roll call should stop listing forty
    schools when four are playing."""
    c, application = client
    everyone = [t.abbr for t in application.contest.teams]
    assert len(everyone) >= 2, "this test needs at least two teams in contest.toml"

    today = datetime.now(timezone.utc).date().isoformat()
    c.post("/api/matches", json={"teams": everyone[:1], "day": today})

    playing = c.get("/api/matches").json()["playing"]
    assert set(playing) == {everyone[0]}
    assert set(playing) != set(everyone)


# ------------------------------------------------------------- the game type

def test_a_match_can_name_its_own_game():
    """A season is allowed to vary: conquest one week, dx the next."""
    from radiorumble import config
    contest = config.load()
    contest.matches = (Match(teams=("KU",), day=date(2026, 9, 12), mode="dx"),)
    assert contest.mode_now(NOON) == "dx"


def test_a_match_without_one_uses_the_contest_default():
    from radiorumble import config
    contest = config.load()
    contest.matches = (Match(teams=("KU",), day=date(2026, 9, 12)),)
    assert contest.mode_now(NOON) == contest.mode


def test_the_game_reverts_once_the_match_is_over():
    """Otherwise last week's rules would still be scoring this week."""
    from radiorumble import config
    contest = config.load()
    contest.matches = (Match(teams=("KU",), day=date(2026, 9, 12), mode="dx"),)
    later = datetime(2026, 9, 19, 12, tzinfo=timezone.utc)
    assert contest.mode_now(NOON) == "dx"
    assert contest.mode_now(later) == contest.mode


def test_the_mode_survives_the_database(db):
    db.add_match(label="DX night", teams=["KU"], day=date(2026, 9, 12), mode="dx")
    (m,) = matchlib.stored_matches(db)
    assert m.mode == "dx"


def test_a_match_with_no_mode_stores_null_not_empty_string(db):
    """None means "use the contest's", and "" would be a mode called nothing."""
    db.add_match(teams=["KU"], day=date(2026, 9, 12), mode="")
    (m,) = matchlib.stored_matches(db)
    assert m.mode is None


def test_the_column_is_added_to_an_older_database(tmp_path):
    """CREATE TABLE IF NOT EXISTS does nothing to a table that already exists,
    so a database made before `mode` existed has to have it added -- otherwise
    the app starts and dies on the first query that mentions it."""
    import sqlite3
    from radiorumble.db import Database

    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, label TEXT NOT NULL DEFAULT '',
            teams TEXT NOT NULL DEFAULT '[]', day TEXT, start_at TEXT, end_at TEXT,
            is_open INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
        INSERT INTO matches (label, teams, day, is_open, created_at)
            VALUES ('before the upgrade', '["KU"]', '2026-09-12', 0, 'then');
    """)
    old.commit()
    old.close()

    upgraded = Database(path)
    (m,) = matchlib.stored_matches(upgraded)
    assert m.label == "before the upgrade"
    assert m.mode is None
    upgraded.add_match(label="after", teams=["KU"], day=date(2026, 9, 19), mode="dx")
    assert [x.mode for x in matchlib.stored_matches(upgraded)] == [None, "dx"]


def test_the_api_offers_every_game(client):
    c, _ = client
    body = c.get("/api/matches").json()
    keys = {m["key"] for m in body["modes"]}
    assert keys == {"classic", "conquest", "dx", "scarcity", "connect", "traverse"}
    assert all(m["label"] for m in body["modes"])


def test_an_unknown_game_is_refused_by_name(client):
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:1]
    r = c.post("/api/matches", json={"teams": teams, "day": "2026-09-12",
                                     "mode": "quidditch"})
    assert r.status_code == 400
    assert "quidditch" in r.json()["detail"]


def test_adding_a_match_with_a_game_changes_what_is_scored(client):
    """The whole point: the scoreboard plays the running match's game."""
    c, application = client
    teams = [t.abbr for t in application.contest.teams][:1]
    today = datetime.now(timezone.utc).date().isoformat()

    before = application.contest.mode_now()
    other = "dx" if before != "dx" else "classic"
    c.post("/api/matches", json={"label": "different game", "teams": teams,
                                 "day": today, "mode": other})
    assert application.contest.mode_now() == other
    assert c.get("/api/matches").json()["mode_now"] == other
