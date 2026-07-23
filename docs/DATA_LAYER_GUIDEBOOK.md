# Data Layer Guidebook — the fleet's layer roster, in one place

**This is the master copy, in the Chicago repo (the reference implementation), covering
every metro fork.** Sibling forks do not carry a copy — not even a stub
(`docs/METRO_EXPANSION_PLAYBOOK.md` §3.1 item 11 is the authoritative list of what is
stubbed vs. not carried). It answers, for every civic-district concept the
fleet has ever considered: which metros ship it, which metros *can't* honestly ship it and
why (recorded drop rationale), which metros simply haven't yet (parity debt), and what's
in the researched-but-unbuilt backlog.

**Maintenance contract — this file is load-bearing, not decorative:**

1. **Any PR in any fork that adds, renames, or removes a layer updates this guidebook in
   the same change** (for a fork PR, a companion CHI PR — same rule as fork-born engine
   improvements). Update the machine-readable coverage map below *and* the affected
   tables.
2. **The weekly fleet-status run enforces it**: `scripts/fleet_status.py` diffs each
   fork's live `metro-worksheet.json` layer roster against the coverage map below and
   puts a **GUIDEBOOK WARN** on the standing "Fleet status" issue on any mismatch. A
   layer that ships without a guidebook row is drift, exactly like an engine fence
   mismatch.
3. **A deliberate "we will not ship this here" is recorded, never implied.** Every
   NO HONEST ANALOG cell cites its rationale; a concept a fork lacks *without* a recorded
   rationale sits in the Parity debts table until someone either ships it or records the
   drop. (This rule exists because SF's BART-districts candidate silently evaporated
   between worksheet and launch; the debt is since paid — `bart-director` shipped
   July 2026 — but the rule stays.)

<!-- ==== GUIDEBOOK:BEGIN coverage-map ==== -->
```json
{
  "chicago": ["il-supreme-court", "congress", "il-senate", "il-house", "county", "school-district-secondary", "school-district-unified", "school-district-elementary", "township", "municipality", "judicial-subcircuit", "county-board", "ccbr", "fire-district", "dupage-county-special-police", "park-district", "library-district", "school-board", "cps-hs-network", "cps-network", "ward-precinct", "ward", "police-beat", "police-district", "ccpsa-district-council", "community-area", "zip-code", "cps-high", "cps-middle", "county-precinct", "cps-elementary", "school-site", "police-station", "fire-station", "post-office", "library", "early-voting"],
  "nyc": ["borough", "judicial-district", "borough-president", "district-attorney", "congress", "municipal-court", "state-senate", "school-district", "cec", "fire-battalion", "council", "community-district", "election-district", "state-assembly", "police-sector", "police-precinct", "zip-code", "neighborhood", "hs-zone", "ms-zone", "es-zone", "school-site", "police-station", "fire-station", "post-office", "library", "early-voting"],
  "sf": ["congress", "ca-senate", "ca-assembly", "bart-director", "election-precinct", "supervisor-district", "police-district", "zip-code", "neighborhood", "elementary-attendance-area", "police-station", "fire-station", "school-site", "post-office", "library", "early-voting"]
}
```
<!-- ==== GUIDEBOOK:END coverage-map ==== -->

The block above is the machine truth `fleet_status.py` checks — one array per metro
(keys = `metros.json` ids), each listing that fork's registered layer ids exactly as its
`metro-worksheet.json` declares them. Everything below is the human explanation.

## How to read the tables

