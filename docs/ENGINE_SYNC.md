# Engine Sync — keeping the metro forks' shared engine identical

*This file is itself part of the shared engine: the SAME copy ships in every
metro fork. Never edit it in one fork only.*

> **SUPERSEDED IN PART — 2026-07-13.** The manual porting loop below (struck
> through) is retired by `docs/MECHANIZATION_PLAYBOOK.md` Conversion 1 in the
> Chicago repo: the engine is now distributed as a **published, hash-verified
> release artifact**. Each fork pins a version + sha256 in `engine.lock.json`;
> deploy-time assembly downloads the pinned release, verifies the hash,
> splices the ENGINE blocks between the fences, and asserts the result
> (`apply_engine.py`, then `check_engine_parity.py --against-bundle … --strict`);
> new releases fan out as gated `engine-bump.yml` PRs that also refresh the
> shared scripts. Parity is true by construction — nobody hand-ports engine
> diffs between forks anymore. The demotion condition (first automated bump
> PR merged green in NYC) fired with DistrictExplorer-NYC#23.
>
> What survives unchanged: the fences (now assembly markers), the METRO
> config seam, the block inventory, and the principle **"port the diff, not
> the prompt"** — the release artifact IS the diff, distributed mechanically.
> The "model" section below still describes how engine code is written;
> only the human porting loop is gone.

## The problem this solves

Each District Explorer metro is its own fork — separate repo, separate site,
separate data layers (see `docs/METRO_EXPANSION_PLAYBOOK.md`, which lives in
the Chicago repo). But ~60% of `index.html` is a metro-agnostic engine, and
"apply the same feature to every fork" **cannot be done by giving each fork's
coding session the same prose prompt**. A prompt is a lossy spec: the same
request produced two different "Explore other metros" footers (different
element ids, class names, label text, and list format) in Chicago and NYC.
Multiply that by every engine change and the forks stop being the same app.

**The rule: port the diff, not the prompt.**

## The model

- **Chicago (`DistrictExplorer-CHI`) is the reference implementation.** A
  region-agnostic engine change lands there first (or, if it was born in
  another fork, is backported there first). Chicago's copy of an engine block
  is canonical whenever forks disagree.
- **Engine code is fenced** so "region-agnostic" is machine-checkable, not a
  judgement call:

  ```js
  /* ==== ENGINE:BEGIN block-name ==== */
  ...byte-identical in every fork...
  /* ==== ENGINE:END block-name ==== */
  ```

  HTML regions use the same markers inside `<!-- ... -->` comments. Blocks
  cannot nest; names are unique per file.
- **Everything metro-specific that engine code needs lives in the `METRO`
  config block** near the top of the script (`/* ==== METRO:BEGIN config
  ==== */`): `THIS_METRO`, `METRO_NAME`, `METRO_BBOX`, `METRO_CENTER`,
  `PERMALINK_GATE`, `SOCRATA_HOST`, `SOCRATA_APP_TOKEN`, `REPO_ISSUES`,
  `FEEDBACK_SUBJECT`, `METRO_EXPLORERS`. An engine block may *reference* these
  names but never defines them. If a new engine block needs a per-city value,
  add a config variable — don't inline the value.
- Code outside ENGINE fences is the fork's own (layer modules, branding,
  marker art, geocoder provider, city constants). It never has to match.
- Fences pin a block's **content**, not its **position**. Where position is
  user-visible it is part of the contract too: `metro-links-html` sits between
  the source-attribution row (`.footer-sources`) and the footer-links row
  (`.footer-links`, the bug-report/source/sponsor line) in every fork. The
  parity check cannot see placement, so a port places the block at the same
  relative slot by hand — a mismatch is drift all the same (CHI and NYC
  shipped the "Explore another metro" row on opposite sides of the bug-report
  row before this rule was written down).

## The porting workflow (superseded 2026-07-13 — see banner above)

