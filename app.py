#!/usr/bin/env python3
"""Radio Rumble — live contest scoreboard.

    uvicorn app:app --host 0.0.0.0 --port 7373 --reload

Serves the scoreboard at / and pushes updates over /ws whenever the log file
grows. The contest itself is defined in contest.toml; nothing here knows the
name of a school or a band.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (Body, Cookie, Depends, FastAPI, File, Form, HTTPException,
                     Request, Response, UploadFile, WebSocket, WebSocketDisconnect)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from radiorumble import auth, config, matches
from radiorumble.db import Database
from radiorumble.ingest import ContestIngest
from radiorumble.listener import WsjtxListener

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("radiorumble")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "index.html"
ADMIN_TEMPLATE = BASE_DIR / "templates" / "admin.html"

contest = config.load()

#  The schedule and the admin password, in the data directory rather than
#  beside the code -- in a container the code is the image, and anything
#  written next to it goes away on the next deploy.
db = Database(config.DATA_DIR / "radiorumble.db")
matches.apply(contest, db)

ingest = ContestIngest(contest)

#  Contacts arrive here as UDP from every operator's WSJT-X and are written
#  into the log directory, where the file watcher picks them up like any other
#  log. Run by the server rather than from a terminal so that whether it is
#  alive is a page rather than a guess.
_listener_cfg = contest.listener or {}
listener = WsjtxListener(
    log_dir=contest.log_dir or contest.log_file.parent,
    host=str(_listener_cfg.get("host", "0.0.0.0")),
    ports=_listener_cfg.get("ports", [2237, 2333]),
    split=bool(_listener_cfg.get("split", True)),
    fallback=contest.log_file,
)

# Voiding a contact changes somebody's score, and the schedule decides who
# is expected at the radio, so neither is something a spectator gets to do.
#
# This used to be one shared token, generated at boot if RR_ADMIN_TOKEN was
# unset. That suited an app whose admin page only struck out contacts during a
# two-hour event -- nothing to set up, nothing left behind. It stopped suiting
# one that owns a schedule: a generated token changes on every restart, and
# a fixed one is a secret in the environment of every shell that starts the
# server. A password chosen once on first launch is less to ask.
#
# radiorumble/auth.py has the mechanics and the reasoning behind them.


def _snapshot() -> dict:
    """The scoreboard, plus which teams the listener can currently hear.

    Merged here rather than in the scoreboard itself: whether a school's radio
    is on says nothing about its score, and `scoring.py` has no business
    knowing a UDP socket exists. But a dot beside the team name is the thing
    somebody running the event looks at first, so it travels with the payload
    that is already being pushed.
    """
    payload = ingest.snapshot(limit=contest.standings_limit)
    live = {row["call"].upper() for row in listener.stations() if row["live"]}
    on_air = {team.abbr for team in contest.teams
              if any(call.upper() in live for call in team.callsigns)}
    for row in payload.get("standings", []):
        row["connected"] = row.get("abbr") in on_air
    return payload


def _safe_name(value: str) -> str:
    """A callsign typed by a stranger becomes part of a filename."""
    keep = [c for c in str(value).upper() if c.isalnum() or c in "-_"]
    return ("".join(keep) or "UNKNOWN")[:24]


def _iso_now() -> str:
    """The server's clock, so a page can say how long ago something was
    without trusting the viewer's laptop to agree about the time."""
    return datetime.now(timezone.utc).isoformat()


def require_admin(rr_admin: str = Cookie(default="")) -> None:
    """Every admin endpoint depends on this.

    409 rather than 403 while no password has been set, because the two are
    different problems with different answers: "sign in" and "claim this
    instance". A page that cannot tell them apart shows a login form to
    somebody who has no password to type.
    """
    if auth.needs_setup(db):
        raise HTTPException(status_code=409,
                            detail="no admin password has been set on this instance yet")
    if not auth.valid_session(db, rr_admin):
        raise HTTPException(status_code=403, detail="sign in on /admin")

# Live websocket connections. Only the event loop touches this set.
clients: set[WebSocket] = set()


