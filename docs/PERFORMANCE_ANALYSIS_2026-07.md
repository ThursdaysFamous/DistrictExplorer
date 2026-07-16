# Performance Analysis — Chicago District Explorer

**Repo:** ThursdaysFamous/DistrictExplorer-CHI · **Date:** 2026-07-14 (rev. 2026-07-16: mobile-Lighthouse + production-capture cross-checks) · **Scope:** `index.html` (6,558 lines / 311 KB), `sw.js`, boot + interaction paths, delivered payload.

This is a fresh, Chrome-measured pass over the *current* working tree — a companion to `docs/OPTIMIZATION_PLAYBOOK.md`, which recorded the 2026-07-09 optimization campaign (externalize embedded data, incremental restyle P7/P8, SW rework, layer-graph release P11). Since then the app has grown from 18 to **33 registered layers** and picked up statewide-Illinois / Will County / Cook County features. This document measures where it stands now and what's worth doing next.

The primary numbers were produced by `scripts/perf_profile.mjs` against this tree — a Playwright + Chrome DevTools Protocol harness (the performance sibling of `scripts/smoke_test.mjs`; re-run with `node scripts/perf_profile.mjs`). The 2026-07-16 revision folds in two external lenses the sandbox can't produce itself: a **Lighthouse mobile** run (§6) and a **production Firefox Profiler capture** (§7). See *Method & environment* for how each is sourced and how faithful it is.

## Method & environment

The harness drives the real `index.html` in headless Chromium via CDP and records: cold-boot timing over 7 runs (median/min/max), Chrome's own `Performance.getMetrics` (ScriptDuration, RecalcStyle, Layout, JS heap, DOM nodes), a `PerformanceObserver` long-task tally, the boot resource waterfall, a **CPU-sampled** (`Profiler` domain, 100 µs) profile of each interaction, and a footprint + pan-frame A/B.

**What is and isn't faithful here.** Like the smoke test, this runs in a sandbox where the Leaflet CDN, the CARTO tile CDN, Google Fonts, and every live district API (Socrata / ArcGIS / TIGERweb / geocoders) are unreachable. Leaflet and a stub tile are served same-origin; the live-API layers can't be exercised, so interaction measurements use the **three same-origin no-API layers** (`school-board`, `il-supreme-court`, `ccbr`) — the same deterministic ground truth the smoke test uses. Consequences for reading the numbers:

- **Environment-independent (trust the absolutes):** payload bytes, `ScriptDuration`/`V8CompileDuration`, DOM-node/heap counts, CPU-sample *shape* (which functions are hot), and every **A/B ratio**.
- **Inflated by headless software rendering (read as relative, not user-facing):** paint, layout, and especially pan/raster wall-times. The sandbox rasterizes on SwiftShader (software GL, no GPU), so a frame that costs 60 ms here is far cheaper on real hardware. This is why the rendering finding below is stated as a **ratio** (filter on ÷ off), which is stable across environments.
- **Not measured here:** the live-API layers' network cost (community areas, wards, police, congress, TIGERweb statewide, …) and real-CDN / real-tile latency. Findings about those paths are labelled *(inferred)* or sourced from the cross-checks below.

