#!/usr/bin/env python3
"""
Source freshness gate for the app's data layers.

Why this exists: unlike the roster scrapers (which re-pull the same page every
week), several layers point at a *specific* upstream dataset that the publisher
silently supersedes with a new one:

  * Chicago Data Portal (Socrata) datasets are versioned by year. The CPS
    attendance-boundary layers, for example, are published fresh every school
    year under a BRAND NEW dataset id (…SY2526 → …SY2627), so the id hardcoded
    in index.html keeps returning last year's boundaries long after a newer one
    exists. Nothing errors; the data just quietly goes stale.
  * The three shapefile-derived boundary layers (school board, IL Supreme
    Court, Cook County Board of Review) were downloaded once from decennial
    redistricting sources with no API. They change ~once a decade, so the check
    there is provenance: is the source we cite still reachable, and a reminder
    to re-verify.

This script does NOT edit index.html or any data file — swapping a dataset id
is a judgement call (the "newer" dataset may have a different schema), so, like
the roster workflows, it surfaces drift for a human instead of auto-applying it.

What it checks (findings carry a severity — FAIL, WARN, or OK):
  1. Manifest ↔ app coherence: every dataset id / data file the manifest knows
     about is still referenced in index.html (guards this file drifting from the
     app it validates).                                                   [FAIL]
  2. Socrata datasets: each id still resolves and still carries the stable part
     of its expected name (a rename usually means it was replaced).       [FAIL]
     For year-versioned datasets, the portal catalog is searched for a newer
     edition than the one in use.                                         [WARN]
  3. Shapefile provenance: the cited source URL is reachable and the built
     data/app file is present.                             [WARN / FAIL if gone]
  4. Live service endpoints (CPD ArcGIS, Census TIGERweb): reachable.      [WARN]

Exit status: 0 when nothing needs a human (OK or WARN only), 1 on any FAIL.
Newer-edition detection is deliberately WARN, not FAIL — the current dataset
still works and a person decides whether/when to migrate. The scheduled
workflow (.github/workflows/validate-sources.yml) opens an issue on WARN or
FAIL so drift is never silent, without turning the build red.

Usage:
    python3 scripts/validate_sources.py                 # human-readable report
    python3 scripts/validate_sources.py --report r.md   # also write markdown
    python3 scripts/validate_sources.py --status-file s.txt   # ok|warn|fail
    python3 scripts/validate_sources.py --offline       # manifest↔app checks only
"""

import argparse
import json
import os
import re
import sys

try:
    import requests
except ImportError:  # pragma: no cover - requests is pinned in requirements.txt
    requests = None

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")
APP_DATA_DIR = os.path.join(REPO_ROOT, "data", "app")

SOCRATA_DOMAIN = "data.cityofchicago.org"
CATALOG_API = "https://api.us.socrata.com/api/catalog/v1"
HTTP_TIMEOUT = 25

