#!/usr/bin/env python3
"""
Generate the per-fork GENERATED regions from metro-worksheet.json
(docs/MECHANIZATION_PLAYBOOK.md, Conversion 2).

Every fact a human used to hand-copy between per-fork files lives ONCE in
metro-worksheet.json (validated against schema/metro-worksheet.schema.json
before any file is touched). This script renders those facts into fenced
regions, marked like the engine's fences but generator-owned:

    /* ==== GENERATED:BEGIN <name> ==== */     (JS / CSS)
    <!-- ==== GENERATED:BEGIN <name> ==== -->  (HTML / Markdown)
    # ==== GENERATED:BEGIN <name> ====         (Python / YAML)
    // ==== GENERATED:BEGIN <name> ====        (JS line style)

Targets (region name -> file):
    metro-config      -> index.html   (interior of the METRO config fence)
    layer-area-rank   -> index.html   (the LAYER_AREA_RANK array)
    sw-metro-config   -> sw.js        (CACHE_NAME + shell/geometry/roster lists)
    validator-config  -> scripts/validate_index.py (floors + expected ids)
    smoke-config      -> scripts/smoke_test.mjs    (anchor/negative points, counts)
    metro-facts       -> CLAUDE.md    (city / geocoder / ground-truth / workflows)
    metro-header      -> README.md    (title + tagline)

Modes:
    python3 scripts/generate_metro_files.py           # splice regions in place
    python3 scripts/generate_metro_files.py --check   # regenerate + diff; exit 1
                                                      # on any drift (the CI gate)
    python3 scripts/generate_metro_files.py --sync-fleet [SRC]
        # Conversion 3: refresh the worksheet's metro_explorers from the fleet
        # manifest (SRC = a metros.json path or URL; default: the repo-root
        # metros.json if present, else https://chidistricts.com/metros.json),
        # then regenerate. Only the metro_explorers value is rewritten — the
        # rest of the worksheet is untouched. Plain runs and --check never
        # touch the network, so the CI gate stays hermetic; launching a new
        # metro is a --sync-fleet regeneration PR in each fork.

Hand-editing a GENERATED region is a CI failure, not a review nit: edit the
worksheet and regenerate. Hand-written content outside the fences is never
touched. Dependencies: stdlib + jsonschema (pinned in scripts/requirements.txt).
"""

import argparse
import difflib
import json
import os
import re
import sys

try:
    import jsonschema
except ImportError:
    print("generate-metro-files: FAIL — jsonschema is not installed "
          "(pip install -c scripts/requirements.txt jsonschema)", file=sys.stderr)
    sys.exit(1)

GENERATED_RE = re.compile(
    r"^[ \t]*(?:/\*|<!--|#|//)?[ \t]*==== GENERATED:(BEGIN|END) ([a-z0-9][a-z0-9-]*) ====[ \t]*(?:\*/|-->)?[ \t]*$"
)


