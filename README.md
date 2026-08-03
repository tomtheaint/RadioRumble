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

## Six games

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

### `scarcity` — the last states standing are the prizes

Conquest, but every state claimed makes the remaining ones worth more. Rhode
Island at minute five is worth the same as Texas; at minute fifty it is worth
several times as much, because it is one of the few left.

The price is locked in at the moment of the claim, so banking a state early
keeps its early price. The reward is for going and getting the awkward ones
*while they are still awkward* — which is the opposite of the incentive in
plain conquest, where the cheap easy states are as good as any.

States never change hands in this mode. A price agreed at the claim would mean
nothing if the state could be taken afterwards.

### `connect` — four in a row

Territory only counts when it touches territory you already hold. Twelve
states scattered across the country are worth nothing; four in a row are worth
everything. Score is the size of your largest unbroken run, and reaching
`target` wins outright.

This is the mode that makes people look at the map before calling CQ — the
nearest unclaimed state stops being an afterthought and becomes the only thing
worth chasing.

### `traverse` — cross the country

An unbroken chain of held states from one side to the other. `axis =
"east-west"` runs Pacific to Atlantic; `"north-south"` runs the Canadian
border to the Gulf. The shortest possible crossings are **seven states** and
**three** respectively, so neither is a formality.

Until somebody completes it, score is the longest chain still reaching back to
the starting coast — partial progress, rather than a scoreboard of zeroes for
most of the afternoon. A completed crossing beats any amount of progress, and
a shorter crossing beats a longer one.

### `dx` — reach, drawn on a globe

Only contacts outside the United States count, and the multiplier is
**countries** rather than grid squares. A team that works twenty stations in
Germany has one multiplier; a team that works twenty countries has twenty. DX
contacts are worth `points_per_dx` (3 by default) because there are far fewer
of them to be had in two hours.

Every contact is plotted on a rotating orthographic globe, positioned from its
grid square. Drag to spin it; it drifts on its own if left alone.

US territories count as DX even though `KH6` and `KP4` look domestic — they are
separate DXCC entities.

Countries come from **`cty.dat`**, the country file every contest program
uses, bundled in `static/`. It is worth having over a hand-written prefix
table: it knows that `UA9X` is European Russia while `UA9A` is Asiatic because
the Urals straddle the continental divide, and it carries some twenty thousand
individual callsigns that are exceptions to their own prefix. Drop in a newer
copy from country-files.com whenever you like — nothing else has to change.

## Setting up a contest

Everything lives in [`contest.toml`](contest.toml). Adding a school is adding a
block; it is never a code change.

```toml
[contest]
name  = "Radio Rumble"
mode  = "conquest"   # classic | conquest | scarcity | connect | traverse | dx
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

## Two boards

`conquest`, `scarcity` and `connect` accept `territory`:

- **`"state"`** — 51 pieces, borders everyone can picture, and a contact often
  claims two at once because a grid square is bigger than a state line.
- **`"grid"`** — 683 squares over the same country, each claimed
  unambiguously. A far longer game, and much more about coverage than luck.

`traverse` is states only: a grid board has no coastline.

## Scoring modifiers

Every one is optional and they stack. Nothing is on by default except the DX
bonus, because a modifier nobody asked for that quietly changes a score is
worse than no modifier at all.

| Setting | Effect |
|---|---|
| `dx` | Extra points outside the home country |
| `qrp` / `qrp_watts` | The other station logged low power (`TX_PWR`) |
| `pota_sota` | A park or summit reference in `SIG` or `COMMENT` |
| `special_event` | A callsign listed in `special_calls` |
| `technician_band` | 10m, 6m, 2m, 1.25m, 70cm — bands a new licensee has |
| `ft4_multiplier` | `0.5` makes an FT4 contact worth half an FT8 one |
| `nil_penalty` | Points *deducted* for a contact the other log lacks |

Everything is read out of the log itself, so nothing has to be declared
separately. The FT4 multiplier scales the total *after* the additions, so a
bonus-laden FT4 contact is still worth half of the same contact on FT8.

`nil_penalty` is deliberately harsher than simply losing the contact: guessing
at a half-copied callsign should cost more than not logging it at all. It is
off by default — it only makes sense once most entrants are submitting logs.

## Who is competing

`compete_as = "team"` puts schools against each other. `compete_as = "operator"`
splits every rostered callsign into its own entry — for a club running a
contest among its own members, or an event thrown open to anyone with a
licence. The machinery is identical; only the unit of competition changes.
Operators keep their school named underneath, and get distinct colours so two
dots on a map are two dots you can tell apart.

Give each entrant a `grid` and their station is drawn on the map and the globe.
That is worth doing: seeing your own dot next to the states you *haven't* taken
is how a team decides which one to chase next.

Teams carry more than a colour. `description`, `gear`, `members`, `website`
and `logo` all appear on the team card — a club station is one callsign and a
dozen people, and the people are the part worth putting on a scoreboard.

## Chasers

Nobody scores without somebody to answer. The people who work the teams are
what makes the event happen, so they get a leaderboard of their own — ranked by
contacts, with the number of different schools reached as the tie-break, and a
**sweep** flag for anyone who worked every one of them. If you are not
competing, a sweep is the thing to chase.

## Cross-checking, and voiding

A contact is one operator's claim that a conversation happened. On its own it
cannot be told apart from an invention. The only real evidence is the other
operator's log saying the same thing.

Point `log_dir` at a directory of submitted logs — one file per entrant — and
every contact is cross-checked:

| Status | Meaning |
|---|---|
| **verified** | the other operator's log has the reciprocal contact |
| **NIL** | they submitted a log and this contact is **not** in it — the classic sign of a busted callsign or an invented contact |
| **unmatched** | they never submitted a log, so there is nothing to check against |
| **voided** | an official struck it out |

**Only NIL is evidence of anything.** Most contacts at a collegiate event are
with people who will never send a log in, and treating those as suspicious
would punish a team for working exactly who the contest wants them to work. So
unmatched contacts score normally, and the cross-check informs a human rather
than silently rewriting anybody's total.

Band has to agree between the two logs. Time is allowed to drift by
`match_minutes` (3 by default) — clocks are not synchronised, and the two ends
record different moments of an exchange that takes about a minute.

### The review screen

`/admin` lists every contact with its status, filterable by entrant and by
status — *NIL only* is the useful one. Voiding removes a contact from every
total it fed and survives a restart; it is reversible.

Actions need `RR_ADMIN_TOKEN`:

```bash
RR_ADMIN_TOKEN=$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))') \
  uv run uvicorn app:app --host 0.0.0.0 --port 7373
