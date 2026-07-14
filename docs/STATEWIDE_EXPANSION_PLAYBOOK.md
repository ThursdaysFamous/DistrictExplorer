# Statewide Expansion Playbook — from one metro to a whole state (Illinois)

Status: **strategy + decision record; a staged build, not a blocked one.** Owner: CHI (reference
implementation). Cross-refs: `docs/MECHANIZATION_PLAYBOOK.md` (the metro-#3 gate — and why the
in-place approach sidesteps it), `docs/METRO_EXPANSION_PLAYBOOK.md` (the per-fork recipe this
borrows from), `docs/ENGINE_SYNC.md` (the artifact pipeline the one engine change rides).

This document maps what it would take to extend the app from Chicago to **statewide Illinois** — the
natural next ask for a single-city civic tool. The need is concrete: outside the city, finding which
precinct, township, county-board, judicial, park, municipal, or school district an address falls in
means chasing disparate, often-clunky county GIS tools, with nowhere that shows those local districts
alongside the state-legislative and Congressional ones. Statewide coverage would report *every*
district containing a point — and who represents you there — for any address in Illinois, **across
townships and counties**, not just one city.

It is written in the project's own spirit (`MECHANIZATION_PLAYBOOK.md` preamble): *"a playbook that
is merely well-written has changed nothing."* So this is the honest map: what already works, the one
real architectural gap, the **decided approach** (expand the existing app in place, rebranded to
Illinois, hiding layers that don't apply to the selected point), and the staged recipe.

**Anchoring convention (inherited from `METRO_EXPANSION_PLAYBOOK.md`):** code is located by **grep
anchor** — a symbol name or distinctive substring — never by line number. Every `code-anchor` below
is a string you `grep -n` for in `index.html`.

---

## 0. What's gated and what isn't (read this first)

The earlier framing of this effort assumed a **separate statewide fork** (`il.chidistricts.com`),
which *is* mechanically a new metro and therefore blocked by the **metro-#3 gate**: *"no new metro is
provisioned until all three conversions' checks have EACH failed once"* (`MECHANIZATION_PLAYBOOK.md`,
grep `The metro-#3 gate`).

**The decided approach is different: expand the existing Chicago app in place, rebranded to Illinois
— not a new fork or domain.** That changes the gating picture materially:

- **Growing the existing app is not "provisioning a new metro,"** so the metro-#3 gate does not apply.
- **Conversion 1 (engine-as-artifact) is DONE** (grep `CONVERSION 1 DONE`), so the hash-verified
  release pipeline that carries any engine change to the NYC fork is already proven and available.

So the two buildable tracks (§5) — the relevance-hiding engine capability, and the statewide shell +
"free" identity layers — are **not blocked by the mechanization gate.** What genuinely paces the work
is practical, not procedural:

1. **Per-county data availability** — the real long tail (precincts, county boards, park districts);
   see §4.
2. **Careful, additive evolution of the live reference app** — every engine change stays strictly
   additive so Chicago behaves byte-identically and NYC is untouched until it opts in.
3. A **recommendation, not a requirement**: let Conversion 2 (config generated from
   `metro-worksheet.json`) land around the same time, so CHI's *growing* config is generated and
   drift-checked rather than hand-maintained (§5).

Honest bottom line: the in-place decision unblocks the timeline. This is a staged build gated by data
and care, not by the metro-#3 machinery.

---

## 1. The reframe — four layers already work statewide today

Of the app's registered layers, four are already **state-scoped, not Chicago-scoped**, and resolve
correctly for *any* Illinois point right now — a Will County township included:

| Layer id | Geometry source | Roster | Statewide today? |
|---|---|---|---|
| `congress` | TIGERweb Legislative MapServer layer 0, `STATE='17'` | `congress-roster.json` (all 17 IL seats) | ✅ |
| `il-senate` | TIGERweb layer 1 (SLDU), `STATE='17'` | `il-senate-members.json` (all 59) | ✅ |
| `il-house` | TIGERweb layer 2 (SLDL), `STATE='17'` | `il-house-members.json` (all 118) | ✅ |
| `il-supreme-court` | static `il-supreme-court-districts.json` (PA 102-0011, 5 statewide districts) | static members | ✅ |

