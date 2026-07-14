# Performance Analysis — Chicago District Explorer

**Repo:** ThursdaysFamous/DistrictExplorer-CHI · **Date:** 2026-07-14 · **Scope:** `index.html` (6,558 lines / 311 KB), `sw.js`, boot + interaction paths, delivered payload.

This is a fresh, Chrome-measured pass over the *current* working tree — a companion to `docs/OPTIMIZATION_PLAYBOOK.md`, which recorded the 2026-07-09 optimization campaign (externalize embedded data, incremental restyle P7/P8, SW rework, layer-graph release P11). Since then the app has grown from 18 to **33 registered layers** and picked up statewide-Illinois / Will County / Cook County features. This document measures where it stands now and what's worth doing next.

Every number here was produced by `scripts/perf_profile.mjs` against this tree — a Playwright + Chrome DevTools Protocol harness (the performance sibling of `scripts/smoke_test.mjs`). Re-run it with `node scripts/perf_profile.mjs`.

## Method & environment

The harness drives the real `index.html` in headless Chromium via CDP and records: cold-boot timing over 7 runs (median/min/max), Chrome's own `Performance.getMetrics` (ScriptDuration, RecalcStyle, Layout, JS heap, DOM nodes), a `PerformanceObserver` long-task tally, the boot resource waterfall, a **CPU-sampled** (`Profiler` domain, 100 µs) profile of each interaction, and a footprint + pan-frame A/B.

**What is and isn't faithful here.** Like the smoke test, this runs in a sandbox where the Leaflet CDN, the CARTO tile CDN, Google Fonts, and every live district API (Socrata / ArcGIS / TIGERweb / geocoders) are unreachable. Leaflet and a stub tile are served same-origin; the live-API layers can't be exercised, so interaction measurements use the **three same-origin no-API layers** (`school-board`, `il-supreme-court`, `ccbr`) — the same deterministic ground truth the smoke test uses. Consequences for reading the numbers:

- **Environment-independent (trust the absolutes):** payload bytes, `ScriptDuration`/`V8CompileDuration`, DOM-node/heap counts, CPU-sample *shape* (which functions are hot), and every **A/B ratio**.
- **Inflated by headless software rendering (read as relative, not user-facing):** paint, layout, and especially pan/raster wall-times. The sandbox rasterizes on SwiftShader (software GL, no GPU), so a frame that costs 60 ms here is far cheaper on real hardware. This is why the rendering finding below is stated as a **ratio** (filter on ÷ off), which is stable across environments.
- **Not measured here:** the live-API layers' network cost (community areas, wards, police, congress, TIGERweb statewide, …) and real-CDN / real-tile latency. Findings about those paths are labelled *(inferred)*.

---

## Executive summary

**The app is fast and lean, and the 2026-07 optimization work clearly holds.** Cold boot reaches first contentful paint in ~116 ms and becomes interactive in ~117 ms with **zero long tasks**, ~32 ms of script evaluation, a 3.5 MB heap, and 835 DOM nodes — this despite 33 registered layers. The incremental-restyle fast path (P7) keeps a point-move at ~8 ms of CPU, and the layer-graph release (P11) makes a warm re-toggle a ~3 ms synchronous rebuild. Nothing here is on fire.

The findings are refinements, ranked by impact:

1. **The selection-highlight drop-shadow filter is the single measurable rendering cost — it ~3.7×'s pan-frame time** (61.6 ms vs 16.7 ms with the filter forced off, over a 2.3-megapixel filter region). *(rendering; medium — higher on low/mid mobile)*
2. **Boot eagerly downloads and parses the full 83 KB school-board geometry on every visit** — for a *decorative* out-of-coverage wash — re-introducing exactly the eager geometry load that P0 externalization removed. *(boot payload; medium)*
3. **~46 KB of marker-icon PNGs are preloaded at boot** for conditionally-shown markers (water-taxi, county seal). *(boot payload; low–medium)*
4. **Third-party Google-Fonts CSS is render-blocking on FCP** (already softened by `preconnect` + `display=swap`). *(FCP; low)*

