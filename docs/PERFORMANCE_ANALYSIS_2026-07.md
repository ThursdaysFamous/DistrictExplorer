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
- **§6 — Lighthouse mobile.** A Lighthouse 13.4.0 run (default mobile config: Moto G4, slow-4G, 4× CPU, *simulated* throttling) against a **local serve of this exact tree**. Chrome in the sandbox can't reach the Leaflet CDN / Google Fonts, so that serve rewrites Leaflet to a same-origin vendored copy and neutralizes the render-blocking font `<link>` — i.e. it measures the **app-intrinsic** mobile profile; production adds its third-party render-blocking + real-tile costs *on top* (reasoned in §6). This stands in for the production PageSpeed Insights mobile run, which couldn't be read directly (its results render client-side and the keyless PSI API is quota-limited). One caveat that matters: Lighthouse's *errors-in-console* / some *best-practices* dings in this run are **harness artifacts** (the sandbox's blocked tile/CDN requests log `ERR_CONNECTION_RESET`), not real app errors — excluded from the findings.
- **§7 — production Firefox Profiler capture.** A 58.5 s real-hardware (i7-1065G7, Firefox 152) capture of a **warm interaction session** hitting the live APIs — the one lens that sees real live-API latency, GC pressure, and Leaflet render cost. Single session / point / machine: directional, not a benchmark average.

Field data: the Chrome UX Report (CrUX) has **no real-user data** for this page, so the production PSI card shows Lighthouse *lab* data only — the same kind of lab figures reported here.

---

## Executive summary

**The app is fast and lean, and the 2026-07 optimization work clearly holds.** Cold boot (desktop, unthrottled) reaches first contentful paint in ~116 ms and becomes interactive in ~117 ms with **zero long tasks**, ~32 ms of script evaluation, a 3.5 MB heap, and 835 DOM nodes — this despite 33 registered layers. Under **Lighthouse mobile** emulation (Moto G4, slow-4G, 4× CPU throttle) the same page scores **Performance 96 / Accessibility 96 / Best-Practices ~100 / SEO 100**, with FCP 1.8 s, LCP 2.1 s, TBT 100 ms, and **CLS 0.012** (essentially no layout shift). The incremental-restyle fast path (P7) keeps a point-move at ~8 ms of CPU, and the layer-graph release (P11) makes a warm re-toggle a ~3 ms synchronous rebuild. Nothing here is on fire.

**This revision folds in two external cross-checks** so the report is one combined picture: a **production Firefox Profiler capture** (real hardware, warm interaction session over a Will County point — §7) and a **Lighthouse mobile run** (§6). Findings sourced from those are attributed inline; my own sandbox measurements are the backbone.

The findings are refinements, ranked by user-perceived impact:

1. **Live-API latency dominates real-world time-to-answer** — TIGERweb legislative ~5.7 s, Nominatim ~2.5 s, ArcGIS ~0.9 s (measured on production by the Firefox capture; my sandbox blocks these APIs). The decadal state/federal legislative districts are a natural pre-build → cache-first `data/app/*.json` candidate, turning a ~5.7 s live query into a ~200 ms same-origin fetch. *(network; highest real-world impact — external capture)*
2. **The selection-highlight drop-shadow filter ~3.7×'s pan-frame time** (61.6 ms vs 16.7 ms filter-off, over a 2.3-megapixel region). *(rendering; medium — worse on low/mid mobile)*
3. **Point-in-polygon has no bounding-box pre-reject** — `findFeatureContaining` (`index.html:3892`) ray-casts every feature; the Firefox capture measured **~1.44 s in `pointInRing`**. Bbox helpers already exist in the file (used by the hover feature, not here). *(app code; medium — inside the `point-in-polygon` ENGINE fence, so a fix must port to sibling forks)*
4. **Boot eagerly downloads the 83 KB school-board geometry (decorative wash) + ~46 KB marker icons every visit** — Lighthouse's byte-weight table independently ranks these as the 2nd–5th heaviest boot resources, corroborating the finding. *(boot payload; medium)*
5. **Render-blocking + unminified/unused JS** — Lighthouse flags render-blocking Leaflet (~462 ms) and (on production) Google-Fonts CSS, **62 KB unused JS**, and **43 KB unminifiable JS/CSS** — the last a real tension with the deliberate no-build, one-readable-file design. *(FCP / payload; low–medium)*
6. **One WCAG-AA color-contrast failure** — `.empty-state-lede` (the default pre-selection intro text, `index.html:1189`) is `--slate-soft` #87929B on white ≈ **3.2 : 1**, below the 4.5 : 1 AA bar. *(accessibility; low — one-token fix)*

