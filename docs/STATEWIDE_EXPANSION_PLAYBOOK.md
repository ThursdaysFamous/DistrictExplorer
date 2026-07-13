# Statewide Expansion Playbook — from one metro to a whole state (Illinois)

Status: **strategy + decision record, deliberately gated. Do not build yet.** Owner: CHI (reference
implementation). Cross-refs: `docs/MECHANIZATION_PLAYBOOK.md` (the gate that governs *when* this may
ship), `docs/METRO_EXPANSION_PLAYBOOK.md` (the per-fork recipe this extends), `docs/ENGINE_SYNC.md`
(why the one engine change here must ride the artifact pipeline).

This document answers a recurring user request — *"can you do this for the whole state?"* — most
recently and concretely from a **Will County township political-organization leader** who keeps a
large paper township map to look up precincts, state-legislative, Congress, and county-board
districts, falls back to a "clunky" county GIS explorer for judicial, park, municipal, and
school districts, and needs *every* district a person sits in, in one place, to build candidate
packets and volunteer walk lists — **across townships and counties**, not just one city.

It is written in the project's own spirit (`MECHANIZATION_PLAYBOOK.md` preamble): *"a playbook that
is merely well-written has changed nothing."* So this is not a green light. It is the honest map of
what already works, the one real architectural gap, why the engine-distribution timeline is the
correct gating factor, and the phased recipe to run **after** the gate opens.

**Anchoring convention (inherited from `METRO_EXPANSION_PLAYBOOK.md`):** code is located by **grep
anchor** — a symbol name or distinctive substring — never by line number. Every `code-anchor` below
is a string you `grep -n` for in `index.html`.

---

## 0. The hard precondition (read this first)

**A statewide deployment is, mechanically, a new metro** — a new fork, a new domain
(`il.chidistricts.com`), a new dataset set. It is therefore blocked by the project's own **metro-#3
gate**: *"no new metro is provisioned until all three conversions' checks have EACH failed once"*
(`MECHANIZATION_PLAYBOOK.md`, grep `The metro-#3 gate`). Conversion 1 (engine-as-artifact) is done
(grep `CONVERSION 1 DONE`); Conversions 2 (per-fork config generated from `metro-worksheet.json`) and
3 (reverse-parity fleet status) are still *in progress* — their `Prose demoted when:` conditions have
not fired. Until they do, **nothing in Phase 1+ here may be built**, and the prose in this document is
authoritative only as a plan, not a warrant.

"After the engine work is fully complete" therefore has a precise meaning: **all three mechanization
drills red, the gate open.** §5 explains why that is not incidental timing but a genuine dependency.

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
Widen those four config values and the four layers above light up statewide with zero engine change.

Everything else the requester listed — **precincts, county board, judicial *circuit* districts, park
districts, municipalities, non-CPS school districts, townships** — is absent or Chicago/Cook-only
today. That is the real work, and §3–§4 size it.

---

## 2. The core architectural gap — coverage-aware dispatch

**Statewide Illinois is not "just another metro fork," and the mechanization effort does not, by
itself, deliver it.** Mechanization makes *spinning up another same-shaped fork* cheap and
hash-verified — necessary groundwork, but orthogonal to statewide coverage. A U.S. state has ~102
counties, ~1,426 townships, ~1,300 municipalities, and hundreds of school and park districts; you
cannot fork per-locality.

The one capability statewide actually needs is **coverage-aware layer dispatch.** Today the dispatch
loop (grep `runAllActiveLayerQueries`) runs *every* toggled layer for *every* point with no coverage
gate; a containment miss returns falsy and `runLayerQuery` renders the generic empty card (grep
`setCardEmpty` → "No result for this point."). Statewide, a Will County click would produce a **wall
of Chicago-only "No result" cards** — the 16 city layers and 2 Cook-only layers all reporting nothing,
indistinguishable from a real "no district here." That is not a coverage tool; it is noise.

The app needs layers to **declare a coverage scope** and only surface where the point is actually in
their jurisdiction — plus honest per-layer copy for the distinct case of "in coverage, but
structurally no district here."

