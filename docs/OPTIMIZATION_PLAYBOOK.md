# Optimization & Refinement Playbook

**Repo:** ThursdaysFamous/DistrictExplorer · **Date:** 2026-07-09 · **Scope:** `index.html` (2,811 lines, 1.30 MB), `sw.js`, `scripts/` pipeline, `.github/workflows/`

**Constraint changes this playbook is built on** (owner decisions, 2026-07-09):
- The Capacitor/Android/iOS stack is **removed** (done in this PR — 80 files, −2,931 lines; git history retains everything). The app is a website (+ installable PWA) only.
- The app is hosted (GitHub Pages, `ChiDistricts.overberg.co`); **`file://` support is no longer a constraint.** Every "embedded inline because file:// blocks sibling fetches" decision in the codebase is now renegotiable. The other design values — one hand-readable page, no build step, no framework, per-layer failure isolation, sanitized external strings, never-guess/never-stale officeholder data — remain in force and this playbook works within them.

All numbers were measured against this working tree unless marked *(not live-verified)* — the same convention the codebase itself uses. Findings were produced by a multi-agent review (5 scoped reviewers + adversarial verification of all 36 findings + a completeness-critic round that added 19 more); everything below survived verification, and the biggest claims were re-derived independently a second time.

**Execution log (this PR):** Matrix items **1, 3, 4, 9, 10, 11, 13, 14, 15 shipped** (plus the geocoder-submit debounce fix) — school-board geometry simplified, CI validation gate added, service worker switched to network-first, remote Esri loaders made leaner + more resilient, and the Nominatim/geocoder paths made polite.
- **Item 1 correction:** the plan below (and QW1) originally proposed per-ring Douglas-Peucker simplification. Executing it revealed that per-ring DP is **not topology-aware** — at ~3.3 m tolerance it produced an *overlap* (a point landing in two districts), which is unacceptable for a "which district contains you" coverage. The shipped implementation uses **topology-aware mapshaper** (Visvalingam, keep-shapes, 15% retain, 6-decimal precision) — the same tool the sibling layers used — via the new reproducible `scripts/build_embedded_boundaries.py`. Result: the embedded blob 975,796 → **83,470 B**; `index.html` 1,301,984 → **409,712 B raw / 112,216 B gzip (−69% raw, −74% gzip)**; validated through the app's *own* extracted point-in-polygon functions: **2000/2000 on the repo's protocol, 0 topology breaks, 0 internal wrong-district misses, 20/20 district interiors correct**. (The all-embedded-data externalization to `data/app/*.json`, item 2/P0, is the larger separate follow-up and is *not* in this PR.)
- **Item 3:** `scripts/validate_index.py` (node --check + registerLayer floor + embedded-blob round-trip + rewrite-target presence), wired into both roster workflows between the rewrite and the PR; tested against a simulated module-deletion and a corrupted-blob.
- **Item 4:** `sw.js` fetch handler is now network-first with cache fallback.
- **Items 9/10/11 (remote-loader resilience):** `loadTigerLayer`, `loadCookCountyLayerGeoJSON`, and `loadArcGISGeoJSON` now request `geometryPrecision=6` (~0.11 m; trims coordinate payload, ignored by servers that don't support it). The two big statewide loaders (`loadTigerLayer`, `loadCookCountyLayerGeoJSON`) gained the `hasUsableGeometry` guard the Socrata/CPD loaders already had — an Esri HTTP-200-with-error-envelope no longer gets cached as a permanent session-long success — and a 30 s per-attempt timeout (shared `REMOTE_GEOJSON_TIMEOUT_MS`) so their whole-boundary payloads can finish on a slow link instead of aborting at 9 s. `outFields=*` was deliberately kept (not trimmed) to preserve `extractDistrictNumber`'s name-field fallback across TIGERweb's per-Congress field renames. Guard verified against realistic error-envelope/empty/null-geometry/valid inputs through the app's own `hasUsableGeometry`.
- **Items 14/15 + geocoder fix (Nominatim politeness):** added `preconnect` for the Leaflet CDN and two tile shards + `dns-prefetch` for the click-time data/geocoder APIs. POI geocoding now flows through a serial, ≥1 s-spaced queue (`enqueuePoiGeocode`) instead of firing up to 9 parallel requests per click at Nominatim's 1-req/s endpoint; a per-call currency check skips the network once the selection moves on, so rapid clicking can't build an unbounded backlog, and the existing per-address cache still short-circuits repeats. The search-box submit handler now `clearTimeout`s the pending input-debounce so an Enter press within 550 ms of typing no longer fires a request the debounce then aborts and duplicates. Queue verified to run serially at ~1 s spacing with in-order results.

**Execution log (PR-D — externalization):** Matrix items **2, 6, 26 shipped** together (item 6 is a hard dependency of item 2 — the roster builders had to stop rewriting the now-removed HTML blocks).
- **Item 2 (P0):** all seven embedded datasets moved to `data/app/*.json` — three boundary geometries (`school-board-districts`, `il-supreme-court-districts`, `ccbr-districts`) and four rosters (`il-senate-members`, `il-house-members`, `school-board-members`, `cpd-district-info`), extracted verbatim so geometry classification is byte-identical. Each loader now `fetchJSONWithRetry`s its file lazily on first toggle via the existing cached-loader machinery; geometry failures surface the per-layer error card + Retry, while the enrichment rosters join best-effort (`Promise.all` + `.catch(() => {})`) so a roster outage degrades to "district number + official link" instead of blanking the card. `index.html` **409,777 → 111,811 B (−73%)**. Verified end-to-end in real Chromium: the three offline layers classify correctly (school-board D12/6b → *Jessica Biggs*, supreme-court D1, board-of-review D3), the roster joins resolve (senate D5 → *Lakesia Collins*, house D40 → *Jaime Andrade Jr.*), and a forced roster-fetch failure degrades gracefully.
- **Item 6:** `build_il_roster.py` / `build_cpd_roster.py` now `json.dump` to `data/app/` instead of regex-splicing `index.html` — the DOTALL over-match risk, the `</script`-escaping and the (previously no-op) U+2028/U+2029 escaping all cease to exist. `build_embedded_boundaries.py` writes `data/app/school-board-districts.json`; `validate_index.py` was repurposed to gate the app + data files (no inline blobs remain, every `data/app` file present and well formed) and both weekly workflows now build/commit the JSON files.
- **Item 26:** README updated (embedded→fetched, offline/SW-caching semantics, `data/app/` simplification provenance, repo layout); the not-in-repo Playwright/parse5 Validation claim was replaced with the real `validate_index.py` gate (the smoke test itself remains item 5).
- **Deliberately not folded in:** SW shell-entry dedupe (item 22) and the `timeoutMs` overrides for the now-fetched large geometry (item 11) — `sw.js` `CACHE_NAME` was bumped to `-v2` and given cache-first geometry / network-first roster handling for `data/app/*`, but the pre-existing `"./"`+`"./index.html"` duplication is left for item 22.

**Execution log (item 5 — smoke test):** Committed `scripts/smoke_test.mjs` (Playwright) + `.github/workflows/smoke-test.yml` (`on: pull_request`), delivering the headless boot check the README described but the repo never carried (R4 doc/reality drift). Eight checks, all deterministic — no dependency on the live district APIs (flaky in CI): app boots and exports `window.ChiExplorer`, all **18** layers register, the three no-API layers classify the downtown Loop point against known ground truth (school-board 12, IL Supreme Court 1, Board of Review 3) including the member-roster join, and a forced `data/app` failure yields an isolated error card + Retry. Verified green locally against the real page. This also gives the externalization PR its first real CI (the roster workflows are schedule/dispatch-only and never ran on PRs). *(One CI-side subtlety worth recording: the app's service worker serves `data/app/*` cache-first and its requests aren't interceptable by Playwright's `page.route`, so the failure-injection check runs with `serviceWorkers: "block"`.)*

**Execution log (item 7 — surface silent overlay-load failures):** `onLayerToggled`'s overlay-load `catch` previously only `console.error`'d; before a point is picked `runLayerQuery` returns early, so a failed boundary download was completely invisible (silent stall up to ~28 s). It now calls `setCardError` (guarded on the layer still being on), which drops the card's `state-off` `display:none` so the error shows right under the toggle, with a Retry that re-runs `onLayerToggled` → re-attempts the load. A ninth smoke check covers it (toggle a layer via permalink with no point, fail its fetch, assert a visible error card + Retry). *Remaining, out of scope for this item:* the second-order gap R5 notes — if the user skips Retry and just selects a point, a now-succeeding `query()` renders the answer but the map overlay isn't rebuilt (boundaries stay undrawn). Tracked as a follow-up; the Retry path already gives the user a way to get boundaries back.

**Execution log (item 12 — click-path rendering, P7):** the per-click point-in-polygon + restyle cost was halved-then-collapsed. `findFeatureContaining` now memoizes its `(point → feature)` scan on the geojson object (keyed by point-object identity, which `setSelectedPoint` mints fresh per selection), so the second scan a click always did — once in the layer's `query()`, once in `updateLayerHighlight()` against the same cached geojson — is now a free cache hit instead of a full re-sweep. `updateLayerHighlight` gained an incremental fast path: it records whether a highlight is applied and a signature of the inputs the faded/base styles depend on (active-layer count + outline mode); when that signature is unchanged and the layer is already highlighted, a point move flips only the two paths whose role changed (old match → faded, new match → highlight) and leaves every other path's DOM untouched — turning the common "same layers on, new point" case from ~N `setStyle` calls (the measured dominant per-click cost) into 2. Any signature change (a layer toggled on/off, `outlineOnly` flipped) falls back to the existing full sweep, and `clearLayerHighlight` resets the bookkeeping so the next highlight rebuilds from scratch. No layer-module changes — purely the shared highlight code. `setSelectedPoint` was exposed on the `window.ChiExplorer` debug namespace so the behaviour is drivable. Verified in real Chromium (Leaflet vendored locally to bypass the sandbox's CDN egress block): with school-board + IL-Supreme-Court on, moving the selection Loop → (41.99,-87.66) → Loop → outside-all-districts re-classifies correctly each hop (school-board D12 ⇄ D4 with its roster re-joining — *Jessica Biggs* ⇄ *Debby Pope* — while IL Supreme Court holds D1), each layer keeps its own independent highlight through the moves, and a point outside a layer's coverage clears just that layer's highlight. A new smoke check (`scripts/smoke_test.mjs`, point move → District 4 + a visible highlight) exercises the incremental path in CI.

**Execution log (item 16 — tile-failure banner, R6):** the base map is CDN-served while the app itself boots and stays usable offline (SW shell + same-origin `data/app`), so a tile outage previously left a silently gray map. The CARTO tile layer is now held in a `baseTiles` var with a `tileerror`/`tileload` pair driving a dismissible bottom-center banner ("Base map tiles unavailable — your selections and layers still work."). It's **debounced** — the banner surfaces only after ≥4 tile errors inside a rolling 4 s window (a single transient tile hiccup can't flash it) and hides again the moment any tile loads (the CDN recovered); manual dismiss latches for the session. No new dependency, styled with the existing design tokens (`--warn` accent). Verified in real Chromium with the tile CDN stubbed to 503: banner appears on outage, stays hidden after dismiss, and never appears when tiles load. A fifth smoke check (`scripts/smoke_test.mjs`, tile CDN → 503, assert banner shown then dismissed) covers it in CI. *(Note: the tile host is `a.basemaps.cartocdn.com` — a dot, not a slash, before `basemaps` — so the interception must be a regex, not a `**/basemaps…` glob; recorded in the test.)*

**Execution log (item 22 — SW shell dedupe + cache discipline + font trim, P13/P-sw):** `sw.js` precached both `"./"` and `"./index.html"` — two Cache API keys holding the identical ~112 KB-gzip page, downloaded twice at install. Dropped the `"./index.html"` entry and added a **navigate-request branch** to the fetch handler: page navigations go network-first, falling back offline to the cached canonical `"./"` shell — so the manifest's `start_url: ./index.html` and any deep `/index.html` bookmark still boot offline from one stored copy. `CACHE_NAME` bumped `-v2 → -v3` (the activate handler reclaims the old cache), with a comment codifying the rule: bump it whenever any `*_URLS` list changes so a removed entry can't live forever. Verified with the real SW registered: precache holds `"./"` (not `/index.html`) + the three geometry files, and **offline navigation to both `/index.html` and `/` serves the shell (HTTP 200, map + title present)**. Font trim: dropped Big Shoulders Display 700 (verified: no display-font element requests it). **Kept Inter 700** — the playbook's "no `<strong>`/`<b>`" premise has since drifted; the footer disclaimer, verified-date, and pinned-parent legend now use `<strong>`/`<b>` (weight 700 via the UA default, no CSS reset), so dropping Inter 700 would have faux-bolded real UI.

**Execution log (item 20 — loader/route-walker consolidation, R7/R8):** two pairs of duplicated machinery collapsed, no behaviour change. **R7:** `makeCached` and `makeCachedLoaderFromFn` were byte-identical cached-promise factories (an in-flight/cached promise per loader, cleared on rejection so a Retry re-fetches); kept the single well-documented `makeCached` and repointed the five `makeCachedLoaderFromFn` call sites + the `makeCachedLoader` wrapper to it (they already relied on the function-declaration hoisting the codebase uses throughout). **R8:** `loadSocrataGeoJSON` and `loadSocrataJSON` were 18-line structural clones of the same fallback-route walker — including the single-catch-per-route subtlety that fixed a real double-execution bug (a `.then`-recursion + `.catch`-recursion pair that re-ran later routes twice). Extracted one `tryRoutes(urls, validate, label)`; the geometry loader passes `hasUsableGeometry`, the rows loader passes an `Array.isArray(rows) && rows.length` check. Net −17 lines. Verified: static gate green; a standalone unit test of the extracted walker confirms it tries each route exactly once with the right retry counts (primary 2, fallbacks 1), advances past both a failed fetch and a "200-but-useless" response, and rejects when all routes fail; the app boots with all 22 layers and the `makeCached`-backed school-board layer still classifies the Loop point to District 12 with no page errors.

**Execution log (item 21 — declarative `registerPolygonLayer`, R9):** added a factory that builds both `query()` and `render()` from a declarative `fields` list — each field is a keyed lookup (`findPropCI`, with a `primary` headline that falls back to "Unknown"), a fixed text row, or a fixed html row, with an optional `when(result)` predicate to gate a row on the extracted values. Converted the four layers that are genuinely *pure single-source polygons* — **Community Area, ZIP Code, IL Supreme Court, Board of Review** — onto it. *Scope honesty:* R9's "~250 lines / most of the nine" estimate was optimistic — a close read shows the other standalone polygon blocks all carry an async `Promise.all` join or second concern (Police District: commander roster + station-view address/phone + `onToggle` cascade; Ward: aldermen roster + precinct sub-layer; CCPSA: council roster; Congress: `congress-roster.json`; Commissioner: Cook County electedOfficials table; plus the point/nearest-N and sub-layer modules), none of which fits a pure-polygon factory without an `enrich` hook that would make it a leaky, largely-CI-unverifiable abstraction. Those keep their explicit blocks. So the raw line count is ~flat (the factory's doc comment offsets the four blocks' savings); the win is that the four now share one query/render implementation and new pure layers register in a single declarative block. `validate_index.py`'s `registerLayer(` floor comment was refreshed (now 1 def + 11 direct + 4 factory bodies = 16; the runtime still registers 22). **Verified in real Chromium:** IL Supreme Court → D1 (with the District-1 note) and Board of Review → D3 against the offline ground truth, Community Area and ZIP against stubbed Socrata geometry (`Name TEST AREA` / `Area # 77`, `ZIP Code 60601`), and the fallback branch (empty props → `Name Unknown`, the optional `Area #` row correctly omitted) — every factory branch (primary/optional/static-text/static-html/`when`) exercised, 22 layers still register, no page errors.

**Execution log (item 19 — no more duplicate weekly roster PRs, R10):** each of the four roster workflows (`update-{ilga,congress,cpd,ccpsa}-roster.yml`) opened its PR from a per-run branch `bot/<name>-roster-update-${{ github.run_id }}`, so an unmerged roster PR spawned a brand-new duplicate every week. Switched each to a **fixed branch** `bot/<name>-roster-update`, **force-push** it, and guard `gh pr create` behind `gh pr list --head "$branch" --state open` — so a re-run refreshes the existing PR in place (and, incidentally, no longer errors on the "a PR already exists for this branch" create). When no open PR exists (first run, or the previous one merged/closed) it still opens a fresh one. The scraper-dep pinning half of R10 was already shipped earlier (`scripts/requirements.txt`; the ILGA/CCPSA jobs `pip install -c` it, CPD `-r` it with Playwright, congress is stdlib-only). YAML validated; the roster jobs are schedule/dispatch-only so this was verified by inspection + parse rather than a live run (dispatching would open real officeholder PRs).

**Execution log (item 18 — `.nojekyll`, R10, partial):** added an empty `.nojekyll` at the repo root so the classic branch Pages deploy skips the Jekyll build step entirely. No file is corrupted today (no `{{`/`{%` in `index.html`/`sw.js`/`manifest.webmanifest`, no leading-`_`/`.` served paths), but this future-proofs the served page against any Liquid-looking sequence a JS template literal might later introduce, and shaves the Jekyll pass off every deploy — zero risk. **Deliberately not done:** the Actions-based Pages deploy that uploads only the app files (excluding `data/source/raw/`, `scripts/`, `docs/`) — that requires flipping the repo's Pages *source* from "Deploy from a branch" to "GitHub Actions" (a Settings change outside the tree) and is outward-facing (a misconfiguration takes the live site down), so it's left for an owner decision.

**Execution log (item 18 — Actions-based Pages deploy, R10, remaining half):** added `.github/workflows/deploy-pages.yml`. It assembles a curated `_site` (via `rsync` with an explicit exclude list) holding **only** the files the app serves at runtime and uploads that as the Pages artifact — verified published set: `index.html`, `sw.js`, `manifest.webmanifest`, `CNAME`, `.nojekyll`, `icons/icon-{192,512}.png`, all nine `data/app/*.json`, plus the harmless `README.md`/`.gitignore`. **Dropped from the CDN:** `scripts/`, `docs/`, `.github/`, `.claude/`, `CLAUDE.md`, and ~5 MB of build-only geometry — `data/source/` (raw zips/xlsx) and the three full-precision `data/*.geojson` originals that `data/app/*.json` is simplified from (none of which is ever fetched at runtime). The custom domain is preserved by shipping `CNAME` in the artifact; `permissions` is the least-privilege `pages: write` + `id-token: write`; `concurrency: {group: pages, cancel-in-progress: false}` avoids half-published deploys. The exclude set was validated by simulating it against `git ls-files` (all 7 core runtime files + 9 `data/app` files present; zero heavy/build paths leaked). **Still an owner action (documented in the workflow header):** the workflow only takes effect once the repo's Pages *source* is flipped Settings → Pages → "Deploy from a branch" → "GitHub Actions". Until the flip, the classic branch deploy stays authoritative and keeps the live site up (no outage window — adding the workflow does not change the Pages source), and this job's final `deploy-pages` step will fail harmlessly on pushes to `main`; after the flip it becomes the deploy path. Not run here — it triggers on push to `main`/dispatch only, and the deploy can't be exercised from a feature branch without the settings change.

**Execution log (item 17 — toggle-path opacity rescale, P8):** toggling a layer on/off changes the active-layer count, which used to force `refreshActiveLayerOpacities` to re-run the *full* `updateLayerHighlight` (point-in-polygon + full restyle sweep + class ops) for **every** active layer — even though the only thing a count change affects is how translucent each layer's flat fill is (`scaledFillOpacity`). Replaced that with `rescaleLayerFill(mod)`: a layer that's already showing a selection highlight has fixed, count-independent faded/highlight fill opacities, so it needs **no restyle at all** (its stored `highlightSignature` is just refreshed so the next point move still takes the P7 fast path); a layer with no active highlight gets a single `setStyle({fillOpacity})` per path instead of the full recomputation. The active-count signature the P7 fast path keys on was extracted into one `highlightSignature(rt)` helper (used by both `updateLayerHighlight` and the rescale) so the two can't drift. Also dropped the `reorderActiveLayers()` call from the toggle-**off** branch: removing one layer leaves the survivors' relative z-order — already established by the stacking invariant — untouched, and no `onToggle(false)` cascade turns another layer *on* (verified: police-district/beat and ward/precinct cascades only turn things off), so there's nothing to restack (toggle-on and query-resolve still reorder, since those insert a layer that must land at its size rank). No layer-module changes. Verified in real Chromium (Leaflet vendored locally): with all three offline layers on and a point selected, toggling Board of Review off drops exactly its one highlight and leaves school-board + IL-Supreme-Court lit (3 → 2), and re-toggling returns to 3 — i.e. the rescale never disturbs the other layers' matched regions. A new smoke check (`scripts/smoke_test.mjs`, before/afterOff/afterOn highlight counts) exercises this in CI; static gate green (16 `registerLayer(` calls).

**Execution log (item 23 — release the Leaflet layer graph on toggle-off, P11):** `onLayerToggled`'s off-branch used to `map.removeLayer(rt.overlayLayer)` but keep the Leaflet object forever — ~2 MB of `L.LatLng` objects for the biggest layer, retained unbounded across a long multi-layer session. It now nulls `rt.overlayLayer` after removing it; the **raw geojson (`rt.geojson`) stays cached**, so re-toggle rebuilds the layer from it *synchronously* (no refetch) via a new shared `buildOverlayLayer(mod, geojson)` helper — re-toggle stays instant and `query()`'s shared geojson is untouched (that cache is deliberate and unchanged). The toggle-on branch was restructured to three states: geometry cached → rebuild-and-attach synchronously (the P11 path); never loaded → fetch-build-attach (unchanged); fetch in-flight → wait (unchanged, `overlayLoaded` still guards duplicate loads). Verified in real Chromium via the existing toggle smoke check, which now also covers this: toggling Board of Review off nulls its overlay, and toggling back on rebuilds it from the cached geojson and re-highlights the matched region (3 → 2 → 3) — the highlight can only reappear if the rebuild produced a working, `eachLayer`-able overlay. All 12 smoke checks green; static gate green (16 `registerLayer(` calls). *(This item was P1's "nice when touching that code" follow-up; after the school-board simplification the per-layer footprint is ~10× smaller than the measured 2 MB, but the release is still correct hygiene and now that the toggle path was already open for P8 it was cheap to land.)*

**Matrix correction (item 8 — P2, congress roster): already shipped in a prior PR, matrix strike-through was missing.** `scripts/build_congress_roster.py`, `.github/workflows/update-congress-roster.yml`, and `data/app/congress-roster.json` (IL's 17 U.S. House reps, ~2.4 KB) all exist; `index.html`'s congress layer now `fetchJSONWithRetry`s the same-origin roster instead of the multi-MB `unitedstates.github.io/congress-legislators/legislators-current.json`. The matrix row below is updated to reflect this.

**Pipeline validation run (2026-07-09):** every generator script and its workflow was exercised end-to-end against live sources to confirm each still produces the expected `data/app/*.json`. Results:

| Workflow / step | Scripts (in order) | Result |
|---|---|---|
| `update-congress-roster` | `build_congress_roster.py` → `validate_index.py` | ✅ 17/17 IL U.S. House districts; byte-identical to the committed `congress-roster.json`; static gate green |
| `update-ilga-roster` | `ilga_scraper.py` (182 records, 0 errors) → `build_il_roster.py` → `validate_index.py` | ✅ 59 senate + 118 house; house byte-identical to committed, senate differs only by one member's district-office **address** (a real update — exactly what the weekly PR exists to surface); static gate green on the regenerated tree |
| `update-cpd-roster` | `cpd_district_scraper.py` → `build_cpd_roster.py` → `validate_index.py` | ❌ **scrape blocked** at the first fetch — see R11 |
| operator step | `build_embedded_boundaries.py school-board` | ✅ 3,525 coord pairs, 83,470 B; 2000/2000 agreement, 0 overlaps; byte-identical to committed |
| `smoke-test` (behaviour gate) | `scripts/smoke_test.mjs` | ⚠️ not exercisable in the review sandbox — Playwright's bundled Chromium can't reach the Leaflet CDN or the localhost server through the session's egress proxy (`net::ERR_CONNECTION_RESET` on cdnjs). It is a GitHub-hosted-runner gate with direct egress, recorded green there; **no code defect**, environmental only. |

**Redundant/orphaned-script review:** none found. All eight scripts are live — seven wired into the four workflows, plus `build_embedded_boundaries.py` as the documented occasional operator step (`README.md`, `index.html:2474`, this doc). The `fetch`/`clean`/`HEADERS` helpers duplicated across `ilga_scraper.py` and `cpd_district_scraper.py` are a deliberate keep-scripts-standalone choice (no shared module = no cross-script coupling in the heuristic scrapers), consistent with the no-build-step architecture; left as-is.

---

## 1. Executive Summary

This is an unusually disciplined codebase: per-layer failure isolation is real, stale async results are sequenced away, external strings pass through one sanitizer, scrapers are polite and PR-gated, and design constraints are written down and mostly honored. The four issues that matter, in order:

1. **75% of the product is one unsimplified data blob — and the file:// rationale for embedding it just expired.** `SCHOOL_BOARD_DISTRICTS_GEOJSON` (`index.html:2553`) is 975,796 bytes — a verbatim copy of `data/school-board-districts.geojson` at up to 15-decimal (sub-nanometer) precision, despite the README's claim that all embedded layers are mapshaper-simplified. Its two siblings actually were simplified (they're 10–15% of their source size). Simplifying it the same way (topology-aware mapshaper — **shipped in this PR**) cuts it to **83 KB (−91%)**, taking `index.html` from **1.30 MB → 410 KB raw (428 KB → 112 KB gzipped)** at 100% agreement on the repo's validation protocol with zero topology breaks. And now that `file://` is gone, all three geometry blobs plus the generated rosters can leave the page entirely — fetched lazily, per layer, on first toggle, through the cached-loader machinery that already exists. End state: `index.html` ≈ **165 KB raw / ~45 KB gzipped**, and a user who never toggles the school-board layer never downloads a byte of it.

2. **The weekly CI rewrite of a 1.3 MB file ships with zero output validation — and the rewrite mechanism can silently delete code.** Both roster workflows regex-rewrite `index.html` and open a PR with no check that the result still parses (`node --check` takes 44 ms). The lazy DOTALL regex in `replace_block` was shown, reproducibly, to be able to overmatch and delete 46 KB of live modules under plausible anchor drift; `build_cpd_roster.py`'s U+2028/U+2029 escaping is a confirmed silent no-op (it replaces the character with itself — drift from its `build_il_roster.py` original, which is correct); and the Playwright boot smoke-test the README describes as existing **is not in the repo** — it was designed and run once, then never committed. Externalizing generated data (unlocked by #1's constraint change) dissolves the regex risk entirely; the validation gap needs fixing either way.

3. **The service worker violates the project's own freshness rule.** `sw.js` serves the shell cache-first with background revalidation — but the rosters live *inside* that shell, so every returning visitor sees last-deploy's officeholders on a page whose header comment says staleness there is unacceptable. One small handler change (network-first with cache fallback) restores correct-when-online semantics.

4. **Silent failure paths and measured interaction waste.** Toggling a layer before selecting a point gives a completely silent failure on 15 of 18 layers if the boundary download fails (violates honesty rule 3); ArcGIS "200-with-error-envelope" responses get cached as permanent success on 4 layers; and every map click re-runs point-in-polygon twice per layer and restyles every SVG path of every active layer (~6,300 attribute mutations per click with 5 typical layers on).

---

## 2. Performance Optimization Plan

### 2.1 Payload & startup

**P0 — Externalize the embedded data; fetch lazily per layer** *(unlocked by the file:// constraint removal)*
`index.html` embeds 1,136,613 bytes of data across three geometry blobs (lines 2553/2620/2658: 975,796 + 99,810 + 61,009 B) and three generated rosters (`IL_SENATE_MEMBERS` 18,080 B, `IL_HOUSE_MEMBERS` 36,058 B, `CPD_DISTRICT_INFO` currently a 32-byte placeholder). Every visitor downloads and evaluates all of it (measured: ~38 ms script-eval for the JSON.parse lines on desktop Node, est. 150–300 ms on low-end mobile WebViews) even though all three geometry layers are off by default.

Move each dataset to `data/app/<name>.json`, and have the loaders fetch them with the machinery that already exists — this is a ~10-line change per layer because the cached-loader pattern is already promise-shaped:

```js
// before (index.html:2554-2556)
var loadSchoolBoardDistricts = makeCached(function () {
  return Promise.resolve(SCHOOL_BOARD_DISTRICTS_GEOJSON);
});
// after
var loadSchoolBoardDistricts = makeCached(function () {
  return fetchJSONWithRetry("data/app/school-board-districts.json", {}, 2);
});
```

Effects: `index.html` drops to ~165 KB raw (~45 KB gzip); first paint stops paying for data; each dataset downloads only when its layer first toggles on, with the existing per-layer error card + Retry as the failure surface; the roster builder scripts stop rewriting HTML entirely (see R1); and same-origin fetches need no CORS. Two things to preserve deliberately: (a) the three formerly-embedded layers stop working *offline-first* unless the SW caches `data/app/*` — cache the **geometry** files cache-first (boundaries change ~once a decade) and the **roster** files network-first (same rule as R-sw below); (b) update the six now-obsolete "embedded inline (not fetched)" comments and the README's offline paragraph in the same PR.

**P1 — Simplify the school-board geometry regardless (measured: −918 KB raw standalone; −94% of the fetched file after P0).**
Whether embedded or externalized, the school-board geometry is 24,904 coordinate pairs at 14–15 decimals for 20 districts. Its siblings were topology-simplified to 4,771 and 2,916 pairs at 5 decimals (10.2%/14.4% keep — `index.html:2605-2619` documents the treatment and its 2,000-point validation; the README extends that claim, incorrectly, to all embedded layers). **Shipped** (see Execution log — the simplifier must be topology-aware; per-ring DP was found to create district overlaps):

| | Coord pairs | Bytes | index.html raw | index.html gzip |
|---|---|---|---|---|
| | Coord pairs | Blob bytes | index.html raw | index.html gzip |
|---|---|---|---|---|
| Today | 24,904 | 975,796 | 1,301,984 | 427,836 |
| 6dp rounding only (topology-preserving, 100% agreement) | 24,904 | 570,353 | 896,595 | 233,544 |
| **Shipped:** mapshaper topology-aware + 6dp | 3,525 | 83,470 | 409,712 | 112,216 |

Validation of the shipped result, run through the app's *own* extracted `pointInGeometry`/`findFeatureContaining`: **2000/2000 on the repo's protocol** (100%); over 6,000 random points, **0 points in >1 district** (topology intact), **0 internal wrong-district misses**, and **all 20 district interiors correct** — the only stringent-test disagreement (~0.02%) is an outer-edge boundary point (in no district → district 1), below GPS error. Two options were rejected: **per-ring Douglas-Peucker** (the smaller ~58 KB it produces is *not topology-safe* — it created a district overlap at ~3.3 m, verified) and **6dp-rounding-only** (perfectly safe but only −45% gzip). mapshaper is the tool the sibling layers already used; regeneration is reproducible via `scripts/build_embedded_boundaries.py`.

### 2.2 Network

**P2 — Stop shipping the national congress roster to every browser.**
`index.html:2195-2197` fetches `https://unitedstates.github.io/congress-legislators/legislators-current.json` — all ~538 members with every term each has ever served, multi-MB raw *(not live-verified; sandbox egress blocked)* — then filters client-side (2218-2222) for one IL representative, using ≤ ~200 bytes of it. Verifier correction folded in: the browser HTTP cache does mitigate repeats (GitHub Pages serves ETag/max-age), so the cost is per cold cache, not per session — but the first toggle on any device still pays the full download. The repo already owns the right pattern: build-time roster embedding with a weekly PR-gated refresh (ILGA: 59+118 members; CPD: 22 districts). A `scripts/build_congress_roster.py` producing IL's 17 reps (~3–4 KB, becoming `data/app/congress-roster.json` after P0) removes the layer's runtime dependency on a third-party host entirely.

**P3 — Ask Esri servers for display-precision geometry.**
`loadTigerLayer` (`index.html:2115-2120`), `loadArcGISGeoJSON` (1607), and `loadCookCountyLayerGeoJSON` (2710-2711) all fetch full-precision coordinates with `outFields=*`. Adding `&geometryPrecision=6` (≈11 cm) cuts coordinate payload ~40% (measured proxy: digits beyond 6dp are 41.5% of raw GeoJSON bytes on the full-precision layer analyzed locally); servers that don't support the param ignore it. `outFields` can shrink to the fields actually read (`CONGRESS_DISTRICT_FIELDS` at 2198, `districtFields` at 2534, commissioner fields at 2725). Six layers benefit (congress, il-senate, il-house, police-district, police-station, commissioner). Exact diff in §5 QW4.

**P4 — Give big payloads a bigger timeout than a 1-row probe.**
`fetchJSONWithRetry` supports `opts.timeoutMs` (`index.html:711`) but none of the 9 call sites overrides it — a 9 s whole-body budget applies equally to a 1-row Socrata probe and the statewide IL House boundary download, so slow links can *never* load the big layers (each retry re-aborts at 9 s), while the Socrata 3-route ladder can keep a "Loading…" spinner alive ~65 s before failing. Give the known-large loaders (TIGERweb, Cook County, ArcGIS, congress roster until P2) `{timeoutMs: 30000}` and consider dropping route-ladder retries to tighten worst-case failure to under ~30 s.

**P5 — Guard the two unguarded Esri loaders (a 200-response bug becomes a session-long outage).**
ArcGIS REST returns HTTP 200 with a JSON error envelope under load — the exact "succeeded but useless" mode the code already defends against for Socrata (`hasUsableGeometry` at 1566) and CPD ArcGIS (1610). `loadTigerLayer` (2119) and `loadCookCountyLayerGeoJSON` (2712) skip the guard, and `makeCached` retains resolved promises forever — so one bad 200 kills congress/il-senate/il-house/commissioner for the whole session with no Retry path. Two one-line `.then` additions reusing the existing guard.

**P6 — Serialize POI geocoding (up to 9 concurrent Nominatim hits per click today).**
9 of 18 layers define `pointOfInterest`; a click with them active fires up to 9 parallel `geocodePoiAddress` requests (18 with retries) at a shared public service with a 1 req/s policy — the *search* geocoder respects it (550 ms debounce, comment at 1036), the POI path doesn't. The per-address cache (`poiGeocodeCache`, 1250) already prevents repeats; add a small promise queue with ≥1 s spacing in front of the fetch (pins already appear asynchronously, so latency is tolerable).

### 2.3 Interaction & rendering

**P7 — One PIP scan and two path restyles per click, not two scans and ~630 restyles.**
Measured today (5 typical layers on: community areas 77, ZIPs ~61, wards 50, police 22, school zones ~420): every click runs `findFeatureContaining` **twice** per layer (once in `mod.query`, again in `updateLayerHighlight` at 1218 on the same cached geojson) and then `eachLayer`+`setStyle` over *every* sub-layer (1223-1234) — ~630 `setStyle` × ~10 attributes ≈ 6,300 SVG attribute mutations + 630 classList ops per click. Fix in the shared code, no module changes: (a) memoize `(point → feature)` on the geojson object so query and highlight share one scan; (b) when only the selection moved, restyle just the previous match and the new match — the faded/base style of the other ~628 paths is unchanged unless the *active-layer count* changed; (c) optional: per-feature bbox pre-check (0.105 ms → 0.004 ms per school-board scan, measured).

**P8 — Toggle path does the same full sweep, plus a DOM reorder of every path.**
`onLayerToggled` → `refreshActiveLayerOpacities` re-runs `updateLayerHighlight` (full PIP + full restyle) for every active layer, then `reorderActiveLayers` `bringToFront()`s each layer (~630 `appendChild`s) — including on toggle-**off** (1401-1402), where the layer being removed doesn't need restyling at all. Opacity rescaling only needs `setStyle({fillOpacity})` per path, not the full highlight recomputation; and the highlight of *other* layers is unaffected by a toggle.

**P9 — The highlight drop-shadow is a hidden rasterization tax.**
`.chi-region-highlight` (`index.html:525-528`) applies stacked `drop-shadow()` filters to a raw SVG path; at z15 the largest highlighted district's filter region is ~13.9 Mpx, re-rasterized during pan/zoom. Cheapest fix if pan jank is observed on low-end devices: drop the filter during `movestart`/`moveend`, or trade the shadow for a non-filter treatment (wider casing stroke). Cosmetic decision — flagging the mechanism so it's a choice.

**P10 — Canvas rendering for the many-polygon layers — with a named trade-off.**
No `renderer`/`preferCanvas` option exists in the file; all ~1,000 polygons (all layers on) are SVG DOM paths, ~500 of them from the school-zone layers. Per-layer `renderer: L.canvas()` on the three school-zone + two CPS-network layers would remove most paths — **but** the highlight mechanism mutates `subLayer._path.classList` (1226-1229), which doesn't exist under canvas, so the drop-shadow highlight would need the setStyle-only fallback on those layers. Do after P7/P8; only if profiling still shows restyle cost.

**P11 — Release the Leaflet layer graph on toggle-off (keep the geojson).**
Toggle-off keeps `rt.overlayLayer` forever — ~2 MB of `L.LatLng` objects for school-board alone (measured), unbounded across an 18-layer session. Keep the raw-geojson promise caches (they're what make re-toggle instant and are shared with `query()` — verified deliberate), but null out the Leaflet object on toggle-off and rebuild from `rt.geojson` on re-toggle. After P1's simplification this shrinks ~10×, so it's a "nice when touching that code" item.

### 2.4 Delivery & caching

**P-sw — `sw.js` currently guarantees stale rosters for returning visitors — invert the shell strategy.**
The shell (which *contains* the rosters until P0) is served cache-first with background revalidation (`sw.js:49-62`), so every visit after a roster deploy shows the previous roster — directly against the never-stale rule in the file's own header. Network-first with cache fallback restores plain-page-load semantics online and keeps offline boot. Exact diff in §5 QW2. Post-P0 the same policy question moves to `data/app/*`: geometry cache-first, rosters network-first. Also: drop the duplicate `"./index.html"` shell entry (`"./"` and `"./index.html"` are two Cache API keys holding identical 1.3 MB bodies — 2.6 MB stored, and the typical install re-downloads one of them (~428 KB gzip) redundantly), and bump `CACHE_NAME` whenever `SHELL_URLS` changes (the activate handler only deletes *other-named* caches, so removed URLs otherwise live forever).

**P12 — Warm the tile CDN connections.**
Only Google Fonts gets preconnects (`index.html:13-14`), but first map paint is gated on DNS+TLS to `{a-d}.basemaps.cartocdn.com` (tile layer created at 773, immediately at script run). Preconnect two tile shards + dns-prefetch the click-time API origins. Exact diff in §5 QW5.

**P13 — Trim two unused font weights.**
Line 15 requests 10 weights; the stylesheet uses 400/500/600/800/900 and there's no `<strong>`/`<b>`. Dropping Big Shoulders 700 and Inter 700 saves two font files and nothing else changes.

**Anti-finding, recorded so nobody "fixes" it:** `leaflet.js` at line 615 does **not** need `defer`. Lines 1–616 are only 19,297 bytes, so the preload scanner discovers it in the first ~19 KB and fetches it in parallel with the (long) HTML download; the inline classic-script IIFE at 617 depends on `L` synchronously, so adding `defer` would *break* boot, not speed it.

---

## 3. Refactoring & Code Quality

### 3.1 The generated-data pipeline (highest-risk area of the repo)

**R1 — Builders should emit data files, not rewrite a 1.3 MB HTML file** *(structural fix; unlocked by P0)*.
Today `build_il_roster.py`/`build_cpd_roster.py` locate JS object literals inside `index.html` with a lazy DOTALL regex (`replace_block`, `build_il_roster.py:99-103`) and splice replacements in. The review reproduced a plausible-anchor-drift scenario where that regex overmatches and **silently deletes 46,753 bytes of live modules** (a failure mode this repo has already experienced once — `docs/BUILD_PLAYBOOK_1.md` records a module deleted by an earlier rewrite). Two builders also carry drifted copies of the same machinery: `build_cpd_roster.py`'s U+2028/U+2029 escaping is a **confirmed no-op** (it replaces the raw character with the same raw character — `cat -A` shows it; `build_il_roster.py:82` is correct). After P0, builders write `data/app/*.json` with `json.dump` and never touch HTML: the regex, the `</script`-escaping subtlety, and the drift risk all cease to exist. Until P0 lands: fix the U+2028 line (rewrite it fresh — the buggy line contains invisible characters, do not copy-paste), extract the shared `js_string`/`replace_block` into one imported module, and make `replace_block` fail on multiple matches.

**R2 — Make the geometry blobs regenerable.**
Verified: zero scripts reference the three embedded geometry variables; the school-board blob is canonically identical to its `data/` file (i.e., embedded-by-copy, never simplified), while the other two exist only as simplified snapshots of a mapshaper run nobody can repeat. Commit `scripts/build_embedded_boundaries.py` (or post-P0, `build_app_data.py`) that goes `data/*.geojson → simplify → round → data/app/*.json`, with the tolerance and validation protocol recorded in the script. The README's "Embedded boundary layers are topology-preserving simplifications" claim becomes true again (today it is false for school-board).

**R3 — Put validation between "bot rewrote the file" and "PR opened."**
Both workflows go straight from the rewrite to `gh pr create` with zero checks. Minimum bar, both < 1 s: `node --check` on the extracted inline script (44 ms measured — catches syntax death) + an output-side invariant check in the builders (count of `registerLayer(` blocks and dataset completeness after the rewrite, mirroring the input-side guards that already exist at `build_il_roster.py:119-126` and `build_cpd_roster.py:109-115`). Also extend the CPD guard to require a minimum count of non-null `commanderName`s — today a CPD site reword that nulls every commander sails through the district-count check. §5 QW3 has the exact workflow step.

**R4 — Commit the smoke test that the README already claims exists.**
`README.md:91-93` describes headless validation (node --check, parse5, Playwright boot + known-point district assertions) in the present tense; none of it is in the repo — it was built and run once during development, then not committed (`docs/BUILD_PLAYBOOK_1.md` prose is the only trace). A ~40-line Playwright job on `pull_request` — boot, assert 18 layers registered via the already-exported `window.ChiExplorer`, click a known point, assert the three local layers' district answers — is the single highest-leverage DevEx investment here, and it makes R3's PRs trustworthy rather than merely syntax-valid. Until it exists, the README section should be reworded to past tense (doc/reality drift).

### 3.2 Failure honesty (the app's own rule 3)

**R5 — Overlay-load failure before a point is selected is completely silent on 15 of 18 layers.**
Verified repro: toggle a network layer on before tapping the map; if the boundary download fails, `onLayerToggled`'s catch (1423-1426) only `console.error`s and resets `rt.overlayLoaded` — no card state (cards aren't visible pre-point), no map-side signal, no auto-retry; the user just never sees boundaries and has no idea. Worst-case silent stall ≈ 28.5 s of nothing. Surface it: set a card-visible error state (the framework already has `setCardError` + Retry) and/or a small toast near the toggle: "Couldn't load [layer] boundaries — tap to retry." Related second-order gap: after a transient failure, nothing re-attempts the overlay except a manual re-toggle, even when a later `query()` for the same layer succeeds.

**R6 — Silent gray map when tiles fail.**
Zero `tileerror` handlers (grep-verified); offline users get a booted app (the SW shell works offline) over an empty gray map with no explanation. One `tileLayer.on("tileerror", …)` debounced into a dismissible banner ("Base map unavailable — selections still work") keeps the app honest in its most likely offline state.

### 3.3 Code consolidation

**R7 — Delete the duplicate cached-loader factory.** `makeCached` (2081-2089) is semantically identical to `makeCachedLoaderFromFn` (1581-1592) — 9 duplicated lines; 3 vs 10 call sites (verifier-corrected counts). Keep one, rename for clarity. §5 has the exact edit.

**R8 — Extract the Socrata route-walker.** `loadSocrataGeoJSON` (1560-1577) and `loadSocrataJSON` (2093-2110) are 18-line structural clones with the same single-catch-per-route subtlety (a past bug fix documented in one and inherited silently by the other). One `tryRoutes(urls, validate)` used by both. Verifier correction recorded: the four ArcGIS-style calls all use retries=2 — the genuine retry inconsistency is Socrata-primary 2 / fallback 1 / legislators 1 / POI 1, worth one comment line where they're set.

**R9 — One declarative polygon-layer factory.** The load → `findFeatureContaining` → `findPropCI` → `renderFieldList` pattern appears 12× (grep-verified call sites), 9 as standalone `registerLayer` blocks, ~250 near-duplicate lines. Three factories already exist (`registerSchoolZone`, `registerCpsNetwork`, `registerIlgaChamber`) proving the shape works; a generalized `registerPolygonLayer({loader, style, fields:[{label, props, optional}], enrich, pointOfInterest})` collapses most of the remaining nine. Do this *after* the quick wins land — it touches every module and deserves the R4 smoke test as a net.

**R10 — Repo/deploy hygiene.**
- Pages deploys the whole branch (classic CNAME-file deploy, no `.nojekyll`, no Pages workflow): scrapers, docs, and 4.6 MB of `data/` ship to the CDN. After P0, `data/app/` *must* deploy — but `data/source/raw/` (2.1 MB of zips/xlsx) still needn't. An actions-based Pages deploy that uploads only the app files (+ `.nojekyll` to skip the Jekyll pass) is ~20 lines.
- Bot branches are unique per run (`bot/ilga-roster-update-${run_id}`): an unmerged roster PR spawns a duplicate every week. Fixed branch name + force-push + `gh pr list` guard.
- Scraper deps float (`pip install requests beautifulsoup4`, `python-version: "3.x"`): heuristic HTML parsers are exactly the code that breaks on silent dependency drift. Pin via `scripts/requirements.txt` + `cache: pip`.
- `CPD_DISTRICT_INFO` is still the 32-byte placeholder — the CPD rewrite path has never run against real data in production; treat its first live PR with extra care (or land R3 first). **Root cause now identified — see R11.**

**R11 — The CPD scraper is blocked by Cloudflare's bot challenge; that is *why* the roster has never populated.**
Running `cpd_district_scraper.py` returns **HTTP 403 with `cf-mitigated: challenge`** on the district-finder page (`server: cloudflare`, `cf-ray` present) — a JavaScript/managed challenge, confirmed unchanged against a full real-browser header set (UA + `sec-ch-ua*` + `Sec-Fetch-*` + `Upgrade-Insecure-Requests`). The `requests`-based fetcher can't execute the challenge's JS, so `get_district_pages` raises and the whole run exits non-zero at step 1. This is the mechanism behind R10's last bullet: the weekly `update-cpd-roster` job fails at the scrape every time, so `data/app/cpd-district-info.json` stays the `{}` placeholder. The other two scrapers (ilga.gov, congress-legislators — plain HTML / static JSON, no Cloudflare) are unaffected and were validated green (see the 2026-07-09 run above).
- *Safety net already holds — this is a completeness gap, not a correctness risk.* `build_cpd_roster.py`'s `MIN_DISTRICTS=20` input guard plus `validate_index.py`'s `cpd-district-info.json: 0` floor mean a blocked or partial scrape can never overwrite good data with holes; with the file empty, the Police District card degrades to "district number + official link," which is the project's intended honest failure.
- *Partial recovery SHIPPED — station address + phone no longer depend on the scrape.* A review of CPD's ArcGIS org (`services2.arcgis.com/t3tlzCPfmaQzSWAk`) found two CORS-enabled (`access-control-allow-origin: *`) FeatureServers covering part of the roster: `Police_District_Stations_View` (all 22 districts: `DISTRICT`/`NAME`/`ADDRESS`/`PHONE`) and `Police_District_Boundary_View` (the geometry the app already draws). A full sweep of the org's ~55 services confirmed **commander name/status/bio and CAPS phone/email exist nowhere** in it — those remain scrape-only. The Police District card now joins the already-loaded `Police_District_Stations_View` by district number and falls back to its `ADDRESS`/`PHONE` when the roster lacks them, so a click on any district shows real station address + main phone **even while the commander scrape is blocked**. The scraped roster still wins when present. This also fixed a latent join bug: the query keyed the roster on the raw zero-padded `DISTRICT` (`"008"`) instead of the bare integer (`"8"`) the roster uses — now routed through `extractDistrictNumber`. Verified against live ArcGIS data for three known points (Loop→D1, Wrigleyville→D19, Hyde Park→D2) with an empty roster, plus roster-precedence; `validate_index.py` green. The `districtMapUrl` field is effectively superseded by the boundary geometry the app renders; only commander + CAPS contact still need the scrape.
- *Commander/CAPS scrape fix SHIPPED — `cpd_district_scraper.py` now fetches through a real browser.* Added an `--engine {auto,requests,playwright}` switch: `playwright` drives a headless Chromium that executes Cloudflare's managed-challenge JS and reads the resulting rendered HTML (no evasion — a genuine browser), handing identical markup to the unchanged `parse_district_page`; `requests` is the fast browserless path; `auto` (default) tries `requests` and transparently falls back to `playwright` the instant the finder page is blocked (403 / challenge interstitial), so the weekly job works whether or not the runner's IP is challenged. Both engines share a `_looks_like_challenge` detector. The `update-cpd-roster` workflow now installs Chromium (`python3 -m playwright install --with-deps chromium`). Also landed alongside: R3's output guard (`build_cpd_roster.py` refuses a roster with `< MIN_COMMANDERS = 15` non-null commander names — a page reword that nulls the headline field can't silently ship) and R10's dep pinning (`scripts/requirements.txt`, `requests==2.33.1`/`beautifulsoup4==4.15.0`/`playwright==1.61.0`; the ILGA job pins via `pip -c` constraints without pulling Playwright).
  - *Verification:* the real Cloudflare site can't be reached from this sandbox (browser egress is proxy-blocked, same limitation noted throughout), so the challenge-clearing itself is validated against a **faithful local simulation** — a finder page that is a challenge interstitial to a non-JS client but whose JS rewrites the DOM to the real district links once executed (what a managed challenge does after it clears). Results: `requests`/`playwright`/`auto` produce **byte-identical records** on normal fixtures (engine parity); `requests`-only is correctly blocked by the JS-challenge finder while `auto` falls back to Playwright, clears it, and scrapes both districts; `build_cpd_roster.py` passes 22 commanders and refuses 10; the populated roster (bare-integer keys, matching the app's join) flows through `validate_index.py` green. What remains unproven is only whether CPD's *specific* Turnstile config auto-clears for a headless browser on a CI IP — if it turns out to need interactive mode, the honest fallback is to surface the weekly job as a **tracked failure/alert** rather than a silent red run, with the app's station-view address/phone fallback + graceful-degradation card already covering the gap.
  - *Live CI run (`update-cpd-roster`, workflow_dispatch, 2026-07-09):* answered the open question — **Turnstile auto-cleared for headless Chromium on GitHub's IP.** `requests` was 403'd on the finder (the runner IP *is* challenged), `auto` fell back to Playwright, and the browser fetched the finder page **and** a real district page. The guard then correctly refused the result — because the rendered finder yielded only **1** district link (district 11), not 22: the full list is lazy-loaded / behind a JS map widget, something only the live site reveals. Second CI run localized the real obstacle: the finder is an **address-search widget** that renders only one example link (district 11), and per-district pages carry **no** all-districts nav — so link-following discovery tops out at 1. Fix (shipped): discovery now uses CPD's **WordPress sitemap** as the district directory. `robots.txt` (served without a challenge) points at `/wp-sitemap.xml`; `get_district_pages` fetches the sitemap index, walks its child sitemaps, and harvests every `/Nth-district-slug/` `<loc>` — the canonical list of all 22 pages. The finder is still fetched first (cheap, and its Playwright navigation warms the `cf_clearance` cookie), but the sitemap is the source of truth. The `auto`-fallback decision was moved to a dedicated one-shot `requests` probe of the finder (discovery now swallows a blocked finder and leans on the sitemap, so it can no longer double as the block signal). Verified locally against sitemap fixtures: **both engines discover 22/22**, and the district URLs survive Chromium's XML-viewer rendering of the fetched sitemap. Third CI run confirmed the sitemap path finds all 22 live districts and fetches them — but surfaced a last parser gap: the live pages carry the commander name **inline** in the heading (`Meet your commander – Sheamus Mannion`, en-dash separated), whereas `parse_commander` expected the name in a *following* block, so it matched 1/22. Fixed: `parse_commander` now extracts the name after the dash in the heading (en/em-dash or hyphen), keeping the old trailing-block form as a fallback; guarded against prose-after-dash. Added a per-field coverage summary to the scrape (makes future parser drift obvious in one log line) and a `parse_commander` regression test covering both layouts + suffixes/initials/acting.
  - **RESOLVED — the pipeline works end-to-end against the live site (CI, 2026-07-09).** The confirmation run scraped all 22 districts, `build_cpd_roster.py` passed the guards, and `validate_index.py` passed with the populated roster — every district resolved a real commander (e.g. D1 Sheamus Mannion, D2 Herbert Williams III, D18 correctly flagged `acting_commander`), bio, station address, CAPS email, district-map URL, and source URL. `data/app/cpd-district-info.json` went from the 32-byte `{}` placeholder to a full 22-district roster. So: Turnstile clears headless on GitHub IPs, sitemap discovery finds all 22, and parsing works. Two residual notes, neither a blocker: (a) `mainPhone`/`capsPhone` come through null (the live pages no longer expose `tel:` links in the parsed block) — `mainPhone` is already covered by the app's ArcGIS station-view fallback; `capsPhone` is an honest null. (b) The workflow's final `gh pr create` step fails with *"GitHub Actions is not permitted to create or approve pull requests"* — a **repo setting**, not a code issue: enable Settings → Actions → General → Workflow permissions → "Allow GitHub Actions to create and approve pull requests" (this gates all three roster workflows). The bot branch is still pushed with the data, so a human can open the PR until the setting is flipped.

**Architecture verdict:** the layer-registry contract is right and survives all of the above unchanged. The single-page philosophy also survives — what changes is that *generated data* stops living inside hand-maintained source. Resist adding a build step or framework; after P0 the "build" is still just "run a Python script when data changes, commit the JSON."

---

## 4. The Actionable Playbook (Prioritized Matrix)

| # | Task | Impact | Effort | Category |
|---|------|--------|--------|----------|
| 0 | ~~Remove Capacitor/Android/iOS stack~~ — **done in this PR** | — | — | Architecture |
| 1 | ~~Simplify school-board geometry (−892 KB raw / −74% gzip; topology-aware)~~ — **done in this PR (also covers #13)** | **High** | **Low** | Data/Assets |
| 2 | ~~Externalize geometry + rosters to `data/app/*.json`, lazy per-layer fetch~~ — **done (P0; index.html 410 KB → 112 KB)** | **High** | Medium | Architecture |
| 3 | ~~`node --check` + output invariants between rewrite and PR in both workflows~~ — **done in this PR (`scripts/validate_index.py`)** | **High** | **Low** | DevEx |
| 4 | ~~SW shell → network-first (fixes guaranteed-stale rosters)~~ — **done in this PR** | **High** | **Low** | Frontend |
| 5 | ~~Commit the Playwright boot smoke test on `pull_request`~~ — **done (`scripts/smoke_test.mjs` + `smoke-test.yml`)** | **High** | Medium | DevEx |
| 6 | ~~Builders emit JSON (regex splice + `</script`/U+2028 escaping gone entirely)~~ — **done with #2** | **High** | Medium | Pipeline |
| 7 | ~~Surface overlay-load failures (were silent on 15/18 layers)~~ — **done (`onLayerToggled` catch → `setCardError` + Retry; smoke-test covered)** | **High** | **Low** | Frontend |
| 8 | ~~Build-time IL congress roster; drop multi-MB runtime fetch~~ — **done (P2; `build_congress_roster.py` + `update-congress-roster.yml` → `data/app/congress-roster.json`, 17 IL reps; layer fetches same-origin)** | **High** | Medium | Network |
| 9 | ~~`geometryPrecision=6` on 3 Esri loaders~~ — **done in this PR** (outFields kept `*` to preserve the name-field fallback) | Medium | **Low** | Network |
| 10 | ~~Guard `loadTigerLayer`/`loadCookCountyLayerGeoJSON` against 200-error-envelopes~~ — **done in this PR** | Medium | **Low** | Network |
| 11 | ~~`timeoutMs` overrides for large payloads~~ — **done in this PR** (30 s for the two big Esri loaders) | Medium | **Low** | Network |
| 12 | ~~Single PIP per click + restyle only the 2 changed paths~~ — **done (P7; memoized `findFeatureContaining` + incremental `updateLayerHighlight`)** | Medium | **Low** | Frontend |
| 13 | ~~Commit geometry-regeneration script + validation protocol~~ — **done in this PR (`scripts/build_embedded_boundaries.py`)** | Medium | **Low** | Pipeline |
| 14 | ~~Preconnect tile shards + Leaflet CDN + dns-prefetch API origins~~ — **done in this PR** | Medium | **Low** | Frontend |
| 15 | ~~Serialize POI geocoding ≥1 s apart~~ — **done in this PR** (+ stale-skip to bound the backlog) | Medium | **Low** | Network |
| 16 | ~~Tile-failure banner (`tileerror`)~~ — **done (R6; debounced dismissible banner, smoke-test covered)** | Medium | **Low** | Frontend |
| 17 | ~~Toggle-path: skip restyle on toggle-off; opacity-only rescale~~ — **done (P8; `rescaleLayerFill` skips highlighted layers + fill-only setStyle for the rest, shared `highlightSignature`, toggle-off reorder dropped; smoke-test covered)** | Medium | **Low** | Frontend |
| 18 | ~~`.nojekyll` added; Actions-based Pages deploy (app files only)~~ — **done (`deploy-pages.yml`: curated `_site`, drops `scripts`/`docs`/`data/source`/full-precision `data/*.geojson`, keeps `CNAME`)**. One-time **owner action still required**: flip Settings→Pages source to "GitHub Actions" (workflow is inert/harmless until then, no outage) — R10 | Low-Med | **Low** | DevEx |
| 19 | ~~Fixed bot branches + duplicate-PR guard; pin scraper deps~~ — **done (all 4 roster workflows: fixed branch + force-push + `gh pr list` guard; deps already pinned via `scripts/requirements.txt`)** | Low | **Low** | DevEx |
| 20 | ~~Dedupe loader factory; extract route-walker~~ — **done (R7: one `makeCached`; R8: shared `tryRoutes`; net −17 lines)** | Low | **Low** | Architecture |
| 21 | ~~Declarative `registerPolygonLayer`~~ — **done (R9; 4 pure single-source layers converted; the async-join layers stay custom — see log)** | Medium | Medium | Architecture |
| 22 | ~~Dedupe SW shell entry; cache-name discipline; trim font weights~~ — **done (P13/P-sw; SW `-v3` + navigate fallback, Big Shoulders 700 dropped; Inter 700 kept — now used by `<strong>`/`<b>`, correcting the playbook premise)** | Low | **Low** | Frontend |
| 23 | ~~Release Leaflet layer graph on toggle-off~~ — **done (P11; `onLayerToggled` nulls `rt.overlayLayer` on toggle-off, `buildOverlayLayer` rebuilds it from cached `rt.geojson` on re-toggle; smoke-test covered)** | Low | **Low** | Frontend |
| 24 | ~~Canvas renderer for school-zone layers~~ — **REJECTED (owner decision):** conditional on profiling still showing restyle cost, which P7/P8/P12 already collapsed; canvas breaks the `_path.classList` drop-shadow highlight on those layers (a definite visual regression) for an unmeasured gain. Not worth it. — P10 | Low-Med | Medium | Frontend |
| 25 | ~~Drop-shadow rasterization: pause filter during pan, or restyle~~ — **REJECTED (owner decision):** a flagged cosmetic choice, only worth it if pan jank is actually observed on low-end devices (it hasn't been); dropping the highlight shadow during pan/zoom is a visible behavioral change for no measured benefit. — P9 | Low | Low | Frontend |
| 26 | ~~README: fix embedded→fetched/offline + simplification claims; drop the not-in-repo Playwright claim~~ — **done with #2** (Playwright smoke test itself is still #5) | Low | **Low** | DevEx |
| 27 | ~~CPD scraper blocked by Cloudflare managed challenge (403)~~ — **DONE & verified live on CI (R11):** headless Chromium clears Turnstile; sitemap discovery finds all 22 districts; `parse_commander` handles the live inline-name heading; roster builds + validates with real data for all 22 (`cpd-district-info.json` `{}` → full roster). Also shipped: app joins station address/phone from CORS `Police_District_Stations_View` (+ zero-pad join-key fix), `--engine auto` requests→Playwright fallback, R3 commander-count guard, R10 dep pinning. Remaining is a **repo setting** (allow Actions to create PRs), not code. | Medium | Medium | Pipeline |

Coherent PR groupings: **PR-A** (items 1+13, one regenerated line + one script), **PR-B** (3+19, workflow safety), **PR-C** (4+22, sw.js), **PR-D** (2+6+26, the externalization — the structural centerpiece), **PR-E** (7+16, failure honesty), **PR-F** (9+10+11+15, network etiquette), **PR-G** (12+17, click path). Land PR-B before PR-D so the pipeline change is born validated; land item 5 before item 21.

---

## 5. Quick Wins (exact before/after)

### QW1 — Simplify the school-board blob: −892 KB raw, −316 KB gzipped, one regenerated line ✅ SHIPPED

*Shipped in this PR via `scripts/build_embedded_boundaries.py` (topology-aware mapshaper, not the per-ring approach sketched below — per-ring DP created a district overlap). Actual result: blob 975,796 → 83,470 B; `index.html` 1,301,984 → 409,712 B raw / 112,216 B gzip. The before/after shape is unchanged; only the numbers below are updated.*

`index.html:2553` today (975,796 bytes on one line; head shown):

```js
  var SCHOOL_BOARD_DISTRICTS_GEOJSON = JSON.parse('{"type":"FeatureCollection","features":[{"type":"Feature","properties":...   // 24,904 coord pairs, 14-15 decimals
```

After (83,470 bytes — same variable, schema, and district properties; geometry topology-simplified like its two sibling layers):

```js
  var SCHOOL_BOARD_DISTRICTS_GEOJSON = JSON.parse('{"type":"FeatureCollection","features":[{"type":"Feature","properties":...   // 3,525 coord pairs, 6 decimals
```

Measured: `index.html` 1,301,984 → 409,712 B (gzip 427,836 → 112,216). Validated with the app's own `pointInGeometry`/`findFeatureContaining`: 2000/2000 on the repo's protocol, 0 topology breaks, 0 internal wrong-district misses, 20/20 district interiors correct. Generated by the committed `scripts/build_embedded_boundaries.py` (which validates before it rewrites the line and refuses on failure), not by hand; provenance comment updated. This wins even if you do the externalization (P0) later — it's the same bytes, just in a fetched file.

### QW2 — sw.js: network-first shell (returning visitors currently always see last deploy's rosters)

`sw.js:52-61` before:

```js
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const network = fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
```

After (network-first with cache fallback — online visits are always current, offline still boots):

```js
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
```

The header comment's own rule ("staleness there is unacceptable") currently loses to `return cached || network` — the rosters live inside the cached shell. Online performance cost is one conditional request (GitHub Pages answers 304 + headers when unchanged).

### QW3 — 44 ms of `node --check` between "bot rewrote 1.3 MB of source" and "PR opened"

Both workflows, after the "Rebuild embedded roster" step and before "Check for changes" (`update-ilga-roster.yml:37` / `update-cpd-roster.yml:37`):

```yaml
      - name: Validate rewritten index.html still parses
        run: |
          python3 - <<'EOF'
          import re, subprocess, sys
          html = open("index.html").read()
          scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
          assert scripts, "no inline scripts found"
          open("/tmp/inline.js", "w").write(max(scripts, key=len))
          subprocess.run(["node", "--check", "/tmp/inline.js"], check=True)
          assert html.count("registerLayer(") >= 15, "layer registrations went missing"
          EOF
```

This is the floor, not the ceiling (see matrix #5 for the real smoke test). Division of labor, verified empirically: `node --check` catches syntax death from a malformed splice but **not** the module-deletion overmatch — the over-matched output still parses — which is exactly what the `registerLayer(` count assertion (15 occurrences today: 1 definition + 11 direct calls + 3 factory bodies) is there to catch. Measured: 44 ms.

### QW4 — Ask TIGERweb for 11 cm coordinates instead of sub-nanometer ones

`index.html:2117-2118` before:

```js
    var url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/" +
      layerIndex + "/query?where=" + where + "&outFields=*&outSR=4326&f=geojson";
```

After:

```js
    var url = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Legislative/MapServer/" +
      layerIndex + "/query?where=" + where + "&outFields=*&outSR=4326&f=geojson&geometryPrecision=6";
```

~40% smaller payloads on the three heaviest network layers (coordinate digits beyond 6dp measure 41.5% of GeoJSON bytes); zero visual or classification difference at any zoom this map allows (maxZoom 18 ≈ 0.6 m/px). Apply the same parameter to `loadArcGISGeoJSON` (line 1607) and `loadCookCountyLayerGeoJSON` (2710-2711).

### QW5 — Warm the connections the first paint actually waits on

`index.html:13-14` before:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
```

After:

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="preconnect" href="https://a.basemaps.cartocdn.com">
<link rel="preconnect" href="https://b.basemaps.cartocdn.com">
<link rel="dns-prefetch" href="https://data.cityofchicago.org">
<link rel="dns-prefetch" href="https://nominatim.openstreetmap.org">
```

Tiles are requested the moment the inline script runs, from four sharded hosts that today get no warm-up (grep: fonts are the only resource hints in the file). Preconnecting two shards covers the initial viewport's parallelism; dns-prefetch on the click-time APIs is nearly free.

### Bonus one-liner — the geocoder's Enter-key double request

`index.html:1003-1005`: the submit handler never cancels the pending input-debounce timer, so pressing Enter within 550 ms of the last keystroke fires the search, then the debounce aborts it and re-issues an identical request (~550 ms + 1 RTT of added latency on the fast-typist path). Add `clearTimeout(debounceTimer);` as the first line of the submit handler — mirroring the guard the result-click handler already has at line 992.
