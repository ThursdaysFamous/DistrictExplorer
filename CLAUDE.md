# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Chicago District Explorer: a single-file, dependency-light web app. Click a point in Chicago (or search an address) and it reports every civic district containing that point and who represents you there — wards, county/state/federal legislative districts, police districts/beats, school zones, and more. Deployed as a static site to `chidistricts.com` (see `CNAME`).

**There is no build step, no framework, and no server-side code.** The entire app — styles, core, and all layer modules — lives inline in `index.html` (~5,000 lines). `sw.js` is the service worker; `data/app/*.json` are runtime-fetched data files. Everything else is data pipeline, scrapers, or CI.

<!-- ==== GENERATED:BEGIN metro-facts ==== -->
**Metro facts** (generated from `metro-worksheet.json` — edit the worksheet and run
`python3 scripts/generate_metro_files.py`; hand-edits here fail CI):

- Metro: Chicago (`chicago`) — https://chidistricts.com/
- Geocoders: address Photon (Chicago-bounded type-ahead); unbounded Photon (whole-coverage, sibling-metro lookup); POI Nominatim (office-address pin lookup, serial >=1s queue)
- Ground truth: 41.88250,-87.62850 (downtown Loop — inside Cook County) → school-board 12; il-supreme-court 1; ccbr 3. Negative point 41.70000,-87.10000 (Lake Michigan, Indiana waters — outside all three anchor layers).
- Layers: 33 registered (political 11, safety 6, schools 9, geography 7); `registerLayer(` floor 15. Debug namespace `window.ChiExplorer`.
- Scheduled workflows: `update-ilga-roster.yml` (Mon 13:00 UTC); `update-congress-roster.yml` (Mon 13:00 UTC); `update-cpd-roster.yml` (Tue 13:00 UTC); `update-ccpsa-roster.yml` (Wed 13:00 UTC); `update-will-county-board-roster.yml` (Thu 13:00 UTC); `validate-sources.yml` (1st of month 14:00 UTC).
- Source registry: `scripts/validate_sources.py` (machine-checked monthly)
<!-- ==== GENERATED:END metro-facts ==== -->

## Running & testing

```bash
# Run locally — any static server works; internet needed for live-API layers:
python3 -m http.server 8000    # then open http://localhost:8000/

# Behaviour gate (real Chromium boot via Playwright) — the main test:
npm install playwright@1.56.1 && npx playwright install --with-deps chromium
BASE_URL=http://localhost:8000/ node scripts/smoke_test.mjs   # serve first, then run

# Static gate (run after any data/app regeneration or app edit):
python3 scripts/validate_index.py index.html

# Generated-region gate (Conversion 2): per-fork facts live ONCE in
# metro-worksheet.json; GENERATED:BEGIN/END regions in index.html, sw.js,
# validate_index.py, smoke_test.mjs, CLAUDE.md, and README.md are emitted from
# it. NEVER hand-edit a GENERATED region — edit the worksheet and regenerate:
pip install -c scripts/requirements.txt jsonschema
python3 scripts/generate_metro_files.py            # regenerate in place
python3 scripts/generate_metro_files.py --check    # the CI drift gate

# Source-freshness gate (checks upstream datasets haven't gone stale):
pip install -c scripts/requirements.txt requests
python3 scripts/validate_sources.py            # add --offline to skip network
```

`smoke_test.mjs` is a single end-to-end script, not a framework — there are no "individual tests" to select. It asserts the app boots, registers all layers, classifies a known downtown point against ground truth (school board 12, IL Supreme Court 1, Board of Review 3), and degrades to an isolated error card when a source fails. `node_modules`/`package.json` are intentionally gitignored — this repo never commits build artifacts.

**Sandboxed environments (Claude Code web) — Leaflet CDN egress:** `index.html` loads Leaflet from `cdnjs.cloudflare.com`. In the Claude Code web/sandbox the headless browser cannot reach that CDN — Chromium doesn't use the agent HTTPS proxy, so the request resets (`ERR_CONNECTION_RESET` → `L is not defined` → the app never boots). This is environmental, **not** a code regression; don't chase it in app code. It's handled automatically: a `SessionStart` hook (`.claude/settings.json`) runs `scripts/vendor_leaflet.sh`, which `curl`s Leaflet (curl *does* go through the proxy) into `scripts/vendor/leaflet/` (gitignored). `smoke_test.mjs` then serves those files same-origin via `page.route`, so the app boots. Production and GitHub Actions CI are untouched — they reach the CDN directly and the vendor dir is absent, so the fallback is skipped. To run the smoke test manually in this env, `bash scripts/vendor_leaflet.sh` first (or just rely on the session-start hook).

`validate_index.py` is the merge gate: it confirms `index.html` passes `node --check`, still registers every layer (a drop in the `registerLayer(` count fails), embeds no dataset inline, and that every `data/app/` file is present with the expected feature/roster counts.