The only thing stopping a downstate user from reaching them is the **input shell**, all of which is
**fork config, not engine**: the Photon type-ahead (grep `photon.komoot.io`) and the Nominatim POI
geocoder (grep `nominatim.openstreetmap.org`) are hard-bounded to `METRO_BBOX`; the map opens on
`METRO_CENTER` (grep `setView(METRO_CENTER`); and incoming permalinks are clamped to `PERMALINK_GATE`.
Widen those config values and the four layers above light up statewide with zero engine change.

Everything else — **precincts, county board, judicial *circuit* districts, park
districts, municipalities, non-CPS school districts, townships** — is absent or Chicago/Cook-only
today. That is the real work, and §3–§4 size it.

---

## 2. The core architectural gap — relevance-aware dispatch

**Statewide Illinois is not "just another metro fork."** A U.S. state has ~102 counties, ~1,426
townships, ~1,300 municipalities, and hundreds of school and park districts; you cannot fork
per-locality.

The one capability statewide actually needs is **relevance-aware layer dispatch.** Today the dispatch
loop (grep `runAllActiveLayerQueries`) runs *every* toggled layer for *every* point with no coverage
gate; a containment miss returns falsy and `runLayerQuery` renders the generic empty card (grep
`setCardEmpty` → "No result for this point."). Statewide, a Will County click would produce a **wall
of Chicago-only "No result" cards** — the 16 city layers and 2 Cook-only layers all reporting nothing,
indistinguishable from a real "no district here." That is not a coverage tool; it is noise.

The app needs each layer to **declare where it applies** and, for a point outside that area, to
**hide the layer entirely** (its toggle, its card, and its map overlay) rather than show an empty or
"not here" card. A downstate user should simply see the districts that *do* apply to them. The
distinct case of "in coverage, but structurally no district here" still gets an honest one-line
explanation (§3).

---

## 3. Recommended architecture — additive `mod.coverage`, presented as hiding

Model it on the existing **`subOf`** precedent (grep `subOf`): an optional per-layer field the engine
interprets to change behavior (the ward→`ward-precinct` nest/cascade). Layers that don't set it behave
**byte-identically to today** — which is exactly what makes this a safe ENGINE change and leaves the
NYC fork untouched until it opts in.

**Every primitive the "hide irrelevant layers" idea needs already exists in the app:**

- **The relevance test.** `maybeUseWaterTaxiMarker` already does an inside-Chicago test via
  `findFeatureContaining(loadCommunityAreas(), point)`, and the citywide outline
  (`loadSchoolBoardDistricts`, the ERSB tiling) is already fetched at boot for `drawOutOfScopeMask`.
  So "is this layer relevant to this point?" reuses `findFeatureContaining` against an already-loaded
  polygon set. (For the 2 Cook-only layers, eagerly load the local `ccbr-districts.json`, or use
  IL-Supreme District 1 which is exactly Cook County.)
- **The hide-a-toggle primitive.** `updateSubLayerVisibility` already sets
  `layerRuntime[id].block.hidden` to show/hide the Ward→Precinct sub-toggle from runtime state. The
  primitive works on any layer (top-level too); generalize its trigger from "`subOf` parent is on" to
  "point is in this layer's area."
- **The single choke point.** `setSelectedPoint` → `runAllActiveLayerQueries` → `runLayerQuery` is the
  sole path shared by map-click, address search, keyboard-select, *and* permalink restore. Relevance
  is computed once here.

**Two optional, additive per-layer fields:**

