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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from radiorumble import config
from radiorumble.ingest import ContestIngest
from radiorumble.scoring import Scoreboard

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("radiorumble")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE = BASE_DIR / "templates" / "index.html"

contest = config.load()
ingest = ContestIngest(Scoreboard(contest))

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
        "%s: %d teams, %d QSOs scored, status %s",
        contest.name,
        len(contest.teams),
        snapshot["totals"]["qsos_scored"],
        contest.status,
    )
    try:
        yield
    finally:
        ingest.stop()


app = FastAPI(title="Radio Rumble", lifespan=lifespan)


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
            "log_file": str(contest.log_file),
            "log_present": contest.log_file.exists(),
        }
    )


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
