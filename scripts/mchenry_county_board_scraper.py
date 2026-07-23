#!/usr/bin/env python3
"""
Scrape the McHenry County Board member roster from mchenrycountyil.gov.

Stage 1 of the two-stage roster pipeline (same shape as
scripts/kendall_county_board_scraper.py — the other Granicus-CMS county);
scripts/build_mchenry_county_board_roster.py resolves the raw records into
data/app/mchenry-county-board-members.json, keyed by county-board district
("1".."9") plus a top-level "chair" for the countywide-elected Board
Chairman (the DuPage roster shape), which index.html's consolidated
county-board layer joins to the county's own boundary GIS by district.

Source (Granicus CMS pages):
  listing: https://www.mchenrycountyil.gov/departments/county-board/meet-your-county-board-members
           -> one content_area table (id="CB"): <td class="dist"> rows mark
              sections ("County Board Chairman", "District 1"...), member
              rows carry photo+name links (two members per district row).
              The Chairman is countywide — emitted district=null,
              role="Chairman".
  member:  .../meet-your-county-board-members/<slug>
           -> a content_area whose first block holds a
              <strong|span class="subtitle"> ("District N" / "County Board
              Chairman"), the member's phone as text (sometimes annotated
              "(work)"/"(home)"/"(mobile)", sometimes two numbers — the
              first is taken, annotation dropped), and an entity-encoded
              mailto with visible text. "Current Term Ends" rides a labeled
              paragraph.

Fetch engines (`--engine`): the county fronts the site with bot management
that 403s datacenter HTTP clients — including, live-verified on the first CI
run (2026-07-23), a genuine headless Chromium: the block is IP-reputation
based, so it never "clears" for a runner no matter how real the browser is.
`--engine auto` (default) is therefore a three-rung ladder: `requests`
first, `playwright` second (covers JS-challenge fronts and residential-ish
egress), and `wayback` last — ask the Internet Archive's Save Page Now to
capture a fresh copy with the Archive's own crawler (which the county has
historically allowed — the site's existing snapshots) and read the archived
original, falling back to the newest existing snapshot when a save fails,
refused entirely if the newest snapshot is older than WAYBACK_MAX_AGE_DAYS.
No evasion anywhere on the ladder: the content is always the county's own
page, fetched either directly or through a public archive, and records
fetched via the archive carry `archived_at` for provenance.

Notes on data honesty (per project conventions):
- A field that can't be found is stored null, never guessed. Email/phone are
  read only from the member's own content block; mailto anchors with no
  visible text are skipped.
- Home/street addresses on the member pages are deliberately NOT collected
  (the card convention surfaces office locations; these are personal).
- Every record includes `source_url` and `scraped_at` for traceability.

Usage:
    python3 mchenry_county_board_scraper.py [output.json]
    python3 mchenry_county_board_scraper.py --engine playwright out.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.mchenrycountyil.gov"
LISTING_PATH = "/departments/county-board/meet-your-county-board-members"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

BLOCK_MARKERS = (
    "errors.edgesuite.net",
    "access denied</h1>",
    "<title>access denied</title>",
    "just a moment",
    "attention required",
    "checking your browser",
    "cf-chl",
)

MEMBER_LINK_RE = re.compile(r"/departments/county-board/meet-your-county-board-members/([a-z0-9-]+)$")
DISTRICT_RE = re.compile(r"district\s*#?\s*(\d+)", re.IGNORECASE)
CHAIR_RE = re.compile(r"\bchairman\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\(?\d{3}\)?[.\-\s]?\d{3}[.\-\s]\d{4}")


def _looks_blocked(html):
    low = (html or "").lower()
    return any(marker in low for marker in BLOCK_MARKERS)


class RequestsFetcher:
    """Plain HTTP fetch — works if the runner's egress isn't challenged."""

    engine = "requests"

    def __init__(self):
        self.session = requests.Session()

    def fetch(self, url, retries=3, timeout=25):
        last_err = None
        for attempt in range(retries):
            try:
                resp = self.session.get(url, headers=HEADERS, timeout=timeout)
                if resp.status_code == 200 and not _looks_blocked(resp.text):
                    return resp.text
                last_err = (
                    "bot-management interstitial"
                    if resp.status_code == 200
                    else "HTTP %d" % resp.status_code
                )
            except requests.RequestException as e:
                last_err = str(e)
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("Failed to fetch %s: %s" % (url, last_err))

    def close(self):
        self.session.close()


class PlaywrightFetcher:
    """Fetch through a real headless Chromium (the cpd_district_scraper
    pattern: a genuine browser, no evasion)."""

    engine = "playwright"

    def __init__(self, timeout=45000, challenge_wait_s=15):
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
        exe = os.environ.get("MCHENRY_CHROMIUM_EXECUTABLE")
        if exe:
            return pw.chromium.launch(headless=True, executable_path=exe)
        try:
            return pw.chromium.launch(headless=True)
        except Exception:
            fallback = os.path.join(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", ""), "chromium")
            if fallback != "chromium" and os.path.exists(fallback):
                return pw.chromium.launch(headless=True, executable_path=fallback)
            raise

    def fetch(self, url, retries=2):
        last_err = None
        for attempt in range(retries + 1):
            page = self.context.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                start = time.time()
                while time.time() - start < self.challenge_wait_s and _looks_blocked(page.content()):
                    page.wait_for_timeout(1000)
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                html = page.content()
                if not _looks_blocked(html):
                    return html
                last_err = "bot-management block did not clear within %ds" % self.challenge_wait_s
            except Exception as e:
                last_err = str(e)
            finally:
                page.close()
            time.sleep(1.5 * (attempt + 1))
        raise RuntimeError("Failed to fetch %s: %s" % (url, last_err))

    def close(self):
        try:
            self.context.close()
            self.browser.close()
        finally:
            self._pw.stop()


# Reject archive copies older than this: a stale snapshot could silently miss
# a new appointee for months, which is worse than a loud failed run (the
# weekly workflow just fails visibly and a human looks).
WAYBACK_MAX_AGE_DAYS = 45


class WaybackFetcher:
    """Terminal fallback: fetch the page through the Internet Archive. Save
    Page Now captures a fresh copy with the Archive's own crawler — which the
    county does not block (the site's existing snapshots prove it) — and the
    raw archived original (`id_` URL) is read back. If the save fails, the
    newest existing snapshot serves, but never one older than
    WAYBACK_MAX_AGE_DAYS. Not evasion: a public archive of the county's own
    page, with the copy's timestamp surfaced for provenance."""

    engine = "wayback"

    def __init__(self):
        self.session = requests.Session()
        self.last_archived_at = None  # timestamp of the copy the last fetch used

    def _save_authenticated(self, url, key, secret):
        """SPN2 (POST + job polling) with an archive.org API key — the
        reliable path when the runner's shared IP has exhausted the anonymous
        quota. Keys ride the ARCHIVE_SPN_ACCESS_KEY / ARCHIVE_SPN_SECRET_KEY
        env vars (repo secrets in CI); absent keys skip straight to the
        anonymous route."""
        auth = {"Accept": "application/json", "Authorization": "LOW %s:%s" % (key, secret)}
        try:
            r = self.session.post("https://web.archive.org/save",
                                  headers=dict(HEADERS, **auth),
                                  data={"url": url}, timeout=60)
            job = r.json().get("job_id")
            if not job:
                return None
            for _ in range(30):  # up to ~2.5 minutes per capture
                time.sleep(5)
                s = self.session.get("https://web.archive.org/save/status/" + job,
                                     headers=dict(HEADERS, **auth), timeout=30).json()
                if s.get("status") == "success":
                    return s.get("timestamp")
                if s.get("status") == "error":
                    return None
        except (requests.RequestException, ValueError):
            pass
        return None

    def _save(self, url):
        """Ask Save Page Now for a fresh capture; return its timestamp or None."""
        key = os.environ.get("ARCHIVE_SPN_ACCESS_KEY")
        secret = os.environ.get("ARCHIVE_SPN_SECRET_KEY")
        if key and secret:
            ts = self._save_authenticated(url, key, secret)
            if ts:
                return ts
        try:
            resp = self.session.get(
                "https://web.archive.org/save/" + url,
                headers=HEADERS, timeout=180, allow_redirects=True)
            m = re.search(r"/web/(\d{14})", resp.url or "")
            if not m:
                m = re.search(r"/web/(\d{14})", resp.headers.get("Content-Location", ""))
            if resp.status_code == 200 and m:
                return m.group(1)
        except requests.RequestException:
            pass
        return None

    def _latest(self, url):
        """Newest existing snapshot's timestamp, or None."""
        try:
            resp = self.session.get(
                "https://archive.org/wayback/available",
                params={"url": url}, headers=HEADERS, timeout=60)
            snap = (resp.json().get("archived_snapshots") or {}).get("closest") or {}
            return snap.get("timestamp") or None
        except (requests.RequestException, ValueError):
            return None

    def fetch(self, url, retries=1):
        last_err = None
        for attempt in range(retries + 1):
            ts = self._save(url) or self._latest(url)
            if ts is None:
                last_err = "no archive snapshot available"
                time.sleep(3 * (attempt + 1))
                continue
            age_days = (datetime.now(timezone.utc)
                        - datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)).days
            if age_days > WAYBACK_MAX_AGE_DAYS:
                last_err = ("newest archive snapshot is %d days old (max %d) — refusing "
                            "stale officeholder data" % (age_days, WAYBACK_MAX_AGE_DAYS))
                break
            try:
                resp = self.session.get(
                    "https://web.archive.org/web/%sid_/%s" % (ts, url),
                    headers=HEADERS, timeout=120)
                if resp.status_code == 200 and not _looks_blocked(resp.text):
                    self.last_archived_at = ts
                    return resp.text
                last_err = ("archived copy is itself a block page" if resp.status_code == 200
                            else "HTTP %d reading snapshot %s" % (resp.status_code, ts))
            except requests.RequestException as e:
                last_err = str(e)
            time.sleep(3 * (attempt + 1))
        raise RuntimeError("Failed to fetch %s via the Internet Archive: %s" % (url, last_err))

    def close(self):
        self.session.close()