**Two external cross-checks incorporated (2026-07-16).** Because the sandbox can't reach production or the live APIs, two other lenses fill the gaps:
- **§6 — production PageSpeed Insights (mobile).** The **real** PSI/Lighthouse 13.4.0 mobile run of chidistricts.com (Slow-4G, emulated Moto G Power), read from the PSI report. This is the authoritative mobile-load lens. *(I couldn't reach it programmatically — PSI renders results client-side, the keyless PSI API is quota-limited, and Chrome here has no egress to production — so I first ran a **local proxy** in-sandbox: Lighthouse against a serve of this tree with Leaflet vendored same-origin and the font `<link>` neutralized so it boots. That proxy measured the app-intrinsic profile and scored Performance 96 / FCP 1.8 s — optimistic, because it stubs exactly the third-party render-blocking + tiles the real run shows dominate. §6 reports the production numbers; the proxy is noted only where the divergence is instructive.)*
- **§7 — production Firefox Profiler capture.** A 58.5 s real-hardware (i7-1065G7, Firefox 152) capture of a **warm interaction session** hitting the live APIs — the one lens that sees real live-API latency, GC pressure, and Leaflet render cost. Single session / point / machine: directional, not a benchmark average.

Field data: the Chrome UX Report (CrUX) has **no real-user data** for this page, so the production PSI card shows Lighthouse *lab* data only — the same kind of lab figures reported here.

---

## Executive summary

**The app's own code is fast and lean — the mobile *load* score is held back by third-party delivery, not by the app's compute.** Cold boot (desktop, unthrottled) reaches first contentful paint in ~116 ms with **zero long tasks**, ~32 ms of script evaluation, a 3.5 MB heap, and 835 DOM nodes — despite 33 registered layers. That compute cleanliness carries to production: the **real PageSpeed Insights mobile** run scores **Accessibility / Best-Practices / SEO all 100**, **TBT 0 ms**, and **CLS 0** — but **Performance 75** (*needs-improvement*), because **FCP is 3.3 s and LCP 5.0 s**. First paint waits behind render-blocking Leaflet + Google-Fonts, and the LCP element is a CARTO map tile. Interaction is similarly clean in-app (P7 point-move ~8 ms CPU; P11 warm re-toggle ~3 ms) yet gated by live-API latency in the real world (§7). **So: strong engine; load-delivery and live-data are the levers.**

**Three lenses, reconciled** (attribution inline): my **sandbox Chrome** harness (§1–4 — boot compute, payload, the render A/B), the **production PageSpeed Insights mobile** run (§6 — the 75 and its causes), and a **production Firefox Profiler capture** (§7 — live-API + Leaflet-render + GC).

Findings, ranked by user-perceived impact:

1. **Render-blocking third-party delivery (~2,110 ms) — the reason production mobile is 75.** `leaflet.js` (1,340 ms) + `leaflet.css` (750 ms) + Google-Fonts CSS (780 ms) block first paint; the LCP element is then a CARTO tile at 5.0 s. Fixes: inline `leaflet.css`, self-host/subset the fonts (takes 107 KiB of woff2 off the critical path), async-load Leaflet. *(load; highest — every visit; PSI §6)*
2. **Live-API latency dominates time-to-answer** — TIGERweb ~5.7 s, Nominatim ~2.5 s, ArcGIS ~0.9 s. Pre-build the **decadal** legislative districts → cache-first `data/app/*.json` (a ~5.7 s query becomes a ~200 ms fetch). *(interaction network; high; Firefox §7)*
3. **Boot eagerly loads the 83 KB scope-mask geometry + ~46 KB marker icons every visit** — PSI independently puts `school-board-districts.json` in the 669 ms initial-navigation critical chain and flags the icons' 10-minute cache TTL, confirming §2.1–2.2. *(boot payload; medium)*
4. **The selection-highlight drop-shadow filter ~3.7×'s pan-frame time** (61.6 ms vs 16.7 ms filter-off). *(rendering; medium — worse on low/mid mobile)*
5. **Point-in-polygon has no bounding-box pre-reject** — the Firefox capture measured **~1.44 s in `pointInRing`**; bbox helpers already exist in the file. *(app code; medium — inside the `point-in-polygon` ENGINE fence, so a fix must port to sibling forks)*
6. **Load hygiene (PSI):** 60 KiB unused JS + 41 KiB minifiable JS (a conscious no-build tradeoff), oversized `@2x` basemap tiles (56 KiB), and 5 `preconnect` hints where Lighthouse wants ≤ 4. *(payload; low–medium)*

The app's *own* work is healthy across the board — **TBT 0 ms, CLS 0**, zero boot long tasks, bounded memory, and **Accessibility / Best-Practices / SEO all 100** in production. (My earlier in-sandbox Lighthouse proxy scored Performance 96 / FCP 1.8 s — optimistic because it stubbed exactly the third-parties PSI shows dominate; §6 explains the divergence.) Details and fixes below.

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

### 2.3 — FINDING: render-blocking third-party CSS/JS *(this is finding #1 — see §6)*

`index.html:102`/`104`/`1278` load the Google-Fonts stylesheet, `leaflet.css`, and `leaflet.js` — all render-blocking. My sandbox stubbed them, so §1's boot numbers don't reflect their cost; **the production PSI run (§6) does, and puts them at the top: ~2,110 ms of blocked first paint** (`leaflet.js` 1,340 ms + `leaflet.css` 750 ms + Fonts CSS 780 ms), which is the single largest reason production mobile scores 75. Text isn't blocked (`display=swap` + `preconnect`), but the *links* gate render, and the fonts pull 107 KiB of woff2 (four files) into the critical chain. Fixes (finding #1): **inline `leaflet.css`** into the existing `<style>`; **self-host + subset the fonts** (removes the blocking CSS *and* the cross-origin fetches); **async-load `leaflet.js`** and init on its `load` (it can't just be `defer`red — the IIFE needs `L`). This was under-weighted as "low" before the production numbers arrived; it isn't.

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
| **1** | Load (render-blocking) | ~2,110 ms of render-blocking third-parties gate first paint — the reason production mobile is **75**; LCP (5.0 s) is then a CARTO tile | PSI §6: `leaflet.js` 1,340 ms + `leaflet.css` 750 ms + Fonts CSS 780 ms; `index.html:102`/`104`/`1278` | inline `leaflet.css`; self-host + subset the fonts (107 KiB woff2 off the critical path); async-load `leaflet.js` | **Highest — every visit** |
| **2** | Network (live API) | Live queries define time-to-answer: TIGERweb ~5.7 s, Nominatim ~2.5 s, ArcGIS ~0.9 s | Firefox capture (§7) | pre-build the **decadal** state/federal legislative districts → cache-first `data/app/*.json` (extends P0/P2); ~5.7 s → ~200 ms | High (interaction) |
| **3** | Boot payload | Decorative scope-mask parses 83 KB school-board geometry + ~46 KB marker icons every boot — PSI puts the geometry in the 669 ms critical chain, icons at a 10-min cache TTL | `index.html:6508`→`1884`, `1401`, `1484`; PSI §6 | `coverage-outline.json` / `requestIdleCallback`; lazy-load icons | Medium |
| **4** | Rendering | Highlight drop-shadow ~3.7×'s pan-frame time (2.3 Mpx filter re-rasterized per frame) | `index.html:1010`; pan A/B 61.6 vs 16.7 ms | drop `filter` during `movestart`→`moveend`, or use a casing stroke | Medium (worse on low/mid mobile) |
| **5** | App code | Point-in-polygon has no per-feature bbox pre-reject — ~1.44 s in `pointInRing` | `index.html:3892`/`1517`; Firefox capture (§7) | compute+cache each feature's bbox, skip the ray-cast on a miss (helpers `featureBBox`/`bboxIntersect` already exist). **Inside the `point-in-polygon` ENGINE fence → port to sibling forks** | Medium |
| **6** | Load hygiene (PSI) | 60 KiB unused JS + 41 KiB minifiable JS/CSS (no-build tradeoff); oversized `@2x` tiles (56 KiB); 5 `preconnect`s (> 4) | PSI §6; `index.html:1750` (`{r}`→`@2x`), `90–98` (preconnects) | drop `{r}` for non-retina tiles (tradeoff); trim preconnects to ≤ 4; minify is a conscious no-build call | Low–Medium |

