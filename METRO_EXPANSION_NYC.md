# Metro Expansion Playbook — porting District Explorer to a new city

The reference-of-truth for recreating this app for another large metro. **Chicago is the reference implementation; each metro is its own fork** — a separate repo and site cloned from this one, evolving independently. Nothing in this document changes the Chicago app.

Part I is the generic recipe (what any city swaps, in what order). Part II is the NYC worked example, researched and source-verified July 10, 2026 — every endpoint labeled **VERIFIED** below was actually fetched that day with real records observed; **UNVERIFIED** means the source was found but not confirmed. Reverify before relying: dataset IDs, field names, and WAF postures drift.

Part I has now survived one full port: the NYC build (Threads 0–6 plus the first live roster refresh) is complete, and every generalizable lesson its Status log recorded as a SURPRISE has been folded back into Part I. The next metro starts from the amended recipe; the log at the bottom is evidence, not required reading.

Same working style as `BUILD_PLAYBOOK_1.md`: build in small, cheap, focused threads; paste only this playbook's contract + the one module being worked on into a thread, never the whole app.

---

# PART I — The generic metro-porting recipe

## 1. What the fork keeps vs. rewrites

`index.html` (4,608 lines as of July 2026) is roughly **60–65% metro-agnostic engine**: the map boot, layer registry + result-card framework, `state`/`sequence` machinery, URL-hash permalinks, hover explorer, highlight/reorder machinery, and the shared utilities (`sanitize`, `pointInGeometry`, `fetchJSONWithRetry`, `haversineMiles`, `findPropCI`, the Socrata/ArcGIS loaders and caching wrappers). All of that ports untouched. What a new metro rewrites is the ~1,500 lines of layer modules (≈ lines 2712–4263) plus a fixed, enumerable set of hardcoded core values.

**Re-core surgery notes (paid for in NYC Threads 0 and 4):** the module lines are *not* contiguous — the four factories and the shared Socrata/ArcGIS/TIGERweb loaders are interleaved with the reference city's `registerXxx({…})` registration blocks. Delete only the registration call blocks and their city-specific preamble; keep every factory and loader. Then **grep each kept factory for helpers that no longer exist**: NYC's kept `registerIlgaChamber` still called a deleted Chicago helper (`officeAddressForGeocode`), and nothing crashed until the first *real* roster landed two threads later — empty-placeholder rosters never exercise those code paths, so placeholder data hides dangling references. The systematic antidote is §3 step 6's land-one-real-roster-early rule.

**"Engine" code can still speak the reference city's dataset vocabulary (paid for post-launch, PR #9):** the hover explorer is engine, but its fallback property-key lists (`HOVER_NUMBER_KEYS` / `HOVER_NAME_KEYS`, top of the HOVER EXPLORER block) were seeded with Chicago field names (`ward`, `beat_num`, `area_numbe`, `community`…). No NYC dataset uses those keys, so after the port every hover row silently fell to its em-dash fallback — layer label, no district identity — and no gate noticed, because the popup *degrades softly by design*. So the port is not "swap the §1 constants + rewrite the modules" alone: **grep the kept engine for feature-property name literals** and treat every hit as a core constant to re-derive from the new city's observed field names. The durable fix (now in the engine) is that hover identity no longer depends on those lists — see §2's hover-parity rule — but the grep still applies to any future engine code that reads feature properties directly.

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

