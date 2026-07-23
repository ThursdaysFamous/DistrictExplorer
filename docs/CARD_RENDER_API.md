# Card Render API — helper surface for the info-card redesign

**Status: IMPLEMENTED** — engine release N (`card-helpers` + `styles-card-v2`
fences, shell mounts, chamber/nearest/polygon-compact factories) and the
Chicago fork wave (county-board ×7 counties, school-board, ccbr, ward, ccpsa,
county clerk, police-district, ward-precinct/police-beat compact, 4c footer
links) are live. Two additive extensions landed during implementation:
`renderLinkRow` also accepts `phone`/`email` (office-like rows such as a CAPS
desk), and `registerPolygonLayer` passes through `opts.primaryLink`.
**Wave 3 is also live**: `renderFieldStack` (the generic label-over-value
stack) joined the helper set and now serves the generic `polygon-factory` /
`polygonCountyEntry` paths and every county-concept entry (judicial-
subcircuit, fire/park/library districts, county-precinct — links moved to
entry-level `primaryLink`); `school-zone-factory` grew the data-only
`profileLink(id)`/`moreLink` opts (Chicago's CPS zones use them) and
`cps-network-factory` renders chief + office natively; `renderLinkRow`
gained a `note` line. **Chicago now has zero `renderFieldList` call sites.**
The four surviving `renderFieldList` references are deliberate sibling-
compat legacy branches (polygon-factory, polygonCountyEntry, school-zone
×2) that fire only for specs still carrying caller-HTML opts — NYC/SF hit
them until they migrate. `school-site` keeps its bespoke filter card by
design. The retirement release (delete `render-helper` + the `.result-row`
CSS + the legacy branches) stays gated on a fleet-wide zero grep.

This is the engineering contract for implementing the card redesign specified in
`docs/design_handoff_county_board_card/` (Handoff 1, County Board card, design
ids 3a–3d) and `docs/design_handoff_card_system/` (Handoff 2, all card types,
ids 4a–4e). It defines the shared helper functions, the `registerLayer` contract
additions, and the rollout sequencing. The API is the load-bearing decision: it
fixes what fork-local layer modules pass versus what the engine renders, and
therefore both the engine diff and the per-fork migration that follows it.

## Why the API is shaped this way

Card rendering is split across the parity fence line:

- **Engine-fenced** (byte-identical across Chicago/NYC/SF, ships via the
  `engine-v*` release pipeline — `docs/ENGINE_SYNC.md`): the card shell and
  states (`overlay-cards`), the shared row builder `renderFieldList`
  (`render-helper`), the card CSS (`styles-app`), and the factories that render
  whole card families (`polygon-factory`, `chamber-factory`,
  `nearest-point-factory`, `school-zone-factory`, `cps-network-factory`,
  `office-helpers`).
- **Fork-local**: ~30 `renderFieldList` call sites per fork in metro layer
  modules (county dispatcher entries, ward, CCBR, …), which NYC/SF mirror with
  their own code.

An engine bump lands in sibling forks **before** their local modules are
converted. The API below is therefore **additive**: `renderFieldList` and its
`dt`/`dd` output keep working unchanged until every fork's call sites have
migrated; a later engine release deletes it. New helpers live in a **new**
ENGINE fence (`card-helpers`) so release N's diff is a pure addition and the
retirement release deletes the old fence without touching the new one.

## Hard rules the helpers enforce

1. **Callers pass data, never markup.** No helper accepts an `html` field. The
   `f.html` "caller certifies this was built with sanitize()" escape hatch in
   `renderFieldList` does not carry over; migrated layers cannot inject markup
   at all. All text lands via `textContent`; all attributes via `setAttribute`.
2. **URLs are scheme-checked centrally.** Every external `url` passes through
   `safeHttpUrl` inside the helper (http/https only, else the link is dropped);
   external links get `target="_blank" rel="noopener"`. `mailto:`/`tel:` hrefs
   are **constructed by the helper** from a raw address/number — callers never
   build hrefs.
3. **Email is never printed.** Per Handoff 1: a raw address renders as an
   "Email" link with the `mailto:` behind it.
4. **Phone display vs. dial value.** Displayed numbers use non-breaking hyphens
   (U+2011) and `tabular-nums`; the `tel:` href strips to digits/`+`. The
   helper does both from one input string. Phones are always links (`tel:` is
   harmless on desktop and required on mobile).
5. **Honesty rules unchanged.** Helpers render exactly what they are passed;
   absent fields render nothing (no placeholders, no guessed officeholders).

## The helpers (new `card-helpers` ENGINE fence)

All return a DOM node/fragment for the module's `render(result)` to compose and
return, exactly as `renderFieldList` does today. ES5 throughout.

### `renderBodyIntro(spec)`

The body-name + count line under the header (Handoff 1 "Body intro").

```js
renderBodyIntro({
  title: "DuPage County Board",          // 14px/600 line
  note: "3 district members · 1 countywide chair"   // optional 12px muted line
})
```

### `renderPersonRows(people, opts)`

The core Handoff 1 vocabulary: one row per person; a person with `details`
becomes a native `<details>` expander (summary = the row, chevron hint).

```js
renderPersonRows([{
  name: "Sherry Williams",               // required; 14.5px/700
  badge: "Democratic Leader",            // optional role/party chip
  note: "Crest Hill",                    // optional muted inline text (hometown)
  phone: "815-354-7291",                 // optional; rendered per rule 4
  email: "swilliams@willcounty.gov",     // optional; renders as "Email" link (rule 3)
  links: [{ label: "Profile", url: "https://…" }],  // optional external links (rule 2)
  details: { label: "Committees",        // optional; presence makes the row an expander
             items: ["Public Works & Transportation", "Landfill (Chair)"] },
  detailsOpen: true                      // optional; desktop-only default-open
}], { tinted: true })                    // opts.tinted: the #f8fafc section bg
                                         // (countywide rows); omit for plain rows
```

`details.items` are plain strings joined with " · " by the helper — role
annotations like "(Chair)" are part of the string, formatted by the caller.
`detailsOpen` is honored only when the results panel is desktop-width at render
time (cards re-render on every selection; a resize between selections is
accepted as stale until the next render).

### `renderSectionLabel(text)`

The uppercase kicker divider row ("COUNTYWIDE") that precedes a tinted
`renderPersonRows(people, {tinted: true})` block.

### `renderOfficeGroup(spec)`

Handoff 2 §4a: the "Offices" `<details>` group of kicker-labeled office blocks.

```js
renderOfficeGroup({
  label: "Offices",                      // summary text
  open: true,                            // desktop-only default-open (as above)
  offices: [{
    label: "District Office",            // uppercase kicker
    lines: ["116 N. Chicago Street, Suite 201, Joliet, IL 60432"],  // address lines
    phone: "630-549-2190"                // optional; rendered per rule 4
  }, { label: "D.C. Office", lines: ["2228 Rayburn HOB, Washington, DC 20515"],
       phone: "202-225-2976" }]
})
```

Callers keep using `officeAddressForGeocode` for the POI pin — unchanged.

### `renderNearestRows(items)`

Handoff 2 §4d: nearest-N rows with distance pills.

```js
renderNearestRows([{
  name: "Naperville PD — Main Station",  // 14px/700
  note: "1350 Aurora Ave, Naperville",   // optional address line
  distanceLabel: "1.8 mi"                // caller-formatted (factory owns rounding/units)
}])
```

### `renderLinkRow(spec)`

Handoff 2 §4c: a name + link line (link-only cards; also the migration target
for `renderSourceUnavailable`'s lookup row).

```js
renderLinkRow({
  title: "Naperville Fire Protection District",   // optional 14.5px/700 line
  links: [{ label: "Official website ↗", url: "https://…" }]
})
```

## `registerLayer` contract additions (all optional, presence-based)

No `cardV2` flag: a layer opts into each new surface by declaring the field,
which keeps unmigrated modules — and whole unmigrated forks — pixel-identical
in behavior to today.

- **`cardIdentifier(result) => string | null`** — the header identifier pill
  ("District 6", "IL‑14"). Rendered by the shell into the header on each
  result, cleared on empty/error. Factories derive it from the same district
  extraction their `hoverName`/card already use, so the three surfaces
  (pill, hover, card) cannot disagree.
- **`primaryLink(result) => {label, url} | null`** — the footer's right-aligned
  link ("Official directory ↗"). The **footer is shell-owned, not a helper**:
  when a result renders, the shell builds the footer from `primaryLink` plus
  the existing "Pin as parent" control (`appendPinControl` moves its button
  into the footer when one exists; its polygon-only/containment rules are
  unchanged). No `primaryLink` and no pin ⇒ no footer, as in Handoff 2 §4d.
- **`compact: true`** — Handoff 2 §4b single-row presentation. The shell
  renders the header as the two-line stack (small layer name over
  `cardIdentifier(result)` as the value line) with
  **`cardMeta(result) => string | null`** right-aligned muted (GEOID). A
  compact layer's `render` is not called on success; loading/error/empty
  states still use the normal body. Richer-data cases (the County card's
  clerk block) simply don't declare `compact` and use person rows instead.

## Shell and CSS changes (engine-side, no API surface)

- **Card chrome** (left accent, radius 10, shadow, restyled header) and the
  **4e states** (spinner row, error accent `#c2410c` + Retry, empty accent
  `#d1d5db`) ship for **all** cards at release N, migrated or not. Legacy
  `dt`/`dd` bodies inside the new chrome read like the handoff's 1d
  "directory table" during the transition — coherent, just not final.
- The redesign's palette lands as engine CSS custom properties (extending the
  existing `--slate`-family tokens) with the handoff hex values; layer theme
  colors stay per-metro config (the color dot keeps each layer's existing
  color, per Handoff 2).
- Mobile deltas (Handoff 1 §mobile) via a container query on the results panel
  at ~420px, applying to all helper-emitted classes; no API impact.
- `renderSourceUnavailable` (engine) migrates off `renderFieldList` to
  `renderLinkRow` in the same release.
- Hover popups, `hoverName`, `pointOfInterest`, coverage, and the
  stale-`seq` guard are untouched.

## Pattern → caller mapping

| Handoff pattern | Helpers | Callers (engine) | Callers (fork-local, per fork) |
|---|---|---|---|
| H1 member roster | `renderBodyIntro` + `renderPersonRows` + `renderSectionLabel` | — | county-board dispatcher entries, ccbr, school-board, ccpsa, ward, il-supreme-court, county (clerk block) |
| 4a representative | person row + `renderOfficeGroup` | `chamber-factory` (congress, il-senate, il-house) | police-district (commander + station), police-beat |
| 4b name-only | *(contract fields only: `compact`, `cardIdentifier`, `cardMeta`)* | `polygon-factory`, `school-zone-factory`, `cps-network-factory` | ward-precinct, county-precinct (+ polling-place row via person/link rows), school-site |
| 4c link-only | `renderLinkRow` | — | fire/park/library districts, judicial-subcircuit, mwrd, tif, dupage-special-police |
| 4d nearest-N | `renderNearestRows` | `nearest-point-factory` | early-voting (bespoke) |
| 4e states | *(shell-owned)* | all layers automatically | — |

## Sequencing (per `docs/ENGINE_SYNC.md`)

1. **Engine release N (additive):** `card-helpers` fence + CSS + shell changes
   (chrome, states, pill/footer/compact mounts) + factory migrations +
   `renderSourceUnavailable` migration. `renderFieldList` and `.result-row`
   CSS remain. At each fork's bump, chrome/states/factory-driven cards restyle
   immediately; fork-local cards keep `dt`/`dd` bodies inside the new chrome.
2. **Per-fork migration:** each fork moves its local `render` functions to the
   helpers at its own pace (Chicago in the same change-set that ships N).
3. **Engine release N+1 (retirement):** when a fleet-wide grep shows zero
   `renderFieldList` call sites (the ENGINE_SYNC "definition of done" gate),
   delete the `render-helper` fence and the `.result-row`/`.result-fields` CSS.

**Gates, all local:** `python3 scripts/check_engine_parity.py index.html`
(fence lint; also runs inside `validate_index.py`), `validate_index.py`
(`registerLayer(` count is unchanged — this is a render-path change, not a
layer change), and the smoke test (boot + all layers + ground-truth
classification are DOM-shape-independent; extend it with a
new-class assertion once cards migrate).

## Open questions for review

1. **Chrome-for-all at release N** (recommended above) vs. chrome gated to
   migrated layers — mixed chrome within one panel looks broken, which is why
   all-at-once is recommended, but it does restyle sibling forks at bump time
   ahead of their content migration.
2. **`detailsOpen` render-time width check** — accepted staleness on resize,
   or listen and re-render? (Recommend: accept; re-render already happens per
   selection.)
3. **Distance pill formatting** — caller-formatted `distanceLabel` (above)
   keeps `toFixed` in the factory; alternatively pass raw miles and let the
   helper own rounding fleet-wide. Caller-formatted is recommended so bespoke
   nearest lists (early-voting) stay free to annotate.
