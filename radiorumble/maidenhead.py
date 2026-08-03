"""Maidenhead grid squares to latitude and longitude.

FT8 exchanges a grid square and nothing else — no state, no country, no
coordinates — so the square is the only position information a contact
carries. Everything on the map and the globe is derived from here.

The locator divides the world into 18x18 fields (AA-RR), each split into
10x10 squares (00-99), each split into 24x24 subsquares (aa-xx). A 4-character
locator is 2 degrees of longitude by 1 of latitude, which is about 100 by 70
miles at mid-latitudes — coarse, but the right size for a map of a country.
"""
from __future__ import annotations

import re

_LOCATOR = re.compile(r"^[A-R]{2}[0-9]{2}([A-X]{2})?", re.IGNORECASE)


def is_valid(locator: str) -> bool:
    return bool(locator) and bool(_LOCATOR.match(locator.strip()))


def to_latlon(locator: str) -> tuple[float, float] | None:
    """Centre of the square, as (latitude, longitude). None if unparseable.

    The centre rather than the corner: a marker drawn at the south-west corner
    of a 2x1 degree box sits visibly outside the area it represents.
    """
    if not locator:
        return None
    loc = locator.strip().upper()
    match = _LOCATOR.match(loc)
    if not match:
        return None
    loc = match.group(0)

    lon = (ord(loc[0]) - ord("A")) * 20.0 - 180.0
    lat = (ord(loc[1]) - ord("A")) * 10.0 - 90.0
    lon += int(loc[2]) * 2.0
    lat += int(loc[3]) * 1.0

    if len(loc) >= 6:
        lon += (ord(loc[4]) - ord("A")) * (2.0 / 24.0)
        lat += (ord(loc[5]) - ord("A")) * (1.0 / 24.0)
        # Centre of the subsquare.
        lon += 1.0 / 24.0
        lat += 0.5 / 24.0
    else:
        # Centre of the 2x1 degree square.
        lon += 1.0
        lat += 0.5

    return (round(lat, 4), round(lon, 4))


def neighbours(square: str) -> list[str]:
    """The eight squares touching this one.

    Squares tile the world 2 degrees by 1, so a neighbour is one step in
    either direction. Longitude wraps at the date line; latitude does not,
    because there is nothing north of the pole.
    """
    position = to_latlon(square)
    if position is None:
        return []
    lat, lon = position
    out = []
    for dlat in (-1, 0, 1):
        for dlon in (-2, 0, 2):
            if dlat == 0 and dlon == 0:
                continue
            nlat = lat + dlat
            nlon = lon + dlon
            if not -90 <= nlat < 90:
                continue
            if nlon >= 180:
                nlon -= 360
            elif nlon < -180:
                nlon += 360
            out.append(to_square(nlat, nlon))
    return sorted(set(out))


def to_square(lat: float, lon: float) -> str:
    """The 4-character square containing a position. Inverse of to_latlon."""
    lon = min(179.999, max(-180.0, lon)) + 180.0
    lat = min(89.999, max(-90.0, lat)) + 90.0
    return (
        chr(int(lon // 20) + ord("A"))
        + chr(int(lat // 10) + ord("A"))
        + str(int((lon % 20) // 2))
        + str(int(lat % 10))
    )
