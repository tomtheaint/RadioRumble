"""The WSJT-X listener, run by the server rather than by hand.

`rec.py` does this from a terminal and still does. The trouble with a terminal
is that nobody can see it: at an event the listener is on some laptop behind a
table, and if it dies, or was never started, or is bound to the wrong port, the
first anybody knows is that the scoreboard stayed at zero. Meanwhile every
operator in the room is asking the same question — *is it hearing me?* — and
there is no way to answer it except by working somebody and hoping.

So the listener lives in the app, and what it hears is a page.

Two things it records, and the second is the point:

* **Contacts.** Written straight out as ADIF into the log directory, one file
  per station, exactly as `rec.py --split` does. Nothing downstream changes;
  the file watcher picks them up and a live station and a mailed-in log stay
  indistinguishable by the time they reach the scoreboard.
* **Presence.** WSJT-X sends a heartbeat every fifteen seconds and a status
  message whenever anything changes, and a station's own callsign is in the
  status. That is what lets somebody confirm their setup at ten to two rather
  than discovering at ten past that their contacts went nowhere.

A station is identified by callsign once it has sent a status message, and by
its address until then, because that is genuinely all we know about it yet.
"""
from __future__ import annotations

import logging
import socket
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import wsjtx

log = logging.getLogger("radiorumble.listener")

#  Both of WSJT-X's reporting servers, because operators can only spare one
#  of them and it is rarely the same one twice.
#
#    2237  UDP Server -- the whole protocol. Usually already taken on the
#          operator's machine by JTAlert or GridTracker.
#    2333  Secondary UDP Server, "logged contact ADIF broadcast". One ADIF
#          record per contact and nothing else -- no heartbeat, no status, so
#          a station using this cannot be seen until it works somebody.
DEFAULT_PORTS = (2237, 2333)
DEFAULT_HOST = "0.0.0.0"

#  How far back the activity counts reach. A day is the longest anyone asks
#  about and is cheap: a station heartbeating every fifteen seconds is 5,760
#  events in twenty-four hours, and there are tens of stations, not thousands.
WINDOWS = (("minute", 60), ("hour", 3600), ("day", 86400))
MAX_EVENTS = 20000
STALE_AFTER = 90.0     # two missed heartbeats, and a station reads as gone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Station:
    """One WSJT-X instance, and what it has been doing."""

    key: str
    call: str = ""
    grid: str = ""
    address: str = ""
    port: int = 0
    instance: str = ""
    version: str = ""
    freq_hz: int = 0
    #: Set when the band was stated rather than derived from a frequency,
    #: which is the only thing an ADIF record gives us.
    band_text: str = ""
    mode: str = ""
    dx_call: str = ""
    transmitting: bool = False
    first_seen: datetime = field(default_factory=_now)
    last_seen: datetime = field(default_factory=_now)
    last_qso: datetime | None = None
    packets: int = 0
    qsos: int = 0
    #: (monotonic-ish epoch seconds, was_it_a_contact)
    events: deque = field(default_factory=lambda: deque(maxlen=MAX_EVENTS))

    @property
    def band(self) -> str:
        return wsjtx.band_for(self.freq_hz) or self.band_text

    def counts(self, now: float) -> dict:
        """Packets and contacts inside each window.

        Counted by walking the events rather than kept as running totals: a
        total that only goes up cannot answer "in the last minute", and the
        list is small enough that the honest version costs nothing.
        """
        out = {}
        for name, span in WINDOWS:
            since = now - span
            packets = sum(1 for at, _ in self.events if at >= since)
            qsos = sum(1 for at, was_qso in self.events if at >= since and was_qso)
            out[name] = {"packets": packets, "qsos": qsos}
        return out

    def as_dict(self, now: float, include_address: bool = False) -> dict:
        quiet = max(0.0, now - self.last_seen.timestamp())
        out = {
            "key": self.key,
            "call": self.call,
            "grid": self.grid,
            "instance": self.instance,
            "version": self.version,
            "band": self.band,
            "mode": self.mode,
            "dx_call": self.dx_call,
            "transmitting": self.transmitting,
            "port": self.port,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "last_qso": self.last_qso.isoformat() if self.last_qso else None,
            "quiet_for": round(quiet, 1),
            "live": quiet < STALE_AFTER,
            "packets": self.packets,
            "qsos": self.qsos,
            "windows": self.counts(now),
        }
        # An address is a person's home network. It is what an official needs
        # to tell two instances apart and nothing a scoreboard should publish.
        if include_address:
            out["address"] = self.address
        return out


