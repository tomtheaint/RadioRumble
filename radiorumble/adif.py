"""ADIF parsing.

ADIF is a tagged format: ``<field:length>value``, with a record ending at
``<eor>``. The length is authoritative — values may contain spaces, and some
loggers emit no delimiter at all between fields — so this reads exactly the
declared number of characters rather than splitting on whitespace.

The input is deliberately not assumed to be clean. `rec.py` writes a raw
listener transcript in which each QSO is surrounded by timestamps, a hex dump
of the UDP packet and rules of dashes, and WSJT-X itself writes plain ADIF.
Both are handled by scanning for tags and ignoring everything between them,
which means a header block, a hex blob or a stray log line costs nothing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

# <name:length> or <name:length:type>. ADIF says field names are case
# insensitive, so everything is folded to lowercase on the way in.
_TAG = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*):(\d+)(?::[A-Za-z])?>")

# Bare <eor>/<eoh> markers carry no length.
_MARKER = re.compile(r"<(eor|eoh)>", re.IGNORECASE)


@dataclass(frozen=True)
class Qso:
    """One logged contact, from the point of view of the station that logged it."""

    station: str          # station_callsign — who made the contact
    call: str             # call — who they worked
    band: str             # normalised lowercase, e.g. "20m"
    mode: str             # normalised uppercase, e.g. "FT8"
    grid: str             # gridsquare of the worked station, 4 chars, uppercase
    my_grid: str          # gridsquare of the logging station
    when: datetime | None  # qso_date + time_on, UTC; None if the log omitted it
    freq: str = ""
    rst_sent: str = ""
    rst_rcvd: str = ""
    raw: dict[str, str] = field(default_factory=dict, repr=False, compare=False)

    #: Which submitted log this came out of. Empty for a single merged file.
    source: str = ""

    @property
    def uid(self) -> str:
        """A stable identifier for one contact, used to void it by name.

        Derived from the contact itself rather than from its position in a
        file, because a log that is re-read after a rotation would otherwise
        renumber everything and un-void whatever an admin had struck out.
        """
        import hashlib

        parts = "|".join([
            self.station, self.call, self.band, self.mode,
            self.when.isoformat() if self.when else "",
        ])
        return hashlib.sha1(parts.encode()).hexdigest()[:12]

    @property
    def square(self) -> str:
        """The 4-character grid square, which is what counts as a multiplier.

        Logs mix 4- and 6-character precision for the same square — WSJT-X
        sends what the other station sent — so EM19 and EM19RF have to collapse
        to one multiplier or a team gets credit twice for the same square.
        """
        return self.grid[:4].upper()


def _parse_datetime(date: str, time: str) -> datetime | None:
    """Combine ADIF qso_date (YYYYMMDD) and time_on (HHMMSS or HHMM) as UTC."""
    if not date:
        return None
    time = (time or "000000").ljust(6, "0")[:6]
    try:
        return datetime.strptime(date + time, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_fields(text: str) -> list[dict[str, str]]:
    """Pull every complete ADIF record out of arbitrary text.

    Returns one dict per record. Anything before the first tag, between
    records, or after the last ``<eor>`` is ignored — an incomplete trailing
    record is dropped rather than half-parsed, which is what lets a caller
    hand over a partially written file and re-feed the tail next time.
    """
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    pos = 0
    end = len(text)

    while pos < end:
        tag = _TAG.search(text, pos)
        marker = _MARKER.search(text, pos)

        # Whichever comes first wins; neither means we're done.
        if tag and (not marker or tag.start() < marker.start()):
            length = int(tag.group(2))
            value_start = tag.end()
            value = text[value_start:value_start + length]
            if len(value) < length:
                break  # truncated mid-value: leave it for the next read
            current[tag.group(1).lower()] = value.strip()
            pos = value_start + length
        elif marker:
            if marker.group(1).lower() == "eor" and current:
                records.append(current)
            current = {}
            pos = marker.end()
        else:
            break

    return records


def parse(text: str, source: str = "") -> list[Qso]:
    """Parse text into Qso objects, skipping records without the essentials.

    A record with no ``call`` or no ``station_callsign`` cannot be scored or
    attributed to a team, so it is dropped here rather than becoming a
    half-populated row that fails somewhere less obvious.

    ``source`` names the log the records came from, which is what makes it
    possible to say later that a contact was confirmed by the other end.
    """
    qsos = []
    for rec in parse_fields(text):
        call = rec.get("call", "").upper()
        station = rec.get("station_callsign", "").upper()
        if not call or not station:
            continue
        qsos.append(
            Qso(
                station=station,
                call=call,
                band=rec.get("band", "").lower(),
                mode=rec.get("mode", "").upper(),
                grid=rec.get("gridsquare", "").upper(),
                my_grid=rec.get("my_gridsquare", "").upper(),
                when=_parse_datetime(rec.get("qso_date", ""), rec.get("time_on", "")),
                freq=rec.get("freq", ""),
                rst_sent=rec.get("rst_sent", ""),
                rst_rcvd=rec.get("rst_rcvd", ""),
                source=source,
                raw=rec,
            )
        )
    return qsos


def split_complete(text: str) -> tuple[str, str]:
    """Split text at the last ``<eor>``: (complete records, trailing remainder).

    The tailer uses this to avoid parsing a record that is still being written.
    A log file is appended to a few hundred bytes at a time and there is no
    guarantee a read lands on a record boundary.
    """
    last = None
    for match in _MARKER.finditer(text):
        if match.group(1).lower() == "eor":
            last = match
    if last is None:
        return "", text
    return text[:last.end()], text[last.end():]