async def _broadcast() -> None:
    """Push the current scoreboard to everyone still listening."""
    if not clients:
        return
    payload = json.dumps(_snapshot())
    for ws in tuple(clients):
        try:
            await ws.send_text(payload)
        except Exception:
            clients.discard(ws)


def _on_log_change() -> None:
    """Called from the watchdog thread, so hop back onto the event loop.

    ``run_coroutine_threadsafe`` is the whole point here: touching the
    websockets directly from the observer thread would be a data race on the
    loop's internals rather than a visible error.
    """
    loop = getattr(_on_log_change, "loop", None)
    if loop is not None:
        asyncio.run_coroutine_threadsafe(_broadcast(), loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _on_log_change.loop = asyncio.get_running_loop()
    ingest.on_change = _on_log_change
    ingest.start()
    snapshot = ingest.snapshot()
    log.info(
        "%s (%s, by %s): %d entries, %d contacts scored, status %s",
        contest.name,
        contest.mode,
        contest.compete_as,
        len(contest.teams),
        snapshot["totals"]["qsos_scored"],
        contest.status,
    )
    if auth.needs_setup(db):
        log.info("no admin password set yet -- open /admin to choose one")
    log.info("%d match(es): %d from contest.toml, %d added from the admin page",
             len(contest.matches), len(getattr(contest, "file_matches", ())),
             len(contest.matches) - len(getattr(contest, "file_matches", ())))

    if (contest.listener or {}).get("enabled", True):
        started, message = listener.start()
        # A port already taken is the ordinary failure -- rec.py is often
        # still running from a rehearsal -- and it is worth saying plainly
        # rather than dying. The scoreboard still works from files.
        log.info("listener: %s", message) if started else log.warning("listener: %s", message)
    else:
        log.info("listener: disabled in contest.toml; start it from /listener")

    try:
        yield
    finally:
        listener.stop()
        ingest.stop()


app = FastAPI(title="Radio Rumble", lifespan=lifespan)

# The map outlines are too large to inline in the page, so they are served as
# files and fetched with a path relative to wherever the page was loaded from
# — which keeps them working behind a path-prefixing proxy.
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))


@app.get("/api/scoreboard")
async def scoreboard() -> JSONResponse:
    """The same payload the websocket pushes, for anything that would rather poll."""
    return JSONResponse(_snapshot())


@app.get("/api/board")
async def board() -> JSONResponse:
    """Where the pieces of the board are, for the page to draw.

    Fetched once and cached by the client, the way the state outlines are:
    683 squares never change during a contest, and pushing them down the
    websocket on every log line would be several times the size of the
    scoreboard they decorate.
    """
    from radiorumble.territory import TerritoryMap

    kind, extent = "state", "conus"
    mode = getattr(contest, "mode_settings", {}) or {}
    if contest.mode in ("conquest", "scarcity", "connect"):
        kind = str(mode.get("territory", "state"))
        extent = str(mode.get("extent", "conus"))
    board_map = TerritoryMap(kind, contest.grid_states, extent=extent)
    return JSONResponse({"kind": board_map.kind,
                         "total": board_map.total,
                         "territories": board_map.geometry()})


LISTENER_TEMPLATE = BASE_DIR / "templates" / "listener.html"
CHECK_TEMPLATE = BASE_DIR / "templates" / "check.html"


@app.get("/check", response_class=HTMLResponse)
async def check_page() -> HTMLResponse:
    """"Is it hearing me?" — the question every operator has while setting up.

    Public on purpose. It is the page somebody looks at on their phone at ten
    to two, and putting a token in front of it would mean the answer is only
    available to the person who least needs it.
    """
    return HTMLResponse(CHECK_TEMPLATE.read_text(encoding="utf-8"))