**Priority read.** #1 is the biggest *load* win and affects every visit — and it's mostly cheap (inline one stylesheet, self-host fonts); it's what moves the mobile 75. #2 is the biggest *interaction* win but the largest change. #3 restores the "download nothing you don't use" property (and helps #1's critical chain). #4 is the cheapest render fix (a movestart/moveend class); #5 is cheap but must port across the ENGINE fence; #6 is hygiene, part deliberate tradeoff. *(Dropped from this list: a color-contrast flag my in-sandbox proxy raised on `.empty-state-lede` — production **Accessibility = 100** doesn't reproduce it, since the empty-state renders below a full-height loaded map on mobile; a one-token darken to `--slate` is optional defensive hygiene. See §6.)*

### What's healthy (measured, no action)

- **Production mobile: TBT 0 ms, CLS 0, Accessibility / Best-Practices / SEO all 100.** The Performance 75 is entirely FCP+LCP (load delivery), not compute or layout.
- Cold boot (desktop): 116 ms FCP / ~117 ms interactive — **0 long tasks**, 32 ms script eval, 3.5 MB heap, 835 nodes, 33 layers.
- `index.html` at 89 KB gzip; the eleven `data/app/*.json` datasets correctly stay lazy (on-toggle), *except* the school-board file pulled early by finding #3.
- Point-move on the P7 incremental path: 8 ms CPU (restyles 2 paths, not all). Warm re-toggle on the P11 path: 3.3 ms synchronous rebuild.
- Memory/DOM growth bounded and proportionate; no leak observed across repeated toggles.

---

## 6. PageSpeed Insights — production mobile (Lighthouse 13.4.0)