---

## 3. Recommended architecture — additive `mod.coverage` capability

Model it on the existing **`subOf`** precedent (grep `subOf`): an optional per-layer field the engine
interprets to change behavior (the ward→`ward-precinct` nest/cascade). Layers that don't set it behave
**byte-identically to today** — which is exactly what makes this a safe ENGINE change and leaves the
NYC fork untouched until it opts in.

Add two optional, additive fields, read in `runLayerQuery` *above* `mod.query`, plus one new card
state:

- **`mod.coverage`** — a scope test (a coverage geometry, or a predicate keyed on the resolved
  county). If the point is outside it, render a new `setCardOutOfScope(mod)` ("Covers the City of
  Chicago only") and **skip the query and the overlay fetch entirely**. Because the gate sits in the
  shared dispatch, it covers both factory layers and hand-written `registerLayer` layers uniformly,
  and it eliminates the wasted boundary fetch a Cook-only layer would otherwise do statewide.
- **`mod.emptyLabel`** — an honest per-layer empty sentence for a real *in-coverage* null, replacing
  the generic `setCardEmpty` string where a miss is structural (a township layer at a Chicago point:
  "Chicago abolished its townships in 1902").

Three UI states, cleanly separated:

| Situation | Will County example | Chicago example | Mechanism |
|---|---|---|---|
| In coverage, has a district | Township = Homer Township; unit school district named | Ward named | `setCardResult` |
| In coverage, structurally none | — | Township: "Chicago has no townships" | `mod.emptyLabel` |
| Out of data coverage | Ward / CPD / CPS: "Covers Chicago only" | — | `mod.coverage` → `setCardOutOfScope` |

**The locality resolver needs no new service.** The engine's shared containment test (grep
`findFeatureContaining`) already answers "which county / township / municipality / school district
applies" as containment against the corresponding statewide TIGER layer. Resolve the point's **county
first** (one `STATE='17'` fetch); its FIPS becomes the key for anything indexed by county — the
county→circuit table (§4), and later which county-clerk precinct/board source to consult (Phase 2).

**Scope of the change:** ~30–50 lines inside the fenced dispatch/cards block, plus the factories (grep
`registerPolygonLayer`, `registerIlgaChamber`) threading `opts.coverage` / `opts.emptyLabel` through.
De-risk the *wording* first with a throwaway fork-only sentinel layer (a hand-written `query` that
returns a truthy out-of-scope object and a bespoke `render`) — that needs no engine edit and settles
copy before the real, additive engine fields ship.

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
families must be coverage-gated and honest, never claimed statewide.

---

## 5. Why this is sequenced *after* the engine work — not incidental timing

1. **The metro-#3 gate is a hard block.** A statewide deployment provisioned as a new fork/domain is a
   new metro; the gate forbids it until all three mechanization drills have fired
   (`MECHANIZATION_PLAYBOOK.md`, grep `The metro-#3 gate`). Conversions 2 and 3 have not drilled red.
2. **Conversion 2 will template exactly the keys this feature adds.** The worksheet schema already
   owns `metro_bbox`, `permalink_gate`, and the per-layer `layers: {id,label,group,area_rank}` list
   (grep `Worksheet schema`). Coverage-aware dispatch adds new per-layer config (each layer's
   `coverage`; the statewide bbox; the county→circuit table). Add those keys *before*
   `generate_metro_files.py` exists and you hand-port config into NYC — the exact drift Conversion 2
   was created to kill (its evidence base is that config/doc drift already happened at N=2).
3. **Conversion 3 is the safety net for a fork-born capability.** If coverage-aware dispatch is
   prototyped in the statewide effort, reverse-parity (grep `reverse-parity`) is what guarantees it
   lands back in CHI/engine within a cycle and is *measured* via the `CAPABILITIES` diff, not left to
   discretion.
