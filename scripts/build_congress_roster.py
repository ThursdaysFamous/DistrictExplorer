#!/usr/bin/env python3
"""
Build the IL U.S. House roster (district -> current officeholder) as a
same-origin app-data file, so the congress card no longer downloads the full
national roster to every browser.

index.html used to fetch unitedstates/congress-legislators'
legislators-current.json (~1.5 MB, all ~538 members with every term each has
ever served) at click time and filter it client-side for the one matching IL
representative — using a few hundred bytes of a multi-megabyte payload. This
script does that filtering once at build time and writes IL's 17 reps to
data/app/congress-roster.json (~3 KB), which index.html fetches lazily on first
click (same-origin, no CORS, no third-party host dependency at runtime).

The source is the canonical single legislators-current.json file. This script
downloads it (stdlib urllib, no extra dependencies) unless a local path is
given, resolves the current officeholder per IL congressional district, and
writes the roster JSON. A weekly GitHub Action
(.github/workflows/update-congress-roster.yml) reruns this and opens a PR when
the roster changes, so officeholder data still gets a human look before it
ships.

Usage:
    python3 build_congress_roster.py [legislators-current.json] [output_dir]

With no arguments it downloads the source and writes to the repo's data/app/.
Pass a local legislators-current.json to build offline; pass an output_dir to
redirect the write (used by tests).
"""

import json
import os
import sys
import urllib.request

SOURCE_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"

# IL currently has 17 U.S. House districts. Refuse to overwrite the roster with
# anything short of a full delegation — a truncated source download or an
# upstream schema change should fail loudly, not ship a roster with holes.
EXPECTED_DISTRICTS = 17

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def load_source(path):
    if path:
        with open(path) as f:
            return json.load(f)
    with urllib.request.urlopen(SOURCE_URL, timeout=60) as resp:
        return json.load(resp)


def rep_name(legislator):
    name = legislator.get("name") or {}
    if name.get("official_full"):
        return name["official_full"]
    first, last = name.get("first"), name.get("last")
    if first and last:
        return first + " " + last
    return last or first


def resolve_roster(legislators):
    # The current officeholder is the person whose most recent term is the seat
    # we're keying on — congress-legislators lists terms chronologically, so the
    # last term is the current one for anyone in legislators-current.json.
    roster = {}
    for legislator in legislators:
        terms = legislator.get("terms") or []
        if not terms:
            continue
        term = terms[-1]
        if term.get("type") != "rep" or term.get("state") != "IL":
            continue
        district = term.get("district")
        if district is None:
            continue
        roster[str(district)] = {
            "name": rep_name(legislator),
            "party": term.get("party"),
            "phone": term.get("phone"),
            "url": term.get("url"),
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
    if len(sys.argv) > 3:
        print(f"usage: {sys.argv[0]} [legislators-current.json] [output_dir]", file=sys.stderr)
        sys.exit(1)

    src_path = sys.argv[1] if len(sys.argv) >= 2 else None
    out_dir = sys.argv[2] if len(sys.argv) == 3 else DEFAULT_OUT_DIR

    legislators = load_source(src_path)
    roster = resolve_roster(legislators)

    if len(roster) < EXPECTED_DISTRICTS:
        print(
            f"WARNING: resolved {len(roster)}/{EXPECTED_DISTRICTS} IL U.S. House "
            "districts — refusing to overwrite the roster with an incomplete "
            "delegation",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "congress-roster.json")
    write_json(out_path, roster)

    print(f"Wrote {out_path} ({len(roster)} districts)", file=sys.stderr)


if __name__ == "__main__":
    main()
