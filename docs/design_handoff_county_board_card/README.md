# Handoff: County Board District Info Card (chidistricts.com)

## Overview
A redesigned "County Board District" info card for the POLITICAL layer panel on chidistricts.com. One card skeleton standardizes rendering across all counties, handling:
- Single-member districts (e.g. Lake County)
- Multi-member districts (e.g. DuPage, Will)
- Optional countywide officials (e.g. DuPage Board Chair) in a visually separated section
- Optional per-member detail data (committees, hometown) behind a collapsible expander

The final approved design is **turn 3 (options 3a–3d)** in the bundled design file: 3a/3b desktop, 3c/3d mobile (360px).

## About the Design Files
The files in this bundle are **design references created in HTML** — prototypes showing intended look and behavior, not production code to copy directly. Recreate these designs in the target codebase's existing environment (whatever framework/stack chidistricts.com uses) with its established patterns. If no component framework exists, plain semantic HTML/CSS matching these specs is fine — the prototype uses only standard HTML (`<details>/<summary>`) and CSS.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and interaction states are final. Recreate pixel-perfectly; exact values below.

## Data Model (drives all variants)
```
DistrictCard {
  districtNumber: string        // "6"
  body: string                  // "DuPage County Board"
  members: Member[]             // district members, in official order
  countywide: Member[]          // optional (chair, exec); renders separated section
  directoryUrl: string          // official county directory
  directoryLabel: string        // "Official directory"
}
Member {
  name: string
  roleBadge?: string            // "Board Chair", "Democratic Leader"
  hometown?: string             // "Lockport"
  phone?: string
  email?: string
  profileUrl?: string
  profileLabel?: string         // "Profile" | "District page"
  committees?: string[]         // if present, member row becomes an expander
}
```
Rendering rules:
- `countywide` empty → section omitted entirely.
- `committees` absent → member renders as a plain row (no expander, no chevron).
- `committees` present → member renders as `<details>`: summary = name row + contact line; expanded body = committees. First member with details may default open on desktop.
- One member → card is just header / member row / footer; nothing else changes.

## Screens / Views

### Desktop card (options 3a, 3b) — width 520px (fluid up to panel width)
Card container: white bg `#ffffff`, border `1px solid rgba(0,0,0,.08)`, **left accent border 3px solid #1d5fd6**, radius 10px, subtle shadow `0 1px 3px rgba(0,0,0,.06)`.

**Header row** — flex, gap 12px, padding 14px 18px, bottom border `1px solid #e8eaef`:
- Checkbox: 20×20, radius 5px, bg `#1d5fd6`, white ✓ (this is the existing layer-toggle checkbox — keep existing behavior)
- Layer dot: 10px circle, `#1e3a5f`
- Title "County Board District": 16px / 700 / `#111827`
- Right-aligned district pill: "District 6" — 13px / 600 / `#1a56c4` on `#eef4fd`, padding 3px 10px, radius 999px

**Body intro** — padding 14px 18px 6px:
- Body name: 14px / 600 / `#374151` ("DuPage County Board")
- Count line: 12px / `#6b7280`, e.g. "3 district members · 1 countywide chair" (omit when single member)

**Member rows** — padding 10px 18px, separated by `1px solid #f1f3f7`, LEFT-aligned (replaces old right-aligned key/value rows):
- Name: 14.5px / 700 / `#111827`; inline after it (gap 8px): optional role badge (11px / 700 / `#1a56c4` on `#e3edfb`, padding 2px 8px, radius 999px) and hometown (12px / `#6b7280`)
- Contact line below (flex-wrap, gap 3px 9px, 12.5px): phone in `#4b5563` with `font-variant-numeric: tabular-nums` and `white-space: nowrap` (use non-breaking hyphens ‑ in numbers); separator "·" in `#c3c9d4`; then short links **Email** and **Profile** (link color `#1a56c4`, no underline, hover `#123c8a`). Do NOT print full email addresses — `mailto:` behind the "Email" link.

