# Handoff 2: Card System Rollout — all layer card types (chidistricts.com)

## Overview
Extends **Handoff 1** (`docs/design_handoff_county_board_card/` — the County Board District card, design ids 3a–3d). This package applies that same design system to every other result-card type in the app, so all 39 layers render from one visual skeleton. Implement Handoff 1 first; this package only specifies what's new.

The reference designs are **turn 4 (ids 4a–4e)** in the bundled `Info Card Explorations.dc.html` (which also contains turns 1–3; turn 3 is Handoff 1's spec, kept for context).

## About the Design Files
Design references created in HTML — recreate in the app's existing vanilla-JS/inline-style environment (`index.html`'s `renderFieldList` framework), not code to paste. High-fidelity: exact colors, sizes, spacing below and readable inline in the file.

## Shared skeleton (from Handoff 1 — unchanged)
Card: white, `1px solid rgba(0,0,0,.08)`, left accent `3px solid #1d5fd6`, radius 10px, shadow `0 1px 3px rgba(0,0,0,.06)`. Header: checkbox (20×20, `#1d5fd6`, radius 5) + layer color dot (10px circle, keeps each layer's existing theme color) + layer name (16px/700/`#111827`) + right-aligned identifier pill (13px/600/`#1a56c4` on `#eef4fd`, radius 999). Footer: "☆ Pin as parent" button + right-aligned primary link. Rows separated by `1px solid #f1f3f7`. All design tokens: see Handoff 1 README.

Key change vs production: **left-aligned content rows replace the right-aligned `dt`/`dd` value rows** everywhere.

## New card types in this package

### 4a — Representative card (congress, il-senate, il-house)
- Identifier pill in header: "IL‑14" (district number).
- Person row (same as Handoff 1 member row): name 14.5px/700 + party as role badge (11px/700/`#1a56c4` on `#e3edfb`, radius 999) + website link line (12.5px).
- "Offices" `<details>` group (open by default on desktop): each office = uppercase kicker label 12px/700/`#6b7280` ("District Office", "D.C. Office"), address 12.5px/`#4b5563` on one line, phone below in tabular-nums. Replaces the wrapping right-aligned address blocks.
- Footer link: "Official website ↗".

### 4b — Name-only polygon (township, municipality, zip-code, community-area, school districts)
Single-row compact card, no body/footer: header contains checkbox + dot + a two-line stack (layer name 13px/600/`#6b7280` over the value 15px/700/`#111827`) + right-aligned GEOID 11.5px/`#9aa3b2` tabular-nums. Card width can stay narrower (~420px). If richer data exists (County card's Clerk contact), it becomes member-style rows per Handoff 1.

### 4c — Link-only card (fire/park/library districts, judicial subcircuits, mwrd, tif)
Header (no pill) → one content row: district name 14.5px/700 + "Official website ↗" link line 12.5px → footer with Pin button only.

### 4d — Nearest-3 list (police-station, fire-station, post-office, library, early-voting)
Header with "(nearest 3)" suffix 13px/600/`#6b7280`. Three rows: name 14px/700 over address 12.5px/`#4b5563`, right-aligned distance pill (12px/600/`#1a56c4` on `#eef4fd`, radius 999, e.g. "1.8 mi"). No footer unless the layer has a directory link.

### 4e — Card states
- **Loading:** header + one row: 16px spinner (2px border `#c7d7f2`, top `#1d5fd6`) + "Loading district data…" 13px/`#6b7280`.
- **Error:** left accent turns `#c2410c`; row: message 13px/`#7c2d12` + "Retry" button (same button style). Failure stays isolated to its own card (app invariant).
- **Empty/outside:** left accent `#d1d5db`; row: "This point isn't inside any district in this layer." 13px/`#6b7280`.

## Layer → pattern mapping (all 39)
- Handoff 1 (member rows + optional committees `<details>` + countywide section): county-board (all 7 counties), ccbr, school-board, ccpsa-district-council, ward, il-supreme-court (justices), county (clerk block)
- 4a representative: congress, il-senate, il-house, police-district (commander + station = office block), police-beat (inherits district contact)
- 4b name-only: township, municipality, zip-code, community-area, school-district-{unified,secondary,elementary}, cps-{elementary,middle,high} zones, cps-network ×2, ward-precinct, county-precinct (+ polling-place row), school-site
- 4c link-only: fire-district, park-district, library-district, judicial-subcircuit, mwrd, tif-district, dupage-county-special-police (About row stays)
- 4d nearest-3: police-station, fire-station, post-office, library, early-voting
- 4e states: all layers

## Interactions
Same as Handoff 1 (native `<details>`, tel:/mailto:, hover `#1a56c4`→`#123c8a`). Mobile (<~420px container): Handoff 1's mobile deltas apply to every type; nearest-3 rows keep the distance pill, min-height 44px.

## Files
- `Info Card Explorations.dc.html` — implement turn 4 (4a–4e) + turn 3 (Handoff 1). All styles inline in the markup.
- Sample data in the mocks (station names/distances in 4d, GEOIDs in 4b) is illustrative — always render real query results.