# ---------------------------------------------------------------------------
# The manifest: every source index.html depends on that can go stale silently.
#
# Socrata datasets — `name_contains` is the part of the portal title that must
# stay stable (a change means the dataset was replaced/renamed). `year_search`,
# when present, turns on newer-edition detection: the catalog is searched with
# `query`, results are kept only if their name also contains name_contains, and
# the `pattern` capture group (an int) is compared to pick the newest edition.
# ---------------------------------------------------------------------------
SOCRATA = [
    {"id": "p293-wvbd", "layer": "Ward + Alderman boundary",
     "name_contains": "Boundaries - Wards"},
    {"id": "htai-wnw4", "layer": "Alderman / Ward Offices",
     "name_contains": "Ward Offices"},
    {"id": "i8fv-xe4b", "layer": "Ward Precincts",
     "name_contains": "Boundaries - Ward Precincts"},
    {"id": "igwz-8jzy", "layer": "Community Area",
     "name_contains": "Boundaries - Community Areas"},
    # ZIP Code moved off Socrata to the statewide Census ZCTA layer (no city
    # boundary line) — the endpoint is tracked in ENDPOINTS below, not here.
    {"id": "x8fc-8rcq", "layer": "Library locations (nearest N)",
     "name_contains": "Libraries - Locations"},
    {"id": "x72b-38qv", "layer": "CPS Elementary School Zone",
     "name_contains": "Elementary School Attendance Boundaries",
     "year_search": {"query": "Elementary School Attendance Boundaries",
                     "pattern": r"SY(\d{4})"}},
    {"id": "xg7c-d8rm", "layer": "CPS High School Zone",
     "name_contains": "High School Attendance Boundaries",
     "year_search": {"query": "High School Attendance Boundaries",
                     "pattern": r"SY(\d{4})"}},
    {"id": "fyff-53xy", "layer": "CPS Middle School Zone",
     "name_contains": "Middle School Attendance Boundaries",
     "year_search": {"query": "Middle School Attendance Boundaries",
                     "pattern": r"SY(\d{4})"}},
    {"id": "pnta-kuqa", "layer": "CPS Network (K-8)",
     "name_contains": "Elementary Geographic Networks"},
    {"id": "aupu-jt2g", "layer": "CPS Network (High School)",
     "name_contains": "High School Geographic Networks"},
]

# Decennial boundary layers built into same-origin data/app files: no runtime
# API. `source_url` is the provenance we cite; `app_file` is the built file.
# These go stale only when the underlying districts are redrawn — the check is a
# reachability probe plus a standing reminder to re-verify against the source.
# The first three are shapefile-derived; the three legislative layers are
# pre-built from Census TIGERweb by scripts/build_legislative_boundaries.py
# (R2-2 — they used to query TIGERweb live at ~5.7 s per first toggle).
PROVENANCE = [
    {"layer": "School Board (ERSB) districts",
     "app_file": "school-board-districts.json",
     "source_url": "https://www.ilsenateredistricting.com/",
     "note": "ERSB 20-subdistrict map (SB 15). Redrawn ~once a decade."},
    {"layer": "IL Supreme Court districts",
     "app_file": "il-supreme-court-districts.json",
     "source_url": "https://www.illinoiscourts.gov/",
     "note": "PA 102-0011 shapefile. Redrawn ~once a decade."},
    {"layer": "Cook County Board of Review districts",
     "app_file": "ccbr-districts.json",
     "source_url": "https://www.cookcountyboardofreview.com/",
     "note": "PA 102-0012 shapefile. Redrawn ~once a decade."},
    {"layer": "Illinois county clerks (roster)",
     "app_file": "il-county-clerks.json",
     "source_url": "https://www.elections.il.gov/ElectionOperations/ElectionAuthorities.aspx",
     "note": "Scraped weekly from ISBE's election-authority directory "
             "(il_county_clerk_scraper.py); Peoria deliberately absent (its "
             "authority is the appointed county election commission)."},
    {"layer": "Board of Review commissioners (roster)",
     "app_file": "ccbr-roster.json",
     "source_url": "https://www.cookcountyboardofreview.com/",
     "note": "Scraped weekly from the Board's commissioner pages "
             "(ccbr_scraper.py); the menu-discovered pages move to new "
             "name-derived paths after elections, which the scraper follows."},
    {"layer": "U.S. House districts (IL)",
     "app_file": "congress-districts.json",
     "source_url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/0?f=json",
     "note": "TIGERweb Legislative layer 0 (STATE=17), pre-built by build_legislative_boundaries.py. Redrawn ~once a decade."},
    {"layer": "IL State Senate districts",
     "app_file": "il-senate-districts.json",
     "source_url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/1?f=json",
     "note": "TIGERweb Legislative layer 1 (2024 Upper, STATE=17), pre-built. Redrawn ~once a decade."},
    {"layer": "IL State House districts",
     "app_file": "il-house-districts.json",
     "source_url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/2?f=json",
     "note": "TIGERweb Legislative layer 2 (2024 Lower, STATE=17), pre-built. Redrawn ~once a decade."},
    {"layer": "Early-voting sites (Chicago Board of Elections)",
     "app_file": "early-voting-sites.json",
     "source_url": "https://chicagoelections.gov/voting/early-voting",
     "note": "Hand-transcribed per election (see WATCH.md row). The site 403s "
             "non-browser clients, so a reachability WARN here is expected, "
             "not drift — refresh the file when the Board posts the next "
             "election's list."},
]

