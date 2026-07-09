#!/usr/bin/env python3
"""
CPD District Commander/Contact Scraper
=======================================
Extracts commander name + status, CAPS unit phone/email, station address,
neighborhood list, and district-map link for each Chicago Police Department
police district, from CPD's own per-district pages.

Why scrape rather than call an API: none of this data (commander name, CAPS
contact, station address) exists in any queryable open dataset (confirmed —
see docs/BUILD_PLAYBOOK_1.md §2c). It's only available as rendered HTML on
CPD's per-district pages, which send no Access-Control-Allow-Origin header,
so it can't be fetched client-side by the browser app either. This scraper
is the operator-run, build-time step that produces a static JSON, later
embedded into index.html by scripts/build_cpd_roster.py (same pattern as
scripts/ilga_scraper.py + scripts/build_il_roster.py for the IL rosters).

District slugs are discovered from CPD's own district-finder page rather
than hardcoded, since districts have been merged/renumbered before and a
stale hardcoded list would silently drop or mis-map districts.

Usage:
    python3 cpd_district_scraper.py --out cpd_district_info.json

Notes on data honesty (per project conventions):
- If a field can't be found on a page, it is stored as null / empty list,
  never guessed or fabricated.
- Every record includes `source_url` and `scraped_at` for traceability.
- Markup on these pages is plain WordPress/UiKit blocks with no stable data
  attributes or consistent CSS classes, so parsing here is heuristic (text/
  heading search, tel:/mailto: link scan) rather than fixed selectors.
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

BASE = "https://www.chicagopolice.org"
FINDER_PATH = "/police-districts/find-your-district/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DISTRICT_LINK_RE = re.compile(r"/(\d{1,2}(?:st|nd|rd|th))-district-([a-z0-9-]+)/", re.IGNORECASE)
CAPS_EMAIL_RE = re.compile(r"caps\.\d+district@chicagopolice\.org", re.IGNORECASE)
COMMANDER_HEADING_RE = re.compile(r"meet your (acting )?commander", re.IGNORECASE)
ADDRESS_RE = re.compile(r"[^\n,]+,\s*Chicago,\s*IL\s*\d{5}", re.IGNORECASE)


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


def get_district_pages(session):
    """Return sorted list of unique (district_number, ordinal, slug, url) tuples."""
    html = fetch(BASE + FINDER_PATH, session)
    seen = {}
    for match in DISTRICT_LINK_RE.finditer(html):
        ordinal, slug = match.group(1), match.group(2)
        number = int(re.match(r"\d+", ordinal).group(0))
        if number in seen:
            continue
        path = f"/{ordinal}-district-{slug}/"
        seen[number] = (number, ordinal, slug, urljoin(BASE, path))
    return [seen[n] for n in sorted(seen)]


def find_tel_links(soup):
    """Return [(phone, elem)] for every tel: link on the page."""
    out = []
    for a in soup.select('a[href^="tel:"]'):
        phone = clean(a.get_text()) or clean(a["href"].replace("tel:", ""))
        out.append((phone, a))
    return out


def nearby_text_mentions_caps(elem):
    """True if CAPS is mentioned in this element's parent or nearby siblings."""
    for ancestor in (elem, elem.parent, getattr(elem.parent, "parent", None)):
        if ancestor is not None and re.search(r"\bCAPS\b", ancestor.get_text(), re.IGNORECASE):
            return True
    return False


def parse_phones(soup):
    """Split tel: links into (main_phone, caps_phone) by nearby CAPS mention."""
    main_phone, caps_phone = None, None
    for phone, elem in find_tel_links(soup):
        if not phone:
            continue
        if nearby_text_mentions_caps(elem) and caps_phone is None:
            caps_phone = phone
        elif main_phone is None:
            main_phone = phone
    return main_phone, caps_phone


def parse_caps_email(soup):
    for a in soup.select('a[href^="mailto:"]'):
        addr = a["href"].replace("mailto:", "").strip()
        if CAPS_EMAIL_RE.match(addr):
            return addr
    return None


def parse_station_address(soup):
    text = soup.get_text("\n")
    match = ADDRESS_RE.search(text)
    return clean(match.group(0)) if match else None


def parse_commander(soup):
    """Return (name, status) by finding the 'Meet your (acting) commander'
    heading and taking the next short text block as the name."""
    heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b", "p"]):
        if COMMANDER_HEADING_RE.search(tag.get_text()):
            heading = tag
            break
    if heading is None:
        return None, None, None

    status = "acting_commander" if re.search(r"\bacting\b", heading.get_text(), re.IGNORECASE) else "commander"

    name, bio = None, None
    for elem in heading.find_all_next(["h1", "h2", "h3", "h4", "h5", "strong", "b", "p"]):
        text = clean(elem.get_text())
        if not text or COMMANDER_HEADING_RE.search(text):
            continue
        if name is None:
            # A name is short and has no sentence-ending punctuation; a bio
            # paragraph is long prose. If the first block already reads like
            # prose, there's no separate name element to find — leave name
            # null rather than guess which words are the name.
            if len(text) <= 60 and not re.search(r"[.!?]\s", text):
                name = text
                continue
            else:
                break
        else:
            bio = text
            break
    return name, status, bio


def parse_neighborhoods(soup):
    heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5"]):
        if re.search(r"neighborhood", tag.get_text(), re.IGNORECASE):
            heading = tag
            break
    if heading is None:
        return []
    list_tag = heading.find_next(["ul", "ol"])
    if not list_tag:
        return []
    return [clean(li.get_text()) for li in list_tag.find_all("li") if clean(li.get_text())]


def parse_district_map_url(soup, source_url):
    for a in soup.find_all("a"):
        if re.search(r"view district map", a.get_text(), re.IGNORECASE):
            href = a.get("href")
            return urljoin(source_url, href) if href else None
    return None


def parse_district_page(html, district_number, source_url):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main") or soup

    main_phone, caps_phone = parse_phones(main)
    commander_name, commander_status, commander_bio = parse_commander(main)

    return {
        "district_number": district_number,
        "source_url": source_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "main_phone": main_phone,
        "caps_phone": caps_phone,
        "caps_email": parse_caps_email(main),
        "station_address": parse_station_address(main),
        "commander_name": commander_name,
        "commander_status": commander_status,
        "commander_bio": commander_bio,
        "neighborhoods": parse_neighborhoods(main),
        "district_map_url": parse_district_map_url(main, source_url),
    }


def scrape_all(session, limit=None, delay=0.5, verbose=True):
    pages = get_district_pages(session)
    if limit:
        pages = pages[:limit]
    results = []
    for i, (number, ordinal, slug, url) in enumerate(pages, 1):
        if verbose:
            print(f"[{i}/{len(pages)}] fetching district {number} ({url})", file=sys.stderr)
        try:
            html = fetch(url, session)
            record = parse_district_page(html, number, url)
        except Exception as e:
            record = {"district_number": number, "source_url": url, "error": str(e)}
        results.append(record)
        time.sleep(delay)
    return results


def main():
    ap = argparse.ArgumentParser(description="Scrape CPD per-district commander/contact pages.")
    ap.add_argument("--out", default="cpd_district_info.json")
    ap.add_argument("--limit", type=int, default=None, help="Limit number of districts (for testing)")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = ap.parse_args()

    session = requests.Session()
    results = scrape_all(session, limit=args.limit, delay=args.delay)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Wrote {len(results)} records to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
