#!/usr/bin/env python3
"""
Resolve scripts/cpd_district_scraper.py's raw output into one record per
district, then rewrite the CPD_DISTRICT_INFO object literal embedded in
index.html.

Why rewrite index.html instead of writing a separate data file: this app is
commonly opened directly via file://, where a relative fetch() of a sibling
JSON file is blocked by the browser's same-origin policy. Every non-CORS
dataset in this app is embedded inline for that reason (see index.html's
"embedded inline (not fetched)" comments) — this script keeps that pattern
while letting the roster itself be regenerated instead of hand-typed, same
as scripts/build_il_roster.py does for the IL Senate/House rosters.

Usage:
    python3 build_cpd_roster.py cpd_district_info.json ../index.html
"""

import json
import sys

# CPD currently operates 22 police districts (some numbers were retired after
# past mergers, e.g. 13 and 21). Refuse to overwrite index.html if a scrape
# resolves suspiciously few districts, rather than silently wiping good data
# with a broken/partial run — same safety net as build_il_roster.py's 59/118
# senate/house guard.
MIN_DISTRICTS = 20


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


def js_string(value):
    if value is None:
        return "null"
    out = json.dumps(value, ensure_ascii=False)
    # This literal lands inside index.html's inline <script> block, where the
    # HTML parser would end the script at any "</script" regardless of JS
    # string context — and scraped commander bios could in principle contain
    # one. "<\/" is identical to "</" to the JS engine but invisible to the
    # HTML parser. U+2028/U+2029 are legal in JSON but line terminators in
    # older JS, so escape those too. (Mirrors build_il_roster.py's js_string,
    # added there after a real injection bug — see docs/BUILD_PLAYBOOK_1.md.)
    out = out.replace("</", "<\\/")
    out = out.replace(" ", "\u2028").replace(" ", "\u2029")
    return out


def js_object_literal(roster):
    lines = ["  var CPD_DISTRICT_INFO = {"]
    for district in sorted(roster.keys(), key=int):
        info = roster[district]
        parts = [
            "commanderName: " + js_string(info["commanderName"]),
            "commanderStatus: " + js_string(info["commanderStatus"]),
            "commanderBio: " + js_string(info["commanderBio"]),
            "mainPhone: " + js_string(info["mainPhone"]),
            "capsPhone: " + js_string(info["capsPhone"]),
            "capsEmail: " + js_string(info["capsEmail"]),
            "stationAddress: " + js_string(info["stationAddress"]),
            "districtMapUrl: " + js_string(info["districtMapUrl"]),
            "sourceUrl: " + js_string(info["sourceUrl"]),
        ]
        lines.append('    "' + district + '": { ' + ", ".join(parts) + " },")
    lines.append("  };")
    return "\n".join(lines)


def replace_block(html, new_literal):
    import re

    pattern = re.compile(r"  var CPD_DISTRICT_INFO = \{.*?\n  \};", re.DOTALL)
    if not pattern.search(html):
        raise RuntimeError("could not find existing CPD_DISTRICT_INFO block in index.html")
    return pattern.sub(lambda _m: new_literal, html, count=1)


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} <raw-scraper-output.json> <index.html>", file=sys.stderr)
        sys.exit(1)

    raw_path, html_path = sys.argv[1], sys.argv[2]

    with open(raw_path) as f:
        records = json.load(f)

    roster = resolve_roster(records)

    if len(roster) < MIN_DISTRICTS:
        print(
            f"WARNING: resolved only {len(roster)}/{MIN_DISTRICTS}+ expected districts — "
            "refusing to overwrite index.html with an incomplete roster",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(html_path) as f:
        html = f.read()

    html = replace_block(html, js_object_literal(roster))

    with open(html_path, "w") as f:
        f.write(html)

    print(f"Updated {html_path}: {len(roster)} districts", file=sys.stderr)


if __name__ == "__main__":
    main()
