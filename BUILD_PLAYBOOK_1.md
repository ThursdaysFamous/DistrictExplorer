# Chicago District Explorer — Build Playbook

The reference-of-truth for building this app in small, cheap, focused threads.
**Add this file to the Project** so every thread has it via retrieval. Never paste the whole app into a thread — paste only this playbook's contract + the one module being worked on.

---

## 1. Architecture: stable core + 4 pluggable modules

**The core is built once and rarely touched.** It owns everything shared:

- HTML shell, Chicago-flag palette, Big Shoulders Display, custom six-point star marker
- Leaflet map init; click-to-select + geocoder (Nominatim, debounced, Chicago bbox `[-87.94, 41.64, -87.52, 42.02]`, swappable, attributed)
- Global state: `selectedPoint {lat, lng}`, monotonic `sequence` counter (discards stale async results)
- Shared utilities: `sanitize(str)`, `pointInPolygon(pt, geom)` (multipolygon + holes), `fetchWithRetry(url, opts)`, `probeGeometryColumn(datasetId)` (Socrata field names vary)
- Layer registry + result-card framework: loading / error / empty states, `aria-live` regions, per-layer failure isolation
- Selected-boundary highlight: for any polygon layer, whichever feature the point actually falls in gets a distinct on-map style (gold outline, brought to front), independent per active layer. Generic — not part of the module contract; the core re-runs `findFeatureContaining` against the overlay's own cached geojson and matches it to the Leaflet sub-layer. Point datasets (fire stations) are unaffected since containment doesn't apply to them.
- Attribution + "data last verified" + legal disclaimer footer

**Each layer module is self-contained** and exposes exactly this interface:

```js
{
  id:    "ward",                 // unique
  group: "political",            // political | safety | schools | geography
  label: "City Ward",
  overlay: {                     // lazy-loaded map overlay
    load: () => Promise<GeoJSON>,// fetched only when toggled on
    style: {...},                // visually distinct; not color-only (polygon/line datasets)
    pointToLayer: (feature, latlng) => L.Layer  // optional; point datasets (e.g. fire stations) use this instead of style
  },
  query: (point, seq) => Promise<Result | null>,  // point-in-district + roster join; tag result with seq
  render: (result) => HTMLElement,                  // one result card; all external strings via sanitize()
  pointOfInterest: (result) => {label, address} | null  // optional; core geocodes `address` and drops a pin colored to match overlay.style.color
}
```

