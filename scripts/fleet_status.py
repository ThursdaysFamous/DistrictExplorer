#!/usr/bin/env python3
"""
Weekly fleet-status aggregator (docs/MECHANIZATION_PLAYBOOK.md, Conversion 3).

Runs in the CHI repo only (one report, in the canonical repo). Reads the fleet
manifest (metros.json) and, for every fork, aggregates:

  - engine pin: the fork's engine.lock.json version vs CHI's latest engine-v*
    release (behind = the bump PR hasn't merged there yet);
  - validator capabilities: the CAPABILITIES list parsed from the fork's
    scripts/validate_index.py, diffed against CHI's. A capability present in a
    fork but absent in CHI is a **reverse-parity WARN** — the back-port debt
    this workflow exists to surface;
  - scraper health: last completed run per workflow named in the fork's
    metro-worksheet.json, plus any per-field coverage one-liners greppable
    from that run's log;
  - open bot PRs (roster + engine-bump branches awaiting human review).

Emits a markdown report and a status word (ok|warn). It never edits anything —
the workflow posts the report to a single auto-updated tracking issue and the
job stays green; the issue is the signal (the validate-sources convention).

Stdlib only. Network: api.github.com (+ raw file contents via the API), using
the GH_TOKEN env var when present.

Usage:
    python3 scripts/fleet_status.py [--manifest metros.json]
        [--report fleet-status.md] [--status-file status.txt]
"""

import argparse
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
import zipfile

API = "https://api.github.com"
CAP_RE = re.compile(r"^CAPABILITIES\s*=\s*\[(.*?)\]", re.DOTALL | re.MULTILINE)


def api_get(path, raw=False):
    req = urllib.request.Request(API + path, headers={
        "User-Agent": "district-explorer-fleet-status",
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
    })
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    return data if raw else json.loads(data.decode("utf-8"))


def fetch_file(repo, path):
    """Raw file contents from the repo's default branch, or None."""
    try:
        return api_get("/repos/%s/contents/%s" % (repo, path), raw=True).decode("utf-8")
    except (urllib.error.URLError, UnicodeDecodeError):
        return None


def parse_capabilities(validator_text):
    m = CAP_RE.search(validator_text or "")
    if not m:
        return None  # fork hasn't declared yet — reported as such, not a WARN
    return sorted(re.findall(r'"([a-z0-9-]+)"', m.group(1)))


def latest_engine_release(chi_repo):
    try:
        rels = api_get("/repos/%s/releases?per_page=10" % chi_repo)
        for r in rels:
            if r.get("tag_name", "").startswith("engine-v") and not r.get("draft"):
                return r["tag_name"]
    except urllib.error.URLError:
        pass
    return None


def workflow_health(repo, wf_file):
    """(conclusion, date, coverage_lines) of the last completed run."""
    try:
        runs = api_get("/repos/%s/actions/workflows/%s/runs?per_page=1&status=completed" % (repo, wf_file))
        run = runs["workflow_runs"][0]
    except (urllib.error.URLError, LookupError):
        return ("no runs", "", [])
    coverage = []
    try:
        blob = api_get("/repos/%s/actions/runs/%d/logs" % (repo, run["id"]), raw=True)
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            for name in z.namelist():
                for line in z.read(name).decode("utf-8", "replace").splitlines():
                    if re.search(r"coverage", line, re.IGNORECASE):
                        coverage.append(re.sub(r"^\S+\s", "", line).strip())
    except Exception:  # noqa: BLE001 — coverage is best-effort garnish, never a failure
        pass
    return (run.get("conclusion") or "?", (run.get("run_started_at") or "")[:10], coverage[:4])


