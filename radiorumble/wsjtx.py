"""Decoding what WSJT-X sends over UDP.

WSJT-X broadcasts a UDP datagram every time something happens, and the one
that matters here is **QSO Logged** (type 5): it carries a completed contact,
already confirmed by the operator pressing Log. Listening for that is how a
contest gets contacts as they happen instead of when somebody remembers to
export an ADIF.

The wire format is a Qt datastream, which is simpler than it sounds — big
endian, length-prefixed strings, and a fixed field order per message type:

    quint32   magic       0xadbccbda
    quint32   schema      2 or 3
    quint32   type        5 is QSO Logged
    utf8      id          "WSJT-X" unless the operator renamed it
    ...       payload     per type

A null string is length 0xffffffff rather than 0, which is the one trap worth
knowing: read it as a length and you will try to allocate four gigabytes.

WSJT-X has two of these, and which one an operator can spare matters:

* **UDP Server** (2237) speaks the whole protocol -- heartbeats, status, and
  contacts as parsed fields. It is also what JTAlert and GridTracker use, so
  on most operators' machines it is already taken by something local.
* **Secondary UDP Server** (2333), "enable logged contact ADIF broadcast",
  sends one thing: a complete ADIF record each time a contact is logged.
  Marked deprecated by WSJT-X and still the field most operators have free.

So both are accepted. The difference worth knowing is that the secondary
sends *nothing at all* until a contact is logged -- no heartbeat, no status --
so a station using it cannot be seen setting up, only working.
"""
from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

log = logging.getLogger("radiorumble.wsjtx")

MAGIC = 0xADBCCBDA
QSO_LOGGED = 5
HEARTBEAT = 0
STATUS = 1
#  Type 12 carries a whole ADIF record rather than parsed fields. It is what
#  the "logged contact ADIF broadcast" sends, and it is the one most operators
#  will actually be using -- see the module docstring.
LOGGED_ADIF = 12
NULL_LENGTH = 0xFFFFFFFF

# Qt counts milliseconds from midnight; QDate counts Julian days.
_JULIAN_EPOCH = 2440588   # Julian day number of 1970-01-01


