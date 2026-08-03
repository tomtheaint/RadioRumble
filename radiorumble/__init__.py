"""Radio Rumble — a live scoreboard for a short collegiate FT8 contest.

The pieces, in the order data moves through them:

    adif.py      turns log text into Qso records
    config.py    contest.toml: the clock, the rules, the team rosters
    scoring.py   folds Qso records into per-team scores
    ingest.py    watches the log file and feeds scoring, exactly once each

``app.py`` at the top level wires them to FastAPI and a websocket.
"""

__all__ = ["adif", "config", "scoring", "ingest"]
