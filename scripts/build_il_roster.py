#!/usr/bin/env python3
"""
Resolve scripts/ilga_scraper.py's raw output into the current officeholder
per district, then rewrite the IL_SENATE_MEMBERS / IL_HOUSE_MEMBERS object
literals embedded in index.html.

Why rewrite index.html instead of writing a separate data file: this app is
commonly opened directly via file://, where a relative fetch() of a sibling
JSON file is blocked by the browser's same-origin policy. Every non-CORS
dataset in this app is embedded inline for that reason (see index.html's
"embedded inline (not fetched)" comments) — this script keeps that pattern
while letting the roster itself be regenerated instead of hand-typed.

Usage:
    python3 build_il_roster.py ilga_network.json ../index.html
"""

import json
import re
import sys

PARTY_NAMES = {"D": "Democratic", "R": "Republican", "I": "Independent"}

DISTRICT_RE = re.compile(r"^\s*(\d+)")


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


def js_string(value):
    return json.dumps(value, ensure_ascii=False)


def js_object_literal(roster, var_name):
    lines = ["  var " + var_name + " = {"]
    for district in sorted(roster.keys(), key=int):
        member = roster[district]
        parts = ["name: " + js_string(member["name"]), "party: " + js_string(member["party"])]
        parts.append("springfieldOffice: " + js_string(member["springfieldOffice"]))
        parts.append("districtOffice: " + js_string(member["districtOffice"]))
        parts.append("url: " + js_string(member["url"]))
        lines.append('    "' + district + '": { ' + ", ".join(parts) + " },")
    lines.append("  };")
    return "\n".join(lines)


def replace_block(html, var_name, new_literal):
    pattern = re.compile(r"  var " + re.escape(var_name) + r" = \{.*?\n  \};", re.DOTALL)
    if not pattern.search(html):
        raise RuntimeError(f"could not find existing {var_name} block in index.html")
    return pattern.sub(lambda _m: new_literal, html, count=1)


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> <index.html>", file=sys.stderr)
        sys.exit(1)

    raw_path, html_path = sys.argv[1], sys.argv[2]

    with open(raw_path) as f:
        records = json.load(f)

    senate_roster = resolve_roster(records, "senate")
    house_roster = resolve_roster(records, "house")

    if len(senate_roster) < 59 or len(house_roster) < 118:
        print(
            f"WARNING: resolved {len(senate_roster)}/59 senate and "
            f"{len(house_roster)}/118 house districts — refusing to overwrite "
            "index.html with an incomplete roster",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(html_path) as f:
        html = f.read()

    html = replace_block(html, "IL_SENATE_MEMBERS", js_object_literal(senate_roster, "IL_SENATE_MEMBERS"))
    html = replace_block(html, "IL_HOUSE_MEMBERS", js_object_literal(house_roster, "IL_HOUSE_MEMBERS"))

    with open(html_path, "w") as f:
        f.write(html)

    print(f"Updated {html_path}: {len(senate_roster)} senate, {len(house_roster)} house districts", file=sys.stderr)


if __name__ == "__main__":
    main()