# Live named services the app queries at runtime. These aren't year-versioned
# (they're views/endpoints kept current by the publisher), so the only useful
# check is reachability — a rename or retirement shows up here before users hit
# a broken card. WARN-only: the app already isolates a down source per-card.
ENDPOINTS = [
    {"layer": "CPD Police District boundaries",
     "url": "https://services2.arcgis.com/t3tlzCPfmaQzSWAk/arcgis/rest/services/Police_District_Boundary_View/FeatureServer/0?f=json"},
    {"layer": "CPD Police District stations",
     "url": "https://services2.arcgis.com/t3tlzCPfmaQzSWAk/arcgis/rest/services/Police_District_Stations_View/FeatureServer/0?f=json"},
    {"layer": "CPD Police Beat boundaries",
     "url": "https://services2.arcgis.com/t3tlzCPfmaQzSWAk/arcgis/rest/services/Police_Beat_Boundary/FeatureServer/0?f=json"},
    {"layer": "CPS school sites",
     "url": "https://services2.arcgis.com/t3tlzCPfmaQzSWAk/arcgis/rest/services/Schools/FeatureServer/0?f=json"},
    {"layer": "USGS National Map structures — post offices (layer 38)",
     "url": "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/38?f=json"},
    {"layer": "USGS National Map structures — fire stations (layer 51; replaced CFD 28km-gtjn)",
     "url": "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/51?f=json"},
    {"layer": "USGS National Map structures — police stations (layer 53; replaced the CPD station list for the nearest-3 layer)",
     "url": "https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/53?f=json"},
    {"layer": "Census TIGERweb counties (statewide county layer)",
     "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer?f=json"},
    {"layer": "Census TIGERweb county subdivisions + places (township/municipality layers)",
     "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer?f=json"},
    {"layer": "Census TIGERweb school districts (unified/secondary/elementary layers)",
     "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/School/MapServer?f=json"},
    {"layer": "Census TIGERweb ZCTAs (statewide ZIP Code layer)",
     "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer?f=json"},
    {"layer": "Census TIGERweb areal hydrography (Lake Michigan marker test)",
     "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Hydro/MapServer?f=json"},
    {"layer": "Will County Board districts 2022 (current 11-district map + reps)",
     "url": "https://services.arcgis.com/fGsbyIOAuxHnF97m/arcgis/rest/services/County_Board_Districts_2022/FeatureServer/0?f=json"},
    {"layer": "Lake County Board districts (19 members + contact carried on the county GIS)",
     "url": "https://services3.arcgis.com/HESxeTbDliKKvec2/arcgis/rest/services/LakeCounty_PoliticalBoundaries/FeatureServer/0?f=json"},
    {"layer": "Kane County Board districts (24 members carried on the county GIS)",
     "url": "https://services1.arcgis.com/oRKmdBXD6EbdmVgJ/arcgis/rest/services/KaneCo_IL_County_Board/FeatureServer/1?f=json"},
]

FAIL, WARN, OK = "FAIL", "WARN", "OK"


class Findings(object):
    """Collects (severity, layer, message) rows and tracks the worst seen."""

    def __init__(self):
        self.rows = []

    def add(self, severity, layer, message):
        self.rows.append((severity, layer, message))

    def status(self):
        if any(s == FAIL for s, _, _ in self.rows):
            return "fail"
        if any(s == WARN for s, _, _ in self.rows):
            return "warn"
        return "ok"