@app.get("/api/stations")
async def stations() -> JSONResponse:
    """Who the listener has heard from, arranged the way the page reads it.

    Two questions, and they are different ones. *Are my team checked in?* is
    answered by a roster: it has to name the operators who have **not** been
    heard, which nothing the listener knows can do on its own — an operator
    who never pointed WSJT-X anywhere is exactly the one somebody is looking
    for. *Who else is out there?* is answered by what was heard.

    Public, minus the addresses: a callsign and a grid are what an operator is
    broadcasting to the world anyway; the address they broadcast it from is
    not, so that stays on the admin side.
    """
    heard = listener.stations(include_address=False)
    by_call = {row["call"].upper(): row for row in heard if row.get("call")}
    playing = set(contest.playing())
    # A free-for-all has no roster to expect anybody from, so the roll call
    # cannot ask "who is missing" — only "who has turned up". The page needs
    # to know which of those two it is showing.
    wide_open = contest.open_now()
    live_matches = [
        {"label": m.label, "open": m.is_open, "teams": list(m.teams)}
        for m in contest.happening()
    ]

    rostered = set()
    teams = []
    for team in contest.teams:
        if wide_open and not any(c.upper() in by_call for c in team.callsigns):
            # Nobody has heard from this entry at all. In a rostered event that
            # is the most important row on the page; in an open one it is an
            # entry from an earlier session with nobody behind it.
            rostered.update(c.upper() for c in team.callsigns)
            continue
        operators = []
        for call in team.callsigns:
            rostered.add(call.upper())
            row = by_call.get(call.upper())
            operators.append({
                "call": call.upper(),
                # The three states an operator can be in, and the middle one is
                # the one worth having: heard earlier, quiet now.
                "heard": row is not None,
                "live": bool(row and row["live"]),
                "last_seen": row["last_seen"] if row else None,
                "last_qso": row["last_qso"] if row else None,
                "quiet_for": row["quiet_for"] if row else None,
                "band": row["band"] if row else "",
                "mode": row["mode"] if row else "",
                "transmitting": bool(row and row["transmitting"]),
                "qsos": row["qsos"] if row else 0,
            })
        teams.append({
            "abbr": team.abbr,
            "name": team.name,
            "color": team.color,
            "playing": team.abbr in playing,
            # A team is connected when any one of its stations is: a school
            # with four operators is on the air if one of them is.
            "connected": any(o["live"] for o in operators),
            "heard_ever": any(o["heard"] for o in operators),
            "live_operators": sum(1 for o in operators if o["live"]),
            "operators": operators,
        })

    return JSONResponse(
        {
            "running": listener.running,
            "ports": list(listener.bound or listener.ports),
            "server_time": _iso_now(),
            "compete_as": contest.compete_as,
            "open": wide_open,
            "matches": live_matches,
            "teams": teams,
            # Everybody else: heard, but on nobody's roster. At a real event
            # this is most of the log and it is not a problem, it is the rest
            # of the world.
            "others": [r for r in heard
                       if (r.get("call") or "").upper() not in rostered],
            "stations": heard,
        }
    )


@app.get("/listener", response_class=HTMLResponse)
async def listener_page() -> HTMLResponse:
    """The control screen. The page is public; every action on it is not."""
    return HTMLResponse(LISTENER_TEMPLATE.read_text(encoding="utf-8"))


@app.get("/api/listener", dependencies=[Depends(require_admin)])
async def listener_status() -> JSONResponse:
    status = listener.status(include_address=True)
    status["server_time"] = _iso_now()
    return JSONResponse(status)


@app.post("/api/listener/start", dependencies=[Depends(require_admin)])
async def listener_start() -> JSONResponse:
    started, message = listener.start()
    return JSONResponse({"started": started, "message": message,
                         "running": listener.running})


@app.post("/api/listener/stop", dependencies=[Depends(require_admin)])
async def listener_stop() -> JSONResponse:
    stopped, message = listener.stop()
    return JSONResponse({"stopped": stopped, "message": message,
                         "running": listener.running})


@app.post("/api/listener/forget", dependencies=[Depends(require_admin)])
async def listener_forget() -> JSONResponse:
    """Clear the presence list without touching a single logged contact.

    Everybody tests before the clock starts, and opening the contest with an
    hour of rehearsal listed is a poor look. The logs are untouched -- this
    forgets who was heard, not what was worked.
    """
    listener.forget()
    return JSONResponse({"cleared": True})