def make_fetcher(engine):
    if engine == "requests":
        return RequestsFetcher()
    if engine == "playwright":
        return PlaywrightFetcher()
    if engine == "wayback":
        return WaybackFetcher()
    raise ValueError("unknown engine: %s" % engine)


def clean(text):
    if text is None:
        return None
    text = re.sub(r"[\s ]+", " ", text).strip()
    return text or None


def parse_listing(html):
    """Return ordered [{slug, name, url, district, role}] from the listing's
    member table. A <td class="dist"> row sets the current section; member
    links are deduped by slug (each member appears as a photo link and a
    name link), and the name comes from the link with visible text."""
    soup = BeautifulSoup(html, "html.parser")
    members = []
    seen = {}
    for area in soup.select("div.content_area"):
        for table in area.find_all("table"):
            if not table.find("td", class_="dist"):
                continue
            section = None  # "chair" | district number string
            for tr in table.find_all("tr"):
                dist_td = tr.find("td", class_="dist")
                if dist_td:
                    text = clean(dist_td.get_text()) or ""
                    if CHAIR_RE.search(text):
                        section = "chair"
                    else:
                        m = DISTRICT_RE.search(text)
                        section = m.group(1) if m else None
                    continue
                if section is None:
                    continue
                for a in tr.find_all("a", href=True):
                    m = MEMBER_LINK_RE.search(a["href"].split("?")[0].rstrip("/"))
                    if not m:
                        continue
                    slug = m.group(1)
                    name = clean(a.get_text())
                    if slug not in seen:
                        rec = {
                            "slug": slug,
                            "name": name,
                            "url": urljoin(BASE, LISTING_PATH + "/" + slug),
                            "district": None if section == "chair" else section,
                            "role": "Chairman" if section == "chair" else None,
                        }
                        seen[slug] = rec
                        members.append(rec)
                    elif name and not seen[slug]["name"]:
                        seen[slug]["name"] = name  # photo link came first
    return members