`validate_sources.py` is the **freshness** gate (complements the merge gate above). It catches the failure mode the roster scrapers can't: a publisher silently superseding a dataset the app hardcodes. Chicago Data Portal (Socrata) datasets are re-published under a **new id** each year — the CPS attendance-boundary layers ship a fresh `…SY####` dataset every school year — so the old id keeps returning stale data with no error. The script carries a manifest of every Socrata dataset id and shapefile provenance URL the app depends on and checks: (1) the manifest still matches index.html (drift guard), (2) each Socrata id still resolves and keeps its expected name, searching the portal catalog for a **newer-year edition** of the year-versioned ones, (3) the three shapefile sources (ilsenateredistricting.com / illinoiscourts.gov / cookcountyboardofreview.com) are reachable and their built `data/app/` files present, (4) the live ArcGIS/TIGERweb endpoints resolve. It **never edits the app** — swapping a dataset id is schema-sensitive — it exits non-zero only on hard FAILs and reports a newer edition as a WARN. `.github/workflows/validate-sources.yml` runs it monthly and opens/updates a single tracking issue on any WARN/FAIL (the job stays green; the issue is the signal), matching the roster pattern of "source changes get a human look before they ship." When a dataset id is swapped in index.html, update the manifest in `validate_sources.py` to match.

## Architecture: stable core + pluggable layer modules

All inside `index.html`, wrapped in one IIFE. The full contract and per-thread build log live in `docs/BUILD_PLAYBOOK_1.md`; `docs/OPTIMIZATION_PLAYBOOK.md` holds measured optimization tasks. `docs/METRO_EXPANSION_PLAYBOOK.md` is the recipe for porting the app to a new metro (Chicago is the reference implementation; each metro is its own fork), with the completed NYC port's build record archived at `docs/archive/METRO_EXPANSION_NYC.md` (fork: `github.com/ThursdaysFamous/DistrictExplorer-NYC`).

**Core** provides: the Leaflet map, click-to-select + debounced Chicago-bounded Nominatim geocoder, a global `state` object `{selectedPoint, sequence, layersOn, ...}`, the layer registry + result-card framework, selected-boundary highlight, and URL-hash permalinks (`#point=lat,lng&layers=ward,school-board`). A small namespace is exposed as `window.ChiExplorer` for debugging.

**Shared utilities** (reuse these; don't reinvent):
- `sanitize(str)` / render via `textContent` — all external strings must go through one of these. Injecting scraped or API text as HTML is treated as a real security bug here.
- `pointInGeometry(pt, geometry)` — the point-in-polygon test every polygon layer's `query` uses.
- `fetchJSONWithRetry(url, opts, retries)` — the standard data-fetch path (retry + failure isolation).
- `haversineMiles(...)` — for the nearest-N layers, which use straight-line proximity instead of point-in-polygon (police/fire stations via the `registerNearestPointLayer` factory; `school-site` as a bespoke block).

**A layer module** is registered via `registerLayer({ id, group, label, overlay: {load, style}, query(point, seq), render(result) })`. `group` is one of `political | safety | schools | geography`. Overlays lazy-load their boundaries on first toggle and are cached; `query` runs locally against the cached geometry. Families of similar layers are built by factory helpers (`registerPolygonLayer`, `registerSchoolZone`, `registerCpsNetwork`, `registerIlgaChamber`, `registerNearestPointLayer`) — follow the existing factory when adding a sibling. The factories derive each layer's hover-popup identity (`hoverName`) from the same properties its card reads, so the two surfaces can't disagree; a bespoke `registerLayer` block declares `hoverName(feature)` explicitly. Optional contract field `pointOfInterest(result) => {label, address} | null` drops a geocoded map pin (used by the school-zone layers). Optional contract field `coverage(point) => boolean | Promise<boolean>` declares where a layer's data applies (location relevance): outside its coverage the layer *hides* — toggle block, card, map overlay, hover-snapshot row, relationship outlines, and query all suppressed — without touching `state.layersOn`, so `layers=` permalinks survive and the layer reappears when a selected point re-enters coverage; a throwing coverage test fails open (the layer runs as if undeclared). Chicago's city-scoped layers declare `chicagoCoverage` (ERSB tiling) and the two Cook layers `cookCountyCoverage` (CCBR tiling); layers that declare nothing behave exactly as before the field existed. Two engine loaders exist purely for metro forks and are unused by Chicago's own layers: `loadArcGISPaged` (transfer-cap paging) and `makeSocrataPointLoader` (point datasets whose coordinates live only in properties) — see `docs/METRO_EXPANSION_PLAYBOOK.md`.

**Two invariants that pervade the code:**

1. **Stale-async guard via `sequence`.** Every point selection bumps `state.sequence`. Async work captures `seq` and bails (`if (seq !== state.sequence) return;`) when a newer point has been selected. Preserve this in any code that awaits between selection and render.

2. **Per-layer failure isolation.** Each result card is independent: a layer whose data source is down shows an error + Retry *inside its own card* and never affects the others. Never let one layer's failure throw out of its `query`/`render` into shared code.

**Honesty rules (non-negotiable, enforced in review):** officeholder data is never guessed. Where no verifiable roster source exists, cards link to the official body instead of inventing a name. External strings are always sanitized or set via `textContent`.

## Cross-metro engine parity

This app is one of several sibling metro forks (NYC lives at `ThursdaysFamous/DistrictExplorer-NYC` / nyc.chidistricts.com); **Chicago is the reference implementation**. The metro-agnostic engine inside `index.html` is fenced with `/* ==== ENGINE:BEGIN <name> ==== */ … ENGINE:END` markers and must stay **byte-identical across forks**; everything city-specific those blocks reference lives in the `METRO:BEGIN config` block near the top of the script. When editing:

- Don't edit inside an ENGINE fence unless the change will be ported to every sibling fork — and port it as the **actual git diff**, never by re-describing the feature in a prompt (same prompt ≠ same code; that's exactly how the forks drifted before the fences existed).
- Region-agnostic changes land in this repo first; siblings apply the diff verbatim.
- Never inline a city-specific value in an ENGINE block — add a variable to the METRO config block instead.
- Verify with `python3 scripts/check_engine_parity.py index.html` (fence lint; `validate_index.py` also runs it) or `--against <sibling path or URL> --strict` (byte comparison). A weekly workflow (`engine-parity.yml`) compares this repo against each sibling's deployed site and opens a tracking issue on drift.
- Full protocol + the known reconciliation backlog: `docs/ENGINE_SYNC.md`.

