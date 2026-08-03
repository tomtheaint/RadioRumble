"""cty.dat — the country file every contest program uses.

Working out which country a callsign belongs to is not a job for a handful of
prefix rules. Entities split, merge and get reassigned; operators sign
portable from places their home prefix says nothing about; and a dozen
callsigns are simply exceptions that no rule covers. AD1C's ``cty.dat`` is the
maintained answer to all of that, updated as the DXCC list changes, and it is
what serious log checkers compare against.

The format is one record per entity::

    United States:            05:  08:  NA:   37.60:    91.87:     5.0:  K:
        AA,AB,AC,K,N,W,=N2NL/MM(7),AA0(4)[7],...;

A header line of eight colon-separated fields, then a comma-separated prefix
list terminated by a semicolon. Prefixes may carry overrides in brackets —
``(n)`` CQ zone, ``[n]`` ITU zone, ``<lat/lon>`` position, ``{XX}`` continent —
and a leading ``=`` marks a full callsign rather than a prefix.

One trap worth naming: **cty.dat longitude is positive west.** Feeding it
straight to a map puts every entity on the wrong side of the world.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CTY = BASE_DIR / "static" / "cty.dat"

# (n) cq zone, [n] itu zone, <lat/lon>, {continent}, ~offset~
_OVERRIDE = re.compile(r"\((\d+)\)|\[(\d+)\]|<([-\d./]+)>|\{(\w+)\}|~([-\d.]+)~")


@dataclass(frozen=True)
class Entity:
    name: str
    primary: str          # primary prefix, the entity's short name
    continent: str
    cq_zone: int
    itu_zone: int
    lat: float
    lon: float            # already flipped to the usual positive-east

    @property
    def position(self) -> tuple[float, float]:
        return (self.lat, self.lon)


class CtyLookup:
    """Prefix table with exact-callsign overrides."""

    def __init__(self) -> None:
        self.entities: dict[str, Entity] = {}
        self.exact: dict[str, Entity] = {}
        self.prefixes: dict[str, Entity] = {}
        self._by_length: list[tuple[int, dict[str, Entity]]] = []

    # -- parsing ----------------------------------------------------------

    @classmethod
    def load(cls, path: Path = DEFAULT_CTY) -> "CtyLookup":
        table = cls()
        if not path.exists():
            return table
        table.parse(path.read_text(encoding="utf-8", errors="replace"))
        return table

    def parse(self, text: str) -> None:
        record: list[str] = []
        for raw in text.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            record.append(line)
            if line.rstrip().endswith(";"):
                self._record(record)
                record = []
        self._index()

    def _record(self, lines: list[str]) -> None:
        header = lines[0]
        fields = [f.strip() for f in header.split(":")]
        if len(fields) < 8:
            return
        name, cq, itu, continent, lat, lon, _offset, primary = fields[:8]
        try:
            entity = Entity(
                name=name,
                primary=primary.strip(),
                continent=continent,
                cq_zone=int(cq or 0),
                itu_zone=int(itu or 0),
                lat=float(lat or 0),
                # cty.dat is positive-west; everything else in the world is not.
                lon=-float(lon or 0),
            )
        except ValueError:
            return
        self.entities[entity.primary] = entity

        body = " ".join(lines[1:]) if len(lines) > 1 else ""
        body = body.replace(";", "").strip()
        for token in body.split(","):
            token = token.strip()
            if not token:
                continue
            self._prefix(token, entity)

    def _prefix(self, token: str, entity: Entity) -> None:
        """One prefix, possibly with per-prefix overrides in brackets."""
        overrides = list(_OVERRIDE.finditer(token))
        key = _OVERRIDE.sub("", token).strip()
        if not key:
            return

        # A prefix may sit at a different place than its entity's centre —
        # a Russian prefix in Asia, say — and that is what gets plotted.
        lat, lon, continent = entity.lat, entity.lon, entity.continent
        for match in overrides:
            if match.group(3):
                try:
                    plat, plon = match.group(3).split("/")
                    lat, lon = float(plat), -float(plon)
                except ValueError:
                    pass
            if match.group(4):
                continent = match.group(4)

        local = entity
        if (lat, lon, continent) != (entity.lat, entity.lon, entity.continent):
            local = Entity(entity.name, entity.primary, continent,
                           entity.cq_zone, entity.itu_zone, lat, lon)

        if key.startswith("="):
            self.exact[key[1:].upper()] = local
        else:
            self.prefixes[key.upper()] = local

    def _index(self) -> None:
        """Group prefixes by length so lookup can try longest first."""
        buckets: dict[int, dict[str, Entity]] = {}
        for prefix, entity in self.prefixes.items():
            buckets.setdefault(len(prefix), {})[prefix] = entity
        self._by_length = sorted(buckets.items(), reverse=True)

    # -- lookup -----------------------------------------------------------

    def lookup(self, callsign: str) -> Entity | None:
        """The entity a callsign belongs to, longest prefix winning."""
        call = (callsign or "").upper().strip()
        if not call:
            return None

        base = strip_portable(call)

        # An exact entry beats every rule: that is what it is there for.
        for candidate in (call, base):
            if candidate in self.exact:
                return self.exact[candidate]

        for length, bucket in self._by_length:
            if length > len(base):
                continue
            found = bucket.get(base[:length])
            if found is not None:
                return found
        return None

    def __bool__(self) -> bool:
        return bool(self.prefixes)

    def __len__(self) -> int:
        return len(self.entities)


def strip_portable(callsign: str) -> str:
    """Reduce a callsign to the part that says where the operator is.

    ``W1ABC/VE3`` is a US operator in Canada, and the contact is with Canada.
    ``/P``, ``/M``, ``/QRP`` and a bare digit say nothing about location, so
    they are discarded and the home call kept.
    """
    call = callsign.upper().strip()
    if "/" not in call:
        return call

    ignorable = {"P", "M", "MM", "AM", "QRP", "A", "R", "LH", "B", "J", "1", "2",
                 "3", "4", "5", "6", "7", "8", "9", "0"}
    parts = [p for p in call.split("/") if p and p not in ignorable]
    if not parts:
        return call.split("/")[0]
    if len(parts) == 1:
        return parts[0]

    # Two real parts: the shorter is the location prefix, as in W1ABC/VE3.
    a, b = parts[0], parts[1]
    return b if len(b) < len(a) else a
