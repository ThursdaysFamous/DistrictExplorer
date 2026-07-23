#!/usr/bin/env python3
"""
Resolve scripts/kane_county_board_scraper.py's raw output into
data/app/kane-county-board-members.json, keyed by Kane County Board district
("1".."24" — 24 single-member districts) plus a top-level "chair" for the
countywide-elected Board Chair (the DuPage/McHenry roster shape).

index.html's consolidated county-board layer fetches this file lazily on
first click (same-origin) and joins it to the county's own
KaneCo_IL_County_Board boundary GIS by district number. The GIS keeps
carrying the sitting member's NAME (used for hover and as the card's
fallback); this roster enriches the card with party, the official office
phone, email, and a profile link. Stage 2 of the two-stage pipeline (see
scripts/kane_county_board_scraper.py); mirrors
build_mchenry_county_board_roster.py.

Usage:
    python3 build_kane_county_board_roster.py <raw-scraper-output.json> [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

SOURCE_URL = "https://www2.kanecountyil.gov/pages/countyboard/boardMembers.aspx"

# 24 single-member districts + the countywide Chair. Refuse to overwrite the
# file with a suspiciously partial scrape rather than silently wiping good
# data — the same safety net as the sibling board builders.
MIN_DISTRICTS = 22
MIN_MEMBERS = 22
# Every list record publishes an email; a collapse means the list schema
# moved (e.g. the E-Mail column renamed), not the members.
MIN_EMAILS = 20

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def member_obj(rec):
    member = {"name": rec["name"]}
    for k in ("role", "party", "phone", "email", "url"):
        if rec.get(k):
            member[k] = rec[k]
    return member


def resolve_roster(records):
    roster = {}
    chair = None
    for rec in records:
        if not rec.get("name"):
            continue
        if rec.get("role") == "Chair" and rec.get("district") is None:
            chair = member_obj(rec)
            continue
        district = rec.get("district")
        if district is None:
            continue
        roster.setdefault(str(district), {"members": [], "sourceUrl": SOURCE_URL})
        roster[str(district)]["members"].append(member_obj(rec))
    if chair:
        roster["chair"] = chair
    return roster


def main():
    if len(sys.argv) not in (2, 3):
        print("usage: %s <raw-scraper-output.json> [output_dir]" % sys.argv[0], file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        records = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    roster = resolve_roster(records)
    districts = [k for k in roster if k != "chair"]
    total_members = sum(len(roster[d]["members"]) for d in districts)
    total_emails = sum(1 for d in districts for m in roster[d]["members"] if m.get("email"))

    if len(districts) < MIN_DISTRICTS:
        print("WARNING: resolved only %d/%d districts — refusing to overwrite the "
              "roster with an incomplete scrape" % (len(districts), MIN_DISTRICTS),
              file=sys.stderr)
        sys.exit(1)
    if total_members < MIN_MEMBERS:
        print("WARNING: only %d/%d+ members parsed across %d districts — likely list "
              "drift; refusing to overwrite" % (total_members, MIN_MEMBERS, len(districts)),
              file=sys.stderr)
        sys.exit(1)
    if total_emails < MIN_EMAILS:
        print("WARNING: only %d/%d+ member emails parsed — the E-Mail column likely "
              "moved; refusing to overwrite" % (total_emails, MIN_EMAILS), file=sys.stderr)
        sys.exit(1)
    if not roster.get("chair", {}).get("email"):
        print("WARNING: no countywide Chair with an email resolved — the Chairman "
              "flag parse likely broke; refusing to overwrite", file=sys.stderr)
        sys.exit(1)

    # district keys in numeric order, chair last
    ordered = {d: roster[d] for d in sorted(districts, key=int)}
    ordered["chair"] = roster["chair"]
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "kane-county-board-members.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print("Wrote %s: %d districts + chair, %d members, %d emails"
          % (out_path, len(districts), total_members, total_emails), file=sys.stderr)


if __name__ == "__main__":
    main()
