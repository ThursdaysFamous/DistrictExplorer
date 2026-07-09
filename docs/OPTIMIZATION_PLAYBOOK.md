# Optimization & Refinement Playbook

**Repo:** ThursdaysFamous/DistrictExplorer · **Date:** 2026-07-09 · **Scope:** `index.html` (2,811 lines, 1.30 MB), `sw.js`, `scripts/` pipeline, `.github/workflows/`, Capacitor wrappers

All numbers below were measured against this working tree unless marked *(not live-verified)* — the same convention the codebase itself uses for claims that couldn't be checked from the build sandbox.

---

## 1. Executive Summary

This is an unusually disciplined codebase for its size: per-layer failure isolation is real, stale async results are sequenced away, external strings are sanitized at one choke point, scrapers are polite and PR-gated, and design constraints (single file, no build step, `file://` support, never-guess-officeholders) are written down and honored. The playbook below deliberately works **within** those constraints; where a recommendation would bend one, it says so explicitly.

The findings, in order of user impact:

1. **One data blob dominates everything.** `SCHOOL_BOARD_DISTRICTS_GEOJSON` (line 2553) is **975,797 bytes — 75% of the entire page** — carrying 24,904 coordinate pairs at up to **15 decimal places (nanometer precision)**. The two sibling embedded layers (IL Supreme Court, CCBR) already received a documented "topology-preserving simplification" treatment (5-decimal, validated with random-point classification); the school-board layer never did. Applying the identical treatment shrinks it to **57.7 KB (−94%)** and shrinks the whole page from **1.30 MB → 384 KB raw (428 KB → 106 KB gzipped)**, with **99.98% classification agreement across 5,000 in-district test points** (the single disagreement lies within the 5.5 m simplification tolerance of a district boundary). This one change cuts first-load bytes by ~75%, cuts the service worker's background revalidation traffic by the same, cuts both app binaries, and speeds `JSON.parse` at boot.

2. **Runtime over-fetch on the network layers.** The U.S. House card downloads the complete `legislators-current.json` roster (every member of Congress, full term history — multi-MB *(not live-verified; egress blocked)*) to display one representative, and the TIGERweb layers download full-resolution statewide geometry with `outFields=*`. The repo already owns the correct pattern for the first problem — build-time roster embedding via a weekly scraper PR (ILGA, CPD) — and the second has a server-side fix (`maxAllowableOffset`, trimmed `outFields`) that keeps the overlay visuals.

3. **Small architecture debts, honestly labeled.** A verbatim duplicate of the cached-loader factory (`makeCached` at 2081 vs `makeCachedLoaderFromFn` at 1581 — the comment even admits it), duplicated Socrata route-fallback walkers, and a click path that runs the same point-in-polygon scan twice per layer and restyles every SVG path of every active layer on every click.

4. **A process gap that will eventually ship a broken page.** Two GitHub Actions regex-rewrite `index.html` weekly and open PRs, but nothing anywhere validates that the rewritten 1.3 MB file still parses and boots. There are no tests of any kind. One malformed replacement away from a blank page.

---

## 2. Performance Optimization Plan

### 2.1 Payload & startup (the big one)

**P1 — Simplify the school-board geometry (measured: −918 KB raw, −322 KB gzipped).**
`index.html:2553`. The blob was embedded from the ERSB shapefile without the simplification pass its two siblings got (their provenance comment at `index.html:2605-2619` documents "reprojected NAD83 → WGS84 and topology-preserving-simplified for embedding — classification agreement … 100% across 2,000 random in-city test points"). Measured on this tree:

| Layer (embedded line) | Coord pairs | Max decimals | Bytes |
|---|---|---|---|
| School board (2553) | 24,904 | **15** | 975,797 |
| IL Supreme Court (2620) | 4,771 | 5 | 99,810 |
| CCBR (2658) | 2,916 | 5 | 61,009 |