def parse_member_page(html):
    """Return {district, chair, email, phone, term} from a member page's OWN
    content area (all nullable — never guessed). The member's area is the
    content_area holding a `.subtitle` marker or a "Current Term Ends"
    label; email/phone are read only inside it."""
    soup = BeautifulSoup(html, "html.parser")
    area = None
    for candidate in soup.select("div.content_area"):
        if candidate.select_one(".subtitle"):
            area = candidate
            break
        for strong in candidate.find_all("strong"):
            if re.search(r"current term ends", strong.get_text(), re.IGNORECASE):
                area = candidate
                break
        if area is not None:
            break
    if area is None:
        return {"district": None, "chair": False, "email": None, "phone": None, "term": None}

    district = None
    chair = False
    subtitle = area.select_one(".subtitle")
    if subtitle:
        text = clean(subtitle.get_text()) or ""
        m = DISTRICT_RE.search(text)
        if m:
            district = m.group(1)
        if CHAIR_RE.search(text):
            chair = True

    email = None
    for a in area.find_all("a", href=re.compile(r"^mailto:", re.IGNORECASE)):
        visible = clean(a.get_text())
        addr = clean(a["href"][len("mailto:"):].split("?")[0])
        if visible and addr:
            email = addr
            break

    # the first phone-shaped number in the member's own block; the pages
    # annotate some numbers ("(work)"/"(home)"/"(mobile)") and one member
    # lists two — the regex takes just the number, first match wins
    phone = None
    m = PHONE_RE.search(area.get_text())
    if m:
        phone = clean(m.group(0))

    term = None
    for strong in area.find_all("strong"):
        if re.search(r"current term ends", strong.get_text(), re.IGNORECASE):
            parent_text = clean(strong.parent.get_text()) or ""
            label = clean(strong.get_text()) or ""
            idx = parent_text.lower().find(label.lower())
            if idx >= 0:
                term = clean(parent_text[idx + len(label):].lstrip(" :"))
            break

    return {"district": district, "chair": chair, "email": email, "phone": phone, "term": term}


