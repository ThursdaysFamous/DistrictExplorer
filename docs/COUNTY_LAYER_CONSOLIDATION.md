# County-Layer Consolidation — one concept layer per district type, dispatched by county

Status: **decided + fully migrated (July 2026): `county-board`, then `judicial-subcircuit`,
`fire-district`, `park-district`, `county-precinct` — every multi-county concept now
county-dispatched (42 → 36 layers) — plus `library-district`, the first concept born
consolidated (37 layers).**
Owner: CHI (fork-level — no engine change). Cross-refs: `docs/STATEWIDE_EXPANSION_PLAYBOOK.md`
(the relevance-hiding capability this builds on, §3; the collar-first rollout, §7),
`docs/DATA_LAYER_GUIDEBOOK.md` (the inventory this reshapes), `docs/ENGINE_SYNC.md` (why
fork-level matters).

## The problem

The collar-county expansion has been shipping one layer per **concept × county**: Will and
DuPage each got their own board / judicial / fire / park / precinct layers, and Cook's
commissioner layer predates them. The per-county layers of one concept are **mutually
exclusive by construction** — a point is in exactly one county, and every one of these
layers is coverage-gated to its county — so the extra toggles buy the user nothing, and the
math turns hostile as counties are added:

| | per-county layers | consolidated |
|---|---|---|
| 3 counties today (board concept) | 3 toggles | 1 toggle |
| 7 collar counties × 5 concepts | ~35 toggles | 5 toggles |
| statewide (102 counties) | impossible | still 5 toggles |

Consolidation is UI-level, not source-level: there is no statewide GIS for county boards,
fire districts, park districts, or precincts (`STATEWIDE_EXPANSION_PLAYBOOK.md` §4
PER-COUNTY), so each county keeps its own loader, query, and card — one **layer** simply
dispatches among them.

## The decision

**One layer per concept, holding a per-county dispatch table.** Implemented as a fork-level
helper, `registerCountyLayer` (grep it in `index.html`), which composes per-county entries
and registers **one** module through the existing engine contract — `registerLayer` already
accepts arbitrary `query` / `render` / `coverage` / `hoverName` / `hoverOfficial` /
`pointOfInterest` callbacks, so **no ENGINE fence is touched** and nothing rides the release
pipeline. This is the same shape as NYC's `registerBoroughOfficeLayer` (one layer, data
picked by borough) applied to counties.

Each dispatch entry: `{ key, coverage, loadGeometry, query, render, hoverName,
hoverOfficial?, pointOfInterest? }` — i.e. exactly the per-county pieces the separate layers
already had, moved into a table row. **Adding a county becomes adding a table entry, not a
layer** — no new toggle, no worksheet/guidebook/count churn beyond the entry's source rows.

## Decided semantics

- **Coverage = OR of the entries' coverages**, checked in table order (each is a cached
  same-origin outline test). Outside every sourced county the layer hides exactly as the
  separate layers did; a throwing check falls through to the next entry, and an
  all-throwing miss propagates so the engine's fail-open applies.
- **Query dispatches by containment, not by coverage**: try each county's own geometry in
  order; the first containment hit wins (they cannot overlap). A county whose source is
  down is skipped while other counties still resolve; if no county matched and one errored,
  the error propagates — so a point in the downed county gets the honest error card +
  Retry, never a lying "No result".
- **Overlay = union of all sourced counties' boundaries**, each feature wrapped (not
  mutated — the per-county GeoJSON caches are shared with other consumers, e.g. the
  precinct cards' board spatial join) and stamped `dxCounty` for hover dispatch. The engine
  contract draws one static overlay per layer, and the union is also better UX: toggling
  the concept shows it across the whole metro. A county whose source fails at load time
  drops out of the overlay while the others draw; **known tradeoff:** the engine caches
  `rt.geojson` for the session (P11), so a partial union persists until reload — same class
  as the recorded relevance-hiding carve-outs, and the query path (which refetches per
  county with Retry) is unaffected.
- **Hover-roster prefetch is all-or-retry.** The engine caches a *resolved* hover roster
  for the session (`rt.roster` is never refetched once truthy), so the composite
  `hoverOfficial.load` deliberately **rejects when any county's load fails** rather than
  resolving with a permanent hole: the engine swallows the rejection and the next
  toggle-on retries, the already-succeeded counties resolving instantly from their cached
  loaders. Until all counties load, hover omits officeholder names (district identity
  still shows); click cards fetch per query and are unaffected.