def http_get(url, want_json=True, params=None):
    """GET with a sane UA; returns (ok, payload_or_error). Never raises."""
    if requests is None:
        return False, "requests not installed"
    try:
        resp = requests.get(
            url,
            params=params,
            timeout=HTTP_TIMEOUT,
            headers={"User-Agent": "DistrictExplorer-CHI source validator (+https://chidistricts.com)"},
        )
    except Exception as e:  # network/TLS/proxy errors are a finding, not a crash
        return False, "request failed: %s" % e
    if resp.status_code >= 400:
        return False, "HTTP %d" % resp.status_code
    if not want_json:
        return True, resp
    try:
        return True, resp.json()
    except ValueError as e:
        return False, "non-JSON response: %s" % e


# ---- check 1: the manifest still matches what index.html actually uses -------
def check_manifest_matches_app(html, findings):
    for d in SOCRATA:
        if d["id"] not in html:
            findings.add(FAIL, d["layer"],
                         "dataset id %s not found in index.html — manifest is "
                         "out of sync with the app (update scripts/validate_sources.py)"
                         % d["id"])
    for p in PROVENANCE:
        if ("data/app/" + p["app_file"]) not in html:
            findings.add(FAIL, p["layer"],
                         "index.html no longer references data/app/%s — manifest drift"
                         % p["app_file"])


# ---- check 2: Socrata datasets resolve, keep their name, aren't superseded ---
def newest_edition(cfg):
    """Search the portal catalog for the newest edition matching cfg.

    Returns (id, name, year_int) for the highest `pattern` capture, or None if
    the search is unavailable / finds nothing usable.
    """
    ys = cfg["year_search"]
    ok, payload = http_get(CATALOG_API, params={
        "domains": SOCRATA_DOMAIN,
        "q": ys["query"],
        "only": "dataset,map,geospatial",
        "limit": 200,
    })
    if not ok or not isinstance(payload, dict):
        return None
    rx = re.compile(ys["pattern"])
    best = None
    for r in payload.get("results", []):
        res = r.get("resource", {})
        name = res.get("name", "")
        if cfg["name_contains"] not in name:
            continue
        m = rx.search(name)
        if not m:
            continue
        year = int(m.group(1))
        if best is None or year > best[2]:
            best = (res.get("id"), name, year)
    return best


def check_socrata(findings, offline):
    for cfg in SOCRATA:
        layer = cfg["layer"]
        if offline:
            continue
        ok, meta = http_get("https://%s/api/views/%s.json" % (SOCRATA_DOMAIN, cfg["id"]))
        if not ok:
            findings.add(FAIL, layer,
                         "dataset %s does not resolve on the portal (%s) — likely "
                         "retired or replaced" % (cfg["id"], meta))
            continue
        name = meta.get("name", "") if isinstance(meta, dict) else ""
        if cfg["name_contains"] not in name:
            findings.add(FAIL, layer,
                         "dataset %s is now named %r — expected it to contain %r; "
                         "the id may have been repurposed"
                         % (cfg["id"], name, cfg["name_contains"]))
            continue

        if "year_search" not in cfg:
            findings.add(OK, layer, "%s — %r" % (cfg["id"], name))
            continue

        # year-versioned: is a newer edition published?
        cur = re.search(cfg["year_search"]["pattern"], name)
        cur_year = int(cur.group(1)) if cur else None
        newest = newest_edition(cfg)
        if newest is None or cur_year is None:
            findings.add(OK, layer,
                         "%s — %r (newer-edition search unavailable)" % (cfg["id"], name))
        elif newest[2] > cur_year and newest[0] != cfg["id"]:
            findings.add(WARN, layer,
                         "in use: %s (%r). NEWER edition on the portal: %s (%r). "
                         "Review the newer dataset's schema, then update the id in index.html."
                         % (cfg["id"], name, newest[0], newest[1]))
        else:
            findings.add(OK, layer, "%s — %r (newest edition)" % (cfg["id"], name))