- **`mod.coverage`** — a relevance test (a coverage geometry, or a predicate keyed on the resolved
  county). When the point is outside it, the dispatch **hides the layer's toggle block, suppresses its
  card, and skips its query + overlay fetch** — but does **not** mutate `state.layersOn` (see the
  permalink note below). Because the gate sits in the shared dispatch, it covers factory layers and
  hand-written `registerLayer` layers uniformly.
- **`mod.emptyLabel`** — an honest per-layer empty sentence for a real *in-coverage* null, replacing
  the generic `setCardEmpty` string where a miss is structural (a township layer at a Chicago point:
  "Chicago abolished its townships in 1902").

Three UI states, cleanly separated:

| Situation | Will County example | Chicago example | Mechanism |
|---|---|---|---|
| In coverage, has a district | Township = Homer Township; unit school district named | Ward named | `setCardResult` |
| In coverage, structurally none | — | Township: "Chicago has no townships" | `mod.emptyLabel` |
| Not applicable here | Ward / CPD / CPS: layer **hidden** | — | `mod.coverage` → hide toggle + card + overlay |

**The one real design decision — permalink stability (decided: hide-only).** `syncUrlHash` encodes
active layers as `layers=<ids>`. If relevance *cascaded a layer off* (mutating `state.layersOn`), the
share-URL would silently drop it. So the gate **hides** the layer (the `.hidden` block + a relevance
check in `runLayerQuery` that suppresses the card/overlay) while leaving `state.layersOn` intact — the
layer stays in the URL and reappears the moment the point re-enters its area. `PERMALINK_GATE` already
spans Will / Cook / the collar counties, so shared links across the metro already survive; widening it
to the state envelope extends that.

**The locality resolver needs no new service.** `findFeatureContaining` already answers "which county
/ township / municipality / school district applies" as containment against the corresponding
statewide TIGER layer. Resolve the point's **county first** (one `STATE='17'` fetch); its FIPS becomes
the key for anything indexed by county — the county→circuit table (§4), and later which county-clerk
precinct/board source to consult (Phase 2).

**Scope of the change:** ~30–50 lines inside the fenced dispatch/cards block (the relevance gate + a
generalized `updateSubLayerVisibility`), plus the factories (grep `registerPolygonLayer`,
`registerIlgaChamber`) threading `opts.coverage` / `opts.emptyLabel` through. It is a **generic**
capability — useful to any metro — so it is worth landing as a clean engine feature, not a
Chicago-specific hack.

---

## 4. The statewide-Illinois data landscape

**FREE** = one statewide GIS source lights up all 102 counties via `STATE='17'`, exactly as the
legislative layers already do (grep `TIGERweb/Legislative`). **DERIVE** = computed from a FREE layer
plus a lookup table. **PER-COUNTY** = no uniform source; 102 clerk/assessor origins → honest partial
coverage only.

| Family | Cost | Source | Officeholders |
|---|---|---|---|
| County boundaries | **FREE** | TIGERweb `State_County/MapServer/1` | link to county |
| Townships / MCDs | **FREE** | TIGERweb `Places_CouSub_ConCity_SubMCD/MapServer/1` (1,426 townships) | **no uniform roster** → link to Township Officials of IL |
| Municipalities / places | **FREE** | same service, layer 4 (Incorporated Places), 5 (CDPs) | link to municipality |
| School districts (non-CPS) | **FREE** | TIGERweb `School/MapServer` 0/1/2 (Unified / Secondary / Elementary) | ISBE directory → link |
| Judicial circuits (25) | **DERIVE** | county→circuit table from 705 ILCS 35, dissolved over the FREE county layer | link to illinoiscourts.gov |
| Judicial subcircuits | PER-SOURCE | PA 102-0693 shapefiles (ilsenateredistricting.com); Cook + single-county collar circuits | link to illinoiscourts.gov |
| County boards / districts | **PER-COUNTY** | per-county ArcGIS Hubs; Cook Commissioner already live in-app (grep `commissioner`) | Cook joins live; else link |
| Precincts | **PER-COUNTY (hardest)** | no current statewide GIS; county clerks (Cook `k7sw-w3b8`, Lake, …); Census 2020 VTD is decennial/stale | geography only |
| Park districts | **PER-COUNTY** | no statewide GIS; per-county Hubs; ~350+ districts | link to district |

