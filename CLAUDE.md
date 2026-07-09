# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Chicago District Explorer: a single-file, dependency-light web app. Click a point in Chicago (or search an address) and it reports every civic district containing that point and who represents you there — wards, county/state/federal legislative districts, police districts/beats, school zones, and more. Deployed as a static site to `ChiDistricts.overberg.co` (see `CNAME`).

**There is no build step, no framework, and no server-side code.** The entire app — styles, core, and all layer modules — lives inline in `index.html` (~3,500 lines). `sw.js` is the service worker; `data/app/*.json` are runtime-fetched data files. Everything else is data pipeline, scrapers, or CI.

## Running & testing

```bash
# Run locally — any static server works; internet needed for live-API layers:
python3 -m http.server 8000    # then open http://localhost:8000/

# Behaviour gate (real Chromium boot via Playwright) — the main test:
npm install playwright@1.56.1 && npx playwright install --with-deps chromium
BASE_URL=http://localhost:8000/ node scripts/smoke_test.mjs   # serve first, then run

# Static gate (run after any data/app regeneration or app edit):
python3 scripts/validate_index.py index.html
```

`smoke_test.mjs` is a single end-to-end script, not a framework — there are no "individual tests" to select. It asserts the app boots, registers all layers, classifies a known downtown point against ground truth (school board 12, IL Supreme Court 1, Board of Review 3), and degrades to an isolated error card when a source fails. `node_modules`/`package.json` are intentionally gitignored — this repo never commits build artifacts.

`validate_index.py` is the merge gate: it confirms `index.html` passes `node --check`, still registers every layer (a drop in the `registerLayer(` count fails), embeds no dataset inline, and that every `data/app/` file is present with the expected feature/roster counts.

## Architecture: stable core + pluggable layer modules

All inside `index.html`, wrapped in one IIFE. The full contract and per-thread build log live in `docs/BUILD_PLAYBOOK_1.md`; `docs/OPTIMIZATION_PLAYBOOK.md` holds measured optimization tasks.

**Core** provides: the Leaflet map, click-to-select + debounced Chicago-bounded Nominatim geocoder, a global `state` object `{selectedPoint, sequence, layersOn, ...}`, the layer registry + result-card framework, selected-boundary highlight, and URL-hash permalinks (`#point=lat,lng&layers=ward,school-board`). A small namespace is exposed as `window.ChiExplorer` for debugging.

**Shared utilities** (reuse these; don't reinvent):
- `sanitize(str)` / render via `textContent` — all external strings must go through one of these. Injecting scraped or API text as HTML is treated as a real security bug here.
- `pointInGeometry(pt, geometry)` — the point-in-polygon test every polygon layer's `query` uses.
- `fetchJSONWithRetry(url, opts, retries)` — the standard data-fetch path (retry + failure isolation).
- `haversineMiles(...)` — for the nearest-N station layers (police/fire), which use straight-line proximity instead of point-in-polygon.

**A layer module** is registered via `registerLayer({ id, group, label, overlay: {load, style}, query(point, seq), render(result) })`. `group` is one of `political | safety | schools | geography`. Overlays lazy-load their boundaries on first toggle and are cached; `query` runs locally against the cached geometry. Families of similar layers are built by factory helpers (`registerSchoolZone`, `registerCpsNetwork`, `registerIlgaChamber`) — follow the existing factory when adding a sibling. Optional contract field `pointOfInterest(result) => {label, address} | null` drops a geocoded map pin (used by the school-zone layers).

**Two invariants that pervade the code:**

1. **Stale-async guard via `sequence`.** Every point selection bumps `state.sequence`. Async work captures `seq` and bails (`if (seq !== state.sequence) return;`) when a newer point has been selected. Preserve this in any code that awaits between selection and render.

2. **Per-layer failure isolation.** Each result card is independent: a layer whose data source is down shows an error + Retry *inside its own card* and never affects the others. Never let one layer's failure throw out of its `query`/`render` into shared code.

**Honesty rules (non-negotiable, enforced in review):** officeholder data is never guessed. Where no verifiable roster source exists, cards link to the official body instead of inventing a name. External strings are always sanitized or set via `textContent`.

## Data pipeline

Most layers fetch live public APIs at runtime (Chicago Data Portal / Socrata, CPD ArcGIS, Cook County GIS, Census TIGERweb, Nominatim). Layers with **no public API** ship their data as same-origin files under `data/app/`, fetched on first toggle:

- **Boundary geometry** (`school-board-districts.json`, `il-supreme-court-districts.json`, `ccbr-districts.json`) — mapshaper-simplified from the full-precision GeoJSON in `data/` (originals in `data/source/raw/`). Regenerate with `scripts/build_embedded_boundaries.py` (rare operator step). Service worker serves these **cache-first** (boundaries change ~once a decade).
- **Officeholder rosters** (`il-{senate,house}-members.json`, `congress-roster.json`, `cpd-district-info.json`, `ccpsa-district-councils.json`, `school-board-members.json`) — regenerated **weekly by CI** from scraper output. Service worker serves these **network-first** so a returning visitor never gets a stale officeholder.

**Scraper → builder pattern** (each roster has a pair): a `*_scraper.py` produces intermediate JSON, a `build_*.py` writes the `data/app/*.json` file with count guards (it refuses to write if too few records resolve). `scripts/requirements.txt` pins deps; the CPD scraper additionally needs Playwright for a Cloudflare managed-challenge fetch. When editing a scraper, keep its `js_string()`-style `</script>` + U+2028/U+2029 escaping — that guard closed a real injection bug.

## CI workflows (`.github/workflows/`)

- `smoke-test.yml` — runs the behaviour gate on every PR and push to `main`.
- `update-{ilga,congress,cpd,ccpsa}-roster.yml` — weekly (staggered) roster refreshes. Each re-scrapes, rebuilds `data/app/`, runs `validate_index.py`, and — if anything changed — **opens a PR rather than committing to `main`.** Officeholder data always gets a human review before it ships. Match this pattern for any new roster: never auto-commit roster changes to `main`.

## Conventions

- Code style is ES5-flavored (`var`, `function` expressions) throughout `index.html` — match it when editing existing modules.
- The "verified" date shown in the UI is hardcoded near the boot block in `index.html`; bump it when reverifying data sources.
- This is a public-facing civic tool that explicitly disclaims legal precision — accuracy and the honesty rules matter more than feature velocity.
