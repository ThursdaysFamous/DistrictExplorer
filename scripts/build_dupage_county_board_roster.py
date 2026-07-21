#!/usr/bin/env python3
"""
Resolve scripts/dupage_county_board_scraper.py's raw output into
data/app/dupage-county-board-members.json, keyed by DuPage County Board district
(plus a top-level "chair" for the countywide-elected Board Chair).

index.html's "DuPage County Board District" layer fetches this file lazily on
first click (same-origin) and joins it to the county's own board-district
boundary GIS by district number — the boundary+roster join Will County and
school-board use. The Chair is elected countywide, so the card surfaces her on
every DuPage district (she represents the whole county). Stage 2 of the
two-stage pipeline; mirrors build_will_county_board_roster.py.

Usage:
    python3 build_dupage_county_board_roster.py <raw-scraper-output.json> [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import sys

SOURCE_URL = "https://www.dupagecounty.gov/government/county_board/county_board_members/"

# 6 districts, 3 members each (18), plus the countywide Chair. Refuse to
# overwrite the file with a suspiciously partial scrape rather than silently
# wiping good data — the safety net every roster builder carries.
MIN_DISTRICTS = 6
MIN_MEMBERS = 18
# Contact is the enrichment this roster adds over the boundary (which carries no
# names at all). Every member publishes a tel: and a @dupagecounty.gov mailto:
# in the directory; guard both counts so a markup change that drops the links
# fails loudly rather than silently shipping a contactless roster.
MIN_EMAILS = 12
MIN_PHONES = 12

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def member_obj(rec):
    m = {"name": rec["name"]}
    # "Member" is the default role and needn't be stored; a real "Chair" does.
    if rec.get("role") and rec["role"] != "Member":
        m["role"] = rec["role"]
    for k in ("phone", "email", "url"):
        if rec.get(k):
            m[k] = rec[k]
    return m


def resolve_roster(records):
    roster = {}
    chair = None
    for rec in records:
        if not rec.get("name"):
            continue
        if rec.get("role") == "Chair":
            chair = member_obj(rec)
            continue
        if rec.get("district") is None:
            continue
        d = str(rec["district"])
        roster.setdefault(d, {"members": [], "sourceUrl": SOURCE_URL})
        roster[d]["members"].append(member_obj(rec))
    if chair:
        roster["chair"] = chair
    return roster


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> [output_dir]", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1]) as f:
        records = json.load(f)
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    roster = resolve_roster(records)
    districts = [k for k in roster if k != "chair"]
    total_members = sum(len(roster[d]["members"]) for d in districts)
    total_emails = sum(1 for d in districts for m in roster[d]["members"] if m.get("email"))
    total_phones = sum(1 for d in districts for m in roster[d]["members"] if m.get("phone"))
    if roster.get("chair", {}).get("email"):
        total_emails += 1
    if roster.get("chair", {}).get("phone"):
        total_phones += 1

    if len(districts) < MIN_DISTRICTS:
        print(f"WARNING: resolved only {len(districts)}/{MIN_DISTRICTS} districts — refusing "
              "to overwrite the roster with an incomplete scrape", file=sys.stderr)
        sys.exit(1)
    if total_members < MIN_MEMBERS:
        print(f"WARNING: only {total_members}/{MIN_MEMBERS} members parsed across "
              f"{len(districts)} districts — likely site drift; refusing to overwrite", file=sys.stderr)
        sys.exit(1)
    if total_emails < MIN_EMAILS:
        print(f"WARNING: only {total_emails}/{MIN_EMAILS}+ member emails — the directory "
              "markup likely changed; refusing to overwrite", file=sys.stderr)
        sys.exit(1)
    if total_phones < MIN_PHONES:
        print(f"WARNING: only {total_phones}/{MIN_PHONES}+ member phones — the directory "
              "markup likely changed; refusing to overwrite", file=sys.stderr)
        sys.exit(1)

    # district keys in numeric order, chair last
    ordered = {d: roster[d] for d in sorted(districts, key=int)}
    if "chair" in roster:
        ordered["chair"] = roster["chair"]

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "dupage-county-board-members.json")
    with open(out_path, "w") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"Wrote {out_path}: {len(districts)} districts, {total_members} members, "
          f"{total_phones} phones, {total_emails} emails{', +chair' if 'chair' in roster else ''}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