def fail(msg):
    print("generate-metro-files: FAIL — " + msg, file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------- rendering

def js_num(n):
    """JSON number -> JS literal, preserving the int/float distinction the
    worksheet encodes (41 stays 41; 41.0 stays 41.0)."""
    return repr(n) if isinstance(n, float) else str(n)


def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def bbox_js(b, order):
    return "{ " + ", ".join("%s: %s" % (k, js_num(b[k])) for k in order) + " }"


def keyed_lines(groups, indent):
    """Grouped key lists -> one line per group, comma-joined."""
    lines = []
    for gi, group in enumerate(groups):
        line = indent + ", ".join(js_str(k) for k in group)
        if gi != len(groups) - 1:
            line += ","
        lines.append(line)
    return lines


def render_metro_config(w):
    L = []
    a = L.append

    def stmt(code, comment=None, pad=37):
        a("  " + (code.ljust(pad) + " // " + comment if comment else code))

    a("  /* Everything metro-specific that the shared ENGINE blocks below reference")
    a("   * lives here, so an ENGINE block never needs a per-city edit. Fenced ENGINE")
    a("   * blocks are byte-identical across every metro fork — see")
    a("   * docs/ENGINE_SYNC.md and scripts/check_engine_parity.py. */")
    stmt("var THIS_METRO = %s;" % js_str(w["this_metro"]), "key into METRO_EXPLORERS below")
    stmt("var METRO_NAME = %s;" % js_str(w["metro_name"]), "used in user-facing strings")
    a("  var METRO_BBOX = %s;" % bbox_js(w["metro_bbox"], ["minLng", "minLat", "maxLng", "maxLat"]))
    a("  var METRO_CENTER = [%s, %s];" % tuple(js_num(v) for v in w["metro_center"]))
    a("  // Permalink sanity gate: the *greater* metro area (wider than METRO_BBOX).")
    a("  var PERMALINK_GATE = %s;" % bbox_js(w["permalink_gate"], ["minLat", "maxLat", "minLng", "maxLng"]))
    a("  var SOCRATA_HOST = %s;" % js_str(w["socrata_host"]))
    a("  // Socrata app token: some metros' portals throttle anonymous requests. It is")
    a("  // a throttling identifier, not a secret — public exposure is Socrata's")
    a("  // intended use (do NOT put an API Key *secret* here). Blank = sent as-is.")
    a("  var SOCRATA_APP_TOKEN = %s;" % js_str(w["socrata_app_token"]))
    a("  var REPO_ISSUES = %s;" % js_str(w["repo_issues"]))
    a("  var FEEDBACK_SUBJECT = %s;" % js_str(w["feedback_subject"]))
    a("  /* Sibling District Explorer deployments — one canonical list shared by every")
    a("   * metro fork. When a new metro launches, add its entry to every fork's")
    a("   * worksheet and regenerate (Conversion 3 will source this list from the")
    a("   * fleet manifest instead). THIS_METRO drops the fork's own entry so the")
    a("   * list is identical in every fork. `bbox` (greater metro area, mirroring")
    a("   * that fork's PERMALINK_GATE) and `emoji` feed the sibling-metro portal")
    a("   * easter egg (ENGINE metro-portal): wander the map into a sibling's bbox —")
    a("   * or search/geolocate a point inside one — and the app offers to hand you")
    a("   * off to that fork's explorer. */")
    a("  var METRO_EXPLORERS = [")
    for i, e in enumerate(w["metro_explorers"]):
        tail = "," if i != len(w["metro_explorers"]) - 1 else ""
        head = "    { id: %s, label: %s, url: %s, emoji: %s," % (
            js_str(e["id"]), js_str(e["label"]), js_str(e["url"]), js_str(e["emoji"]))
        if "bbox" in e:
            a(head)
            a("      bbox: %s }%s" % (bbox_js(e["bbox"], ["minLng", "minLat", "maxLng", "maxLat"]), tail))
        else:
            a(head.rstrip(",") + " }%s" % tail)
    a("  ];")
    a("  /* CSS class names for the fork-branded map chrome: ENGINE code applies them,")
    a("   * this fork's stylesheet defines them (they carry the fork's palette). */")
    stmt("var HIGHLIGHT_CLASS = %s;" % js_str(w["highlight_class"]),
         "selected-region highlight (drop-shadow filter)", pad=44)
    stmt("var POI_PIN_CLASS = %s;" % js_str(w["poi_pin_class"]),
         "geocoded point-of-interest marker", pad=44)
    a("  // FALLBACK district-number key list, fed through extractDistrictNumber")
    a("  // (which adds a name-field regex fallback for the layers whose number only")
    a("  // lives inside a \"…name\" string). The factories declare per-layer hoverName")
    a("  // sourced from the same properties each click card reads (the hover-parity")
    a("  // rule), so this generic path only runs if hoverName comes back empty. These")
    a("  // keys are this metro's dataset vocabulary — re-seed them from observed")
    a("  // field names in the worksheet, keeping encoded fields out.")
    a("  var HOVER_NUMBER_KEYS = [")
    L.extend(keyed_lines(w["hover_number_keys"], "    "))
    a("  ];")
    a("")
    a("  // Name-ish property keys that read better than a bare district number when a")
    a("  // feature carries one — deliberately narrow. Generic \"name\"/\"label\" fields")
    a("  // are excluded on purpose: for legislative layers those just restate the")
    a("  // number this pairs with.")
    a("  var HOVER_NAME_KEYS = [")
    L.extend(keyed_lines(w["hover_name_keys"], "    "))
    a("  ];")
    return "\n".join(L)


def render_layer_area_rank(w):
    layers = sorted(w["layers"], key=lambda l: l["area_rank"])
    L = []
    a = L.append
    a("  // Approximate real-world area ranking, largest to smallest, used to keep")
    a("  // smaller/more granular boundaries visible on top of larger ones (see")
    a("  // reorderActiveLayers()). Hand-authored from known geography — there's no")
    a("  // geometry library in this codebase to compute polygon area from data.")
    a("  // GENERATED from the worksheet's layers[] (area_rank order + rank notes).")
    a("  var LAYER_AREA_RANK = [")
    for i, l in enumerate(layers):
        for c in l.get("rank_comment", []):
            a("    // " + c)
        entry = js_str(l["id"]) + ("," if i != len(layers) - 1 else "")
        note = l.get("rank_note")
        a(("    " + entry.ljust(20) + (" // " + note if note else "")).rstrip())
    a("  ];")
    return "\n".join(L)


def render_sw_metro_config(w):
    L = []
    a = L.append
    a("const CACHE_NAME = %s;" % js_str(w["sw"]["cache_name"]))
    a("")
    a("const SHELL_URLS = [")
    for u in w["sw"]["shell_urls"]:
        a("  %s," % js_str(u))
    a("];")
    a("")
    a("// Boundary geometry (data/app/*.json, fetched lazily on first toggle).")
    a("// Boundaries change ~once a decade, so serve them cache-first (instant, and")
    a("// works offline) and refresh in the background. Precached at install so")
    a("// those layers work offline.")
    a("const GEOMETRY_URLS = [")
    for g in w["data_files"]["geometry"]:
        a("  %s," % js_str("./data/app/" + g["file"]))
    a("];")
    a("")
    a("// Roster/officeholder data (also in data/app/) is refreshed by the weekly CI")
    a("// and must never be served stale — network-first, with the cached copy only")
    a("// as an offline fallback. Same freshness rule as the shell.")
    a("const ROSTER_URLS = [")
    for r in w["data_files"]["rosters"]:
        a("  %s," % js_str("./data/app/" + r["file"]))
    a("];")
    return "\n".join(L)


def render_validator_config(w):
    L = []
    a = L.append
    a("# Floor, not a moving target: new layers only raise this; a drop means")
    a("# modules were lost.")
    a("MIN_REGISTER_LAYER = %d" % w["min_register_layer"])
    a("")
    a("# Every layer id that must be registered in index.html. Most modules register")
    a("# through the factories, so deleting one would NOT lower the raw registerLayer(")
    a("# count above — this per-id list is the direct module-loss guard. Emitted in")
    a("# LAYER_AREA_RANK order; check 5 keeps the two naming the same set.")
    a("EXPECT_LAYER_IDS = [")
    line = "   "
    for l in sorted(w["layers"], key=lambda x: x["area_rank"]):
        piece = " %s," % js_str(l["id"])
        if len(line) + len(piece) > 78:
            a(line)
            line = "   "
        line += piece
    a(line)
    a("]")
    a("")
    a("# file -> (min features, max features) for the boundary layers fetched by the app.")
    a("GEOMETRY_FILES = {")
    for g in w["data_files"]["geometry"]:
        a("    %s: (%d, %d),%s" % (js_str(g["file"]), g["min_features"], g["max_features"],
                                   ("  # " + g["note"]) if g.get("note") else ""))
    a("}")
    a("")
    a("# file -> minimum key count (officeholder rosters).")
    a("ROSTER_FILES = {")
    for r in w["data_files"]["rosters"]:
        a("    %s: %d,%s" % (js_str(r["file"]), r["min_keys"],
                             ("  # " + r["note"]) if r.get("note") else ""))
    a("}")
    return "\n".join(L)


def render_smoke_config(w):
    pt = w["anchor_point"]
    neg = w["negative_point"]
    L = []
    a = L.append
    a("const POINT = \"%.5f,%.5f\";%s" % (pt["lat"], pt["lng"],
                                          (" // " + pt["note"]) if pt.get("note") else ""))
    a("const OFFLINE = [%s];" % ", ".join(js_str(x["layer"]) for x in w["anchors"]))
    a("const EXPECT_DISTRICT = { %s };" % ", ".join(
        "%s: %s" % (js_str(x["layer"]), js_str(x["expected"])) for x in w["anchors"]))
    a("const NEGATIVE_POINT = \"%.5f,%.5f\";%s" % (neg["lat"], neg["lng"],
                                                   (" // " + neg["note"]) if neg.get("note") else ""))
    a("const EXPECT_LAYERS = %d;%s" % (len(w["layers"]),
                                       (" // " + w["layer_count_note"]) if w.get("layer_count_note") else ""))
    return "\n".join(L)


def render_metro_facts(w):
    groups = {}
    for l in w["layers"]:
        groups[l["group"]] = groups.get(l["group"], 0) + 1
    anchor = w["anchor_point"]
    neg = w["negative_point"]
    L = []
    a = L.append
    a("**Metro facts** (generated from `metro-worksheet.json` — edit the worksheet and run")
    a("`python3 scripts/generate_metro_files.py`; hand-edits here fail CI):")
    a("")
    a("- Metro: %s (`%s`) — %s" % (w["metro_name"], w["this_metro"], w["domains"]["canonical"]))
    a("- Geocoders: address %s; unbounded %s; POI %s" % (
        w["geocoder"]["address"], w["geocoder"]["unbounded"], w["geocoder"]["poi"]))
    a("- Ground truth: %.5f,%.5f (%s) → %s. Negative point %.5f,%.5f (%s)." % (
        anchor["lat"], anchor["lng"], anchor.get("note", ""),
        "; ".join("%s %s" % (x["layer"], x["expected"]) for x in w["anchors"]),
        neg["lat"], neg["lng"], neg.get("note", "")))
    a("- Layers: %d registered (%s); `registerLayer(` floor %d. Debug namespace `window.%s`." % (
        len(w["layers"]),
        ", ".join("%s %d" % (g, groups[g]) for g in ["political", "safety", "schools", "geography"] if g in groups),
        w["min_register_layer"], w["exports_name"]))
    a("- Scheduled workflows: %s." % "; ".join(
        "`%s` (%s)" % (wf["file"], wf["schedule"]) for wf in w["workflows"]))
    a("- Source registry: %s" % (
        "`%s` (machine-checked monthly)" % w["data_sources"]["registry"]
        if isinstance(w["data_sources"], dict) else "%d rows in the worksheet" % len(w["data_sources"])))
    return "\n".join(L)


def render_metro_header(w):
    return "\n".join([
        "# %s District Explorer" % w["metro_name"],
        "",
        "**Click any point in %s — or search an address — and see every civic district that contains it, and who represents you there.**" % w["metro_name"],
    ])


TARGETS = [
    ("index.html", "metro-config", render_metro_config),
    ("index.html", "layer-area-rank", render_layer_area_rank),
    ("sw.js", "sw-metro-config", render_sw_metro_config),
    ("scripts/validate_index.py", "validator-config", render_validator_config),
    ("scripts/smoke_test.mjs", "smoke-config", render_smoke_config),
    ("CLAUDE.md", "metro-facts", render_metro_facts),
    ("README.md", "metro-header", render_metro_header),
]


# ---------------------------------------------------------------- splicing

FLEET_URL = "https://chidistricts.com/metros.json"


def render_explorers_json(entries):
    """Render a metro_explorers array in the worksheet's two-lines-per-entry
    house style, so a fleet sync rewrites only those lines."""
    L = ["["]
    for i, e in enumerate(entries):
        tail = "," if i != len(entries) - 1 else ""
        L.append('    { "id": %s, "label": %s, "url": %s, "emoji": %s,' % (
            json.dumps(e["id"]), json.dumps(e["label"], ensure_ascii=False),
            json.dumps(e["url"]), json.dumps(e["emoji"], ensure_ascii=False)))
        b = e["bbox"]
        L.append('      "bbox": { "minLng": %s, "minLat": %s, "maxLng": %s, "maxLat": %s } }%s' % (
            json.dumps(b["minLng"]), json.dumps(b["minLat"]),
            json.dumps(b["maxLng"]), json.dumps(b["maxLat"]), tail))
    L.append("  ]")
    return "\n".join(L)


def sync_fleet(ws_path, src):
    """Rewrite ONLY the worksheet's "metro_explorers" value from the fleet
    manifest (metros.json), projecting away fleet-only fields like `repo`.
    Returns True if the worksheet changed."""
    if src.startswith("http://") or src.startswith("https://"):
        import urllib.request
        req = urllib.request.Request(src, headers={"User-Agent": "district-explorer-fleet-sync"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            manifest = json.loads(resp.read().decode("utf-8"))
    else:
        with open(src, encoding="utf-8") as f:
            manifest = json.load(f)
    entries = [
        {"id": m["id"], "label": m["label"], "url": m["url"], "emoji": m["emoji"], "bbox": m["bbox"]}
        for m in manifest["metros"]
    ]
    text = open(ws_path, encoding="utf-8", newline="").read()
    key = '"metro_explorers": ['
    i = text.index(key)
    depth = 0
    j = i + len(key) - 1
    for j in range(i + len(key) - 1, len(text)):
        if text[j] == "[":
            depth += 1
        elif text[j] == "]":
            depth -= 1
            if depth == 0:
                break
    else:
        fail("could not find the end of metro_explorers in %s" % ws_path)
    new_text = text[:i] + '"metro_explorers": ' + render_explorers_json(entries) + text[j + 1:]
    if new_text != text:
        open(ws_path, "w", encoding="utf-8", newline="").write(new_text)
        print("generate-metro-files: %s — metro_explorers synced from %s" % (ws_path, src))
        return True
    print("generate-metro-files: %s — metro_explorers already match %s" % (ws_path, src))
    return False


def split_regions(text, path):
    """Return (lines, {name: (begin_idx, end_idx)}) — marker line indices."""
    lines = text.split("\n")
    regions = {}
    open_name = None
    open_at = None
    for i, line in enumerate(lines):
        m = GENERATED_RE.match(line)
        if not m:
            continue
        kind, name = m.groups()
        if kind == "BEGIN":
            if open_name is not None:
                fail("%s:%d: GENERATED:BEGIN %s while %s is still open" % (path, i + 1, name, open_name))
            if name in regions:
                fail("%s:%d: duplicate GENERATED region %r" % (path, i + 1, name))
            open_name, open_at = name, i
        else:
            if name != open_name:
                fail("%s:%d: GENERATED:END %s does not match open region %r" % (path, i + 1, name, open_name))
            regions[name] = (open_at, i)
            open_name = None
    if open_name is not None:
        fail("%s: GENERATED region %s is never closed" % (path, open_name))
    return lines, regions


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repo root (default: .)")
    ap.add_argument("--worksheet", default="metro-worksheet.json")
    ap.add_argument("--schema", default="schema/metro-worksheet.schema.json")
    ap.add_argument("--check", action="store_true",
                    help="verify committed regions match the worksheet; exit 1 on drift")
    ap.add_argument("--sync-fleet", nargs="?", const="", metavar="SRC",
                    help="refresh metro_explorers from the fleet manifest before generating "
                         "(SRC path/URL; default: repo-root metros.json, else %s)" % FLEET_URL)
    args = ap.parse_args()

    ws_path = os.path.join(args.root, args.worksheet)
    if args.sync_fleet is not None:
        if args.check:
            fail("--sync-fleet and --check are mutually exclusive (the CI gate stays hermetic)")
        src = args.sync_fleet
        if not src:
            local = os.path.join(args.root, "metros.json")
            src = local if os.path.exists(local) else FLEET_URL
        try:
            sync_fleet(ws_path, src)
        except (OSError, ValueError, KeyError) as e:
            fail("fleet sync from %s failed: %s" % (src, e))
    schema_path = os.path.join(args.root, args.schema)
    try:
        with open(ws_path, encoding="utf-8") as f:
            worksheet = json.load(f)
    except (OSError, ValueError) as e:
        fail("cannot read worksheet %s: %s" % (ws_path, e))
    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)
    except (OSError, ValueError) as e:
        fail("cannot read schema %s: %s" % (schema_path, e))
    try:
        jsonschema.validate(worksheet, schema)
    except jsonschema.ValidationError as e:
        fail("worksheet does not validate against the schema: %s (at %s)"
             % (e.message, "/".join(str(p) for p in e.absolute_path) or "<root>"))

    ranks = sorted(l["area_rank"] for l in worksheet["layers"])
    if ranks != list(range(1, len(ranks) + 1)):
        fail("layers[].area_rank must be exactly 1..%d with no gaps or duplicates" % len(ranks))
    anchor_ids = {a["layer"] for a in worksheet["anchors"]}
    layer_ids = {l["id"] for l in worksheet["layers"]}
    if not anchor_ids <= layer_ids:
        fail("anchors reference unknown layer id(s): %s" % ", ".join(sorted(anchor_ids - layer_ids)))

    drift = []
    for rel_path, name, render in TARGETS:
        path = os.path.join(args.root, rel_path)
        try:
            with open(path, encoding="utf-8", newline="") as f:
                text = f.read()
        except OSError as e:
            fail("cannot read target %s: %s" % (path, e))
        lines, regions = split_regions(text, rel_path)
        if name not in regions:
            fail("%s has no GENERATED region %r — fences missing?" % (rel_path, name))
        begin, end = regions[name]
        current = "\n".join(lines[begin + 1:end])
        rendered = render(worksheet)
        if args.check:
            if current != rendered:
                drift.append((rel_path, name, current, rendered))
        elif current != rendered:
            new_lines = lines[:begin + 1] + rendered.split("\n") + lines[end:]
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(new_lines))
            print("generate-metro-files: %s — region %r regenerated" % (rel_path, name))
        else:
            print("generate-metro-files: %s — region %r already current" % (rel_path, name))

    if args.check:
        if drift:
            for rel_path, name, current, rendered in drift:
                print("generate-metro-files: DRIFT in %s region %r:" % (rel_path, name), file=sys.stderr)
                for dl in difflib.unified_diff(current.splitlines(), rendered.splitlines(),
                                               fromfile="committed", tofile="regenerated", lineterm="", n=1):
                    print("  " + dl, file=sys.stderr)
            print("generate-metro-files: FAIL — %d region(s) drifted from the worksheet. "
                  "Edit metro-worksheet.json and regenerate; never hand-edit a GENERATED region."
                  % len(drift), file=sys.stderr)
            sys.exit(1)
        print("generate-metro-files: OK — all %d GENERATED regions match the worksheet" % len(TARGETS))
    else:
        print("generate-metro-files: OK — %d regions processed" % len(TARGETS))


if __name__ == "__main__":
    main()
