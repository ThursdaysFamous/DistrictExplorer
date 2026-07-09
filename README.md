# Chicago District Explorer

**Click any point in Chicago — or search an address — and see every civic district that contains it, and who represents you there.**

A single-file, dependency-light web app: one `index.html`, Leaflet for the map, no build step, no framework, no server-side code. Deployed as a static site — any static host or server works.

![Chicago District Explorer showing a selected point with the Elected School Board, IL Supreme Court, and Board of Review layers on](docs/screenshot.png)

## What it answers

Pick a point. The app runs a point-in-district lookup across every layer you have toggled on and builds a "civic profile" for that location:

| Group | Layer | What you get |
|---|---|---|
| **Political** | City Ward | Ward number, alderman, office phone + address |
| | Cook County Commissioner District | District number, commissioner, office address |
| | U.S. House District | District (IL-N), representative, party, D.C. phone, website |
| | IL State Senate District | Senator, party, Springfield + district offices, ILGA page |
| | IL State House District | State representative, party, offices, ILGA page |
| | Elected School Board District | ERSB district + "6b"-style sub-district, elected board member |
| | IL Supreme Court District | District under PA 102-0011 (District 1 = Cook County) |
| | Cook County Board of Review District | District under PA 102-0012 (property-tax appeals) |
| **Public Safety** | Police District | CPD district number and name, commander, CAPS unit phone/email, station address + phone, district map link |
| | Police Station (nearest 3) | Station name, address, phone, straight-line distance |
| | Fire Station (nearest 3) | Firehouse + engine designation, distance |
| **Schools** | Elementary / Middle / High School Zone | CPS attendance-boundary school, grades, address, profile link, map pin |
| | CPS Network (K-8 / High School) | Network, chief, phone, office address |
| **Geography** | Community Area | Official community area name + number |
| | ZIP Code | ZIP code |

Every result card is independent: a layer whose data source is down shows an error with a Retry button in that card and never affects the others.

### Shareable links

The URL hash mirrors your current view (`#point=41.88250,-87.62850&layers=ward,school-board`). Copy it from the URL bar — or use the **Copy link** button on the selected-point chip — and anyone opening the link sees the same point with the same layers on.

## Running it

There is nothing to build.

```bash
# any static server works:
python3 -m http.server 8000
# then open http://localhost:8000/
```

Most layers fetch live data from public APIs at runtime, so they need an internet connection. Three layers — Elected School Board, IL Supreme Court, and Board of Review — are embedded in the page and work fully offline.

## Architecture

Stable core + pluggable layer modules, all inside `index.html`. The full contract and build history live in [`docs/BUILD_PLAYBOOK_1.md`](docs/BUILD_PLAYBOOK_1.md).

- **Core**: Leaflet map, click-to-select + Nominatim geocoder (debounced, Chicago-bounded), global `{selectedPoint, sequence}` state where a monotonic sequence counter discards stale async results, shared `sanitize` / `pointInGeometry` / `fetchJSONWithRetry` utilities, layer registry + result-card framework with per-layer failure isolation, selected-boundary highlight, URL-hash permalinks.
- **Modules**: each layer registers `{id, group, label, overlay:{load, style}, query(point, seq), render(result)}`. Overlays lazy-load on first toggle and are cached; `query` runs a local point-in-polygon test against the cached boundaries (or nearest-N haversine for station layers).
- **Honesty rules**: external strings are sanitized or rendered via `textContent`; officeholder data is never guessed — where no verifiable roster source exists, cards link to the official body instead.

### Data sources

| Source | Used for |
|---|---|
| [Chicago Data Portal](https://data.cityofchicago.org) (Socrata) | Wards + aldermen roster, fire stations, CPS zones + networks, community areas, ZIP codes |
| CPD ArcGIS (`services2.arcgis.com/t3tlzCPfmaQzSWAk`) | Police district boundaries, police station roster |
| [chicagopolice.org](https://www.chicagopolice.org) per-district pages (scraped weekly by CI) | Police district commander, CAPS unit phone/email, station address (embedded inline) |
| Cook County GIS (`gis.cookcountyil.gov/traditional/rest/services/politicalBoundary`) | Cook County Commissioner District boundaries + office roster |
| [U.S. Census TIGERweb](https://tigerweb.geo.census.gov) | Congressional, IL Senate, IL House boundaries |
| [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | U.S. House roster |
| [ilga.gov](https://www.ilga.gov) (scraped weekly by CI) | IL Senate/House member rosters (embedded inline) |
| ERSB shapefile (`ERSB_20_Sub_District_Map_FA1_SB_15`) | Elected School Board sub-districts (embedded inline) |
| PA 102-0011 / PA 102-0012 shapefiles | IL Supreme Court + Cook County Board of Review districts (embedded inline) |
| [Nominatim / OpenStreetMap](https://www.openstreetmap.org/copyright) | Address search + school-address pins |

Embedded boundary layers are topology-preserving simplifications (mapshaper) of the official shapefiles; the full-precision GeoJSON conversions are kept in `data/` and the untouched originals in `data/source/raw/`. The simplified copies agreed with full precision on 100% of 2,000 random in-city test points.

## Repository layout

```
index.html                  the entire app (styles, core, all layer modules, embedded data)
data/                       full-precision GeoJSON reference conversions
data/source/                intermediate conversions
data/source/raw/            original shapefiles / KML / KMZ / XLSX as supplied
scripts/ilga_scraper.py     scrapes ilga.gov member rosters
scripts/build_il_roster.py  rewrites the inline IL rosters in index.html from scraper output
scripts/cpd_district_scraper.py  scrapes chicagopolice.org per-district commander/contact pages
scripts/build_cpd_roster.py      rewrites the inline CPD_DISTRICT_INFO roster in index.html from scraper output
.github/workflows/          weekly roster refreshes — open a PR for human review, never commit to main
docs/BUILD_PLAYBOOK_1.md    architecture contract + per-thread build/status log
docs/OPTIMIZATION_PLAYBOOK.md  optimization & refinement playbook (measured findings + prioritized tasks)
docs/screenshot.png         README screenshot
```

## Validation

The app is exercised headlessly in CI-like conditions: the inline script passes `node --check`, the HTML parses with zero errors (parse5), all embedded datasets are checked for completeness (20 school-board districts, 59 + 118 IL legislators, 5 + 3 court/board districts), and a Playwright run in real Chromium verifies boot, map-click selection, the offline layers' point-in-district answers against known ground truth, permalink restore, and graceful per-layer degradation when data sources are unreachable.

## Not for legal or official use

Boundary and roster data come from public sources that explicitly disclaim legal precision. Always confirm district assignments and officeholders with the relevant government office before relying on them for anything official.
