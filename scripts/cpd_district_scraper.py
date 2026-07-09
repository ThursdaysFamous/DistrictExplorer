#!/usr/bin/env python3
"""
CPD District Commander/Contact Scraper
=======================================
Extracts commander name + status, CAPS unit phone/email, station address,
neighborhood list, and district-map link for each Chicago Police Department
police district, from CPD's own per-district pages.

Why scrape rather than call an API: the commander name/status/bio and the CAPS
unit phone/email exist in no queryable open dataset (confirmed — see
docs/BUILD_PLAYBOOK_1.md §2c, re-confirmed 2026-07-09 by sweeping CPD's own
ArcGIS org, which carries only station address/phone + boundaries). They are
only available as rendered HTML on CPD's per-district pages, which send no
Access-Control-Allow-Origin header, so they can't be fetched client-side by the
browser app either. This scraper is the operator-run, build-time step that
produces a static JSON, later written to data/app/cpd-district-info.json by
scripts/build_cpd_roster.py (same pattern as scripts/ilga_scraper.py +
scripts/build_il_roster.py for the IL rosters).

Fetch engines (`--engine`): CPD fronts these pages with Cloudflare's *managed*
(JavaScript) challenge, which returns HTTP 403 to a plain `requests` client that
can't execute the challenge JS. The `playwright` engine drives a real headless
Chromium that runs the challenge and reads the resulting rendered HTML — no
evasion, just a genuine browser — and hands identical HTML to the same parser.
`--engine auto` (default) tries `requests` first (fast, no browser) and falls
back to `playwright` the moment the finder page is blocked, so the job works
whether or not the runner's IP gets challenged.

District slugs are discovered from CPD's own district-finder page rather
than hardcoded, since districts have been merged/renumbered before and a
stale hardcoded list would silently drop or mis-map districts.

Usage:
    python3 cpd_district_scraper.py --out cpd_district_info.json
    python3 cpd_district_scraper.py --engine playwright --out cpd_district_info.json
    python3 cpd_district_scraper.py --engine requests --out cpd_district_info.json

The playwright engine needs the `playwright` package and a Chromium build
(`python3 -m playwright install chromium`); the weekly workflow installs both.
Set CPD_CHROMIUM_EXECUTABLE to point at a pre-installed browser binary if the
default channel isn't present (e.g. a shared PLAYWRIGHT_BROWSERS_PATH).

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
import os
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

# Substrings that mean a Cloudflare interstitial (not the real page) is still
# on screen. Used by both engines to tell "blocked" from "fetched".
CHALLENGE_MARKERS = (
    "just a moment",
    "attention required",
    "checking your browser",
    "cf-chl",
    "challenges.cloudflare.com/turnstile",
)


def _looks_like_challenge(html):
    low = (html or "").lower()
    return any(marker in low for marker in CHALLENGE_MARKERS)


class RequestsFetcher:
    """Plain HTTP fetch. Fast and browserless, but a Cloudflare managed
    challenge answers it with 403 (or a challenge interstitial body)."""

    engine = "requests"

    def __init__(self):
        self.session = requests.Session()

    def fetch(self, url, retries=3, timeout=20, wait_ready=None):
        # wait_ready is a browser-only readiness predicate; a plain HTTP client
        # gets whatever the server sends in one shot, so it's ignored here.
        last_err = None
        for attempt in range(retries):
            try:
                resp = self.session.get(url, headers=HEADERS, timeout=timeout)
                if resp.status_code == 200 and not _looks_like_challenge(resp.text):
                    return resp.text
                last_err = (
                    "Cloudflare challenge interstitial"
                    if resp.status_code == 200
                    else f"HTTP {resp.status_code}"
                )
            except requests.RequestException as e:
                last_err = str(e)
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    def close(self):
        self.session.close()


class PlaywrightFetcher:
    """Fetch through a real headless Chromium so Cloudflare's managed (JS)
    challenge is executed and cleared. The rendered HTML is identical in shape
    to what a browser user sees, so the existing BeautifulSoup parser is reused
    unchanged. No CAPTCHA-solving or evasion — just a genuine browser."""

    engine = "playwright"

    def __init__(self, timeout=45000, challenge_wait_s=20):
        from playwright.sync_api import sync_playwright

        self.timeout = timeout
        self.challenge_wait_s = challenge_wait_s
        self._pw = sync_playwright().start()
        self.browser = self._launch(self._pw)
        self.context = self.browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="en-US",
            viewport={"width": 1366, "height": 900},
        )

    def _launch(self, pw):
        # Honor an explicit executable first, then the default channel, then a
        # co-located PLAYWRIGHT_BROWSERS_PATH build (sandbox/CI without a
        # per-project `playwright install`).
        exe = os.environ.get("CPD_CHROMIUM_EXECUTABLE")
        if exe:
            return pw.chromium.launch(headless=True, executable_path=exe)
        try:
            return pw.chromium.launch(headless=True)
        except Exception:
            fallback = os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "chromium")
            if fallback != "chromium" and os.path.exists(fallback):
                return pw.chromium.launch(headless=True, executable_path=fallback)
            raise

    def fetch(self, url, retries=2, wait_ready=None):
        last_err = None
        for attempt in range(retries + 1):
            page = self.context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                # The managed challenge runs its JS then redirects to the real
                # page; give it a bounded window to clear before reading.
                start = time.time()
                while time.time() - start < self.challenge_wait_s and _looks_like_challenge(page.content()):
                    page.wait_for_timeout(1000)
                # Some pages (the district finder) inject their real content via
                # JS after the challenge clears; wait_ready is a JS predicate that
                # lets the caller block until that content is actually present.
                if wait_ready:
                    try:
                        page.wait_for_function(wait_ready, timeout=12000)
                    except Exception:
                        pass  # fall through with whatever rendered; caller copes
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                html = page.content()
                if not _looks_like_challenge(html):
                    return html
                last_err = "Cloudflare challenge did not clear within %ds" % self.challenge_wait_s
            except Exception as e:
                last_err = str(e)
            finally:
                page.close()
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")

    def close(self):
        try:
            self.context.close()
            self.browser.close()
        finally:
            self._pw.stop()


def make_fetcher(engine):
    if engine == "requests":
        return RequestsFetcher()
    if engine == "playwright":
        return PlaywrightFetcher()
    raise ValueError(f"unknown engine: {engine}")


def clean(text):
    if text is None:
        return None
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# CPD runs 22 active districts. Discovery reality (confirmed against the live
# site via CI, 2026-07-09): the finder page is an address-search *widget* that
# renders only one example district link, and per-district pages carry no
# all-districts nav — so neither is a usable directory. The reliable roster of
# every district page is CPD's WordPress sitemap (robots.txt points at it). We
# still hit the finder first: it's cheap, occasionally yields a link, and — the
# real reason — its Playwright navigation clears the Cloudflare challenge so the
# cf_clearance cookie warms the whole context before we pull the sitemaps.
EXPECTED_DISTRICTS = 22
WP_SITEMAP = BASE + "/wp-sitemap.xml"
FINDER_READY_JS = (
    r"(document.documentElement.innerHTML.match(/\d(?:st|nd|rd|th)-district-/gi) || []).length >= 1"
)
# Any .xml URL (sitemap-index children), tag-agnostic so it survives Chromium's
# XML-viewer rendering of the fetched sitemap.
SUBSITEMAP_RE = re.compile(r"https?://[^\s\"'<>]+?\.xml", re.IGNORECASE)


def _harvest_district_links(html, seen):
    """Add every /Nth-district-slug/ link found in html to the seen map."""
    for match in DISTRICT_LINK_RE.finditer(html):
        ordinal, slug = match.group(1), match.group(2)
        number = int(re.match(r"\d+", ordinal).group(0))
        if number in seen:
            continue
        path = f"/{ordinal}-district-{slug}/"
        seen[number] = (number, ordinal, slug, urljoin(BASE, path))
    return seen


def _harvest_from_sitemap(fetcher, seen):
    """Pull district page URLs from the WordPress sitemap index + its children."""
    try:
        index = fetcher.fetch(WP_SITEMAP)
    except Exception as e:
        print(f"sitemap index fetch failed: {e}", file=sys.stderr)
        return
    _harvest_district_links(index, seen)  # in case the index inlines page URLs
    subs = []
    for u in SUBSITEMAP_RE.findall(index):
        if u not in subs and u.rstrip("/") != WP_SITEMAP.rstrip("/"):
            subs.append(u)
    print(f"sitemap index lists {len(subs)} sub-sitemap(s)", file=sys.stderr)
    for sm in subs:
        if len(seen) >= EXPECTED_DISTRICTS:
            break
        try:
            _harvest_district_links(fetcher.fetch(sm), seen)
        except Exception as e:
            print(f"  sub-sitemap {sm} failed: {e}", file=sys.stderr)


def get_district_pages(fetcher):
    """Return sorted list of unique (district_number, ordinal, slug, url) tuples."""
    seen = {}
    try:
        _harvest_district_links(fetcher.fetch(BASE + FINDER_PATH, wait_ready=FINDER_READY_JS), seen)
    except Exception as e:
        print(f"finder fetch failed: {e}", file=sys.stderr)
    print(f"finder page yielded {len(seen)} district link(s)", file=sys.stderr)

    if len(seen) < EXPECTED_DISTRICTS:
        _harvest_from_sitemap(fetcher, seen)
        print(f"after sitemap: {len(seen)} district link(s)", file=sys.stderr)

    if len(seen) < EXPECTED_DISTRICTS:
        print(
            f"WARNING: discovered {len(seen)}/{EXPECTED_DISTRICTS} districts",
            file=sys.stderr,
        )
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


# Live CPD pages put the commander name inline in the heading, after an en/em
# dash or hyphen: "Meet your commander – Sheamus Mannion" (verified via CI,
# 2026-07-09). Group 2 is the name.
COMMANDER_INLINE_RE = re.compile(
    r"meet your (acting )?commander\s*[–—\-:]\s*(.+)$", re.IGNORECASE
)


def parse_commander(soup):
    """Return (name, status, bio) for the district commander.

    The live layout carries the name inline in the "Meet your commander – NAME"
    heading; an older layout put it in a short block right after the heading.
    Handle the inline form first, fall back to the trailing-block form."""
    heading = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "strong", "b", "p"]):
        if COMMANDER_HEADING_RE.search(tag.get_text()):
            heading = tag
            break
    if heading is None:
        return None, None, None

    heading_text = clean(heading.get_text()) or ""
    status = "acting_commander" if re.search(r"\bacting\b", heading_text, re.IGNORECASE) else "commander"

    name, bio = None, None
    inline = COMMANDER_INLINE_RE.search(heading_text)
    if inline:
        candidate = clean(inline.group(2))
        # A name is short; anything long after the dash is prose, not a name.
        if candidate and len(candidate) <= 60:
            name = candidate
        # Bio: the first substantial following paragraph (not another heading).
        for elem in heading.find_all_next(["p"]):
            text = clean(elem.get_text())
            if text and len(text) > 40 and not COMMANDER_HEADING_RE.search(text):
                bio = text
                break
    else:
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


def scrape_all(fetcher, limit=None, delay=0.5, verbose=True, pages=None):
    if pages is None:
        pages = get_district_pages(fetcher)
    if limit:
        pages = pages[:limit]
    results = []
    for i, (number, ordinal, slug, url) in enumerate(pages, 1):
        if verbose:
            print(f"[{i}/{len(pages)}] fetching district {number} ({url})", file=sys.stderr)
        try:
            html = fetcher.fetch(url)
            record = parse_district_page(html, number, url)
        except Exception as e:
            record = {"district_number": number, "source_url": url, "error": str(e)}
        results.append(record)
        time.sleep(delay)
    return results


def scrape(engine, limit=None, delay=0.5):
    """Run the scrape under the requested engine. `auto` tries `requests` first
    and transparently falls back to `playwright` the moment the finder page is
    blocked (403 / challenge), so the job survives whether or not the runner's
    IP is challenged by Cloudflare."""
    if engine in ("requests", "playwright"):
        fetcher = make_fetcher(engine)
        try:
            return scrape_all(fetcher, limit=limit, delay=delay)
        finally:
            fetcher.close()

    # auto: one decisive probe — can plain requests clear the site at all? The
    # finder page is Cloudflare-protected, so a 403/challenge here means every
    # page will be too, and we switch to the browser engine. (This probe, not
    # get_district_pages' return, drives the decision: discovery swallows a
    # blocked finder and leans on the sitemap, so it can't be the block signal.)
    req = RequestsFetcher()
    try:
        req.fetch(BASE + FINDER_PATH)
    except Exception as e:
        req.close()
        print(f"requests engine blocked ({e}); falling back to Playwright", file=sys.stderr)
        pw = make_fetcher("playwright")
        try:
            return scrape_all(pw, limit=limit, delay=delay)
        finally:
            pw.close()
    else:
        try:
            return scrape_all(req, limit=limit, delay=delay)
        finally:
            req.close()


def main():
    ap = argparse.ArgumentParser(description="Scrape CPD per-district commander/contact pages.")
    ap.add_argument("--out", default="cpd_district_info.json")
    ap.add_argument(
        "--engine",
        choices=["auto", "requests", "playwright"],
        default="auto",
        help="Fetch engine: auto (requests, fall back to playwright on a Cloudflare block), "
        "requests (browserless), or playwright (real Chromium).",
    )
    ap.add_argument("--limit", type=int, default=None, help="Limit number of districts (for testing)")
    ap.add_argument("--delay", type=float, default=0.5, help="Delay between requests (seconds)")
    args = ap.parse_args()

    results = scrape(args.engine, limit=args.limit, delay=args.delay)

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    # Per-field coverage summary — makes parser drift visible at a glance (e.g.
    # "commander_name 1/22" says the pages were fetched but the commander block
    # didn't parse), so a red build points straight at the field that broke.
    ok = [r for r in results if not r.get("error")]
    fields = ("commander_name", "commander_status", "main_phone", "caps_phone",
              "caps_email", "station_address", "district_map_url")
    coverage = "  ".join(f"{f}={sum(1 for r in ok if r.get(f))}/{len(ok)}" for f in fields)
    print(f"Wrote {len(results)} records to {args.out} ({len(ok)} without error)", file=sys.stderr)
    print(f"field coverage: {coverage}", file=sys.stderr)


if __name__ == "__main__":
    main()