## Data pipeline

Most layers fetch live public APIs at runtime (Chicago Data Portal / Socrata, CPD ArcGIS, Cook County GIS, Census TIGERweb, Nominatim). Layers with **no public API** ship their data as same-origin files under `data/app/`, fetched on first toggle:

- **Boundary geometry** (`school-board-districts.json`, `il-supreme-court-districts.json`, `ccbr-districts.json`) — mapshaper-simplified from the full-precision GeoJSON in `data/` (originals in `data/source/raw/`). Regenerate with `scripts/build_embedded_boundaries.py` (rare operator step). Service worker serves these **cache-first** (boundaries change ~once a decade).
- **Officeholder rosters** (`il-{senate,house}-members.json`, `congress-roster.json`, `cpd-district-info.json`, `ccpsa-district-councils.json`, `school-board-members.json`) — regenerated **weekly by CI** from scraper output. Service worker serves these **network-first** so a returning visitor never gets a stale officeholder.

**Scraper → builder pattern** (each roster has a pair): a `*_scraper.py` produces intermediate JSON, a `build_*.py` writes the `data/app/*.json` file with count guards (it refuses to write if too few records resolve). `scripts/requirements.txt` pins deps; the CPD scraper additionally needs Playwright for a Cloudflare managed-challenge fetch. Builders emit plain JSON via `json.dump` into `data/app/`, and the app renders every external string through `sanitize()`/`textContent` — together that closes the injection surface for scraped text. (The historical `js_string()`-style `</script>` + U+2028/U+2029 escaping guard existed only when data was spliced directly into the HTML; it closed a real injection bug then, and becomes mandatory again only if scraped text is ever spliced into HTML/JS — don't.)

## CI workflows (`.github/workflows/`)

- `smoke-test.yml` — runs the behaviour gate on every PR and push to `main`.
- `update-{ilga,congress,cpd,ccpsa}-roster.yml` — weekly (staggered) roster refreshes. Each re-scrapes, rebuilds `data/app/`, runs `validate_index.py`, and — if anything changed — **opens a PR rather than committing to `main`.** Officeholder data always gets a human review before it ships. Match this pattern for any new roster: never auto-commit roster changes to `main`.
- `validate-sources.yml` — monthly source-freshness check. Runs `scripts/validate_sources.py`; on any WARN/FAIL (e.g. a Socrata dataset superseded by a newer-year edition, or a shapefile source gone unreachable) it **opens or updates a single tracking issue** rather than editing anything — the job stays green, the issue is the signal. Same "surface for a human, don't auto-apply" convention as the roster PRs.

## Conventions

- Code style is ES5-flavored (`var`, `function` expressions) throughout `index.html` — match it when editing existing modules.
- The "verified" date shown in the UI is hardcoded near the boot block in `index.html`; bump it when reverifying data sources.
- This is a public-facing civic tool that explicitly disclaims legal precision — accuracy and the honesty rules matter more than feature velocity.
