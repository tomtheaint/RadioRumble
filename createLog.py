#!/usr/bin/env python3
"""Generate a mock contest log from contest.toml.

The teams, bands and modes come from the contest definition, so the mock data
always matches the rules being tested — change a roster and the generated log
follows. Deliberately includes contacts that should *not* score (duplicates,
off-contest bands, stations on no roster), because a scoreboard that has only
ever seen clean input is a scoreboard whose filtering has never been tried.

    python createLog.py                    # 600 contacts over the last two hours
    python createLog.py --qsos 2000
    python createLog.py --raw              # wrap them the way rec.py logs
    python createLog.py --live             # append in real time, for demos
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone

from radiorumble import config

# Stations the teams work. On no roster — these are the rest of the world.
CHASERS = [
    "K4VHE", "AC4WW", "W4HIJ", "K3NOQ", "KF9UG", "WB0DHB", "N3JPV",
    "W1MKC", "K4UVU", "K7AMB", "N9FGH", "KI6BQ", "W5TXA", "N2LOM",
]

# DX stations and roughly where they are, so the globe has something to plot
# and DX mode has something to score. Grids are real for the country.
DX_STATIONS = [
    ("VE3ABC", "FN03"), ("VE7XYZ", "CN89"), ("VE1QQ", "FN75"),
    ("XE1MEX", "EK09"), ("TI2CR", "EJ79"), ("HP1PAN", "FJ08"),
    ("CO8LY", "FL20"), ("KP4XX", "FK68"), ("6Y5AB", "FK18"),
    ("PY2ABC", "GG66"), ("LU3DX", "GF05"), ("CE3AA", "FF46"),
    ("HK3QQ", "FJ24"), ("YV5BB", "FK60"), ("CX2CC", "GF15"),
    ("G0ABC", "IO91"), ("GM4XYZ", "IO85"), ("EI4DD", "IO63"),
    ("DL1ABC", "JO41"), ("F5XYZ", "JN18"), ("PA0RDT", "JO22"),
    ("ON4AA", "JO20"), ("OE1ABC", "JN88"), ("HB9XX", "JN47"),
    ("IK2ABC", "JN45"), ("EA3QQ", "JN11"), ("CT1AA", "IM58"),
    ("SM5ABC", "JO89"), ("LA1XX", "JO59"), ("OZ1AA", "JO65"),
    ("OH2BB", "KP20"), ("SP5XYZ", "KO02"), ("OK1ABC", "JO70"),
    ("HA5QQ", "JN97"), ("YO3AA", "KN34"), ("LZ1BB", "KN12"),
    ("SV1XX", "KM18"), ("9A1CC", "JN85"), ("UR5ABC", "KO50"),
    ("UA3QQ", "KO85"), ("RA9XX", "MO06"), ("EA8AA", "IL18"),
    ("TF3XX", "HP94"), ("JA1XYZ", "PM95"), ("JH8BB", "QN02"),
    ("HL2AA", "PM37"), ("BV1QQ", "PL05"), ("BD4XX", "PM01"),
    ("VU2ABC", "MK68"), ("9V1AA", "OJ11"), ("YB1XX", "OI33"),
    ("DU1QQ", "PK04"), ("HS0AA", "OK03"), ("4X4BB", "KM72"),
    ("A61XX", "LL75"), ("UN7AA", "MN69"), ("VK2DEF", "QF56"),
    ("VK6XX", "OF78"), ("ZL1ABC", "RF73"), ("P29QQ", "QI20"),
    ("KH6ABC", "BL11"), ("KL7AA", "BP51"), ("ZS6ABC", "KG44"),
    ("CN8XX", "IM63"), ("5Z4BB", "KI88"),
    ("TR8QQ", "JJ40"), ("9J2XX", "KH44"), ("V51AA", "JG87"), ("SU1AA", "KM59"),
    ("3B8BB", "LG89"), ("VP8XX", "GD18"), ("OX3AA", "GP60"),
]
PREFIXES = ["K", "W", "N", "AA", "AB", "AC", "KB", "KC", "KD", "KE", "KF", "KI"]
SUFFIXES = ["DX", "UV", "QK", "TX", "YY", "PT", "BF", "RA", "LM", "NB", "JT", "XP"]

BAND_FREQ = {
    "80m": "3.573000", "40m": "7.074000", "30m": "10.136000",
    "20m": "14.074000", "15m": "21.074000", "10m": "28.074000",
}
OFF_CONTEST_BANDS = ["6m", "2m", "30m"]


def random_call(rng: random.Random) -> str:
    return f"{rng.choice(PREFIXES)}{rng.randint(0, 9)}{rng.choice(SUFFIXES)}"


def adif_record(rng, station, call, grid, band, mode, when, my_grid="EM19RF") -> str:
    """One ADIF record. Lengths are computed, because the parser trusts them."""
    def f(name: str, value: str) -> str:
        return f"<{name}:{len(value)}>{value} "

    def report() -> str:
        return f"{rng.choice('+-')}{rng.randint(1, 20):02d}"

    return (
        f("call", call)
        + f("gridsquare", grid)
        + f("mode", mode)
        + f("rst_sent", report())
        + f("rst_rcvd", report())
        + f("qso_date", when.strftime("%Y%m%d"))
        + f("time_on", when.strftime("%H%M%S"))
        + f("band", band)
        + f("freq", BAND_FREQ.get(band, "14.074000"))
        + f("station_callsign", station)
        + f("my_gridsquare", my_grid)
        + "<eor>"
    )


def wrap_raw(record: str, rng: random.Random) -> str:
    """Wrap a record the way rec.py writes it: header, hex dump, then the ADIF."""
    stamp = datetime.now(timezone.utc).strftime("[%Y-%m-%d %H:%M:%S.%f]")[:-3]
    port = rng.randint(50000, 65000)
    blob = os.urandom(rng.randint(100, 130)).hex()
    return (
        "-" * 80 + "\n"
        + f"{stamp} From ('192.168.1.84', {port}) ({len(blob) // 2} bytes)\n"
        + blob + "\n"
        + record + "\n"
    )


def build(contest, count: int, rng: random.Random, window, dx_share: float = 0.3) -> list[str]:
    """Produce `count` records spread across the given window.

    `dx_share` is the fraction of contacts made with stations outside the US.
    A real collegiate log has plenty of them, and without them DX mode has
    nothing to score and the globe has nothing to plot.
    """
    teams = [t for t in contest.teams if t.callsigns]
    if not teams:
        sys.exit("contest.toml defines no teams with callsigns.")

    bands = sorted(contest.bands) or ["20m", "40m"]
    modes = sorted(contest.modes) or ["FT8"]
    squares = sorted(contest.grid_states) or ["EM19", "EN12", "FN20"]

    start, end = window
    span = max(1, int((end - start).total_seconds()))

    # Give the teams different levels of activity so the standings have a
    # shape — a scoreboard where everyone ties tests nothing.
    weights = [max(1, len(teams) - i) for i in range(len(teams))]
    worked: dict[str, set] = {t.abbr: set() for t in teams}
    records = []

    for _ in range(count):
        team = rng.choices(teams, weights=weights)[0]
        station = rng.choice(team.callsigns)
        when = start + timedelta(seconds=rng.randint(0, span))
        band = rng.choice(bands)
        mode = rng.choice(modes)
        grid = rng.choice(squares)

        roll = rng.random()
        if roll < 0.06 and worked[team.abbr]:
            # A duplicate: same station, same band, already in this team's log.
            call, band = rng.choice(sorted(worked[team.abbr]))
        elif roll < 0.09:
            # Off-contest band — the sort of thing an operator does by accident.
            call = rng.choice(CHASERS)
            band = rng.choice(OFF_CONTEST_BANDS)
        elif roll < 0.09 + dx_share:
            # A DX station, carrying its own grid so the globe plots it in the
            # right country rather than somewhere in Kansas.
            call, grid = rng.choice(DX_STATIONS)
            worked[team.abbr].add((call, band))
        else:
            call = rng.choice(CHASERS) if rng.random() < 0.45 else random_call(rng)
            worked[team.abbr].add((call, band))

        records.append(adif_record(rng, station, call, grid, band, mode, when))

    # A handful logged by stations on no roster: the rest of the world, which
    # the scoreboard has to drop rather than rank.
    for _ in range(max(1, count // 40)):
        when = start + timedelta(seconds=rng.randint(0, span))
        records.append(
            adif_record(rng, random_call(rng), rng.choice(CHASERS),
                        rng.choice(squares), rng.choice(bands),
                        rng.choice(modes), when, my_grid="FN31")
        )

    rng.shuffle(records)
    return records


def contest_window(contest, minutes: int):
    """The configured window, or the last `minutes` if the contest is open."""
    if contest.start and contest.end:
        return contest.start, contest.end
    now = datetime.now(timezone.utc)
    return now - timedelta(minutes=minutes), now


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--qsos", type=int, default=600, help="how many contacts to generate")
    ap.add_argument("--minutes", type=int, default=120,
                    help="window length when contest.toml sets no start/end")
    ap.add_argument("--raw", action="store_true",
                    help="wrap records the way rec.py logs them")
    ap.add_argument("--live", action="store_true",
                    help="append contacts continuously instead of writing once")
    ap.add_argument("--rate", type=float, default=1.5,
                    help="average seconds between contacts in --live mode")
    ap.add_argument("--seed", type=int, default=None, help="make the output repeatable")
    ap.add_argument("--output", default=None,
                    help="defaults to the log_file named in contest.toml")
    args = ap.parse_args()

    contest = config.load()
    rng = random.Random(args.seed)
    out = args.output or contest.log_file

    if args.live:
        return run_live(contest, rng, out, args)

    window = contest_window(contest, args.minutes)
    records = build(contest, args.qsos, rng, window)
    with open(out, "w", encoding="utf-8") as fh:
        for record in records:
            fh.write(wrap_raw(record, rng) if args.raw else record + "\n")

    print(f"Wrote {len(records)} records to {out}")
    print(f"Window: {window[0]:%Y-%m-%d %H:%M} - {window[1]:%H:%M} UTC")
    print("Teams:  " + ", ".join(f"{t.abbr} ({', '.join(t.callsigns)})"
                                 for t in contest.teams if t.callsigns))


def run_live(contest, rng, out, args) -> None:
    """Append one contact at a time so the scoreboard can be watched moving."""
    print(f"Appending to {out} every ~{args.rate}s. Ctrl+C to stop.")
    written = 0
    try:
        while True:
            now = datetime.now(timezone.utc)
            record = build(contest, 1, rng, (now, now))[0]
            with open(out, "a", encoding="utf-8") as fh:
                fh.write(wrap_raw(record, rng) if args.raw else record + "\n")
            written += 1
            print(f"\r{written} contacts appended", end="", flush=True)
            time.sleep(max(0.05, rng.uniform(args.rate * 0.4, args.rate * 1.6)))
    except KeyboardInterrupt:
        print(f"\nStopped after {written} contacts.")


if __name__ == "__main__":
    main()