Everything else measured — heap growth, DOM growth, toggle latency, classify latency — is healthy. Details and fixes below.

---

## 1. Cold boot — measured (7 runs, median (min–max))

| Metric | Value | Read |
|---|---|---|
| First Contentful Paint | **116 ms** (84–160) | masthead paints early (it's above the script tags) |
| Time to app-ready (`window.ChiExplorer` set) | **116.8 ms** (104–178) | end of the boot IIFE — app is interactive |
| DOMContentLoaded | 120.6 ms (108–184) | |
| Load event (all async resources) | 178.9 ms (152–232) | includes the scope-mask fetch + icon preloads (§2) |
| **Script evaluation** (`ScriptDuration`) | **32.1 ms** (31–34) | whole app IIFE; very stable |
| V8 compile (`V8CompileDuration`) | 3.0 ms | |
| Recalc style | 9.5 ms | for a 1,012-line inline stylesheet |
| Layout | 25.7 ms | initial layout of shell + map + card scaffold |
| JS heap used | **3.5 MB** (3.5–4.3) | |
| DOM nodes | **835** | flat across runs |
| JS event listeners | 193 | |
| **Long tasks (>50 ms) during boot** | **0** | nothing blocks the main thread |

**Verdict: excellent, and nothing to fix in the boot *compute* path.** 32 ms of script eval and zero long tasks on a 5,200-line inline IIFE with 33 layer registrations is a strong result — the "register layers, don't touch the network until toggled" design keeps boot cheap. The boot *network* path has two avoidable every-visit downloads — see §2.

---

## 2. Payload & network

### Delivered bytes (raw / gzip -9, measured)

| Asset | Raw | Gzip | When |
|---|--:|--:|---|
| `index.html` | 311,522 | **88,965** | every visit (render-blocking parse) |
| `leaflet.js` | 147,552 | 42,356 | every visit (CDN; SW cache-first after 1st) |
| `leaflet.css` | 14,806 | 3,534 | every visit (CDN) |
| Google Fonts CSS | — | ~small | every visit (render-blocking; §2.3) |
| **Critical path to interactive** | | **≈ 135 KB gzip** | html + leaflet js/css |
| `data/app/school-board-districts.json` | 83,470 | 20,189 | **every boot** (see §2.1) — should be on-toggle |
| `icons/water-taxi.png` | 27,076 | (png) | **every boot** (see §2.2) |
| `icons/seals/cook-county.png` | 18,607 | (png) | **every boot** (see §2.2) |
| other `data/app/*.json` (11 files) | — | 0.4–31 KB each | lazily, on first toggle of their layer ✅ |

A cold first visit transfers **~135 KB gzip to interactive**, plus **~66 KB** of *avoidable* every-visit tail (§2.1 + §2.2). That's a lean app — `index.html` at 89 KB gzip is the result of the P0/P1 externalization work, and the eleven lazily-fetched datasets (16–31 KB gzip for the big geometries) correctly stay off the boot path until their layer is toggled. Except:

### 2.1 — FINDING: the decorative scope-mask eagerly downloads + parses the 83 KB school-board geometry every boot

`index.html:6508` calls, unconditionally at boot:

```js
drawOutOfScopeMask(loadSchoolBoardDistricts);   // loadSchoolBoardDistricts = fetch data/app/school-board-districts.json
```

`drawOutOfScopeMask` (`index.html:1884`) awaits the **full 20-district school-board GeoJSON** (20 KB gzip → **83 KB parsed**), then runs `coverageOutlineRings` to dissolve it into the outer boundary and paints a single `fillOpacity: 0.18` gray polygon over everything outside Chicago's coverage. It's explicitly decorative — its own `catch` says *"decorative — skip the wash, never surface an error."*

**Why it matters.** This is the single largest data download at boot, and it directly undoes the P0 design goal ("a user who never toggles the school-board layer never downloads a byte of it"): school-board geometry is now fetched and `JSON.parse`d on **every** visit regardless of what the user toggles. Confirmed in the boot resource waterfall — `school-board-districts.json` (20,213 B) loads with no layer on and no point selected. It's `async` so it doesn't delay FCP, but it costs 20 KB of transfer + an 83 KB parse + the outline-dissolve compute on every load, and on a slow/metered mobile link that's real.

**Fix (two good options, both low-risk):**
- **Ship a dedicated coverage-outline file.** The wash only needs the *outer boundary* of the coverage union, not 20 districts at full detail. A pre-dissolved `data/app/coverage-outline.json` (one MultiPolygon) would be a few KB and skip the runtime `coverageOutlineRings` dissolve entirely. The repo already has this exact pattern — `will-county-outline.json` is a purpose-built outline file. *(Note: coverage now spans more than the city — statewide/Will/Cook layers exist — so the outline should be the union the mask actually intends, decided against the current coverage story, not blindly the city border.)*
- **Or defer it off the boot path.** Wrap the call in `requestIdleCallback` (fallback `setTimeout(…, 0)`) so the wash paints after the app is interactive and never competes with first interaction. Cheapest change; keeps the current geometry source.

### 2.2 — FINDING: ~46 KB of marker icons preloaded at boot for conditional markers

At boot the app eagerly warms two marker images that most sessions never display:
- `icons/water-taxi.png` (27 KB) — `waterTaxiImg.src = …` at `index.html:1401` — the marker shown only when a selected point lands on water.
- `icons/seals/cook-county.png` (18.6 KB) — warmed by the `COUNTY_SEAL_URLS` preload loop at `index.html:1484` — shown only for a point in Cook County *outside* the City of Chicago.

The comments are candid about intent ("Warm the seals we ship so the first out-of-city selection swaps instantly"). It's a deliberate latency-for-bandwidth trade, but it spends ~46 KB on **every** visit for markers that appear on a minority of selections. **Fix:** load these lazily on the first out-of-Chicago / on-water selection (the swap is a single image decode — imperceptible), or at worst move the warm into `requestIdleCallback` so it's off the boot path. If the instant-swap is considered essential, leaving it is defensible — but it should be a conscious choice, not invisible boot weight.

### 2.3 — Note: render-blocking third-party font CSS *(low)*

`index.html:102` loads the Google-Fonts stylesheet as a render-blocking `<link rel="stylesheet">`. Text itself isn't blocked (`display=swap` lets fallbacks paint, and the fonts are `preconnect`ed), but the stylesheet *link* still gates render on one RTT to `fonts.googleapis.com` in production. Self-hosting the `@font-face` CSS (inline, same-origin) removes a third-party dependency from the FCP critical path. Low priority given the existing mitigations; flagged for completeness.

---

## 3. Interaction & rendering

All CPU figures are `Profiler`-sampled *active* CPU (idle/RPC-wait excluded); wall-times include the async card-render settle.

### 3.1 — Classify / point-move / toggle: healthy

| Interaction | Wall | Active CPU | Notes |
|---|--:|--:|---|
| First classify (select point, 3 layers on) | 24.5 ms | 9.9 ms | PIP + highlight + 3 card renders |
| **Point move** (re-classify, same layers) | 36.5 ms | **8.3 ms** | P7 incremental fast path — only the 2 changed paths restyle |
| Cold toggle-on (school-board: fetch+parse 83 KB + build 3,525-coord layer + render) | 27.6 ms | 7.0 ms | |
| Warm toggle-off | 24 ms | — | |
| **Warm toggle-on** (rebuild from cached geojson, P11) | **3.3 ms** | — | synchronous, no refetch |

These confirm the 2026-07 interaction work is paying off. The point-move CPU profile is dominated by Leaflet's own projection/clip (`project`, `_projectLatlngs`, `latLngToLayerPoint`, `_clipPoints`) — i.e. the app's own restyle is *not* the bottleneck, exactly as P7 intended (it flips 2 paths, not all ~630). Warm toggle-on at 3.3 ms is the P11 synchronous rebuild working as designed.

*(Inferred, not measurable here) — coverage re-checks on point-move.* Layers that declare `coverage()` (`school-board` → `chicagoCoverage`, `ccbr` → `cookCountyCoverage`) re-evaluate on every selection. `chicagoCoverage`'s fallback leg consults the community-area Socrata dataset after an ERSB-tiling miss, so a point near a tiling edge can trigger a **network round-trip per point-move**. In-sandbox this showed up as multi-hundred-ms outliers on specific downtown points (the fallback fetch is aborted here). In production it's a real, if occasional, per-interaction network dependency — worth being aware of, though the tiling primary handles the common case locally. No change recommended without production measurement.

### 3.2 — FINDING: the selection-highlight drop-shadow filter is a ~3.7× pan tax

The matched-district highlight (`index.html:1010`) is:

```css
.chi-region-highlight {
  filter: drop-shadow(0 5px 7px rgba(20,24,28,0.5)) drop-shadow(0 1px 2px rgba(20,24,28,0.35));
  transition: filter 120ms ease-out;
}
```

**two stacked `drop-shadow()` filters** applied to raw SVG paths — one highlight per active layer whose region contains the point. Measured pan-frame A/B (identical scene, 3 layers + 3 highlights, filter on vs. forced `filter:none`, 60 `panBy` frames each):

| | Median frame | p95 | Max |
|---|--:|--:|--:|
| Drop-shadow **on** (as shipped) | **61.6 ms** | 82 ms | 133.8 ms |
| Drop-shadow **off** | **16.7 ms** | — | 17 ms |
| **Ratio** | **3.7×** | | |

The highlighted paths span a **2.3-megapixel** filter region (measured from their bounding boxes) that Chrome re-rasterizes with a blurred, stacked drop-shadow **every frame** during pan/zoom. The `il-supreme-court` "District 1 = all of Cook County" highlight is a large polygon, so its filter region is large.

The absolute 61.6 ms is inflated by software rendering — on a GPU the per-frame cost is lower — **but the 3.7× ratio is environment-independent**, and blurred filters over large regions are exactly the case that stays expensive on mid/low-end mobile GPUs (frequent full-region repaints, no cheap layer promotion). This is the mechanism `docs/OPTIMIZATION_PLAYBOOK.md` flagged as P9; it's now measured.

**Fix (cheap, standard, no visual change at rest):**
- **Drop the filter during movement.** On the map's `movestart` add a class that sets `filter:none` on `.chi-region-highlight`; remove it on `moveend`. The shadow is a static decoration — it doesn't need to re-rasterize mid-pan. This is the lowest-risk fix and collapses the pan cost to the filter-off baseline.
- **Or replace the shadow with a non-filter treatment** — a wider casing stroke (a second, darker, semi-transparent stroke underneath) reads as depth without a raster-time filter at all. Slightly more work; removes the cost permanently, pan or not.

Either is a small, localized change to the shared highlight code (no layer-module edits).

---

## 4. Memory & DOM footprint

| State | JS heap | DOM nodes | `#map` SVG paths |
|---|--:|--:|--:|
| Booted, no layers, no point | 3.55 MB | 835 | 4 |
| + point + 3 no-API layers on (school-board, il-supreme-court, ccbr) | ~5.7–7.4 MB | 980 | 33 |
| **Delta for 3 layers** | ~2–3.8 MB | **+145** | +29 |

Heap and DOM growth are modest and bounded; the delta varies with GC timing (3.5 → 5.7 MB on one run, 7.4 MB on another before collection). +145 DOM nodes and +29 SVG paths for three boundary layers (including `il-supreme-court`'s large all-Cook polygon and `ccbr`'s district set) is proportionate. The P11 toggle-off geojson-retain / layer-graph-release keeps a long multi-toggle session from accumulating Leaflet `LatLng` graphs. No leak or bloat surfaced.

*(Inferred) — the heavy live layers.* Not exercisable here, but by construction the render load scales with rendered polygon count: community areas (77), ZIPs (~61), wards (50), and the school-zone layers (~420 polygons) are the heavy ones. The architecture handles this well for *steady-state* interaction — P7 makes a point-move restyle only the paths whose match changed, independent of total path count — so the cost that scales with "everything on" is the **cold first render** of each layer (Leaflet SVG path creation), not ongoing interaction. Cold toggle-on measured at 27.6 ms for school-board's 20 districts / 3,525 coords; the ~420-polygon school-zone layers will be proportionally heavier on their *first* toggle only.

---

## 5. Prioritized findings

| # | Area | Finding | Evidence | Suggested fix | Impact |
|---|---|---|---|---|---|
| **1** | Rendering | Highlight drop-shadow ~3.7×'s pan-frame time (2.3 Mpx filter re-rasterized per frame) | `index.html:1010`; pan A/B 61.6 vs 16.7 ms | drop `filter` during `movestart`→`moveend`, or use a casing stroke | Medium (higher on low/mid mobile) |
| **2** | Boot payload | Decorative scope-mask downloads + parses full 83 KB school-board geometry every boot | `index.html:6508` → `1884`; boot waterfall | dedicated small `coverage-outline.json`, or defer to `requestIdleCallback` | Medium |
| **3** | Boot payload | ~46 KB marker-icon PNGs preloaded at boot for conditional markers | `index.html:1401`, `1484`; boot waterfall | lazy-load on first water/out-of-city selection, or idle-warm | Low–Medium |
| **4** | FCP | Render-blocking third-party Google-Fonts CSS | `index.html:102` | self-host/inline `@font-face` (already `preconnect` + `display=swap`) | Low |

**None of these is urgent.** #1 has the broadest user-visible payoff (smoother pan on the devices most likely to feel it) for the least code. #2 and #3 are pure every-visit-bytes wins that restore the "download nothing you don't use" property the externalization work established. #4 is a completeness note.

### What's healthy (measured, no action)

- Cold boot: 116 ms FCP, ~117 ms interactive, **0 long tasks**, 32 ms script eval, 3.5 MB heap, 835 nodes — with 33 layers registered.
- `index.html` at 89 KB gzip; the eleven `data/app/*.json` datasets correctly stay lazy (on-toggle), *except* the school-board file pulled early by finding #2.
- Point-move on the P7 incremental path: 8 ms CPU (restyles 2 paths, not all). Warm re-toggle on the P11 path: 3.3 ms synchronous rebuild.
- Memory/DOM growth bounded and proportionate; no leak observed across repeated toggles.

---

## Appendix — reproducing these numbers

```bash
# In a CDN-blocked sandbox (Claude Code web) only — vendor Leaflet same-origin:
bash scripts/vendor_leaflet.sh

# Run the profiler (starts its own gzip static server, drives headless Chromium):
npm install playwright@1.56.1
node scripts/perf_profile.mjs          # writes perf-results.json + prints a summary
BOOT_RUNS=15 node scripts/perf_profile.mjs   # more boot samples for a tighter median
```

`scripts/perf_profile.mjs` is an operator/analysis tool, not a CI gate (behaviour is gated by `scripts/smoke_test.mjs`; the merge gate is `scripts/validate_index.py`). It depends only on the app shell + the three same-origin no-API layers, so it's deterministic and needs no live district API. Outputs (`perf-results.json`, `docs/perf-app-screenshot.png`) are gitignored transient artifacts, same convention as the smoke test's.

**Reading the results as this document does:** trust payload bytes, `ScriptDuration`, node/heap counts, CPU-sample shape, and every A/B ratio as-is; treat raw paint/pan wall-times as *relative* (headless software rendering inflates them); and label any claim about the live-API layers or real CDN/tile latency as inferred — this harness intentionally never touches them.