4. **The artifact pipeline is how the feature reaches NYC.** `mod.coverage` lives in the fenced
   dispatch/factory blocks that `scripts/check_engine_parity.py` requires byte-identical and
   `engine.lock.json` pins by sha. Post-Conversion-1 it ships as a hash-verified release and fans out
   via an automated bump PR. Building it as engine *after* the pipeline's own drills are green means
   you are not debugging the feature and the distribution mechanism at once — *"machinery you have
   never seen fail is machinery you do not know works."*

**Net sequence:** finish Conversions 2 & 3 (all three drills red → gate opens) → ship `mod.coverage`
as an engine release → it fans out to NYC (byte-identical; NYC declares no coverage) → provision the
statewide deployment consuming the new engine plus a statewide worksheet.

---

## 6. Recommended shape — statewide deployment, collar-counties-first

Three options were weighed:

- **(A) Statewide single deployment** (`il.chidistricts.com`) + coverage-aware dispatch — all 102
  counties get the FREE identity layers; Chicago/Cook layers coverage-gated; per-county layers grow
  outward.
- **(B) Regional "Chicago + collar counties" fork** — simpler and bounded, but fails the requester the
  moment her coordination reaches downstate; a *footprint*, not an *architecture*.
- **(C) More per-metro city forks** — rejected: townships, county boards, and circuits are not city
  concepts, and the requester is not in a city core.

**Recommendation: A as the container, seeded with B's footprint.** One `METRO = "Illinois"` fork whose
statewide TIGER identity layers cover all 102 counties on day one; the expensive per-county layers
(precincts, county-board districts, park districts, subcircuits) are realized first across the
collar-county region (Cook / DuPage / Lake / Will / Kane / McHenry / Kendall — the requester's
operating area) and grow outward. Coverage-aware dispatch is exactly what lets one deployment carry
deep-in-some-places coverage **honestly**: a downstate user sees county / township / municipality /
school-district / circuit + state-leg / Congress and honest "Covers {region} only" cards for the deep
layers; a collar-county user sees the full stack. This matches the stated cross-county need without
pretending we have 102 counties of precincts on launch day.

---

## 7. Phased roadmap

- **Phase 0 — exploit what works + widen the shell (fork-only, no engine change, gate-safe).** On a
  preview branch, apply the config-only shell changes: `METRO_BBOX` / `METRO_CENTER` / `PERMALINK_GATE`
  → statewide, the map zoom floor (grep `setView(METRO_CENTER`), the Photon center bias, `METRO_NAME` →
  "Illinois", and swap the scope-mask loader (grep `drawOutOfScopeMask`) to a 102-county `STATE='17'`
  loader so the engine dissolve (grep `coverageOutlineRings`) washes only genuinely-outside-Illinois.
  Result: the four already-statewide layers resolve for any IL point. Prototype the two new card-state
  copy strings here (throwaway sentinel layer). This is buildable as a demo even pre-gate because it
  provisions no new metro and touches no engine bytes.
- **Phase 1 — statewide identity layers, no per-county work (post-gate).** Land the additive
  `mod.coverage` / `mod.emptyLabel` / `setCardOutOfScope` engine capability via the engine-release
  train, then add the FREE TIGER layers (county, township/MCD, municipality/place, school districts
  ×3) + the derived judicial circuit, likely under a new "Local Government" group alongside the
  existing groups (grep `GROUPS`). Declare `coverage` on the 16 Chicago-only and 2 Cook-only layers and
  `emptyLabel` where a null is structural. Official-body links only — **no invented township / mayor /
  board names.** This takes a Will County resident from four cards to the bulk of the requester's list.
- **Phase 2 — per-county / harder sources, honest partial coverage.** Grow from the collar counties:
  county-board districts (per-county Hubs; Cook already live via grep `commissioner`), precincts (Cook
  `k7sw-w3b8`, Lake, …), subcircuits (PA 102-0693 shapefiles on the static `il-supreme-court` pattern,
  grep `registerPolygonLayer`), park districts. Each newly-sourced county flips its coverage card from
  "Covers {others} only" to a real result — coverage-aware dispatch makes incremental rollout legible
  instead of a bug.

---

## 8. Biggest risks

