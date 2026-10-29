"""Mapped fence and wall lines rendered as reused Forest models on the road tile."""
import hashlib
import json
import math

import numpy as np

import mapcells
import mapgeom

GROUPS = ("russia_fence_wood", "russia_fence_metal", "russia_fence_chainlink", "russia_fence_wall", "russia_fence_gate")
KIND_GROUP = {"wood": 0, "metal": 1, "chainlink": 2, "wall": 3, "gate": 4}
MODULE_M = {"wood": 5.4, "metal": 4.0, "chainlink": 6.0, "wall": 4.0, "gate": 4.0}
SEARCH_PAD_M = 3.0
ROAD_CLEARANCE_M = 1.5
MAX_TILE_ITEMS = 1200


def _tags(feats, i):
    values = feats.attrs.get("tags")
    if values is None:
        return {}
    try:
        got = json.loads(str(values[i]))
    except (TypeError, ValueError):
        return {}
    if not isinstance(got, dict):
        return {}
    return {str(k).strip().lower(): str(v).strip().lower() for k, v in got.items()}


def fence_kind(feats, i):
    """Map Overture barrier classes and preserved OSM fence tags to a small shared asset catalog."""
    classes = feats.attrs.get("class")
    subtypes = feats.attrs.get("subtype")
    cls = str(classes[i]).strip().lower() if classes is not None else ""
    subtype = str(subtypes[i]).strip().lower() if subtypes is not None else ""
    tags = _tags(feats, i)
    barrier = tags.get("barrier", "")
    if subtype != "barrier" and cls not in {"fence", "wall", "gate"} \
            and barrier not in {"fence", "wall", "gate", "guard_rail"}:
        return None
    if cls == "gate" or barrier == "gate":
        return "gate"
    if cls == "wall" or barrier == "wall":
        material = tags.get("wall", "") + " " + tags.get("material", "")
        return "wall" if any(k in material for k in ("brick", "stone", "concrete", "masonry")) else "metal"
    fence_type = (tags.get("fence_type", "") + " " + tags.get("material", "")).replace("-", "_")
    if any(k in fence_type for k in ("chain", "wire", "mesh", "welded")):
        return "chainlink"
    if any(k in fence_type for k in ("wood", "timber", "picket", "board")):
        return "wood"
    if any(k in fence_type for k in ("brick", "stone", "concrete", "masonry")):
        return "wall"
    if cls in {"fence", "barrier"} or barrier == "fence":
        return "metal" if any(k in fence_type for k in ("metal", "steel", "corrugated", "iron", "sheet")) else "wood"
    return None


def _line_rows(fid, line, kind, box, frame, elev, roads=None):
    """Deterministic module rows from one mapped polyline, clipped to one tile and clear of road envelopes."""
    line = np.asarray(line, np.float64).reshape(-1, 2)
    if len(line) < 2:
        return []
    delta = np.diff(line, axis=0)
    lengths = np.hypot(delta[:, 0], delta[:, 1])
    keep = lengths > 1e-4
    if not keep.any():
        return []
    line = np.vstack((line[0], line[1:][keep]))
    arc = np.r_[0.0, np.cumsum(np.hypot(*np.diff(line, axis=0).T))]
    total = float(arc[-1])
    if total < 1.0:
        return []
    module_m = MODULE_M[kind]
    count = max(1, int(math.floor(total / module_m)))
    step = total / count
    x0, y0, x1, y1 = map(float, box)
    placements = []
    for k in range(count):
        s = (k + 0.5) * step
        j = min(int(np.searchsorted(arc, s, side="right") - 1), len(line) - 2)
        t = (s - arc[j]) / max(arc[j + 1] - arc[j], 1e-9)
        p = line[j] + t * (line[j + 1] - line[j])
        tangent = line[j + 1] - line[j]
        yaw = math.degrees(math.atan2(tangent[1], tangent[0])) % 360.0
        if not (x0 <= p[0] < x1 and y0 <= p[1] < y1):
            continue
        if roads is not None and len(roads[0]):
            from fast import require, _ef
            require(0, "points_near_segments")
            probes = np.array([p - tangent / max(np.linalg.norm(tangent), 1e-9) * step / 2, p,
                               p + tangent / max(np.linalg.norm(tangent), 1e-9) * step / 2])
            if np.asarray(_ef.points_near_segments(probes, np.ascontiguousarray(roads[0], np.float64),
                                                   np.ascontiguousarray(roads[1], np.float64),
                                                   np.asarray(roads[2], np.float64) + ROAD_CLEARANCE_M)).any():
                continue
        placements.append((k, p, yaw))
    if not placements:
        return []
    points = np.asarray([p for _, p, _ in placements], np.float64)
    la, lo, _ = frame.enu_to_geodetic(points[:, 0], points[:, 1], np.zeros(len(points)))
    heights = np.asarray(elev(la, lo), np.float64)
    rows = []
    for (k, p, yaw), z in zip(placements, heights):
        if not np.isfinite(z):
            continue
        rank = int.from_bytes(hashlib.blake2b(f"{fid}:{k}".encode("utf-8"), digest_size=4).digest(), "big") / 4294967296.0
        rows.append([GROUPS[KIND_GROUP[kind]], round(float(p[0]), 2), round(float(p[1]), 2), round(z, 2),
                     round(yaw, 1), 1.0, 1.3 if kind == "wood" else 1.8 if kind == "chainlink" else 2.0, rank])
    return rows


def tile_rows(frame, infra_fn, exact, elev, roads=None):
    """Mapped fence/wall modules for one road tile; coordinates are in the anchor frame."""
    x0, y0, x1, y1 = map(float, exact)
    corners = np.array([[x0, y0], [x0, y1], [x1, y0], [x1, y1]], np.float64)
    la, lo, _ = frame.enu_to_geodetic(corners[:, 0], corners[:, 1], np.zeros(len(corners)))
    try:
        cells = mapcells.cells_for_points(la, lo, pad_lat=0.00005, pad_lon=0.00005, max_cells=64)
    except (ValueError, OverflowError):
        return []
    rows, seen = [], set()
    for cell in cells:
        feats = infra_fn(cell)
        if feats is None or not len(feats):
            continue
        for i in range(len(feats)):
            fid = str(feats.ids[i])
            if fid in seen or int(feats.kind[i]) != mapgeom.LINE:
                continue
            kind = fence_kind(feats, i)
            if kind is None:
                continue
            seen.add(fid)
            for part_no, part in enumerate(feats.parts(i)):
                if not part or len(part[0]) < 2:
                    continue
                e, n = mapgeom.enu_xy(feats, frame, np.asarray(part[0], np.float64))
                line = np.column_stack((e, n))
                bounds = (line[:, 0].min(), line[:, 1].min(), line[:, 0].max(), line[:, 1].max())
                if bounds[2] < x0 - SEARCH_PAD_M or bounds[0] > x1 + SEARCH_PAD_M or bounds[3] < y0 - SEARCH_PAD_M or bounds[1] > y1 + SEARCH_PAD_M:
                    continue
                rows.extend(_line_rows(f"{fid}:{part_no}", line, kind, exact, frame, elev, roads))
    if len(rows) > MAX_TILE_ITEMS:
        rows = sorted(rows, key=lambda row: (row[-1], row[1], row[2]))[:MAX_TILE_ITEMS]
    return rows
