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
from contextlib import asynccontextmanager
from pathlib import Path

import os
import secrets

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from radiorumble import config
from radiorumble.ingest import ContestIngest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("radiorumble")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "index.html"
ADMIN_TEMPLATE = BASE_DIR / "templates" / "admin.html"

contest = config.load()
ingest = ContestIngest(contest)

# Voiding a contact changes somebody's score, so it is not something a
# spectator gets to do. One shared token is the right weight for a two-hour
# event: no accounts to create, and nothing to leave behind afterwards.
# Generated if unset so the endpoints are never accidentally open.
ADMIN_TOKEN = os.environ.get("RR_ADMIN_TOKEN") or secrets.token_urlsafe(16)
ADMIN_TOKEN_GENERATED = "RR_ADMIN_TOKEN" not in os.environ


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
    try:
        yield
    finally:
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