def scrape_all(fetcher, delay=0.75, verbose=True, listing_html=None):
    if listing_html is None:
        listing_html = fetcher.fetch(BASE + LISTING_PATH)
    listing = parse_listing(listing_html)
    if verbose:
        print("listing yielded %d member link(s) [engine=%s]" % (len(listing), fetcher.engine),
              file=sys.stderr)
    records = []
    for i, m in enumerate(listing, 1):
        if verbose:
            print("[%d/%d] fetching %s" % (i, len(listing), m["url"]), file=sys.stderr)
        rec = {
            "slug": m["slug"],
            "name": m["name"],
            "district": m["district"],
            "role": m["role"],
            "source_url": m["url"],
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            detail = parse_member_page(fetcher.fetch(m["url"]))
            if detail["district"]:
                rec["district"] = detail["district"]
            if detail["chair"] and not rec["role"]:
                rec["role"] = "Chairman"
            rec["email"] = detail["email"]
            rec["phone"] = detail["phone"]
            rec["term_expiration"] = detail["term"]
            archived = getattr(fetcher, "last_archived_at", None)
            if archived:
                rec["archived_at"] = archived  # provenance: the archive copy used
        except Exception as e:
            rec["error"] = str(e)
        records.append(rec)
        time.sleep(delay)
    return records


def scrape(engine, delay=0.75):
    """auto: walk the engine ladder (requests -> playwright -> wayback),
    probing each on the listing page; the first engine that can fetch it runs
    the whole scrape. The probe result is reused so the winning engine never
    refetches the listing (a Save Page Now capture is not free)."""
    if engine in ("requests", "playwright", "wayback"):
        fetcher = make_fetcher(engine)
        try:
            return scrape_all(fetcher, delay=delay)
        finally:
            fetcher.close()

    last_err = None
    for name in ("requests", "playwright", "wayback"):
        try:
            fetcher = make_fetcher(name)
        except Exception as e:  # e.g. playwright/Chromium not installed
            print("%s engine unavailable (%s); trying next" % (name, e), file=sys.stderr)
            last_err = e
            continue
        try:
            listing_html = fetcher.fetch(BASE + LISTING_PATH)
        except Exception as e:
            print("%s engine blocked (%s); trying next" % (name, e), file=sys.stderr)
            last_err = e
            fetcher.close()
            continue
        try:
            return scrape_all(fetcher, delay=delay, listing_html=listing_html)
        finally:
            fetcher.close()
    raise RuntimeError("all fetch engines failed; last error: %s" % last_err)


def main():
    ap = argparse.ArgumentParser(description="Scrape McHenry County Board member pages.")
    ap.add_argument("out", nargs="?", default=None, help="output JSON path (default: stdout)")
    ap.add_argument(
        "--engine",
        choices=["auto", "requests", "playwright", "wayback"],
        default="auto",
        help="Fetch engine: auto (the requests -> playwright -> wayback ladder), "
        "requests (browserless), playwright (real Chromium), or wayback "
        "(Internet Archive Save Page Now + snapshot read).",
    )
    ap.add_argument("--delay", type=float, default=0.75, help="Delay between requests (seconds)")
    args = ap.parse_args()

    records = scrape(args.engine, delay=args.delay)

    payload = json.dumps(records, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload + "\n")
    else:
        print(payload)

    ok = [r for r in records if not r.get("error")]
    fields = ("district", "email", "phone", "term_expiration")
    coverage = "  ".join("%s=%d/%d" % (f, sum(1 for r in ok if r.get(f)), len(ok)) for f in fields)
    print("Scraped %d members (%d without error)" % (len(records), len(ok)), file=sys.stderr)
    print("field coverage: %s" % coverage, file=sys.stderr)


if __name__ == "__main__":
    main()
