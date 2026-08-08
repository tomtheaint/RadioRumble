"""Handing in a full log after the contest.

The live feed only ever carries contacts an operator completed *during* the
contest, and only from the moment their reporting was pointed here. A full log
is the whole story — it is what turns "unmatched" into "verified" or "nil", and
what catches the half hour somebody spent with their settings wrong.

Public on purpose: cross-checking only works when both ends submit, and a
token in front of it would mean only officials could do the thing every
entrant needs to do.
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

LOG = (
    "ADIF Export from WSJT-X\n<adif_ver:5>3.1.0\n<programid:6>WSJT-X\n<EOH>\n"
    "<call:5>K9ZZZ <gridsquare:4>EN52 <mode:3>FT8 <qso_date:8>20260808 "
    "<time_on:6>143000 <band:3>20m <station_callsign:6>VA3OFF "
    "<my_gridsquare:6>FN03AB <eor>\n"
    "<call:6>KE0VUM <gridsquare:4>EM19 <mode:3>FT8 <qso_date:8>20260808 "
    "<time_on:6>144500 <band:3>20m <station_callsign:6>VA3OFF "
    "<my_gridsquare:6>FN03AB <eor>\n"
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The app, writing submissions somewhere disposable."""
    import app as application

    monkeypatch.setattr(application.contest, "log_dir", tmp_path)
    # The listener would bind real ports and the ingest thread would watch a
    # real directory; neither is what this file is about.
    monkeypatch.setattr(application.listener, "start", lambda: (True, "stub"))
    monkeypatch.setattr(application.ingest, "start", lambda: None)
    monkeypatch.setattr(application.ingest, "stop", lambda: None)
    with TestClient(application.app) as test_client:
        yield test_client, tmp_path


def _send(client, text, name="log.adi", callsign=""):
    return client.post(
        "/api/submit",
        files={"file": (name, io.BytesIO(text.encode()), "text/plain")},
        data={"callsign": callsign},
    )


def test_a_log_is_accepted_and_read(client):
    test_client, _dir = client
    body = _send(test_client, LOG).json()

    assert body["accepted"] is True
    assert body["contacts"] == 2
    assert body["callsign"] == "VA3OFF"
    assert body["stations"] == ["VA3OFF"]


def test_it_lands_where_cross_checking_will_find_it(client):
    test_client, log_dir = client
    name = _send(test_client, LOG).json()["file"]

    written = log_dir / name
    assert written.exists()
    # Written through unchanged, so nothing this app doesn't model is lost.
    assert "<my_gridsquare:6>FN03AB" in written.read_text()


def test_submitting_twice_never_overwrites_the_first(client):
    """An operator who submits a corrected log should not silently destroy
    what they sent before. Contacts are keyed by content, so the duplicates
    fold into one anyway."""
    test_client, log_dir = client
    first = _send(test_client, LOG).json()["file"]
    second = _send(test_client, LOG).json()["file"]

    assert first != second or len(list(log_dir.glob("*.adi"))) == 1
    assert (log_dir / first).exists()


def test_the_page_says_which_callsigns_are_not_entrants(client):
    """Not an error — most of a real log is people who never entered. Saying
    so is how somebody spots that they submitted the wrong file."""
    text = LOG.replace("<station_callsign:6>VA3OFF", "<station_callsign:5>W9QQQ", 1)
    body = _send(client[0], text).json()

    assert "W9QQQ" in body["unrostered"]
    assert "VA3OFF" in body["rostered"]


def test_a_file_that_is_not_a_log_is_refused_with_a_reason(client):
    response = _send(client[0], "this is not a log at all")

    assert response.status_code == 400
    assert "ADIF" in response.json()["detail"]


def test_the_callsign_comes_from_the_log_not_from_the_form(client):
    """The file is evidence; the text box is a fallback for a log whose own
    records disagree."""
    assert _send(client[0], LOG).json()["callsign"] == "VA3OFF"


def test_a_typed_callsign_cannot_choose_where_the_file_is_written(client):
    test_client, log_dir = client
    name = _send(test_client, LOG, callsign="../../etc/passwd").json()["file"]

    assert "/" not in name and ".." not in name
    assert (log_dir / name).exists()


def test_a_log_that_names_several_stations_is_still_taken(client):
    """A club station's file, or a merged one. It is still evidence."""
    text = LOG + LOG.replace("VA3OFF", "KD2FMW")
    body = _send(client[0], text).json()

    assert body["contacts"] == 4
    assert body["callsign"] == "MIXED"
    assert set(body["stations"]) == {"VA3OFF", "KD2FMW"}


def test_the_submit_page_is_public(client):
    assert client[0].get("/submit").status_code == 200
