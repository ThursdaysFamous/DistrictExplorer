# Metro Expansion Playbook — porting District Explorer to a new city

The reference-of-truth for recreating this app for another large metro. **Chicago is the reference implementation; each metro is its own fork** — a separate repo and site cloned from this one, evolving independently. Nothing in this document changes the Chicago app.

Part I is the generic recipe (what any city swaps, in what order). Part II is the NYC worked example, researched and source-verified July 10, 2026 — every endpoint labeled **VERIFIED** below was actually fetched that day with real records observed; **UNVERIFIED** means the source was found but not confirmed. Reverify before relying: dataset IDs, field names, and WAF postures drift.

Same working style as `BUILD_PLAYBOOK_1.md`: build in small, cheap, focused threads; paste only this playbook's contract + the one module being worked on into a thread, never the whole app.

---

# PART I — The generic metro-porting recipe

## 1. What the fork keeps vs. rewrites

`index.html` (4,608 lines as of July 2026) is roughly **60–65% metro-agnostic engine**: the map boot, layer registry + result-card framework, `state`/`sequence` machinery, URL-hash permalinks, hover explorer, highlight/reorder machinery, and the shared utilities (`sanitize`, `pointInGeometry`, `fetchJSONWithRetry`, `haversineMiles`, `findPropCI`, the Socrata/ArcGIS loaders and caching wrappers). All of that ports untouched. What a new metro rewrites is the ~1,500 lines of layer modules (≈ lines 2712–4263) plus a fixed, enumerable set of hardcoded core values.

**Core constants to swap (line anchors verified against the July 2026 tree — re-locate by name if drifted):**

| What | Where | Chicago value |
|---|---|---|
| City bbox + map center | `CHI_BBOX` / `CHI_CENTER`, `index.html:1020–1021` | `[-87.94, 41.64, -87.52, 42.02]`, `[41.8781, -87.6298]` |
| Permalink sanity gate | `index.html:1416` (independent of `CHI_BBOX` — easy to miss) | `lat 41–42.6, lng -88.6–-87` |
| Geolocation out-of-area string | `index.html:1456–1457` | "…outside the Chicago area this app covers." |
| Type-ahead geocoder bias/bbox | Photon call, `index.html:1638–1639` | `lat=41.88&lon=-87.63` + `CHI_BBOX` |
| POI geocoder viewbox | Nominatim call, `index.html:2076–2077` | `CHI_BBOX`, `bounded=1` |
| Group taxonomy | `GROUPS`, `index.html:1723–1728` | political / safety / schools / geography |
| Z-order ranking | `LAYER_AREA_RANK`, `index.html:1734–1766` | all 22 Chicago layer ids (see §3 rule) |
| Socrata host | `socrataRouteUrls`, `index.html:2553–2555` | `data.cityofchicago.org` |
| TIGERweb state filter | `loadTigerLayer`, `index.html:3521` | `STATE='17'` |
| "Data last verified" date | `index.html:4586` | hardcoded string |
| Debug namespace | `window.ChiExplorer`, `index.html:4590` — **twinned in `scripts/smoke_test.mjs:64`**; rename both or neither | — |
| Preconnect/dns-prefetch hosts | `index.html:19–24` | Chicago data hosts |
| Branding | `<title>`/meta (6–11), palette `:root` (31–55), masthead (905–906), footer sources (976–986), feedback email (1498) | Chicago flag palette, star motif |

**Sibling files to swap:** `CNAME` (custom domain — preserved purely by shipping the file in the Pages artifact), `manifest.webmanifest` (name + theme colors), `icons/` (192/512 PNGs), `README.md` (entirely city-specific), and `sw.js`'s two hardcoded lists (§4). `.github/workflows/` carry over structurally — only constants and dataset names change (§9 shows the NYC mapping).

**Test/gate constants to re-derive (never copy):** `scripts/smoke_test.mjs` `POINT` / `OFFLINE` / `EXPECT_LAYERS` (lines 36–38), `EXPECT_DISTRICT` (87), the second re-highlight point (124/135); `scripts/validate_index.py` `MIN_REGISTER_LAYER`, `GEOMETRY_FILES`, `ROSTER_FILES`; every scraper/builder count guard.

## 2. The layer contract (unchanged, verbatim)

Every metro's modules implement exactly the `BUILD_PLAYBOOK_1.md` §1 interface:

```js
{
  id:    "ward",                 // unique
  group: "political",            // political | safety | schools | geography
  label: "City Ward",
  overlay: {                     // lazy-loaded map overlay
    load: () => Promise<GeoJSON>,// fetched only when toggled on
    style: {...},                // polygon layers; visually distinct, not color-only
    pointToLayer: (feature, latlng) => L.Layer  // point datasets instead of style
  },
  query: (point, seq) => Promise<Result | null>,  // point-in-district + roster join; tag result with seq
  render: (result) => HTMLElement,                  // one result card; all external strings via sanitize()
  pointOfInterest: (result) => {label, address} | null  // optional; core geocodes address, drops a pin
}
```