Status key: **SHIPPED** `id` · **NO HONEST ANALOG** (recorded drop — the body doesn't
exist, isn't elected, or publishes no boundary; never faked) · **GAP** (a sibling ships
the concept, this fork doesn't, and no rationale is recorded — parity debt) · **n/a**
(structurally inapplicable, e.g. a township layer in a consolidated city).

Pattern legend (which engine factory a layer uses): **Polygon** `registerPolygonLayer` ·
**Bespoke** hand-written `registerLayer` (roster joins, shared geometry, filters) ·
**Chamber** `registerIlgaChamber` (legislative boundary + roster file) · **SchoolZone**
`registerSchoolZone` via each fork's wrapper · **CpsNetwork** `registerCpsNetwork` ·
**BoroughOffice** `registerBoroughOfficeLayer` (NYC) · **NearestPt**
`registerNearestPointLayer` (nearest-3 haversine; hover identity built in as of engine
v1.0.6) · **CountyDispatch** `registerCountyLayer` (CHI fork-level dispatcher: one
concept layer holding a per-county entry table — see
`docs/COUNTY_LAYER_CONSOLIDATION.md`; adding a county is a table entry, not a layer).

Fleet totals: **Chicago 37 · NYC 27 · SF 16** layers.

---

## Concept coverage matrix

### Political / legislative

| Concept | Chicago | NYC | SF |
|---|---|---|---|
| U.S. House district | SHIPPED `congress` | SHIPPED `congress` | SHIPPED `congress` |
| State upper chamber | SHIPPED `il-senate` | SHIPPED `state-senate` | SHIPPED `ca-senate` |
| State lower chamber | SHIPPED `il-house` | SHIPPED `state-assembly` | SHIPPED `ca-assembly` |
| City council district | SHIPPED `ward` (50) | SHIPPED `council` (51) | SHIPPED `supervisor-district` (11; doubles as the county board — consolidated city-county) |
| Electoral precinct / ballot sub-unit | SHIPPED `ward-precinct` + `county-precinct` (consolidated CountyDispatch: Will 2022 map 310 + DuPage 2024 map 600 + Lake current map 431 + Kane current map 292 + McHenry current map 223 + Kendall current map 78 w/ the county's own polling-place assignment per precinct) | SHIPPED `election-district` (~4,200) | SHIPPED `election-precinct` (`jg6x-23ig`, 2022 map; subOf `supervisor-district`, polling-place lookup link) |
| County legislature / commissioner | SHIPPED `county-board` (consolidated CountyDispatch layer: Cook Commissioner 17 + Will 11 + DuPage 6 + Lake 19 + Kane 24 + McHenry 9 + Kendall 2 districts; absorbed the former `commissioner` / `will-county-board` / `dupage-county-board` layers, old permalink ids aliased; Lake's members + contact and Kane's member names ride on those counties' own boundary GIS — no scrapers; McHenry's and Kendall's GIS are district-number-only, so their cards link the counties' member directories) | NO HONEST ANALOG¹ | NO HONEST ANALOG (folded into `supervisor-district`) |
| County property-tax appeals board (elected) | SHIPPED `ccbr` (commissioner roster scraped weekly from the Board's own site) | NO HONEST ANALOG² | NO HONEST ANALOG⁵ |
| State high-court electoral district | SHIPPED `il-supreme-court` | SHIPPED `judicial-district` (NY Supreme is trial-level, elected by district) | NO HONEST ANALOG⁶ |
| Trial/civil-court sub-district | SHIPPED `judicial-subcircuit` (consolidated CountyDispatch: Cook 20 — live from the county GIS, cross-validated against the enacted ilsenateredistricting.com shapefile, with the Circuit Court's 6 municipal districts + courthouses as a card row — + Will 12th-Circuit 5 + DuPage 18th-Circuit 7 + Lake 19th-Circuit 12 + Kane 16th-Circuit 4 (pre-built from the enacted shapefile — the county's services are permission-locked) + McHenry 22nd-Circuit 4 (pre-built — the county publishes no subcircuit service), all PA 102-0693; Kendall's 23rd Circuit received NO subcircuits under the act — structurally n/a, the layer hides there) | SHIPPED `municipal-court` (28) | NO HONEST ANALOG⁶ |
| District Attorney (districted) | n/a (Cook State's Attorney is one countywide office) | SHIPPED `district-attorney` (5 borough DAs) | NO HONEST ANALOG (one citywide DA)⁷ |
| Borough president / by-county executive | n/a | SHIPPED `borough-president` | n/a |
| Community district / board (appointed, labeled so) | n/a | SHIPPED `community-district` | n/a |
| Elected school board (districted) | SHIPPED `school-board` (ERSB) | NO HONEST ANALOG³ | NO HONEST ANALOG (at-large board)⁴ |
| Parent-elected education council | n/a | SHIPPED `cec` | n/a |
| Elected regional transit board | NO HONEST ANALOG⁸ | NO HONEST ANALOG⁸ | SHIPPED `bart-director` (9 districts, BART's own ArcGIS + hand-verified roster) |
| County clerk (surfaced on the county-identity card) | SHIPPED on `county` — all 101 clerk-authority counties via ISBE's election-authority directory (weekly CI; Peoria deliberately absent, its authority is an appointed election commission) | SHIPPED on `borough` — appointed (Appellate Division), labeled so; operator-verified `clerk` entries in `borough-officials.json` (nycourts.gov is Cloudflare-fronted, so no scraper; names only where the office's own page publishes one) | n/a⁹ |
| Early-voting / vote-center sites | SHIPPED `early-voting` (hand-curated per election; every site doubles as a secured ballot drop box) | SHIPPED `early-voting` (live NYS GIS) | SHIPPED `early-voting` (hand-curated; includes the 37 ballot drop boxes) |

Recorded drop rationales (full quotes live in the cited docs):
¹ NYC counties have no legislature — county government absorbed into the City (*Board of
Estimate v. Morris*, 1989). ² NYC's Tax Commission is appointed, citywide, no districts.
³ Mayoral control; the Panel for Educational Policy is appointed — `cec` is the honest
*parent*-elected analog and its card says so. ⁴ SF's Board of Education is elected
at-large; no district geometry exists. ⁵ SF's assessment-appeals board is appointed.
⁶ California Supreme Court is statewide; Courts of Appeal justices are appointed →
link-only at most. ⁷ SF's DA is one at-large office. ⁸ Neither sibling elects its
transit board: the Chicago Transit Board is appointed (4 mayoral + 3 gubernatorial
appointees, 70 ILCS 3605/19) and the MTA board is appointed (Governor + city/county
recommendations) — BART is the fleet's only transit board elected by district.
⁹ SF has no county-identity card to host a clerk (city and county are coterminous —
the `county` concept itself is recorded n/a) and the SF County Clerk is an appointed
city office under the City Administrator. **Future-metro recipe for this concept:**
if the fork has a county-identity layer, join the state's election-authority /
clerk directory (Illinois: ISBE's ElectionAuthorities.aspx — one postback returns
every county; other states usually have a Secretary-of-State analog) via the
weekly scraper→builder→review-PR pattern; where the authoritative source is
challenge-fronted or names aren't published, fall back to NYC's operator-verified
entries with per-office source URLs, and label appointed clerks as appointed. (¹–³:
`docs/METRO_EXPANSION_PLAYBOOK.md` Part II "NO honest NYC analog" table /
`docs/archive/METRO_EXPANSION_NYC.md` §7; ⁴–⁷: `docs/METRO_EXPANSION_SF_WORKSHEET.md`
§0 + the SF repo's worksheet drop appendix.)

### Public safety

| Concept | Chicago | NYC | SF |
|---|---|---|---|
| Police district / precinct | SHIPPED `police-district` (22) | SHIPPED `police-precinct` (78) | SHIPPED `police-district` (10) |
| Police subdivision (beat / sector) | SHIPPED `police-beat` | SHIPPED `police-sector` | NO HONEST ANALOG — SFPD publishes no patrol-beat boundary (the only "beats" dataset is Parking Control's) |
| Elected police oversight | SHIPPED `ccpsa-district-council` | NO HONEST ANALOG — CCRB is appointed/citywide; oversight story lives as labeled link rows on the precinct card | NO HONEST ANALOG — the SF Police Commission (Charter §4.109) and Department of Police Accountability are appointed (Mayor + Board of Supervisors), citywide, no districts; NYC's labeled-link-row precedent is the upgrade path if oversight links are ever wanted on the card |
| Fire-service boundary | SHIPPED `fire-district` (consolidated CountyDispatch: Cook + Will + DuPage + Lake + Kane + McHenry + Kendall suburban Fire *Protection* Districts; Cook from the Clerk's tax-agency tiling and DuPage/McHenry/Kendall name-only, Lake carries office contact, Kane names each district's chief + contact) | SHIPPED `fire-battalion` (operational battalions, 49) | NO HONEST ANALOG — SFFD battalions exist but no boundary is published |
| Township police-service tax district | SHIPPED `dupage-county-special-police` (unincorporated-area township tax districts that fund supplemental DuPage County Sheriff patrol; card links the elected Sheriff, coverage-gated) | NO HONEST ANALOG — NYC has no townships | NO HONEST ANALOG — SF has no townships |
| Police / fire station points | SHIPPED `police-station` · `fire-station` (both metro-wide from USGS National Map structures L53/L51 as of 2026-07 — replaced the city-gated CPD/CFD point sets after a completeness check: 22/22 CPD stations, 91/92 CFD houses; the CPD source still feeds the police-district card's station rows) | SHIPPED (city sources) | SHIPPED (city sources) |

Note the fire-boundary concept is not equivalent across forks: NYC maps *operational*
battalions; CHI maps suburban *taxing* districts. Chicago-proper CFD battalion/division
boundaries are a **recorded drop (verified negative, 2026-07)**: neither the Chicago Data
Portal nor CFD publishes any battalion/division boundary — the only official CFD spatial
dataset is the station-point file the `fire-station` layer already uses (`28km-gtjn`);
the boundary maps that circulate online are hobbyist reconstructions (e.g. FDmaps),
which the never-guess rule excludes as a source.

### Schools

| Concept | Chicago | NYC | SF |
|---|---|---|---|
| Elementary attendance zone | SHIPPED `cps-elementary` | SHIPPED `es-zone` | SHIPPED `elementary-attendance-area` (bespoke — card carries the lottery-tiebreaker caveat) |
| Middle / high attendance zone | SHIPPED `cps-middle` · `cps-high` | SHIPPED `ms-zone` · `hs-zone` | NO HONEST ANALOG — SFUSD publishes only elementary areas; MS is feeder-pattern, HS is citywide choice |
| School admin region / network | SHIPPED `cps-network` · `cps-hs-network` | SHIPPED `school-district` (32 CSDs) | NO HONEST ANALOG — one undivided district, no sub-regions |
| Statewide school-district identity | SHIPPED `school-district-{unified,secondary,elementary}` (TIGERweb, coverage-gated) | n/a | n/a |
| School site points | SHIPPED `school-site` | SHIPPED `school-site` | SHIPPED `school-site` |

### Geography / amenities

| Concept | Chicago | NYC | SF |
|---|---|---|---|
| Neighborhood / community area | SHIPPED `community-area` (77) | SHIPPED `neighborhood` (NTA, ~262) | SHIPPED `neighborhood` (41) |
| ZIP code | SHIPPED `zip-code` (ZCTA) | SHIPPED `zip-code` (MODZCTA) | SHIPPED `zip-code` (ZCTA) |
| County | SHIPPED `county` (statewide IL) | SHIPPED `borough` (= county) | n/a — city and county are coterminous (recorded) |
| Township / municipality | SHIPPED `township` · `municipality` (statewide IL) | n/a | n/a |
| Park district | SHIPPED `park-district` (consolidated CountyDispatch: Cook + Will + DuPage + Lake + Kane + Kendall; Cook's Clerk tiling includes the Chicago Park District — a Loop click resolves the city's own park taxing body; DuPage/Kendall name-only, Lake carries office contact, Kane names each district's board president + contact; McHenry is the one sourced county with no entry — recorded gap, it publishes facilities not district boundaries) | n/a | n/a |
| Library taxing district | SHIPPED `library-district` (CountyDispatch, born consolidated: Cook's two Clerk tax-agency tilings — 59 Public Library Districts + 54 municipal Library Funds, incl. the City of Chicago Library Fund at a Loop click — + Will 27 w/ trustees + DuPage 32 name-only + Lake 15 w/ office contact + Kane 16 w/ board president + contact + McHenry 13 name-only + Kendall 9 name-only incl. the municipal Joliet/Yorkville city-library funds its tax tiling records, the Cook-style shape) | n/a — NYC's three library systems (NYPL/BPL/QPL) are nonprofit corporations, not taxing districts | n/a — SFPL is a city department |
| Post office points | SHIPPED `post-office` (USGS National Map L38 — same national source in every fork) | SHIPPED | SHIPPED |
| Library points | SHIPPED `library` (CPL) | SHIPPED `library` (NYPL/BPL/QPL) | SHIPPED `library` (SFPL) |
| Ballot drop boxes | SHIPPED — folded into `early-voting`: Chicago's secured drop boxes (10 ILCS 5/19-6 collection sites, chicagoelections.gov/voting/drop-boxes) are hosted at the early-voting sites themselves — the 50 ward sites in the shipped 52-site file (plus the 2 downtown sites) — and the card intro says so | NO HONEST ANALOG — NYC runs no standalone drop-box program; absentee/mail ballots return by mail, at any poll site, or at BOE offices (vote.nyc / RequestBallot), all already covered by `early-voting` + the card's official links | SHIPPED (inside `early-voting`) |

---

## Parity debts (GAPs with no recorded decision — work them or record the drop)

_None open._ The original five debts were cleared in July 2026 — the outcomes now live
in the matrix above: SF shipped `election-precinct` and `bart-director`; the SF
police-oversight and NYC ballot-drop-box gaps are recorded NO HONEST ANALOG cells;
Chicago's drop boxes folded into `early-voting` (hosted at the same sites); and Chicago-proper CFD
battalions are a verified-negative drop (see the fire-boundary note). New GAP cells go
here as rows until shipped or recorded.

## Backlog — researched candidates, deliberately not (yet) built

Every entry cites where it's recorded and the blocker. When one ships, move it into the
matrix; when one is rejected, move the rationale into a NO HONEST ANALOG footnote.

**Fleet-wide**
- **Card-order conformance audit — RUN 2026-07-20** (sweep of all 79 cards against
  procedure step 2a and against each layer's source). Result: 73 of 79 conform or
  deviate with a justified reason (nearest-N lists; no-officer geography/identity
  concepts; honesty-rule link-only judicial bodies). Fixes shipped from the findings:
  - *Engine v1.0.7*: `cps-network-factory` location-before-contact row swap;
    `chamber-factory` profile-link label now follows the actual href (a directory
    fallback no longer masquerades as the member's own page).
  - *CHI `ward`*: the roster's real phone column (`ward_phone`) was never matched, so
    the Office Phone row had been silently dead — fixed; rows reordered to
    location→contact; per-ward `website` (in the roster all along) now rendered, with
    the chicago.gov lookup as fallback — ward was the only officeholder card with no
    link.
  - *NYC*: `police-precinct` latent contact-before-location order fixed; the state
    legislature scraper/builder now capture each member's official page (Open States
    `links`) so the chamber cards gain per-member links on the next weekly roster PR.
  - *SF `early-voting`*: drop-box features' `supervisorial_district` (present on
    37/38 sites) now surfaces on the card line.
  Recorded as fine-as-is (checked, no action): NYC school zones carry no school
  address/grades in the DOE datasets (verified live — `addressKeys`/`gradeKeys`
  deliberately unwired, now documented in code); CHI/SF/NYC fire-station + SF/NYC
  library sources genuinely carry no phone; SF `supervisor-district` upstream
  (`hcgx-vtsb`) carries no contact fields; congress rosters ship the D.C. office only
  (a builder-scope enrichment candidate, below). Cosmetic unfetched-or-unrendered
  fields (SF/NYC `post-office` STATE, NYC `school-site` city/zip, NYC `early-voting`
  county) trimmed or left recorded here.
- **Congress district-office enrichment** — **shipped for Chicago (2026-07).**
  `build_congress_roster.py` now joins unitedstates/congress-legislators'
  `legislators-district-offices.json` by bioguide id, so `congress-roster.json`
  carries each rep's primary district office (street + phone) and D.C. office
  alongside name/party. The CHI congress card was migrated off its bespoke block
  onto the shared `registerIlgaChamber` factory (new backward-compatible
  `districtPrefix` opt keeps the "IL-7" header), so it now surfaces a map-pinned
  District Office + D.C. Office like the ILGA chambers. The factory change ported
  byte-identical to NYC/SF. **Follow-ups:** migrate the NYC/SF congress cards onto
  the factory and enrich their builders the same way (their card layout is
  unchanged until then); and the same source family offers committee assignments
  and social media (both bioguide-keyed) as further per-member enrichment.

**San Francisco**
- _(empty — BART Director districts, formerly the strongest unbuilt candidate in the
  fleet, shipped as `bart-director` in July 2026: geometry from BART's own ArcGIS org,
  roster hand-verified against bart.gov/about/bod.)_

**New York City** (from `docs/METRO_EXPANSION_PLAYBOOK.md` Part II "Future layers")
- Surrogate's Court judges — borough geometry ready; roster unverified.
- FDNY Divisions — Socrata `68m2-uzcb` is map-type (export-route geometry only).
- NYPD sector NCO names — no structured source exists (honesty rules say wait).
- Full community-board member lists — per-borough HTML, non-uniform; only chair/manager
  are machine-readable today.
- LCGMS principal enrichment for `school-site` — needs a Socrata app token.
- Mayor / Public Advocate / Comptroller — real citywide electeds, but an at-large
  citywide polygon adds zero point-discrimination (the at-large rule: link, don't map).
- District Leader / State Committee — party-internal; recorded as "recommend never".

**Chicago / Illinois** (from `docs/STATEWIDE_EXPANSION_PLAYBOOK.md` §4/§7 +
`docs/BUILD_PLAYBOOK_1.md` §2b)
- Statewide judicial circuits (25) — blocked: the county→circuit table has no
  authoritative machine-readable source (ilga.gov 403s; illinoiscourts.gov JS-rendered);
  hand-encoding violates the never-guess rule.
- Judicial subcircuits — **complete for the metro (2026-07)**: every PA 102-0693
  subcircuit county in coverage has shipped inside `judicial-subcircuit` (Cook
  live from county GIS L5; Will/DuPage/Lake from their county GIS; Kane 16th +
  McHenry 22nd pre-built from the enacted ilsenateredistricting.com shapefile
  ZIP archived in data/source/raw/, each 100% on the 2,000-point agreement
  protocol — Kane's services are permission-locked, McHenry publishes none).
  Kendall's 23rd Circuit received NO subcircuits under PA 102-0693 (absent from
  the enacted set) — structurally n/a, not a gap.
- Statewide voting precincts — hardest class: 102 clerks, non-uniform, frequently
  redrawn; collar-first plan recorded (Will + DuPage + Lake + Kane + McHenry +
  Kendall shipped inside `county-precinct` — every collar county; suburban
  Cook `k7sw-w3b8` is the remaining metro case).
- Collar-county boards — **complete (2026-07): all seven counties shipped.**
  Cook + Will + DuPage + Lake + Kane + McHenry + Kendall (Kendall 2026-07:
  five dispatch entries from the county's own ArcGIS Enterprise
  (maps.co.kendall.il.us/server) — board 2 districts (the current line: the
  post-2020-census reapportionment kept it, so the County_Board_2010 service
  IS the current map), fire 10 FPDs / park 5 / library 9 on the county's
  parcel-derived tax-code tilings, precincts 78 with township names derived
  from the county's own layers and the county's per-precinct polling-place
  assignment joined by GlobalID) (McHenry 2026-07: five
  dispatch entries — board 9 district-number-only, 22nd-Circuit judicial
  pre-built, fire 19 and library 13 after excluding the county's own
  Z-filler/municipal/rescue-squad rows, precincts 223 — the county GIS
  carries no officeholder or contact fields, so cards link the county's own
  directories) (Kane 2026-07: the Lake recipe again — five dispatch entries, zero new layers/scrapers; the KaneCo_IL_* hosted family carries board member names, precinct board-district fields, and fire/park/library officer + office contact) (DuPage board 2026-07: boundary + coverage
  + a weekly-scraped member roster — 18 members across 6 districts + the
  countywide Chair. Lake 2026-07: the first county to land entirely as dispatch
  entries — zero new layers, and zero scrapers, because Lake's own boundary GIS
  carries each member's name/phone/official email/district page, verified
  against the county's published directory). Future counties join the
  consolidated `county-board` layer as dispatch entries, not new layers
  (`docs/COUNTY_LAYER_CONSOLIDATION.md`).
- Park districts statewide (~350) — no statewide GIS; per-county sources. Will +
  DuPage + Lake + Kane + Kendall shipped inside the consolidated
  `park-district` layer (Will: commissioners in GIS attrs; DuPage: name-only —
  its GIS carries no commissioner/contact fields; Lake: district office
  contact in GIS attrs; Kane: board president + contact; Kendall: name-only
  tax-code tiling).
  **McHenry: recorded gap (2026-07)** — the county publishes park *facilities*
  (~350 point/asset features), not park-district boundaries, so no honest
  McHenry entry is possible until the county ships a district tiling.
- Cook County GIS layers never wired — TIF/MWRD/forest-preserve tax districts on
  `gis.cookcountyil.gov` (`politicalBoundary` server), "not evaluated" in the
  original build. (The library tilings — L20 districts + L19 municipal funds —
  shipped 2026-07 as `library-district`'s Cook entry; the fire L17 and park L23
  tilings followed as Cook entries in `fire-district` / `park-district`, the park
  tiling putting the Chicago Park District on a Loop click.)

---

## Per-fork inventories

### Chicago — 37 layers

| id | label | group | pattern | source | roster / join | coverage |
|---|---|---|---|---|---|---|
| `il-supreme-court` | IL Supreme Court District | political | Polygon | pre-built (PA 102-0011 shapefile) | link-only | — |
| `congress` | U.S. House District | political | Bespoke | pre-built (TIGERweb L0, STATE=17) | `congress-roster.json` (weekly CI) | — |
| `il-senate` | IL State Senate District | political | Chamber | pre-built (TIGERweb L1) | `il-senate-members.json` (weekly CI) | — |
| `il-house` | IL State House District | political | Chamber | pre-built (TIGERweb L2) | `il-house-members.json` (weekly CI) | — |
| `county` | County | geography | Bespoke | live TIGERweb State_County | `il-county-clerks.json` (weekly CI from ISBE; Peoria deliberately absent) | — |
| `school-district-secondary` | High School District | schools | Polygon | live TIGERweb School L1 | — | outsideChicagoSchoolCoverage |
| `school-district-unified` | Unified School District | schools | Polygon | live TIGERweb School L0 | — | — |
| `school-district-elementary` | Elementary School District | schools | Polygon | live TIGERweb School L2 | — | outsideChicagoSchoolCoverage |
| `township` | Township / County Subdivision | geography | Polygon | live TIGERweb CouSub | — | — (subOf `county`) |
| `municipality` | Municipality | geography | Polygon | live TIGERweb Places | — | — |
| `judicial-subcircuit` | Judicial Subcircuit | political | CountyDispatch | Cook County GIS L5 (20 subcircuits) + L27 (municipal districts) · Will County ArcGIS · DuPage County ArcGIS (`Judicial_Subcircuits`) · Lake County ArcGIS (`LakeCounty_PoliticalBoundaries` L1) · pre-built `kane-judicial-subcircuits.json` + `mchenry-judicial-subcircuits.json` (PA 102-0693 enacted shapefile) — no Kendall entry: its 23rd Circuit received no subcircuits under the act | link-only (each card links its circuit's court; Cook adds the Municipal District + courthouse row) | OR of cook/will/dupage/lake/kane/mchenry county coverages |
| `county-board` | County Board District | political | CountyDispatch | Cook County GIS L9 · Will County ArcGIS · DuPage County ArcGIS (`County_Board_Dist_new`) · Lake County ArcGIS (`LakeCounty_PoliticalBoundaries` L0) · Kane County ArcGIS (`KaneCo_IL_County_Board` L1) · McHenry County ArcGIS (`McHenry_County_Board_Districts` L0) · Kendall County ArcGIS Enterprise (`County_Board_2010` — the CURRENT 2-district map: the post-2020-census reapportionment kept the line, Dec 2021 hearing) | Cook: live office join (same server); Will: `will-county-board-members.json` (weekly CI); DuPage: `dupage-county-board-members.json` (weekly CI; + countywide Chair); Lake: member + phone/email/district page on the boundary GIS itself (verified vs the county directory 2026-07); Kane: member names on the boundary GIS (verified incl. the 2026 D2/D9 appointments); McHenry + Kendall: district number only on the boundary GIS — the cards link each county's member directory instead of naming members (honesty rule) | OR of cook/will/dupage/lake/kane/mchenry/kendall county coverages |
| `ccbr` | Cook County Board of Review District | political | Bespoke | pre-built (PA 102-0012 shapefile) | `ccbr-roster.json` (weekly CI from cookcountyboardofreview.com) | cookCountyCoverage |
| `fire-district` | Fire Protection District | safety | CountyDispatch | Cook County GIS L17 (Clerk fire tax-agency tiling) · Will County ArcGIS · DuPage County ArcGIS (`Fire_Protection_Districts_`) · Lake County ArcGIS (`LakeCounty_TaxDistricts` L4) · Kane County ArcGIS (`KaneCo_IL_Districts_Fire` L1, IDOR-coded districts only) · McHenry County ArcGIS (`Fire_Districts` L0, 19 after the loader excludes the 8 'Z NO FIRE DISTRICT' fillers, the municipal Crystal Lake city-fire row, and the overlapping Marengo rescue-squad district — a 70 ILCS 3105 ambulance body, not a fire protection district) · Kendall County ArcGIS Enterprise (`Fire_Protection_Districts` L0 — the parcel-derived tax-code tiling, 10 FPDs after excluding the municipal 'CITY OF JOLIET FIRE DISTRICT' rows; hairline no-result gaps at unparceled slivers) | Cook: name-only; Will: trustees in GIS attrs; DuPage: name-only; Lake: district office contact in GIS attrs; Kane: chief + office contact in GIS attrs; McHenry + Kendall: name-only | OR of cook/will/dupage/lake/kane/mchenry/kendall county coverages |
| `dupage-county-special-police` | DuPage Special Police District | safety | Polygon | DuPage County ArcGIS (`Special_Police_Districts_`, "Real Estate Tax Code polygons") | link-only (elected DuPage County Sheriff; unincorporated-area police-tax district) | dupageCountyCoverage |
| `park-district` | Park District | geography | CountyDispatch | Cook County GIS L23 (Clerk park tax-agency tiling, incl. the Chicago Park District) · Will County ArcGIS · DuPage County ArcGIS (`Park_Districts_`) · Lake County ArcGIS (`LakeCounty_TaxDistricts` L11) · Kane County ArcGIS (`KaneCo_IL_Districts_Park` L1) · Kendall County ArcGIS Enterprise (`Park_Districts` L0 tax-code tiling, 5 genuine districts — Fox Valley/Joliet/Oswegoland/Plainfield/Sandwich) — McHenry: recorded gap, publishes facilities not district boundaries | Cook: name-only; Will: commissioners in GIS attrs; DuPage: name-only; Lake: district office contact in GIS attrs; Kane: board president + office contact in GIS attrs; Kendall: name-only | OR of cook/will/dupage/lake/kane/kendall county coverages |
| `library-district` | Library District | geography | CountyDispatch | Cook County GIS L20 (Library Tax District) + L19 (Library Fund) · Will County ArcGIS (`Library_District`) · DuPage County ArcGIS (`Library_Districts_`) · Lake County ArcGIS (`LakeCounty_TaxDistricts` L8) · Kane County ArcGIS (`KaneCo_IL_Districts_Library` L1) · McHenry County ArcGIS (`Library_Districts` L0, 13 after the loader excludes 6 'Z_None' fillers + the lone municipal Crystal Lake city row) · Kendall County ArcGIS Enterprise (`Library_Districts` L0 tax-code tiling, 9 bodies incl. the municipal Joliet/Yorkville city-library funds — Kendall's tiling records EVERY library taxing body, the Cook-style complete shape, so its municipal rows stay) | Cook: agency name + a Type row distinguishing district vs municipal fund; Will: trustees in GIS attrs (sparse); DuPage: name-only; Lake: district office contact in GIS attrs; Kane: board president + office contact in GIS attrs; McHenry + Kendall: name-only | OR of cook/will/dupage/lake/kane/mchenry/kendall county coverages |
| `school-board` | Elected School Board District | political | Bespoke | pre-built (ERSB SB15 shapefile) | `school-board-members.json` (hand-curated) | chicagoCoverage |
| `cps-hs-network` | CPS Network (High School) | schools | CpsNetwork | Socrata `aupu-jt2g` | chief in dataset props | chicagoCoverage |
| `cps-network` | CPS Network (K-8) | schools | CpsNetwork | Socrata `pnta-kuqa` | chief in dataset props | chicagoCoverage |
| `ward-precinct` | Ward Precinct | political | Bespoke | Socrata `i8fv-xe4b` | — | chicagoCoverage (subOf `ward`) |
| `ward` | City Ward | political | Bespoke | Socrata `p293-wvbd` | live Socrata `htai-wnw4` join | chicagoCoverage |
| `police-beat` | Police Beat | safety | Bespoke | CPD ArcGIS | — | chicagoCoverage (subOf `police-district`) |
| `police-district` | Police District | safety | Bespoke | CPD ArcGIS | `cpd-district-info.json` (weekly CI, Playwright) | chicagoCoverage |
| `ccpsa-district-council` | CCPSA District Council | safety | Bespoke | shares `police-district` geometry | `ccpsa-district-councils.json` (weekly CI) | chicagoCoverage |
| `community-area` | Community Area | geography | Polygon | Socrata `igwz-8jzy` | — | chicagoCoverage |
| `zip-code` | ZIP Code | geography | Polygon | live TIGERweb ZCTA | — | — |
| `cps-high` | CPS High School Zone | schools | SchoolZone | Socrata `xg7c-d8rm` (year-versioned) | zoned-school POI | chicagoCoverage |
| `cps-middle` | CPS Middle School Zone | schools | SchoolZone | Socrata `fyff-53xy` (year-versioned) | zoned-school POI | chicagoCoverage |
| `county-precinct` | Voting Precinct | geography | CountyDispatch | Will County ArcGIS `Precincts_2022` · DuPage County ArcGIS `Precincts_2024` (current 600-precinct map) · Lake County ArcGIS (`LakeCounty_PoliticalBoundaries` L7, 431) · Kane County ArcGIS (`KaneCo_IL_ElectionsPrecincts` L1, 292) · McHenry County ArcGIS (`Precincts` L0, 223) · Kendall County ArcGIS Enterprise (`Voting_Precincts_and_Polling_Places` L1 `status='A'`, 78 — township names derived at load from the county's own townships layer, the assigned polling place joined by GlobalID from L0) | County Board district via spatial join (Kane: carried on the features); Kendall also shows the county's own polling-place assignment; each card links its county clerk | OR of will/dupage/lake/kane/mchenry/kendall county coverages (subOf `township`) |
| `cps-elementary` | CPS Elementary School Zone | schools | SchoolZone | Socrata `x72b-38qv` (year-versioned) | zoned-school POI | chicagoCoverage |
| `school-site` | School Location (nearest N) | schools | Bespoke nearest | CPD-org ArcGIS `Schools` | — | chicagoCoverage |
| `police-station` | Police Station | safety | NearestPt | USGS National Map structures L53 (metro bbox) | — | — (metro-wide) |
| `fire-station` | Fire Station | safety | NearestPt | USGS National Map structures L51 (metro bbox) | — | — (metro-wide) |
| `post-office` | Post Office | geography | NearestPt | USGS National Map structures L38 | — | — |
| `library` | Library | geography | NearestPt | Socrata `x8fc-8rcq` | — | chicagoCoverage |
| `early-voting` | Early Voting Site | political | NearestPt | hand-curated `early-voting-sites.json` (per election; sites double as the secured drop boxes; WATCH.md row) | — | chicagoCoverage |

### NYC — 27 layers

| id | label | group | pattern | source | roster / join |
|---|---|---|---|---|---|
| `borough` | Borough / County | geography | Bespoke | pre-built (offline anchor) | `borough-officials.json` clerk entries (operator-verified; appointed, labeled) |
| `judicial-district` | NY Supreme Court Judicial District | political | Polygon | pre-built (counties → districts derivation) | link-only |
| `borough-president` | Borough President | political | BoroughOffice | shares `borough` geometry | `borough-officials.json` (operator-maintained) |
| `district-attorney` | District Attorney | political | BoroughOffice | shares `borough` geometry | same roster |
| `congress` | U.S. House District | political | Chamber | pre-built (TIGERweb L0, STATE=36) | `congress-roster.json` (weekly CI) |
| `municipal-court` | Civil Court District | political | Polygon | pre-built (offline anchor) | link-only |
| `state-senate` | NY State Senate District | political | Chamber | pre-built (TIGERweb L1) | `ny-senate-members.json` (weekly CI; API keys) |
| `school-district` | Community School District | schools | Polygon | Socrata `8ugf-3d8u` | superintendent link-only |
| `cec` | Community Education Council | schools | Bespoke | shares `school-district` geometry | `cec-members.json` (weekly CI, placeholder until scrape lands) |
| `fire-battalion` | FDNY Battalion | safety | Polygon | DCP ArcGIS | — |
| `council` | City Council District | political | Bespoke | Socrata `872g-cjhh` | `council-members.json` (weekly CI) |
| `community-district` | Community District / Board | political | Bespoke | Socrata `5crt-au7u` | live Socrata `ruf7-3wgc` join (chair/manager, labeled appointed) |
| `election-district` | Election District | political | Bespoke | DCP ArcGIS (paged, ~4,200) | — (subOf `state-assembly`) |
| `state-assembly` | NY State Assembly District | political | Chamber | pre-built (TIGERweb L2) | `ny-assembly-members.json` (weekly CI) |
| `police-sector` | NYPD Sector | safety | Bespoke | Socrata `5rqd-h5ci` | — (subOf `police-precinct`) |
| `police-precinct` | NYPD Precinct | safety | Bespoke | Socrata `y76i-bdw7` | `nypd-precinct-info.json` (weekly CI) |
| `zip-code` | ZIP Code (MODZCTA) | geography | Polygon | Socrata `pri4-ifjk` | — |
| `neighborhood` | Neighborhood (NTA 2020) | geography | Polygon | Socrata `9nt8-h7nd` | — |
| `hs-zone` / `ms-zone` / `es-zone` | School Zones | schools | SchoolZone | Socrata `ruu9-egea` / `t26j-jbq7` / `cmjf-yawu` (year-versioned) | zoned-school POI |
| `school-site` | School (nearest 3) | schools | NearestPt | NYSED ArcGIS L2/3/4 (paged) | — |
| `police-station` | Police Station | safety | NearestPt | Socrata `ji82-xba5` (FacDB) | — |
| `fire-station` | Firehouse | safety | NearestPt | Socrata `hc8x-tcnd` | — |
| `post-office` | Post Office | geography | NearestPt | USGS National Map L38 | — |
| `library` | Library | geography | NearestPt | Socrata `feuq-due4` (all 3 systems) | — |
| `early-voting` | Early Voting Site | political | NearestPt | live NYS GIS elections service L1 | — |

### SF — 16 layers

| id | label | group | pattern | source | roster / join |
|---|---|---|---|---|---|
| `congress` | U.S. House District | political | Chamber | pre-built SF-clipped (TIGERweb L0, STATE=06) | `congress-roster.json` (weekly CI) |
| `ca-senate` | CA State Senate District | political | Chamber | pre-built SF-clipped (TIGERweb L1) | `ca-senate-members.json` (weekly CI, OpenStates) |
| `ca-assembly` | CA State Assembly District | political | Chamber | pre-built SF-clipped (TIGERweb L2) | `ca-assembly-members.json` (weekly CI) |
| `bart-director` | BART Director District | political | Bespoke | BART's own ArcGIS org (Board_of_Directors_District_Boundary, 9 districts) | `bart-directors.json` (hand-verified per election cycle; WATCH.md rows) |
| `election-precinct` | Election Precinct | political | Bespoke | Socrata `jg6x-23ig` (2022 map, 514 precincts) | — (subOf `supervisor-district`; polling-place lookup link) |
| `supervisor-district` | Supervisor District | political | Bespoke | pre-built (DataSF `hcgx-vtsb`, water-trimmed; offline anchor) | `sf-supervisor-members.json` (weekly CI) |
| `police-district` | Police District | safety | Polygon | pre-built (DataSF `d4vc-q76h`; offline anchor) | — |
| `zip-code` | ZIP Code | geography | Polygon | live TIGERweb ZCTA | — |
| `neighborhood` | Neighborhood | geography | Polygon | pre-built (DataSF `j2bu-swwd`; offline anchor) | — |
| `elementary-attendance-area` | Elementary Attendance Area | schools | Bespoke | Socrata `e6tr-sxwg` (year-versioned) | — (lottery caveat on card) |
| `police-station` | Police Station | safety | NearestPt | Socrata `rwdu-9wb2` | — |
| `fire-station` | Fire Station | safety | NearestPt | Socrata `nc68-ngbr` (City Facilities filter) | — |
| `school-site` | School Location | schools | NearestPt | Socrata `7e7j-59qk` | — |
| `post-office` | Post Office | geography | NearestPt | USGS National Map L38 | — |
| `library` | Library | geography | NearestPt | Socrata `fhhu-wqa7` (support facility excluded) | — |
| `early-voting` | Voting Center & Ballot Drop-off | political | NearestPt | hand-curated `early-voting-sites.json` (incl. 37 drop boxes; WATCH.md row) | — |

---

## Adding or changing a layer — the procedure

1. Consult the matrix first: if a sibling already ships the concept, reuse its recorded
   pattern and source-hunting notes (`docs/METRO_EXPANSION_PLAYBOOK.md` §2/§6); if a
   sibling recorded a drop, check whether the rationale applies to your metro before
   re-researching.
2. Build per the playbook (worksheet entry → regenerate → registration → source manifest
   → docs), and **in the same change** update: the coverage-map JSON above, the fork's
   inventory table, the concept matrix row (add the row if the concept is new
   fleet-wide), and — if the layer resolves a Parity debt or Backlog entry — move that
   entry accordingly.
2a. **Card content order (fleet convention):** the result card leads with the layer name
   (card header), then the district identifier, then — wherever a verifiable source
   exists — the representative(s)/officeholder(s), the office location, contact info,
   and a link to more detail, in that order. Deviate only where the concept demands it
   (nearest-N lists, layers with no elected officer) — and when identity/location/contact
   data exists in the layer's source but isn't on the card yet, record the gap in the
   Backlog rather than shipping it silently.
3. If you decide a concept **won't** ship in a metro, add the NO HONEST ANALOG footnote
   with the rationale and source of truth. Silence is the only wrong answer.
4. The weekly fleet-status run cross-checks the coverage map against every fork's live
   worksheet; a mismatch WARNs on the "Fleet status" issue until the guidebook and the
   fleet agree.
