#!/usr/bin/env python3
"""
Regenerate the embedded boundary blobs in index.html from the full-precision
GeoJSON in data/, applying the same topology-preserving simplification the
other embedded layers already received.

Why this exists: three layers ship their geometry inline in index.html as
`var NAME = JSON.parse('...')` because they have no CORS-enabled endpoint and
the app is served as a static page. Two of them (IL Supreme Court, Board of
Review) were mapshaper-simplified and rounded to a handful of decimals before
embedding; the school-board layer was embedded straight from the full-precision
conversion (24,904 vertices at 14-15 decimals), which alone was ~75% of the
whole page. This script makes that simplification reproducible instead of a
one-off manual step, so the embedded copy can be regenerated whenever the
source boundary changes and never silently drifts from data/.

Simplification uses mapshaper (the same tool the sibling layers used), which
builds a topology and simplifies shared arcs once, so adjacent districts keep
coincident boundaries — a per-ring simplifier would create gaps/overlaps and
put some points in zero or two districts. The result is validated against the
full-precision source before anything is written: point-in-district agreement
must hold on the project's 2,000-random-point protocol and no point may fall
in two districts. If validation fails, index.html is left untouched.

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
import re
import subprocess
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
MAPSHAPER = "mapshaper@0.6.102"  # pinned for reproducible output

# var_name -> how to regenerate it.
#   source:   full-precision GeoJSON under data/ (the source of truth)
#   simplify: mapshaper Visvalingam retain percentage (topology-aware, keep-shapes)
#   precision: coordinate rounding on export (0.000001 = 6 decimals ~= 0.11 m)
#   key_prop:  the property findFeatureContaining/findPropCI keys on, used only
#              to validate point-in-district agreement below
LAYERS = {
    "school-board": {
        "var": "SCHOOL_BOARD_DISTRICTS_GEOJSON",
        "source": "data/school-board-districts.geojson",
        "simplify": "15%",
        "precision": "0.000001",
        "key_prop": "district",
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


def js_single_quoted(json_text):
    """Escape a JSON string so it survives inside index.html's
    `JSON.parse('...')` single-quoted literal (matches build_il_roster.py)."""
    out = json_text.replace("\\", "\\\\").replace("'", "\\'")
    out = out.replace("</", "<\\/")  # invisible to the HTML parser, identical to the JS engine
    out = out.replace(chr(0x2028), "\\u2028").replace(chr(0x2029), "\\u2029")
    return out


def splice(html, var_name, json_text):
    new_line = "  var %s = JSON.parse('%s');" % (var_name, js_single_quoted(json_text))
    pattern = re.compile(r"^  var " + re.escape(var_name) + r" = JSON\.parse\('.*'\);$", re.MULTILINE)
    matches = pattern.findall(html)
    if len(matches) != 1:
        raise RuntimeError(
            "expected exactly one %s line to replace, found %d" % (var_name, len(matches))
        )
    # callable replacement: the return value is used literally, no backslash processing
    return pattern.sub(lambda _m: new_line, html, count=1)


def build_layer(name, cfg, html):
    source_path = os.path.join(REPO_ROOT, cfg["source"])
    with open(source_path) as f:
        source = json.load(f)

    with tempfile.TemporaryDirectory() as tmp:
        out_path = os.path.join(tmp, name + ".geojson")
        run_mapshaper(source_path, cfg["simplify"], cfg["precision"], out_path)
        with open(out_path) as f:
            simplified = json.load(f)

    ok, msg = validate(source["features"], simplified["features"], cfg["key_prop"])
    if not ok:
        raise RuntimeError("%s validation failed: %s" % (name, msg))

    compact = json.dumps(simplified, separators=(",", ":"))
    html = splice(html, cfg["var"], compact)

    # Round-trip: re-extract the spliced literal and confirm it re-parses to the
    # same object the app will see, so an escaping bug can't ship silently.
    extracted = re.search(
        r"  var " + re.escape(cfg["var"]) + r" = JSON\.parse\('(.*)'\);", html
    ).group(1)
    unescaped = (
        extracted.replace("\\/", "/").replace("\\'", "'").replace("\\\\", "\\")
    )
    if json.loads(unescaped) != simplified:
        raise RuntimeError("%s round-trip mismatch after splicing" % name)

    print(
        "%s: %s; embedded %d bytes (%s)"
        % (name, msg, len(compact), cfg["simplify"] + " retain, " + cfg["precision"] + " precision"),
        file=sys.stderr,
    )
    return html


def main():
    targets = sys.argv[1:] or list(LAYERS)
    unknown = [t for t in targets if t not in LAYERS]
    if unknown:
        print("unknown layer(s): %s; known: %s" % (unknown, list(LAYERS)), file=sys.stderr)
        sys.exit(1)

    with open(INDEX_HTML) as f:
        html = f.read()
    before = len(html)

    for name in targets:
        html = build_layer(name, LAYERS[name], html)

    with open(INDEX_HTML, "w") as f:
        f.write(html)
    print("index.html: %d -> %d bytes" % (before, len(html)), file=sys.stderr)


if __name__ == "__main__":
    main()