The release workflow that replaces this loop: an engine change lands in
Chicago inside the fences → a reviewed PR bumps `engine.lock.json` → the
`engine-v*` tag publishes an immutable release (`release-engine.yml`
self-checks round-trip + gates before publishing) → the fan-out opens a
gated bump PR in every sibling → each fork's deploy assembles and asserts
the pinned bytes. Fork-born engine improvements still land in Chicago first,
as reviewed PRs, then ship in the next release.

1. ~~**Make the change in the Chicago repo**, inside the relevant ENGINE
   block(s) (or add a new block). Run the gates; commit with a message that
   names the blocks touched, e.g. `engine(metro-links): …`.~~
2. ~~**Port to each sibling by handing its session the actual diff** —
   `git show <sha>` output, or the PR's `.diff` URL — with the standing
   instruction: *"Apply this engine diff verbatim. Text inside ENGINE blocks
   must be byte-identical after the port; only METRO config values may
   differ. Then run `python3 scripts/check_engine_parity.py index.html
   --against <chicago file or https://chidistricts.com/> --strict` and the
   repo's normal gates."*~~
3. ~~**Verify before pushing**: the parity check must report the ported blocks
   identical. If a hunk doesn't apply because the fork genuinely diverges
   there, that code wasn't engine — either reconcile it first or move it out
   of the fence; never "adapt" a hunk inside a fence.~~
4. ~~New-metro forks inherit the fences by construction (they start as a clone
   of Chicago), so this protocol applies from their first commit.~~ New-metro
   forks now start from a clone of Chicago and **add** the consumer half of the
   artifact model — `engine.lock.json`, `apply_engine.py`, the *consumer*
   `engine-bump.yml`, and the deploy assembly steps. (Chicago itself carries
   only the *producer* side: `release-engine.yml` + `create-engine-tag.yml`;
   it has no `engine-bump.yml`.) The artifact model applies from the fork's
   first commit.

## The tooling

- `scripts/build_engine_artifact.py` (Chicago only) — builds the
  byte-deterministic `engine.bundle.js` + `engine.manifest.json` a release
  publishes; `scripts/apply_engine.py` (every fork) — downloads, hash-verifies
  against `engine.lock.json`, and splices the pinned release between the
  fences, failing hard with nothing written on any mismatch. Both ship as
  release assets — the release is the shared scripts' distribution channel,
  and bump PRs refresh them automatically.
- `scripts/check_engine_parity.py` — extract, lint, and compare ENGINE
  blocks. Lint mode (`… index.html`) runs in every fork's
  `validate_index.py`-adjacent workflow. **Demoted from drift detector to
  post-assembly assertion**: `--against-bundle engine.manifest.json --strict`
  runs inside every deploy's assemble job, right after `apply_engine.py`,
  asserting the spliced blocks equal the downloaded bundle. The cross-fork
  compare mode (`--against <path-or-URL>`) remains for ad-hoc checks.
- `.github/workflows/engine-parity.yml` — the old scheduled cross-fork
  watcher, superseded by construction. Siblings carry no copy (NYC deleted
  its under work order 1.6 after its first clean assembled deploy; SF's
  inherited copy was removed 2026-07). **Decision (2026-07): Chicago's weekly
  run is retained indefinitely** as a deployed-site belt-and-suspenders check
  — it costs one scheduled job and catches the class of drift the assemble
  gate can't (a fork deploying outside the pipeline).

## Definition of done for fork-born engine improvements (Conversion 3)

An engine-quality improvement born in a fork (a new validator check, a
hardened loader, a factory fix) is **not done when the fork's PR merges — it
is done when the CHI release containing the back-port is tagged.** Every
fork's `validate_index.py` declares a module-level `CAPABILITIES` list
(kebab-case strings, one per check the code actually performs; CHI's copy
defines the shape). The weekly fleet-status workflow in the CHI repo diffs
each fork's list against CHI's: a capability present in a fork but absent in
CHI is a **reverse-parity WARN** on the fleet-status tracking issue, and it
stays there until the CHI release ships. The fork PR description must link
that tracking issue. Discretionary back-porting is dead; the WARN is the
debt collector.

