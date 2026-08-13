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
- **`"grid"`** — 469 squares over the same country, each claimed
  unambiguously. A far longer game, and much more about coverage than luck.

`traverse` is states only: a grid board has no coastline.

### How much country is on the grid board

`extent` decides, and only matters for `territory = "grid"`:

| `extent` | Board |
|---|---|
| `conus` | The lower 48 — **469 squares**. Every one is reachable in a short contest and legible on the map. The default. |
| `all` | **683 squares**, adding Alaska and Hawaii. |

Alaska alone is **207 of those 683 — 30% of the board**, and nearly all of it
is Aleutian sea that nobody will work in two hours. On the state board Alaska
is one piece in fifty-one and costs nothing; on the grid board it is a third
of the denominator, so "68 of 683 held" stops meaning anything and the map has
to squeeze 207 squares into an inset the size of a postage stamp.

Narrowing the board never costs anyone a contact. An Alaskan station still
scores exactly as it did — it just doesn't take a square.

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

| `compete_as` | Who competes |
|---|---|
| `team` | Schools against each other, rosters as written |
| `operator` | Every **rostered** callsign as its own entry — a club running a contest among its own members |
| `open` | A **free-for-all**. No roster at all: anybody whose log reaches the server is entered, from the moment it does |

The machinery is identical; only the unit of competition changes. Operators
keep their school named underneath, and get distinct colours so two dots on a
map are two dots you can tell apart.

`open` is the one that needed building. `operator` still requires everybody to
be listed in advance, and a club night or anything advertised on a repeater
does not work that way — you find out who entered by seeing who turns up, and
the first contact somebody logs is the only moment we could possibly learn they
exist. So the entry is created then, keeping the colour it was given so a field
does not repaint itself on a reload.

Teams listed under an open event are still honoured: they are pre-registered
entrants with a name and colours somebody chose, and everybody else is admitted
on arrival. Every game mode works unchanged — a mode is handed an entrant and
asked what a contact is worth, and has never needed to know whether that
entrant is a school or a stranger.

A rostered event still keeps the world out, which is the invariant the
standings depend on: at a collegiate event most of the log is contacts with
people who never entered.

### How many people can enter

As many as turn up. **Nobody is capped — only the list is.**

Scoring is not the constraint: 60,000 contacts across 3,000 entrants is under
two seconds, and the whole thing is rebuilt from scratch on every change. What
did not scale was the *payload*. The scoreboard pushes a full snapshot down the
websocket every time the log grows, and a table of three thousand callsigns is
1.4MB a time.

So `standings_limit` (default 15) caps the rows that are sent:

| Entrants | Payload sent | Snapshot |
|---|---|---|
| 250 | 21 KB | 0.03s |
| 1,000 | 21 KB | 0.13s |
| 3,000 | 21 KB | 0.23s |
| 10,000 | 21 KB | 0.54s |

Flat, because the size of the field stopped being in it. Three things had to be
true for that:

- **The map carries only the colours it uses.** It used to carry one per
  entrant, which would have moved the problem rather than fixed it — a
  territory board is bounded by the board, not by the field.
- **Only the rows being sent are built.** `as_dict` pulls in every band, mode,
  operator and bonus an entry has; doing that for ten thousand people to show
  fifteen was most of the cost of a snapshot.
- **A position is a position in the whole field.** Row 400 says 400, or the cap
  turns a leaderboard into a lie.

Everybody below the cut is still scored, still holds territory, still counts
towards every total on the page — and can still find themselves:
`/api/standings?q=` serves the whole table, searchable, and the page asks for it
only when somebody types. Set `standings_limit = 0` to send everyone, which is
the right answer for a handful of schools.

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

### The two admin screens

There are two, and they are one click apart:

