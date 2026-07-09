#!/usr/bin/env python3
"""
CCPSA District Council Councilor Scraper
========================================
Extracts the elected District Councilors (name + role on the council + member
profile link) for each of Chicago's 22 Police District Councils, from the
Community Commission for Public Safety and Accountability's own per-district
pages at ccpsa.chicago.gov.

Why scrape rather than call an API: the July 2021 ordinance that created the
CCPSA also created 22 District Councils — one per Chicago Police District — each
with three Councilors elected in the regular municipal elections. Those elected
Councilor names exist in no queryable open dataset (confirmed 2026-07-09 by an
initial dataset search); they are only published as rendered HTML on the CCPSA
site's per-district-council pages. This scraper is the operator-run, build-time
step that produces a static JSON, later written to
data/app/ccpsa-district-councils.json by scripts/build_ccpsa_roster.py (same
two-stage pattern as scripts/ilga_scraper.py + scripts/build_il_roster.py).

Unlike CPD's site (see scripts/cpd_district_scraper.py), ccpsa.chicago.gov is
not fronted by a Cloudflare JS challenge — a plain requests client gets the full
rendered HTML — so this scraper stays browserless (requests + BeautifulSoup),
matching the simpler ilga_scraper.py template.

District-council page URLs are discovered from the site's own
district-council-sitemap.xml rather than hardcoded, so a future re-numbering
(districts 13 and 21 were retired before, which is why only 22 councils exist:
1-12, 14-20, 22, 24, 25) can't silently drop or mis-map a council.

Usage:
    python3 ccpsa_scraper.py --out ccpsa_district_councils.json

Notes on data honesty (per project conventions):
- If a field can't be found on a page, it is stored as null / empty list,
  never guessed or fabricated.
- Every record includes `source_url` and `scraped_at` for traceability.
- The council markup is a stable WordPress template (`.member-column` cards with
  an `h3.title` name + `p.position` role + `a.see-more` profile link), so parsing
  keys on those classes; it degrades to an empty member list rather than crashing
  if the template changes.
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

BASE = "https://ccpsa.chicago.gov"
DC_SITEMAP = BASE + "/district-council-sitemap.xml"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# CCPSA runs 22 District Councils, one per active police district. (13 and 21
# are retired district numbers, so there is no 13th/21st council.)
EXPECTED_COUNCILS = 22

# /district-council/{ordinal}-district-council/ — group 1 is the leading integer.
DC_URL_RE = re.compile(r"/district-council/(\d{1,2})(?:st|nd|rd|th)-district-council/?", re.IGNORECASE)


def fetch(url, session, retries=3, timeout=20):
    last_err = None
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 200:
                return resp.text
            last_err = f"HTTP {resp.status_code}"
        except requests.RequestException as e:
            last_err = str(e)
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def get_council_pages(session):
    """Return sorted list of unique (district_number, url) tuples for every
    District Council page, discovered from the site's own sitemap."""
    seen = {}
    try:
        xml = fetch(DC_SITEMAP, session)
    except Exception as e:
        print(f"district-council sitemap fetch failed: {e}", file=sys.stderr)
        return []
    for url in re.findall(r"https?://[^\s<>\"']+/district-council/[^\s<>\"']+", xml):
        m = DC_URL_RE.search(url)
        if not m:
            continue
        number = int(m.group(1))
        if number in seen:
            continue
        # Normalize to the bare canonical page URL (drop any trailing junk).
        seen[number] = (number, urljoin(BASE, m.group(0)))
    if len(seen) < EXPECTED_COUNCILS:
        print(
            f"WARNING: discovered {len(seen)}/{EXPECTED_COUNCILS} district councils",
            file=sys.stderr,
        )
    return [seen[n] for n in sorted(seen)]


def parse_members(soup):
    """Return [{name, role, profile_url}] for each Councilor card on the page.

    The council page renders each Councilor as a `.member-column` card holding an
    `h3.title` (name), a `p.position` (role on the council, e.g. "Chair",
    "Nominating Committee", "Community Engagement"), and an `a.see-more` link to
    the member's profile. A card with no name is skipped rather than emitted with
    a null name — an unnamed Councilor is meaningless."""
    members = []
    # Scope to the Members block so unrelated cards elsewhere on the page can't
    # leak in; fall back to the whole document if the wrapper markup changes.
    scope = soup.select_one(".member-container") or soup
    for card in scope.select(".member-column"):
        name_el = card.select_one("h3.title") or card.find(["h3", "h4"])
        name = clean(name_el.get_text()) if name_el else None
        if not name:
            continue
        role_el = card.select_one("p.position")
        role = clean(role_el.get_text()) if role_el else None
        link_el = card.select_one("a.see-more") or card.find("a", href=True)
        profile_url = urljoin(BASE, link_el["href"]) if link_el and link_el.get("href") else None
        members.append({"name": name, "role": role, "profile_url": profile_url})
    return members


def parse_council_page(html, district_number, source_url):
    soup = BeautifulSoup(html, "html.parser")
    return {
        "district_number": district_number,
        "source_url": source_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "members": parse_members(soup),
    }


def scrape_all(session, pages=None, limit=None, delay=0.5, verbose=True):
    if pages is None:
        pages = get_council_pages(session)
    if limit:
        pages = pages[:limit]
    results = []
    for i, (number, url) in enumerate(pages, 1):
        if verbose:
            print(f"[{i}/{len(pages)}] fetching district {number} ({url})", file=sys.stderr)
        try:
            html = fetch(url, session)
            record = parse_council_page(html, number, url)
        except Exception as e:
            record = {"district_number": number, "source_url": url, "error": str(e)}
        results.append(record)
        time.sleep(delay)
    return results


def main():
    ap = argparse.ArgumentParser(description="Scrape CCPSA per-district-council Councilor rosters.")
    ap.add_argument("--out", default="ccpsa_district_councils.json")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of councils (for testing)")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = ap.parse_args()

    session = requests.Session()
    results = scrape_all(session, limit=args.limit, delay=args.delay)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    # Coverage summary — makes template drift visible at a glance (e.g.
    # "members=0/22 districts populated" means the pages fetched but the card
    # parser found nothing), so a red build points straight at the break.
    ok = [r for r in results if not r.get("error")]
    total_members = sum(len(r.get("members") or []) for r in ok)
    populated = sum(1 for r in ok if r.get("members"))
    print(f"Wrote {len(results)} records to {args.out} ({len(ok)} without error)", file=sys.stderr)
    print(
        f"coverage: {populated}/{len(ok)} councils have >=1 member, "
        f"{total_members} councilors total",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