**Releases that ship NEW blocks need sibling fence seeding first**
(learned shipping engine-v1.0.10, backlog item 11): `apply_engine.py`
fills existing fences only — it cannot decide where a brand-new block
belongs in a fork's file — so before (or immediately after) tagging such a
release, land a markers-only PR in each sibling adding the empty
`ENGINE:BEGIN/END` pair at the reference fork's placement; the bump then
splices the pinned body in. Without it the sibling's `engine-bump` run
fails with "index.html is missing ENGINE block(s) the manifest requires".
Note the re-run trap: a failed `repository_dispatch` run RE-RUNS at its
original head SHA — after fixing the fork's main, trigger a fresh fan-out
(re-run the CHI release workflow; publish self-skips, dispatch repeats)
rather than re-running the failed sibling run.

## Current ENGINE block inventory (50 in index.html + 2 in sw.js)

index.html: `app-token`, `arcgis-loader`, `arcgis-paged-loader`,
`cached-loaders`, `card-helpers`, `chamber-factory`, `cps-network-factory`,
`exports`, `extract-district-number`, `feedback`, `fetch-retry`,
`find-prop-ci`, `geocoder-search`, `geocoder-shell`, `geolocation`,
`groups`, `haversine`, `hover-explorer`, `int-field`, `layer-registry`,
`map-chrome-classes`, `map-pan-filter`, `metro-links`, `metro-links-html`,
`metro-portal`, `nearest-point-factory`, `office-helpers`, `overlay-cards`,
`permalink`, `poi-geocode`, `point-in-polygon`, `polygon-containment`,
`polygon-factory`, `probe-geometry-column`, `relationship-pinning`,
`render-helper`, `sanitize`, `school-zone-factory`, `scope-mask`,
`selection-controls`, `socrata-loader`, `socrata-point-loader`, `state`,
`styles-app`, `styles-card-v2`, `styles-core`, `styles-footer`,
`styles-hover-responsive`, `styles-markers`, `styles-sibling-result`.
(Count and list re-synced against `check_engine_parity.py` output while
adding the two card blocks — the previous list said 45 but had drifted,
missing `map-chrome-classes`, `map-pan-filter`, and `styles-markers`.)

(`card-helpers` + `styles-card-v2` are the card-system redesign surface —
docs/CARD_RENDER_API.md. Both are additive on top of `render-helper` /
`styles-app`: `renderFieldList` and the `.result-row` CSS keep serving
unmigrated call sites until the fleet-wide retirement release deletes them.)

(`geocoder-shell`/`geocoder-search`/`poi-geocode` fence the geocoder UI —
search-shell expander, result rendering, submit/debounce wiring, the
sibling-metro search fallback, and the serial >=1s POI queue. They call
three fork-defined providers, declared with each fork's unfenced GEOCODER
section: `geocodeAddress()` (city-scoped type-ahead), `geocodeUnbounded()`
(whole-coverage, feeds the sibling lookup), and `poiGeocodeRequest()`
(office-address pin lookup). Provider code stays unfenced even where the
forks' implementations currently coincide — the provider choice is
per-metro by design.)

(`layer-registry`/`overlay-cards` fence the registry, styling/highlight
machinery, and card framework; `HIGHLIGHT_CLASS`/`POI_PIN_CLASS` are METRO
config so the fork-branded CSS class names stay out of the fences. The
factory blocks keep their Chicago-born function names (`registerIlgaChamber`,
`registerCpsNetwork`) as shared engine names; per-city dataset schemas enter
through fork-side wrapper functions at the call sites — Chicago's
`registerCpsZone`, NYC's `registerNycZone` — so the fenced factories never
carry a city key list.)