def open_bot_prs(repo):
    try:
        prs = api_get("/repos/%s/pulls?state=open&per_page=100" % repo)
        return sorted("#%d (%s)" % (p["number"], p["head"]["ref"]) for p in prs
                      if p["head"]["ref"].startswith("bot/"))
    except urllib.error.URLError:
        return []


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="metros.json")
    ap.add_argument("--report", help="write the markdown report here (default: stdout)")
    ap.add_argument("--status-file", help="write ok|warn here")
    args = ap.parse_args()

    with open(args.manifest, encoding="utf-8") as f:
        manifest = json.load(f)
    metros = manifest["metros"]
    chi = next(m for m in metros if m["id"] == "chicago")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "validate_index.py"),
              encoding="utf-8") as f:
        chi_caps = parse_capabilities(f.read()) or []

    latest = latest_engine_release(chi["repo"])
    warns = []
    lines = ["# Fleet status", ""]
    lines.append("Latest engine release: **%s**" % (latest or "unknown (API unreachable?)"))
    lines.append("")

    for m in metros:
        repo = m["repo"]
        lines.append("## %s (`%s`)" % (m["label"], repo))
        lines.append("")

        lock_raw = fetch_file(repo, "engine.lock.json")
        pin = None
        if lock_raw:
            try:
                pin = json.loads(lock_raw).get("engine_version")
            except ValueError:
                pass
        if pin and latest and pin != latest:
            warns.append("%s: engine pin %s is behind latest release %s" % (m["id"], pin, latest))
            lines.append("- Engine pin: **%s — BEHIND %s** (bump PR pending?)" % (pin, latest))
        else:
            lines.append("- Engine pin: %s" % (pin or "not found"))

        caps = parse_capabilities(fetch_file(repo, "scripts/validate_index.py"))
        if caps is None:
            lines.append("- Validator capabilities: not declared yet (Conversion 3 §3.1)")
        elif m["id"] == "chicago":
            lines.append("- Validator capabilities: %d declared (the reference set)" % len(caps))
        else:
            ahead = sorted(set(caps) - set(chi_caps))
            behind = sorted(set(chi_caps) - set(caps))
            if ahead:
                warns.append("%s: REVERSE-PARITY — capabilities not in CHI: %s" % (m["id"], ", ".join(ahead)))
                lines.append("- Validator capabilities: **REVERSE-PARITY WARN — fork has %s; CHI lacks them.** "
                             "Back-port to CHI within one release cycle (docs/ENGINE_SYNC.md DoD)." % ", ".join("`%s`" % c for c in ahead))
            else:
                lines.append("- Validator capabilities: no reverse-parity debt")
            if behind:
                lines.append("  (fork missing vs CHI: %s — forward parity, arrives via normal porting)" % ", ".join("`%s`" % c for c in behind))

        ws_raw = fetch_file(repo, "metro-worksheet.json")
        wfs = []
        if ws_raw:
            try:
                wfs = json.loads(ws_raw).get("workflows", [])
            except ValueError:
                pass
        if not wfs:
            lines.append("- Scrapers: worksheet not found — no workflow inventory (Conversion 2 pending?)")
        else:
            lines.append("- Scrapers (last completed run):")
            for wf in wfs:
                concl, date, cov = workflow_health(repo, wf["file"])
                if concl not in ("success", "no runs"):
                    warns.append("%s: %s last run %s (%s)" % (m["id"], wf["file"], concl, date))
                mark = "✅" if concl == "success" else ("➖" if concl == "no runs" else "❌")
                lines.append("  - %s `%s` %s %s" % (mark, wf["file"], concl, date))
                for c in cov:
                    lines.append("    - coverage: `%s`" % c)

        bots = open_bot_prs(repo)
        lines.append("- Open bot PRs: %s" % (", ".join(bots) if bots else "none"))
        lines.append("")

    status = "warn" if warns else "ok"
    lines.append("---")
    if warns:
        lines.append("**%d WARN(s):**" % len(warns))
        for w in warns:
            lines.append("- %s" % w)
    else:
        lines.append("No WARNs — fleet is current.")
    report = "\n".join(lines) + "\n"

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
    else:
        print(report)
    if args.status_file:
        with open(args.status_file, "w") as f:
            f.write(status)
    print("fleet-status: %s — %d warn(s)" % (status.upper(), len(warns)), file=sys.stderr)


if __name__ == "__main__":
    main()
