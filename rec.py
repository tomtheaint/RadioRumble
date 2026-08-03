#!/usr/bin/env python3
"""Listen for WSJT-X and write contacts straight into a contest log.

    python rec.py                          # append to the contest's log_file
    python rec.py --station KE0VUM         # write logs/KE0VUM.adi instead
    python rec.py --port 2237 --raw dump.txt

Point WSJT-X at this machine under *Reporting → UDP Server*, port 2237. Every
time an operator presses Log, the contact arrives here and is appended as ADIF
— the same format a submitted log is in, so a live station and a mailed-in
file are indistinguishable by the time they reach the scoreboard.

This used to write the hex of every packet and nothing else, which recorded
that something happened without recording what. The bytes are still available
with ``--raw`` when a datagram needs looking at, but they are no longer the
point.

Several WSJT-X instances can report to one server. With ``--split`` each
station's contacts land in their own file inside the log directory, which is
what cross-checking needs.
"""
from __future__ import annotations

import argparse
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

from radiorumble import config, wsjtx


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--port", type=int, default=2237, help="WSJT-X UDP port")
    ap.add_argument("--host", default="0.0.0.0", help="address to listen on")
    ap.add_argument("--output", default=None,
                    help="file to append to; defaults to the contest's log_file")
    ap.add_argument("--station", default=None,
                    help="write to <log_dir>/<STATION>.adi instead")
    ap.add_argument("--split", action="store_true",
                    help="one file per station callsign, taken from each contact")
    ap.add_argument("--raw", default=None, metavar="FILE",
                    help="also append the hex of every datagram, for debugging")
    args = ap.parse_args()

    contest = config.load()
    log_dir = contest.log_dir or contest.log_file.parent
    fixed_output = None
    if args.output:
        fixed_output = Path(args.output)
    elif args.station:
        log_dir.mkdir(parents=True, exist_ok=True)
        fixed_output = log_dir / f"{args.station.upper()}.adi"
    elif not args.split:
        fixed_output = contest.log_file

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((args.host, args.port))
    except OSError as err:
        sys.exit(f"cannot listen on {args.host}:{args.port} — {err}")

    where = fixed_output if fixed_output else f"{log_dir}/<STATION>.adi"
    print(f"Listening for WSJT-X on {args.host}:{args.port}")
    print(f"Writing contacts to {where}")
    print("Set WSJT-X: Reporting -> UDP Server to this address. Ctrl+C to stop.\n")

    logged = ignored = 0
    stations: set[str] = set()
    try:
        while True:
            data, addr = sock.recvfrom(8192)

            if args.raw:
                stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
                with open(args.raw, "a", encoding="utf-8") as fh:
                    fh.write(f"[{stamp}] {addr[0]}:{addr[1]} {len(data)} bytes\n")
                    fh.write(data.hex() + "\n")

            try:
                kind, qso = wsjtx.decode(data)
            except ValueError as err:
                print(f"  ignoring a datagram from {addr[0]}: {err}")
                continue

            if qso is None:
                # Heartbeats and status updates arrive constantly and say
                # nothing about contacts. Counted, not printed.
                ignored += 1
                continue

            target = fixed_output
            if target is None:
                station = qso.my_call or "UNKNOWN"
                log_dir.mkdir(parents=True, exist_ok=True)
                target = log_dir / f"{station}.adi"

            with open(target, "a", encoding="utf-8") as fh:
                fh.write(qso.to_adif() + "\n")

            logged += 1
            stations.add(qso.my_call)
            when = (qso.when_on or qso.when_off)
            print(f"  {when:%H:%M:%S}z  {qso.my_call:>8} worked {qso.call:<8} "
                  f"{qso.band:>5} {qso.mode:<4} {qso.grid:<6} -> {target.name}"
                  if when else
                  f"  {qso.my_call} worked {qso.call} -> {target.name}")

    except KeyboardInterrupt:
        print(f"\nStopped. {logged} contacts written from {len(stations)} station(s); "
              f"{ignored} non-contact datagrams ignored.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