Optional fields the core also honors: `subOf` (nested sub-layer toggle — police-beat/ward-precinct pattern), `color` (theme color for point layers), `onToggle(on)`, `hoverName(feature)`, `hoverOfficial{load?, name()}`.

The five rules every module must honor are unchanged and non-negotiable: seq-tagged results, toggle-off clears the card, failures surface *inside that card* only, all external strings through `sanitize()`/`textContent`, and explicit honest states for no-result/no-match/slow-load. So are the honesty rules: **officeholder data is never guessed** — no verifiable roster source means the card links to the official body.

**Reuse the four factories before writing a bespoke module:**

- `registerPolygonLayer` (`index.html:2674`) — single boundary source, point-in-polygon, field list. Fits most layers.
- `registerSchoolZone` (`index.html:3275`) — attendance-zone shape with POI pin; the school-profile URL builder inside it is city-specific, generalize it.
- `registerCpsNetwork` (`index.html:3341`) — admin-region shape where the officeholder rides in the boundary dataset's own properties.
- `registerIlgaChamber` (`index.html:3815`) — TIGERweb boundary + same-origin roster-file join; the pattern for any state-legislature chamber.

Also reusable as-is: the `ward` module's two-live-datasets join (boundary + roster joined client-side on district number), the `ccpsa-district-council` module's shared-geometry pattern (one loader serving two layers), and the nearest-N haversine pattern (`police-station`/`fire-station`/`school-site`).

## 3. The porting checklist (in order)

