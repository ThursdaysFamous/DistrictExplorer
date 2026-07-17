# SF Port — §0 City Worksheet (Thread 0 deliverable)

Working artifact for porting District Explorer to **San Francisco**, per
`docs/METRO_EXPANSION_PLAYBOOK.md` Part I §0. This is the parameter block the
rest of the port refers back to. It lives here on the `next-metro-port` branch
until the `DistrictExplorer-SF` fork repo exists, then moves into that repo as
its own worksheet (the NYC record — `docs/archive/METRO_EXPANSION_NYC.md` — is
the model for a completed one).

**Honesty markers** (repo convention — never guess officeholders or IDs):
- ✅ **Confirmed** — established from an authoritative source *this session* (July 2026); see the verification log.
- 🔎 **Needs live-fetch** — value is proposed, but the playbook's VERIFIED bar means *fetching that exact endpoint and seeing records* before wiring. Not yet done.
- ⏳ **TBD (mid-port)** — cannot be finalized until the layer roster / anchor files exist (§0 marks these).
- 🎛️ **Operator decision** — a choice for Adam (domain, brand, repo).

---

## The worksheet

| Parameter | San Francisco value | Status |
|---|---|---|
| `CITY_NAME` | San Francisco | ✅ |
| Metro slug (`THIS_METRO`) | `sf` | ✅ (matches the `nyc` convention) |
| `METRO_NAME` | San Francisco | ✅ |
| `STATE_FIPS` | `'06'` (California) | ✅ |
| County structure | **City and County of San Francisco** — consolidated, **coterminous** (city = county), FIPS **06075**. One county, no multi-county partial-coverage problem. The Board of Supervisors is simultaneously the city council **and** the county board. | ✅ — the single biggest simplifier vs. Chicago; kills the §7 multi-county gotcha outright |
| School governance | **One unified district (SFUSD).** Board of Education = **7 commissioners elected *at-large* (citywide)**, *not* by district → per §3 step 4's at-large rule there is **no districted `school-board` layer** (the biggest roster delta from Chicago's 10 ERSB districts). Assignment is **choice-based / lottery** (attendance area is only a tiebreaker) → the schools group needs NYC-style honest "not a guaranteed school" empty states. | ✅ governance; 🔎 zone datasets |
| `BBOX` | `{minLng:-122.517, minLat:37.703, maxLng:-122.353, maxLat:37.833}` — mainland peninsula + Treasure Island. **Farallon Islands** (~-123.00, 37.70) are legally SF but excluded from the box (far-west exclave — handle as MultiPolygon per §7, don't let them blow out the bias box). | 🔎 (tighten against the real county polygon at conversion) |
| `CENTER` + zoom | `[37.7749, -122.4194]`, initial zoom **12**, `minZoom` **11** (SF is compact — ~47 mi², smaller than Chicago, so one notch tighter than Chicago's 11/9). | 🔎 (eyeball after boot) |
| Permalink sanity bounds | lat **37.60–37.95**, lng **-122.60–-122.30** (deliberately looser than `BBOX` — greater SF/peninsula; independent constant, §1's easiest-to-miss row). | 🔎 |
| Open-data portal(s) | **`data.sfgov.org` — Socrata** (DataSF; mature, same platform + SoQL grammar as Chicago/NYC → the engine's whole Socrata stack ports as a host-constant swap). Consolidation means nearly all civic geometry lives on DataSF; SF Enterprise GIS / `sfgov` ArcGIS backs a few layers. | ✅ platform; 🔎 per-dataset |
| App token needed? | Start anonymous; register a **free Socrata app token** at the first 403/429. NYC's DataSF twin WAF-throttled anonymous clients during research, so budget for one (public constant in `index.html`, `X-App-Token` repo secret for CI — §5.4). | 🔎 |
| Geocoders | **Photon** (SF-biased type-ahead) + **Nominatim** (POI, submit-time, serial ≥1s queue) — Chicago's stack, unchanged. **No city-run keyless autocomplete API found** (SF publishes the **EAS** address-point dataset `3mea-di5p` on DataSF but not a GeoSearch-style endpoint), so §5.3 rule → fall back to Photon/Nominatim. EAS noted as a possible future self-hosted-Pelias upgrade, not a launch dependency. | ✅ decision; 🔎 EAS-upgrade |
| School profile URL | SFUSD school pages under `sfusd.edu` (exact deep-link slug pattern to confirm). | 🔎 |
| Domain / CNAME | **`sf.chidistricts.com`** (proposed — mirrors `nyc.chidistricts.com`). | 🎛️ |
| Feedback email | `adam@overberg.co` | ✅ |
| Repo | **`ThursdaysFamous/DistrictExplorer-SF`** (public, same account as CHI/NYC — to create). | 🎛️ |
| Brand | Proposed: **International Orange** (Golden Gate Bridge, ≈`#C0362C`) primary + a bay-blue / SF-gold secondary; SF-flag phoenix as the masthead emblem. | 🎛️ / ⏳ |
| Offline anchors *(mid-port)* | Candidates: **`supervisor-districts` (11)**, **`analysis-neighborhoods` (41)**, and a third stable one (**`police-districts` (10)** or the countywide **Superior Court** = 1 feature, weak). Use **`supervisor-districts`** as the out-of-scope mask tiler — 11 districts tile the city exactly (Chicago's ERSB / NYC's boroughs analog). | ⏳ |
| Ground truth *(mid-port)* | Primary: **SF City Hall `37.77927,-122.41924`** → Supervisor District 5 (verify), + its neighborhood + police district. Second point (different districts): **Ferry Building `37.79550,-122.39370`** → Supervisor District 3. Negative point: mid-Bay or Pacific (e.g. `37.83,-122.37`) → honest no-match on the shoreline-clipped supervisor/neighborhood layer (§4 negative-point). | ⏳ — assert only after classifying against the converted files |
| `EXPECT_LAYERS` *(mid-port)* | TBD — final registered-layer count (expect **fewer** than Chicago's 33 / NYC's 24-analog: SF drops the districted school board, districted supreme court, separate county commissioner, and board-of-review layers). | ⏳ |

---

## Roster implications worth flagging now (headline deltas from Chicago)

Full §3-step-4 map-or-drop table is Thread 4 work, but the structural consequences of SF's government shape are already clear and shape the whole port:

- **Board of Supervisors (11) is one shared-loader layer doing two jobs** — city council *and* county board (consolidated). Chicago needs separate `ward` (50) + `commissioner`; SF collapses both into 11 supervisor districts. (§7 "one boundary hosts several offices → one cached loader.")
- **Drop the districted `school-board` layer** — SF's Board of Education is elected **at-large**; no district geometry exists to map. The board becomes a citywide office (at-large rule: link/defer, never a polygon).
- **Drop `il-supreme-court` analog** — the California Supreme Court is statewide (not districted). CA Courts of Appeal have districts but justices are **appointed** → link-only at most.
- **Drop `ccbr` / `commissioner` analogs** — SF's assessment-appeals board is appointed; there's no elected county board of review, and no county commissioner separate from the supervisors.
- **District Attorney is countywide (citywide)** — unlike NYC's five borough DAs, SF's DA is one at-large office → no DA polygon layer.
- **Federal/state tier is free & standard** — CA Senate (40) / Assembly (80) / US House (52) via TIGERweb `STATE='06'` + `congress-legislators` (re-parameterize `IL`→`CA`, 17→52). SF spans a handful of each.
- **Candidate SF-specific *add*: BART Director districts** — the regional transit board **is elected by district**, and part of the network sits in SF. A genuinely local, honestly-districted, roster-backed layer with no Chicago analog. Flag for the roster thread.

Net: SF's *political* stack is **thinner** than Chicago's (consolidation + at-large offices remove several districted layers), but cleaner — and the schools group leans on NYC's choice-based honest-empty precedent rather than Chicago's attendance-guarantee model.

---

## Draft METRO config values (the §1 constant swaps — partial, §0-level only)

The layers / anchors / data-files / rosters sections of a real `metro-worksheet.json`
are filled during the module threads; this is only the config-level block.

```jsonc
{
  "this_metro": "sf",
  "metro_name": "San Francisco",
  "metro_bbox": { "minLng": -122.517, "minLat": 37.703, "maxLng": -122.353, "maxLat": 37.833 },
  "metro_center": [37.7749, -122.4194],
  "permalink_gate": { "minLat": 37.60, "maxLat": 37.95, "minLng": -122.60, "maxLng": -122.30 },
  "socrata_host": "https://data.sfgov.org",
  "socrata_app_token": "",                       // set at first 403/429
  "repo_issues": "https://github.com/ThursdaysFamous/DistrictExplorer-SF/issues/new",
  "feedback_subject": "San Francisco District Explorer feedback",
  "exports_name": "SFExplorer",                  // rename ChiExplorer in index.html + smoke_test.mjs together
  "domains": { "canonical": "https://sf.chidistricts.com/" }
}
```

**Cross-metro footer (`METRO_EXPLORERS`) — add this entry in *every* fork (CHI, NYC, SF) per §1:**

```jsonc
{ "id": "sf", "label": "San Francisco", "url": "https://sf.chidistricts.com/", "emoji": "🌉",
  "bbox": { "minLng": -122.60, "minLat": 37.60, "maxLng": -122.30, "maxLat": 37.95 } }
```

---

## Verification log (this session, July 2026)

Established from authoritative sources — **not** yet the playbook's endpoint-level VERIFIED (no DataSF endpoint fetched this session):

- **Consolidated city-county / coterminous** — SF government structure. *(Wikipedia: Government of San Francisco.)*
- **Board of Supervisors: 11 districts, elected by district, nonpartisan 4-yr terms.** *(Wikipedia: SF Board of Supervisors; Ballotpedia 2026.)*
- **Board of Education: 7 commissioners, elected at-large citywide.** *(Wikipedia: SF Board of Education.)*
- **DataSF is Socrata; SFUSD Attendance Areas published there (`e6tr-sxwg`, 2024-25).** *(DataSF; dev.socrata.com foundry.)*
- **Assignment is choice-based/lottery, attendance area a tiebreaker.** *(SFUSD student-assignment pages; KQED.)*
- **EAS address points on DataSF (`3mea-di5p`); no city keyless autocomplete geocoder surfaced.** *(DataSF EAS dataset.)*

## Still to verify at build time (the 🔎 rows)

1. One live `intersects(the_geom,'POINT(lng lat)')` on a DataSF dataset at a known SF landmark — validates endpoint + geometry column + app-token posture in one shot (§6.5).
2. Exact dataset IDs + geometry route + observed field names for: supervisor districts, analysis neighborhoods, police districts/companies, SFPD/SFFD stations, ES/MS/HS attendance zones (rotate yearly → freshness chore), SFUSD schools points.
3. SFUSD school-profile deep-link pattern.
4. BART director-district geometry + elected roster source (candidate add).

## Performance parity for the SF port (see playbook §13)

The reference forks' measured perf campaign splits into what SF **already has** and what SF **must re-earn** — playbook §13 is the full guide; this is the SF-specific cut.

**Already in the SF seed (engine-fenced — do NOT delete in the Thread-0 re-core):** bbox pre-reject in `findFeatureContaining` (R2-6), `whenIdle` scope-mask boot-defer (R2-3), drop-shadow pan-pause (R2-5), memoized/incremental click + toggle paths (P7/P8/P11), loader hardening (`geometryPrecision=6`, timeouts, `hasUsableGeometry`), `loadArcGISPaged` + `makeSocrataPointLoader`, geocoder debounce + serial POI queue, the whole `sw.js` handler block. SF's `index.html` is byte-identical to the current CHI reference (verified), so it carries all 45 engine fences at their latest state. **Guard after the re-core:** `check_engine_parity.py index.html --against https://chidistricts.com/ --strict` clean.

**SF must re-earn (metro-specific — §13.2):**
- *Thread 0 `<head>`:* inline `leaflet.css`; self-host + subset SF's fonts via `scripts/build_fonts.py` (International Orange brand faces, `font-display: swap`, metric-matched fallback) and precache them in `SHELL_URLS`; defer `leaflet.js` + gate boot on `DOMContentLoaded` as `initSFExplorer()` (defer **both** — the bare-defer trap).
- *Thread 0 preconnects (≤4):* `preconnect` cdnjs + the CARTO basemap tile shards (the LCP is a tile); `dns-prefetch` `data.sfgov.org`, `photon.komoot.io`, `nominatim.openstreetmap.org`.
- *Thread 5 pipeline:* `build_legislative_boundaries.py` with `STATE='06'` → same-origin cache-first `data/app/{congress,ca-senate,ca-assembly}-districts.json` (CA U.S. House 52 / State Senate 40 / State Assembly 80), simplified through the §6.7 gate — turns the ~5.7 s TIGERweb query into a ~200 ms fetch. The engine's `opts.loadDistricts` hook is already present.
- *Thread 6:* measure on **production PSI mobile** after deploy (sandbox scores are a lower bound); expect an LCP-bound frontier (~78) — don't chase past it.
- **Don't** implement the canvas renderer (§13.4) — inherit it when the reference ships it.

## Operator decisions — RESOLVED (2026-07-16)

1. ✅ **Repo created & seeded** — `ThursdaysFamous/DistrictExplorer-SF` (public), seeded byte-identical from the CHI tree (engine/gates/CI + this worksheet).
2. ✅ **Domain** — `sf.chidistricts.com` (Thread 0 points the CNAME).
3. ✅ **Brand** — International Orange (Golden Gate) direction confirmed.

*Outstanding operator item (not blocking the SF port):* the Claude GitHub App lacks repository-**creation** permission (Administration: write) — granting it would enable hands-off creation of future metro forks.