The **real production run** (chidistricts.com, mobile, Slow-4G, emulated Moto G Power, Jul 16 2026). *I first ran a local proxy of this in-sandbox (same-origin Leaflet, stubbed fonts/tiles) which scored Performance 96 / FCP 1.8 s — **optimistic by exactly the third-party costs it couldn't reach**. The production numbers below supersede that proxy; the divergence is itself the lesson (see the note at the end).*

| Category | Score | | Metric (Slow-4G) | Value | Score points |
|---|--:|---|---|--:|--:|
| **Performance** | **75** | | First Contentful Paint | 3.3 s | 4 / 10 |
| Accessibility | **100** | | **Largest Contentful Paint** | **5.0 s** | **7 / 25** |
| Best Practices | **100** | | Total Blocking Time | **0 ms** | 30 / 30 ✓ |
| SEO | **100** | | Cumulative Layout Shift | **0** | 25 / 25 ✓ |
| Field data (CrUX) | No Data | | Speed Index | 3.4 s | 9 / 10 |

The score composition is the whole story: **TBT and CLS score full marks (55/55 points); the entire gap to 100 is FCP + LCP.** This is a *load-delivery* problem, not a main-thread or layout-shift problem — which agrees with §1 (0 long tasks) and the production capture (§7): the app's own compute is clean, but first paint waits on third-party resources.

**LCP is a basemap tile.** The LCP element is `c.basemaps.cartocdn.com/…/525/761@2x.png` — a CARTO map tile — with a **900 ms element-render delay + 500 ms load delay**. The tile can't paint until Leaflet initializes, which waits behind the render-blocking resources below. So the LCP lever is *cutting render-blocking*, not the tile.

### Opportunities (production, by estimated savings)

| Insight | Est. savings | What it is |
|---|--:|---|
| **Render-blocking requests** | **~2,110 ms** | `leaflet.js` (1,340 ms) + `leaflet.css` (750 ms) + Google-Fonts CSS (780 ms) block first paint |
| Improve image delivery | 56 KiB | CARTO `@2x` tiles are 512×512 for a 448×448 display, and PNG not WebP/AVIF |
| Efficient cache lifetimes | 42 KiB | `water-taxi.png` (27 KiB) + `cook-county.png` (18 KiB) served with a **10-minute** cache TTL |
| Reduce unused JavaScript | 60 KiB | 38 KiB of the inline app JS + 21 KiB of Leaflet unused at load |
| Minify JavaScript | 41 KiB | the inline IIFE (a deliberate no-build tradeoff — see below) |
| Minify CSS | 3 KiB | the inline `:root` stylesheet |
| Preconnect hygiene | — | **5 preconnect hints** (Lighthouse warns > 4) + 1 unused |

**Reconciliation with the rest of the report:**