Everything else measured — heap growth, DOM growth, toggle/classify latency, and CLS — is healthy. Details and fixes below.

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
| **1** | Network (live API) | Live queries define time-to-answer: TIGERweb ~5.7 s, Nominatim ~2.5 s, ArcGIS ~0.9 s | Firefox capture (§7) | pre-build the **decadal** state/federal legislative districts → cache-first `data/app/*.json` (extends P0/P2); ~5.7 s → ~200 ms | **Highest (real-world)** |
| **2** | Rendering | Highlight drop-shadow ~3.7×'s pan-frame time (2.3 Mpx filter re-rasterized per frame) | `index.html:1010`; pan A/B 61.6 vs 16.7 ms | drop `filter` during `movestart`→`moveend`, or use a casing stroke | Medium (higher on low/mid mobile) |
| **3** | App code | Point-in-polygon has no per-feature bbox pre-reject — ~1.44 s in `pointInRing` | `index.html:3892`/`1517`; Firefox capture (§7) | compute+cache each feature's bbox, skip the ray-cast on a miss (helpers `featureBBox`/`bboxIntersect` already exist). **Inside the `point-in-polygon` ENGINE fence → port to sibling forks** | Medium |
| **4** | Boot payload | Decorative scope-mask parses 83 KB school-board geometry + ~46 KB marker icons every boot | `index.html:6508`→`1884`, `1401`, `1484`; LH byte-weight (§6) | `coverage-outline.json` / `requestIdleCallback`; lazy-load icons | Medium |
| **5** | FCP / payload | Render-blocking Leaflet (~462 ms) + Google-Fonts CSS; 62 KB unused JS; 43 KB unminifiable JS/CSS | `index.html:102`; LH (§6) | inline/self-host critical CSS; the minify gap is a conscious no-build tradeoff (see §6) | Low–Medium |
| **6** | Accessibility | `.empty-state-lede` contrast ≈ 3.2 : 1, below WCAG-AA 4.5 : 1 | `index.html:1018`/`1189`; LH color-contrast (§6) | `--slate-soft` → `--slate` (#55626C ≈ 6 : 1) for this rule | Low (trivial) |

**Priority read.** #1 is the biggest *real-world* win (it's what makes a card feel slow) but the largest change; #2 and #6 are the cheapest high-value fixes (a movestart/moveend class; a one-token color swap); #3 is cheap and reuses existing helpers but must port to sibling forks per the engine-parity rules; #4 restores the "download nothing you don't use" property; #5 is partly a deliberate design tradeoff.

### What's healthy (measured, no action)

- Cold boot: 116 ms FCP / ~117 ms interactive (desktop) — **0 long tasks**, 32 ms script eval, 3.5 MB heap, 835 nodes, 33 layers. Under Lighthouse mobile: **CLS 0.012** (no layout shift), **TBT 100 ms**, main-thread work 1.6 s — all in the green.
- `index.html` at 89 KB gzip; the eleven `data/app/*.json` datasets correctly stay lazy (on-toggle), *except* the school-board file pulled early by finding #4.
- Point-move on the P7 incremental path: 8 ms CPU (restyles 2 paths, not all). Warm re-toggle on the P11 path: 3.3 ms synchronous rebuild.
- Memory/DOM growth bounded and proportionate; no leak observed across repeated toggles. SEO 100; Best-Practices ~100 once the sandbox's blocked-request console noise is excluded.

---

## 6. Lighthouse mobile (cross-check)

A Lighthouse 13.4.0 pass, default **mobile** config (Moto G4, slow-4G, 4× CPU, *simulated* throttling), against a local serve of this tree. This stands in for the production PageSpeed Insights mobile run (unreadable directly — client-rendered results + a quota-limited keyless API + no sandbox egress to production). **Fidelity:** Leaflet is served same-origin and the render-blocking font `<link>` neutralized so the app boots, so this is the **app-intrinsic** profile — production adds third-party render-blocking + real tiles on top, so its scores run a little lower.

| Category | Score | | Metric (mobile-throttled) | Value |
|---|--:|---|---|--:|
| Performance | **96** | | First Contentful Paint | 1.8 s |
| Accessibility | **96** | | Largest Contentful Paint | 2.1 s |
| Best Practices | ~100\* | | Total Blocking Time | 100 ms |
| SEO | **100** | | Cumulative Layout Shift | **0.012** |
| | | | Speed Index | 3.6 s |
| | | | Time to Interactive | 2.2 s |

\* *The raw run shows 96, docked only by an `errors-in-console` audit whose entries are all `net::ERR_CONNECTION_RESET` from the **sandbox's blocked tile/CDN requests** — a harness artifact, not a production error. Production's console is clean, so Best-Practices is effectively 100.*

**New findings this surfaces (beyond the sandbox pass):**

- **62 KB unused JavaScript at load** — 38 KB of `index.html`'s inline JS + 25 KB of Leaflet. Both are *expected* for this architecture (a single file that registers all 33 layer modules up front, and a full mapping lib used partially) rather than a defect — but it's the largest byte opportunity Lighthouse names. Deferring per-layer module bodies until first toggle would cut initial parse; it also cuts against the "one hand-readable file, no build" value, so it's a design call, not a clear win.
- **43 KB of unminifiable JS/CSS** (40 KB JS + 3 KB CSS). This is a **direct tension with the deliberate no-build / one-readable-file design** — Lighthouse always wants minification, the repo explicitly ships readable source. Gzip already recovers most of it on the wire (the gzipped delta is far smaller than 43 KB), and a production-only minify step would reintroduce a build. Worth stating as a conscious tradeoff, not silently "failing."
- **Render-blocking resources** — Lighthouse attributes ~462 ms to Leaflet's `<script>` and ~162 ms to `leaflet.css` under mobile throttle, *plus* (on production, stubbed here) the Google-Fonts stylesheet. Leaflet's script can't simply be `defer`red (the boot IIFE needs `L` synchronously — see the OPTIMIZATION_PLAYBOOK anti-finding), so the realistic wins are self-hosting/inlining the two stylesheets and, longer-term, trimming how much Leaflet loads. Folded into finding #5.
- **One color-contrast failure (Accessibility)** — the only thing between the app and a 100 a11y score: `.empty-state-lede` (`index.html:1018`) — the intro copy shown in the results panel before any point is picked (`:1189`) — is `--slate-soft` **#87929B on white ≈ 3.2 : 1**, under the 4.5 : 1 AA bar for 12.5 px text. Swapping that one rule to `--slate` (#55626C ≈ 6 : 1) fixes it with no layout change. Finding #6.

**What it corroborates:** Lighthouse's total-byte-weight table (196 KB) ranks the boot resources **index.html 87 KB → leaflet.js 42 KB → water-taxi.png 26 KB → school-board-districts.json 20 KB → cook-county seal 18 KB** — i.e. the eager marker icons and the decorative-wash geometry are independently the 3rd–5th heaviest things loaded at boot, exactly finding #4. And CLS 0.012 / TBT 100 ms confirm the boot compute path is clean.

## 7. Production Firefox Profiler capture (cross-check)

A 58.5 s real-hardware capture (i7-1065G7 · Firefox 152 · Win 11) of a **warm interaction session** on the live site — panning + toggling political layers over a Will County point (`#point=41.578,-88.065&layers=county`), hitting the real APIs and tiles. This is the only lens that sees production live-API latency, GC, and real Leaflet render cost. **Caveat:** one session, one point, one machine — directional, not an average; and it's *interaction*, not cold load (its 610 ms LCP is a retained earlier warm-load figure, not this capture's headline).

