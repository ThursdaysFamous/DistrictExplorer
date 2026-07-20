#!/usr/bin/env python3
"""
Illinois County Clerk Scraper (ISBE election-authority directory)
=================================================================
Extracts every Illinois county clerk (name + office address + phone + email)
from the State Board of Elections' own election-authority directory at
elections.il.gov/ElectionOperations/ElectionAuthorities.aspx.

Why this source: the county card is the app's statewide TIGERweb county
layer, so surfacing the clerk needs an authoritative directory covering all
102 counties at once — and ISBE maintains exactly that, because every county
clerk is an election authority under 10 ILCS 5. The page is an ASP.NET
postback form whose county dropdown includes an "All Election Authorities"
option (-1): one GET for the form tokens + one POST returns the complete
directory as a single GridView table (Jurisdiction | Name | Title | Email |
Address | Phone | Fax), 108 rows = 102 county clerks + the municipal boards
of election commissioners (Jurisdiction "CITY OF …"), which the builder
filters out.

Emails are Cloudflare-obfuscated (`data-cfemail`) and decoded with the
standard XOR scheme (first byte is the key).

This is the build-time half of the usual two-stage roster pattern; the raw
output is resolved into data/app/il-county-clerks.json by
scripts/build_county_clerk_roster.py.

Usage:
    python3 il_county_clerk_scraper.py --out il_county_clerks.json

Notes on data honesty (per project conventions):
- Fields that can't be parsed are stored as null, never guessed.
- Every record includes `source_url` and `scraped_at` for traceability.
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

URL = "https://www.elections.il.gov/ElectionOperations/ElectionAuthorities.aspx"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}
REQUEST_TIMEOUT = 40


def decode_cfemail(enc):
    """Cloudflare email obfuscation: hex string, first byte XOR key."""
    try:
        key = int(enc[:2], 16)
        return "".join(chr(int(enc[i:i + 2], 16) ^ key) for i in range(2, len(enc), 2))
    except (ValueError, IndexError):
        return None


def cell_text(td):
    return " ".join(td.get_text(" ", strip=True).split()) or None


def cell_email(td):
    a = td.find(attrs={"data-cfemail": True})
    if a is not None:
        return decode_cfemail(a["data-cfemail"])
    m = td.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
    if m is not None:
        return m["href"].split(":", 1)[1].split("?")[0].strip() or None
    return cell_text(td)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", default="il_county_clerks.json")
    args = parser.parse_args()

    session = requests.Session()
    form = session.get(URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
    form.raise_for_status()
    soup = BeautifulSoup(form.text, "html.parser")

    def token(name):
        el = soup.find(id=name)
        if el is None or not el.get("value"):
            print("FATAL: ASP.NET form token %s missing — page structure changed" % name,
                  file=sys.stderr)
            sys.exit(1)
        return el["value"]

    resp = session.post(URL, headers=HEADERS, timeout=REQUEST_TIMEOUT, data={
        "__VIEWSTATE": token("__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": token("__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": token("__EVENTVALIDATION"),
        "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlCounty",
        "ctl00$ContentPlaceHolder1$ddlCounty": "-1",  # All Election Authorities
    })
    resp.raise_for_status()

    table = BeautifulSoup(resp.text, "html.parser").find(id="ContentPlaceHolder1_gvAllJurisdictions")
    if table is None:
        print("FATAL: all-jurisdictions table not found — page structure changed", file=sys.stderr)
        sys.exit(1)

    scraped_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    records = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 7:
            continue  # header row (th) or malformed
        records.append({
            "jurisdiction": cell_text(tds[0]),
            "name": cell_text(tds[1]),
            "title": cell_text(tds[2]),
            "email": cell_email(tds[3]),
            "address": cell_text(tds[4]),
            "phone": cell_text(tds[5]),
            "fax": cell_text(tds[6]),
            "source_url": URL,
            "scraped_at": scraped_at,
        })

    with open(args.out, "w") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    n_clerk = sum(1 for r in records if r["title"] and "COUNTY CLERK" in r["title"].upper())
    print("scraped %d election authorities (%d county clerks) -> %s"
          % (len(records), n_clerk, args.out), file=sys.stderr)


if __name__ == "__main__":
    main()
