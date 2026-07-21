#!/usr/bin/env python3
"""
Scrape the DuPage County Board members directory into raw roster records.

Stage 1 of the two-stage pipeline (scripts/build_dupage_county_board_roster.py
is stage 2), mirroring the Will County board scraper. Unlike Will's, DuPage's
directory (dupagecounty.gov, a Revize CMS "business directory") is plain
server-rendered HTML with no JS challenge, so requests + BeautifulSoup suffice.

Each member is a <div class="rz-business-block"> carrying an <h2> name, an
inline "District N" field, term dates, a member-specific tel: phone and mailto:
email, and a "More about <name>" link to the member's detail page. Everything
the card needs is on this one list page, so a single fetch suffices. The Board
Chair is elected countywide (no district) and is emitted with district=null,
role="Chair".

Names, phones, and emails are read verbatim from the county's own directory —
never guessed. The per-member tel: link is the member's own published number
(distinct from the general 630-407-6500 board-office line).

Usage:
    python3 dupage_county_board_scraper.py [output.json]   # default: stdout
"""

import json
import re
import sys

import requests
from bs4 import BeautifulSoup

BASE = "https://www.dupagecounty.gov"
LIST_URL = BASE + "/government/county_board/county_board_members/"
UA = {"User-Agent": "Mozilla/5.0 (compatible; districtexplorer-roster/1.0)"}
# mailto: local-parts that are site chrome / role inboxes, not a member address.
BOILERPLATE_EMAIL = ("noreply", "webpageupdate", "bootstrap", "webmaster", "info@")


def fetch(url):
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    return r.text


def abs_url(href):
    href = (href or "").strip()
    if not href:
        return None
    if href.startswith("http"):
        return href
    return BASE + "/" + href.lstrip("/")


def format_phone(raw):
    """Normalize a tel: value to XXX-XXX-XXXX; leave anything unexpected as-is."""
    d = re.sub(r"\D", "", raw or "")
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    if len(d) == 10:
        return "%s-%s-%s" % (d[:3], d[3:6], d[6:])
    return (raw or "").strip() or None


def block_email(block):
    """The member's own @dupagecounty.gov address from a mailto: link, if any."""
    for a in block.find_all("a", href=True):
        h = a["href"].strip()
        if h.lower().startswith("mailto:"):
            addr = h[7:].split("?")[0].strip()
            if addr.lower().endswith("@dupagecounty.gov") and not addr.lower().startswith(BOILERPLATE_EMAIL):
                return addr
    return None


def block_phone(block):
    """The member's own published number from the block's tel: link."""
    for a in block.find_all("a", href=True):
        h = a["href"].strip()
        if h.lower().startswith("tel:"):
            return format_phone(h[4:])
    return None


def scrape():
    soup = BeautifulSoup(fetch(LIST_URL), "html.parser")
    blocks = soup.find_all("div", class_="rz-business-block")
    records = []
    for b in blocks:
        h2 = b.find("h2")
        if not h2:
            continue
        raw_name = h2.get_text(" ", strip=True)
        is_chair = bool(re.search(r"chair", raw_name, re.I))
        name = re.sub(r"\s*[–—-]\s*chair\s*$", "", raw_name, flags=re.I).strip()
        if not name:
            continue
        text = b.get_text(" ", strip=True)
        dm = re.search(r"District\s+([1-6])\b", text)
        district = int(dm.group(1)) if (dm and not is_chair) else None
        link = b.find("a", href=re.compile(r"/[A-Za-z]+\.php", re.I))
        rec = {"name": name, "district": district,
               "role": "Chair" if is_chair else "Member",
               "url": abs_url(link["href"]) if link else None}
        phone = block_phone(b)
        email = block_email(b)
        if phone:
            rec["phone"] = phone
        if email:
            rec["email"] = email
        records.append(rec)
    return records


def main():
    records = scrape()
    n_dist = sum(1 for r in records if r["district"] is not None)
    n_chair = sum(1 for r in records if r["role"] == "Chair")
    n_email = sum(1 for r in records if r.get("email"))
    n_phone = sum(1 for r in records if r.get("phone"))
    print("scraped %d records (%d district members, %d chair, %d phones, %d emails)"
          % (len(records), n_dist, n_chair, n_phone, n_email), file=sys.stderr)
    out = json.dumps(records, ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) >= 2:
        with open(sys.argv[1], "w") as f:
            f.write(out)
        print("wrote %s" % sys.argv[1], file=sys.stderr)
    else:
        sys.stdout.write(out)


if __name__ == "__main__":
    main()
