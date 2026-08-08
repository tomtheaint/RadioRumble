"""The WSJT-X listener, and what it can tell an operator about themselves.

The listener exists so that "is the server hearing me?" has an answer before
anybody has worked anybody. That makes presence — heartbeats and status
messages — as much the point as the contacts are, and most of what is worth
pinning here is about a station that has not logged a thing yet.
"""
from __future__ import annotations

import struct
from datetime import datetime, timezone

import pytest

from radiorumble import wsjtx
from radiorumble.listener import WsjtxListener

MAGIC, SCHEMA = 0xADBCCBDA, 3
_JULIAN = 2440588


def _s(text: str) -> bytes:
    raw = (text or "").encode()
    return struct.pack(">I", len(raw)) + raw


def _head(kind: int, ident: str = "WSJT-X") -> bytes:
    return struct.pack(">III", MAGIC, SCHEMA, kind) + _s(ident)


def _qdatetime(when: datetime) -> bytes:
    days = when.toordinal() - datetime(1970, 1, 1).toordinal() + _JULIAN
    ms = (when.hour * 3600 + when.minute * 60 + when.second) * 1000
    return struct.pack(">qIB", days, ms, 1)


def heartbeat(ident: str = "WSJT-X") -> bytes:
    return _head(0, ident) + struct.pack(">I", 3) + _s("2.6.1") + _s("abc123")


def status(call: str, grid: str = "EM19rf", freq: int = 14_074_000,
           mode: str = "FT8", dx: str = "", tx: bool = False,
           ident: str = "WSJT-X") -> bytes:
    return (_head(1, ident) + struct.pack(">Q", freq) + _s(mode) + _s(dx)
            + _s("-10") + _s(mode) + struct.pack(">?", True) + struct.pack(">?", tx)
            + struct.pack(">?", True) + struct.pack(">II", 1500, 1200)
            + _s(call) + _s(grid) + _s(""))


def logged(my_call: str, dx: str, dx_grid: str = "EM12", my_grid: str = "EM19rf",
           freq: int = 14_074_000, ident: str = "WSJT-X") -> bytes:
    now = datetime.now(timezone.utc)
    return (_head(5, ident) + _qdatetime(now) + _s(dx) + _s(dx_grid)
            + struct.pack(">Q", freq) + _s("FT8") + _s("-08") + _s("-11")
            + _s("50") + _s("") + _s("") + _qdatetime(now) + _s(my_call)
            + _s(my_call) + _s(my_grid) + _s("") + _s(""))


@pytest.fixture
def listener(tmp_path):
    return WsjtxListener(log_dir=tmp_path, port=0)


# ------------------------------------------------------------- what it decodes

def test_a_heartbeat_names_the_instance_and_its_version():
    found = wsjtx.describe(heartbeat("WSJT-X-2"))
    assert found.kind == wsjtx.HEARTBEAT
    assert found.instance == "WSJT-X-2"
    assert found.version == "2.6.1"


def test_a_status_message_carries_the_operator_s_own_callsign():
    """This is the whole basis of the check page: a station says who it is
    without having worked anybody."""
    found = wsjtx.describe(status("KE0VUM", "EM19rf", 7_074_000, "FT8", dx="W1AW", tx=True))
    assert found.call == "KE0VUM"
    assert found.grid == "EM19RF"
    assert found.band == "40m"
    assert found.dx_call == "W1AW"
    assert found.transmitting is True


def test_something_that_is_not_wsjtx_is_refused():
    with pytest.raises(ValueError):
        wsjtx.describe(b"not a datagram at all")


# ------------------------------------------------------------- what it records

def test_a_station_appears_before_it_works_anybody(listener):
    listener._handle(status("KE0VUM"), "10.0.0.5")

    rows = listener.stations()
    assert [r["call"] for r in rows] == ["KE0VUM"]
    assert rows[0]["qsos"] == 0
    assert rows[0]["live"] is True


def test_a_heartbeat_alone_is_still_somebody(listener):
    """WSJT-X heartbeats before it has a callsign to report. Listing it by
    address is the honest answer -- it is all we know so far."""
    listener._handle(heartbeat(), "10.0.0.9")

    rows = listener.stations()
    assert len(rows) == 1
    assert rows[0]["call"] == ""
    assert "10.0.0.9" in rows[0]["key"]


def test_a_callsign_takes_over_the_row_its_address_started(listener):
    """Otherwise the same operator is listed twice — once as an address and
    once as a callsign — and the count of who is on the air is wrong."""
    listener._handle(heartbeat(), "10.0.0.9")
    listener._handle(status("KE0VUM"), "10.0.0.9")

    rows = listener.stations()
    assert len(rows) == 1
    assert rows[0]["call"] == "KE0VUM"
    assert rows[0]["packets"] == 2


def test_a_contact_is_written_as_adif_where_the_watcher_will_find_it(listener, tmp_path):
    listener._handle(logged("KE0VUM", "K5ABC"), "10.0.0.5")

    written = tmp_path / "KE0VUM.adi"
    assert written.exists()
    text = written.read_text()
    assert "<call:5>K5ABC" in text and "<station_callsign:6>KE0VUM" in text
    assert text.rstrip().endswith("<eor>")