Rules every module must honor (from the prompt's quality requirements):
1. `query` results tagged with `seq`; the core discards any result whose `seq` is stale.
2. Toggling a layer off clears its result card.
3. Any fetch can fail — surface it *in that card*, never break the app.
4. All external API values passed through `sanitize()` before render.
5. No-result / no-match / slow-load each get an explicit honest state.

---

## 2. Data registry (verified July 2026 — reverify before relying)

| Layer | Source | ID / endpoint |
|---|---|---|
| Wards (2023–) | Socrata | `p293-wvbd` |
| Aldermen roster | Socrata | `htai-wnw4` (join on ward #) |
| Police districts | Socrata | `fthy-xz3r` |
| Fire stations (points) | Socrata | `28km-gtjn` (nearest-N proximity, not point-in-polygon) |
| CPS elementary zones | Socrata | `5ihw-cbdn` |
| CPS high school zones | Socrata | `4kfz-zr3a` |
| CPS middle zones | Socrata | none verified current; legacy `9kct-c3uq`, ~22 schools only — degrade gracefully |
| Community areas | Socrata | `igwz-8jzy` |
| ZIP codes | Socrata | `gdcf-axmw` |
| Congress / IL upper / IL lower boundaries | Census TIGERweb Legislative MapServer | layers 0 / 1 / 2 — request `outSR=4326` |
| Congress rosters | congress-legislators | filter `state=IL`, join on district # |
| IL GA rosters | Open States people | **no browser CORS** — fallback to ILGA directory links |
| School board districts | KML on ilsenateredistricting.com | not on data portal; needs manual convert→host (see §4) |

Socrata caps at 1,000 rows by default. Some serve `/resource/{id}.geojson`; legacy ones use `/api/geospatial/{id}?method=export`.
Commanders + principals: **not in open data** — link to CPD district pages and `cps.edu/schools/schoolprofiles/{school_id}`, never guess.

---

## 3. Thread sequence

Build simplest first to prove the contract, then escalate. **Use Claude Sonnet for module work; reserve Opus for genuinely hard logic (likely only the Political group).**

- **Thread 0 — Core shell.** Deliver the stable core + one trivial stub module so the plumbing is proven end-to-end.
- **Thread 1 — Geography.** Community area + ZIP. Simplest; validates the module pattern.
- **Thread 2 — Public Safety.** Police district (polygon) + fire stations (nearest-N proximity).
- **Thread 3 — Schools.** Elementary / middle / high zones + profile links; handle missing middle zones.
- **Thread 4 — Political.** Ward+alderman, congress+reps/senators, IL Senate/House, school board. Heaviest — split into two threads if needed. Do the school-board KML conversion (§4) before this thread.
- **Thread 5 — Assembly + audit.** Concatenate into single file; a11y pass, on-demand-loading check, disclaimer/attribution, "data last verified" date.

---

## 4. Manual step required before the Political thread

The school-board KML can't be fetched by a browser app (Drive interstitials + CORS). Operator must:
1. Download the KML from the ilsenateredistricting.com source.
2. Convert to GeoJSON: `mapshaper in.kml -o out.geojson` (or `ogr2ogr -f GeoJSON out.geojson in.kml`).
3. Host it as a static asset alongside the app.
4. Confirm which KML property identifies the district number — if unclear, ask rather than guess.

---

## 5. Per-thread handoff protocol (keeps threads cheap)

**Start of a module thread, paste only:** this playbook's §1 contract + §2 rows for that layer. That's it.
**End of a module thread, append 3 lines here** under a "Status" heading:

- `[module] DONE — exposes contract, tested against <point>`
- `[module] STUB — <what's faked>`
- `[module] SURPRISE — <any dataset quirk found>`

Then update the Project copy of this file. Next thread starts clean with full context but tiny token cost.

---

## Status

_(append handoff notes here as modules complete)_

- `core-shell` DONE — delivers HTML shell, Chicago-flag palette, Big Shoulders Display + Inter + IBM Plex Mono, six-point-star marker/icons, flag-stripe header motif; Leaflet map with click-to-select and a keyboard/screen-reader "select map center" fallback button; Nominatim geocoder (debounced 550ms, Chicago bbox-bounded, OSM-attributed, in-flight requests aborted on new input); global `state {selectedPoint, sequence, layersOn}`; shared utils `sanitize`, `pointInGeometry` (Polygon/MultiPolygon, holes via even-odd across all rings), `fetchWithRetry` (timeout + backoff), `probeGeometryColumn` (Socrata field sniff); layer registry + result-card framework (loading/error/empty/off states, aria-live, per-layer isolation, retry button); footer with disclaimer, "data last verified" date, and source attribution. Tested against a manual click near the Loop (41.8825, -87.6285) and via the keyboard-select fallback — sequence counter correctly discards a stale query when a second point is selected before the first (artificially delayed) query resolves.
- `demo-radius` (geography, STUB) DONE — exercises the full module contract end-to-end: lazy overlay.load(), query() against a synthetic square via the shared `pointInGeometry`, seq-tagged result, render() via shared `renderFieldList`. Intended to be deleted once Thread 1 lands real Geography modules.
- SURPRISE — none of the verified endpoints were called yet (out of scope for Thread 0); first real-data risk to watch in Thread 1 is Socrata's default query behavior when `probeGeometryColumn` guesses wrong on an unfamiliar dataset — worth a manual spot-check per dataset rather than trusting the sniff blindly.
- `community-area` (geography) DONE — full-dataset fetch + local point-in-polygon, case-insensitive field lookup, dashed overlay style
- `zip-code` (geography) DONE — same pattern, dotted overlay style
- demo-radius STUB removed per plan
- SURPRISE — couldn't get a live JSON field-name confirmation (web_fetch sandbox only allows previously-searched/fetched URLs); modules degrade gracefully via findPropCI's alias list if the guessed field name is wrong, but a manual spot-check against real data is still worth doing before Thread 4 depends on the same pattern
- Moved to Claude Code: `index_1.html` (Thread 0 + Thread 1) is now the single canonical `index.html`; the old Thread-0-only `index.html` snapshot was removed. Each future thread edits `index.html` in place rather than saving a new numbered file.
- Fixed after moving to Claude Code: the Leaflet CSS/JS `integrity` hashes pasted into the core shell didn't match the real CDN files, so browsers silently blocked both and crashed the whole init script (blank map, dead Layers dropdown). Corrected to the hashes the browser itself reported. Also swapped the OSM tile layer for CARTO's basemap tiles — OSM's tile CDN 403s requests with no HTTP referrer, which `file://` pages (the common way to open this app) never send; CARTO doesn't enforce that check.
- `police-district` (safety) DONE — same polygon/point-in-polygon pattern as Thread 1's Geography modules; red dash-pattern overlay distinct from Geography's green/blue.
- `fire-station` (safety) DONE — point dataset, so no point-in-polygon test; instead does nearest-3 straight-line (haversine) proximity, sorted ascending. Required one small, backward-compatible core addition: `overlay.pointToLayer`, since the core's overlay renderer only knew `style` (meaningless for Point geometries) — existing polygon modules are unaffected since they never set it.
- SURPRISE — same sandboxed web_fetch limitation as Thread 1: couldn't get a live field-name confirmation for `fthy-xz3r` (police districts) or `28km-gtjn` (fire stations). Both modules degrade gracefully via `findPropCI`'s alias lists if a guessed field name is wrong, but a manual spot-check against real data is worth doing, especially before Thread 4 (Political) leans on the same pattern for higher-stakes datasets.
- BUG FOUND + FIXED (operator spot-check, post-thread) — `gdcf-axmw` (ZIP) and `fthy-xz3r` (police districts) are the correct current dataset IDs, but both always returned "No result" because their primary `.geojson?$limit=...` route returns HTTP 200 with every feature's geometry stripped to `null` — a "succeeded but useless" response the original `.catch()`-only fallback never detected. Fixed in `loadSocrataGeoJSON` with a `hasUsableGeometry()` check that now falls back to the legacy `method=export` route whenever the primary response has no real geometry, not just on outright fetch failure. Worth checking whether any other "legacy" dataset in the registry (§2) has this same silent-200 behavior.
- `fire-station` firehouse designation added — confirmed via live sample of `28km-gtjn`: the field is `engine` (e.g. `"E5"`).
- Police District fixed for real — the `hasUsableGeometry` fallback alone wasn't enough because the legacy `method=export` route didn't help either; `fthy-xz3r`'s `/resource/{id}.geojson` route reliably 200s with null geometry. The portal page's own dataset id and the id that actually serves geometry aren't the same: operator confirmed `https://data.cityofchicago.org/api/v3/views/24zt-jpfn/query.geojson` returns real `MultiPolygon` geometry with `dist_num`/`dist_label` properties (matching what was already guessed). `loadSocrataGeoJSON` now tries three routes in order (`/resource/{id}.geojson`, `/api/v3/views/{id}/query.geojson`, legacy `method=export`) and Police District's loader now points at `24zt-jpfn`. ZIP Code fixed the same way: operator confirmed `https://data.cityofchicago.org/api/v3/views/unjd-c2ca/query.geojson` returns real `MultiPolygon` geometry with a `zip` property (matching what was already guessed). ZIP Code's loader now points at `unjd-c2ca` (portal page is still `gdcf-axmw`, same null-geometry issue as police districts).
- `cps-elementary` / `cps-high` (schools) DONE — same point-in-polygon factory (`registerSchoolZone`) as the other polygon modules, against `5ihw-cbdn` / `4kfz-zr3a`. School profile link only renders when the dataset actually supplies a school id (never guessed into the cps.edu URL); degrades to name-only otherwise.
- `cps-middle` (schools) DONE, per plan labeled "legacy, partial coverage" — no current verified dataset exists (per §2), so this registers the legacy `9kct-c3uq` (~22 schools) and honestly shows "no result" for most points rather than pretending to have full coverage.
- SURPRISE (expected, given Thread 2) — none of `5ihw-cbdn` / `4kfz-zr3a` / `9kct-c3uq` were live-checked (same sandboxed fetch limitation). Given Thread 2 found the portal-page dataset id and the id that actually serves geometry can differ, these three should get the same live spot-check (open `/resource/{id}.geojson`, and if geometry is null try `/api/v3/views/{id}/query.geojson`) before relying on them — `loadSocrataGeoJSON`'s 3-route fallback should catch it automatically, but worth confirming the id even resolves at all, plus checking the real school-name/school-id field names.
- `cps-elementary` corrected — operator found `5ihw-cbdn` was the wrong dataset entirely. Live sample of `x72b-38qv` confirmed it's the real per-school attendance boundary: `school_id`, `short_name`, `grade_cat: "ES"`, `boundarygr` (grade list). Elementary now points at `x72b-38qv`; `registerSchoolZone` also surfaces `boundarygr` as a "Grades" field when present. High School Zone (`4kfz-zr3a`) and Middle School Zone (`9kct-c3uq`) still unverified — same live spot-check still needed.
- `cps-network` (schools) NEW, DONE — operator's second dataset (`pnta-kuqa`) turned out not to be an elementary attendance boundary at all; it's a CPS "Network" administrative region (bigger than a single school) with a real named administrator, phone, and office address (`network`/`admin`/`phone`/`address` fields, confirmed live). Added as its own layer rather than folded into the school-zone module, since it's genuinely-available admin contact info the playbook flagged as usually missing from open data.
- `cps-high` corrected — `4kfz-zr3a` was wrong, same mistake pattern as elementary. Live sample of `xg7c-d8rm` confirmed the real attendance boundary (`school_id`, `school_nam` — note the different field name from elementary's `short_name`, `grade_cat: "HS"`, `boundarygr`). `registerSchoolZone`'s name-field alias list now includes `school_nam`.
- `cps-hs-network` (schools) NEW, DONE — same admin-boundary pattern as `cps-network` but for High School networks, confirmed live via `aupu-jt2g` (same `network`/`admin`/`phone`/`address` schema, separate dataset from the K-8 one). Both network layers now share one `registerCpsNetwork` factory.
- `cps-middle` corrected — the playbook's `9kct-c3uq` (~22 schools, marked legacy) is superseded. Operator found `fyff-53xy`, live-confirmed to be a current, full attendance boundary with the same schema as elementary/high (`school_id`, `school_nam`, `grade_cat: "MS"`, `boundarygr`). Label dropped the "legacy, partial coverage" caveat since this is no longer the sparse legacy dataset. Confirmed via `query.geojson` too (operator's first sample used `query.json` by mistake) — proper `Feature`/`MultiPolygon` GeoJSON, same schema.
- All three school-zone datasets (elementary, middle, high) and both CPS Network datasets are now live-confirmed. Thread 3 is in good shape.
- Selected-boundary highlight ADDED (core feature, not a module) — whichever polygon feature actually contains the selected point now gets a distinct gold outline + brought-to-front, per active layer, reverted correctly on toggle-off/re-toggle/new-point/error. Implemented generically in the core (`updateLayerHighlight`/`clearLayerHighlight`) rather than per-module, so no existing module needed to change.
- §4 manual step DONE — operator supplied `ESRB Numbered District Map 11.3.23.kml` (the Chicago elected school board's 20 numbered districts). Converted to GeoJSON (`data/school-board-districts.geojson`, hosted alongside `index.html`) with a one-off Python script rather than mapshaper/ogr2ogr (neither available in this sandbox); preserved holes (District 2 has 2, District 12 has 1) as separate rings → `MultiPolygon` where needed. District number comes from each Placemark's `<name>` (`"District N"`), not from a KML `SimpleData`/`ExtendedData` field — there wasn't one. Verified: all 20 districts present, every ring closed, 500 random in-bbox points produced zero multi-district matches, and a known Loop point (41.8825, -87.6285) resolved to exactly one district.
- Operator also supplied two unrelated redistricting shapefiles (`CCBR PA 102 0012.zip`, `Supreme-Court-PA102-0011.zip`). Inspected their attribute tables: 3 and 5 records respectively, matching Cook County Board of Review (3 districts) and the IL Supreme Court (5 districts) — neither is in this playbook's Political-thread scope (§3: ward/alderman, congress, IL Senate/House, school board), so left unused and uncommitted to the module registry. Flagging in case a future thread wants them.
- `ward` (political) DONE — same polygon join pattern, but joins two independently-fetched Socrata datasets locally (boundary `p293-wvbd` + alderman roster `htai-wnw4` on ward number) rather than one dataset per layer, since Ward is the only political layer with a full-roster join.
- `congress` (political) DONE — first module to source overlay geometry from Census TIGERweb (Esri REST, not Socrata): `MapServer/0`, filtered to `STATE='17'` and requested as `f=geojson` directly (no separate Esri→GeoJSON conversion step needed). Roster comes from `congress-legislators`' `legislators-current.json`, joined on each legislator's latest `rep`-type term's `district`.
- `il-senate` / `il-house` (political) DONE — same TIGERweb pattern as Congress (layers 1/2, `SLDU`/`SLDL`), but per the playbook Open States has no browser CORS, so instead of a roster join these surface a link to ILGA's own senate/house directory page. Deliberately did NOT construct a per-district ILGA deep link (e.g. `district.asp?GA=...&Senate=N`) since the current General Assembly session number isn't reliably derivable client-side and guessing it risks linking to a stale or wrong session — the general directory page is the honest fallback the playbook calls for.
- `school-board` (political) DONE — point-in-polygon against the converted GeoJSON above. No roster source exists for this newly-elected body (not in open data, not covered by congress-legislators or Open States), so this links to CPS's official Board of Education page rather than guessing at contact info.
- BUG FOUND + FIXED (operator console log, real browser) — `school-board`'s overlay/query both failed with a same-origin-policy error when the app was opened via `file://`: `fetch("data/school-board-districts.geojson")` is a cross-origin request under `file://` and browsers block it outright (no server to send CORS headers from, unlike every other layer's `https://` API calls). Fixed by embedding the converted GeoJSON inline as a `JSON.parse('...')`-wrapped string literal (`SCHOOL_BOARD_DISTRICTS_GEOJSON`) directly in `index.html` instead of fetching it as a separate file; `data/school-board-districts.geojson` is kept in the repo as the build artifact/reference but is no longer read at runtime. Worth remembering for any future locally-hosted (non-API) dataset: it has to ship inline, not as a fetched sibling file, if `file://` is a supported way to open this app.
- SURPRISE — same sandboxed-fetch limitation as every prior thread, now compounded: this sandbox's outbound network policy blocks not just live Socrata/TIGERweb JSON samples but the CDNs the app itself depends on (Leaflet, Google Fonts) and even a raw `curl`, so this thread's live browser smoke test only got as far as confirming the script parses (`node --check`) and that the map/layer JS doesn't throw before Leaflet loads — Leaflet itself never loaded in this sandbox. None of the following field-name guesses have been spot-checked against real data: `p293-wvbd`/`htai-wnw4`'s ward-number field and the alderman roster's name/email/phone/address fields, and TIGERweb's per-Congress/GA field name (guessed as `cd119fp`/`sldust`/`sldlst` with a regex fallback against any `*name*` field, e.g. `NAMELSAD`, in case the direct field guess is wrong). All four should get the same live spot-check prior threads did before relying on them. The KML-derived school board data, by contrast, *was* fully verified locally (see above) since it required no live fetch.
- Thread 4 is otherwise feature-complete per §3: Ward+alderman, Congress+roster, IL Senate/House (boundary + directory link), and School Board are all registered under the Political group.
- Highlight UPGRADED — every other boundary in that layer now fades (`fadedStyle`: lower stroke/fill opacity, thinner weight) while the match gets a CSS drop-shadow filter (`.chi-region-highlight`) applied by mutating the SVG path's class list directly, since Leaflet's `className` style option only applies at path creation, not on later `setStyle()` calls — that distinction cost one iteration to discover.
- School address pins ADDED — new optional contract field `mod.pointOfInterest(result) => {label, address} | null`. When present, the core geocodes the address via Nominatim (cached per address string, same Chicago-bounded pattern as the search box) and drops a small pin colored to match the layer's `overlay.style.color`, with a tooltip showing the school name. Wired into `cps-elementary`/`cps-middle`/`cps-high` via their confirmed `school_add` field; the address also now shows as plain text in the sidebar card regardless of whether geocoding succeeds. CPS Network layers don't use this (their `address` field is an admin office, not a per-click point of interest) — left as text-only, matching the original ask's scope.
- `school-board` boundaries REPLACED with the official ERSB shapefile — operator supplied `ERSB_20_Sub_District_Map_FA1_SB_15.zip` (shp/shx/dbf/prj, EPSG:4326, no reprojection needed), the authoritative source superseding the earlier ad hoc KML→GeoJSON conversion. Parsed with `pyshp` (installed via pip; no GDAL/fiona in this environment) rather than a hand-rolled binary parser. District 1 (3 rings) and District 18 (2 rings) have holes; outer vs. hole rings were disambiguated by signed ring area (shapefile convention: CW outer, CCW hole) and each hole was verified to fall inside its outer ring via point-in-ring before assembly. Total polygon area and bounding box are effectively identical to the old file (0.0658419 vs. 0.0658417 sq-deg — same underlying map), but the DISTRICT numbering differs from the old KML's ad hoc placemark numbers (only ~12% of a 1300-point random sample landed in the same-numbered district under both files) — this shapefile's `DISTRICT` field (1–20) is the real SB15 sub-district number and is what's now used. `LONGNAME` ("District 1a", "1b", "2a", ...) and `SHORTNAME` ("D1"–"D20") were also carried into each feature's properties (`longName`/`shortName`) since candidate questionnaires reference districts by that "1A"/"2B"-style scheme — useful once a member roster is joined in. Updated both `data/school-board-districts.geojson` and the inline `SCHOOL_BOARD_DISTRICTS_GEOJSON` in `index.html`; verified the inline JS blob still parses (`node --check`) and evaluates to a valid 20-feature FeatureCollection whose point-in-polygon behavior matches the standalone file. The raw shapefile is kept at repo root (`ERSB_20_Sub_District_Map_FA1_SB_15.zip`) alongside the other original source maps.
- SURPRISE — a member roster (elected board members per sub-district) was first supplied as a "publish to web" Google Sheets link, but `docs.google.com` is blocked by this environment's egress policy (confirmed via the agent-proxy status endpoint: explicit `connect_rejected`/403, not an auth issue) and the sheet wasn't reachable through the connected Google Drive account either (its `pubhtml` publish-token URL isn't a real Drive file ID, and the sheet didn't turn up in that account's Drive search). Operator instead exported and uploaded the roster as an `.xlsx` (`cpsschoolsbyersbdistrictsy25.xlsx`, a per-school "CPS schools by ERSB district" list with a `Board Member` column) — read with `openpyxl`, de-duplicated down to one member per district (993 school rows → 20 districts), each matched to a member with no conflicts. District 9a ("VACANT" in the source) is surfaced as "Vacant" rather than guessed at.
- `school-board` member roster ADDED — `SCHOOL_BOARD_MEMBERS`, an inline object keyed by the same flat district number (1–20) as the geometry, built by joining the uploaded roster's `ERSB District` column (e.g. "District 2b") against each geojson feature's `longName` property added in the shapefile-replacement step above. Wired into the module's `query()`/`render()`: the result card now shows a "Board member" field alongside the existing district number and CPS board-page link. Verified end-to-end in Node (outside a browser, since this sandbox can't reach the Leaflet CDN either): the inline geometry blob and the inline roster both parse, every one of the 20 districts resolves to a roster entry, and the known Loop point (41.8825, -87.6285) resolves to District 12 / "District 6b" / Jessica Biggs.