class Reader:
    """A cursor over one datagram."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.pos = 0

    def _take(self, count: int) -> bytes:
        if self.pos + count > len(self.data):
            raise ValueError("datagram ended early")
        chunk = self.data[self.pos:self.pos + count]
        self.pos += count
        return chunk

    def uint32(self) -> int:
        return struct.unpack(">I", self._take(4))[0]

    def uint64(self) -> int:
        return struct.unpack(">Q", self._take(8))[0]

    def int32(self) -> int:
        return struct.unpack(">i", self._take(4))[0]

    def double(self) -> float:
        return struct.unpack(">d", self._take(8))[0]

    def boolean(self) -> bool:
        return self._take(1) != b"\x00"

    def string(self) -> str:
        length = self.uint32()
        if length == NULL_LENGTH:      # Qt's null string, not a 4GB one
            return ""
        return self._take(length).decode("utf-8", errors="replace")

    def datetime(self) -> datetime | None:
        """QDateTime: Julian day, milliseconds since midnight, then a timespec."""
        julian = self.uint64()
        msecs = self.uint32()
        spec = self._take(1)[0]
        if spec == 2:                  # offset from UTC follows
            self.int32()
        if julian == 0:
            return None
        days = julian - _JULIAN_EPOCH
        return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
            days=days, milliseconds=msecs
        )


@dataclass
class LoggedQso:
    """A contact WSJT-X has just logged."""

    when_off: datetime | None
    call: str
    grid: str
    freq_hz: int
    mode: str
    rst_sent: str
    rst_rcvd: str
    tx_power: str
    comments: str
    name: str
    when_on: datetime | None
    operator: str
    my_call: str
    my_grid: str
    exchange_sent: str = ""
    exchange_rcvd: str = ""

    @property
    def band(self) -> str:
        return band_for(self.freq_hz)

    def to_adif(self) -> str:
        """Render as an ADIF record, so it joins the same pipeline as a file.

        Everything downstream already understands ADIF. Writing it out means
        a live feed and a submitted log are the same thing by the time they
        reach the scoreboard, and the file on disk is a real log an operator
        can keep.
        """
        when = self.when_on or self.when_off
        fields = [
            ("call", self.call),
            ("gridsquare", self.grid[:6]),
            ("mode", self.mode or "FT8"),
            ("rst_sent", self.rst_sent),
            ("rst_rcvd", self.rst_rcvd),
            ("qso_date", when.strftime("%Y%m%d") if when else ""),
            ("time_on", when.strftime("%H%M%S") if when else ""),
            ("band", self.band),
            ("freq", f"{self.freq_hz / 1_000_000:.6f}" if self.freq_hz else ""),
            ("station_callsign", self.my_call),
            ("my_gridsquare", self.my_grid[:6]),
            ("tx_pwr", self.tx_power),
            ("comment", self.comments),
            ("operator", self.operator),
        ]
        out = []
        for name, value in fields:
            value = (value or "").strip()
            if value:
                out.append(f"<{name}:{len(value)}>{value} ")
        return "".join(out) + "<eor>"


# Where each FT8 watering hole sits, so a frequency becomes a band name.
_BANDS = (
    (1_800_000, 2_000_000, "160m"), (3_500_000, 4_000_000, "80m"),
    (5_250_000, 5_450_000, "60m"), (7_000_000, 7_300_000, "40m"),
    (10_100_000, 10_150_000, "30m"), (14_000_000, 14_350_000, "20m"),
    (18_068_000, 18_168_000, "17m"), (21_000_000, 21_450_000, "15m"),
    (24_890_000, 24_990_000, "12m"), (28_000_000, 29_700_000, "10m"),
    (50_000_000, 54_000_000, "6m"), (144_000_000, 148_000_000, "2m"),
    (222_000_000, 225_000_000, "1.25m"), (420_000_000, 450_000_000, "70cm"),
)


def band_for(freq_hz: int) -> str:
    for low, high, name in _BANDS:
        if low <= freq_hz <= high:
            return name
    return ""


@dataclass
class Presence:
    """Who is out there, from a datagram that isn't a contact.

    WSJT-X talks constantly: a heartbeat every fifteen seconds and a status
    message whenever anything changes. Neither is a contact, and `decode`
    rightly ignores both -- but between them they are the only way to know a
    station is connected *before* it works anybody, which is exactly the
    question an operator has while setting up.

    Status carries the operator's own callsign and grid, so a station
    identifies itself the moment WSJT-X is pointed here.
    """

    kind: int
    instance: str = ""          # the sending instance's id, "WSJT-X" by default
    call: str = ""              # the operator's own callsign
    grid: str = ""              # ...and their own grid
    freq_hz: int = 0
    mode: str = ""
    dx_call: str = ""           # who they are working right now
    transmitting: bool = False
    version: str = ""

    @property
    def band(self) -> str:
        return band_for(self.freq_hz)


def describe(data: bytes) -> Presence:
    """What a datagram says about the station that sent it.

    Every message type is read far enough to be useful and no further: a
    heartbeat identifies the instance and its version, a status message adds
    the callsign, grid, band and what it is doing. A contact is read by
    `decode`; here it only says that one arrived.

    Fields are read in the order WSJT-X writes them and stop at the first
    short read, because a newer schema appends and an older one simply ends --
    a datagram that runs out is a version difference, not a corruption.
    """
    reader = Reader(data)
    if reader.uint32() != MAGIC:
        raise ValueError("not a WSJT-X datagram")
    reader.uint32()                       # schema
    kind = reader.uint32()
    found = Presence(kind=kind, instance=reader.string())

    try:
        if kind == HEARTBEAT:
            reader.uint32()               # maximum schema this instance speaks
            found.version = reader.string()
        elif kind == STATUS:
            found.freq_hz = reader.uint64()
            found.mode = reader.string().upper()
            found.dx_call = reader.string().upper()
            reader.string()               # report
            reader.string()               # tx mode
            reader.boolean()              # tx enabled
            found.transmitting = reader.boolean()
            reader.boolean()              # decoding
            reader.uint32()               # rx df
            reader.uint32()               # tx df
            found.call = reader.string().upper()
            found.grid = reader.string().upper()
    except ValueError:
        pass                              # an older WSJT-X stops earlier
    return found


def is_wsjtx(data: bytes) -> bool:
    """Does this datagram carry WSJT-X's framing at all?

    The secondary UDP server sends bare ADIF with no header, so "is this one
    of ours" has to be answerable before anything is decoded.
    """
    return len(data) >= 4 and data[:4] == b"\xad\xbc\xcb\xda"


def adif_text(data: bytes) -> str:
    """The ADIF out of a Logged ADIF datagram, or "" if it isn't one.

    Type 12 is a binary header followed by a complete ADIF file -- header,
    one record, and the terminator. WSJT-X's own note says a receiver can
    treat the whole datagram as ADIF without special parsing, which is true
    because an ADIF reader skips anything that isn't a tag; this reads the
    string properly anyway, so what lands in the log is text rather than text
    with sixteen bytes of Qt in front of it.
    """
    reader = Reader(data)
    if reader.uint32() != MAGIC:
        return ""
    reader.uint32()                       # schema
    if reader.uint32() != LOGGED_ADIF:
        return ""
    reader.string()                       # the sending instance's id
    try:
        return reader.string()
    except ValueError:
        return ""


def decode(data: bytes) -> tuple[int, LoggedQso | None]:
    """Decode a datagram. Returns (message type, contact if it was one).

    Anything that isn't a logged contact returns its type and None — the
    heartbeats and status messages are useful for knowing a station is alive,
    but they are not contacts.
    """
    reader = Reader(data)
    if reader.uint32() != MAGIC:
        raise ValueError("not a WSJT-X datagram")
    schema = reader.uint32()
    kind = reader.uint32()
    reader.string()                    # the sending instance's id

    if kind != QSO_LOGGED:
        return kind, None

    qso = LoggedQso(
        when_off=reader.datetime(),
        call=reader.string().upper(),
        grid=reader.string().upper(),
        freq_hz=reader.uint64(),
        mode=reader.string().upper(),
        rst_sent=reader.string(),
        rst_rcvd=reader.string(),
        tx_power=reader.string(),
        comments=reader.string(),
        name=reader.string(),
        when_on=reader.datetime(),
        operator=reader.string().upper(),
        my_call=reader.string().upper(),
        my_grid=reader.string().upper(),
    )
    # Schema 3 appends the contest exchanges. Older versions simply stop here,
    # so a short datagram is a version difference rather than a corrupt one.
    if schema >= 3:
        try:
            qso.exchange_sent = reader.string()
            qso.exchange_rcvd = reader.string()
        except ValueError:
            pass
    return kind, qso
