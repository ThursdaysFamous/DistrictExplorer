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
  "chicago": ["il-supreme-court", "congress", "il-senate", "il-house", "county", "school-district-secondary", "school-district-unified", "school-district-elementary", "township", "municipality", "will-county-judicial", "will-county-board", "ccbr", "commissioner", "will-county-fire", "will-county-park", "school-board", "cps-hs-network", "cps-network", "ward-precinct", "ward", "police-beat", "police-district", "ccpsa-district-council", "community-area", "zip-code", "cps-high", "cps-middle", "will-county-precinct", "cps-elementary", "school-site", "police-station", "fire-station", "post-office", "library", "early-voting"],
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
v1.0.6).

Fleet totals: **Chicago 36 · NYC 27 · SF 16** layers.

---

## Concept coverage matrix

### Political / legislative

| Concept | Chicago | NYC | SF |
|---|---|---|---|
| U.S. House district | SHIPPED `congress` | SHIPPED `congress` | SHIPPED `congress` |
| State upper chamber | SHIPPED `il-senate` | SHIPPED `state-senate` | SHIPPED `ca-senate` |
| State lower chamber | SHIPPED `il-house` | SHIPPED `state-assembly` | SHIPPED `ca-assembly` |
| City council district | SHIPPED `ward` (50) | SHIPPED `council` (51) | SHIPPED `supervisor-district` (11; doubles as the county board — consolidated city-county) |
| Electoral precinct / ballot sub-unit | SHIPPED `ward-precinct` + `will-county-precinct` | SHIPPED `election-district` (~4,200) | SHIPPED `election-precinct` (`jg6x-23ig`, 2022 map; subOf `supervisor-district`, polling-place lookup link) |
| County legislature / commissioner | SHIPPED `commissioner` (Cook) + `will-county-board` | NO HONEST ANALOG¹ | NO HONEST ANALOG (folded into `supervisor-district`) |
| County property-tax appeals board (elected) | SHIPPED `ccbr` (commissioner roster scraped weekly from the Board's own site) | NO HONEST ANALOG² | NO HONEST ANALOG⁵ |
| State high-court electoral district | SHIPPED `il-supreme-court` | SHIPPED `judicial-district` (NY Supreme is trial-level, elected by district) | NO HONEST ANALOG⁶ |
| Trial/civil-court sub-district | SHIPPED `will-county-judicial` (12th-Circuit subcircuits) | SHIPPED `municipal-court` (28) | NO HONEST ANALOG⁶ |
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
| Fire-service boundary | SHIPPED `will-county-fire` (suburban Fire *Protection* Districts, coverage-gated) | SHIPPED `fire-battalion` (operational battalions, 49) | NO HONEST ANALOG — SFFD battalions exist but no boundary is published |
| Police / fire station points | SHIPPED `police-station` · `fire-station` | SHIPPED | SHIPPED |

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
| Park district | SHIPPED `will-county-park` (Will) · `dupage-county-park` (DuPage) | n/a | n/a |
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
- Judicial subcircuits beyond Will — PA 102-0693 shapefiles exist (Cook + collar).
- Statewide voting precincts — hardest class: 102 clerks, non-uniform, frequently
  redrawn; collar-first plan recorded (suburban Cook `k7sw-w3b8`, Lake, …).
- Collar-county boards (Lake, Kane, McHenry, Kendall) — per-county ArcGIS Hubs;
  Cook + Will + DuPage shipped (DuPage board 2026-07: boundary + coverage + a
  weekly-scraped member roster — 18 members across 6 districts + the countywide
  Chair, with published @dupagecounty.gov emails. The directory turned out to be
  static server-rendered HTML, so a plain requests+bs4 scrape sufficed — no
  Playwright).
- Park districts statewide (~350) — no statewide GIS; per-county sources. Will +
  DuPage shipped (`will-county-park`, commissioners in GIS attrs; `dupage-county-park`
  2026-07, name-only — DuPage's GIS carries no commissioner/contact fields).
- Cook County GIS layers never wired — library/park/fire/TIF/MWRD/forest-preserve tax
  districts on `gis.cookcountyil.gov` (`politicalBoundary` server), "not evaluated" in
  the original build.

---

## Per-fork inventories

### Chicago — 38 layers

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
| `will-county-judicial` | Judicial Subcircuit (12th Circuit) | political | Polygon | Will County ArcGIS | link-only | willCountyCoverage |
| `will-county-board` | Will County Board District | political | Bespoke | Will County ArcGIS | `will-county-board-members.json` (weekly CI) | willCountyCoverage |
| `dupage-county-board` | DuPage County Board District | political | Bespoke | DuPage County ArcGIS (`County_Board_Dist_new`) | `dupage-county-board-members.json` (weekly CI from dupagecounty.gov; + countywide Chair) | dupageCountyCoverage |
| `ccbr` | Cook County Board of Review District | political | Bespoke | pre-built (PA 102-0012 shapefile) | `ccbr-roster.json` (weekly CI from cookcountyboardofreview.com) | cookCountyCoverage |
| `commissioner` | Cook County Commissioner District | political | Bespoke | Cook County GIS L9 | live office join (same server) | cookCountyCoverage |
| `will-county-fire` | Fire Protection District | safety | Polygon | Will County ArcGIS | trustees in GIS attrs | willCountyCoverage |
| `will-county-park` | Park District | geography | Polygon | Will County ArcGIS | commissioners in GIS attrs | willCountyCoverage |
| `dupage-county-park` | DuPage Park District | geography | Polygon | DuPage County ArcGIS (`Park_Districts_`) | name-only (GIS carries no commissioner/contact) | dupageCountyCoverage |
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
| `will-county-precinct` | Voting Precinct | geography | Bespoke | Will County ArcGIS `Precincts_2022` | — | willCountyCoverage (subOf `township`) |
| `cps-elementary` | CPS Elementary School Zone | schools | SchoolZone | Socrata `x72b-38qv` (year-versioned) | zoned-school POI | chicagoCoverage |
| `school-site` | School Location (nearest N) | schools | Bespoke nearest | CPD-org ArcGIS `Schools` | — | chicagoCoverage |
| `police-station` | Police Station | safety | NearestPt | CPD ArcGIS stations | — | chicagoCoverage |
| `fire-station` | Fire Station | safety | NearestPt | Socrata `28km-gtjn` | — | chicagoCoverage |
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
