"""The admin password, and the cookie that remembers it.

What this replaces had no tests at all -- the shared token, the header, the
`#token=` URL trick and every endpoint behind them went untested for the whole
life of the feature. So these cover the mechanism rather than only the happy
path: a forged cookie, an expired one, a password change while somebody is
signed in.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from radiorumble import auth
from radiorumble.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "t.db")


@pytest.fixture
def client(monkeypatch, tmp_path):
    """A running app with its own empty database."""
    import app as application

    monkeypatch.setattr(application, "db", Database(tmp_path / "app.db"))
    monkeypatch.setattr(application.listener, "start", lambda: (True, "stub"))
    monkeypatch.setattr(application.ingest, "start", lambda: None)
    monkeypatch.setattr(application.ingest, "stop", lambda: None)
    with TestClient(application.app) as test_client:
        yield test_client, application


# ------------------------------------------------------------- the mechanics

def test_a_fresh_instance_has_no_password(db):
    assert auth.needs_setup(db)


def test_setting_a_password_claims_the_instance(db):
    auth.set_password(db, "rumble2026")
    assert not auth.needs_setup(db)
    assert auth.check_password(db, "rumble2026")


def test_the_wrong_password_is_refused(db):
    auth.set_password(db, "rumble2026")
    assert not auth.check_password(db, "rumble2025")


def test_the_password_is_not_stored_in_the_clear(db):
    auth.set_password(db, "rumble2026")
    stored = db.get_setting(auth.PASSWORD_KEY)
    assert "rumble2026" not in stored
    assert stored.startswith("scrypt$")


def test_the_cost_parameters_travel_with_the_hash(db):
    """So raising the cost later does not invalidate an existing password."""
    auth.set_password(db, "rumble2026")
    scheme, n, r, p, _salt, _digest = db.get_setting(auth.PASSWORD_KEY).split("$")
    assert scheme == "scrypt"
    assert (int(n), int(r), int(p)) == (auth.SCRYPT_N, auth.SCRYPT_R, auth.SCRYPT_P)


def test_two_identical_passwords_hash_differently(db, tmp_path):
    """Salted, so a stolen database does not reveal that two instances share
    a password -- or let one rainbow table answer for both."""
    other = Database(tmp_path / "other.db")
    auth.set_password(db, "same-password")
    auth.set_password(other, "same-password")
    assert db.get_setting(auth.PASSWORD_KEY) != other.get_setting(auth.PASSWORD_KEY)


def test_a_short_password_is_refused(db):
    with pytest.raises(ValueError):
        auth.set_password(db, "abc")


def test_a_malformed_hash_is_false_not_an_exception(db):
    db.set_setting(auth.PASSWORD_KEY, "not-a-hash")
    assert auth.check_password(db, "anything") is False


# --------------------------------------------------------------- the cookie

def test_a_session_this_server_issued_is_accepted(db):
    auth.set_password(db, "rumble2026")
    assert auth.valid_session(db, auth.issue_session(db))


def test_a_tampered_session_is_rejected(db):
    auth.set_password(db, "rumble2026")
    cookie = auth.issue_session(db)
    assert not auth.valid_session(db, cookie[:-4] + "AAAA")


def test_an_extended_expiry_is_rejected(db):
    """The expiry is inside the signed payload, so moving it breaks the
    signature. Reading it from an unverified cookie would be taking the
    attacker's word for when their access ends."""
    auth.set_password(db, "rumble2026")
    who, expires, signature = auth.issue_session(db).rsplit(".", 2)
    forged = f"{who}.{int(expires) + 86400}.{signature}"
    assert not auth.valid_session(db, forged)


def test_an_expired_session_is_rejected(db):
    auth.set_password(db, "rumble2026")
    cookie = auth.issue_session(db)
    assert not auth.valid_session(db, cookie, now=9e9)


def test_nonsense_is_rejected_rather_than_raising(db):
    auth.set_password(db, "rumble2026")
    for junk in ("", None, "nonsense", "a.b.c", "admin.notanumber.xxx"):
        assert not auth.valid_session(db, junk)


def test_changing_the_password_ends_every_session(db):
    """Otherwise "reset the password" would not lock anybody out, which is the
    main reason somebody resets it."""
    auth.set_password(db, "first-password")
    cookie = auth.issue_session(db)
    assert auth.valid_session(db, cookie)
    auth.set_password(db, "second-password")
    assert not auth.valid_session(db, cookie)


def test_sessions_survive_a_restart(db, tmp_path):
    """The signing key is in the database, not in memory -- the old token was
    regenerated on every boot and signed everybody out."""
    auth.set_password(db, "rumble2026")
    cookie = auth.issue_session(db)
    reopened = Database(db.path)
    assert auth.valid_session(reopened, cookie)


# ------------------------------------------------------------- over the wire

def test_admin_endpoints_are_refused_before_setup(client):
    c, _ = client
    r = c.get("/api/contacts")
    assert r.status_code == 409          # not 403: there is no password to type


def test_setup_then_the_log_opens(client):
    c, _ = client
    assert c.get("/api/auth").json() == {"needs_setup": True, "signed_in": False}

    assert c.post("/api/auth/setup", json={"password": "rumble2026"}).status_code == 200
    assert c.get("/api/auth").json() == {"needs_setup": False, "signed_in": True}
    assert c.get("/api/contacts").status_code == 200


def test_setup_cannot_be_used_to_reset_a_password(client):
    """Otherwise it is a password reset with no authentication in front of it."""
    c, _ = client
    c.post("/api/auth/setup", json={"password": "rumble2026"})
    r = c.post("/api/auth/setup", json={"password": "stolen"})
    assert r.status_code == 409
    c.cookies.clear()
    assert c.post("/api/auth/login", json={"password": "rumble2026"}).status_code == 200


def test_a_short_password_is_refused_over_the_wire(client):
    c, _ = client
    r = c.post("/api/auth/setup", json={"password": "abc"})
    assert r.status_code == 400
    assert "6" in r.json()["detail"]


def test_signing_out_closes_the_log(client):
    c, _ = client
    c.post("/api/auth/setup", json={"password": "rumble2026"})
    assert c.get("/api/contacts").status_code == 200
    c.post("/api/auth/logout")
    assert c.get("/api/contacts").status_code == 403


def test_the_wrong_password_does_not_sign_you_in(client):
    c, _ = client
    c.post("/api/auth/setup", json={"password": "rumble2026"})
    c.post("/api/auth/logout")
    assert c.post("/api/auth/login", json={"password": "wrong"}).status_code == 403
    assert c.get("/api/contacts").status_code == 403


def test_the_cookie_is_httponly(client):
    """It authorises voiding contacts; script has no reason to read it."""
    c, _ = client
    r = c.post("/api/auth/setup", json={"password": "rumble2026"})
    assert "httponly" in r.headers["set-cookie"].lower()


def test_the_scoreboard_stays_public(client):
    """None of this is meant to put a password in front of the audience."""
    c, _ = client
    for route in ("/", "/api/scoreboard", "/api/standings", "/check", "/matches"):
        assert c.get(route).status_code == 200, route
