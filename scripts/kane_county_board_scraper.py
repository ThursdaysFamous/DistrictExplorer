#!/usr/bin/env python3
"""
Scrape the Kane County Board member roster from the county's own SharePoint
list API.

Stage 1 of the two-stage roster pipeline (the Will/Kendall/McHenry shape);
scripts/build_kane_county_board_roster.py resolves the raw records into
data/app/kane-county-board-members.json, keyed by county-board district
("1".."24") plus a top-level "chair" for the countywide-elected Board Chair
(the DuPage roster shape), which index.html's consolidated county-board
layer joins to the county's own KaneCo_IL_County_Board boundary GIS by
district number (the GIS keeps carrying the sitting member's NAME — this
roster adds party, the official office phone, email, and a profile link).

Source: the directory page at
  https://www2.kanecountyil.gov/pages/countyboard/boardMembers.aspx
is a SharePoint page whose member table is rendered client-side from the
site's own REST API — the page's inline script calls

  GET /_api/web/lists/getbytitle('Board Members')/items?$orderby=District
  Accept: application/json;odata=nometadata

anonymously, and this scraper calls exactly that endpoint (no HTML parsing,
no browser, no bot-management ladder: unlike the Kendall/McHenry sites,
Kane's does not block automated clients — verified 2026-07-23). Fields
used: ID, FullName, District (null for the countywide Chair), Party,
Office/Cell/Home (the first non-empty is the published contact number —
Office is the county's official 630-444-12NN board line), E_x002d_Mail
(SharePoint's encoding of "E-Mail", a mailto: URL), and the Chairman flag.
The Chair's FullName carries a ", Madam Chair"-style suffix that is
stripped (the role is emitted separately); the record's Address (the
Government Center) and ServiceStart/Expires are not collected — the card
convention carries contact, not terms, and members' Address fields are
empty anyway.

Notes on data honesty (per project conventions):
- Values are read verbatim from the county's own list; a missing field is
  stored null, never guessed.
- Every record includes `source_url` (the member's own profile page, built
  from the list ID exactly as the county's directory links do) and
  `scraped_at` for traceability.

Usage:
    python3 kane_county_board_scraper.py [output.json]   # default: stdout
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests

BASE = "https://www2.kanecountyil.gov"
LISTING_PAGE = BASE + "/pages/countyboard/boardMembers.aspx"
API_URL = BASE + "/_api/web/lists/getbytitle('Board%20Members')/items?$orderby=District"
PROFILE_URL = BASE + "/Pages/CountyBoard/BoardMember.aspx?bmID=%d"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json;odata=nometadata",
}

CHAIR_SUFFIX_RE = re.compile(r",\s*(madam\s+)?chair(man|woman)?\s*$", re.IGNORECASE)


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text or None


def fetch_items(retries=3, timeout=30):
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(API_URL, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                items = resp.json().get("value", [])
                if items:
                    return items
                last_err = "empty item list"
            else:
                last_err = "HTTP %d" % resp.status_code
        except (requests.RequestException, ValueError) as e:
            last_err = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError("Failed to fetch %s: %s" % (API_URL, last_err))


def to_record(item):
    raw_name = clean(item.get("FullName"))
    is_chair = bool(item.get("Chairman"))
    name = CHAIR_SUFFIX_RE.sub("", raw_name) if (raw_name and is_chair) else raw_name

    district = item.get("District")
    district = str(int(district)) if isinstance(district, (int, float)) else clean(district)

    phone = clean(item.get("Office")) or clean(item.get("Cell")) or clean(item.get("Home"))

    email = clean(item.get("E_x002d_Mail"))
    if email and email.lower().startswith("mailto:"):
        email = email[len("mailto:"):].strip() or None

    list_id = item.get("ID")
    return {
        "id": list_id,
        "name": name,
        "district": district,
        "role": "Chair" if is_chair else None,
        "party": clean(item.get("Party")),
        "phone": phone,
        "email": email,
        "url": PROFILE_URL % list_id if isinstance(list_id, int) else None,
        "source_url": PROFILE_URL % list_id if isinstance(list_id, int) else LISTING_PAGE,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    ap = argparse.ArgumentParser(description="Scrape the Kane County Board SharePoint list.")
    ap.add_argument("out", nargs="?", default=None, help="output JSON path (default: stdout)")
    args = ap.parse_args()

    records = [to_record(i) for i in fetch_items()]

    payload = json.dumps(records, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload + "\n")
    else:
        print(payload)

    fields = ("district", "party", "phone", "email")
    coverage = "  ".join("%s=%d/%d" % (f, sum(1 for r in records if r.get(f)), len(records))
                         for f in fields)
    chairs = sum(1 for r in records if r.get("role") == "Chair")
    print("Scraped %d members (%d chair record)" % (len(records), chairs), file=sys.stderr)
    print("field coverage: %s" % coverage, file=sys.stderr)


if __name__ == "__main__":
    main()
