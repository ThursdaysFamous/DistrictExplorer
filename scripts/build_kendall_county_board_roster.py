#!/usr/bin/env python3
"""
Resolve scripts/kendall_county_board_scraper.py's raw output into
data/app/kendall-county-board-members.json, keyed by Kendall County Board
district ("1"/"2" — the county's two-district, 10-member board).

index.html's consolidated county-board layer fetches this file lazily on
first click (same-origin) and joins it to the county's own County_Board_2010
boundary by district number — the same boundary+roster join the Will and
DuPage entries use. Stage 2 of the two-stage pipeline (see
scripts/kendall_county_board_scraper.py); mirrors
build_will_county_board_roster.py.

Usage:
    python3 build_kendall_county_board_roster.py <raw-scraper-output.json> [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

SOURCE_URL = "https://www.kendallcountyil.gov/county-board/board-members"

# The board is 2 districts electing 5 members each (10). Refuse to overwrite
# the file with a suspiciously partial scrape rather than silently wiping good
# data — the same safety net as build_will_county_board_roster.py.
MIN_DISTRICTS = 2
MIN_MEMBERS = 9
# Emails are the enrichment this roster exists for (the county GIS carries
# only the district number); every member page publishes one, so a collapse
# in the email count means the Contact-block parse broke, not the members.
MIN_EMAILS = 8

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
        for k in ("role", "phone", "email"):
            if rec.get(k):
                member[k] = rec[k]
        roster.setdefault(str(district), {"members": [], "sourceUrl": SOURCE_URL})
        roster[str(district)]["members"].append(member)
    return roster


def main():
    if len(sys.argv) not in (2, 3):
        print("usage: %s <raw-scraper-output.json> [output_dir]" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        records = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    roster = resolve_roster(records)
    total_members = sum(len(v["members"]) for v in roster.values())
    total_emails = sum(1 for v in roster.values() for m in v["members"] if m.get("email"))

    if len(roster) < MIN_DISTRICTS:
        print("WARNING: resolved only %d/%d districts — refusing to overwrite the "
              "roster with an incomplete scrape" % (len(roster), MIN_DISTRICTS), file=sys.stderr)
        sys.exit(1)
    if total_members < MIN_MEMBERS:
        print("WARNING: only %d/%d+ members parsed across %d districts — likely site "
              "drift; refusing to overwrite" % (total_members, MIN_MEMBERS, len(roster)),
              file=sys.stderr)
        sys.exit(1)
    if total_emails < MIN_EMAILS:
        print("WARNING: only %d/%d+ member emails parsed — the Contact-block parse "
              "likely broke; refusing to overwrite" % (total_emails, MIN_EMAILS),
              file=sys.stderr)
        sys.exit(1)

    ordered = {d: roster[d] for d in sorted(roster, key=int)}
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "kendall-county-board-members.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Wrote %s: %d districts, %d members, %d emails"
          % (out_path, len(roster), total_members, total_emails), file=sys.stderr)


if __name__ == "__main__":
    main()