SUBMIT_TEMPLATE = BASE_DIR / "templates" / "submit.html"

#: A collegiate log is a few hundred contacts. A megabyte is a decade of them,
#: and refusing more is cheaper than discovering what a browser will upload.
MAX_LOG_BYTES = 4 * 1024 * 1024


@app.get("/submit", response_class=HTMLResponse)
async def submit_page() -> HTMLResponse:
    """Where an operator hands in their full log after the contest.

    Public, and deliberately so: the whole value of cross-checking is that
    both ends submit, and putting a token in front of it means only officials
    can do the thing every entrant needs to do.
    """
    return HTMLResponse(SUBMIT_TEMPLATE.read_text(encoding="utf-8"))


@app.post("/api/submit")
async def submit_log(file: UploadFile = File(...),
                     callsign: str = Form(default="")) -> JSONResponse:
    """Take a full log and put it where cross-checking will find it.

    The live feed only ever carries contacts an operator completed *during*
    the contest, and only from the moment they pointed WSJT-X here. A full log
    is the whole story: it is what turns "unmatched" into "verified" or "nil",
    and what catches the half hour somebody spent with their reporting
    misconfigured.

    Submitted alongside the live logs rather than over them. A file is never
    replaced -- an operator who submits twice gets two files and the store
    keys contacts by content, so the duplicates fold into one.
    """
    raw = await file.read()
    if len(raw) > MAX_LOG_BYTES:
        raise HTTPException(status_code=413,
                            detail=f"That log is larger than "
                                   f"{MAX_LOG_BYTES // (1024 * 1024)}MB.")
    text = raw.decode("utf-8", "replace")

    from radiorumble import adif

    contacts = adif.parse(text)
    if not contacts:
        raise HTTPException(
            status_code=400,
            detail="No contacts could be read out of that file. It should be "
                   "an ADIF log — the .adi your logging software writes.")

    # Whose log it is comes from the log itself; the typed callsign is only a
    # fallback for a file whose records disagree with each other.
    stations = {q.station for q in contacts if q.station}
    who = (callsign or "").strip().upper() or (
        sorted(stations)[0] if len(stations) == 1 else "MIXED")

    log_dir = contest.log_dir or contest.log_file.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    target = log_dir / f"submitted-{_safe_name(who)}-{stamp}.adi"
    target.write_text(text, encoding="utf-8")
    log.info("log submitted: %s, %d contacts -> %s", who, len(contacts), target.name)

    known = {c.upper() for t in contest.teams for c in t.callsigns}
    return JSONResponse(
        {
            "accepted": True,
            "callsign": who,
            "contacts": len(contacts),
            "stations": sorted(stations),
            "rostered": sorted(s for s in stations if s in known),
            "unrostered": sorted(s for s in stations if s not in known),
            "first": contacts[0].when.isoformat() if contacts[0].when else None,
            "last": contacts[-1].when.isoformat() if contacts[-1].when else None,
            "file": target.name,
        }
    )


