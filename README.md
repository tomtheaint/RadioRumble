# Radio Rumble

A live scoreboard for a short collegiate FT8 contest — schools compete as
teams, the standings move while you watch, and the whole thing is driven by
the ADIF log your station software is already writing.

```bash
uv venv && uv pip install -r requirements.txt
uv run uvicorn app:app --host 0.0.0.0 --port 7373 --reload
```

Then open <http://localhost:7373>.

## The idea

Amateur radio contests are scored the same way everywhere: points for
contacts, multiplied by the number of distinct places you reached. That second
half is what makes it a sport rather than a typing race — a team parked on one
frequency can out-log everybody and still lose to a team that moved around.

Radio Rumble applies that to schools. Each team has a roster of station
callsigns; every contact logged by a rostered station scores for that school.
Everything else in the log — and at a real event that is most of it — belongs
to the rest of the world and is ignored.

**Score = QSO points × grid squares worked.**

## Setting up a contest

Everything lives in [`contest.toml`](contest.toml). Adding a school is adding a
block; it is never a code change.

```toml
[contest]
name  = "Radio Rumble"
start = 2026-09-12T18:00:00Z      # both UTC; omit for an open contest
end   = 2026-09-12T20:00:00Z
log_file = "mock_contest_log.txt"
bands = ["80m", "40m", "20m", "15m", "10m"]
modes = ["FT8", "FT4"]
qso_points = 1
dupe_scope = "band"               # band | band-mode | contest

[[teams]]
name = "Kansas State University"
abbr = "KSU"
color = "#512888"
callsigns = ["KE0VUM"]
```

`callsigns` lists what your operators *log under* — the ADIF
`<station_callsign>` field — not the stations they work.

Two hours is a good length. Long enough that band changes matter, short enough
that a crowd will watch the whole thing.

### The rules, and why each one is there

| Rule | Effect |
|---|---|
| Roster membership | A contact logged by an unrostered call scores for nobody |
| Contest window | Contacts outside `start`–`end` don't count. A contact with no timestamp does — refusing one over a missing optional field is worse than allowing it |
| Band / mode list | Anything off-list is ignored. Empty list means "anything" |
| `dupe_scope = "band"` | Work a station once per band. Working it again on another band counts, which is what makes moving worthwhile |
| Multipliers | Distinct 4-character grid squares. `EM19` and `EM19RF` are the same square and count once |
| States | Derived from [`grid.txt`](grid.txt) and shown for colour. A square straddling a state line credits both — `EM19` is Kansas *and* Missouri |

Dupes are tracked per team, not globally, so the fastest school doesn't lock
everyone else out of a station.

## Feeding it a log

Point `log_file` at whatever your setup writes. Two shapes are understood:

- **Plain ADIF** — what WSJT-X, N1MM and friends produce.
- **The raw listener transcript** that [`rec.py`](rec.py) writes, where each
  QSO sits between a timestamp header and a hex dump of the UDP packet.

The parser looks for ADIF tags and ignores everything between them, so
headers, hex blobs and stray log lines cost nothing.

Reading is incremental: the file is tracked by byte offset, so only genuinely
new bytes are parsed. A record split across two writes is held back until its
`<eor>` arrives, and a file that *shrinks* is treated as a rotation and
re-read from the start.

### Mock data

```bash
python createLog.py                 # 600 contacts over the last two hours
python createLog.py --qsos 2000 --seed 7
python createLog.py --raw           # wrapped the way rec.py logs
python createLog.py --live          # append in real time — watch it move
```

The generator reads `contest.toml`, so the mock data always matches the rules.
It deliberately produces contacts that should *not* score — duplicates,
off-contest bands, unrostered stations — because filtering that has only seen
clean input has never actually been tried. `--live` is the one to use for a
demo: run it in a second terminal and the standings move on their own.

## Layout

```
app.py                  FastAPI: the page, /api/scoreboard, /ws
contest.toml            the clock, the rules, the rosters
radiorumble/
  adif.py               log text -> Qso records
  config.py             contest.toml -> Contest
  scoring.py            Qso records -> per-team scores
  ingest.py             watches the log, feeds scoring exactly once each
templates/index.html    the scoreboard (self-contained: no external requests)
grid.txt                48 states -> 369 grid squares
createLog.py            mock log generator
rec.py                  raw WSJT-X UDP listener
tests/
```

The scoreboard page has no external stylesheet, font or script by design. It
gets opened through whatever network path is to hand at an event — a tunnel, a
path-prefixing proxy, someone's hotspot — and a page that makes no outside
requests cannot lose its styling to a rewritten URL. The websocket address is
built from `location.pathname` for the same reason, and falls back to polling
`/api/scoreboard` where websockets don't survive the trip.

## Endpoints

| Path | Purpose |
|---|---|
| `/` | The scoreboard |
| `/ws` | Websocket; pushes a full snapshot whenever the log grows |
| `/api/scoreboard` | The same snapshot over HTTP, for anything that would rather poll |
| `/api/health` | Status, and whether the log file is actually there |

## Tests

```bash
uv pip install -r requirements-dev.txt
uv run pytest
```

Organised by the rule each one protects — the dupe rule, the window, the
multiplier collapse, and the incremental read that stops a QSO being counted
twice. That last one is worth keeping: an earlier version re-read the tail of
the log on every change, and scores climbed on their own during a contest.
