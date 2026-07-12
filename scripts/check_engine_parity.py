#!/usr/bin/env python3
"""
Cross-metro engine parity check.

Every District Explorer metro is its own fork (see docs/ENGINE_SYNC.md), but
the metro-agnostic "engine" inside index.html is meant to be byte-identical
across forks. Shared code is fenced with marker comments:

    /* ==== ENGINE:BEGIN block-name ==== */
    ...shared code, byte-identical in every fork...
    /* ==== ENGINE:END block-name ==== */

(HTML regions use the same markers inside <!-- ... --> comments.) Everything
metro-specific that engine blocks reference lives in the METRO config block
near the top of the script, so an engine block never needs a per-city edit.

This script is itself part of the shared engine: the SAME file ships in every
fork. Per-fork values (which sibling to compare against) are passed on the
command line by each fork's workflow, never hardcoded here.

Modes:
  Lint (default) — markers are balanced, non-nested, uniquely named:
      python3 scripts/check_engine_parity.py index.html

  Compare — same blocks, byte-identical bodies, against a sibling fork's
  index.html (a local path or a deployed URL):
      python3 scripts/check_engine_parity.py index.html \
          --against https://nyc.chidistricts.com/ [--label nyc]

  Post-assembly assertion — compare this file's blocks against a downloaded
  engine release (docs/MECHANIZATION_PLAYBOOK.md, Conversion 1). Reads the
  manifest, takes the blocks it assigns to this file's basename, and compares
  them byte-wise against the bundle. Run with --strict inside the deploy job,
  right after apply_engine.py, so a splice that doesn't reproduce the pinned
  engine fails the deploy:
      python3 scripts/check_engine_parity.py index.html \
          --against-bundle engine.manifest.json --strict

Exit codes: 0 = ok (or drift found without --strict; drift is a WARN that a
human ports, matching validate_sources.py's "surface, don't block" pattern),
1 = hard FAIL (malformed markers, unreadable input), 2 = drift with --strict.
--report FILE writes a markdown report; --status-file FILE writes ok|warn|fail.
"""

import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import urllib.request

MARKER_RE = re.compile(
    r"^[ \t]*(?:/\*|<!--)[ \t]*==== ENGINE:(BEGIN|END) ([a-z0-9][a-z0-9-]*) ====[ \t]*(?:\*/|-->)[ \t]*$"
)