def test_a_callsign_cannot_choose_where_it_is_written(listener, tmp_path):
    """The callsign arrives over the network and becomes a filename."""
    listener._handle(logged("../../etc/passwd", "K5ABC"), "10.0.0.5")

    assert not (tmp_path / ".." / ".." / "etc" / "passwd").exists()
    written = list(tmp_path.glob("*.adi"))
    assert len(written) == 1
    assert "/" not in written[0].name and ".." not in written[0].name


def test_counts_are_kept_per_window(listener):
    for _ in range(3):
        listener._handle(status("KE0VUM"), "10.0.0.5")
    listener._handle(logged("KE0VUM", "K5ABC"), "10.0.0.5")

    row = listener.stations()[0]
    assert row["windows"]["minute"] == {"packets": 4, "qsos": 1}
    assert row["windows"]["hour"]["packets"] == 4
    assert row["windows"]["day"]["packets"] == 4


def test_an_old_event_falls_out_of_the_short_window(listener):
    """A running total can't answer "in the last minute", which is the number
    somebody actually looks at."""
    import time

    listener._handle(status("KE0VUM"), "10.0.0.5")
    station = listener._stations["KE0VUM"]
    # Re-date the event to two minutes ago rather than waiting for it.
    station.events[0] = (time.time() - 120, False)

    row = listener.stations()[0]
    assert row["windows"]["minute"]["packets"] == 0
    assert row["windows"]["hour"]["packets"] == 1


def test_a_bad_datagram_is_counted_and_does_not_stop_anything(listener):
    with pytest.raises(ValueError):
        listener._handle(b"rubbish", "10.0.0.5")
    listener._handle(status("KE0VUM"), "10.0.0.5")
    assert listener.stations()[0]["call"] == "KE0VUM"


# -------------------------------------------------------------- what it shows

def test_the_public_view_keeps_addresses_to_itself(listener):
    """A callsign and a grid are broadcast to the world anyway. The address
    they are broadcast from is not."""
    listener._handle(status("KE0VUM"), "192.168.1.50")

    assert "address" not in listener.stations(include_address=False)[0]
    assert listener.stations(include_address=True)[0]["address"] == "192.168.1.50"
    assert "address" not in listener.status(include_address=False)["stations"][0]


def test_the_status_totals_add_up_across_stations(listener):
    listener._handle(status("KE0VUM"), "10.0.0.5")
    listener._handle(status("KD2FMW", ident="WSJT-X-2"), "10.0.0.6")
    listener._handle(logged("KE0VUM", "K5ABC"), "10.0.0.5")

    snapshot = listener.status()
    assert snapshot["live_stations"] == 2
    assert snapshot["packets"] == 3
    assert snapshot["contacts"] == 1
    assert snapshot["windows"]["minute"] == {"packets": 3, "qsos": 1}


def test_forgetting_clears_who_was_heard_and_not_what_was_logged(listener, tmp_path):
    """Everybody tests before the clock starts. Opening the contest with an
    hour of rehearsal on the board is a poor look -- but the contacts are the
    operator's log and are not ours to delete."""
    listener._handle(logged("KE0VUM", "K5ABC"), "10.0.0.5")
    listener.forget()

    assert listener.stations() == []
    assert listener.status()["packets"] == 0
    assert (tmp_path / "KE0VUM.adi").exists()


# ------------------------------------------------------------ starting, stopping

def test_it_starts_and_stops(tmp_path):
    listener = WsjtxListener(log_dir=tmp_path, host="127.0.0.1", port=0)
    started, _message = listener.start()
    assert started and listener.running
    stopped, _message = listener.stop()
    assert stopped and not listener.running


def test_starting_twice_says_so_rather_than_binding_twice(tmp_path):
    listener = WsjtxListener(log_dir=tmp_path, host="127.0.0.1", port=0)
    listener.start()
    try:
        started, message = listener.start()
        assert started is False
        assert "Already listening" in message
    finally:
        listener.stop()


def test_stopping_when_it_was_never_running_is_not_an_error(tmp_path):
    stopped, message = WsjtxListener(log_dir=tmp_path, port=0).stop()
    assert stopped is False
    assert "wasn't running" in message


def test_a_port_already_taken_is_reported_not_raised(tmp_path):
    """rec.py is often still running from a rehearsal. That is a sentence on a
    page, not a stack trace in a log nobody is reading."""
    first = WsjtxListener(log_dir=tmp_path, host="127.0.0.1", port=0)
    first.start()
    port = first._sock.getsockname()[1]
    try:
        second = WsjtxListener(log_dir=tmp_path, host="127.0.0.1", port=port)
        # SO_REUSEADDR lets two UDP sockets share a port on some systems, so
        # this asserts the shape of the answer rather than that it must fail.
        started, message = second.start()
        assert isinstance(message, str) and message
        if not started:
            assert "Cannot listen" in message and second.error
        else:
            second.stop()
    finally:
        first.stop()