**The Phase-1 "free" set** — county, township/MCD, municipality/place, the three school-district
layers, and the derived judicial circuit — is 5–6 new statewide layers, all "which district am I in?"
with official-body links and **zero invented officeholders**, all on the TIGERweb `STATE='17'` pattern
the app already ships.

**Field-name caveat:** the existing TIGER loader assumes a `STATE` field. The `Places_CouSub`,
`School`, and `State_County` services follow the same TIGERweb schema, but confirm `STATE` vs
`STATEFP` and the district-key field per service at implementation — the app already carries the tools
for exactly this (grep `extractDistrictNumber` with its name-field fallback, `findPropCI`,
`probeGeometryColumn`).

This is precisely the boundary `METRO_EXPANSION_PLAYBOOK.md` warns about under *"Scope, honestly"*:
large metros with digitized district geography are in the box; *"small towns may have no digitized
local boundaries at all."* Statewide pushes directly into that zone — which is why the PER-COUNTY
families must be relevance-gated (hidden where unsourced) and honest, never claimed statewide.

---

## 5. Sequencing — two decoupled tracks

The build splits into two tracks that ship independently:

### Track 1 — relevance-hiding (a generic engine capability)
Add `mod.coverage` + `mod.emptyLabel` + the hide-only dispatch gate (§3). It benefits Chicago and NYC
regardless of statewide (any metro has layers with different footprints), so it is a legitimate engine
improvement on its own. It is **CHI-born**, strictly additive, and rides the **DONE Conversion-1
artifact pipeline** (grep `CONVERSION 1 DONE`): published as a hash-verified release from CHI and
fanned out to NYC via an automated bump PR (`MECHANIZATION_PLAYBOOK.md`, grep `repository_dispatch`).
NYC stays byte-identical because it declares no coverage. **Not gated** — the pipeline that distributes
it is already proven.

### Track 2 — statewide-IL work on CHI (fork-owned, in place)
Widen the shell (`METRO_BBOX` / `METRO_CENTER` / `PERMALINK_GATE` / `METRO_NAME` + the statewide
scope-mask), rebrand to Illinois, declare `coverage` on the 16 Chicago-only + 2 Cook-only layers, then
add the FREE TIGER identity layers (Phase 1) and grow the per-county long tail (Phase 2). This is
CHI's own METRO config + layer modules (fork-owned surface, not engine) — **not** a new-metro
provision, so **not gated** by metro-#3.

### Complementary mechanization (recommended, not required)
**Conversion 2** (config generated from `metro-worksheet.json`, grep `Worksheet schema`) is worth
landing around the same time: CHI's config is *growing* (statewide bbox, ~6 new layers, `coverage`
declarations on ~18 layers), and generating + drift-checking it beats hand-maintaining it. This is a
quality win, not a blocker. **Conversion 3** (reverse-parity) is not a dependency here, since the
capability is CHI-born and flows outward through Conversion 1, not back-ported.

**Net:** build Track 1 now via the proven pipeline → build Track 2's shell + free identity layers as
CHI fork work → stage the per-county tail by data availability → fold in Conversion 2 for clean,
generated config as CHI's worksheet grows.

---

## 6. Decided shape — expand chidistricts.com in place, rebranded to Illinois

Three options were weighed:

- **(A) Expand the existing app in place**, rebranded to Illinois (e.g. "Illinois District Explorer"),
  with relevance-hiding — **chosen.**