# ---- check 3: shapefile provenance reachable, built file present ------------
def check_provenance(findings, offline):
    for p in PROVENANCE:
        layer = p["layer"]
        fpath = os.path.join(APP_DATA_DIR, p["app_file"])
        if not os.path.exists(fpath):
            findings.add(FAIL, layer, "built data file data/app/%s is missing" % p["app_file"])
        if offline:
            continue
        ok, res = http_get(p["source_url"], want_json=False)
        if ok:
            findings.add(OK, layer, "source reachable: %s — %s" % (p["source_url"], p["note"]))
        else:
            findings.add(WARN, layer,
                         "source not reachable (%s): %s. Boundaries change ~once a "
                         "decade; verify the source still exists and re-download if redrawn. %s"
                         % (res, p["source_url"], p["note"]))


# ---- check 4: live endpoints reachable --------------------------------------
def check_endpoints(findings, offline):
    if offline:
        return
    for e in ENDPOINTS:
        ok, res = http_get(e["url"], want_json=False)
        if ok:
            findings.add(OK, e["layer"], "endpoint reachable")
        else:
            findings.add(WARN, e["layer"],
                         "endpoint not reachable (%s): %s — the service may have been "
                         "renamed or retired" % (res, e["url"]))


def render(findings):
    order = {FAIL: 0, WARN: 1, OK: 2}
    rows = sorted(findings.rows, key=lambda r: (order[r[0]], r[1]))
    n_fail = sum(1 for s, _, _ in rows if s == FAIL)
    n_warn = sum(1 for s, _, _ in rows if s == WARN)
    n_ok = sum(1 for s, _, _ in rows if s == OK)
    lines = []
    lines.append("# Layer source validation")
    lines.append("")
    lines.append("**%d FAIL · %d WARN · %d OK**" % (n_fail, n_warn, n_ok))
    lines.append("")
    if n_fail or n_warn:
        lines.append("Sources below need a human look. Nothing is auto-changed — "
                     "review, then update `index.html` (dataset ids) or re-download the "
                     "boundary shapefile as needed.")
        lines.append("")
    for sev in (FAIL, WARN, OK):
        group = [r for r in rows if r[0] == sev]
        if not group:
            continue
        lines.append("## %s (%d)" % (sev, len(group)))
        for _, layer, msg in group:
            lines.append("- **%s** — %s" % (layer, msg))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description="Validate the app's data-layer sources are current.")
    ap.add_argument("--report", metavar="PATH", help="write the markdown report to PATH (also printed to stdout)")
    ap.add_argument("--status-file", metavar="PATH", help="write ok|warn|fail to PATH (for CI)")
    ap.add_argument("--offline", action="store_true", help="run only the manifest↔index.html checks (no network)")
    args = ap.parse_args()

    if not os.path.exists(INDEX_HTML):
        print("validate_sources: FAIL — index.html not found at %s" % INDEX_HTML, file=sys.stderr)
        sys.exit(1)
    html = open(INDEX_HTML).read()

    if not args.offline and requests is None:
        print("validate_sources: requests not installed; run with --offline or "
              "`pip install -c scripts/requirements.txt requests`", file=sys.stderr)
        sys.exit(1)

    findings = Findings()
    check_manifest_matches_app(html, findings)
    check_socrata(findings, args.offline)
    check_provenance(findings, args.offline)
    check_endpoints(findings, args.offline)

    report = render(findings)
    sys.stdout.write(report)
    if args.report:
        with open(args.report, "w") as f:
            f.write(report)

    status = findings.status()
    if args.status_file:
        with open(args.status_file, "w") as f:
            f.write(status)

    sys.exit(1 if status == "fail" else 0)


if __name__ == "__main__":
    main()
