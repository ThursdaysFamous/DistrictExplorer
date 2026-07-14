#!/usr/bin/env python3
"""
Resolve scripts/will_county_board_scraper.py's raw output into
data/app/will-county-board-members.json, keyed by Will County Board district.

index.html's "Will County Board District" layer fetches this file lazily on
first click (same-origin) and joins it to the county's own board-district
boundary GIS by district number — the same boundary+roster join school-board
and ccpsa-district-council use. Stage 2 of the two-stage pipeline (see
scripts/will_county_board_scraper.py); mirrors build_ccpsa_roster.py.

Usage:
    python3 build_will_county_board_roster.py <raw-scraper-output.json> [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

SOURCE_URL = "https://www.willcountyboard.com/board-members.html"

# The board is 11 districts, 2 members each (22). Refuse to overwrite the file
# with a suspiciously partial scrape rather than silently wiping good data —
# the same safety net as build_ccpsa_roster.py / build_il_roster.py.
MIN_DISTRICTS = 11
MIN_MEMBERS = 20
# Emails are the enrichment this roster exists for (names alone are already on
# the boundary GIS). They come from decoding the pages' Cloudflare obfuscation;
# if that encoding changes, the decode yields nothing and the roster silently
# loses its whole point — so guard the email count explicitly.
MIN_EMAILS = 15

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def resolve_roster(records):
    roster = {}
    for rec in records:
        district = rec.get("district")
        name = rec.get("name")
        if district is None or not name:
            continue
        member = {"name": name}
        for k in ("role", "city", "phone", "email"):
            if rec.get(k):
                member[k] = rec[k]
        if rec.get("committees"):
            member["committees"] = rec["committees"]
        roster.setdefault(str(district), {"members": [], "sourceUrl": SOURCE_URL})
        roster[str(district)]["members"].append(member)
    return roster


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> [output_dir]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        records = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    roster = resolve_roster(records)
    total_members = sum(len(v["members"]) for v in roster.values())
    total_emails = sum(1 for v in roster.values() for m in v["members"] if m.get("email"))

    if len(roster) < MIN_DISTRICTS:
        print(f"WARNING: resolved only {len(roster)}/{MIN_DISTRICTS} districts — refusing to "
              "overwrite the roster with an incomplete scrape", file=sys.stderr)
        sys.exit(1)
    if total_members < MIN_MEMBERS:
        print(f"WARNING: only {total_members}/{MIN_MEMBERS}+ members parsed across "
              f"{len(roster)} districts — likely site drift; refusing to overwrite", file=sys.stderr)
        sys.exit(1)
    if total_emails < MIN_EMAILS:
        print(f"WARNING: only {total_emails}/{MIN_EMAILS}+ member emails decoded — the "
              "Cloudflare email encoding likely changed; refusing to overwrite", file=sys.stderr)
        sys.exit(1)

    ordered = {d: roster[d] for d in sorted(roster, key=int)}
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "will-county-board-members.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {out_path}: {len(roster)} districts, {total_members} members, "
          f"{total_emails} emails", file=sys.stderr)


if __name__ == "__main__":
    main()