**Member with committees** — `<details>` wrapping the row:
- Summary = the member row above + right-aligned hint "details ▾/▸" (11px / `#9aa3b2`)
- Expanded body (padding 0 18px 12px): "Committees:" label 12.5px / 600 / `#374151`, then list in `#5b6472`, items joined with " · ", role annotations in parens, line-height 1.5

**Countywide section** (only if `countywide` non-empty):
- Divider row on `#f8fafc` bg, top border `#e8eaef`: label "COUNTYWIDE" 10.5px / 700 / uppercase / letter-spacing .08em / `#6b7280`, followed by 1px rule `#e8eaef` filling the row
- Member row(s) same format, on `#f8fafc` bg, with role badge (e.g. "Board Chair")

**Footer** — flex, padding 12px 18px, top border `#e8eaef`:
- "☆ Pin as parent" button: 13px / 600 / `#1a56c4`, white bg, border `1px solid #c7d7f2`, radius 8px, padding 6px 12px
- Right-aligned "Official directory ↗" link: 13px / 600

### Mobile card (options 3c, 3d) — 360px, distinct compact layout
Same structure with these deltas:
- Horizontal padding 14px (not 18px); header checkbox 22×22 radius 6px
- Header stacks title + subtitle: "County Board District 6" 14.5px / 700; below it "DuPage County Board · 3 members + chair" 12px / `#6b7280` (district pill merged into title, no dot)
- Member rows: min-height 44px; every tappable link gets ≥8px vertical padding (44px effective target)
- Committees expand by tapping the whole member row (`<details>` summary), chevron-only hint ▾/▸
- Footer: "☆ Pin" (short label) + "Directory ↗"

## Interactions & Behavior
- Expander: native `<details>/<summary>` semantics (or framework equivalent). Chevron flips ▾ open / ▸ closed. No animation required; if desired, ≤150ms ease-out height fade.
- Links: `tel:` for phone (mobile), `mailto:` for Email, profile URL opens new tab. Hover: link color darkens `#1a56c4` → `#123c8a`.
- Pin as parent: existing app behavior, unchanged; hover bg `#f3f7fd`.
- Checkbox: existing layer-visibility toggle, unchanged.
- Responsive: switch to mobile layout below ~420px container width (container query preferred over viewport).

## State Management
- Per-member expander open/closed (local state or native details; no persistence needed)
- Everything else derives from the district data object; no new global state

## Design Tokens
Colors: primary `#1d5fd6`, link `#1a56c4`, link-hover `#123c8a`, text `#111827`, text-secondary `#374151`, text-body `#4b5563`, muted `#6b7280`, detail-text `#5b6472`, hint `#9aa3b2`, separator-dot `#c3c9d4`, badge-bg `#e3edfb`, pill-bg `#eef4fd`, section-bg `#f8fafc`, border `#e8eaef`, row-border `#f1f3f7`, button-border `#c7d7f2`, layer-dot `#1e3a5f`.
Typography: system-ui stack. Sizes: 16/14.5/14/13/12.5/12/11/10.5px; weights 400/600/700. Phone numbers: tabular-nums.
Spacing: card padding x 18px (desktop) / 14px (mobile); row padding-y 10–12px; flex gaps 8/9/12px.
Radii: card 10px, buttons 8px, pills/badges 999px, checkbox 5–6px. Shadow: `0 1px 3px rgba(0,0,0,.06)`.

## Assets
None. ✓, ☆, ↗, ▾, ▸ are text glyphs; replace with the app's existing icon set if one exists.

## Files
- `Info Card Explorations.dc.html` — full design exploration. **Implement turn 3 (ids 3a, 3b, 3c, 3d)**; turns 1–2 are earlier iterations kept for reference. Open in a browser; all styles are inline on the elements, so exact values can be read directly from the markup.
