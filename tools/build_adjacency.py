#!/usr/bin/env python3
"""Work out which states border which, from static/us-states.json.

    python tools/build_adjacency.py

Two states are neighbours if their outlines share points. The boundaries come
from one dataset, so a shared border really is the same coordinates in both
shapes — no distance threshold, no guessing.

Also records the west, east, north and south edges of the country, because a
game about crossing it has to know where crossing starts and stops. Alaska and
Hawaii are excluded from those: a line to the Pacific is not a line to Hawaii.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATES = BASE / "static" / "us-states.json"
OUTPUT = BASE / "static" / "adjacency.json"

OFFSHORE = {"Alaska", "Hawaii"}

# The neighbour graph is computed; these are declared, on purpose.
#
# Deriving "which states are on the edge of the country" from the outlines
# does not work. Every rule that looks reasonable — furthest west, no
# neighbour beyond it — puts the District of Columbia on all four sides and
# Delaware on the west coast, because tiny states break comparisons between
# extents. More to the point, where a crossing starts and stops is a rules
# decision rather than a geometric fact: an organiser might want Pacific to
# Atlantic, or Canada to Mexico, and both are defensible.
#
# Override any of these in contest.toml under [traverse].
EDGES = {
    # Pacific coast.
    "west": ["California", "Oregon", "Washington"],
    # Atlantic coast, top to bottom.
    "east": ["Connecticut", "Delaware", "Florida", "Georgia", "Maine", "Maryland",
             "Massachusetts", "New Hampshire", "New Jersey", "New York",
             "North Carolina", "Rhode Island", "South Carolina", "Virginia"],
    # Canadian border, including the Great Lakes crossings.
    "north": ["Idaho", "Maine", "Michigan", "Minnesota", "Montana",
              "New Hampshire", "New York", "North Dakota", "Vermont", "Washington"],
    # Mexican border and the Gulf.
    "south": ["Alabama", "Arizona", "California", "Florida", "Louisiana",
              "Mississippi", "New Mexico", "Texas"],
}


def rings(geometry):
    if geometry["type"] == "Polygon":
        return geometry["coordinates"]
    if geometry["type"] == "MultiPolygon":
        return [ring for poly in geometry["coordinates"] for ring in poly]
    return []


def main() -> None:
    data = json.loads(STATES.read_text())

    points: dict[tuple, set[str]] = defaultdict(set)
    extent: dict[str, tuple[float, float, float, float]] = {}

    for feature in data["features"]:
        name = feature["properties"]["name"]
        xs, ys = [], []
        for ring in rings(feature["geometry"]):
            for lon, lat in ring:
                points[(round(lon, 2), round(lat, 2))].add(name)
                xs.append(lon)
                ys.append(lat)
        if xs:
            extent[name] = (min(xs), max(xs), min(ys), max(ys))

    # A point belonging to two states is a point on the border between them.
    neighbours: dict[str, set[str]] = defaultdict(set)
    for owners in points.values():
        if len(owners) < 2:
            continue
        for a in owners:
            for b in owners:
                if a != b:
                    neighbours[a].add(b)

    payload = {
        "neighbours": {k: sorted(v) for k, v in sorted(neighbours.items())},
        "edges": EDGES,
        "excluded": sorted(OFFSHORE),
    }
    OUTPUT.write_text(json.dumps(payload, indent=1, sort_keys=True))

    isolated = [n for n in extent if not neighbours.get(n)]
    print(f"{len(neighbours)} states with neighbours; isolated: {isolated}")
    for side, names in payload["edges"].items():
        print(f"  {side:6} {', '.join(names)}")
    print(f"written to {OUTPUT.relative_to(BASE)}")


if __name__ == "__main__":
    main()
