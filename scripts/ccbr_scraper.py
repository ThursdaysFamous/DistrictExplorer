#!/usr/bin/env python3
"""
Cook County Board of Review Commissioner Scraper
================================================
Extracts the three elected Commissioners (name + district + on-page contact
info + commissioner-page link) from the Board of Review's own site at
cookcountyboardofreview.com.

Why scrape rather than call an API: the Board of Review's three districts ship
in the app as pre-built PA 102-0012 geometry (data/app/ccbr-districts.json),
but the shapefile carries no officeholder fields and no queryable open dataset
names the commissioners (confirmed 2026-07-20 — the county's electedOfficials
GIS table covers the Board of Commissioners, not the Board of Review). The
commissioners are only published as rendered HTML on the Board's own site.
This scraper is the build-time step that produces a raw JSON, resolved into
data/app/ccbr-roster.json by scripts/build_ccbr_roster.py (same two-stage
pattern as scripts/ccpsa_scraper.py + scripts/build_ccpsa_roster.py).

The site is a plain Drupal build with no Cloudflare JS challenge — a plain
requests client gets the full rendered HTML — so this scraper stays
browserless (requests + BeautifulSoup), matching the ccpsa_scraper.py
template.

Commissioner page URLs are discovered from the site's own "Commissioner Menu"
block rather than hardcoded, so a post-election name/URL change (the paths are
name-derived, e.g. /GeorgeCardenas) can't silently break the scrape: a new
commissioner shows up in the menu with a new path and is followed from there.

District extraction: the three pages word their district inconsistently —
"First District" (ordinal-first), "serves as Commissioner for District 2"
(digit-after), "3rd District" (numeric-ordinal) were all live wordings on
2026-07-20 — so both orderings are matched, words and numerals.

Usage:
    python3 ccbr_scraper.py --out ccbr_commissioners.json

Notes on data honesty (per project conventions):
- If a field can't be found on a page, it is stored as null / empty list,
  never guessed or fabricated. In particular a district email is NOT inferred
  from the other districts' BORDistrict<N>info@ pattern — District 2 published
  no email on 2026-07-20 (contact form only) and its record honestly omits it.
- Every record includes `source_url` and `scraped_at` for traceability.
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE = "https://www.cookcountyboardofreview.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_TIMEOUT = 30
POLITE_DELAY_S = 1.0

WORD_TO_NUM = {
    "first": 1, "second": 2, "third": 3,
    "1st": 1, "2nd": 2, "3rd": 3,
    "one": 1, "two": 2, "three": 3,
}

# Both live wordings, most-specific first: "First District"/"3rd District"
# (ordinal before the noun) and "District 2"/"District Two" (noun first).
DISTRICT_BEFORE = re.compile(
    r"\b(first|second|third|1st|2nd|3rd)\s+district\b", re.IGNORECASE)
DISTRICT_AFTER = re.compile(
    r"\bdistrict\s+(1|2|3|one|two|three)\b", re.IGNORECASE)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\(?\d{3}\)?[ .-]\d{3}[ .-]\d{4}")


def fetch(url, session):
    resp = session.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def discover_commissioners(home_html):
    """[(name, absolute_url)] from the homepage's Commissioner Menu block.

    Keys on the Drupal block id (block-commissionermenu) so nav restyles that
    keep the menu block keep the scrape working; entries whose text doesn't
    contain "Commissioner" are skipped (defensive against menu additions).
    """
    soup = BeautifulSoup(home_html, "html.parser")
    block = soup.find(id=re.compile(r"block-commissionermenu", re.IGNORECASE))
    if block is None:
        # Fallback: any nav link whose text starts with "Commissioner " —
        # weaker, but survives a block-id rename.
        block = soup
    out = []
    seen = set()
    for a in block.find_all("a", href=True):
        text = " ".join(a.get_text(" ", strip=True).split())
        if not re.match(r"commissioner\s+\S", text, re.IGNORECASE):
            continue
        name = re.sub(r"^commissioner\s+", "", text, flags=re.IGNORECASE).strip()
        url = urljoin(BASE, a["href"])
        if not name or url in seen:
            continue
        seen.add(url)
        out.append((name, url))
    return out


def extract_district(page_text):
    m = DISTRICT_BEFORE.search(page_text)
    if m:
        return WORD_TO_NUM.get(m.group(1).lower())
    m = DISTRICT_AFTER.search(page_text)
    if m:
        token = m.group(1).lower()
        return int(token) if token.isdigit() else WORD_TO_NUM.get(token)
    return None


def scrape_commissioner(name, url, session):
    record = {
        "name": name,
        "url": url,
        "district_number": None,
        "emails": [],
        "phones": [],
        "source_url": url,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    html = fetch(url, session)
    soup = BeautifulSoup(html, "html.parser")
    # Contact extraction is scoped to the page's MAIN content region: the
    # sitewide footer carries the Board's main line (312-603-5542) on every
    # page, and attributing it to a commissioner who publishes no number of
    # their own would be a small dishonesty (District 2 published no direct
    # contact as of 2026-07-20 — its record should say so, not borrow the
    # switchboard). Falls back to the whole page if Drupal's <main> vanishes.
    content = soup.find("main") or soup
    emails = []
    for a in content.find_all("a", href=re.compile(r"^mailto:", re.IGNORECASE)):
        emails.append(a["href"].split(":", 1)[1].split("?")[0].strip())
    text = " ".join(content.get_text(" ", strip=True).split())
    emails.extend(EMAIL_RE.findall(text))
    record["emails"] = list(dict.fromkeys(e for e in emails if e))
    record["phones"] = list(dict.fromkeys(PHONE_RE.findall(text)))
    record["district_number"] = extract_district(text)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default="ccbr_commissioners.json")
    args = parser.parse_args()

    session = requests.Session()
    home = fetch(BASE + "/", session)
    commissioners = discover_commissioners(home)
    if not commissioners:
        print("FATAL: no commissioner links found in the Commissioner Menu", file=sys.stderr)
        sys.exit(1)

    records = []
    for name, url in commissioners:
        try:
            records.append(scrape_commissioner(name, url, session))
        except Exception as e:  # noqa: BLE001 — record the failure, never fabricate
            records.append({"name": name, "url": url, "error": str(e)})
        time.sleep(POLITE_DELAY_S)

    with open(args.out, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    ok = [r for r in records if not r.get("error")]
    resolved = [r for r in ok if r.get("district_number")]
    print("scraped %d commissioner pages (%d ok, %d with a district) -> %s"
          % (len(records), len(ok), len(resolved), args.out), file=sys.stderr)


if __name__ == "__main__":
    main()