**Hover-parity rule (added after PR #9):** the hover explorer is a *second render surface* for every polygon layer, and its row identity must come from the **same properties the layer's card reads** — never from the engine's generic key lists alone (those are a per-city fallback, and they cannot decode encoded fields like NYC's `boro_cd` or `ElectDist`). The factories guarantee this for free: `registerPolygonLayer` derives `hoverName` from the card's `primary` field, `registerIlgaChamber` from its `districtFields`, `registerSchoolZone` from its zoned-school (DBN) logic. A **bespoke `registerLayer` block must declare `hoverName(feature)` explicitly**, and `hoverOfficial{load, name}` when the card joins a roster — the same join, prefetched on toggle-on, so hovering never fires a network request (a not-yet-loaded roster just omits the name). A polygon layer with neither a factory-derived nor an explicit `hoverName` should fail review. The honesty rules extend to this surface: an appointed official's name carries its role (NYC renders the community-board chair as "Name (Chair)") so it never reads as an elected district representative.

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
5. **Pick the offline anchors** (§4) and the smoke-test ground-truth points — two positive points landing in different districts, plus the §4 negative point where the geography allows one.
6. **Map the pipeline**: for each roster, which scraper/builder pair template applies, which fetch engine, and the count guards (§9 is the model). Don't defer *every* roster to the pipeline thread: land the cheapest real one (a no-scrape public file, congress-legislators-style) during the modules thread itself — real data flushes factory paths that empty placeholders never exercise (see §1's re-core surgery notes).
7. **Re-derive every gate constant** (§1's last paragraph) and both `sw.js` lists.
8. **Swap deploy**: CNAME, manifest, icons, README, footer attribution. The `deploy-pages.yml` rsync exclude list is generic — but confirm nothing city-new (e.g. a large source GeoJSON) slips into the artifact.
9. **Cross-group parity audit** before calling assembly done: for each field one group's cards render (office address, inline pin, map pin, phone, oversight links), check every other group's cards that *could* carry it. NYC shipped its political cards name-only while the safety and school cards already carried addresses and pins — no gate catches this class of gap; only a deliberate side-by-side pass does. The audit has a **second axis: surfaces, not just groups.** The hover explorer renders every polygon layer too, and it fails *soft* by design (a missed property is a blank row, not an error card) — so also do a **hover sweep**: toggle every polygon layer on, hover each smoke-test ground-truth point, and confirm every row shows a real identity matching its card's headline, not the em-dash fallback. NYC shipped every hover row label-only (fixed in PR #9) because no automated gate exercises the popup.

## 4. The offline-anchor rule

Chicago ships three layers whose boundaries have no reliable public API as same-origin static files (`data/app/*.json`, built by `scripts/build_embedded_boundaries.py`). These are load-bearing far beyond their cards — they are the app's **deterministic anchors**:

- `smoke_test.mjs` classifies the ground-truth point against them (`OFFLINE`/`EXPECT_DISTRICT`) — the only assertions that don't depend on a third-party API being up in CI.
- `validate_index.py` pins their exact feature counts (`GEOMETRY_FILES`).
- `sw.js` serves them **cache-first** (`GEOMETRY_URLS`; boundaries change ~once a decade) vs. **network-first** for rosters (`ROSTER_URLS`; never serve a stale officeholder).
- `build_embedded_boundaries.py`'s `LAYERS` dict is where they're produced: mapshaper (`npx -y mapshaper@0.6.102`, visvalingam keep-shapes) + the validation protocol below.

**Every metro must pick ≥3 such layers** — prefer boundaries that essentially never change and whose live APIs are absent or unreliable — plus a well-known ground-truth point and a second point that lands in different districts (the re-highlight fast-path check). Where the geography allows it (water, unincorporated pockets), also pin a **negative point** that honestly resolves to *no district* in at least one layer — NYC's mid-East-River point returns no borough — so the never-snap-to-nearest honesty rule is an executable smoke check, not prose.

**New invariant for forks** (a gap Chicago itself shipped — `ccpsa-district-councils.json` and `congress-roster.json` were fetched by the app but absent from both SW lists until fixed alongside this playbook): **every file in `data/app/` appears in exactly one of `sw.js`'s `GEOMETRY_URLS` or `ROSTER_URLS`**, and the fork's `validate_index.py` checks it. Bump `CACHE_NAME` on every list change.

## 5. Dataset & roster verification protocol (lessons already paid for)

1. **Live-sample field names before wiring a module.** Every Chicago thread that skipped this shipped a wrong guess. Seed `findPropCI` alias lists with all observed candidates.
2. **The portal-page dataset ID and the geometry-serving ID can differ.** Chicago's ZIP and police-district datasets both 200'd with every geometry `null` on the obvious ID. `loadSocrataGeoJSON` tries three routes (`/resource/{id}.geojson` → `/api/v3/views/{id}/query.geojson` → legacy `method=export`) for exactly this reason; keep that machinery.
3. **The Socrata "map-type" trap:** older map-type datasets return empty/`null` from `/resource/` **by design** — only `/api/geospatial/{id}?method=export&format=GeoJSON` or a sibling ArcGIS FeatureServer serves them. If a registry row is known map-type, don't burn two failing routes per load: give `loadSocrataGeoJSON` a per-dataset route-order override in the fork (the export route already exists as route 3).
4. **Simplification validation:** `build_embedded_boundaries.py` reimplements the app's own even-odd point-in-polygon and requires ≥99.5% agreement on 2,000 seeded random points AND zero points classified into >1 district (topology break = hard fail), feature count and properties unchanged. Use it unmodified for the new city's anchors.
5. **Watch record caps:** Socrata route 1 hardcodes `$limit=1000`; TIGERweb caps transfers (`exceededTransferLimit`) — filter server-side (state/county `where`) or paginate for large layers. NYC hit this twice (1,591 public school points; 4,214 election districts) — the fork's paged ArcGIS loader (`loadArcGISPaged`) is the reusable fix.
6. **Point datasets may serve no geometry at all on the geojson route.** Both NYC point sources (FacDB police stations, FDNY firehouses) return nothing usable from `.geojson` — the coordinates live only in `latitude`/`longitude` *properties*. Sample the geometry route for point datasets separately from polygon datasets; the fix is a loader that assembles a real Point FeatureCollection from the `.json` rows (`makeSocrataPointLoader` in the NYC fork, reused by three layers).
7. **Sample exact values, not just field names.** SoQL `$where` string equality is case-sensitive — `factype='Police Station'` matched **0** rows where `'POLICE STATION'` matched 80 — and numeric-looking fields can arrive as float strings (`schooldist` = `"15.0"`). Record observed *values* alongside field names in the registry, and normalize in the loader so consumers never see the quirk.
8. **Verify coverage, not existence.** A pattern confirmed on one sample can cover a fraction of the roster: Legistar's member grid carried district URLs for only ~24 of 51 council members (forcing a source switch at build time), and the NYPD precinct pages resolve 74 of 78 commanding officers. When a scrape plan depends on a per-record link or label, count how many of N records actually carry it before committing — and set builder count floors below 100% so honest misses don't wedge the weekly pipeline.
9. **Freshness checks fire on successors, not age.** "Stale if `rowsUpdatedAt` > 14 months" cried wolf on NYC's school zones, which legitimately go untouched for 2+ years. The real "swap the dataset ID" signal is a newer edition appearing in the portal catalog (or a 404) — alert on that, never on age alone.
10. **Honesty is per-field, not per-roster.** A source that verifies names may still not publish party or office address (NYC's Open Legislation API covers both chambers but exposes no party; no official page labels it cleanly either). Verify each *field* against a source; store `null` for the rest and render "not published" with a link to where it is published — never backfill a field from a weaker source than the roster itself.
11. **When the official site is unscrapeable, a maintained open aggregator is the honest fallback for structured fields.** nysenate.gov is WAF-403 and nyassembly.gov renders addresses via JS — but Open States v3 publishes each member's structured `offices` array, exactly as congress-legislators does for U.S. House district offices. The official site stays as the card's link target; the aggregator feeds the structured fields it maintains.
12. **Ship keyed enrichments dark.** Guard every enrichment that needs an API key so a missing repo secret — or any fetch error — degrades to the unenriched roster instead of blocking it. Proven end-to-end in NYC: the Open States office-address wiring shipped with no key available; when the operator later added `OPENSTATES_API_KEY`, the next live run populated 63/63 Senate + 150/150 Assembly district offices with zero code change (PR #6).
13. **Surfaces that degrade softly ship broken — audit them by hand.** The hover popup derives each row from feature properties, and its generic fallback key lists were still Chicago vocabulary after the port — so on NYC every row fell to the em-dash fallback and *nothing failed*: soft degradation (the same property the failure-isolation rules require) is invisible to the smoke test, to `validate_index.py`, and to per-card review. Two standing antidotes: (a) every polygon layer sources its hover identity from its card's own field definitions (§2 hover-parity rule), so card and popup cannot disagree; (b) the §3 step 9 hover sweep. When porting, still re-flavor the fallback lists (`HOVER_NUMBER_KEYS` / `HOVER_NAME_KEYS`) to the new city's *observed* field names (§5.1's sampling feeds this), and keep encoded fields **out** of them — NYC's `boro_cd` (`"410"` = Queens CD 10) and `ElectDist` (AD·1000+ED) would misread shown raw; they need each layer's decoder, which is exactly why the per-layer `hoverName` is the primary mechanism and the lists are only a net.

---

# PART II — NYC worked example (nycdistricts fork)

Everything below was researched and (where marked) live-verified **July 10, 2026**. NYC's open-data portal `data.cityofnewyork.us` is Socrata — same platform, same SoQL grammar as Chicago's, and the `intersects(the_geom, 'POINT(lng lat)')` server-side point-in-polygon pattern was **confirmed working** (a Times Square point correctly returned its NTA). The geometry column is `the_geom` on every dataset checked.

## 6. NYC data registry (verified July 10, 2026 — reverify before relying)

| Layer target | Source | ID / endpoint | Status |
|---|---|---|---|
| City Council districts (51) | Socrata | `872g-cjhh` `/resource/872g-cjhh.geojson` | geometry **VERIFIED** (real MultiPolygon); **field names UNVERIFIED** (expect `coundist` — sample before wiring) |
| Council member roster | Legistar (HTML) | `legistar.council.nyc.gov/People.aspx` | **VERIFIED** — server-rendered 51-row grid; district encoded in member URLs (`/district-N/`). **Thread 5 correction: only ~24/51 rows carry that URL (§5.8) — production scrapes council.nyc.gov `/districts/` instead.** `webapi.legistar.com` REJECTED: Incapsula 403 + key-gated |
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
| Municipal Court districts (NYC Civil Court — elected judges) | Socrata | `7vpq-4bh4` — map-type; fields `boro_code`, `boro_name`, `muni_court`. **Route corrected (Thread 1):** the geospatial *export* route returns an empty FeatureCollection — the **v3 view route `/api/v3/views/7vpq-4bh4/query.geojson`** serves the real geometry (loadSocrataGeoJSON route 2) | geometry **VERIFIED** — **28 features**. No clean per-district judge roster → link to the Civil Court directory |
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
3. **`municipal-court-districts.json`** — from `7vpq-4bh4` via the **v3 view route** (the geospatial export returns empty — see §6). Feature count pinned at **28** in `validate_index.py`; `key_prop` is a synthesized unique `label` ("Manhattan Municipal Court District 1", …) since `muni_court` repeats across boroughs.

**Smoke test:** primary point **New York City Hall, `40.71274,-74.00602`** — `OFFLINE = ["borough","judicial-district","municipal-court"]`, `EXPECT_DISTRICT = {borough: "Manhattan", judicial-district: "1", municipal-court: <pin at conversion>}` (assert values only after classifying the point against the converted files — the Loop→District-12 protocol). Second point (re-highlight fast path; all three values must differ): **Brooklyn Borough Hall, `40.69354,-73.98963`** → Brooklyn / JD 2. The roster-join check moves to `district-attorney` at City Hall, asserting the field-row *label* renders (names churn; labels don't). New NYC-only check: a mid-East-River point (~`40.7223,-73.9697`) asserts the honest no-match state on `borough` — the water-click honesty rule made executable.

**`validate_index.py` re-derivation:** `GEOMETRY_FILES`: borough (5,5), judicial-districts (5,5), municipal-court (exact, pinned). `ROSTER_FILES` min_keys: `council-members` 48 (vacancy tolerance), `ny-senate-members` 63, `ny-assembly-members` 145, `congress-roster` 26, `borough-officials` 5, `nypd-precinct-info` 0 → raise to 70 after first scrape, `cec-members` 0 → raise to 28 after first scrape (the `cpd-district-info` empty-placeholder precedent). Re-derive `MIN_REGISTER_LAYER` at the assembly thread. Add the §4 sw.js exactly-one-list check.

## 9. Pipeline plan (scraper/builder successors)

Keep the two-stage discipline exactly: scraper writes raw JSON with `source_url`+`scraped_at` per record (nulls on miss, never fabricates); builder resolves into `data/app/` and **refuses to overwrite** below its count floor. Weekly workflows keep the fixed-`bot/*`-branch, force-push, **open-PR-never-commit-to-main** shape — officeholder data always gets human review.

| Chicago pair | NYC successor | Source | Engine | Count guards | Cron (UTC) |
|---|---|---|---|---|---|
| `ilga_scraper.py` + `build_il_roster.py` | `ny_legislature_scraper.py` + `build_ny_roster.py` | **Corrected (Thread 5):** Open Legislation API `/members` (both chambers, repo secret `NYSENATE_API_KEY`) + best-effort Open States v3 office enrichment (`OPENSTATES_API_KEY`, §5.12); the nysenate.gov/nyassembly.gov HTML plan stays as the documented no-key fallback | stdlib urllib | 63 senate / 145 assembly; party = `null` both chambers (API exposes none, §5.10) | Mon 13:00 |
| `build_congress_roster.py` | same script, re-parameterized | `legislators-current.json` (keep JSON + stdlib urllib — no YAML switch) | stdlib | `"IL"→"NY"`, 17→26; keep whole-state (geometry is whole-state too; `NY-N` labels) | Mon 13:00 |
| `cpd_district_scraper.py` + `build_cpd_roster.py` | `nypd_precinct_scraper.py` + `build_nypd_roster.py` | nyc.gov precinct pages; loop driven from `y76i-bdw7` `precinct` values | `--engine auto` | 70 precincts / 60 commanding officers | Tue 13:00 |
| `ccpsa_scraper.py` + `build_ccpsa_roster.py` | `cec_scraper.py` + `build_cec_roster.py` | schools.nyc.gov CEC "Current Members" pages | **Playwright default** | 28 councils / 150 members | Wed 13:00 |
| — (new) | `council_scraper.py` + `build_council_roster.py` | **Corrected (Thread 5):** council.nyc.gov `/districts/` + per-district pages (all 51, incl. district-office addresses); the Legistar `People.aspx` plan was dropped — its district URLs cover only ~24/51 members (§5.8) | stdlib urllib | 48 members | Thu 13:00 (new slot) |
| — (new, builder only) | `build_borough_officials.py` | operator-maintained source list: 5 BP + 5 DA official sites | n/a | exactly 5 boroughs × 2 offices | manual (elections are quadrennial). Thread-4 chore: one live Green Book fetch to test upgrading this to a scraper |
| `build_embedded_boundaries.py` | extend `LAYERS` dict | the three §8 anchors | mapshaper via pinned `npx` | existing 2,000-point protocol | operator-run |
| — (new chore) | `check-school-zone-ids.yml` | `/api/views/{id}.json` metadata + catalog search for the three zone datasets | requests | opens an **issue** (not a PR) if an ID 404s **or a newer school-year zones dataset appears in the catalog** (refined in Thread 3 — age alone cries wolf, §5.9) | monthly |

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

Status keys: ⬜ not started · 🟡 wired, awaiting operator input · ✅ done.

1. **Socrata app token** — ✅ obtained + wired into the `SOCRATA_APP_TOKEN` constant in `index.html` (2026-07-10); verified live (requests carry `$$app_token=`, bad token → 403). It is public (a throttling id, not a secret), so committing it is correct — do **not** put a Socrata *API Key Secret* here. ✅ Also stored as the `SOCRATA_APP_TOKEN` **repo secret** (confirmed by operator 2026-07-10) so the Thread 5 CI scrapers send it via `X-App-Token` — all five weekly workflows now have every secret they need.
2. 🟡 **Custom domain + icons** — `CNAME` ✅ set to `nyc.chidistricts.com` (operator-owned subdomain, Thread 2); `manifest`/`README`/branding done; borough-seal selection markers + ferry pin landed via PR #2 (`icons/boroughs/`, `icons/app/ferry.png`). ⬜ The PWA icons `icons/app/icon-{192,512}.png` are still the Chicago placeholders — replace them.
3. ⬜ **`borough-officials.json`** (Thread 4) — supply 10 names (5 Borough Presidents + 5 District Attorneys) from the official sites, verified by hand, per the honesty rule.
4. ✅ **Static-file conversions** (Thread 1) — the three anchors are built, validated (≥99.95% / 0 overlaps), and the municipal-court count (28) + City-Hall/Brooklyn ground truth are pinned in `smoke_test.mjs`/`validate_index.py`.
5. ⬜ One live fetch of the Green Book (`a856-gbol.nyc.gov`) to assess upgrading `borough-officials` to a scraper (Thread 4).
6. Optional API keys, both documented upgrades over the HTML scrapes, **neither required at launch**:
   - ✅ **NY Senate Open Legislation API key** — obtained, stored as the repo secret **`NYSENATE_API_KEY`**, wired in Thread 5 (`ny_legislature_scraper.py` reads it server-side — **never** place it in `index.html`, it is a real secret: key-gated, 401 without it), and consumed by the first live roster run (PR #6).
   - ⬜ **Legistar API key** (City Council roster — the HTML `People.aspx` scrape works without it). Request from Granicus/Legistar.
   - ✅ **Open States v3 API key** (`OPENSTATES_API_KEY`) — obtained, stored as the repo secret, and **live**: the first roster run after the secret landed populated district-office address + phone for **63/63 Senate and 150/150 Assembly** members (PR #6); `registerIlgaChamber` renders each with the inline card pin + geocoded map pin. The enrichment stays best-effort (§5.12) — on a missing key or any error it degrades to names-only, never guessing.

### API-key summary (what actually needs a key)

| Service | Key needed? | Used for | Where to get it |
|---|---|---|---|
| **NYC Planning GeoSearch** (geocoder) | **No** — keyless | address search + POI pins | already wired (§6a) |
| **NYC Open Data / Socrata** | **App token obtained ✓ + wired** | every Socrata layer + CI scrapers | in `index.html` + repo secret `SOCRATA_APP_TOKEN` ✓ |
| **U.S. Census TIGERweb / DCP·NYSED ArcGIS** | **No** | legislative + battalion + school-point geometry | — |
| **congress-legislators** | **No** (public CC0 file) | U.S. House roster | — |
| **Legistar API** | Optional | City Council roster (HTML scrape works without) | Granicus/Legistar support request |
| **NY Senate Open Legislation API** | **Obtained + wired ✓** | State Senate + Assembly roster (Thread 5; first live run = PR #6) | repo secret `NYSENATE_API_KEY` |
| **Open States v3 API** | **Obtained + wired ✓** | State Senate + Assembly **district-office addresses** — live, 63 + 150 (degrades to names-only without it) | repo secret `OPENSTATES_API_KEY` (free at `openstates.org/accounts/signup`) |
| GeoClient / Geoservice (NYC) | N/A — **skip** | (server-side only, key-gated; GeoSearch replaces it) | — |

## 12. Per-thread handoff protocol

Identical to `BUILD_PLAYBOOK_1.md` §5. Start of a thread: paste Part I §2 (contract) + the §6/§7 rows for the layers being built. End of a thread: append 3 lines under Status —

- `[module] DONE — exposes contract, tested against <point>`
- `[module] STUB — <what's faked>`
- `[module] SURPRISE — <any dataset quirk found>`

---

## Status

### Thread 0 — Fork & re-core — DONE (2026-07-10)

- `engine` DONE — forked from `DistrictExplorer-CHI`; re-cored to the metro-agnostic engine + one stub layer. Boots on an NYC map; verified headless (Playwright) at New York City Hall `40.71274,-74.00602` — `window.NycExplorer` exported, 1 layer registered, stub card renders, tile-failure banner degrades honestly. `scripts/smoke_test.mjs` (4 checks) passes.
- `stub` STUB — single placeholder layer (`id: "stub"`, group `geography`). No network: empty overlay FeatureCollection, `query()` echoes the picked coordinate, `render()` links the playbook. `EXPECT_LAYERS=1`. Deleted when Thread 1's real geography layers land.
- Core constants swapped (§1): `NYC_BBOX` `[-74.27,40.48,-73.68,40.93]` / `NYC_CENTER` `[40.7128,-74.0060]` (minZoom 10); permalink gate `lat 40.4–41.05, lng -74.3–-73.6`; geolocation + map/search strings; Socrata host → `data.cityofnewyork.us`; TIGERweb `STATE='36'`; verified date `July 10, 2026`; debug namespace `window.NycExplorer` (twinned in `smoke_test.mjs`); preconnect/dns-prefetch hosts. `GROUPS` unchanged. `LAYER_AREA_RANK = ["stub"]` (full §7 rank filled in Threads 1–6).
- Geocoders swapped (§6a): type-ahead → GeoSearch `/v2/autocomplete`; POI → GeoSearch `/v2/search` (both keyless, NYC-scoped, no viewbox). Nominatim retained only as documented fallback.
- Socrata app-token wiring added (§6b): `SOCRATA_APP_TOKEN` top-of-file constant (empty) + `withAppToken()` no-op until the operator registers a token; applied to both Socrata loaders. **Manual step (§11.1) still pending.**
- Branding: title/meta/manifest/theme-color, NYC flag palette (`--nyc-blue #2A6EBB`, `--nyc-blue-deep #12305C`, `--nyc-orange #FF6319`), favicon = NYC flag bands, footer sources, feedback subject. **Chicago six-pointed star replaced with a map-pin motif** (masthead + selection marker). `icons/*.png` are still the Chicago placeholders — **operator to replace (§11.2).**
- `CNAME` set to placeholder `nycdistricts.com` — **operator must own/confirm before deploying to `main` (§11.2).**
- `sw.js` re-cored to shell-only (`CACHE_NAME` → `nyc-district-explorer-shell-v1`); `GEOMETRY_URLS`/`ROSTER_URLS` emptied (refilled Threads 1/5). Orphaned Chicago `data/` removed — no Chicago rosters ship in the NYC app.
- `engine` SURPRISE — the four reusable factories (`registerPolygonLayer` / `registerSchoolZone` / `registerCpsNetwork` / `registerIlgaChamber`) and the shared Socrata/ArcGIS/TIGERweb loaders are interleaved with the deleted module registration calls, not contiguous; the re-core deletes only the 22 `registerXxx({…})` call blocks and their Chicago preamble, preserving the factories. `index.html` 211 KB → 150 KB.

**Carried over as templates, still Chicago, deferred by design:** `scripts/*.py` scraper/builder pairs (→ Thread 5, §9), the 4 Chicago roster-update workflows in `.github/workflows/` (they fail safe at the `validate_index.py` gate — `MIN_REGISTER_LAYER` no longer met — so no bad PR is opened; replaced in Thread 5), `scripts/validate_index.py` (re-derived in Thread 6, §8), factory doc-comments that still cite Chicago datasets. Generic infra kept as-is: `build_embedded_boundaries.py`, `vendor_leaflet.sh`, `deploy-pages.yml`, `smoke-test.yml`, `docs/BUILD_PLAYBOOK_1.md`, `docs/OPTIMIZATION_PLAYBOOK.md`.

_Next: Thread 1 — offline anchors + geography (borough / judicial-district / municipal-court static files; neighborhood; zip-code). Pin the smoke-test ground truth and set `EXPECT_LAYERS` accordingly._

### Thread 1 — Offline anchors + Geography — DONE (2026-07-10)

Five layers registered (`EXPECT_LAYERS = 5`); `LAYER_AREA_RANK` = borough → judicial-district → municipal-court → zip-code → neighborhood. All verified headless (Playwright) at NYC City Hall + Times Square + Brooklyn Borough Hall; the 3 anchors are the deterministic smoke-test ground truth. `scripts/smoke_test.mjs` (10 checks) and `scripts/validate_index.py` both pass.

- `borough` DONE — offline anchor `data/app/borough-boundaries.json` (5 shoreline-clipped counties from Socrata `gthc-hcne`; county + FIPS added via the §6d.1 crosswalk). Shared cached loader `loadBoroughBoundaries` — reused by borough-president / district-attorney in Thread 4. City Hall → Manhattan / New York Co. / 36061.
- `judicial-district` DONE — offline anchor `data/app/judicial-districts.json` (5 TIGERweb counties relabeled JD 1/2/11/12/13; no live source — the derivation IS the layer). Link-only to the court (justices elected countywide, 14-yr terms). City Hall → JD 1.
- `municipal-court` DONE — offline anchor `data/app/municipal-court-districts.json` (**28** features). Link-only to the NYC Civil Court directory. City Hall → "Manhattan Municipal Court District 1".
- `neighborhood` DONE — live Socrata `9nt8-h7nd` (262 NTAs). Times Square → "Midtown-Times Square / MN0502 / Manhattan" (matches §6 verified sample). `ntatype` code mapped to a word onto a derived `ntatype_label` (0=residential hidden; 5 Rikers, 6 non-residential, 7 cemetery, 8 airport, 9 park) so park/airport clicks read honestly (§6d.6).
- `zip-code` DONE — live Socrata `pri4-ifjk` (178 MODZCTA). Times Square → 10036, pop 27428.
- `municipal-court` SURPRISE — the §6 geospatial *export* route returns an **empty** FeatureCollection; the **v3 view route** (`/api/v3/views/7vpq-4bh4/query.geojson`, = loadSocrataGeoJSON route 2) serves the real 28-feature geometry. Playbook §6/§8 corrected. `muni_court` repeats across boroughs, so the build synthesizes a unique `label` for `key_prop`.
- `anchors` SURPRISE — all three built through `build_embedded_boundaries.py` (15% Visvalingam keep-shapes, 6-decimal): borough 99.95% / judicial 100% / municipal 100% point-in-district agreement on the 2,000-point protocol, 0 topology overlaps. TIGERweb county geometry is a single Polygon incl. water (so a mid-East-River point still classifies into a *judicial* district — legally correct), while `borough` (shoreline-clipped MultiPolygon) returns **no borough** there — the water-click honesty rule, now an executable smoke check. Rockaway peninsula (across Jamaica Bay) correctly resolves to Queens (MultiPolygon spot-check).

Gates re-pinned: `smoke_test.mjs` EXPECT_LAYERS=5 + City-Hall/Brooklyn ground truth + mid-river no-borough + per-layer failure isolation; `sw.js` `GEOMETRY_URLS` = the 3 anchors, `CACHE_NAME` → `…-shell-v2`; `validate_index.py` GEOMETRY_FILES (5/5/28) + `EXPECT_LAYER_IDS` + empty ROSTER_FILES. Full-precision sources committed under `data/*.geojson` (excluded from the Pages artifact by `deploy-pages.yml`).

_Next: Thread 2 — Public Safety (NYPD precinct + sector `subOf`, police/fire stations nearest-3, FDNY battalion). `nypd-precinct-info.json` ships as an empty placeholder._

### Thread 2 — Public Safety — DONE (2026-07-10)

Five safety layers registered (`EXPECT_LAYERS = 10`). Verified headless at City Hall (all 5 render; `subOf` nesting confirmed on map + sidebar). Smoke test (10 checks) + `validate_index.py` pass. `CNAME` set to `nyc.chidistricts.com` (operator-owned subdomain). Socrata app token wired + verified.

- `police-precinct` DONE — Socrata `y76i-bdw7` (78). Joins `data/app/nypd-precinct-info.json` (CO roster, **empty placeholder** until Thread 5) **and** the FacDB station houses (address + map pin, keyed on `policeprct`) so the card carries real content pre-scrape (City Hall → Precinct 1, 1st Precinct station @ 16-20 Ericsson Pl). Oversight links: NYPD precinct page (ordinal URL) + CCRB (labeled appointed/citywide, non-elected).
- `police-sector` STUB-roster — Socrata `5rqd-h5ci` (303), `subOf: "police-precinct"` (nests + frames like Chicago beats). Shows sector + parent precinct + patrol borough (code→name map). No NCO roster exists.
- `police-station` DONE — FacDB `ji82-xba5`, nearest-3 haversine.
- `fire-station` DONE — Socrata `hc8x-tcnd` (219), nearest-3.
- `fire-battalion` DONE — DCP ArcGIS `NYC_Fire_Battalions` (49, `FireBN`) via `registerPolygonLayer` + `loadArcGISGeoJSON`.
- SURPRISE — **FacDB `factype` is `'POLICE STATION'` (uppercase)**; the playbook's `'Police Station'` matches **0 rows** (80 with the uppercase value). Used `$where=factype='POLICE STATION'`.
- SURPRISE — **NYC point datasets (FacDB, firehouses) serve NO geometry on the `.geojson` route** — coordinates live in `latitude`/`longitude` *properties*. Added a reusable `makeSocrataPointLoader(dataset, where, latField, lngField)` that builds a real Point FeatureCollection from the `.json` rows (used by both nearest-3 layers; reused by school-site in Thread 3). Added `registerNearestPointLayer` factory + `toTitleCase`/`ordinalSuffix` helpers.

Gates: `smoke_test.mjs` EXPECT_LAYERS=10 (safety layers are live-API, not asserted as CI ground truth); `sw.js` `ROSTER_URLS` += `nypd-precinct-info.json`, `CACHE_NAME` → `…-shell-v3`; `validate_index.py` EXPECT_LAYER_IDS += the 5 safety ids, ROSTER_FILES += `nypd-precinct-info.json` (min 0).

_Next: Thread 3 — Schools (ES/MS/HS attendance zones with honest choice-based empty states, community school district, CEC placeholder, school-site nearest-3). School-zone dataset IDs rotate yearly — add the freshness chore._

### Thread 3 — Schools — DONE (2026-07-10)

Six schools layers registered (`EXPECT_LAYERS = 16`). Verified headless at Park Slope / Brooklyn (CSD 15) — zoned ES + honest choice-based empty states for MS/HS; screenshot. Smoke (16 checks) + `validate_index.py` + the new freshness check all pass.

- `es-zone` / `ms-zone` / `hs-zone` DONE — Socrata `cmjf-yawu` / `t26j-jbq7` / `ruu9-egea` via the generalized `registerSchoolZone` factory. `schoolProfileHtml` re-pointed off Chicago's cps.edu to **MySchools** (`/en/schools/<dbn>/`, verified 200). Honest empty states: the factory keys "is there a zoned school" on the **DBN** (MS/HS choice catchments carry a district placeholder label like `"D15"` with a null DBN), so a choice-based area renders opts.emptyNote instead of a bogus school. Park Slope → ES "P.S. 321", MS/HS "None — choice-based / by application".
- `school-district` DONE — Socrata `8ugf-3d8u` (32) via `registerPolygonLayer`. Superintendent link-only (appointed by the Chancellor, not elected). `schooldist` arrives as a float string (`"15.0"`) — normalized to `"15"` in the loader (`intField`).
- `cec` DONE — shares the `school-district` geometry; `data/app/cec-members.json` ships **empty placeholder** until the Thread 5 Playwright scrape (schools.nyc.gov WAF-blocks plain clients). Card carries the "parent-elected council — not a school board (NYC has mayoral control)" one-liner (§7).
- `school-site` DONE — NYSED ArcGIS `NYS_Schools` layers 2/3/4 (public 1591 / private 809 / charter 431), 5-county filter, `outSR=4326`. Public exceeds the 1000-row transfer cap → added a **paged** ArcGIS loader (§5.5). `registerNearestPointLayer` across the merged, type-tagged points.
- SURPRISE — the zone datasets are **"School Zones 2024-2025"**, last touched 2024-03 (~28 months). The playbook's ">14-month `rowsUpdatedAt`" heuristic would cry wolf on this genuinely-current data (NYC leaves zones untouched for 2+ years), so the freshness chore was **refined**: it now flags a 404 **or** a *newer school-year zones dataset appearing in the catalog* (per level), which is the real "time to swap the id" signal. Catalog confirms 2024-2025 is the latest → check passes; it will fire when 2025-2026 lands.

Freshness chore added (§9): `scripts/check_school_zone_ids.py` + `.github/workflows/check-school-zone-ids.yml` (monthly; opens a deduped tracking **issue**, never a PR). Gates: `smoke_test.mjs` EXPECT_LAYERS=16; `sw.js` `ROSTER_URLS` += `cec-members.json`, `CACHE_NAME` → `…-shell-v4`; `validate_index.py` += the 6 school ids + `cec-members.json` (min 0).

_Next: Thread 4 — Political (10 layers: council, election-district `subOf` assembly, community district/board live join, congress, state senate/assembly, judicial already done, borough-president, DA). Heaviest thread; operator supplies `borough-officials.json`. The NY Senate roster can use the Open Legislation key (Thread 5)._

### Thread 4 — Political — DONE (2026-07-10, branch `claude/nyc-thread-4-political`)

Eight political layers registered — **all 24 layers now live** (`EXPECT_LAYERS = 24`). Built on a fresh branch off the merged `main` (which had also gained borough-seal selection markers via PR #2 — untouched). Verified headless at City Hall (all 8 render, no page errors); smoke (24-layer) + `validate_index.py` pass.

- `community-district` DONE — Socrata `5crt-au7u` (`boro_cd` "410" = Queens CD 10) **live-joined** to `ruf7-3wgc` (chair + district manager + office phone/email/website). City Hall → Manhattan CD 1, Chair Tammy Meltzer, DM Zach Bohmer. Note labels the board as appointed, not elected.
- `congress` DONE — TIGERweb layer 0 + **real roster** `congress-roster.json` (26 NY U.S. House reps built now from congress-legislators, public CC0 — no scrape). City Hall → NY-10, Daniel S. Goldman (D). Via `registerIlgaChamber`.
- `state-senate` / `state-assembly` DONE — TIGERweb layers 1/2 (`SLDU`/`SLDL`) via `registerIlgaChamber`; rosters `ny-senate-members.json` / `ny-assembly-members.json` ship **empty placeholders** (Thread 5 scrapes) → cards degrade to the official directory. City Hall → SD 27, AD 66.
- `election-district` DONE — DCP ArcGIS `NYC_Election_Districts` (**4,214** features, paged past the 1000-row cap via new `loadArcGISPaged`). `ElectDist` = AD·1000 + ED. `subOf: "state-assembly"` (nests + frames like police-sector). City Hall → ED 72 (AD 66) — AD matches the parent Assembly district.
- `council` DONE — Socrata `872g-cjhh` (51); `council-members.json` empty placeholder → links to `council.nyc.gov/district-N`.
- `borough-president` / `district-attorney` DONE — share the Thread-1 `borough` geometry; `borough-officials.json` **empty placeholder** (operator supplies 10 hand-verified names, §11.3) → cards name no one and link to the **NYC Green Book** (authoritative directory).
- SURPRISE — the kept `registerIlgaChamber` factory referenced `officeAddressForGeocode`, a Chicago helper that had been deleted in Thread 0 — never triggered until a real roster (congress) landed. Defined it + generalized the factory's Chicago labels (Springfield → `capitolLabel`, "ILGA profile/directory" → configurable) so all three chambers read correctly.

Gates: `smoke_test.mjs` EXPECT_LAYERS=24 (political roster-backed layers are live/placeholder, not CI ground truth — the 3 offline anchors remain the deterministic check); `sw.js` `ROSTER_URLS` += the 5 new roster files, `CACHE_NAME` → `…-shell-v6`; `validate_index.py` += the 8 political ids + roster floors (`congress-roster` 26, rest 0).

_Next: Thread 5 — Pipeline & CI (the scraper/builder pairs + weekly workflows for every roster: NY legislature, NYPD precinct CO, CEC, City Council/Legistar, congress refresh; operator-maintained borough-officials). Then Thread 6 — assembly & audit (final `LAYER_AREA_RANK` visual pass, the `sw.js` exactly-one-list invariant, a11y, deploy)._

### Thread 5 — Pipeline & CI — DONE (2026-07-10, branch `claude/nyc-thread-5-pipeline`)

Six scraper/builder pairs + five staggered weekly workflows; **five rosters now carry real officeholders** (verified headless — the cards that linked to a directory in Thread 4 now name the person). Chicago pipeline removed. Smoke + `validate_index.py` (floors raised) pass.

- `ny-senate-members` / `ny-assembly-members` DONE — `ny_legislature_scraper.py` (NY Senate **Open Legislation API**, key-gated) + `build_ny_roster.py`. 63 senate / 150 assembly, deduped by district (incumbent-preferred). City Hall → SD 27 Brian Kavanagh, AD 66 Deborah Glick.
- `council-members` DONE — `council_scraper.py` + `build_council_roster.py`. **51** members. City Hall → CD 1 Christopher Marte.
- `nypd-precinct-info` DONE — `nypd_precinct_scraper.py` (nyc.gov precinct pages, driven from `y76i-bdw7` precinct values) + `build_nypd_roster.py`. 78 precincts, **74 commanders**. Precinct 1 → Captain Robert Fisher.
- `congress-roster` DONE — `build_congress_roster.py` (re-parameterized from Chicago; congress-legislators, 26 NY reps).
- `cec-members` STUB — `cec_scraper.py` (Playwright, §6c) + `build_cec_roster.py` written; the per-council URL map on schools.nyc.gov needs confirming, so the builder keeps the **empty placeholder** (a short scrape is a no-op, not a failure) and the card links to the council page. Not a hard blocker.
- `borough-officials` STUB — `build_borough_officials.py` + `scripts/borough_officials_source.json` (operator template). Left **empty on purpose**: a Nov-2025 election means the current 5 BP + 5 DA can't be verified here, and officeholders are never guessed — the operator fills the source (§11.3). Cards link to the NYC Green Book until then.
- SURPRISE — the Open Legislation API `/members` endpoint covers **both** chambers but exposes **no party**; nysenate/nyassembly/council.nyc.gov don't cleanly label it either, so **party is stored null everywhere** (never guessed) — cards show name + district + the member's directory (where party is shown).
- SURPRISE — Legistar `People.aspx` only populates the district-website link for **~24 of 51** council members, so its "district from `/district-N/` URLs" plan (§9) is incomplete; used `council.nyc.gov/districts/` instead (all 51, name in each card's photo alt).

Workflows (staggered, open-PR-never-commit): `update-ny-legislature-roster.yml` (Mon 13:00), `update-congress-roster.yml` (Mon 13:30), `update-nypd-roster.yml` (Tue 13:00), `update-cec-roster.yml` (Wed 13:00, Playwright), `update-council-roster.yml` (Thu 13:00). Removed the Chicago scrapers/builders (`ilga`, `cpd`, `ccpsa`, `build_il`) + their workflows. `validate_index.py` roster floors raised (senate 60 / assembly 145 / council 48 / nypd 70 / congress 26; CEC + borough 0). Scraper intermediates go to `scripts/.cache/` (gitignored).

**Operator, for CI (§11):** add two repo secrets — `SOCRATA_APP_TOKEN` (NYPD scrape) and `NYSENATE_API_KEY` (NY legislature scrape). Without them those two weekly workflows fail at the scrape step; the rest run without secrets.

_Next: Thread 6 — assembly & audit (final `LAYER_AREA_RANK` visual pass, the `sw.js` exactly-one-list invariant check in `validate_index.py`, a11y/attribution, deploy). Optional: confirm the CEC council-page URL map so `cec_scraper.py` resolves; operator fills `borough_officials_source.json`._

### Fix — Political office addresses + map pins (2026-07-10, branch `claude/nyc-political-addresses`)

The political cards showed name + district but (unlike the safety/school cards) no office address, inline card-pin icon, or map pin. Added them where an office source exists:

- `community-district` — the live `ruf7-3wgc` data already carries `cb_office_address` (+ `cb_address_line_2`); surfaced it as a "Board Office" field with the inline pin + a `pointOfInterest` map pin (Manhattan CB 1 → 1 Centre Street, Room 2202-N).
- `congress` — `build_congress_roster.py` now joins `legislators-district-offices.json` (address + lat/lng) and adds `districtOffice` to each rep; `registerIlgaChamber` renders it with pin + POI automatically (NY-10 → 290 Broadway Suite 291). 26/26.
- `council` — `council_scraper.py` now fetches each `council.nyc.gov/district-N` page and extracts the "District Office" address; the module renders it with pin + POI. 51/51.
- `state-senate` / `state-assembly` — **wired via Open States v3** (`ny_legislature_scraper.py` → optional `openstates_offices()`; needs the free `OPENSTATES_API_KEY`, §11.6). The direct sources are unusable (Open Legislation API exposes no offices; nysenate.gov is WAF-403; nyassembly.gov renders addresses via JS, empty in static HTML), so we pull the structured `offices` array from Open States, prefer the `district` office, and pass it through `build_ny_roster.py` as `districtOffice`. `registerIlgaChamber` renders it with pin + POI automatically. **The key is not set in this sandbox, so the shipped roster is still names-only** — the addresses populate the moment the operator adds the repo secret and the weekly workflow reruns (or `OPENSTATES_API_KEY=… python3 scripts/ny_legislature_scraper.py && python3 scripts/build_ny_roster.py` locally). Enrichment is best-effort: on missing key or any error it degrades to names-only, never guessing.
- **Deferred:** Borough President / District Attorney offices come with the operator's `borough-officials.json`; Judicial / Civil Court / Election District have no single office by design.

Verified headless: address + inline pin icon + map POI pin render for community-district/congress/council; the state-leg wiring was verified with a `districtOffice` fixture (SD 27 → 250 Broadway Suite 2011 renders inline pin + map pin). smoke + `validate_index.py` pass.

### Thread 6 — Assembly & audit — DONE (2026-07-10, branch `claude/nyc-thread-6-assembly`)

Final assembly pass over the fully-populated 24-layer app. No new layers — this thread hardens the invariants that the module threads only checked by eye.

- **`LAYER_AREA_RANK` audit → executable.** All 24 registered ids appear exactly once in the z-order stack, in the §7 order (beat-rule exceptions intact: `election-district` before `state-assembly`, `police-sector` before `police-precinct`; points topmost). `validate_index.py` now cross-checks `LAYER_AREA_RANK` against the registered id set — a registered-but-unstacked layer (or a stale id) now fails the gate instead of silently mis-rendering. Negative-tested both directions.
- **`sw.js` exactly-one-list invariant → executable.** The §4 rule ("every `data/app/` file in exactly one of GEOMETRY_URLS / ROSTER_URLS") is now enforced in `validate_index.py`: it parses both sw.js arrays and fails on a file that's double-listed, in neither, or missing from disk. All 10 data files map cleanly (3 boundaries cache-first, 7 rosters network-first). Negative-tested (both-list case caught).
- **`EXPECT_LAYERS = 24`** — confirmed at runtime by the smoke test (counts `input[id^=toggle-]`; found 24), not just asserted.
- **a11y** — verified the carried-over scaffolding is intact: `map` `role=application` + descriptive label, search `role=search` with associated (visually-hidden) label, results `aria-live=polite`, layer toggles built as `<label for=toggle-id>`+checkbox with decorative color-dots `aria-hidden`, banners `role=status`, feedback `role=dialog aria-modal`. No gaps found.
- **Attribution** — added the three now-active sources missing from the footer: NYC ArcGIS (fire battalions + election districts), NYS Education Dept (school districts), and Open States (state-leg offices). Basemap tiles already carry on-map OSM + CARTO attribution.
- **Deploy** — GitHub Pages deploys from `main` on merge (existing `Deploy to GitHub Pages` workflow); CNAME `nyc.chidistricts.com`. All 10 smoke checks + `validate_index.py` (now 6 checks) green.

Operator items still open (unchanged, §11): enable "Allow GitHub Actions to create and approve PRs"; add repo secrets `SOCRATA_APP_TOKEN` + `NYSENATE_API_KEY` (+ optional `OPENSTATES_API_KEY` for state-leg office addresses); replace placeholder `icons/app/*.png`; fill `borough_officials_source.json`; confirm CEC page URLs.

### Roster refresh #1 + playbook generalization — DONE (2026-07-10, branch `claude/metro-expansion-playbook-e3rpzi`)

The pipeline completed its first live cycle, and this pass folds every generalizable lesson from the NYC build back into Part I so the next metro inherits the amended recipe instead of re-mining this log.

- `pipeline` DONE — `update-ny-legislature-roster.yml` ran with the operator's `NYSENATE_API_KEY` + `OPENSTATES_API_KEY` secrets and opened **PR #6** (bot-authored, human-reviewed, merged): the open-PR-never-commit shape carried from Chicago is now proven end-to-end on NYC. The Senate (63/63) and Assembly (150/150) rosters carry `districtOffice` (address + phone) — the enrichment that shipped dark in the addresses fix populated with **zero code change** once the secrets landed (§5.12, made real). Party remains `null` everywhere (§5.10).
- `playbook` DONE — generalization pass: §5 retitled "Dataset & roster verification protocol" and extended with lessons 6–12 (point-geometry route, exact-value sampling, coverage-not-existence, successor-not-age freshness, per-field honesty, aggregator fallback, ship-enrichments-dark); §1 gained the re-core surgery notes (interleaved factories; the dangling-helper trap); §3 gained the land-one-real-roster-early rule (step 6) and the cross-group card-parity audit (step 9); §4 gained the negative ground-truth point; §11 statuses refreshed (CNAME ✅ `nyc.chidistricts.com`; both state-legislature keys ✅ wired). `README.md` brought current (pipeline live, layers no longer "planned", operator list trimmed).
- SURPRISE — Thread 6 landed on `main` (PR #7) mid-pass, closing the two gate items this entry originally tracked as open (`LAYER_AREA_RANK` cross-check and the §4 sw.js exactly-one-list invariant are now executable in `validate_index.py`). Its closing operator list restated stale §11 state, corrected here by evidence from PR #6: the PR was **opened by `github-actions[bot]`** (Actions PR-creation already enabled) and its roster carries API + Open States data (`NYSENATE_API_KEY` + `OPENSTATES_API_KEY` already set). Actually remaining for the operator (§11): replace the Chicago PWA icons (`icons/app/icon-{192,512}.png`), fill `borough_officials_source.json`, confirm the CEC per-council URL map. (`SOCRATA_APP_TOKEN` was subsequently confirmed as a repo secret too — all five weekly workflows are fully keyed.)

### Fix — Hover popup identity sourcing — DONE (2026-07-10, branch `claude/hover-popup-data-sourcing-8spx8j`, PR #9)

User-reported: the hover popup showed only layer names. Every row's value fell to the em-dash fallback because the engine's generic key lists (`HOVER_NUMBER_KEYS` / `HOVER_NAME_KEYS`) still carried Chicago field vocabulary (`ward`, `beat_num`, `area_numbe`, `community`…) that no NYC dataset uses — the port's re-core swap missed them because they live in "engine" code, and the popup's designed soft degradation meant no gate fired (the smoke test doesn't exercise hover).

- `hover` DONE — every polygon layer now sources its hover identity from the same properties its card reads: `registerPolygonLayer` auto-derives `hoverName` from the card's `primary` field (neighborhood, zip-code, borough, judicial-district, municipal-court, school-district, fire-battalion); `registerIlgaChamber` extracts via its `districtFields` (congress, state-senate, state-assembly); `registerSchoolZone` mirrors the card's DBN logic (school name, honest "None" for choice catchments); explicit `hoverName` on the bespoke blocks — police-precinct, council, cec ("CEC n"), community-district (decoded "Boro CD n"), borough-president / district-attorney. Fallback lists re-flavored to NYC field names; encoded fields (`boro_cd`, `electdist`) deliberately excluded from them.
- `hoverOfficial` DONE — the popup now names officeholders via the same joins the cards make, prefetched on toggle-on (never a network request mid-hover): council member, precinct commanding officer, community-board chair (rendered "Name (Chair)" — the board is appointed, so the name must not read as an elected rep), BP/DA wired dark until `borough-officials.json` is filled (§5.12 pattern).
- SURPRISE — "engine" code carried city vocabulary: §1's metro-agnostic-engine claim hid two Chicago property-key lists inside the hover explorer. Folded back into Part I as the §1 grep-the-engine-for-property-literals note, the §2 hover-parity rule, the §3 step 9 hover sweep, and §5 lesson 13.
- Verified: `validate_index.py` + full smoke test pass; a Playwright hover check at City Hall shows all five offline-anchor rows with real identities (Manhattan / JD 1 / "Manhattan Municipal Court District 1" / BP + DA boroughs) where before each showed only the label.