@app.get("/api/standings")
async def standings(limit: int = 100, offset: int = 0, q: str = "") -> JSONResponse:
    """The whole field, for when the top of it is not the part you want.

    The scoreboard pushes only its first rows, because a free-for-all with
    three thousand callsigns is 1.4MB of JSON on every log line. Everybody
    below that still needs to be able to find themselves, so the rest of the
    table is here, searchable, and asked for only when somebody asks.
    """
    limit = max(1, min(int(limit or 100), 500))
    with ingest.lock:
        rows = ingest.scoreboard.standings(limit=limit, offset=max(0, offset),
                                           query=q)
        total = len(ingest.scoreboard.teams)
    return JSONResponse({"standings": rows, "entrants": total,
                         "limit": limit, "offset": max(0, offset), "q": q})


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "contest": contest.name,
            "state": contest.status,
            "mode": contest.mode,
            "compete_as": contest.compete_as,
            "log_dir": str(contest.log_dir) if contest.log_dir else None,
            "log_file": str(contest.log_file),
            "log_present": contest.log_file.exists(),
            "contacts_held": len(ingest.store.qsos),
            "voided": len(ingest.store.voids),
        }
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page() -> HTMLResponse:
    """The review screen. The page is public; every action on it is not."""
    return HTMLResponse(ADMIN_TEMPLATE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- signing in

COOKIE_NAME = auth.COOKIE_NAME


def _with_session(payload: dict, value: str, status: int = 200) -> JSONResponse:
    """A JSON reply carrying a fresh admin cookie.

    The cookie goes on the response being *returned*, not on an injected
    `Response` parameter. FastAPI only merges an injected response's headers
    when the handler returns a plain dict; return a JSONResponse and it
    replaces the lot, cookie included. That failed silently -- the login
    answered 200 and set nothing, so every later request was refused with no
    clue why. The tests caught it; a person would have been baffled.

    Not `secure=True`: this app is routinely run on a laptop at an event and
    reached over plain HTTP on the local network, and a Secure cookie would be
    silently dropped there -- the login would appear to work and every
    subsequent request would be refused, which is a miserable thing to debug at
    a radio club. Behind the tunnel it is HTTPS anyway.

    `samesite=lax` and `httponly` still apply: no cross-site posting, and no
    reading it from script.
    """
    response = JSONResponse(payload, status_code=status)
    response.set_cookie(COOKIE_NAME, value, max_age=auth.SESSION_SECONDS,
                        httponly=True, samesite="lax", path="/")
    return response


@app.get("/api/auth")
async def auth_status(rr_admin: str = Cookie(default="")) -> JSONResponse:
    """What the operator pages ask before deciding what to draw.

    Three states, not two: nobody has claimed this instance, somebody has and
    you are not them, or you are signed in.
    """
    return JSONResponse({
        "needs_setup": auth.needs_setup(db),
        "signed_in": auth.valid_session(db, rr_admin),
    })


@app.post("/api/auth/setup")
async def auth_setup(password: str = Body(..., embed=True)) -> JSONResponse:
    """Claim this instance by choosing the admin password.

    Refused once a password exists, because otherwise it is not a setup route,
    it is a password reset with no authentication in front of it.
    """
    if not auth.needs_setup(db):
        raise HTTPException(status_code=409, detail="a password has already been set")
    try:
        auth.set_password(db, password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    log.info("admin password set; this instance is now claimed")
    return _with_session({"ok": True}, auth.issue_session(db))


@app.post("/api/auth/login")
async def auth_login(password: str = Body(..., embed=True)) -> JSONResponse:
    if auth.needs_setup(db):
        raise HTTPException(status_code=409, detail="no password has been set yet")
    if not auth.check_password(db, password):
        # Deliberately not "wrong password" versus "no such account": there is
        # only one account, so the only thing that could vary is the password,
        # and saying so adds nothing an attacker did not already know.
        raise HTTPException(status_code=403, detail="that password was not accepted")
    return _with_session({"ok": True}, auth.issue_session(db))


@app.post("/api/auth/logout")
async def auth_logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE_NAME, path="/")
    return response


# ---------------------------------------------------------------- the games

MODES_TEMPLATE = BASE_DIR / "templates" / "modes.html"


@app.get("/modes", response_class=HTMLResponse)
async def modes_page() -> HTMLResponse:
    """What the games are. Public -- it explains the contest to spectators."""
    return HTMLResponse(MODES_TEMPLATE.read_text(encoding="utf-8"))


@app.get("/api/modes")
async def modes_api() -> JSONResponse:
    """Every game, what it is, how it is won, and what can be tuned.

    Assembled from the mode classes themselves rather than written out here:
    each one carries its own docstring, objective and OPTIONS, so adding a
    seventh game makes it appear on the page with no page to edit. The
    alternative -- a hand-kept list -- had already gone stale twice over, in
    modes.py's own docstring and in contest.toml, both of which described
    three of the six.
    """
    from radiorumble.modes import MODES

    now = datetime.now(timezone.utc)
    active = contest.mode_now(now)
    games = []
    for key, cls in sorted(MODES.items()):
        described = cls.describe()
        described["default"] = key == contest.mode
        described["active"] = key == active
        # What this game is *actually* set to right now, so somebody reading
        # the page knows the difference between the documented default and the
        # value this contest is using.
        described["settings"] = {
            name: contest.mode_settings.get(name, default) if key == contest.mode else default
            for name, default, _about in cls.OPTIONS
        }
        games.append(described)

    bonuses = contest.bonuses
    return JSONResponse({
        "games": games,
        "active": active,
        "default": contest.mode,
        # Settings that belong to the contest rather than to any one game.
        # They apply whichever game is being played, which is exactly why they
        # are worth separating on the page.
        "shared": [
            {"name": "qso_points", "value": contest.qso_points,
             "about": "Points for one accepted contact."},
            {"name": "dupe_scope", "value": contest.dupe_scope,
             "about": "When the same station may be worked again: 'band' "
                      "(once per band), 'band-mode', or 'contest' (once, ever)."},
            {"name": "bands", "value": sorted(contest.bands),
             "about": "Bands that count. A contact on anything else is ignored."},
            {"name": "modes", "value": sorted(contest.modes),
             "about": "Transmission modes that count -- FT8 and FT4, not the game."},
            {"name": "compete_as", "value": contest.compete_as,
             "about": "'team' for schools, 'operator' for individuals, 'open' "
                      "for a free-for-all with no roster."},
            {"name": "match_minutes", "value": contest.match_minutes,
             "about": "How far apart two logs may place the same contact and "
                      "still be treated as the same one."},
        ],
        "bonuses": {
            "enabled": bool(getattr(bonuses, "enabled", False)),
            "items": [
                {"name": n, "value": getattr(bonuses, n, 0), "about": a}
                for n, a in (
                    ("dx", "Extra points for a contact outside the home country."),
                    ("qrp", "The other station logged low power."),
                    ("pota_sota", "POTA/SOTA/WWFF/IOTA named in the log."),
                    ("special_event", "A callsign listed in special_calls."),
                    ("technician_band", "10m, 6m, 2m, 1.25m or 70cm."),
                    ("nil_penalty", "Deducted for a contact the other log denies."),
                )
                if hasattr(bonuses, n)
            ],
        },
    })


# -------------------------------------------------------------- the matches

MATCHES_TEMPLATE = BASE_DIR / "templates" / "matches.html"


@app.get("/matches", response_class=HTMLResponse)
async def matches_page() -> HTMLResponse:
    """The schedule. Readable by anyone; only an official may change it."""
    return HTMLResponse(MATCHES_TEMPLATE.read_text(encoding="utf-8"))


def _mode_choices() -> list:
    """Every game this build can score, with the name it goes by."""
    from radiorumble.modes import MODES

    return [{"key": key, "label": cls.label} for key, cls in sorted(MODES.items())]


def _match_ids() -> dict:
    """Map each stored match back to its row id.

    The contest holds `Match` objects with no idea where they came from, which
    is right -- the scoring rules should not care. But the page needs to know
    which ones it may delete, so the mapping is rebuilt here from the rows
    rather than smuggled into the dataclass.
    """
    out = {}
    for row in db.all_matches():
        out[matches.match_from_row(row)] = row["id"]
    return out


@app.get("/api/matches")
async def list_matches() -> JSONResponse:
    """Now, next, and already played."""
    now = datetime.now(timezone.utc)
    ids = _match_ids()

    def described(items):
        return [matches.describe(m, ids.get(m)) for m in items]

    return JSONResponse({
        "now": described(contest.happening(now)),
        "upcoming": described(contest.upcoming(now)),
        "past": described(contest.past(now, limit=20)),
        "playing": list(contest.playing(now)),
        "open_now": contest.open_now(now),
        "teams": [{"abbr": t.abbr, "name": t.name} for t in contest.teams],
        # The games available, so the page can offer them rather than making
        # somebody read modes.py. Two of the six were not even named in
        # contest.toml's own list of them.
        "modes": _mode_choices(),
        "default_mode": contest.mode,
        "mode_now": contest.mode_now(now),
        "server_time": now.isoformat(),
        # Nothing at all is a state the page should say out loud rather than
        # render as an empty list, because it is the normal state of a fresh
        # install and it means "every team counts as playing".
        "any": bool(contest.matches),
    })


@app.post("/api/matches", dependencies=[Depends(require_admin)])
async def create_match(payload: dict = Body(...)) -> JSONResponse:
    """Add a match.

    A date or a start/end window, never neither: a match with no date is
    permanently on, which silences every other match in the list and is
    almost certainly a typo rather than an intention. The TOML loader allows it
    because a hand-written file is a considered act; a form submission is not.
    """
    label = str(payload.get("label", "")).strip()
    teams = [str(t).strip().upper() for t in payload.get("teams", []) if str(t).strip()]
    wide = bool(payload.get("open")) or not teams

    day = matches._parse_date(payload.get("day"))
    start = matches._parse_datetime(payload.get("start"))
    end = matches._parse_datetime(payload.get("end"))

    if not day and not (start and end):
        raise HTTPException(
            status_code=400,
            detail="Give a date, or both a start and an end. A match with no "
                   "date is always on, which would hide every other one.")
    if start and end and end <= start:
        raise HTTPException(status_code=400, detail="The end has to be after the start.")

    from radiorumble.modes import MODES
    mode = (payload.get("mode") or "").strip().lower() or None
    if mode and mode not in MODES:
        raise HTTPException(
            status_code=400,
            detail=f"No game called {mode!r}. Choose one of: " + ", ".join(sorted(MODES)))

    known = {t.abbr.upper() for t in contest.teams}
    unknown = [t for t in teams if t not in known]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"No team called {', '.join(unknown)}. Teams come from "
                   f"contest.toml; add a [[teams]] block there first.")

    match_id = db.add_match(label=label, teams=teams, day=day,
                            start=start, end=end, is_open=wide, mode=mode)
    matches.apply(contest, db)
    log.info("match %d added: %s", match_id, label or (", ".join(teams) or "open night"))
    return JSONResponse({"id": match_id}, status_code=201)