Douglas-Peucker at ~5.5 m tolerance + 6-decimal rounding → **2,394 coord pairs, 57,736 bytes**, `index.html` = 383,923 bytes raw / 105,974 gzipped. Validation: 5,000 random points *inside* the original districts, classified with the app's own even-odd `pointInGeometry` algorithm → 4,999/5,000 agreement (99.98%). See §5 Quick Win 1 for the exact change. Commit the generator as `scripts/build_embedded_boundaries.py` so the blob is regenerable (today the geometry blobs — unlike the rosters — have no scripted path; that's finding R6).

**P2 — Defer `JSON.parse` of embedded blobs to first toggle.**
Lines 2553/2620/2658 execute `JSON.parse` on ~1.14 MB of string at script-eval time on *every* page load, even when none of the three layers is ever toggled (they are off by default). The loaders are already promise-shaped (`loadSchoolBoardDistricts` at 2554 wraps the parsed constant in `Promise.resolve`), so the change is mechanical: store the raw string, parse inside the existing `makeCached` wrapper — first toggle pays the parse, and the parsed object is retained by the same cache that retains it today. After P1 this is ~220 KB of string instead of 1.14 MB, so it drops from "tens of ms on low-end mobile" to noise — do it in the same commit as P1 while you're editing those lines.

**P3 — Replace the runtime congress-legislators download with a build-time roster (consistent with existing architecture).**
`index.html:2195-2197`:

```js
var loadCongressLegislators = makeCached(function () {
  return fetchJSONWithRetry("https://unitedstates.github.io/congress-legislators/legislators-current.json", {}, 1);
});
```

Every browser that toggles the U.S. House layer downloads the full national roster — every legislator, every term ever served — to `filter()` out one IL representative (`index.html:2218-2222`). The repo already has the exact pattern this should use: `scripts/ilga_scraper.py` + `build_il_roster.py` + a weekly PR-gated Action embed the *resolved current officeholder per district* directly into `index.html`. An `IL_CONGRESS_MEMBERS` object for IL's 17 districts is ~3–4 KB embedded, eliminates a multi-MB runtime fetch *(size not live-verified)*, removes the layer's dependency on a third-party host at runtime, and even improves the `file://` story. The source can remain `legislators-current.json` — fetched once a week by CI instead of once per user.

**P4 — Server-side generalization for TIGERweb layers.**
`index.html:2115-2120` (`loadTigerLayer`) fetches Congressional/SLDU/SLDL boundaries for all of Illinois at full resolution with `outFields=*`. Esri REST supports `maxAllowableOffset` (generalize geometry server-side to the display tolerance) and explicit `outFields` lists — the app only reads the district-number fields (`CONGRESS_DISTRICT_FIELDS` at 2198, `districtFields` per chamber at 2534) plus a name-field fallback. Adding `&maxAllowableOffset=0.0001&outFields=BASENAME,NAME,CD119FP,SLDUST,SLDLST` (tune per layer) keeps the overlay visually identical at city zoom and typically cuts Esri payloads by 5–20× *(exact delta not live-verified; egress blocked)*. Same applies to `loadCookCountyLayerGeoJSON` (2709) and `loadArcGISGeoJSON` (1606), both of which use `where=1=1&outFields=*`.

### 2.2 Interaction path

**P5 — The same point-in-polygon scan runs twice per layer per click, then every path gets restyled.**
Click → `runLayerQuery` (1470) → `mod.query()` → `findFeatureContaining(rt.geojson, point)` … then the `.then` at 1479 calls `updateLayerHighlight(mod)` (1215), which calls `findFeatureContaining` **again** on the same cached geojson, then `eachLayer`+`setStyle` over *every* sub-layer (1223-1234) — for every active layer, on every click. `refreshActiveLayerOpacities` (1130) triggers the same full sweep on every toggle. With the school zones active (hundreds of attendance polygons) that's hundreds of SVG attribute rewrites per click.
Fixes, in increasing ambition: (a) memoize the match — have `updateLayerHighlight` accept the feature the query already found (or cache `{seq, feature}` on `rt`); (b) restyle only the two affected paths (previous highlight, new highlight) instead of `eachLayer` when only the selection changed — the faded/base style for the other paths only changes when the *active-layer count* changes; (c) add a per-feature bbox pre-check to `findFeatureContaining` (1628) — compute bboxes once at load, skip ray-casting features whose bbox excludes the point. Each is small and independent.