| | |
| --- | --- |
| **[`/listener`](http://localhost:7373/listener)** | Start and stop the WSJT-X listener, and see what it has heard |
| **[`/admin`](http://localhost:7373/admin)** | Review the log: every contact, its status, and voiding |
| **[`/matches`](http://localhost:7373/matches)** | The fixture list: what is on, what is next, and adding one |

One password covers all three. Sign in on any of them and the rest follow —
the session is a cookie, so it travels with the browser rather than with the
tab, and it outlives a restart of the server.

### The review screen

`/admin` lists every contact with its status, filterable by entrant and by
status — *NIL only* is the useful one. Voiding removes a contact from every
total it fed and survives a restart; it is reversible.

Actions need the admin password. The first time anybody opens `/admin` on a new
instance it asks for one to be set; there are no accounts, just the one
password, and setting it is what claims the instance. Until then every admin
endpoint answers 409 — an unclaimed instance is not an open one.

Six characters is the minimum. This guards a scoreboard for an afternoon, not a
bank, and a password somebody has to shout across a radio room should be short
enough to shout.

Forgotten it? Delete the stored hash and the next visit starts over:

```bash
sqlite3 data/radiorumble.db "DELETE FROM settings WHERE key = 'admin_password'"
```

You can also hand the token to either admin page in the address bar, which
saves typing it on a laptop across the room:

```
http://<host>:7373/admin#token=YOUR_TOKEN
http://<host>:7373/listener#token=YOUR_TOKEN
```

Put it in the **fragment** (`#token=`) rather than the query string: a fragment
never leaves the browser, so the token stays out of the server's access log and
out of any proxy in between. `?token=` is accepted too, for when something has
mangled the `#`. Either way the page strips it from the address bar as soon as
it reads it — it still lands in that browser's history, so a shared machine
wants the box instead.

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

The server listens itself, on **both** of WSJT-X's reporting servers, because
operators can only spare one of them and it is rarely the same one twice.

| WSJT-X setting | Port | Sends | You appear |
|---|---|---|---|
| **Secondary UDP Server** — “Enable logged contact ADIF broadcast” | 2333 | One ADIF record per logged contact, and nothing else | **After your first contact** |
| **UDP Server** | 2237 | The whole protocol: heartbeat, status, contacts | **Within ~15 seconds**, before working anybody |

The secondary is the one most operators have free — the box above it is usually
taken by JTAlert or GridTracker — and WSJT-X marks it deprecated, which has not
stopped it being the practical answer. The cost is that it is silent until a
contact is logged, so a station using it cannot be seen setting up. That is a
property of the protocol, not of this app.

Which shape a datagram is decided by **what is in it**, not by the port it
arrived on: a header beginning `0xadbccbda` is read as WSJT-X, anything else is
tried as ADIF. So an operator who puts the secondary in the primary's box is
still understood, which somebody will and it is not worth a support
conversation. Either way the contact is appended as ADIF into the log
directory, so a live station and a mailed-in file are indistinguishable by the
time they reach the scoreboard.

It starts with the server and is configured in `[listener]`:

```toml
[listener]
enabled = true
host = "0.0.0.0"
ports = [2237, 2333]
split = true        # one file per station callsign, which cross-checking needs
```

One port failing does not stop the other, and which ones actually bound is on
the listener page.

#### “Is it hearing me?”

**[`/check`](http://localhost:7373/check) is public and is the point.** Every
operator has the same question while setting up, and before this the only way
to answer it was to work somebody and hope.

Two sections, because there are two questions.

**Roll call** — the teams playing today, one card each, with a dot on the team
name for whether their radio is reaching us. Under it, every rostered operator
and the time of their last contact. The state worth having is the third one:

| | |
|---|---|
| **live** | heard within the last 90 seconds |
| **last heard 6 min ago** | they were here and have gone quiet |
| **not heard yet** | nothing, ever — the row somebody checking in is looking for |

That last one is why the roster drives this section rather than the listener:
the operator you are hunting for is by definition the one who has never sent
anything, and no amount of listening produces them. Filterable by team.

**Everyone else** — every station heard that is on nobody's roster, with a
slider for how far back to look: 5 minutes, 15, an hour, 3 hours, a day, or
any time. At a real event this is most of the log, and it is not a problem —
it is the rest of the world.

Both refresh every five seconds. How soon somebody appears depends on which
box they used, per the table above; the page says so rather than leaving an
operator on the secondary server wondering why nothing happened.

Addresses are not shown: a callsign is broadcast to the world anyway and an
address is not.

The same dot appears beside each team on the scoreboard itself, which is what
somebody running the event looks at first. It is merged onto the payload in
`app.py` rather than computed in `scoring.py` — whether a school's radio is on
says nothing about its score, and the scoreboard has no business knowing a UDP
socket exists.

#### Who is playing today

`[[matches]]` is optional. Leave it out and every team counts as playing, which
is what a one-off event means:

```toml
[[matches]]
date  = 2026-09-12
teams = ["KU", "KSU"]
label = "Week 1"
```

Write it and the roll call shows only the schools actually expected at the
radio that afternoon — listing forty teams when four are playing is as useless
as listing none. Use `start`/`end` instead of `date` when a day is not precise
enough.

A **free-for-all is a fixture with nobody named in it**, because a fixture with
nobody in it can only mean everybody:

```toml
[[matches]]
date  = 2026-09-19
open  = true
label = "Open night"
```

A season of team matches can hold an open night among them. On an open night
the roll call stops asking "who is missing" — there is no roster to ask it of —
and becomes a list of who has checked in.

#### Controlling it

**[`/listener`](http://localhost:7373/listener)** starts and stops it, and
shows what it has heard — per station and in total, over the last minute, hour
and day. The page is public; every action on it needs the admin password, like
the review screen.

*Clear presence* forgets who has been heard without touching a single logged
contact. Everybody tests before the clock starts, and opening the contest with
an hour of rehearsal listed is a poor look — but the contacts are the
operator's log and are not ours to delete.

A port already in use is the ordinary failure — `rec.py` is often still running
from a rehearsal — and it is reported on the page rather than stopping the
server. The scoreboard still works from files.

#### Still fine from a terminal

```bash
python rec.py --split           # one file per station, which cross-checking needs
```

[`rec.py`](rec.py) does the same job standalone, which is what you want when
the scoreboard is somewhere else. The trouble with a terminal is that nobody
can see it: if it dies, or was never started, or is bound to the wrong port,
the first anybody knows is that the scoreboard stayed at zero. That is why the
server does it too.

The raw bytes are available with `--raw` when a datagram needs looking at.

### Full logs, afterwards

**[`/submit`](http://localhost:7373/submit) is public**, for the same reason
the check page is: cross-checking only works when *both* ends submit, and a
token in front of it would mean only officials could do the thing every entrant
needs to do.

The live feed only carries contacts an operator completed while their reporting
was pointed here. A full log is the whole story — it is what turns a contact
from **unmatched** into **verified** or **nil**, and what catches the half hour
somebody spent with their settings wrong. The file lands beside the live logs
as `submitted-<CALL>-<timestamp>.adi`, and cross-checking picks it up on the
next read.

Submitting twice is harmless and never overwrites: contacts are keyed by their
content, so duplicates fold into one. Whose log it is comes from the log's own
`station_callsign` fields; the callsign box is only a fallback for a file whose
records disagree with each other.

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
  listener.py           the UDP listener the server runs, and who it has heard
  store.py              every contact held, plus the void list
  verify.py             one log checked against another
  ingest.py             watches the logs, reads each byte once
templates/index.html    scoreboard, US map and globe in one page
templates/admin.html    the review screen
templates/listener.html the listener's controls
templates/check.html    "is it hearing me?", for operators setting up
templates/submit.html   handing in a full log afterwards
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
| `/api/board` | The pieces of the board and where they are. Fetched once by the page |
| `/api/standings` | The whole field, paged and searchable, for everyone below the cut |
| `/check` | “Is it hearing me?” — public, for operators setting up |
| `/api/stations` | Who the listener has heard from. Public, minus the addresses |
| `/submit` · `/api/submit` | Hand in a full log after the contest. Public |
| `/listener` | Start, stop, and what has been heard |
| `/api/listener` · `/start` · `/stop` · `/forget` | The same, as JSON. Needs signing in |
| `/api/health` | Status, how many contacts are held, how many are voided |
| `/admin` | The review screen |
| `/api/contacts` | Every contact with its status. Needs signing in |
| `/api/contacts/{uid}/void` · `/restore` | Strike one out, or put it back |
| `/matches` · `/api/matches` | The fixture list. Public to read; signing in to change |
| `/api/auth` · `/setup` · `/login` · `/logout` | Claim the instance, sign in, sign out |

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
