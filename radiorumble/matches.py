"""The schedule, from both places a match can come from.

``contest.toml`` can carry ``[[matches]]``, and the admin page can now write
them too. Neither is the loser: a season checked into the repository alongside
the teams is a perfectly good way to run this, and so is typing next week's
match into a form on the night.

So they are merged rather than one overriding the other, and the app never
rewrites the TOML. That file is hand-authored and heavily commented -- forty
lines of documentation live in its matches section alone -- and no round-trip
TOML writer preserves comments. A file the app edits is a file whose comments
have a life expectancy.

The rule for telling them apart afterwards: rows from the database carry an
``id`` and can be deleted from the page; matches from the file do not and
cannot. Trying to delete one is an error that says where it actually lives,
rather than a button that silently does nothing.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone

from .config import Match


def _parse_date(text):
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _parse_datetime(text):
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    # Naive input is read as UTC, matching the TOML loader and the rest of the
    # app -- every clock here is UTC and a bare timestamp meaning local time
    # would be a different answer depending on which machine wrote it.
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def match_from_row(row) -> Match:
    """A database row as the same Match the TOML loader produces."""
    try:
        teams = tuple(json.loads(row["teams"]))
    except (ValueError, TypeError):
        teams = ()
    return Match(
        teams=teams,
        day=_parse_date(row["day"]),
        start=_parse_datetime(row["start_at"]),
        end=_parse_datetime(row["end_at"]),
        label=row["label"] or "",
        open=bool(row["is_open"]) or not teams,
        mode=(row["mode"] or None) if "mode" in row.keys() else None,
    )


def stored_matches(db) -> tuple:
    return tuple(match_from_row(row) for row in db.all_matches())


def apply(contest, db) -> None:
    """Point the contest at the file's matches plus the stored ones.

    Mutates rather than returning a copy, because one Contest object is loaded
    at import and referenced from the scoreboard, the roll call and the
    listener. Handing back a second one would leave those looking at the first.

    ``file_matches`` is kept so this can be called again after a match is
    added or deleted without the TOML ones multiplying each time.
    """
    if not hasattr(contest, "file_matches"):
        contest.file_matches = tuple(contest.matches)
    contest.matches = tuple(contest.file_matches) + stored_matches(db)


def describe(match, source_id=None) -> dict:
    """A match as JSON for the page.

    ``id`` is None for a match that came from the TOML, which is what the
    page uses to decide whether to offer a delete button.
    """
    begins = match.begins()
    return {
        "id": source_id,
        "label": match.label,
        "teams": list(match.teams),
        "open": match.is_open,
        "day": match.day.isoformat() if match.day else None,
        "start": match.start.isoformat() if match.start else None,
        "end": match.end.isoformat() if match.end else None,
        "begins": begins.isoformat() if begins else None,
        "mode": match.mode,
        "editable": source_id is not None,
    }