**P6 — Memoize POI geocoding.**
`geocodePoiAddress` (1252) hits Nominatim for the office address on every render — click three points in the same ward and the same alderman office address geocodes three times. A `Map` keyed by address string (the result never changes within a session) is one line of state and is also politer to a shared public service whose usage policy the geocoder code already respects (see the 550 ms debounce comment at 1036).

### 2.3 Delivery & caching

**P7 — `sw.js` shell entries: `"./"` and `"./index.html"` double-store the page.**
`sw.js:4-12` lists both; each is cached as a separate Cache Storage entry (2.6 MB today, ~770 KB after P1), and the stale-while-revalidate fetch handler (43-63) re-downloads the full page in the background per navigation. After P1 the revalidation cost drops 75%, which is the real fix; normalizing to one entry is polish. Two genuine correctness notes while in the file: `CACHE_NAME` is fixed at `"district-explorer-shell-v1"`, and the activate handler only deletes *other-named* caches — an entry removed from `SHELL_URLS` in a future edit would live in cache forever until the name is bumped; and the `response.ok` check in the fetch handler (49) means opaque responses would never refresh — currently harmless because both cdnjs entries use `crossorigin` (CORS, non-opaque), worth a comment so nobody adds a non-CORS shell URL.

**P8 — Preconnect the tile CDN.**
First map paint is gated on DNS+TLS to `a–d.basemaps.cartocdn.com` (tile layer added at `index.html:773` as soon as the script runs), but the `<head>` only preconnects Google Fonts (13-14). Adding preconnects for the tile subdomains (and `cdnjs.cloudflare.com`, used by both head CSS and body JS) shaves a round trip off every cold load. Exact diff in §5 Quick Win 2.

**P9 — Trim unused font weights.**
Line 15 requests 10 weights across 3 families (Big Shoulders 600/700/800/900, Inter 400/500/600/700, IBM Plex Mono 400/500). The stylesheet uses weights 400/500/600/800/900 and contains no `<strong>`/`<b>` (so no implicit 700). Dropping Big Shoulders 700 and Inter 700 saves two font files (~25–40 KB) and is a one-line edit to the Google Fonts URL.

### 2.4 Memory

**P10 — Overlay caches are unbounded but acceptable — document it.**
Every toggled layer's full GeoJSON is retained forever (`rt.geojson` + the Leaflet layer + the `makeCached` promise). Worst case (every layer toggled once) is tens of MB after the school-zone layers load. That's a deliberate simplicity/speed trade-off that mostly suits this app; the one place it stings is low-end Android WebViews inside the Capacitor shell. Cheap mitigation if it ever matters: drop `rt.overlayLayer` (the Leaflet object, not the geojson) when a layer is toggled off — rebuild from `rt.geojson` on re-toggle is fast. Not worth doing preemptively; noted so it's a decision rather than an accident.

---

## 3. Refactoring & Code Quality

**R1 — Delete the duplicate cached-loader factory.**
`makeCached` (`index.html:2081-2089`) is line-for-line identical to `makeCachedLoaderFromFn` (1581-1592); the comment above it even says the earlier one "predates this." Keep one name, delete the other, update ~8 call sites. Zero-risk deletion of dead weight in the file's most load-bearing abstraction. Exact diff in §5 Quick Win 3.

