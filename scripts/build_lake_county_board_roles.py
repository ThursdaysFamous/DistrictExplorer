#!/usr/bin/env python3
"""
Resolve scripts/lake_county_board_roles_scraper.py's raw output into
data/app/lake-county-board-roles.json, keyed by Lake County Board district
("1".."19").

Each entry is {"name": ..., "role"?: "Chair"|"Vice-Chair"} — role omitted
for ordinary members. The name is included so index.html can apply a role
ONLY when the scraped surname matches the boundary GIS's member name for
that district (the GIS stays the live source for names/contact; this file
adds just the leadership tags the GIS lacks, and a post-reorganization
mismatch degrades to a role-less row rather than mislabeling a chair).

Usage:
    python3 build_lake_county_board_roles.py <raw-scraper-output.json> [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

SOURCE_URL = "https://www.lakecountyil.gov/2336/Board-Members"

# 19 single-member districts with exactly one Chair and one Vice-Chair —
# anything else means the directory page changed shape (or a partial parse)
# and the file must not be overwritten.
EXPECTED_DISTRICTS = 19

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def main():
    if len(sys.argv) not in (2, 3):
        print("usage: %s <raw-scraper-output.json> [output_dir]" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        raw = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    roster = {}
    for rec in raw.get("members", []):
        if not rec.get("district") or not rec.get("name"):
            continue
        entry = {"name": rec["name"]}
        if rec.get("role"):
            entry["role"] = rec["role"]
        roster[str(rec["district"])] = entry

    chairs = [d for d, e in roster.items() if e.get("role") == "Chair"]
    vices = [d for d, e in roster.items() if e.get("role") == "Vice-Chair"]

    if len(roster) != EXPECTED_DISTRICTS:
        print("WARNING: parsed %d/%d districts — refusing to overwrite the roles "
              "file with a partial parse" % (len(roster), EXPECTED_DISTRICTS), file=sys.stderr)
        sys.exit(1)
    if len(chairs) != 1 or len(vices) != 1:
        print("WARNING: parsed %d Chair / %d Vice-Chair rows (expected exactly 1 each) "
              "— the directory page likely changed shape; refusing to overwrite"
              % (len(chairs), len(vices)), file=sys.stderr)
        sys.exit(1)

    ordered = {d: roster[d] for d in sorted(roster, key=int)}
    ordered["sourceUrl"] = SOURCE_URL
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "lake-county-board-roles.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Wrote %s: %d districts (Chair d%s, Vice-Chair d%s)"
          % (out_path, len(roster), chairs[0], vices[0]), file=sys.stderr)


if __name__ == "__main__":
    main()