- **Precinct sourcing (highest).** No current statewide GIS; 102 clerks, non-uniform, frequently
  redrawn; Census VTD is stale. Mitigation: strictly coverage-gate per county, never claim statewide,
  start collar. Do not let it block Phases 0–1.
- **Officeholder rosters vs the honesty rules.** 1,426 townships + ~1,300 municipalities + 102 county
  boards have no uniform, verifiable, keyed roster. Naming them would violate the never-guess rule.
  Mitigation: identity + official-body link only (the existing `il-supreme-court` / `ccbr` link
  precedent); reserve live rosters for genuinely keyed sources (Cook Commissioner today; ISBE / ILGA
  where clean). This aligns with `MECHANIZATION_PLAYBOOK.md`'s *"Deliberately NOT mechanized"* honesty
  rules — they stay prose + the smoke test's failure-isolation assertion.
- **Engine-parity friction.** `mod.coverage` must be strictly additive so `check_engine_parity.py`
  stays green and the pinned-hash pipeline holds; a non-additive change breaks NYC's deploy.
- **Fork-vs-single-deployment.** Getting it wrong yields either an unmaintainable 102-county monolith
  or a fleet of forks that never serves a cross-county user. §6's recommendation is the mitigation.

---

## 9. When the gate opens — worksheet + verification

A statewide fork extends the Conversion-2 worksheet (`metro-worksheet.json`, grep `Worksheet schema`),
not a hand-edited config block:

- `metro_bbox` / `metro_center` / `permalink_gate` → statewide envelope; `this_metro` = "illinois".
- `layers[]` gains the new identity layers with `area_rank` and the new "Local Government" group; each
  Chicago/Cook layer gains a `coverage` declaration.
- `anchors[]` gains ≥1 collar-county ground-truth point (e.g. a Homer Glen address → its township,
  county, unit school district, judicial circuit) **and** the negative no-district point the schema
  already requires — the honest out-of-coverage case is now first-class test data.
- `data_sources[]` gains the TIGERweb service rows (county, county-subdivision, place, school) with
  vintage.

**Verification (mirrors `smoke_test.mjs` ground-truth style):**

- *Phase 0:* serve locally, drop a Will County point, confirm the four statewide layers resolve with
  correct rep names; confirm the scope-mask washes only outside IL; run `python3
  scripts/validate_index.py index.html` and the Playwright boot gate.
- *`mod.coverage` capability:* assert a layer with no `coverage` is behaviorally byte-identical (parity
  check green, other forks' `engine.lock.json` sha unchanged); a Chicago-only layer shows
  `setCardOutOfScope` outside Chicago and a normal result inside.
- *Phase 1 layers:* ground-truth a known point against each new TIGER layer; verify every card links to
  the correct official body and names no unverified officeholder.
- *Deployment:* only after all three mechanization drills are red and the engine release carrying
  `mod.coverage` has fanned out to NYC with parity green.

---

## 10. Cross-references

- `docs/MECHANIZATION_PLAYBOOK.md` — the metro-#3 gate, the Conversion-2 worksheet schema, Conversion-3
  reverse-parity. **Governs when this may ship.**
- `docs/METRO_EXPANSION_PLAYBOOK.md` — the per-fork provisioning recipe a statewide worksheet extends;
  the *"Scope, honestly"* boundary this effort pushes against.
- `docs/ENGINE_SYNC.md` — the fence protocol and artifact pipeline the `mod.coverage` capability must
  ride through additively.
- `scripts/check_engine_parity.py` + `engine.lock.json` — byte-identical enforcement + pinned sha.
- `index.html` — dispatch/cards engine (grep `runAllActiveLayerQueries`, `runLayerQuery`,
  `setCardEmpty`) where `mod.coverage` / `setCardOutOfScope` land; `METRO:BEGIN config`; the fork shell
  (grep `setView(METRO_CENTER`, `photon.komoot.io`, `nominatim.openstreetmap.org`,
  `drawOutOfScopeMask`); factories (grep `registerPolygonLayer`, `registerIlgaChamber`); the TIGER
  loader (grep `TIGERweb/Legislative`).