class WsjtxListener:
    """Owns the socket, the log files, and what has been heard."""

    def __init__(self, log_dir: Path, host: str = DEFAULT_HOST,
                 ports=DEFAULT_PORTS, split: bool = True,
                 fallback: Path | None = None):
        self.host = host
        self.ports = tuple(int(p) for p in (ports if isinstance(ports, (list, tuple))
                                            else [ports]))
        self.split = split
        self.log_dir = Path(log_dir)
        self.fallback = fallback
        self._socks: list[socket.socket] = []
        self._threads: list[threading.Thread] = []
        self._bound: list[int] = []
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._stations: dict[str, Station] = {}
        self.started_at: datetime | None = None
        self.error: str = ""
        self.packets = 0
        self.contacts = 0
        self.rejected = 0
        self.on_contact = None      # called after a contact is written

    # -- running ----------------------------------------------------------

    @property
    def running(self) -> bool:
        return any(t.is_alive() for t in self._threads)

    @property
    def bound(self) -> tuple[int, ...]:
        """The ports actually being listened on, which is not always the ones
        that were asked for."""
        return tuple(self._bound)

    def start(self) -> tuple[bool, str]:
        """-> (started, message). Never raises: a port already in use is a
        thing to report on the page, not a stack trace in a log nobody reads.

        One port failing does not stop the others. An operator whose only
        spare field is the secondary server is still served when 2237 is taken
        by something else on this machine, which is exactly the situation
        where the message matters.
        """
        if self.running:
            return False, f"Already listening on {self._where()}."

        self._stop.clear()
        failures = []
        for port in self.ports:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((self.host, port))
            except OSError as err:
                sock.close()
                failures.append(f"{port} ({err.strerror or err})")
                continue
            # A timeout rather than a blocking read, so stopping doesn't have
            # to wait for a datagram that may never come.
            sock.settimeout(0.5)
            self._socks.append(sock)
            self._bound.append(sock.getsockname()[1])
            thread = threading.Thread(target=self._run, args=(sock,),
                                      name=f"wsjtx-listener-{port}", daemon=True)
            thread.start()
            self._threads.append(thread)

        if not self._socks:
            self.error = f"Cannot listen on {self.host}: {', '.join(failures)}"
            log.warning(self.error)
            return False, self.error

        self.error = (f"Port {', '.join(failures)} is in use; the rest are listening."
                      if failures else "")
        self.started_at = _now()
        log.info("WSJT-X listener started on %s", self._where())
        return True, f"Listening on {self._where()}." + (
            f" {self.error}" if self.error else "")

    def _where(self) -> str:
        ports = self._bound or list(self.ports)
        return f"{self.host}:" + "/".join(str(p) for p in ports)

    def stop(self) -> tuple[bool, str]:
        if not self.running:
            return False, "The listener wasn't running."
        self._stop.set()
        threads, self._threads = self._threads, []
        for thread in threads:
            thread.join(timeout=3.0)
        for sock in self._socks:
            sock.close()
        self._socks = []
        self._bound = []
        log.info("WSJT-X listener stopped")
        return True, "Stopped."

    def _run(self, sock: socket.socket) -> None:
        port = sock.getsockname()[1]
        while not self._stop.is_set():
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break                     # the socket was closed under us
            try:
                self._handle(data, addr[0], port)
            except Exception:             # noqa: BLE001 - one bad packet is not fatal
                log.debug("bad datagram from %s", addr[0], exc_info=True)
                with self._lock:
                    self.rejected += 1

    # -- what arrives -----------------------------------------------------

    def _handle(self, data: bytes, address: str, port: int = 0) -> None:
        """One datagram, in whichever of the two shapes it arrived.

        The primary server sends Qt-framed messages; the secondary sends bare
        ADIF text with no header at all. Deciding on the magic number rather
        than on which port it came in by means an operator who puts the
        secondary on 2237, or the primary on 2333, is still understood --
        which somebody will, and it is not worth a support conversation.
        """
        if not wsjtx.is_wsjtx(data):
            # The secondary UDP server: one complete ADIF record, nothing else.
            self._handle_adif(data.decode("utf-8", "replace"), address, port)
            return

        seen = wsjtx.describe(data)          # raises if it isn't WSJT-X at all
        if seen.kind == wsjtx.LOGGED_ADIF:
            # Same contact as type 5, said as ADIF. Whichever arrives, the
            # station is credited once: the store keys contacts by content.
            self._handle_adif(wsjtx.adif_text(data), address, port,
                              instance=seen.instance)
            return

        qso = None
        if seen.kind == wsjtx.QSO_LOGGED:
            _kind, qso = wsjtx.decode(data)

        # A callsign is the identity once we have one, so an operator who
        # restarts WSJT-X or changes address stays the same station on the
        # page. Until then the address is all we know.
        call = (qso.my_call if qso else seen.call) or ""
        key = call or f"{address}/{seen.instance}"

        written = None
        if qso is not None:
            written = self._write(qso)

        with self._lock:
            self.packets += 1
            station = self._stations.get(key)
            if station is None:
                # Promote the address-keyed row once its callsign turns up,
                # rather than leaving the same operator listed twice.
                if call:
                    provisional = f"{address}/{seen.instance}"
                    station = self._stations.pop(provisional, None)
                    if station is not None:
                        station.key = key
                if station is None:
                    station = Station(key=key)
                self._stations[key] = station

            now = _now()
            station.address = address
            station.port = port or station.port
            station.instance = seen.instance or station.instance
            station.version = seen.version or station.version
            station.call = call or station.call
            station.grid = (qso.my_grid if qso else seen.grid) or station.grid
            if seen.kind == wsjtx.STATUS:
                station.freq_hz = seen.freq_hz or station.freq_hz
                station.mode = seen.mode or station.mode
                station.dx_call = seen.dx_call
                station.transmitting = seen.transmitting
            station.last_seen = now
            station.packets += 1
            station.events.append((now.timestamp(), qso is not None))
            if qso is not None:
                station.qsos += 1
                station.last_qso = now
                self.contacts += 1

        if qso is not None and written and self.on_contact:
            try:
                self.on_contact(written)
            except Exception:             # noqa: BLE001
                log.debug("contact callback failed", exc_info=True)

    def _handle_adif(self, text: str, address: str, port: int = 0,
                     instance: str = "") -> None:
        """A logged contact that arrived as ADIF rather than as fields.

        The text is written through unchanged rather than re-serialised from
        the parsed record: it is already the format the logs are in, and a
        round trip would quietly drop every field this app does not happen to
        model.
        """
        from . import adif

        contacts = adif.parse(text)
        if not contacts:
            with self._lock:
                self.rejected += 1
            return

        station_call = contacts[0].station
        written = self._write_text(station_call, text)

        with self._lock:
            self.packets += 1
            key = station_call or f"{address}/{instance}"
            station = self._stations.get(key)
            if station is None:
                if station_call:
                    station = self._stations.pop(f"{address}/{instance}", None)
                    if station is not None:
                        station.key = key
                if station is None:
                    station = Station(key=key)
                self._stations[key] = station

            now = _now()
            station.address = address
            station.port = port or station.port
            station.instance = instance or station.instance
            station.call = station_call or station.call
            station.grid = contacts[0].my_grid or station.grid
            station.mode = contacts[0].mode or station.mode
            station.dx_call = contacts[0].call
            #: An ADIF record names its band directly; there is no frequency
            #: to derive one from, so it is carried as text.
            station.band_text = contacts[0].band.lower() or station.band_text
            station.last_seen = now
            station.last_qso = now
            station.packets += 1
            station.qsos += len(contacts)
            for _ in contacts:
                station.events.append((now.timestamp(), True))
            self.contacts += len(contacts)

        if written and self.on_contact:
            try:
                self.on_contact(written)
            except Exception:             # noqa: BLE001
                log.debug("contact callback failed", exc_info=True)

    def _write_text(self, station_call: str, text: str) -> Path | None:
        target = self.fallback
        if self.split or target is None:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            target = self.log_dir / f"{_safe(station_call or 'UNKNOWN')}.adi"
        try:
            with open(target, "a", encoding="utf-8") as fh:
                fh.write(text.strip() + "\n")
        except OSError as err:
            log.warning("could not write %s: %s", target, err)
            return None
        return target

    def _write(self, qso) -> Path | None:
        """Append the contact as ADIF, the same shape `rec.py --split` writes."""
        target = self.fallback
        if self.split or target is None:
            station = qso.my_call or "UNKNOWN"
            self.log_dir.mkdir(parents=True, exist_ok=True)
            target = self.log_dir / f"{_safe(station)}.adi"
        try:
            with open(target, "a", encoding="utf-8") as fh:
                fh.write(qso.to_adif() + "\n")
        except OSError as err:
            log.warning("could not write %s: %s", target, err)
            return None
        return target

    # -- what it has heard ------------------------------------------------

    def stations(self, include_address: bool = False, limit: int = 0) -> list[dict]:
        """Everyone heard from, the most recently active first."""
        now = _now().timestamp()
        with self._lock:
            rows = [s.as_dict(now, include_address) for s in self._stations.values()]
        rows.sort(key=lambda r: r["last_seen"], reverse=True)
        return rows[:limit] if limit else rows

    def status(self, include_address: bool = False) -> dict:
        rows = self.stations(include_address)
        now = _now().timestamp()
        with self._lock:
            totals = {name: {"packets": 0, "qsos": 0} for name, _ in WINDOWS}
            for station in self._stations.values():
                counted = station.counts(now)
                for name, _span in WINDOWS:
                    totals[name]["packets"] += counted[name]["packets"]
                    totals[name]["qsos"] += counted[name]["qsos"]
            snapshot = {
                "running": self.running,
                "host": self.host,
                "ports": list(self._bound or self.ports),
                "split": self.split,
                "log_dir": str(self.log_dir),
                "started_at": self.started_at.isoformat() if self.started_at else None,
                "error": self.error,
                "packets": self.packets,
                "contacts": self.contacts,
                "rejected": self.rejected,
                "windows": totals,
            }
        snapshot["stations"] = rows
        snapshot["live_stations"] = sum(1 for r in rows if r["live"])
        return snapshot

    def forget(self) -> None:
        """Clear what has been heard, without touching the logs.

        For the gap between setting up and starting: everyone tests, and
        nobody wants the contest to open with an hour of rehearsal already on
        the board.
        """
        with self._lock:
            self._stations.clear()
            self.packets = self.contacts = self.rejected = 0


def _safe(name: str) -> str:
    """A callsign arrives over the network and ends up as a filename."""
    keep = [c for c in str(name).upper() if c.isalnum() or c in "-_/"]
    return ("".join(keep).replace("/", "-") or "UNKNOWN")[:24]