1. **Fork** the Chicago repo. Don't start from scratch — the engine, gates, and CI shape are the value.
2. **Swap the §1 core constants** and branding; rename the debug namespace in both files or leave it.
3. **Decide the layer roster** for your city: walk Chicago's 22 layers, map each to the local equivalent, and be explicit where **no honest analog exists** — drop the layer rather than invent geometry or names for an appointed/citywide body. Add local layers Chicago lacks. Then write the full `LAYER_AREA_RANK`, largest→smallest. **Rule: every registered layer id appears in the rank, no exceptions** — an id missing from the list is invisible to both consumers of the rank: `reorderActiveLayers` (`index.html:1887`) never restacks it, and `hoverContainingLayers` (`index.html:4291`) omits it from hover civic profiles entirely. (Chicago itself shipped this bug — `ward-precinct` was missing from the rank until it was fixed alongside this playbook.) Sub-layers deliberately rank just *before* their parent so the parent outline frames the fills — see the police-beat comment in the Chicago rank.
4. **Build the data registry** (Part II §6 is the model): one row per layer, geometry source + roster source, each labeled VERIFIED only after a live fetch you performed. Record dataset IDs, exact query URLs, and observed field names.
5. **Pick the offline anchors** (§4) and the smoke-test ground-truth points.
6. **Map the pipeline**: for each roster, which scraper/builder pair template applies, which fetch engine, and the count guards (§9 is the model).
7. **Re-derive every gate constant** (§1's last paragraph) and both `sw.js` lists.
8. **Swap deploy**: CNAME, manifest, icons, README, footer attribution. The `deploy-pages.yml` rsync exclude list is generic — but confirm nothing city-new (e.g. a large source GeoJSON) slips into the artifact.

## 4. The offline-anchor rule

Chicago ships three layers whose boundaries have no reliable public API as same-origin static files (`data/app/*.json`, built by `scripts/build_embedded_boundaries.py`). These are load-bearing far beyond their cards — they are the app's **deterministic anchors**:

- `smoke_test.mjs` classifies the ground-truth point against them (`OFFLINE`/`EXPECT_DISTRICT`) — the only assertions that don't depend on a third-party API being up in CI.
- `validate_index.py` pins their exact feature counts (`GEOMETRY_FILES`).
- `sw.js` serves them **cache-first** (`GEOMETRY_URLS`; boundaries change ~once a decade) vs. **network-first** for rosters (`ROSTER_URLS`; never serve a stale officeholder).
- `build_embedded_boundaries.py`'s `LAYERS` dict is where they're produced: mapshaper (`npx -y mapshaper@0.6.102`, visvalingam keep-shapes) + the validation protocol below.

**Every metro must pick ≥3 such layers** — prefer boundaries that essentially never change and whose live APIs are absent or unreliable — plus a well-known ground-truth point and a second point that lands in different districts (the re-highlight fast-path check).

**New invariant for forks** (a gap Chicago itself shipped — `ccpsa-district-councils.json` and `congress-roster.json` were fetched by the app but absent from both SW lists until fixed alongside this playbook): **every file in `data/app/` appears in exactly one of `sw.js`'s `GEOMETRY_URLS` or `ROSTER_URLS`**, and the fork's `validate_index.py` checks it. Bump `CACHE_NAME` on every list change.

## 5. Dataset verification protocol (lessons already paid for)

1. **Live-sample field names before wiring a module.** Every Chicago thread that skipped this shipped a wrong guess. Seed `findPropCI` alias lists with all observed candidates.
2. **The portal-page dataset ID and the geometry-serving ID can differ.** Chicago's ZIP and police-district datasets both 200'd with every geometry `null` on the obvious ID. `loadSocrataGeoJSON` tries three routes (`/resource/{id}.geojson` → `/api/v3/views/{id}/query.geojson` → legacy `method=export`) for exactly this reason; keep that machinery.
3. **The Socrata "map-type" trap:** older map-type datasets return empty/`null` from `/resource/` **by design** — only `/api/geospatial/{id}?method=export&format=GeoJSON` or a sibling ArcGIS FeatureServer serves them. If a registry row is known map-type, don't burn two failing routes per load: give `loadSocrataGeoJSON` a per-dataset route-order override in the fork (the export route already exists as route 3).
4. **Simplification validation:** `build_embedded_boundaries.py` reimplements the app's own even-odd point-in-polygon and requires ≥99.5% agreement on 2,000 seeded random points AND zero points classified into >1 district (topology break = hard fail), feature count and properties unchanged. Use it unmodified for the new city's anchors.
5. **Watch record caps:** Socrata route 1 hardcodes `$limit=1000`; TIGERweb caps transfers (`exceededTransferLimit`) — filter server-side (state/county `where`) or paginate for large layers.

---

# PART II — NYC worked example (nycdistricts fork)

Everything below was researched and (where marked) live-verified **July 10, 2026**. NYC's open-data portal `data.cityofnewyork.us` is Socrata — same platform, same SoQL grammar as Chicago's, and the `intersects(the_geom, 'POINT(lng lat)')` server-side point-in-polygon pattern was **confirmed working** (a Times Square point correctly returned its NTA). The geometry column is `the_geom` on every dataset checked.

## 6. NYC data registry (verified July 10, 2026 — reverify before relying)

| Layer target | Source | ID / endpoint | Status |
|---|---|---|---|
| City Council districts (51) | Socrata | `872g-cjhh` `/resource/872g-cjhh.geojson` | geometry **VERIFIED** (real MultiPolygon); **field names UNVERIFIED** (expect `coundist` — sample before wiring) |
| Council member roster | Legistar (HTML) | `legistar.council.nyc.gov/People.aspx` | **VERIFIED** — server-rendered 51-row grid; district encoded in member URLs (`/district-N/`). `webapi.legistar.com` REJECTED: Incapsula 403 + key-gated |
| Election districts (~5,000; AD·1000+ED) | DCP ArcGIS | `services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/NYC_Election_Districts/FeatureServer/0` (`ElectDist`) | **VERIFIED** (sample `ElectDist=23001`). Socrata `h2n3-98hq` is map-type — `/resource/` geometry is null |
| Community districts (59) | Socrata | `5crt-au7u` `.geojson` (`boro_cd`, e.g. `"410"` = Queens CD 10) | **VERIFIED** |
| Community Board leadership | Socrata | `ruf7-3wgc` `.json` — `cb_chair`, `cb_district_manager`, office address/phone/email, meeting info | **VERIFIED** — the only machine-readable CB roster; full ~50-member lists are per-borough HTML only (link, don't scrape) |
| Borough boundaries (5; = county) | Socrata | `gthc-hcne` — `borocode`, `boroname` (clipped to shoreline) | **VERIFIED**. Crosswalk: Manhattan=New York Co. 36061, Bronx 36005, Brooklyn=Kings 36047, Queens 36081, Staten Island=Richmond 36085 |
| U.S. House geometry (NY: 26) | TIGERweb | `Legislative/MapServer/0`, `STATE='36'` → 26 features (`CD119`, `BASENAME`) | **VERIFIED** |
| NY Senate geometry (63) / Assembly (150) | TIGERweb | `Legislative/MapServer/1` / `/2`, `STATE='36'` → 63 / 150 | **VERIFIED** |
| U.S. House roster | congress-legislators | `legislators-current.json` (CC0), filter `state=NY`, `type=rep` | **VERIFIED** — same file the Chicago builder already consumes |
| NY Senate roster | nysenate.gov (HTML) | `/senators-committees` — 63 linked cards: name, party, district | **VERIFIED** scrapeable. Official Open Legislation API (`legislation.nysenate.gov/api/3/`) **confirmed key-gated** (401 without key) — optional upgrade |
| NY Assembly roster | nyassembly.gov (HTML) | `/mem/` — ~150 cards: name + district. **No party field on the page** — store `null`, never guess | **VERIFIED** scrapeable |
| NY Supreme Court judicial districts (NYC: 1, 2, 11, 12, 13 — elected justices, 14-yr terms) | derived | 1:1 with counties — TIGERweb `State_County/MapServer/13`, `STATE='36' AND COUNTY IN ('005','047','061','081','085')`, relabeled | counties **VERIFIED**; justices roster = per-JD pages on `nycourts.gov` (HTML, one page per district) — link-only at launch |
| Municipal Court districts (NYC Civil Court — elected judges) | Socrata | `7vpq-4bh4` — map-type: use `/api/geospatial/7vpq-4bh4?method=export&format=GeoJSON`; metadata fields `boro_code`, `boro_name`, `muni_court` | geometry **partially VERIFIED** (metadata + boundary confirmed; export route not exercised). No clean per-district judge roster → link to the Civil Court directory |
| NYPD precincts (78, incl. Central Park's 22nd) | Socrata | `y76i-bdw7` `.geojson` (`precinct`) | **VERIFIED** — 78 features |
| Precinct commanding officers | nyc.gov (HTML) | `nyc.gov/site/nypd/bureaus/patrol/precincts/{Nth}-precinct.page` — bold `Commanding Officer:` label + address + phone | **VERIFIED** on the 13th Precinct page. Ordinals are irregular — drive the loop from `y76i-bdw7`'s `precinct` values, never 1..N |
| NYPD sectors (303) | Socrata | `5rqd-h5ci` `.geojson` — `sector` ("75D"), `pct`, `patrol_bor`, `nco_phase` | **VERIFIED** — sector geometry is public (rare); no structured NCO roster exists |
| Police station points | Socrata (FacDB) | `ji82-xba5`, filter `factype='Police Station'`; `$q=Police` full-text is the reliable query form | **VERIFIED** (coords observed) |
| FDNY firehouses (219) | Socrata | `hc8x-tcnd` — `facilityname` ("Engine 4/Ladder 15"), address, lat/lng | **VERIFIED** |
| FDNY battalions (49) | DCP ArcGIS | `services5.arcgis.com/GfwWNkhOj9bNBqoJ/.../NYC_Fire_Battalions/FeatureServer/0` (`FireBN`) | **VERIFIED** (count 49). Socrata mirror `uh7r-6nya` is map-type |
| School attendance zones ES/MS/HS (2024–25) | Socrata (DOE) | `cmjf-yawu` / `t26j-jbq7` / `ruu9-egea` `.geojson` — `dbn`, `schooldist`, `label`; HS adds `sch_name` | all three **VERIFIED**. **IDs rotate every school year** — see §9's freshness chore. MS partial and HS sparse **by design** (choice-based admission) |
| Community school districts (32) | Socrata | `8ugf-3d8u` `.geojson` (`schooldist` 1–32) | **VERIFIED**. D75/D79 are citywide, no polygon — not mappable |
| CEC member rosters | schools.nyc.gov (HTML) | per-council "Current Members" pages | content confirmed to exist; **UNVERIFIED-fetch — site 403s plain clients (WAF)** → Playwright scraper |
| School points, public+charter+private | NYSED ArcGIS | `services6.arcgis.com/EbVsqZ18sv1kVJ3k/arcgis/rest/services/NYS_Schools/FeatureServer` — layer 2 public / 3 private / 4 charter; 5-county filter → private 809, charter 431; fields `LEGAL_NAME`, `PHYSADDRLINE1`, contact/CEO fields. **Geometry is UTM 18N — request `outSR=4326`** | **VERIFIED** (root + layer sample + counts). City alternative LCGMS `3bkj-34v2` (has principal, DBN) UNVERIFIED-fetch — WAF-throttled without app token |
| Neighborhoods (NTA 2020, 262) | Socrata | `9nt8-h7nd` — `intersects` confirmed (Times Square → "Midtown-Times Square / Manhattan / MN0502"); ~65 NTAs are parks/airports/cemeteries (`ntatype` distinguishes) | **VERIFIED** (262 rows; sample full field list before wiring) |
| ZIP (MODZCTA, 178) | Socrata | `pri4-ifjk` `.geojson` — `modzcta`, `label`, `zcta`, `pop_est` | **VERIFIED** — prefer MODZCTA over raw ZCTA (merges sliver ZIPs, covers the city) |
| BP / DA / citywide officials | official sites | 5 BP sites + 5 DA sites + Mayor/PA/Comptroller; NYC **Green Book** `a856-gbol.nyc.gov` is the authoritative directory | **UNVERIFIED** as scrape targets — see §9 (operator-maintained roster at launch) |

### 6a. Geocoding — GeoSearch replaces both Chicago geocoders

**NYC Planning GeoSearch** (`geosearch.planninglabs.nyc`, Pelias-based, **keyless**, backed by the city's own PAD address file — more authoritative than OSM for NYC addresses):

- `/v2/autocomplete?text=…` — **VERIFIED**; replaces the Photon type-ahead (`index.html:1562–1716`).
- `/v2/search?text=…` — **VERIFIED** (sample: "120 Broadway Manhattan" → `[-74.010542, 40.708233]`); replaces the Nominatim POI geocode (`index.html:2076–2077`) — `pointOfInterest` geocodes street addresses, exactly what PAD covers.

Both return GeoJSON; NYC-scoped by construction, so no viewbox needed. Display the attribution line. Be a courteous client (keep the existing debounce). Nominatim stays as documented fallback only — its usage policy (1 req/s, **no as-you-type autocomplete**) makes it unfit as a public site's primary geocoder. NYC GeoClient/Geoservice requires a key and is server-side-only — skip.

### 6b. Socrata specifics NYC adds over Chicago

- **App token (new requirement):** anonymous NYC portal requests hit WAF throttling (403s observed on `.json` paths during research). Register one free Socrata app token. Runtime: append `$$app_token=` via a top-of-file constant in `index.html` — it's a throttling identifier, not a secret; public exposure is Socrata's intended use. CI scrapers: send `X-App-Token` from a repo secret.
- **Map-type datasets** (`h2n3-98hq`, `uh7r-6nya`, `7vpq-4bh4`): give `loadSocrataGeoJSON` a `preferExport` per-dataset override (Part I §5.3) or use the sibling ArcGIS FeatureServer.
- **Record caps:** several NYC layers approach or exceed route 1's `$limit=1000` (sectors 303 is fine; election districts ~5,000 is not — use the ArcGIS endpoint with `resultOffset` paging).

### 6c. WAF / fetch-engine map (which scraper template to start from)

| Target | Engine |
|---|---|
| nysenate.gov, nyassembly.gov, all Socrata/ArcGIS/TIGERweb | plain `requests` (all fetched clean) — `ilga_scraper.py` template |
| nyc.gov precinct pages, Legistar `People.aspx` | `--engine auto` (fetched clean in research, but keep the Playwright fallback — `cpd_district_scraper.py` template) |
| schools.nyc.gov (CEC, superintendents) | **Playwright from day one** — known 403 bot-block; do not start from the requests template |
| `webapi.legistar.com` | rejected (Incapsula 403 + key requirement); documented alternative only |

### 6d. NYC gotchas that break Chicago assumptions

1. **Borough = county (5 counties in one city).** One static borough geometry serves every borough-level layer (borough, BP, DA, and the judicial relabeling); any "county officeholder" is 5 separate offices.
2. **MultiPolygon everywhere.** Staten Island, the Rockaways, Broad Channel, Roosevelt, City, and Rikers Islands: every boundary dataset is multi-ring MultiPolygon. `pointInGeometry` already handles multi-ring even-odd (confirmed in the Chicago build log) — but spot-check the Rockaways in Thread 1.
3. **Water-heavy map bounds.** Practical bbox ≈ SW `[40.48, -74.27]`, NE `[40.93, -73.68]` (Tottenville → north Bronx → Rockaways). Many in-bounds clicks land in rivers/bays and legitimately resolve to **no district** — surface that honestly, never snap to nearest. Permalink sanity gate ≈ `lat 40.4–41.05, lng -74.3–-73.6`.
4. **Marble Hill** is physically attached to the Bronx but legally Manhattan. Correct polygons give the legally right (counterintuitive) answer — trust them, don't "fix" it.
5. **Nearest-N across water:** haversine can return a station across the East River. Keep N small so "nearest as the crow flies" stays obviously honest.
6. **Non-neighborhood NTAs:** a click in Central Park or JFK returns a real park/airport NTA. Ship unfiltered and surface `ntatype` on the card rather than hiding the feature.

## 7. NYC layer roster — 24 layers (political 10 · safety 5 · schools 6 · geography 3)

`GROUPS` taxonomy unchanged. `EXPECT_LAYERS = 24`.

| # | id | group | label | geometry | roster / officeholder | Chicago pattern reused |
|---|---|---|---|---|---|---|
| 1 | `neighborhood` | geography | Neighborhood (NTA) | Socrata `9nt8-h7nd` | — | `registerPolygonLayer` (community-area) |
| 2 | `zip-code` | geography | ZIP Code (MODZCTA) | Socrata `pri4-ifjk` | — | `registerPolygonLayer` |
| 3 | `borough` | geography | Borough / County | **static** `data/app/borough-boundaries.json` | — (carries county/FIPS crosswalk props) | school-board static-file pattern |
| 4 | `police-precinct` | safety | NYPD Precinct | Socrata `y76i-bdw7` | `data/app/nypd-precinct-info.json` (CO scrape) + non-elected oversight links (CCRB + precinct community council) | police-district + `cpd-district-info` |
| 5 | `police-sector` | safety | NYPD Sector | Socrata `5rqd-h5ci`, `subOf` precinct | — | police-beat `subOf` |
| 6 | `police-station` | safety | Police Station (nearest 3) | FacDB `ji82-xba5` | — | haversine nearest-3 |
| 7 | `fire-station` | safety | Firehouse (nearest 3) | Socrata `hc8x-tcnd` | — | haversine nearest-3 |
| 8 | `fire-battalion` | safety | FDNY Battalion | DCP ArcGIS `NYC_Fire_Battalions` | — | `registerPolygonLayer` + `loadArcGISGeoJSON` |
| 9 | `es-zone` | schools | Elementary School Zone | Socrata `cmjf-yawu` | zoned school via `dbn` + MySchools link | `registerSchoolZone` (generalize profile URL) |
| 10 | `ms-zone` | schools | Middle School Zone | Socrata `t26j-jbq7` | same; honest "choice-based admission" empty state | `registerSchoolZone` + cps-middle honest-empty precedent |
| 11 | `hs-zone` | schools | High School Zone | Socrata `ruu9-egea` | same — most HS admission is unzoned; say so | `registerSchoolZone` |
| 12 | `school-district` | schools | Community School District | Socrata `8ugf-3d8u` | superintendent **link-only** (WAF'd directory) | `registerCpsNetwork` shape, roster→link |
| 13 | `cec` | schools | Community Education Council (parent-elected) | shares `school-district` loader | `data/app/cec-members.json` — ships **empty placeholder** until the Playwright scraper lands | ccpsa shared-geometry + roster-file |
| 14 | `school-site` | schools | School (nearest 3; public/charter/private) | NYSED FeatureServer layers 2/3/4, `outSR=4326` | contact fields in-dataset | school-site nearest-3, `Promise.all` over 3 sublayers |
| 15 | `council` | political | City Council District | Socrata `872g-cjhh` | `data/app/council-members.json` (Legistar scrape) | congress/ILGA same-origin-roster join |
| 16 | `election-district` | political | Election District | DCP ArcGIS `NYC_Election_Districts`, `subOf` state-assembly (`ElectDist` = AD·1000+ED) | — (ballot-counting unit, like ward-precinct) | police-beat `subOf` + ArcGIS loader |
| 17 | `community-district` | political | Community District / Community Board | Socrata `5crt-au7u` | **live** Socrata `ruf7-3wgc` join (chair + district manager + office contacts); membership is BP-appointed — label it so, link the borough site for full lists | `ward` two-live-dataset join |
| 18 | `congress` | political | U.S. House District (NY-N) | TIGERweb layer 0, `STATE='36'` | `data/app/congress-roster.json`, NY-filtered | congress pattern |
| 19 | `state-senate` | political | NY State Senate District | TIGERweb layer 1 | `data/app/ny-senate-members.json` | `registerIlgaChamber` |
| 20 | `state-assembly` | political | NY State Assembly District | TIGERweb layer 2 | `data/app/ny-assembly-members.json` (party stored `null` — source page omits it; render "not published" rather than guess) | `registerIlgaChamber` |
| 21 | `judicial-district` | political | NY Supreme Court Judicial District | **static** `data/app/judicial-districts.json` (counties relabeled 1/2/11/12/13) | link-only: per-JD justices pages on nycourts.gov | il-supreme-court static pattern |
| 22 | `municipal-court` | political | Civil Court (Municipal Court District) | **static** `data/app/municipal-court-districts.json` (from `7vpq-4bh4` export) | link-only: Civil Court directory | ccbr static pattern |
| 23 | `borough-president` | political | Borough President | shares `borough` static loader | `data/app/borough-officials.json` (operator-maintained, §9) | ccpsa shared-geometry + school-board-members roster |
| 24 | `district-attorney` | political | District Attorney | shares `borough` static loader | same `borough-officials.json` | same |

### NYC `LAYER_AREA_RANK` (largest→smallest; **all 24 present**)

```
borough → judicial-district → borough-president → district-attorney   // identical 5 polygons; later = on top
→ congress (~13 in-city) → municipal-court (slot provisional — confirm count at conversion)
→ state-senate (~26 in-city) → school-district (32) → cec (same 32, just after)
→ fire-battalion (49) → council (51) → community-district (59)
→ election-district (deliberately BEFORE its parent, per the beat rule: parent outline frames the fills)
→ state-assembly (~65 in-city)
→ police-sector (before its parent, same rule) → police-precinct (78)
→ zip-code (178) → neighborhood (262)
→ hs-zone → ms-zone → es-zone
→ school-site → police-station → fire-station                          // point layers, topmost
```

### Chicago layers with NO honest NYC analog (dropped, not faked)

| Chicago layer | Why there is no NYC layer |
|---|---|
| `commissioner` | NYC's five counties have no county legislature or elected commissioners — county government was absorbed into the City (Board of Estimate dissolved after *Board of Estimate v. Morris*, 1989). |
| `ccbr` (elected property-tax appeals board) | NYC's analog is the Tax Commission — **appointed, citywide, no districts**. No geometry, no elected roster. |
| `ccpsa-district-council` (elected police oversight) | NYC has no elected police-oversight body. CCRB is appointed and citywide; precinct community councils are volunteer with no central roster. The oversight story becomes link rows on the `police-precinct` card, explicitly labeled non-elected. |
| `school-board` (general-electorate elected board) | No elected school board — mayoral control; the Panel for Educational Policy is appointed. The **CEC** (#13) is the honest *parent*-elected analog; its card carries that one-liner and never calls itself a school board. |

### Future layers (researched, deliberately not at launch)

Surrogate's Court judges (elected countywide; borough geometry ready, roster UNVERIFIED) · FDNY Divisions (`68m2-uzcb`, map-type) · Citywide Education Councils (no geometry) · LCGMS principal enrichment for `school-site` (needs app token) · sector NCO names (no structured source) · full ~50-member Community Board lists (per-borough HTML, non-uniform) · District Leader/State Committee (party-internal — recommend never).

## 8. Offline anchors + smoke-test ground truth

The three static geometry files (Part I §4), all through `build_embedded_boundaries.py`'s `LAYERS` dict with full-precision originals in `data/` and raw pulls in `data/source/raw/`:

1. **`borough-boundaries.json`** — 5 features from `gthc-hcne`; props `{borocode:int, boroname, county, countyfips}`. One shared cached loader serves `borough`, `borough-president`, and `district-attorney`.
2. **`judicial-districts.json`** — 5 features: TIGERweb counties relabeled `{district: 1|2|11|12|13, borough, county}`. No live source for this layer exists anywhere — the derivation *is* the layer.
3. **`municipal-court-districts.json`** — from the `7vpq-4bh4` geospatial export; **pin the exact feature count at conversion time** into `validate_index.py` and the rank slot in §7.

**Smoke test:** primary point **New York City Hall, `40.71274,-74.00602`** — `OFFLINE = ["borough","judicial-district","municipal-court"]`, `EXPECT_DISTRICT = {borough: "Manhattan", judicial-district: "1", municipal-court: <pin at conversion>}` (assert values only after classifying the point against the converted files — the Loop→District-12 protocol). Second point (re-highlight fast path; all three values must differ): **Brooklyn Borough Hall, `40.69354,-73.98963`** → Brooklyn / JD 2. The roster-join check moves to `district-attorney` at City Hall, asserting the field-row *label* renders (names churn; labels don't). New NYC-only check: a mid-East-River point (~`40.7223,-73.9697`) asserts the honest no-match state on `borough` — the water-click honesty rule made executable.

**`validate_index.py` re-derivation:** `GEOMETRY_FILES`: borough (5,5), judicial-districts (5,5), municipal-court (exact, pinned). `ROSTER_FILES` min_keys: `council-members` 48 (vacancy tolerance), `ny-senate-members` 63, `ny-assembly-members` 145, `congress-roster` 26, `borough-officials` 5, `nypd-precinct-info` 0 → raise to 70 after first scrape, `cec-members` 0 → raise to 28 after first scrape (the `cpd-district-info` empty-placeholder precedent). Re-derive `MIN_REGISTER_LAYER` at the assembly thread. Add the §4 sw.js exactly-one-list check.

## 9. Pipeline plan (scraper/builder successors)

Keep the two-stage discipline exactly: scraper writes raw JSON with `source_url`+`scraped_at` per record (nulls on miss, never fabricates); builder resolves into `data/app/` and **refuses to overwrite** below its count floor. Weekly workflows keep the fixed-`bot/*`-branch, force-push, **open-PR-never-commit-to-main** shape — officeholder data always gets human review.

| Chicago pair | NYC successor | Source | Engine | Count guards | Cron (UTC) |
|---|---|---|---|---|---|
| `ilga_scraper.py` + `build_il_roster.py` | `ny_legislature_scraper.py` + `build_ny_roster.py` | nysenate.gov `/senators-committees` + nyassembly.gov `/mem/` | requests+BS4 | 63 senate / 145 assembly; assembly party = `null` | Mon 13:00 |
| `build_congress_roster.py` | same script, re-parameterized | `legislators-current.json` (keep JSON + stdlib urllib — no YAML switch) | stdlib | `"IL"→"NY"`, 17→26; keep whole-state (geometry is whole-state too; `NY-N` labels) | Mon 13:00 |
| `cpd_district_scraper.py` + `build_cpd_roster.py` | `nypd_precinct_scraper.py` + `build_nypd_roster.py` | nyc.gov precinct pages; loop driven from `y76i-bdw7` `precinct` values | `--engine auto` | 70 precincts / 60 commanding officers | Tue 13:00 |
| `ccpsa_scraper.py` + `build_ccpsa_roster.py` | `cec_scraper.py` + `build_cec_roster.py` | schools.nyc.gov CEC "Current Members" pages | **Playwright default** | 28 councils / 150 members | Wed 13:00 |
| — (new) | `legistar_council_scraper.py` + `build_council_roster.py` | Legistar `People.aspx` (district from `/district-N/` URLs) | `--engine auto` | 48 members | Thu 13:00 (new slot) |
| — (new, builder only) | `build_borough_officials.py` | operator-maintained source list: 5 BP + 5 DA official sites | n/a | exactly 5 boroughs × 2 offices | manual (elections are quadrennial). Thread-4 chore: one live Green Book fetch to test upgrading this to a scraper |
| `build_embedded_boundaries.py` | extend `LAYERS` dict | the three §8 anchors | mapshaper via pinned `npx` | existing 2,000-point protocol | operator-run |
| — (new chore) | `check-school-zone-ids.yml` | `/api/views/{id}.json` metadata for the three zone datasets | requests | opens an **issue** (not a PR) if an ID 404s or `rowsUpdatedAt` goes >14 months stale | monthly |

Every builder that splices text keeps the `js_string()` `</script>` + U+2028/U+2029 escaping — that guard closed a real injection bug in Chicago and scraped free text (bios, council pages) is exactly where it matters.

## 10. Thread sequence (port order — differs from Chicago's greenfield order)

- **Thread 0 — Fork & re-core.** Swap every Part I §1 constant, delete the Chicago modules (~`index.html:2712–4263`) leaving one stub layer, swap both geocoders to GeoSearch (§6a), temporary `EXPECT_LAYERS=1`. Deliverable: the engine boots on an NYC map with one stub card.
- **Thread 1 — Offline anchors + Geography.** Convert the three §8 static files; register `borough`, `judicial-district`, `municipal-court`, `neighborhood`, `zip-code`; pin the smoke-test ground truth; Rockaways/islands MultiPolygon spot-check.
- **Thread 2 — Safety.** 5 layers; `nypd-precinct-info.json` ships as empty placeholder.
- **Thread 3 — Schools.** 6 layers; the honest choice-based empty states for MS/HS; `cec-members.json` placeholder.
- **Thread 4 — Political.** 10 layers — heaviest, split in two if needed; operator supplies `borough-officials.json`; Green Book upgrade chore.
- **Thread 5 — Pipeline & CI.** All scraper/builder pairs + workflows; full `validate_index.py` re-derivation; school-zone freshness chore. (Safe to do after modules: every roster-consuming card contractually degrades on an empty placeholder.)
- **Thread 6 — Assembly & audit.** Final `LAYER_AREA_RANK` visual check, both `sw.js` lists + the exactly-one-list invariant, `EXPECT_LAYERS=24`, a11y pass, attribution/footer/disclaimer, deploy.

## 11. Manual operator steps

1. Register a free Socrata app token; add the public constant to `index.html` and the `X-App-Token` repo secret for CI.
2. Buy/point the domain; replace `CNAME`, manifest name/colors, icons, README.
3. Supply the initial `borough-officials.json` (10 names from the 5 BP + 5 DA official sites — verified by hand, per the honesty rule).
4. Review the three static-file conversions (mapshaper validation output) and pin the municipal-court feature count + City Hall ground-truth values into `smoke_test.mjs`/`validate_index.py`.
5. One live fetch of the Green Book (`a856-gbol.nyc.gov`) to assess upgrading `borough-officials` to a scraper.
6. Optional: request a Legistar API key and an Open Legislation API key — both are documented upgrades over the HTML scrapes, neither is required at launch.

## 12. Per-thread handoff protocol

Identical to `BUILD_PLAYBOOK_1.md` §5. Start of a thread: paste Part I §2 (contract) + the §6/§7 rows for the layers being built. End of a thread: append 3 lines under Status —

- `[module] DONE — exposes contract, tested against <point>`
- `[module] STUB — <what's faked>`
- `[module] SURPRISE — <any dataset quirk found>`

---

## Status

_(append handoff notes here as the NYC fork's threads complete)_