sw.js: `sw-header`, `sw-handlers` — the config between them (cache name +
URL lists) is the service worker's METRO section.

(The four `styles-*` blocks fence the shared layout CSS on the neutral
`--accent`/`--accent-deep`/`--accent-warm`/`--accent-warm-deep` custom
properties; each fork's `:root` palette *values* stay fork code, as do the
fork-only style islands between the fences — see backlog item 6's leftovers.)

(`metro-portal` — the sibling-metro portal easter egg — reads per-metro
`bbox`/`emoji` fields on `METRO_EXPLORERS` entries; its card CSS is engine
too (inside `styles-app`), as are the `.sibling-result*` styles
(`styles-sibling-result`). It sits between the `feedback` fence and the
geocoder.
Entries without a bbox opt out of the portal; overlapping bboxes resolve to
the nearest bbox center; per-metro dismissals re-arm on leaving that bbox —
all so the block survives N metros unchanged. Each fork's
`validate_index.py` lints the list (see that script). The *search* trigger —
one unbounded retry of a zero-result query, hits classified into sibling
bboxes via `siblingMetroAt`, matches rendered as hand-off rows — is fenced
in `geocoder-search`, with the whole-coverage lookup behind the fork's
`geocodeUnbounded()` provider.)

(`scope-mask` shows the seam pattern for engine code that needs a per-metro
*function*, not a config constant: `drawOutOfScopeMask(loadCoverageGeometry)`
takes the fork's coverage-geometry loader as a parameter at its unfenced BOOT
call site, so the block body stays byte-identical. The geocoder blocks use
the same shape via their three fork-defined provider functions.)

Growing this inventory is encouraged: when you touch shared-looking code that
isn't fenced yet, reconcile it across forks and fence it as part of the
change.

## Reconciliation backlog (known structural drift, July 2026)

These engine-quality areas had forked between Chicago and NYC before the
fences existed. **All of them are now reconciled and fenced** — the struck
entries below record what moved where. When new shared-looking drift
appears, start a fresh numbered entry here: drift can run in *both*
directions, so reconciling means merging features, not overwriting:

1. ~~Geocoder (search box + POI geocode)~~ — **resolved July 2026**: the
   engine UI (search-shell expander, result rendering, submit/debounce
   wiring, the sibling-metro search fallback, and the serial >=1s POI
   queue + address cleaner) is fenced as `geocoder-shell` /
   `geocoder-search` / `poi-geocode`. Each fork defines three providers
   with its unfenced GEOCODER section: `geocodeAddress()` (type-ahead,
   city-scoped), `geocodeUnbounded()` (whole-coverage, for the sibling
   lookup), and `poiGeocodeRequest()` (office-address pin lookup) —
   Chicago: Photon / Photon / Nominatim; NYC: GeoSearch / Photon /
   GeoSearch. The sibling-search fallback thereby reached NYC (with the
   `styles-sibling-result` CSS and a Photon/OSM credit in its footer);
   provider code stays unfenced even where the forks currently coincide,
   because the provider choice is per-metro by design.
2. ~~Result-card / overlay styling framework + factories~~ — **resolved July
   2026**: NYC adopted Chicago's `styleForFeature` threading (a dormant seam
   there until a layer defines it), the factories were reconciled to byte
   parity and fenced (`polygon-factory`, `nearest-point-factory`,
   `school-zone-factory`, `cps-network-factory`, `chamber-factory`,
   `office-helpers`, `int-field`), and the registry + card framework fenced
   as `groups`/`layer-registry`/`overlay-cards`. The school-zone merge moved
   city dataset schemas into opts fed by fork wrappers (`registerCpsZone` /
   `registerNycZone`) and converged Chicago's card headline on NYC's more
   precise "Zoned school" copy; the chamber merge kept Chicago's ILGA copy
   via `profileLabel`/`directoryLabel`/`capitolLabel` opts at its call sites.
