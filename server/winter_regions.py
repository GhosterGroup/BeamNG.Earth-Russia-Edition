"""A small Natural Earth Russia boundary for winter-map coverage checks."""
import gzip
import json
import math
import os
import sys
from functools import lru_cache


def _data_path():
    root = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "data", "winter", "russia_admin0_50m.geojson.gz")


def _unwrap(ring):
    """Unwrap a polygon ring around the antimeridian so a point test stays local."""
    if not ring:
        return ()
    result = [(float(ring[0][0]), float(ring[0][1]))]
    last = result[0][0]
    for lon, lat in ring[1:]:
        lon = float(lon)
        while lon - last > 180:
            lon -= 360
        while lon - last < -180:
            lon += 360
        result.append((lon, float(lat)))
        last = lon
    return tuple(result)


@lru_cache(maxsize=1)
def _polygons():
    with gzip.open(_data_path(), "rt", encoding="utf-8") as f:
        geometry = json.load(f)
    polygons = []
    for polygon in geometry["coordinates"]:
        rings = tuple(_unwrap(r) for r in polygon)
        outer = rings[0] if rings else ()
        if len(outer) < 4:
            continue
        xs, ys = zip(*outer)
        polygons.append(((min(xs), min(ys), max(xs), max(ys)), rings))
    return tuple(polygons)


def _inside_ring(x, y, ring):
    inside = False
    x1, y1 = ring[-1]
    for x2, y2 in ring:
        if (y2 > y) != (y1 > y):
            cross = (x1 - x2) * (y - y2) / (y1 - y2) + x2
            if x < cross:
                inside = not inside
        x1, y1 = x2, y2
    return inside


def in_russia(lon, lat):
    """True when (lon, lat) falls within the bundled 1:50m admin-0 Russia polygon."""
    lon, lat = float(lon), float(lat)
    for (xmin, ymin, xmax, ymax), rings in _polygons():
        if not ymin <= lat <= ymax:
            continue
        centre = (xmin + xmax) * 0.5
        x = lon + round((centre - lon) / 360.0) * 360.0
        if not xmin <= x <= xmax or not _inside_ring(x, lat, rings[0]):
            continue
        if not any(_inside_ring(x, lat, hole) for hole in rings[1:]):
            return True
    return False


def is_siberia(lon, lat):
    """Siberian winter coverage, clipped to mapped Russia to exclude neighbouring countries.

    The first coverage envelope starts east of the Urals (60 E), covers the four initial test
    locations, and stops at 78 N. Admin-0 geometry is checked before the envelope.
    """
    lon, lat = float(lon), float(lat)
    return 60.0 <= lon <= 180.0 and 45.0 <= lat <= 78.0 and in_russia(lon, lat)


def tile_is_siberia(z, x, y):
    """Whether an XYZ Web Mercator tile's centre is inside the initial Siberia region."""
    z, x, y = int(z), int(x), int(y)
    if z < 0 or z > 30:
        return False
    n = 1 << z
    if not (0 <= x < n and 0 <= y < n):
        return False
    lon = (x + 0.5) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * (y + 0.5) / n))))
    return is_siberia(lon, lat)