def read_source(spec):
    """Read text from a local path or an http(s) URL."""
    if spec.startswith("http://") or spec.startswith("https://"):
        req = urllib.request.Request(spec, headers={"User-Agent": "district-explorer-engine-parity"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    with open(spec, encoding="utf-8") as f:
        return f.read()


def extract_blocks(text, label):
    """Return {name: body} for every ENGINE block. Raises ValueError on
    malformed fences (unbalanced, nested, duplicate names, END/BEGIN mismatch).
    Bodies exclude the marker lines themselves, so JS vs HTML comment style
    never affects comparison."""
    blocks = {}
    open_name = None
    body = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = MARKER_RE.match(line)
        if not m:
            if open_name is not None:
                body.append(line)
            continue
        kind, name = m.groups()
        if kind == "BEGIN":
            if open_name is not None:
                raise ValueError(
                    "%s:%d: ENGINE:BEGIN %s while %s is still open (nesting is not allowed)"
                    % (label, lineno, name, open_name)
                )
            if name in blocks:
                raise ValueError("%s:%d: duplicate ENGINE block name %r" % (label, lineno, name))
            open_name = name
            body = []
        else:
            if open_name is None:
                raise ValueError("%s:%d: ENGINE:END %s without a matching BEGIN" % (label, lineno, name))
            if name != open_name:
                raise ValueError(
                    "%s:%d: ENGINE:END %s does not match open block %s" % (label, lineno, name, open_name)
                )
            blocks[open_name] = "\n".join(body)
            open_name = None
    if open_name is not None:
        raise ValueError("%s: ENGINE block %s is never closed" % (label, open_name))
    return blocks


def digest(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]


def blocks_from_bundle(manifest_path, target_file):
    """Return ({name: body}, label) for the blocks an engine-release manifest
    assigns to target_file's basename, read out of the bundle it describes.
    The bundle re-wraps every block in the same fence markers, so the one
    shared parser reads it back. Raises ValueError on a manifest whose block
    list and bundle contents disagree — that is a corrupt artifact, never a
    porting WARN."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    bundle_path = os.path.join(os.path.dirname(manifest_path) or ".", manifest["bundle"])
    with open(bundle_path, encoding="utf-8") as f:
        bundle_blocks = extract_blocks(f.read(), bundle_path)
    wanted = {}
    base = os.path.basename(target_file)
    for entry in manifest["blocks"]:
        if entry["file"] != base:
            continue
        if entry["name"] not in bundle_blocks:
            raise ValueError(
                "%s: manifest lists block %r for %s but the bundle does not contain it"
                % (manifest_path, entry["name"], base)
            )
        wanted[entry["name"]] = bundle_blocks[entry["name"]]
    if not wanted:
        raise ValueError(
            "%s: manifest assigns no blocks to %r — wrong target file?" % (manifest_path, base)
        )
    return wanted, "bundle %s (%s)" % (manifest.get("engine_version", "?"), manifest_path)


def short_diff(name, ours, theirs, ours_label, theirs_label, max_lines=24):
    lines = list(
        difflib.unified_diff(
            ours.splitlines(), theirs.splitlines(),
            fromfile="%s %s" % (ours_label, name), tofile="%s %s" % (theirs_label, name),
            lineterm="", n=1,
        )
    )
    clipped = lines[:max_lines]
    if len(lines) > max_lines:
        clipped.append("... (%d more diff lines)" % (len(lines) - max_lines))
    return "\n".join(clipped)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file", nargs="?", default="index.html", help="this fork's index.html")
    ap.add_argument("--against", help="sibling index.html: local path or deployed URL")
    ap.add_argument("--against-bundle", metavar="MANIFEST",
                    help="engine.manifest.json of a downloaded release: compare this file's "
                         "blocks against the bundle (post-assembly assertion; use with --strict)")
    ap.add_argument("--label", default=None, help="short name for the sibling in the report")
    ap.add_argument("--report", help="write a markdown report to this path")
    ap.add_argument("--status-file", help="write ok|warn|fail to this path")
    ap.add_argument("--strict", action="store_true", help="exit 2 on drift (for local pre-port checks)")
    args = ap.parse_args()

    status = "ok"
    report = []

    try:
        ours = extract_blocks(read_source(args.file), args.file)
    except (ValueError, OSError) as e:
        print("engine-parity: FAIL — %s" % e, file=sys.stderr)
        if args.status_file:
            open(args.status_file, "w").write("fail")
        sys.exit(1)

    if not ours:
        print("engine-parity: FAIL — %s contains no ENGINE blocks" % args.file, file=sys.stderr)
        if args.status_file:
            open(args.status_file, "w").write("fail")
        sys.exit(1)

    if args.against and args.against_bundle:
        print("engine-parity: FAIL — --against and --against-bundle are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    if not args.against and not args.against_bundle:
        print("engine-parity: OK — %d ENGINE blocks, markers well formed:" % len(ours))
        for name in sorted(ours):
            print("  %-28s %s  (%d lines)" % (name, digest(ours[name]), ours[name].count("\n") + 1))
        if args.status_file:
            open(args.status_file, "w").write("ok")
        return

    if args.against_bundle:
        # Post-assembly assertion: a release artifact that is unreadable or
        # self-inconsistent is a hard FAIL, never a porting WARN — the deploy
        # must stop, not open an issue.
        try:
            theirs, sibling_label = blocks_from_bundle(args.against_bundle, args.file)
        except (ValueError, OSError, KeyError) as e:
            print("engine-parity: FAIL — %s" % e, file=sys.stderr)
            if args.status_file:
                open(args.status_file, "w").write("fail")
            sys.exit(1)
        if args.label:
            sibling_label = args.label
    else:
        sibling_label = args.label or args.against
        try:
            theirs = extract_blocks(read_source(args.against), sibling_label)
        except (ValueError, OSError) as e:
            # A sibling that hasn't shipped markers yet (or is unreachable) is a
            # WARN, not a FAIL: surface it, let a human decide.
            print("engine-parity: WARN — could not extract sibling blocks: %s" % e, file=sys.stderr)
            report.append("## Sibling `%s`\n\n**Could not extract ENGINE blocks:** %s\n" % (sibling_label, e))
            status = "warn"
            theirs = {}

    if args.against and not theirs and status == "ok":
        # Readable, well-formed source with zero fences: the sibling hasn't
        # shipped the marked engine yet (e.g. the parity release is merged but
        # not deployed there). Surface it — silence would read as parity.
        print("engine-parity: WARN — sibling %s contains no ENGINE blocks (markers not shipped yet?)" % sibling_label,
              file=sys.stderr)
        report.append("## Sibling `%s`\n\n**No ENGINE blocks found** — the sibling has not shipped the fenced engine yet (merged but undeployed?), or its fences were deleted.\n" % sibling_label)
        status = "warn"

    ok, drifted, missing_theirs, missing_ours = [], [], [], []
    if theirs:
        for name in sorted(set(ours) | set(theirs)):
            if name not in theirs:
                missing_theirs.append(name)
            elif name not in ours:
                missing_ours.append(name)
            elif ours[name] == theirs[name]:
                ok.append(name)
            else:
                drifted.append(name)
        if drifted or missing_theirs or missing_ours:
            status = "warn"

        report.append("## Sibling `%s`\n" % sibling_label)
        report.append("| status | blocks |")
        report.append("|---|---|")
        report.append("| identical | %d |" % len(ok))
        report.append("| **drifted** | %s |" % (", ".join("`%s`" % n for n in drifted) or "—"))
        report.append("| missing in sibling | %s |" % (", ".join("`%s`" % n for n in missing_theirs) or "—"))
        report.append("| missing here | %s |" % (", ".join("`%s`" % n for n in missing_ours) or "—"))
        report.append("")
        for name in drifted:
            report.append("### drift in `%s`\n" % name)
            report.append("```diff")
            report.append(short_diff(name, ours[name], theirs[name], args.file, sibling_label))
            report.append("```\n")

    print("engine-parity: %s — %d identical, %d drifted, %d missing in sibling, %d missing here"
          % (status.upper(), len(ok), len(drifted), len(missing_theirs), len(missing_ours)))
    for name in drifted:
        print("  DRIFT   %s" % name)
    for name in missing_theirs:
        print("  THEIRS? %s (not in sibling)" % name)
    for name in missing_ours:
        print("  OURS?   %s (sibling has it, we don't)" % name)

    if args.report:
        header = (
            "# Engine parity report\n\n"
            "Byte-level comparison of `ENGINE` blocks (see `docs/ENGINE_SYNC.md`). "
            "Drift means one fork's engine changed without the diff being ported to the sibling — "
            "port the missing commit(s); never re-implement from a prose prompt.\n\n"
        )
        open(args.report, "w").write(header + "\n".join(report) + "\n")
    if args.status_file:
        open(args.status_file, "w").write(status)
    if status != "ok" and args.strict:
        sys.exit(2)


if __name__ == "__main__":
    main()