3. ~~Hover explorer~~ — **resolved July 2026**: NYC adopted the
   `hoverDotColor` per-feature dot override (dormant there until a layer
   defines it), `HOVER_NUMBER_KEYS`/`HOVER_NAME_KEYS` moved into each fork's
   METRO config block (they are city dataset vocabulary, per their own
   comments), and the machinery is fenced as `hover-explorer`,
   `relationship-pinning`, and `extract-district-number`.
4. ~~`LAYER_AREA_RANK`/`LAYER_ORDER` + `GROUPS`~~ — **resolved July 2026**
   with (2): `GROUPS` turned out identical and is fenced, and the consuming
   machinery (`reorderActiveLayers`, the highlight/rescale sweeps) is fenced
   inside `layer-registry`. `LAYER_AREA_RANK`'s entries stay city data
   outside the fences, as designed.
5. ~~Exports namespace~~ — **resolved July 2026**: the member list is built
   in the fenced `exports` block (`var EXPLORER_EXPORTS = {…}`); only the
   fork-branded window assignment (`window.ChiExplorer` /
   `window.NycExplorer`, twinned with each fork's `smoke_test.mjs`) stays
   fork code. The `.chi-*`/`.nyc-*` CSS class prefixes on the marker /
   region-highlight styles were the same flavor of namespace drift —
   **resolved in item 10.**
6. ~~CSS palette namespace~~ — **resolved July 2026**: both palettes renamed
   to neutral `--accent`/`--accent-deep`/`--accent-warm`/`--accent-warm-deep`
   (values stay per-fork in `:root`) and the shared layout CSS fenced as
   `styles-core`/`styles-app`/`styles-footer`/`styles-hover-responsive`.
   Still deliberately fork CSS: the `:root` palette values, `.sibling-result*`
   (rides with the geocoder, item 1), Chicago's School Location styles, and the
   fork-specific marker *art* (NYC's borough-seal, Chicago's water-taxi /
   county-seal, and each fork's palette-colored selection-marker divIcon — which
   carry no shared CSS rule, just a divIcon className). The shared marker /
   region-highlight *chrome* that used to sit unfenced beside them was
   neutralized and fenced — **item 10.**
7. ~~`sw.js`~~ — **resolved July 2026**: comments neutralized, handler logic
   fenced (`sw-header`/`sw-handlers`, METRO config between them),
   `validate_index.py` lints the fences, and `engine-parity.yml` compares
   `sw.js` alongside `index.html` in every fork.
8. ~~`validate_index.py` / `smoke_test.mjs`~~ — **resolved July 2026**, both
   directions: Chicago adopted NYC's `check_sw_lists()` and `cardText()`;
   NYC adopted Chicago's `check_metro_explorers()` (with
   `_split_object_literals`). The rest of both files is legitimately
   fork-specific config (layer rosters, ground-truth points, data floors) —
   port *checks*, not bytes, when reconciling them.
9. ~~Duplicated playbook copies~~ — **resolved July 2026**: the master
   `METRO_EXPANSION_PLAYBOOK.md` lives in the Chicago repo under `docs/`
   (sibling forks carry a pointer stub at `docs/METRO_EXPANSION_PLAYBOOK.md`
   — all doc stubs live under `docs/`), and the raw NYC research notes are
   archived at `docs/archive/METRO_EXPANSION_NYC.md` in the Chicago repo.
   The authoritative stubbed-vs-not-carried list is
   `METRO_EXPANSION_PLAYBOOK.md` §3.1 item 11.
