#!/usr/bin/env python3
"""
ILGA Network Connections Scraper
=================================
Extracts "network connection" data for Illinois General Assembly members
(Senate + House): committee memberships (with chair info), cross-chamber
associated legislator links, office/contact info, and basic bio metadata.

Designed to be repeatable across the full roster of both chambers so it
can back a member-network API (e.g. for District Explorer).

Usage:
    python3 ilga_scraper.py --chamber senate --out senate_network.json
    python3 ilga_scraper.py --chamber house  --out house_network.json
    python3 ilga_scraper.py --chamber both   --out ilga_network.json

Notes on data honesty (per project conventions):
- If a field can't be found on a page, it is stored as null / empty list,
  never guessed or fabricated.
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

BASE = "https://www.ilga.gov"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CHAMBERS = {
    "senate": {"list_path": "/Senate/Members", "detail_prefix": "/Senate/Members/Details/"},
    "house": {"list_path": "/House/Members", "detail_prefix": "/House/Members/Details/"},
}


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


def get_roster_ids(chamber, session):
    """Return sorted list of unique member IDs listed on the roster page."""
    cfg = CHAMBERS[chamber]
    html = fetch(BASE + cfg["list_path"], session)
    ids = sorted(set(re.findall(cfg["detail_prefix"].lstrip("/") + r"(\d+)", html)))
    return ids


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def parse_office_block(block_div):
    """Turn a Springfield/District office <div> into structured lines."""
    if block_div is None:
        return None
    # Replace <br> with newlines before extracting text
    for br in block_div.find_all("br"):
        br.replace_with("\n")
    raw = block_div.get_text()
    lines = [clean(l) for l in raw.split("\n")]
    lines = [l for l in lines if l]
    return lines or None


def parse_member_detail(html, member_id, chamber, source_url):
    soup = BeautifulSoup(html, "html.parser")
    record = {
        "member_id": member_id,
        "chamber": chamber,
        "source_url": source_url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "name": None,
        "party": None,
        "role": None,
        "term": None,
        "district": None,
        "photo_url": None,
        "springfield_office": None,
        "district_office": None,
        "other_contact_info": None,
        "biography": None,
        "associated_legislators": [],  # cross-chamber links
        "committees": [],  # [{name, code, url, chair_name, chair_url, chair_party}]
        "committees_note": None,  # e.g. "Committees are currently not available." (site-reported gap)
    }

    # --- Header: "Name (Party)  - 104th General Assembly" ---
    # Scope to the "inner-page" section to avoid picking up nav/breadcrumb h2s.
    inner = soup.select_one("section.inner-page") or soup
    h2 = inner.find("h2")
    if h2:
        header_text = clean(h2.get_text())
        m = re.match(r"^(.*?)\s*\((\w)\)\s*-\s*(.*)$", header_text or "")
        if m:
            record["name"] = m.group(1).strip()
            record["party"] = m.group(2).strip()
            record["general_assembly"] = m.group(3).strip()
        else:
            record["name"] = header_text

    # --- Photo card: role / term / district ---
    photo_col = soup.select_one(".member-photo-col")
    if photo_col:
        img = photo_col.find("img")
        if img and img.get("src"):
            record["photo_url"] = img["src"]
        muted_ps = photo_col.select(".text-muted")
        muted_vals = [clean(p.get_text()) for p in muted_ps]
        muted_vals = [v for v in muted_vals if v]
        # Expected order: Senator/Representative, term range, district
        if len(muted_vals) >= 1:
            record["role"] = muted_vals[0]
        if len(muted_vals) >= 2:
            record["term"] = muted_vals[1]
        if len(muted_vals) >= 3:
            record["district"] = muted_vals[2]

    # --- Member Details card: Springfield/District/Other offices ---
    info_col = soup.select_one(".member-info-col")
    if info_col:
        rows = info_col.select(".row")
        for row in rows:
            label_div = row.select_one(".fw-bold")
            if not label_div:
                continue
            label = clean(label_div.get_text())
            value_div = label_div.find_next_sibling("div")
            if label == "Springfield Office:":
                record["springfield_office"] = parse_office_block(value_div)
            elif label == "District Office:":
                record["district_office"] = parse_office_block(value_div)
            elif label == "Other Contact Info:":
                record["other_contact_info"] = parse_office_block(value_div)

        # Biography
        bio_header = info_col.find("h3", string=re.compile("Biography"))
        if bio_header:
            bio_p = bio_header.find_next("p")
            if bio_p:
                record["biography"] = clean(bio_p.get_text())

        # Associated Representatives / Associated Senator
        assoc_header = info_col.find(
            "h3", string=re.compile(r"Associated (Representatives|Senator)")
        )
        if assoc_header:
            container = assoc_header.find_next("p")
            if container:
                for a in container.find_all("a"):
                    record["associated_legislators"].append(
                        {
                            "name": clean(a.get_text()),
                            "url": urljoin(source_url, a["href"]) if a.get("href") else None,
                        }
                    )

    # --- Committees table (desktop version) ---
    committees_pane = soup.select_one("#pane-Committees")
    if committees_pane:
        table = committees_pane.find("table")
        if table:
            body = table.find("tbody")
            if body:
                for tr in body.find_all("tr"):
                    cells = tr.find_all(["th", "td"])
                    if len(cells) == 1:
                        # e.g. "Committees are currently not available."
                        record["committees_note"] = clean(cells[0].get_text())
                        continue
                    if len(cells) < 3:
                        continue
                    name_link = cells[0].find("a")
                    code = clean(cells[1].get_text())
                    chair_link = cells[2].find("a")
                    chair_party_match = re.search(r"\(([A-Z])\)", cells[2].get_text())
                    committee = {
                        "name": clean(name_link.get_text()) if name_link else clean(cells[0].get_text()),
                        "code": code,
                        "url": urljoin(source_url, name_link["href"])
                        if name_link and name_link.get("href")
                        else None,
                        "chair_name": clean(chair_link.get_text()) if chair_link else None,
                        "chair_url": urljoin(source_url, chair_link["href"])
                        if chair_link and chair_link.get("href")
                        else None,
                        "chair_party": chair_party_match.group(1) if chair_party_match else None,
                    }
                    record["committees"].append(committee)

    return record


def scrape_chamber(chamber, session, limit=None, delay=0.5, verbose=True):
    cfg = CHAMBERS[chamber]
    ids = get_roster_ids(chamber, session)
    if limit:
        ids = ids[:limit]
    results = []
    for i, member_id in enumerate(ids, 1):
        url = f"{BASE}{cfg['detail_prefix']}{member_id}"
        if verbose:
            print(f"[{chamber}] {i}/{len(ids)} fetching {url}", file=sys.stderr)
        try:
            html = fetch(url, session)
            record = parse_member_detail(html, member_id, chamber, url)
            results.append(record)
        except Exception as e:
            results.append(
                {
                    "member_id": member_id,
                    "chamber": chamber,
                    "source_url": url,
                    "error": str(e),
                }
            )
        time.sleep(delay)
    return results


def main():
    ap = argparse.ArgumentParser(description="Scrape ILGA member network connections.")
    ap.add_argument("--chamber", choices=["senate", "house", "both"], default="both")
    ap.add_argument("--out", default="ilga_network.json")
    ap.add_argument("--limit", type=int, default=None, help="Limit members per chamber (for testing)")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = ap.parse_args()

    session = requests.Session()
    all_results = []
    chambers = ["senate", "house"] if args.chamber == "both" else [args.chamber]
    for chamber in chambers:
        all_results.extend(scrape_chamber(chamber, session, limit=args.limit, delay=args.delay))

    with open(args.out, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"Wrote {len(all_results)} records to {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