- **One style per concept layer** (a concept has one legend identity), and a **generic
  toggle label** ("County Board District"). County identity moves into the card: a `Body`
  row right after the district number ("Cook County Board of Commissioners" / "Will County
  Board" / "DuPage County Board") keeps the card order convention (identity → people →
  contact → link) and removes the need for the old "DuPage …"-prefixed labels that only
  existed to dodge toggle-name collisions.
- **Permalinks keep working.** Retired ids (`commissioner`, `will-county-board`,
  `dupage-county-board`) are rewritten to the consolidated id by a fork-side alias shim
  that runs before the boot-time `applyStateFromHash` parse (unknown ids in `layers=` are
  otherwise silently dropped). The alias map lives next to the consolidated registration;
  every future consolidation appends its retired ids there. (A hashchange mid-session with
  an old id still degrades silently — boot-time links are the shipping surface.)

## What does NOT consolidate

- **`ccbr`** — a different elected body (property-tax appeals), not Cook's county
  legislature. Concepts consolidate; bodies don't merge.
- **`ward-precinct`** — same *concept* as the county precincts but a different parent
  (`subOf ward`, not township) and a different electoral system; it stays a city layer.
- **Single-county concepts** (`dupage-county-special-police`) — consolidation starts when a
  **second** county ships the concept; until then a dedicated layer is simpler and honest.

## Migration plan

1. **`county-board`** (DONE — the prototype): absorbs `commissioner` (Cook, live
   GIS office join), `will-county-board` (weekly-scraped roster), `dupage-county-board`
   (weekly-scraped roster + countywide Chair). Card content per county is preserved
   verbatim, plus the new `Body` row. Roster scrapers, builders, CI workflows, and
   `data/app/` files are untouched.
2. **`judicial-subcircuit` / `fire-district` / `park-district` / `county-precinct`**
   (DONE — second pass): the three polygon-factory pairs consolidate via the
   `polygonCountyEntry` adapter (a registerPolygonLayer-style spec — loader + declarative
   fields — as a dispatch entry, so their cards moved without rewriting); the precinct
   pair's bespoke entries carry their board-district spatial join and county-clerk links,
   with `subOf`/`onToggle` passed through at the CONCEPT level (the township outline-only
   handoff is identical in every county). Every consolidated card names its county
   somewhere fixed: Body row (board), Court row (judicial), County row (fire/park), the
   clerk link (precinct). The retired "DuPage …"-prefixed labels are gone with the
   toggle-collision that motivated them.
2b. **New concepts launch consolidated** — proven by **`library-district` (2026-07)**,
   the first concept born on the dispatcher with no per-county predecessors: Cook
   (the Clerk's two tax-agency tilings, distinguishing independent Public Library
   Districts from municipal Library Funds — a Chicago click resolves the City of
   Chicago Library Fund), Will (trustees in GIS attrs), DuPage (name-only), and
   Lake (office contact in GIS attrs) as day-one entries of one toggle.
2c. **Existing concepts absorb new counties as entries** — Cook joined `fire-district`
   (40, the Clerk's fire tax-agency tiling) and `park-district` (99, incl. the
   Chicago Park District — a Loop click now resolves the city's own park taxing
   body) in 2026-07: two loaders + two `polygonCountyEntry` rows, no other surface
   changed.
3. **Future counties ship as dispatch entries from day one** — proven by **Lake
   (DONE, 2026-07)**: the first county to land with **zero new layers and zero
   scrapers** — five `lake` entries (board 19 / judicial 12 / fire 22 / park 23 /
   precinct 431) plus one TIGER outline for `lakeCountyCoverage`. Lake's own
   boundary GIS carries the board members' names/phone/official email/district
   page (verified against the county's published directory) and each fire/park
   district's office contact, so the honesty rules are satisfied by the county's
   own data with no roster pipeline at all. Kane followed in the same change-shape (2026-07): five entries from the county's
   public `KaneCo_IL_*` hosted family — board members and even each precinct's
   board district ride the features; its 16th-Circuit judicial entry honestly
   waits on a public source (only permission-locked proxies exist). McHenry and
   Kendall follow the same recipe; a county-specific layer is only ever created for a concept no
   consolidated layer covers yet (as `dupage-county-special-police` remains
   today).

## Verification

Per migration: the standard gates (`generate_metro_files.py --check`, `validate_index.py`,
`check_engine_parity.py` — must stay byte-green, this is fork code), the Playwright smoke
test (registration count, coverage-hide, permalink stability — plus an alias-shim
assertion: an old-id `layers=` link must light the consolidated toggle), and a live
dispatch harness against the real county GIS endpoints asserting (a) each test point
matches exactly one county's geometry and (b) known ground-truth districts still resolve
(Loop → Cook commissioner district; Wheaton → DuPage board 4; a Will point → its board
district + roster entry).
