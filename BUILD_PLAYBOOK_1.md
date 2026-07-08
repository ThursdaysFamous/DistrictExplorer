# Chicago District Explorer — Build Playbook

The reference-of-truth for building this app in small, cheap, focused threads.
**Add this file to the Project** so every thread has it via retrieval. Never paste the whole app into a thread — paste only this playbook's contract + the one module being worked on.

---

## 1. Architecture: stable core + 4 pluggable modules

**The core is built once and rarely touched.** It owns everything shared:

- HTML shell, Chicago-flag palette, Big Shoulders Display, custom six-point star marker
- Leaflet map init; click-to-select + geocoder (Nominatim, debounced, Chicago bbox `[-87.94, 41.64, -87.52, 42.02]`, swappable, attributed)
- Global state: `selectedPoint {lat, lng}`, monotonic `sequence` counter (discards stale async results)
- Shared utilities: `sanitize(str)`, `pointInPolygon(pt, geom)` (multipolygon + holes), `fetchWithRetry(url, opts)`, `probeGeometryColumn(datasetId)` (Socrata field names vary)
- Layer registry + result-card framework: loading / error / empty states, `aria-live` regions, per-layer failure isolation
- Attribution + "data last verified" + legal disclaimer footer

**Each layer module is self-contained** and exposes exactly this interface:

```js
{
  id:    "ward",                 // unique
  group: "political",            // political | safety | schools | geography
  label: "City Ward",
  overlay: {                     // lazy-loaded map overlay
    load: () => Promise<GeoJSON>,// fetched only when toggled on
    style: {...},                // visually distinct; not color-only (polygon/line datasets)
    pointToLayer: (feature, latlng) => L.Layer  // optional; point datasets (e.g. fire stations) use this instead of style
  },
  query: (point, seq) => Promise<Result | null>,  // point-in-district + roster join; tag result with seq
  render: (result) => HTMLElement                  // one result card; all external strings via sanitize()
}
```