**R2 — Extract the Socrata route-walker.**
`loadSocrataGeoJSON` (1560-1577) and `loadSocrataJSON` (2093-2110) duplicate the same `tryRoute(i)` fallback recursion (including the subtle single-catch-per-route fix, whose rationale comment appears in one and is referenced by the other). Extract `tryRoutes(urls, validate)` and both become two-liners; the retry-count asymmetry (`i === 0 ? 2 : 1`) lives in one place.

**R3 — Deduplicate office-address assembly in the commissioner module.**
`index.html:2759-2762` (render) and 2774-2777 (pointOfInterest) build the same `[district_a, suite, city+zip]` lines twice with copy-pasted `findPropCI` calls. Build it once in `query()` and put the assembled lines on the result object — which is also where every other module does this kind of work.

**R4 — Separate data from code *within* the single file.**
The single-file constraint is load-bearing (file://, no build step) — keep it. But the file currently interleaves three kinds of content: hand-written code, generated rosters (`IL_SENATE_MEMBERS`, `IL_HOUSE_MEMBERS`, `CPD_DISTRICT_INFO`), and generated geometry (three `JSON.parse` lines). Moving all generated data to `<script type="application/json" id="data-...">` tags in a clearly-fenced "GENERATED DATA" section at the end of the file (parsed lazily by the loaders — this is also P2) gets you: cleaner diffs for the weekly roster PRs (JSON text nodes, not JS object literals), simpler and safer builder scripts (`build_il_roster.py`'s `replace_block` regex over JS literals and its `</script`-escaping comment at `scripts/build_il_roster.py:73-83` become plain JSON serialization — the `<\/` escape is still needed but the JS-literal parsing risk disappears), and a file where "code above the fence" is reviewable at a glance. This is the highest-leverage maintainability change available without touching the architecture philosophy.

**R5 — Add a boot smoke-test to CI (the missing safety net).**
`update-ilga-roster.yml` and `update-cpd-roster.yml` regex-rewrite `index.html` weekly and open PRs. `build_il_roster.py` refuses incomplete rosters (guardrail at 119-126 — good), but *nothing* checks that the resulting file still parses and boots. A ~40-line workflow step — serve the tree, load it headless (Chromium + Playwright), assert `window.ChiExplorer` exists (already exported at 2794-2804 "for later module threads / debugging"), assert 18 layers registered, click a known point and assert the ward/community-area cards render expected districts using the embedded layers — turns "the bot PR looks plausible" into "the bot PR provably boots." Run it on `pull_request` so human PRs get it too. This is the single best DevEx investment in the repo, precisely because a 2,811-line hand-edited file with machine-rewritten sections is the risk profile tests exist for.

**R6 — Script the geometry-embedding path.**
The rosters are regenerable by script; the three geometry blobs are not — no script in the repo produces the embedded `JSON.parse` lines from `data/*.geojson` (verified: no reference to the embedded variable names anywhere in `scripts/`). The provenance comments are excellent, but provenance ≠ reproducibility: today, fixing P1 by hand would *create* drift between `data/school-board-districts.geojson` (which stays full-precision, correctly, as the source of truth) and the embedded copy. Commit `scripts/build_embedded_boundaries.py` (simplify → round → escape → splice, same `replace`-pattern as the roster builders) and note in each blob's comment which command regenerates it.

**R7 — package.json dependency hygiene.**
`@capacitor/geolocation` is declared (`package.json:21`) but nothing uses it: the page uses `navigator.geolocation` (index.html:882-901), and neither generated native manifest includes the plugin (`android/app/capacitor.build.gradle` has an empty dependencies block; `ios/App/CapApp-SPM/Package.swift` lists only Capacitor/Cordova). The next `npx cap sync` would silently wire it into both binaries — dead code plus a location-permission-bearing plugin you don't use. Also `@capacitor/cli` belongs in `devDependencies`. Both platforms already declare the right permissions for the web-API path (`AndroidManifest.xml:41-42`, `Info.plist` NSLocationWhenInUseUsageDescription), so removal is safe. Exact diff in §5 Quick Win 4. *(Alternative: if Android-WebView geolocation prompts prove unreliable in the installed app, the fix is to actually wire the plugin — the current half-state is the only wrong option.)*

**R8 — Repo/deploy hygiene (low urgency, worth a decision).**
`data/source/raw/` carries 2.7 MB of `.zip`/`.kmz`/`.xlsx` originals, and `data/*.geojson` another 2.5 MB, in every clone — and GitHub Pages deploys the whole branch, so all of it is publicly served though the app never fetches it at runtime. Options: keep (provenance is a stated value — legitimate), or move raw archives to a GitHub Release asset and keep only the converted GeoJSON. Either way, record the decision. The Python scrapers and workflows themselves are in good shape (Session reuse, backoff, rate-limit delays, PR-gated writes); the only nits are missing pip caching (`actions/setup-python` supports `cache: pip`) and unpinned `python-version: "3.x"`.

**Architecture verdict:** the layer-registry contract (`{id, group, label, overlay, query, render}`) is the right shape and needs no rework. The refactors above are consolidations within it, not a new architecture. Resist the temptation to introduce a build step or framework — the constraint is the feature.

---

## 4. The Actionable Playbook (Prioritized Matrix)

| # | Task | Impact | Effort | Category |
|---|------|--------|--------|----------|
| 1 | Simplify school-board geometry to match sibling layers (−918 KB raw / −75% page weight; validated 99.98%) — §P1 | **High** | **Low** | Data/Assets |
| 2 | Add boot smoke-test CI for the weekly roster-rewrite PRs — §R5 | **High** | Medium | DevEx |
| 3 | Embed IL congress roster at build time; drop multi-MB runtime fetch — §P3 | **High** | Medium | Network |
| 4 | Commit `build_embedded_boundaries.py`; make geometry blobs regenerable — §R6 | **High** (risk) | Low | Pipeline |
| 5 | Server-side generalization + `outFields` trim for TIGERweb/ArcGIS/Cook County — §P4 | Medium-High | Low | Network |
| 6 | Preconnect tile CDN + cdnjs — §P8 | Medium | **Low** | Frontend |
| 7 | Lazy-parse embedded blobs on first toggle — §P2 | Medium | Low | Frontend |
| 8 | Move generated data to fenced JSON script tags; simplify builder scripts — §R4 | Medium | Medium | Architecture |
| 9 | Single PIP per click: pass query's matched feature to highlight; bbox pre-check — §P5 | Medium | Low | Frontend |
| 10 | Remove `@capacitor/geolocation`, move CLI to devDependencies — §R7 | Medium (mobile) | **Low** | Mobile |
| 11 | Delete duplicate `makeCached` factory — §R1 | Low (quality) | **Low** | Architecture |
| 12 | Extract shared Socrata route-walker — §R2 | Low (quality) | Low | Architecture |
| 13 | Memoize `geocodePoiAddress` per address — §P6 | Low | **Low** | Network |
| 14 | Trim 2 unused font weights — §P9 | Low | **Low** | Frontend |
| 15 | sw.js: dedupe shell entry, cache-name bump discipline, opaque-response comment — §P7 | Low | Low | Frontend |
| 16 | pip cache + version pin in both workflows — §R8 | Low | **Low** | DevEx |
| 17 | Highlight restyle: touch 2 paths, not every path — §P5b | Low | Medium | Frontend |
| 18 | Decide raw-archive hosting (Release asset vs in-repo) — §R8 | Low | Low | DevEx |

Sequencing note: items 1+4+7 are one coherent PR (they all edit the same three lines); items 11+12+13 are a second quick cleanup PR; item 2 should land *before* item 3 so the new congress-roster Action is born with a safety net.

---

## 5. Quick Wins (exact before/after)

### Quick Win 1 — Simplify the school-board blob: −918 KB raw, −322 KB gzipped, one line

`index.html:2553` currently (line is 975,797 bytes; head shown):

```js
  var SCHOOL_BOARD_DISTRICTS_GEOJSON = JSON.parse('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"OBJECTID":1,"DISTRICT":10,...  // 24,904 coord pairs at 15 decimals
```

After (57,736 bytes — same variable, same schema, simplified geometry):

```js
  var SCHOOL_BOARD_DISTRICTS_GEOJSON = JSON.parse('{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"OBJECTID":1,"DISTRICT":10,...  // 2,394 coord pairs at 6 decimals
```

Regenerate with (add as `scripts/build_embedded_boundaries.py`; validated in this review — Douglas-Peucker ε=0.00005° ≈ 5.5 m, 6-decimal rounding, ring-closure preserved, tiny rings kept intact):

```
python3 scripts/build_embedded_boundaries.py data/school-board-districts.geojson index.html SCHOOL_BOARD_DISTRICTS_GEOJSON
```

Measured result: `index.html` 1,301,984 → 383,923 bytes (gzip 427,836 → 105,974). Classification agreement with the app's own `pointInGeometry`: 4,999/5,000 random in-district points; the disagreement is a point ~5 m from a district 4/7 boundary — the same accuracy class as the documented treatment already applied to the IL Supreme Court and CCBR blobs (`index.html:2605-2619`), and below GPS accuracy. Update the provenance comment at 2541-2552 to record the tolerance.

### Quick Win 2 — Preconnect the tile CDN (first map paint)

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
<link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>
```

The tile layer (`index.html:773`) fetches from `{a-d}.basemaps.cartocdn.com` the moment the script runs; today those connections start only after HTML download + parse + Leaflet execution. Preconnecting the first two subdomains (browsers cap speculative sockets; a/b cover the initial viewport's tiles) removes a DNS+TLS round trip from first map paint on every cold load.

### Quick Win 3 — Delete the duplicate loader factory

`index.html:2078-2089` before:

```js
  /* ---------- generic cached-promise wrapper (Socrata-geojson-specific
   * makeCachedLoader above predates this; this variant memoizes any loader
   * function, used here for roster JSON, TIGERweb, and the local file) ---------- */
  function makeCached(fn) {
    var pending = null;
    return function () {
      if (!pending) {
        pending = fn().catch(function (err) { pending = null; throw err; });
      }
      return pending;
    };
  }
```

After — delete the block entirely; it is byte-for-byte the same logic as `makeCachedLoaderFromFn` (`index.html:1581-1592`). Then a rename-only sweep of the 8 `makeCached(` call sites (2142, 2143, 2194, 2195, plus the ilga/school-board/cook-county loaders) to `makeCachedLoaderFromFn(`, or — better name — rename the survivor to `makeCached` and delete the long alias plus its one-line wrapper `makeCachedLoader` becomes `makeCached(function () { return loadSocrataGeoJSON(id); })`.

### Quick Win 4 — Drop the unwired geolocation plugin before it ships

`package.json:17-23` before:

```json
  "dependencies": {
    "@capacitor/android": "^8.4.1",
    "@capacitor/cli": "^8.4.1",
    "@capacitor/core": "^8.4.1",
    "@capacitor/geolocation": "^8.2.0",
    "@capacitor/ios": "^8.4.1"
  }
```

After:

```json
  "dependencies": {
    "@capacitor/android": "^8.4.1",
    "@capacitor/core": "^8.4.1",
    "@capacitor/ios": "^8.4.1"
  },
  "devDependencies": {
    "@capacitor/cli": "^8.4.1"
  }
```

The page uses `navigator.geolocation` (`index.html:901`) — the plugin is referenced nowhere, isn't in either generated native project yet, and the next `npx cap sync` would embed it (native code + a location-permission plugin surface) into both binaries for nothing. Both platforms already carry the correct declarations for the web API path (`AndroidManifest.xml:41-42`; `Info.plist` `NSLocationWhenInUseUsageDescription`).
