#!/usr/bin/env python3
"""
Resolve scripts/ccpsa_scraper.py's raw output into one record per District
Council and write it as the JSON app-data file the CCPSA District Council card
reads: data/app/ccpsa-district-councils.json, keyed by police-district number.

index.html fetches this file lazily on first click (same-origin, no CORS needed)
and joins it to the police-district boundary the app already loads — the CCPSA's
22 District Councils share the CPD district boundaries exactly (one council per
district). Same two-stage build pattern as scripts/ilga_scraper.py +
scripts/build_il_roster.py and scripts/cpd_district_scraper.py +
scripts/build_cpd_roster.py.

Usage:
    python3 build_ccpsa_roster.py ccpsa_district_councils.json [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

# CCPSA runs 22 District Councils (districts 13 and 21 are retired numbers).
# Refuse to overwrite the file if a scrape resolves suspiciously few councils,
# rather than silently wiping good data with a broken/partial run — same safety
# net as build_cpd_roster.py's MIN_DISTRICTS and build_il_roster.py's 59/118.
MIN_COUNCILS = 20

# Output-side guard: councilors are this roster's whole reason to exist, and the
# name is the field most likely to silently vanish if CCPSA reworks the member
# card template (the parser drops unparseable cards rather than crashing). Each
# council seats up to three councilors, so a healthy scrape yields dozens of
# names; refuse a scrape that fetched councils but parsed almost no councilors.
MIN_COUNCILORS = 40

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def resolve_roster(records):
    roster = {}
    for record in records:
        if record.get("error"):
            continue
        district = record.get("district_number")
        if district is None:
            continue
        members = []
        for m in record.get("members") or []:
            name = m.get("name")
            if not name:
                continue
            members.append(
                {
                    "name": name,
                    "role": m.get("role"),
                    "profileUrl": m.get("profile_url"),
                }
            )
        roster[str(district)] = {
            "members": members,
            "sourceUrl": record.get("source_url"),
        }
    return roster


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> [output_dir]", file=sys.stderr)
        sys.exit(1)

    raw_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    with open(raw_path) as f:
        records = json.load(f)

    roster = resolve_roster(records)

    if len(roster) < MIN_COUNCILS:
        print(
            f"WARNING: resolved only {len(roster)}/{MIN_COUNCILS}+ expected councils — "
            "refusing to overwrite the roster file with an incomplete roster",
            file=sys.stderr,
        )
        sys.exit(1)

    total_councilors = sum(len(v["members"]) for v in roster.values())
    if total_councilors < MIN_COUNCILORS:
        print(
            f"WARNING: only {total_councilors}/{MIN_COUNCILORS}+ councilors parsed across "
            f"{len(roster)} councils — the scrape likely fetched pages but failed to parse "
            "the member cards (CCPSA site drift); refusing to overwrite the roster",
            file=sys.stderr,
        )
        sys.exit(1)

    # Emit councils in numeric order so the file diffs cleanly week to week.
    ordered = {d: roster[d] for d in sorted(roster, key=int)}

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "ccpsa-district-councils.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"Wrote {out_path}: {len(roster)} councils, {total_councilors} councilors",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
