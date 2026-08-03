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

Radio Rumble is schools competing over the air. Each team has a roster of
station callsigns; every contact logged by a rostered station scores for that
school. Everything else in the log — and at a real event that is most of it —
belongs to the rest of the world and is ignored.

## Three games

Same log, same teams, same clock. What changes is what a contact is *worth*.
Set `mode` in [`contest.toml`](contest.toml), or override it for a demo with
`RR_MODE=dx uvicorn app:app ...`.

### `classic` — points × places

The traditional shape. A contact is a point; each new grid square multiplies
them. That second half is what makes it a sport rather than a typing race — a
team parked on one frequency can out-log everybody and still lose to a team
that moved around.

### `conquest` — a map of the United States

Work a station in a state and your school owns it, coloured in your colours on
a live map. **Score is territory held**, and the map is the scoreboard.

A grid square is 2 degrees by 1 — roughly 100 miles by 70 — so it routinely
straddles a state line, and FT8 sends a grid square and nothing else. A
contact into a square that spans a border therefore stakes a claim in every
state it touches. That is the honest reading: there is genuinely no way to
tell which side of the line the other station was on.

Who holds a state is set by `claim`:

| `claim` | Behaviour |
|---|---|
| `first` | Whoever gets there first keeps it. Rewards speed; the map stops changing once it fills up. |
| `most` | Whoever has the most contacts into it, ties going to whoever claimed it first. States change hands all afternoon — **this is the version that behaves like a game.** |

Contacts outside the US can't take territory, and are reported as *not in a US
state* rather than dropped silently.

### `dx` — reach, drawn on a globe

Only contacts outside the United States count, and the multiplier is
**countries** rather than grid squares. A team that works twenty stations in
Germany has one multiplier; a team that works twenty countries has twenty. DX
contacts are worth `points_per_dx` (3 by default) because there are far fewer
of them to be had in two hours.

Every contact is plotted on a rotating orthographic globe, positioned from its
grid square. Drag to spin it; it drifts on its own if left alone.

US territories count as DX even though `KH6` and `KP4` look domestic — they are
separate DXCC entities. Callsigns are resolved by prefix, and a portable
indicator names where the operator actually is, so `W1ABC/VE3` is Canada.

## Setting up a contest

Everything lives in [`contest.toml`](contest.toml). Adding a school is adding a
block; it is never a code change.

```toml
[contest]
name  = "Radio Rumble"
mode  = "conquest"                # classic | conquest | dx
start = 2026-09-12T18:00:00Z      # both UTC; omit for an open contest
end   = 2026-09-12T20:00:00Z
log_file = "mock_contest_log.txt"
bands = ["80m", "40m", "20m", "15m", "10m"]
modes = ["FT8", "FT4"]
qso_points = 1
dupe_scope = "band"               # band | band-mode | contest

[conquest]
claim = "first"                   # first | most

[dx]
points_per_dx = 3
count_domestic = false

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

These apply in every mode:

| Rule | Effect |
|---|---|
| Roster membership | A contact logged by an unrostered call scores for nobody |
| Contest window | Contacts outside `start`–`end` don't count. A contact with no timestamp does — refusing one over a missing optional field is worse than allowing it |
| Band / mode list | Anything off-list is ignored. Empty list means "anything" |
| `dupe_scope = "band"` | Work a station once per band. Working it again on another band counts, which is what makes moving worthwhile |
| Multipliers | Distinct 4-character grid squares. `EM19` and `EM19RF` are the same square and count once |

Dupes are tracked per team, not globally, so the fastest school doesn't lock
everyone else out of a station.

Every rejection is counted and shown under the scoreboard. At a live event
"my last ten contacts didn't count" is the question that actually gets asked,
and an answer of *dupe on 20m* ends the conversation where a silent drop
starts an argument.

### Where the geography comes from

[`grid.txt`](grid.txt) maps grid squares to states and is **generated**, not
hand-written:

```bash
python tools/build_grid.py
```

It samples a lattice of points inside each square against the real state
boundaries in `static/us-states.json` and records every state any of them
lands in. The hand-maintained list this replaced was missing `EM19` entirely —
the square containing Manhattan, Kansas — while crediting Kansas with squares
that are in Colorado and Oklahoma. Of 683 squares touching the country, 158
span more than one state.

Map outlines are Natural Earth (public domain), converted from TopoJSON and
bundled so nothing is fetched at runtime — an event venue's wifi is not
something to depend on.

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
app.py                  FastAPI: the page, /api/scoreboard, /ws, /static
contest.toml            the mode, the clock, the rules, the rosters
radiorumble/
  adif.py               log text -> Qso records
  config.py             contest.toml -> Contest
  scoring.py            Qso records -> per-team scores (mode-independent)
  modes.py              what a contact is worth: classic, conquest, dx
  maidenhead.py         grid square -> latitude and longitude
  dxcc.py               callsign prefix -> country and continent
  ingest.py             watches the log, feeds scoring exactly once each
templates/index.html    scoreboard, US map and globe in one page
static/
  us-states.json        50 states + DC, Natural Earth
  world-land.json       world coastline, Natural Earth
grid.txt                grid square -> state, generated by tools/build_grid.py
tools/build_grid.py     regenerates grid.txt from the state boundaries
createLog.py            mock log generator
rec.py                  raw WSJT-X UDP listener
tests/
```

A mode never sees the log or the roster. It is handed a contact that has
already passed every common rule and says what that contact does to a score —
which is why adding a fourth game means adding one class to `modes.py`.

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