```

If you don't set one, a token is generated per run and written to the server
log at startup — so the endpoints are never accidentally open, but you also
can't forget to set it and quietly end up with no protection.

Generate a set of per-entrant logs to try this with:

```bash
python createLog.py --split logs
```

Most contacts between entrants land in both logs; a deliberate handful land in
only one, so there is something for the NIL filter to find.

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

### Live, from WSJT-X

```bash
python rec.py --split           # one file per station, which cross-checking needs
```

Point WSJT-X at this machine under **Reporting → UDP Server**, port 2237.
Every time an operator presses Log, the contact arrives as a UDP datagram, is
decoded, and appended as ADIF — so a live station and a mailed-in file are
indistinguishable by the time they reach the scoreboard. Several instances can
report to one server, which is what a multi-operator team wants.

`rec.py` used to write the hex of every packet and nothing else, recording that
something had happened without recording what. The bytes are still available
with `--raw` when a datagram needs looking at.

### From files

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
  scoring.py            Qso records -> per-entrant scores (mode-independent)
  modes.py              what a contact is worth: classic, conquest, scarcity, dx
  maidenhead.py         grid square -> latitude and longitude
  territory.py          the board: what a contact claims, what touches what
  bonuses.py            the optional scoring modifiers
  dxcc.py               callsign -> country, via cty.dat
  cty.py                the cty.dat parser
  wsjtx.py              decodes WSJT-X's UDP datagrams
  store.py              every contact held, plus the void list
  verify.py             one log checked against another
  ingest.py             watches the logs, reads each byte once
templates/index.html    scoreboard, US map and globe in one page
templates/admin.html    the review screen
static/
  us-states.json        50 states + DC, Natural Earth
  world-land.json       world coastline, Natural Earth
  adjacency.json        which states border which, generated
  cty.dat               the DXCC country file
grid.txt                grid square -> state, generated by tools/build_grid.py
tools/build_grid.py     regenerates grid.txt from the state boundaries
tools/build_adjacency.py  regenerates the neighbour graph
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
| `/ws` | Websocket; pushes a full snapshot whenever a log grows |
| `/api/scoreboard` | The same snapshot over HTTP, for anything that would rather poll |
| `/api/health` | Status, how many contacts are held, how many are voided |
| `/admin` | The review screen |
| `/api/contacts` | Every contact with its status. Needs the admin token |
| `/api/contacts/{uid}/void` · `/restore` | Strike one out, or put it back |

Reading is incremental — each byte of each log is parsed once — but what is
*derived* from the contacts is rebuilt from scratch on every change. It has to
be: cross-checking and voiding both reach backwards. A contact scored an hour
ago becomes confirmed when the other operator finally submits, and one struck
out has to leave every total it ever fed.

## Tests

```bash
uv pip install -r requirements-dev.txt
uv run pytest
```

Organised by the rule each one protects — the dupe rule, the window, the
multiplier collapse, and the incremental read that stops a QSO being counted
twice. That last one is worth keeping: an earlier version re-read the tail of
the log on every change, and scores climbed on their own during a contest.
