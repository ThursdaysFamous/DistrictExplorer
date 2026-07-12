#!/usr/bin/env python3
"""
Regenerate the app-data boundary files in data/app/ from the full-precision
GeoJSON in data/, applying the same topology-preserving simplification the
sibling boundary layers received.

Why this exists: the boundary layers with no CORS-enabled endpoint are shipped
as same-origin static files under data/app/, fetched lazily by index.html on
first toggle (they used to be embedded inline in index.html; the P0 change moved
them out). The full-precision conversions in data/ (e.g. school-board's 24,904
vertices at 14-15 decimals) need simplifying before they ship; this script makes
that simplification reproducible instead of a one-off manual step, so each
app-data copy can be regenerated whenever its source boundary changes and never
silently drifts from data/. All three Chicago anchors (school-board,
il-supreme-court, ccbr) are registered in LAYERS below.

Simplification uses mapshaper (the same tool the sibling layers used), which
builds a topology and simplifies shared arcs once, so adjacent districts keep
coincident boundaries — a per-ring simplifier would create gaps/overlaps and
put some points in zero or two districts. The result is validated against the
full-precision source before anything is written: point-in-district agreement
must hold on the project's 2,000-random-point protocol and no point may fall
in two districts. If validation fails, the data file is left untouched.

Prerequisites: Node.js (mapshaper is fetched via `npx mapshaper@<pinned>`).
This is an occasional operator step (boundaries change ~once a decade), not
part of the weekly roster CI.

Usage:
    python3 scripts/build_embedded_boundaries.py            # regenerate all
    python3 scripts/build_embedded_boundaries.py school-board
"""

import json
import os
import random
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DATA_DIR = os.path.join(REPO_ROOT, "data", "app")
MAPSHAPER = "mapshaper@0.6.102"  # pinned for reproducible output

# name -> how to regenerate its data/app/<out> file.
#   source:   full-precision GeoJSON under data/ (the source of truth)
#   out:      the app-data file index.html fetches for this layer
#   simplify: mapshaper Visvalingam retain percentage (topology-aware, keep-shapes)
#   precision: coordinate rounding on export (0.000001 = 6 decimals ~= 0.11 m)
#   key_prop:  the property findFeatureContaining/findPropCI keys on, used only
#              to validate point-in-district agreement below
LAYERS = {
    "school-board": {
        "source": "data/school-board-districts.geojson",
        "out": "school-board-districts.json",
        "simplify": "15%",
        "precision": "0.000001",
        "key_prop": "district",
    },
    # The two 2021-redistricting anchors. Both were originally converted by
    # one-off runs of this same protocol before it was generalized; registering
    # them here means a source change (or a reproducibility check) never has to
    # regress to a manual mapshaper run. Retain percentages are the ones the
    # shipped copies were built with (BUILD_PLAYBOOK_1: "12% / 15%", 6-decimal),
    # both of which agreed 100% with full precision on the 2,000-point protocol.
    # key_prop is the uppercase attribute-table field (ID/DISTRICT/DISTRICTN);
    # the app itself keys case-insensitively on districtn/district.
    "il-supreme-court": {
        "source": "data/il-supreme-court-districts.geojson",
        "out": "il-supreme-court-districts.json",
        "simplify": "12%",
        "precision": "0.000001",
        "key_prop": "DISTRICT",
    },
    "ccbr": {
        "source": "data/ccbr-districts.geojson",
        "out": "ccbr-districts.json",
        "simplify": "15%",
        "precision": "0.000001",
        "key_prop": "DISTRICT",
    },
}


def run_mapshaper(source_path, simplify, precision, out_path):
    subprocess.run(
        [
            "npx", "-y", MAPSHAPER, source_path,
            "-simplify", "visvalingam", "keep-shapes", simplify,
            "-o", "precision=" + precision, "format=geojson", out_path,
        ],
        check=True,
        cwd=REPO_ROOT,
    )


# --- point-in-polygon, mirroring index.html's even-odd implementation so the
#     validation agrees with what the app will actually compute at runtime ---
def _point_in_ring(pt, ring):
    x, y = pt
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_geometry(pt, geom):
    if geom["type"] == "Polygon":
        inside = False
        for ring in geom["coordinates"]:
            if _point_in_ring(pt, ring):
                inside = not inside
        return inside
    if geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            inside = False
            for ring in poly:
                if _point_in_ring(pt, ring):
                    inside = not inside
            if inside:
                return True
    return False