Headline numbers: main thread **28 % busy** (16.4 s CPU over 58.5 s, bursty); **slowest request 5.69 s** (Census TIGERweb legislative); long tasks **7.8 s** across 60 blocks (biggest 766 ms); **GC/CC 3.5 s** incl. a 999 ms full-GC pause; worst frame gap 1.9 s; `eventDelay` p95 822 ms / p99 1,487 ms during the toggle burst, but ~60 fps (16.7 ms median frame) outside it. Page JS splits **Leaflet 4,155 ms vs app 1,729 ms**; the single hottest app function is **`pointInRing` 1,437 ms**; 47 CARTO tiles totalled 23.9 s of transfer.

**What it uniquely establishes, and how it reconciles with the two lab lenses:**

- **Live-API latency is the real time-to-answer** (finding #1) — invisible to my sandbox and to the app-intrinsic Lighthouse pass, both of which stub the network. This is the most important production finding and belongs at the top of the list.
- **The point-in-polygon bbox gap** (finding #3) — 1.44 s in `pointInRing` over a long session. My sandbox scenario (small offline layers, short session) never stressed it; this capture makes it concrete.
- **Leaflet SVG reproject/repaint dominates client render** — agrees with my point-move CPU profile (the hot frames are all Leaflet `project`/`_projectLatlngs`/`_clipPoints`) and points to the same structural fix (Canvas renderer / OPTIMIZATION_PLAYBOOK P10). My drop-shadow A/B (finding #2) is a *component* of the Graphics/Layout cost this capture aggregates — real, cheap to fix, but ranked below live-API and the Leaflet-render bulk on real hardware.
- **Corroborates that cold load isn't the problem** — its aside that "the page itself is light" (610 ms LCP) matches my cold-boot data (116 ms FCP; Lighthouse mobile LCP 2.1 s). The pain is *interaction over live data*, not load.

The three lenses are complementary: **§1–4 (sandbox Chrome)** own cold-boot / payload / the controlled render A/B; **§6 (Lighthouse mobile)** owns the throttled-mobile scores + a11y/minify audits; **§7 (production Firefox)** owns real live-API / GC / Leaflet-render cost. No lens contradicts another where they overlap.

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

**§6 Lighthouse mobile** (app-intrinsic, per its fidelity note) — serve this tree with Leaflet vendored same-origin, then run Lighthouse's default mobile config:

```bash
bash scripts/vendor_leaflet.sh          # in a CDN-blocked sandbox
# serve index.html with the cdnjs Leaflet <link>/<script> rewritten to the
# vendored copy and the fonts <link> removed (so Chrome can boot it offline), then:
npx lighthouse http://localhost:<port>/ --form-factor=mobile --only-categories=performance,accessibility,best-practices,seo --chrome-flags="--headless=new --no-sandbox"
```

Against production directly (from a machine with real egress, no rewrite needed): `npx lighthouse https://chidistricts.com/ --form-factor=mobile`, or PageSpeed Insights / the PSI API with a key. **§7** is a Firefox Profiler export, not reproducible from this repo — treat its numbers as the cited external capture.

**Reading the results as this document does:** trust payload bytes, `ScriptDuration`, node/heap counts, CPU-sample shape, and every A/B ratio as-is; treat raw paint/pan wall-times as *relative* (headless software rendering inflates them); and label any claim about the live-API layers or real CDN/tile latency as inferred — this harness intentionally never touches them.