@app.delete("/api/matches/{match_id}", dependencies=[Depends(require_admin)])
async def remove_match(match_id: int) -> JSONResponse:
    """Delete a stored match.

    Only ones this app wrote. A match from contest.toml has no id to address
    and is not the app's to remove -- saying where it lives is more use than a
    404 would be.
    """
    if not db.delete_match(match_id):
        raise HTTPException(
            status_code=404,
            detail="No stored match with that id. Matches written in "
                   "contest.toml are edited there, not here.")
    matches.apply(contest, db)
    log.info("match %d deleted", match_id)
    return JSONResponse({"ok": True})


@app.get("/api/contacts", dependencies=[Depends(require_admin)])
async def contacts(limit: int = 500, team: str = "", status: str = "") -> JSONResponse:
    """Every contact an official might want to look at, newest first."""
    return JSONResponse(
        {
            "contacts": ingest.contacts(limit=limit, team=team, status=status),
            "teams": [{"abbr": t.abbr, "name": t.name, "color": t.color}
                      for t in contest.teams],
        }
    )


@app.post("/api/contacts/{uid}/void", dependencies=[Depends(require_admin)])
async def void_contact(uid: str, reason: str = "") -> JSONResponse:
    if ingest.store.find(uid) is None:
        raise HTTPException(status_code=404, detail="no such contact")
    changed = ingest.void(uid, reason)
    await _broadcast()
    return JSONResponse({"uid": uid, "voided": True, "changed": changed})


@app.post("/api/contacts/{uid}/restore", dependencies=[Depends(require_admin)])
async def restore_contact(uid: str) -> JSONResponse:
    changed = ingest.restore(uid)
    await _broadcast()
    return JSONResponse({"uid": uid, "voided": False, "changed": changed})


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    try:
        await websocket.send_text(json.dumps(_snapshot()))
        while True:
            # The client says nothing; this is here to notice when it leaves.
            # Without a read, a closed browser tab would sit in `clients`
            # until the next broadcast failed to write to it.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        log.debug("websocket dropped", exc_info=True)
    finally:
        clients.discard(websocket)