def _bbox(geom):
    b = [1e9, 1e9, -1e9, -1e9]

    def walk(c):
        if c and isinstance(c[0], (int, float)):
            b[0], b[1] = min(b[0], c[0]), min(b[1], c[1])
            b[2], b[3] = max(b[2], c[0]), max(b[3], c[1])
        else:
            for x in c:
                walk(x)

    walk(geom["coordinates"])
    return b


def _model(features, key_prop):
    return [(f["properties"][key_prop], f["geometry"], _bbox(f["geometry"])) for f in features]


def _districts_at(model, pt):
    hits = []
    for key, geom, bb in model:
        if bb[0] <= pt[0] <= bb[2] and bb[1] <= pt[1] <= bb[3] and _point_in_geometry(pt, geom):
            hits.append(key)
    return hits


def validate(source_features, simplified_features, key_prop, samples=2000, seed=2024):
    """Refuse the simplification unless it preserves the district coverage.

    Returns (ok, message). Agreement is measured the project's way: uniform
    random points across the layer bbox, classified against source vs
    simplified. Any point landing in two simplified districts is a topology
    break and fails outright.
    """
    src_props = sorted(tuple(sorted(f["properties"].items())) for f in source_features)
    new_props = sorted(tuple(sorted(f["properties"].items())) for f in simplified_features)
    if len(simplified_features) != len(source_features):
        return False, "feature count changed: %d -> %d" % (len(source_features), len(simplified_features))
    if src_props != new_props:
        return False, "feature properties changed during simplification"

    src = _model(source_features, key_prop)
    new = _model(simplified_features, key_prop)
    ob = [1e9, 1e9, -1e9, -1e9]
    for _, _, bb in src:
        ob[0], ob[1] = min(ob[0], bb[0]), min(ob[1], bb[1])
        ob[2], ob[3] = max(ob[2], bb[2]), max(ob[3], bb[3])

    rng = random.Random(seed)
    agree = overlaps = 0
    for _ in range(samples):
        pt = (rng.uniform(ob[0], ob[2]), rng.uniform(ob[1], ob[3]))
        s_hits = _districts_at(new, pt)
        if len(s_hits) > 1:
            overlaps += 1
        o_hits = _districts_at(src, pt)
        o = o_hits[0] if len(o_hits) == 1 else (None if not o_hits else "MULTI")
        s = s_hits[0] if len(s_hits) == 1 else (None if not s_hits else "MULTI")
        if o == s:
            agree += 1
    pct = 100.0 * agree / samples
    if overlaps > 0:
        return False, "topology broken: %d/%d points fell in >1 district" % (overlaps, samples)
    if pct < 99.5:
        return False, "point-in-district agreement only %.2f%% (need >= 99.5%%)" % pct
    return True, "%d/%d (%.2f%%) agreement, 0 overlaps" % (agree, samples, pct)


def build_layer(name, cfg):
    source_path = os.path.join(REPO_ROOT, cfg["source"])
    with open(source_path) as f:
        source = json.load(f)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = os.path.join(tmp, name + ".geojson")
        run_mapshaper(source_path, cfg["simplify"], cfg["precision"], tmp_path)
        with open(tmp_path) as f:
            simplified = json.load(f)

    ok, msg = validate(source["features"], simplified["features"], cfg["key_prop"])
    if not ok:
        raise RuntimeError("%s validation failed: %s" % (name, msg))

    compact = json.dumps(simplified, separators=(",", ":"))
    out_path = os.path.join(APP_DATA_DIR, cfg["out"])

    # Round-trip: re-read what we're about to write and confirm it parses back
    # to the same object the app will fetch, so a serialization bug can't ship
    # silently. (Only after this passes is the real file overwritten.)
    if json.loads(compact) != simplified:
        raise RuntimeError("%s round-trip mismatch before writing" % name)

    os.makedirs(APP_DATA_DIR, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(compact)

    print(
        "%s -> data/app/%s: %s; %d bytes (%s)"
        % (name, cfg["out"], msg, len(compact), cfg["simplify"] + " retain, " + cfg["precision"] + " precision"),
        file=sys.stderr,
    )


def main():
    targets = sys.argv[1:] or list(LAYERS)
    unknown = [t for t in targets if t not in LAYERS]
    if unknown:
        print("unknown layer(s): %s; known: %s" % (unknown, list(LAYERS)), file=sys.stderr)
        sys.exit(1)

    for name in targets:
        build_layer(name, LAYERS[name])


if __name__ == "__main__":
    main()