- **(B) A separate statewide deployment** (`il.chidistricts.com`) — rejected: it is a new metro (trips
  the metro-#3 gate), duplicates deployment/CI/service-worker surface, and fragments the cross-county
  user experience for no benefit the in-place path lacks.
- **(C) More per-metro city forks** — rejected: townships, county boards, and circuits are not city
  concepts, and the statewide user is typically not in a city core.

**Why in place wins.** The target user coordinates *across* townships and counties, and needs **one
map** that answers township / county-board / circuit / municipality / school-district *and* keeps
state-leg / Congress, across many counties at once. Expanding the existing app delivers exactly that,
reuses everything already built (deployment, CI, service worker, the four already-statewide layers),
and — because it is not a new metro — sidesteps the metro-#3 gate.

**Rollout: all 102 counties on day one for the free layers; collar-counties-first for the deep ones.**
The statewide TIGER identity layers cover the whole state immediately. The expensive per-county layers
(precincts, county-board districts, park districts, subcircuits) are realized first across the
collar-county region (Cook / DuPage / Lake / Will / Kane / McHenry / Kendall) and grow outward. Relevance-hiding is what makes deep-in-some-places coverage
**honest and legible**: a downstate user simply sees county / township / municipality /
school-district / circuit + state-leg / Congress, with the not-yet-sourced deep layers *hidden* rather
than shown as broken empty cards; a collar-county user sees the full stack.

**Branding is the one open product decision.** A "Chicago District Explorer" at `chidistricts.com`
covering all of Illinois is a name/scope mismatch. Options: evolve the app name to "Illinois District
Explorer" while keeping `chidistricts.com` as the URL; add a state-neutral domain; or keep the Chicago
identity and accept the mismatch. This is a product call, not a technical blocker.

---

## 7. Phased roadmap

- **Phase 0 — widen the shell + exploit what works (fork-only, no engine change).** Apply the
  config-only shell changes: `METRO_BBOX` / `METRO_CENTER` / `PERMALINK_GATE` → statewide, the map zoom
  floor (grep `setView(METRO_CENTER`), the Photon center bias, `METRO_NAME` → "Illinois", and swap the
  scope-mask loader (grep `drawOutOfScopeMask`) to a 102-county `STATE='17'` loader so the engine
  dissolve (grep `coverageOutlineRings`) washes only genuinely-outside-Illinois. Result: the four
  already-statewide layers resolve for any IL point. Ships as a preview immediately (no engine bytes).
- **Phase 1 — relevance-hiding + statewide identity layers.** Land Track 1 (the `mod.coverage`
  hide-only capability) via the engine-release pipeline; declare `coverage` on the 16 Chicago-only + 2
  Cook-only layers (they hide outside their areas) and `emptyLabel` where a null is structural. Add the
  FREE TIGER layers (county, township/MCD, municipality/place, school districts ×3) + the derived
  judicial circuit, likely under a new "Local Government" group alongside the existing groups (grep
  `GROUPS`). Official-body links only — **no invented township / mayor / board names.** This takes a
  Will County resident from four cards to the bulk of the local-district list, with a clean UI that hides
  the Chicago-only layers.
- **Phase 2 — per-county / harder sources, collar-first.** Grow from the collar counties: county-board
  districts (per-county Hubs; Cook already live via grep `commissioner`), precincts (Cook `k7sw-w3b8`,
  Lake, …), subcircuits (PA 102-0693 shapefiles on the static `il-supreme-court` pattern, grep
  `registerPolygonLayer`), park districts. Each newly-sourced county un-hides its layer for that
  county — relevance-hiding makes incremental, partial rollout legible instead of a bug.

---

## 8. Biggest risks

- **Precinct sourcing (highest).** No current statewide GIS; 102 clerks, non-uniform, frequently
  redrawn; Census VTD is stale. Mitigation: relevance-gate per county (hidden where unsourced), never
  claim statewide, start collar. Do not let it block Phases 0–1.
- **Officeholder rosters vs the honesty rules.** 1,426 townships + ~1,300 municipalities + 102 county
  boards have no uniform, verifiable, keyed roster. Naming them would violate the never-guess rule.
  Mitigation: identity + official-body link only (the existing `il-supreme-court` / `ccbr` link
  precedent); reserve live rosters for genuinely keyed sources (Cook Commissioner today; ISBE / ILGA
  where clean). This aligns with `MECHANIZATION_PLAYBOOK.md`'s *"Deliberately NOT mechanized"* honesty
  rules — they stay prose + the smoke test's failure-isolation assertion.
- **Engine-parity friction.** The relevance-hiding capability must be strictly additive so
  `check_engine_parity.py` stays green and the pinned-hash pipeline holds; a non-additive change breaks
  NYC's deploy. A layer with no `coverage` must behave byte-identically to today.
- **Evolving the live reference app.** Because this expands the *running* Chicago site rather than a
  fresh fork, every step must preserve the Chicago experience exactly (Chicago points still show all
  Chicago layers). Ship behind the existing gates (`validate_index.py`, `smoke_test.mjs`) and keep the
  first statewide rollout on a preview branch until the Chicago ground-truth assertions still pass.

---

## 9. Verification

Mirror the existing `smoke_test.mjs` ground-truth style:

- **Phase 0:** serve locally, drop a Will County point (e.g. a Homer Glen address), confirm the four
  statewide layers resolve with correct rep names; confirm the scope-mask washes only outside IL; run
  `python3 scripts/validate_index.py index.html` and the Playwright boot gate. Confirm a **Chicago**
  point is unchanged.
- **Relevance-hiding capability:** assert a layer with no `coverage` is behaviorally byte-identical
  (parity check green, other forks' `engine.lock.json` sha unchanged); assert a Chicago-only layer is
  **hidden** (toggle + card + overlay absent, but still present in the `layers=` permalink) outside
  Chicago and shows a normal result inside; assert re-entering Chicago un-hides it.
- **Phase 1 layers:** ground-truth a known point against each new TIGER layer (county, township,
  municipality, school district, circuit); verify every card links to the correct official body and
  names no unverified officeholder.
- **Rebrand:** confirm no stale "Chicago"-only copy remains in the masthead, title, meta description,
  and geolocation strings once `METRO_NAME` flips (grep the pre-rename brand strings per
  `METRO_EXPANSION_PLAYBOOK.md`'s branding rows).

---

## 10. Cross-references

- `docs/MECHANIZATION_PLAYBOOK.md` — the metro-#3 gate (which the in-place path sidesteps), the
  Conversion-1 artifact pipeline (DONE — carries Track 1 to NYC), and the Conversion-2 worksheet schema
  (recommended for CHI's growing config).
- `docs/METRO_EXPANSION_PLAYBOOK.md` — the per-fork provisioning recipe this borrows shell/branding
  steps from; the *"Scope, honestly"* boundary this effort pushes against.
- `docs/ENGINE_SYNC.md` — the fence protocol + artifact pipeline the relevance-hiding capability must
  ride through additively.
- `scripts/check_engine_parity.py` + `engine.lock.json` — byte-identical enforcement + pinned sha.
- `index.html` — dispatch/cards engine (grep `runAllActiveLayerQueries`, `runLayerQuery`,
  `setCardEmpty`) where the relevance gate lands; the hide primitive (grep `updateSubLayerVisibility`,
  `layerRuntime`); the relevance test (grep `findFeatureContaining`, `maybeUseWaterTaxiMarker`,
  `loadSchoolBoardDistricts`); permalink (grep `syncUrlHash`, `state.layersOn`, `PERMALINK_GATE`); the
  fork shell (grep `setView(METRO_CENTER`, `photon.komoot.io`, `nominatim.openstreetmap.org`,
  `drawOutOfScopeMask`); factories (grep `registerPolygonLayer`, `registerIlgaChamber`); the TIGER
  loader (grep `TIGERweb/Legislative`).
