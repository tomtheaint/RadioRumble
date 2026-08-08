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

import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from radiorumble import config
from radiorumble.ingest import ContestIngest
from radiorumble.listener import WsjtxListener

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("radiorumble")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "index.html"
ADMIN_TEMPLATE = BASE_DIR / "templates" / "admin.html"

contest = config.load()
ingest = ContestIngest(contest)

#  Contacts arrive here as UDP from every operator's WSJT-X and are written
#  into the log directory, where the file watcher picks them up like any other
#  log. Run by the server rather than from a terminal so that whether it is
#  alive is a page rather than a guess.
_listener_cfg = contest.listener or {}
listener = WsjtxListener(
    log_dir=contest.log_dir or contest.log_file.parent,
    host=str(_listener_cfg.get("host", "0.0.0.0")),
    port=int(_listener_cfg.get("port", 2237)),
    split=bool(_listener_cfg.get("split", True)),
    fallback=contest.log_file,
)

# Voiding a contact changes somebody's score, so it is not something a
# spectator gets to do. One shared token is the right weight for a two-hour
# event: no accounts to create, and nothing to leave behind afterwards.
# Generated if unset so the endpoints are never accidentally open.
ADMIN_TOKEN = os.environ.get("RR_ADMIN_TOKEN") or secrets.token_urlsafe(16)
ADMIN_TOKEN_GENERATED = "RR_ADMIN_TOKEN" not in os.environ


def _iso_now() -> str:
    """The server's clock, so a page can say how long ago something was
    without trusting the viewer's laptop to agree about the time."""
    return datetime.now(timezone.utc).isoformat()


def require_admin(x_admin_token: str = Header(default="")) -> None:
    """Constant-time comparison, so the token can't be guessed a byte at a time."""
    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="admin token required")

# Live websocket connections. Only the event loop touches this set.
clients: set[WebSocket] = set()


async def _broadcast() -> None:
    """Push the current scoreboard to everyone still listening."""
    if not clients:
        return
    payload = json.dumps(ingest.snapshot())
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
    if ADMIN_TOKEN_GENERATED:
        log.info("admin token for this run: %s  (set RR_ADMIN_TOKEN to fix it)",
                 ADMIN_TOKEN)

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
    return JSONResponse(ingest.snapshot())


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
    """Who the listener has heard from. Public, minus the addresses.

    A callsign and a grid are what an operator is broadcasting to the world
    anyway; the address they are broadcasting it from is not, so it stays on
    the admin side.
    """
    return JSONResponse(
        {
            "running": listener.running,
            "port": listener.port,
            "server_time": _iso_now(),
            "stations": listener.stations(include_address=False),
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
        await websocket.send_text(json.dumps(ingest.snapshot()))
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
