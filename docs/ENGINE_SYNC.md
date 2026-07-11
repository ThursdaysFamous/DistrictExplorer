# Engine Sync — keeping the metro forks' shared engine identical

*This file is itself part of the shared engine: the SAME copy ships in every
metro fork. Never edit it in one fork only.*

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

## The porting workflow

1. **Make the change in the Chicago repo**, inside the relevant ENGINE
   block(s) (or add a new block). Run the gates; commit with a message that
   names the blocks touched, e.g. `engine(metro-links): …`.
2. **Port to each sibling by handing its session the actual diff** —
   `git show <sha>` output, or the PR's `.diff` URL — with the standing
   instruction: *"Apply this engine diff verbatim. Text inside ENGINE blocks
   must be byte-identical after the port; only METRO config values may
   differ. Then run `python3 scripts/check_engine_parity.py index.html
   --against <chicago file or https://chidistricts.com/> --strict` and the
   repo's normal gates."*
3. **Verify before pushing**: the parity check must report the ported blocks
   identical. If a hunk doesn't apply because the fork genuinely diverges
   there, that code wasn't engine — either reconcile it first or move it out
   of the fence; never "adapt" a hunk inside a fence.
4. New-metro forks inherit the fences by construction (they start as a clone
   of Chicago), so this protocol applies from their first commit.

## The tooling

- `scripts/check_engine_parity.py` — extract, lint, and compare ENGINE
  blocks. Lint mode (`… index.html`) runs in every fork's
  `validate_index.py`-adjacent workflow; compare mode
  (`--against <path-or-URL>`) diffs this fork's blocks against a sibling's
  working tree or deployed site. Drift is a WARN to be ported by a human,
  matching the repo-wide "surface for a human, don't auto-apply" convention.
- `.github/workflows/engine-parity.yml` — the scheduled watcher. It runs in
  the **Chicago repo only** (one tracking issue, in the canonical repo,
  instead of N mirrored ones); other forks carry the same workflow file with
  `workflow_dispatch` only, for on-demand checks. It compares the repo's
  `index.html` against each sibling's **deployed** site, so it also catches
  "merged but the sibling never shipped." Expect a transient WARN while a
  port is merged-but-undeployed on one side.

## Current ENGINE block inventory (23)

`app-token`, `arcgis-loader`, `arcgis-paged-loader`, `cached-loaders`,
`feedback`, `fetch-retry`, `find-prop-ci`, `geolocation`, `haversine`,
`metro-links`, `metro-links-html`, `metro-portal`, `permalink`,
`point-in-polygon`, `polygon-containment`, `probe-geometry-column`,
`render-helper`, `sanitize`, `scope-mask`, `selection-controls`,
`socrata-loader`, `socrata-point-loader`, `state`.

(`metro-portal` — the sibling-metro portal easter egg — reads per-metro
`bbox`/`emoji` fields on `METRO_EXPLORERS` entries and expects fork CSS to
define the `#metro-portal`/`.metro-portal-*`/`.sibling-result*` classes in
that fork's palette; it sits between the `feedback` fence and the geocoder.
Entries without a bbox opt out of the portal; overlapping bboxes resolve to
the nearest bbox center; per-metro dismissals re-arm on leaving that bbox —
all so the block survives N metros unchanged. Each fork's
`validate_index.py` lints the list (see that script). The *search* trigger —
one unbounded retry of a zero-result query, hits classified into sibling
bboxes via `siblingMetroAt` — is geocoder-provider code, so it lives with
the fork's geocoder, not in the fence; see backlog item 1.)

(`scope-mask` shows the seam pattern for engine code that needs a per-metro
*function*, not a config constant: `drawOutOfScopeMask(loadCoverageGeometry)`
takes the fork's coverage-geometry loader as a parameter at its unfenced BOOT
call site, so the block body stays byte-identical. The geocoder reconciliation
below should use the same shape.)

Growing this inventory is encouraged: when you touch shared-looking code that
isn't fenced yet, reconcile it across forks and fence it as part of the
change.

## Reconciliation backlog (known structural drift, July 2026)

These engine-quality areas have already forked between Chicago and NYC and
are **deliberately not fenced yet**. Each is a future "reconcile, then fence"
task — drift here runs in *both* directions, so reconciling means merging
features, not overwriting:

1. **Geocoder (search box + POI geocode)** — Chicago: Photon/Nominatim; NYC:
   NYC Planning GeoSearch (Pelias). Needs a provider seam behind
   `geocodeAddress()`/`geocodePoiAddress()` so the engine part (debounce,
   queue, rate-limit, render) can be fenced while the provider stays per-metro.
   July 2026 addition to reconcile alongside: Chicago's
   `maybeRenderSiblingMatches()`/`buildSiblingResultRow()` — the search-side
   trigger for the fenced `metro-portal` easter egg (a zero-result query is
   retried ONCE unbounded, hits classified into sibling metros via
   `siblingMetroAt`, matches rendered as hand-off rows — one extra request
   per miss regardless of metro count). NYC's GeoSearch only covers NYC, so
   its port needs a whole-OSM provider (e.g. the same Photon call) for the
   sibling lookup.
2. **Result-card / overlay styling framework + factories** — Chicago added
   `styleForFeature`/`restyleOverlayFeatures`/`hoverDotColor` (per-feature
   color-coding, School Location); NYC added `primaryField`/`hoverName` to the
   polygon factory. Chicago's July 2026 back-port (#82) lifted NYC's hover
   parity + `registerNearestPointLayer`/`loadArcGISPaged`/
   `makeSocrataPointLoader` into the reference tree, so the *semantics* now
   match (and the two loaders are already fenced) — but the factory *text*
   still differs between forks. Reconcile the factories to byte-parity, then
   fence the registry.
3. **Hover explorer** — same two-way drift as (2), plus per-city
   `HOVER_NUMBER_KEYS`/`HOVER_NAME_KEYS` lists that belong in METRO config.
4. **`LAYER_AREA_RANK`/`LAYER_ORDER` + `GROUPS`** — city data, but the
   *consuming* machinery (reorder/highlight sweeps) should be fenced once (2)
   is reconciled.
5. **Exports namespace** — `window.ChiExplorer` vs `window.NycExplorer`
   (twinned with each `smoke_test.mjs`). Either standardize the name or build
   the object in a fenced block and assign the window property in METRO code.
6. **CSS palette namespace** — `--chi-*` vs `--nyc-*` variables block CSS
   fencing (e.g. the footer-metros styles differ only by
   `var(--chi-blue)`/`var(--nyc-blue)`). Rename both to neutral `--accent-*`
   names, then fence the shared layout CSS.
7. **`sw.js`** — handler logic is already byte-identical; only comments and
   the per-city URL lists differ. Neutralize comments, fence the logic.
8. **`validate_index.py`** — NYC added `check_sw_lists()` (every `data/app/`
   file in exactly one sw.js list); Chicago should adopt it. `smoke_test.mjs`:
   NYC added a `cardText()` helper worth backporting.
9. ~~Duplicated playbook copies~~ — **resolved July 2026**: the master
   `METRO_EXPANSION_PLAYBOOK.md` lives in the Chicago repo under `docs/`
   (sibling forks carry a root pointer stub only), and the raw NYC
   research notes are archived at `docs/archive/METRO_EXPANSION_NYC.md`
   in the Chicago repo.