Rules every module must honor (from the prompt's quality requirements):
1. `query` results tagged with `seq`; the core discards any result whose `seq` is stale.
2. Toggling a layer off clears its result card.
3. Any fetch can fail — surface it *in that card*, never break the app.
4. All external API values passed through `sanitize()` before render.
5. No-result / no-match / slow-load each get an explicit honest state.

---

## 2. Data registry (verified July 2026 — reverify before relying)

| Layer | Source | ID / endpoint |
|---|---|---|
| Wards (2023–) | Socrata | `p293-wvbd` |
| Aldermen roster | Socrata | `htai-wnw4` (join on ward #) |
| Police districts | Socrata | `fthy-xz3r` |
| Fire stations (points) | Socrata | `28km-gtjn` (nearest-N proximity, not point-in-polygon) |
| CPS elementary zones | Socrata | `5ihw-cbdn` |
| CPS high school zones | Socrata | `4kfz-zr3a` |
| CPS middle zones | Socrata | none verified current; legacy `9kct-c3uq`, ~22 schools only — degrade gracefully |
| Community areas | Socrata | `igwz-8jzy` |
| ZIP codes | Socrata | `gdcf-axmw` |
| Congress / IL upper / IL lower boundaries | Census TIGERweb Legislative MapServer | layers 0 / 1 / 2 — request `outSR=4326` |
| Congress rosters | congress-legislators | filter `state=IL`, join on district # |
| IL GA rosters | Open States people | **no browser CORS** — fallback to ILGA directory links |
| School board districts | KML on ilsenateredistricting.com | not on data portal; needs manual convert→host (see §4) |

Socrata caps at 1,000 rows by default. Some serve `/resource/{id}.geojson`; legacy ones use `/api/geospatial/{id}?method=export`.
Commanders + principals: **not in open data** — link to CPD district pages and `cps.edu/schools/schoolprofiles/{school_id}`, never guess.

---

## 3. Thread sequence

Build simplest first to prove the contract, then escalate. **Use Claude Sonnet for module work; reserve Opus for genuinely hard logic (likely only the Political group).**

- **Thread 0 — Core shell.** Deliver the stable core + one trivial stub module so the plumbing is proven end-to-end.
- **Thread 1 — Geography.** Community area + ZIP. Simplest; validates the module pattern.
- **Thread 2 — Public Safety.** Police district (polygon) + fire stations (nearest-N proximity).
- **Thread 3 — Schools.** Elementary / middle / high zones + profile links; handle missing middle zones.
- **Thread 4 — Political.** Ward+alderman, congress+reps/senators, IL Senate/House, school board. Heaviest — split into two threads if needed. Do the school-board KML conversion (§4) before this thread.
- **Thread 5 — Assembly + audit.** Concatenate into single file; a11y pass, on-demand-loading check, disclaimer/attribution, "data last verified" date.

---

## 4. Manual step required before the Political thread

The school-board KML can't be fetched by a browser app (Drive interstitials + CORS). Operator must:
1. Download the KML from the ilsenateredistricting.com source.
2. Convert to GeoJSON: `mapshaper in.kml -o out.geojson` (or `ogr2ogr -f GeoJSON out.geojson in.kml`).
3. Host it as a static asset alongside the app.
4. Confirm which KML property identifies the district number — if unclear, ask rather than guess.

---

## 5. Per-thread handoff protocol (keeps threads cheap)

**Start of a module thread, paste only:** this playbook's §1 contract + §2 rows for that layer. That's it.
**End of a module thread, append 3 lines here** under a "Status" heading:

- `[module] DONE — exposes contract, tested against <point>`
- `[module] STUB — <what's faked>`
- `[module] SURPRISE — <any dataset quirk found>`

Then update the Project copy of this file. Next thread starts clean with full context but tiny token cost.

---

## Status

_(append handoff notes here as modules complete)_

- `core-shell` DONE — delivers HTML shell, Chicago-flag palette, Big Shoulders Display + Inter + IBM Plex Mono, six-point-star marker/icons, flag-stripe header motif; Leaflet map with click-to-select and a keyboard/screen-reader "select map center" fallback button; Nominatim geocoder (debounced 550ms, Chicago bbox-bounded, OSM-attributed, in-flight requests aborted on new input); global `state {selectedPoint, sequence, layersOn}`; shared utils `sanitize`, `pointInGeometry` (Polygon/MultiPolygon, holes via even-odd across all rings), `fetchWithRetry` (timeout + backoff), `probeGeometryColumn` (Socrata field sniff); layer registry + result-card framework (loading/error/empty/off states, aria-live, per-layer isolation, retry button); footer with disclaimer, "data last verified" date, and source attribution. Tested against a manual click near the Loop (41.8825, -87.6285) and via the keyboard-select fallback — sequence counter correctly discards a stale query when a second point is selected before the first (artificially delayed) query resolves.
- `demo-radius` (geography, STUB) DONE — exercises the full module contract end-to-end: lazy overlay.load(), query() against a synthetic square via the shared `pointInGeometry`, seq-tagged result, render() via shared `renderFieldList`. Intended to be deleted once Thread 1 lands real Geography modules.
- SURPRISE — none of the verified endpoints were called yet (out of scope for Thread 0); first real-data risk to watch in Thread 1 is Socrata's default query behavior when `probeGeometryColumn` guesses wrong on an unfamiliar dataset — worth a manual spot-check per dataset rather than trusting the sniff blindly.
- `community-area` (geography) DONE — full-dataset fetch + local point-in-polygon, case-insensitive field lookup, dashed overlay style
- `zip-code` (geography) DONE — same pattern, dotted overlay style
- demo-radius STUB removed per plan
- SURPRISE — couldn't get a live JSON field-name confirmation (web_fetch sandbox only allows previously-searched/fetched URLs); modules degrade gracefully via findPropCI's alias list if the guessed field name is wrong, but a manual spot-check against real data is still worth doing before Thread 4 depends on the same pattern
- Moved to Claude Code: `index_1.html` (Thread 0 + Thread 1) is now the single canonical `index.html`; the old Thread-0-only `index.html` snapshot was removed. Each future thread edits `index.html` in place rather than saving a new numbered file.
- Fixed after moving to Claude Code: the Leaflet CSS/JS `integrity` hashes pasted into the core shell didn't match the real CDN files, so browsers silently blocked both and crashed the whole init script (blank map, dead Layers dropdown). Corrected to the hashes the browser itself reported. Also swapped the OSM tile layer for CARTO's basemap tiles — OSM's tile CDN 403s requests with no HTTP referrer, which `file://` pages (the common way to open this app) never send; CARTO doesn't enforce that check.
- `police-district` (safety) DONE — same polygon/point-in-polygon pattern as Thread 1's Geography modules; red dash-pattern overlay distinct from Geography's green/blue.
- `fire-station` (safety) DONE — point dataset, so no point-in-polygon test; instead does nearest-3 straight-line (haversine) proximity, sorted ascending. Required one small, backward-compatible core addition: `overlay.pointToLayer`, since the core's overlay renderer only knew `style` (meaningless for Point geometries) — existing polygon modules are unaffected since they never set it.
- SURPRISE — same sandboxed web_fetch limitation as Thread 1: couldn't get a live field-name confirmation for `fthy-xz3r` (police districts) or `28km-gtjn` (fire stations). Both modules degrade gracefully via `findPropCI`'s alias lists if a guessed field name is wrong, but a manual spot-check against real data is worth doing, especially before Thread 4 (Political) leans on the same pattern for higher-stakes datasets.
- BUG FOUND + FIXED (operator spot-check, post-thread) — `gdcf-axmw` (ZIP) and `fthy-xz3r` (police districts) are the correct current dataset IDs, but both always returned "No result" because their primary `.geojson?$limit=...` route returns HTTP 200 with every feature's geometry stripped to `null` — a "succeeded but useless" response the original `.catch()`-only fallback never detected. Fixed in `loadSocrataGeoJSON` with a `hasUsableGeometry()` check that now falls back to the legacy `method=export` route whenever the primary response has no real geometry, not just on outright fetch failure. Worth checking whether any other "legacy" dataset in the registry (§2) has this same silent-200 behavior.
- `fire-station` firehouse designation added — confirmed via live sample of `28km-gtjn`: the field is `engine` (e.g. `"E5"`).