#!/usr/bin/env python3
"""
Resolve scripts/il_county_clerk_scraper.py's raw ISBE output into one record
per Illinois county and write it as the JSON app-data file the County card
reads: data/app/il-county-clerks.json.

Keys are the county name NORMALIZED to uppercase letters only ("STCLAIR",
"DEKALB", "LASALLE") because the two sides of the join spell counties
differently — ISBE writes "ST. CLAIR"/"DuPAGE"/"JoDAVIESS" while the TIGERweb
county layer's NAME field writes "St. Clair"/"DuPage"/"JoDaviess". index.html
applies the same normalization (uppercase, strip non-letters) to the TIGER
name before the lookup, so the two can't drift apart on punctuation or
casing.

Municipal boards of election commissioners (Jurisdiction "CITY OF …") are
election authorities but not county clerks; they are filtered out here.

Usage:
    python3 build_county_clerk_roster.py il_county_clerks.json [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import re
import sys

# Illinois has 102 counties, but ISBE's directory lists each county's
# ELECTION AUTHORITY — which is the elected county clerk everywhere except
# Peoria, whose authority is the appointed Peoria County Election Commission
# (its row carries an EXECUTIVE DIRECTOR title, not the clerk). Attributing
# the commission's director to the "County Clerk" card row would be wrong, so
# Peoria is a known, deliberate absence: its county card simply shows no
# clerk rows. The guard pins BOTH facts — 101 clerks AND Peoria being the one
# missing — so if another county adopts a commission, Peoria reverts to a
# clerk authority, or the parse breaks, the build fails for a human look
# instead of silently shifting coverage.
EXPECTED_COUNTIES = 101
EXPECTED_MISSING = {"PEORIA"}

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def norm_county(name):
    return re.sub(r"[^A-Z]", "", (name or "").upper())


def main():
    if len(sys.argv) < 2:
        print("usage: build_county_clerk_roster.py <scraper_output.json> [output_dir]", file=sys.stderr)
        sys.exit(2)
    with open(sys.argv[1]) as f:
        records = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT_DIR

    roster = {}
    for r in records:
        title = (r.get("title") or "").upper()
        jurisdiction = r.get("jurisdiction") or ""
        # county rows only: municipal boards ("CITY OF …") are not county
        # clerks, and a title without COUNTY CLERK (e.g. EXECUTIVE DIRECTOR)
        # isn't the elected officer this roster exists to name.
        if jurisdiction.upper().startswith("CITY OF") or "COUNTY CLERK" not in title:
            continue
        name = (r.get("name") or "").strip()
        key = norm_county(jurisdiction)
        if not name or not key:
            continue
        if key in roster:
            print("FATAL: two clerk rows resolved to county %s" % key, file=sys.stderr)
            sys.exit(1)
        entry = {"name": name}
        for field in ("address", "phone", "email"):
            value = (r.get(field) or "").strip()
            if value:
                entry[field] = value
        roster[key] = entry

    if len(roster) != EXPECTED_COUNTIES:
        print("FATAL: resolved %d county clerks, expected exactly %d — refusing to write"
              % (len(roster), EXPECTED_COUNTIES), file=sys.stderr)
        sys.exit(1)
    if EXPECTED_MISSING & set(roster):
        print("FATAL: %s resolved a county-clerk row but is expected to be an "
              "election-commission county — source changed, review before shipping"
              % sorted(EXPECTED_MISSING & set(roster)), file=sys.stderr)
        sys.exit(1)

    out_path = os.path.join(out_dir, "il-county-clerks.json")
    with open(out_path, "w") as f:
        json.dump(roster, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print("wrote %s: %d county clerks" % (out_path, len(roster)), file=sys.stderr)


if __name__ == "__main__":
    main()