- **Render-blocking (~2,110 ms) is the dominant load cost, and the #1 lever for both FCP (3.3 s) and LCP (5.0 s).** My sandbox stubbed all three culprits, so it never saw this. Realistic fixes, cheapest first: **inline `leaflet.css`** into the existing `<style>` (3.8 KiB — removes one blocking request outright); **self-host the fonts** (the Google-Fonts stylesheet is render-blocking and pulls **107 KiB of woff2** — four files at ~513 ms each in the critical chain; subsetting + same-origin `@font-face` removes both the blocking CSS and the cross-origin fetches); and — harder — restructure boot so `leaflet.js` isn't a synchronous blocker (it can't just be `defer`red, the IIFE needs `L`, so this means loading it async and initializing on its `load`).
- **Confirms finding #3 (boot payload).** `school-board-districts.json` (20 KiB) appears **in the initial-navigation critical chain at 669 ms** — the decorative scope-mask geometry loaded at boot, exactly as §2.1 found. The marker icons resurface under *cache lifetimes*: their 10-minute TTL is a **GitHub-Pages platform default** (not tunable without a CDN in front), so the lever is loading fewer/smaller icons lazily — again finding #3.
- **Confirms unused / minify JS.** 60 KiB unused, 41 KiB minifiable — the minify gap being the conscious no-build, one-readable-file tradeoff (gzip already recovers most of it on the wire; a prod-only minify step would reintroduce a build).
- **New: image delivery + preconnect hygiene.** The `@2x` retina tiles (Leaflet's `{r}` token resolves to `@2x` on any high-DPR phone, `index.html:1750`) are oversized for their CSS display box; dropping `{r}` trades tile crispness for ~56 KiB. And the page ships **5 `preconnect` hints** (`index.html:90–98`) where Lighthouse wants ≤ 4, with one flagged unused — trim the least-important (e.g. a second tile shard).
- **Corrects my local a11y flag.** Production **Accessibility = 100.** My stubbed local run flagged `.empty-state-lede` contrast (#87929B on white ≈ 3.2 : 1 by the numbers, `index.html:1018`), but production PSI does **not** — on mobile the empty-state renders below a full-height loaded map and isn't caught. It's a *latent* borderline token, not a live finding, so it's **dropped from the prioritized list**; a one-token darkening to `--slate` remains cheap defensive hygiene if desired. **Best-Practices = 100** likewise confirms the earlier "console errors were a harness artifact" call.

**Bottom line + the lesson.** Production mobile is **75 (needs-improvement)**, and essentially everything holding it there is **third-party load delivery** — render-blocking Leaflet + Google Fonts, then a CARTO tile as the LCP element. The app's *own* work is already green (TBT 0 ms, CLS 0, main-thread clean). My in-sandbox proxy scored 96 because it stubbed exactly those third-parties — a textbook case of this report's own "environment-independent vs not" caveat: the boot **compute** numbers (§1) transferred (production TBT is 0 ms), but the **network/paint** numbers did not, and only the real production run surfaces the render-blocking that dominates mobile.

## 7. Production Firefox Profiler capture (cross-check)

A 58.5 s real-hardware capture (i7-1065G7 · Firefox 152 · Win 11) of a **warm interaction session** on the live site — panning + toggling political layers over a Will County point (`#point=41.578,-88.065&layers=county`), hitting the real APIs and tiles. This is the only lens that sees production live-API latency, GC, and real Leaflet render cost. **Caveat:** one session, one point, one machine — directional, not an average; and it's *interaction*, not cold load (its 610 ms LCP is a retained earlier warm-load figure, not this capture's headline).

Headline numbers: main thread **28 % busy** (16.4 s CPU over 58.5 s, bursty); **slowest request 5.69 s** (Census TIGERweb legislative); long tasks **7.8 s** across 60 blocks (biggest 766 ms); **GC/CC 3.5 s** incl. a 999 ms full-GC pause; worst frame gap 1.9 s; `eventDelay` p95 822 ms / p99 1,487 ms during the toggle burst, but ~60 fps (16.7 ms median frame) outside it. Page JS splits **Leaflet 4,155 ms vs app 1,729 ms**; the single hottest app function is **`pointInRing` 1,437 ms**; 47 CARTO tiles totalled 23.9 s of transfer.

**What it uniquely establishes, and how it reconciles with the two lab lenses:**

- **Live-API latency is the real time-to-answer** (finding #2) — invisible to my sandbox and to the production PSI *load* pass, both of which measure page load, not a live-query interaction session. This is the top *interaction* finding.
- **The point-in-polygon bbox gap** (finding #5) — 1.44 s in `pointInRing` over a long session. My sandbox scenario (small offline layers, short session) never stressed it; this capture makes it concrete.
- **Leaflet SVG reproject/repaint dominates client render** — agrees with my point-move CPU profile (the hot frames are all Leaflet `project`/`_projectLatlngs`/`_clipPoints`) and points to the same structural fix (Canvas renderer / OPTIMIZATION_PLAYBOOK P10). My drop-shadow A/B (finding #4) is a *component* of the Graphics/Layout cost this capture aggregates — real, cheap to fix, but ranked below live-API and the Leaflet-render bulk on real hardware.
- **Compute is light; cold-mobile *load* is not.** The capture's aside that "the page itself is light" (610 ms warm LCP) and my 116 ms desktop FCP both reflect the app's clean *compute* — but they're warm and/or desktop-unthrottled. The production PSI cold-mobile run (§6) shows the load side plainly: render-blocking third-parties push FCP to 3.3 s and LCP (a tile) to 5.0 s. No contradiction — the *engine* is light, the *cold-mobile delivery* is the cost (finding #1), and the *live-data interaction* is this capture's own headline (finding #2).

The three lenses are complementary: **§1–4 (sandbox Chrome)** own cold-boot / payload / the controlled render A/B; **§6 (production PageSpeed Insights)** owns the real mobile scores + the render-blocking / load audits; **§7 (production Firefox)** owns real live-API / GC / Leaflet-render cost. No lens contradicts another where they overlap — and where they do (my proxy's 96 vs PSI's 75), §6 explains why.

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

**§6 production PageSpeed Insights** — the authoritative numbers come from running PSI/Lighthouse against the **live site** (needs real egress this sandbox lacks): [pagespeed.web.dev](https://pagespeed.web.dev/) on `https://chidistricts.com/` (mobile), or `npx lighthouse https://chidistricts.com/ --form-factor=mobile`, or the PSI API with a key. The **in-sandbox proxy** (optimistic; see §6) reproduces as: `bash scripts/vendor_leaflet.sh`, serve `index.html` with the cdnjs Leaflet `<link>`/`<script>` rewritten same-origin and the fonts `<link>` removed so Chrome can boot it offline, then `npx lighthouse http://localhost:<port>/ --form-factor=mobile`. **§7** is a Firefox Profiler export, not reproducible from this repo — treat its numbers as the cited external capture.

**Reading the results as this document does:** trust payload bytes, `ScriptDuration`, node/heap counts, CPU-sample shape, and every A/B ratio as-is; treat raw paint/pan wall-times as *relative* (headless software rendering inflates them); and label any claim about the live-API layers or real CDN/tile latency as inferred — this harness intentionally never touches them.

---

## Production verification (2026-07-16) — R2 shipped, then measured live

A production PageSpeed Insights **mobile** run after Round 2 deployed (chidistricts.com):

| Metric | Pre-R2 baseline | Post-R2 | Post-self-host (final) |
|---|---|---|---|
| FCP | 3.3 s | 1.2 s | **1.2 s** |
| Speed Index | 3.4 s | 1.6 s | **1.3 s** ✅ |
| LCP | 5.0 s | 6.4 s | **5.9 s** ✅ |
| TBT | 0 ms | 70 ms | 70 ms |
| CLS | 0 | 0.054 | 0.052 |
| **Performance** | 75 | 76 | **78** |

**R2-1 landed as designed** — render-blocking elimination cut FCP −2.1 s and Speed Index −1.8 s. The score barely moved (75→76) because LCP (25%) + CLS (25%) + TBT (30%) = 80% of the weight, and:

- **LCP is now a basemap tile** (`*.basemaps.cartocdn.com/…@2x.png`). With FCP fast, the largest paint is the map tile, gated on tile delivery over Slow 4G. PSI's fix: **preconnect the tile shards** (a/b/c/d, ~160 ms each) — which means the **R2-7 preconnect trim (dropping `b.`) was the wrong direction**, the ambiguity §6 flagged, now resolved by data.
- **CLS 0.054** is the **async font swap** (R2-1's `media=print` + `display=swap` → FOUT reflow of `main.layout`).
- **TBT 70 ms is Google Tag Manager** (third-party analytics), not app code.

**Fix shipped + re-measured (the self-hosting §6 held for data):** fonts self-hosted (`scripts/build_fonts.py`, same-origin `@font-face`), the two font preconnects reallocated to the tile shards (a/b/c), a metric-matched `Inter Fallback` added. The **post-self-host PSI** (third column) confirms it: **LCP 6.4→5.9 s** and **Speed Index 1.6→1.3 s**, score **76→78** — the tile-preconnect reallocation worked.

Two honest results:
- **CLS barely moved (0.054→0.052).** The `Inter Fallback` uses `src: local('Arial')`, and the Moto G Power PSI device (Android) has **no Arial**, so the metric-match never fires there — it helps Win/Mac users but can't move the Android number. CLS 0.052 stays in the "good" range.
- **The map-tile LCP is near its Slow-4G floor.** It loads after Leaflet + map init (~220 ms delay) then downloads over throttled 4G; preconnects shave a little but PSI flags them "unused" (the tiles request too late to reuse the warmed connection). 5.9 s is close to the practical floor for a map app on Slow 4G.

**Tradeoff frontier (2026-07-16, banked at 78).** Every remaining PSI lever now costs something real, so the campaign rests here: dropping `{r}`/@2x tiles buys LCP + 56 KB but blurs the basemap on retina (bad for reading street labels); `font-display: optional` zeroes the CLS but shows fallback fonts to first-time visitors; deferring **Google Tag Manager** clears TBT (70 ms) + 66 KB unused JS but it's the owner's analytics; minifying the inline JS/CSS (−47 KB) breaks the single-file no-build design. The one non-tradeoff experiment left is collapsing the 4 sharded tile hosts to one (HTTP/2 multiplexes anyway) — uncertain, needs a real-device capture. The remaining *app-side* lever is the canvas renderer (**OPTIMIZATION_PLAYBOOK §7**), which targets pan/zoom interaction, not the PSI load score.