10. ~~Marker / region-highlight class namespace~~ — **resolved July 2026**
   (the last leftover of items 5–6): the three shared map-chrome classes were
   fork-prefixed (`chi-`/`nyc-`/`sf-region-highlight`, `-poi-pin`, `-panning`)
   with their CSS sitting unfenced beside fork content, the class strings
   worksheet-driven (`highlight_class`/`poi_pin_class`), and NYC missing the
   pan-pause optimization entirely. Neutralized to `region-highlight` /
   `poi-pin` / `map-panning` and fenced three ways: the CSS trio as
   `styles-markers`, the JS constants (`HIGHLIGHT_CLASS` / `POI_PIN_CLASS` /
   `PANNING_CLASS`) as `map-chrome-classes` (promoted out of the worksheet +
   generator + schema into byte-identical engine constants — the "they carry
   the fork's palette" comment was false; the rules are identical dark
   drop-shadows), and the movestart/moveend toggle as `map-pan-filter`.
   Reconciling merged features rather than overwriting: **NYC gained the
   pan-pause drop-shadow optimization** (CSS rule + toggle JS) it had never
   adopted. Result: **48/48 ENGINE blocks byte-identical across CHI/NYC/SF**
   (strict parity, 0 drift). Each fork's `smoke_test.mjs` highlight selector
   moved to `.region-highlight`. The only still-fork-named map classes are the
   genuine marker *art* divIcons (item 6).
11. **Card-system redesign rollout (engine-v1.0.10, July 2026)** — the first
   release to ship NEW blocks through the pipeline (`card-helpers`,
   `styles-card-v2`, + 7 changed blocks; contract in
   `docs/CARD_RENDER_API.md`). Both siblings are bumped and deployed:
   **50/50 ENGINE blocks byte-identical across CHI/NYC/SF**, verified
   against the deployed sites post-rollout. The rollout surfaced three
   fork-adoption requirements, recorded in
   `docs/engine-changelog/v1.0.10.md`: seed new-block fence pairs before
   the bump (NYC #66 / SF #30), adopt the pill-aware smoke card reader
   where smoke asserts factory-card text (SF #31), and migrate role-label
   roster assertions to person-row presence (SF #32). **Residual cleared
   (July 2026):** NYC (#68) and SF (#34) migrated their fork-local cards
   onto the helper vocabulary the same week (CHI PRs #172/#173 were the
   reference), taking the fleet-wide `renderFieldList` grep to zero call
   sites. The retirement release — deleting `render-helper`, the
   `.result-row` CSS, and the factories' legacy caller-HTML branches — is
   now unblocked; it ships as a normal `engine-v*` cut when an operator
   chooses (no urgency: the legacy branches are dead code, not drift).
12. **Design-review polish + Handoff 3 (engine-v1.0.11 + v1.0.12, July
   2026)** — two follow-on releases from a design review of the redesign's
   first pass, both **changed-blocks-only** (no new fences, so no sibling
   seeding). `v1.0.11` (changed `styles-card-v2`, `card-helpers`,
   `polygon-factory`): restored the layer-colored card accent/shadow tie,
   made `<details>` expanders default closed fleet-wide (the desktop-width
   auto-open + its `cardDesktopWidth` helper removed), and added the
   `pill`/`dotColor` opts. `v1.0.12` (changed `styles-card-v2`,
   `card-helpers`, `school-zone-factory`): Handoff 3's engine surface —
   card shadow + id pill tinted with the layer color (5a),
   `cardTitleCase`/`cardGradeRange` + `renderNearestRows` `tag`/`accentColor`
   (6a/8a), and the `school-zone-factory` `titleCaseData` opt + grade-range
   identifier pill (6a). Both fanned out and merged clean (NYC #69/#70, SF
   #35/#36); the engine block count is unchanged at **50/50 byte-identical**.
   Fork adoption this round was **card-side, not seeding**: each sibling took
   a fork pass on the `v1.0.12` bump (NYC #71, SF #37) adding universal id
   pills, a compact neighborhood card, and the 8a/8b School Location chips
   rebuild — plus the now-standard pill-aware/compact-aware smoke reader
   adjustments where those cards are asserted (NYC judicial-district; SF
   `cardText` gained compact value/meta reading for the now-compact
   neighborhood). Recorded in `docs/engine-changelog/v1.0.11.md` and
   `v1.0.12.md`.
