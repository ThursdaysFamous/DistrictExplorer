#!/usr/bin/env python3
"""
Resolve scripts/ilga_scraper.py's raw output into the current officeholder
per district and write the IL Senate / IL House rosters as JSON app-data files.

These rosters used to be spliced into object literals inside index.html. They
now live in data/app/il-senate-members.json and data/app/il-house-members.json,
which index.html fetches lazily on first click (same-origin, no CORS needed).
Writing plain JSON instead of rewriting a 400 KB HTML file removes the regex
splice entirely — the class of bug that could silently drop live code (see
docs/BUILD_PLAYBOOK_1.md) no longer exists here.

Usage:
    python3 build_il_roster.py ilga_network.json [output_dir]

output_dir defaults to the repo's data/app/ directory.
"""

import json
import os
import re
import sys

PARTY_NAMES = {"D": "Democratic", "R": "Republican", "I": "Independent"}

DISTRICT_RE = re.compile(r"^\s*(\d+)")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def district_number(record):
    for field in ("district", "term"):
        value = record.get(field)
        if value:
            m = DISTRICT_RE.match(value)
            if m:
                return m.group(1)
    return None


def is_current(record):
    term = record.get("term") or ""
    return "present" in term.lower()


def resolve_roster(records, chamber):
    by_district = {}
    for record in records:
        if record.get("chamber") != chamber or record.get("error"):
            continue
        district = district_number(record)
        if not district:
            continue
        by_district.setdefault(district, []).append(record)

    roster = {}
    for district, candidates in by_district.items():
        current = [c for c in candidates if is_current(c)]
        if current:
            chosen = current[0]
        else:
            # No record explicitly says "Present" (e.g. a same-day handoff) —
            # fall back to the highest member_id, since ILGA assigns these
            # sequentially and a newer id means a more recently seated member.
            chosen = max(candidates, key=lambda c: int(c["member_id"]))
        party_code = chosen.get("party")
        roster[district] = {
            "name": chosen.get("name"),
            "party": PARTY_NAMES.get(party_code, party_code),
            "springfieldOffice": chosen.get("springfield_office"),
            "districtOffice": chosen.get("district_office"),
            "url": chosen.get("source_url"),
        }
    return roster


def ordered(roster):
    # Emit districts in numeric order so the file diffs cleanly week to week.
    return {d: roster[d] for d in sorted(roster, key=int)}


def write_json(path, roster):
    with open(path, "w") as f:
        json.dump(ordered(roster), f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    if len(sys.argv) not in (2, 3):
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> [output_dir]", file=sys.stderr)
        sys.exit(1)

    raw_path = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    with open(raw_path) as f:
        records = json.load(f)

    senate_roster = resolve_roster(records, "senate")
    house_roster = resolve_roster(records, "house")

    if len(senate_roster) < 59 or len(house_roster) < 118:
        print(
            f"WARNING: resolved {len(senate_roster)}/59 senate and "
            f"{len(house_roster)}/118 house districts — refusing to overwrite "
            "the roster files with an incomplete roster",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    write_json(os.path.join(out_dir, "il-senate-members.json"), senate_roster)
    write_json(os.path.join(out_dir, "il-house-members.json"), house_roster)

    print(
        f"Wrote {out_dir}/il-senate-members.json ({len(senate_roster)} districts), "
        f"il-house-members.json ({len(house_roster)} districts)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
