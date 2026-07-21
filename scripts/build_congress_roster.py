#!/usr/bin/env python3
"""
Build the IL U.S. House roster (district -> current officeholder + offices) as a
same-origin app-data file, so the congress card no longer downloads the full
national roster to every browser.

index.html used to fetch unitedstates/congress-legislators'
legislators-current.json (~1.5 MB, all ~538 members with every term each has
ever served) at click time and filter it client-side for the one matching IL
representative — using a few hundred bytes of a multi-megabyte payload. This
script does that filtering once at build time and writes IL's 17 reps to
data/app/congress-roster.json (a few KB), which index.html fetches lazily on
first click (same-origin, no CORS, no third-party host dependency at runtime).

Each entry now carries the two offices the card renders through the shared
chamber factory (registerIlgaChamber), matching the IL Senate / House cards:

  - capitolOffice  the Washington, D.C. office (room + building, city, phone),
                   from the legislator's current term.
  - districtOffice the member's primary local (in-district) office — street,
                   city/ZIP, phone — from legislators-district-offices.json,
                   joined by bioguide id. This is the office the card pins on
                   the map. A member can have several district offices; we emit
                   the first listed (typically the main one). Nearest-to-click
                   selection and the source's per-office lat/long are a possible
                   future refinement.

Both office feeds are the same canonical @unitedstates/congress-legislators
project already trusted for name/party — never guessed. District-office data is
crowdsourced from members' official sites there; if that feed is unreachable at
build time we still ship the D.C. office (the district office is simply omitted,
and the card degrades to the same surface as any member without one).

A weekly GitHub Action (.github/workflows/update-congress-roster.yml) reruns
this and opens a PR when the roster changes, so officeholder data still gets a
human look before it ships.

Usage:
    python3 build_congress_roster.py [legislators-current.json] [output_dir]

With no arguments it downloads the sources and writes to the repo's data/app/.
Pass a local legislators-current.json to build offline (the district-office
feed is still fetched from the network unless it is cached alongside it as
legislators-district-offices.json); pass an output_dir to redirect the write
(used by tests).
"""

import json
import os
import sys
import urllib.request

SOURCE_URL = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
DISTRICT_OFFICES_URL = "https://unitedstates.github.io/congress-legislators/legislators-district-offices.json"

# The state whose U.S. House delegation this fork's congress card covers.
STATE = "IL"

# IL currently has 17 U.S. House districts. Refuse to overwrite the roster with
# anything short of a full delegation — a truncated source download or an
# upstream schema change should fail loudly, not ship a roster with holes.
EXPECTED_DISTRICTS = 17

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "data", "app")


def fetch_json(url):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def load_source(path):
    if path:
        with open(path) as f:
            return json.load(f)
    return fetch_json(SOURCE_URL)


def load_district_offices(path):
    """Return {bioguide: [office, ...]}. Best-effort: a fetch failure yields an
    empty map so the roster still ships with D.C. offices only."""
    try:
        if path:
            with open(path) as f:
                data = json.load(f)
        else:
            data = fetch_json(DISTRICT_OFFICES_URL)
    except Exception as exc:  # network / parse — non-fatal, D.C. office still ships
        print(f"WARNING: district offices unavailable ({exc}); shipping D.C. "
              "offices only", file=sys.stderr)
        return {}
    offices = {}
    for member in data:
        bioguide = (member.get("id") or {}).get("bioguide")
        if bioguide:
            offices[bioguide] = member.get("offices") or []
    return offices


def rep_name(legislator):
    name = legislator.get("name") or {}
    if name.get("official_full"):
        return name["official_full"]
    first, last = name.get("first"), name.get("last")
    if first and last:
        return first + " " + last
    return last or first


def dc_office_lines(term):
    """Address lines for the Washington, D.C. office (rendered as capitolOffice).
    The card shows these as plain text; officeAddressForGeocode is not applied to
    the capitol office, so the phone line is safe to include here."""
    lines = []
    office = term.get("office") or term.get("address")
    if office:
        lines.append(office)
    # The standard House ZIP is 20515; term.office omits it, term.address folds
    # it into one string. Add the city/state/ZIP line only when it isn't already
    # present in the line we kept.
    if office and "20515" not in office and "Washington" not in office:
        lines.append("Washington, DC 20515")
    if term.get("phone"):
        lines.append("Phone: " + term["phone"])
    return lines


def district_office_lines(office):
    """Address lines for a single local (in-district) office, rendered as
    districtOffice. Street (+ suite / building) first, then city/state/ZIP, then
    phone — the order officeAddressForGeocode expects (it drops the phone line
    and geocodes the rest to drop the map pin)."""
    lines = []
    street = office.get("address")
    if street:
        if office.get("suite"):
            street += ", " + office["suite"]
        lines.append(street)
    if office.get("building"):
        lines.append(office["building"])
    # city/state/zip as "City, ST ZIP"
    if office.get("city") and office.get("state"):
        line = office["city"] + ", " + office["state"]
        if office.get("zip"):
            line += " " + office["zip"]
        lines.append(line)
    elif office.get("zip"):
        lines.append(office["zip"])
    if office.get("phone"):
        lines.append("Phone: " + office["phone"])
    return lines


def resolve_roster(legislators, offices_by_bioguide):
    # The current officeholder is the person whose most recent term is the seat
    # we're keying on — congress-legislators lists terms chronologically, so the
    # last term is the current one for anyone in legislators-current.json.
    roster = {}
    for legislator in legislators:
        terms = legislator.get("terms") or []
        if not terms:
            continue
        term = terms[-1]
        if term.get("type") != "rep" or term.get("state") != STATE:
            continue
        district = term.get("district")
        if district is None:
            continue
        entry = {
            "name": rep_name(legislator),
            "party": term.get("party"),
            "url": term.get("url"),
        }
        capitol = dc_office_lines(term)
        if capitol:
            entry["capitolOffice"] = capitol
        bioguide = (legislator.get("id") or {}).get("bioguide")
        member_offices = offices_by_bioguide.get(bioguide) or []
        if member_offices:
            district_lines = district_office_lines(member_offices[0])
            if district_lines:
                entry["districtOffice"] = district_lines
        roster[str(district)] = entry
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

    # If a local legislators-current.json was passed, look for a cached
    # district-offices file next to it so a fully-offline build is possible.
    do_path = None
    if src_path:
        sibling = os.path.join(os.path.dirname(src_path), "legislators-district-offices.json")
        if os.path.exists(sibling):
            do_path = sibling

    legislators = load_source(src_path)
    offices_by_bioguide = load_district_offices(do_path)
    roster = resolve_roster(legislators, offices_by_bioguide)

    if len(roster) < EXPECTED_DISTRICTS:
        print(
            f"WARNING: resolved {len(roster)}/{EXPECTED_DISTRICTS} {STATE} U.S. House "
            "districts — refusing to overwrite the roster with an incomplete "
            "delegation",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "congress-roster.json")
    write_json(out_path, roster)

    with_district = sum(1 for e in roster.values() if e.get("districtOffice"))
    print(
        f"Wrote {out_path} ({len(roster)} districts; {with_district} with a "
        f"district office)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
