#!/usr/bin/env python3
"""
Resolve scripts/cpd_district_scraper.py's raw output into one record per
district and write it as the JSON app-data file the Police District card reads.

This roster used to be spliced into a CPD_DISTRICT_INFO object literal inside
index.html. It now lives in data/app/cpd-district-info.json, which index.html
fetches lazily on first click (same-origin, no CORS needed). Writing plain JSON
instead of rewriting a 400 KB HTML file removes the regex splice entirely, along
with the </script and U+2028/U+2029 escaping subtleties it required — json.dump
handles all of that. Same approach as scripts/build_il_roster.py.

Usage:
    python3 build_cpd_roster.py cpd_district_info.json [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

# CPD currently operates 22 police districts (some numbers were retired after
# past mergers, e.g. 13 and 21). Refuse to overwrite the file if a scrape
# resolves suspiciously few districts, rather than silently wiping good data
# with a broken/partial run — same safety net as build_il_roster.py's 59/118
# senate/house guard.
MIN_DISTRICTS = 20

# Output-side guard (playbook R3): station address/phone now have a CORS
# fallback in the app, so the commander name is the roster's real reason to
# exist — and it's the field most likely to silently vanish if CPD rewords the
# "Meet your commander" block, since the heuristic parser nulls it rather than
# crashing. A scrape that returns enough *districts* but almost no *commanders*
# is parser drift, not real data; refuse it so a reworded page can't quietly
# blank every card's headline field.
MIN_COMMANDERS = 15

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
        roster[str(district)] = {
            "commanderName": record.get("commander_name"),
            "commanderStatus": record.get("commander_status"),
            "commanderBio": record.get("commander_bio"),
            "mainPhone": record.get("main_phone"),
            "capsPhone": record.get("caps_phone"),
            "capsEmail": record.get("caps_email"),
            "stationAddress": record.get("station_address"),
            "districtMapUrl": record.get("district_map_url"),
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

    if len(roster) < MIN_DISTRICTS:
        print(
            f"WARNING: resolved only {len(roster)}/{MIN_DISTRICTS}+ expected districts — "
            "refusing to overwrite the roster file with an incomplete roster",
            file=sys.stderr,
        )
        sys.exit(1)

    commanders = sum(1 for v in roster.values() if v.get("commanderName"))
    if commanders < MIN_COMMANDERS:
        print(
            f"WARNING: only {commanders}/{MIN_COMMANDERS}+ districts have a commander name — "
            "the scrape likely fetched pages but failed to parse the commander block "
            "(CPD site drift); refusing to overwrite the roster",
            file=sys.stderr,
        )
        sys.exit(1)

    # Emit districts in numeric order so the file diffs cleanly week to week.
    ordered = {d: roster[d] for d in sorted(roster, key=int)}

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "cpd-district-info.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {out_path}: {len(roster)} districts", file=sys.stderr)


if __name__ == "__main__":
    main()
