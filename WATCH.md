# WATCH.md — redistricting watch calendar

The one place the dates live. `docs/REDISTRICTING_RUNBOOK.md` is *what to do* when a
boundary changes; this file is *when to look*. Keep it at repo root so it's the first thing
seen. Update the "Last done" column each time you complete a row — a checkpoint with a stale
date is a checkpoint that didn't happen.

Rule of thumb: **detection runs itself monthly; you run the CPS drill yearly; you open the
runbook per-layer whenever a map is enacted.** Everything below is just those three habits
pinned to dates so a trigger never catches you cold.

---

## Standing (already automated — verify, don't perform)

| Cadence | What | Where | You do |
|---|---|---|---|
| Monthly (1st, 14:00 UTC) | Source-freshness + redistricting-watch scan | `.github/workflows/validate-sources.yml` → single tracking issue on WARN/FAIL | Glance at the issue when it updates. A WARN = a trigger below may have fired. |

If that workflow isn't live yet, that's the prerequisite — see the runbook's "detection
layer" section. Until it runs, you're watching by hand, which is the failure mode.

---

## Yearly — the CPS drill (the load-bearing habit)

| When | What | Runbook steps | Last done |
|---|---|---|---|
| Late summer, when the new `SYxxyy` CPS attendance datasets post | Execute the response procedure against the rotated school-zone datasets as a live rehearsal | Steps 2–6, 10–11 | _(never)_ |

This is the only time the machinery gets exercised before it matters. If the drill is
painful, fix the runbook **that year**, not during the 2031 census scramble. A repo that has
run this three times will handle the decennial cycle; one that has only read the runbook
won't. Record the run in the runbook's drill-evidence habit and stamp the date above.

---

## Fixed checkpoints (put these on a real calendar)

| Date | Trigger | Action | Done |
|---|---|---|---|
| **2029 Q4** | Pre-cycle dry read | Re-read `docs/REDISTRICTING_RUNBOOK.md` against current code; confirm the per-layer inventory and appendix still match reality. Catches drift while it's calm. | ☐ |
| **2031 Q2** | P.L. 94-171 redistricting data delivered to states (statutory deadline ~Apr 1 2031; the 2020 cycle slipped to Aug/Sep — don't assume) | Begin active watch on congressional + state-legislative layers in every metro. State map-drawing starts now. | ☐ |
| **2031–2032** | State maps enacted, effective 2032 elections | Per-layer response procedure for Congress / IL Senate / IL House as each is enacted. Enacted ≠ effective — do the geometry work on enactment, keep showing current districts until the effective date. | ☐ |
| **2032–2033** | Municipal remaps | Response procedure for wards, commissioner, ERSB as each city body redraws. | ☐ |
| Rolling, post-enactment | Census TIGERweb publishes the new CD vintage | The monthly scan's CD119→CD121 watch should flag this; when it does, update the TIGERweb layer index + field alias per the runbook. | ☐ |
| Per-body, ad hoc | A districting commission / city council convenes to redraw | Open that layer's watch window; expect an enactment within the session. | ☐ |

---

## Off-cycle triggers (no date — stay alert)

Redistricting is **not** only decennial. Any of these fires the per-layer response procedure
immediately, regardless of where we are in the ten-year cycle:

- **Court order** — very common 2022–2024 (NY, AL, LA, GA congressional maps). NY had three
  congressional maps in three years.
- **Mid-decade partisan redraw** — the 2025–2026 wave (CA Prop 50, TX, OH, and others). If a
  state we cover joins it, act.
- **Administrative safety-layer reorg** — e.g. NYC's 116th Precinct (opened Dec 2024, carved
  from the 105th/113th). Police/fire districts change with no census.
- **Annual school-zone rotation** — the CPS drill above is the scheduled instance; NYC school
  zones rotate similarly.

When one fires: confirm enactment + effective date, then work **one layer at a time** through
`docs/REDISTRICTING_RUNBOOK.md` steps 1–14. Don't touch layers that didn't change.

---

## Per-metro note

This file is CHI's. Each sibling fork carries its own `WATCH.md` with its own municipal
bodies and enactment history (NYC: Districting Commission ~2032–2033, BOE election districts
which rotate frequently, NYPD precinct reorgs). The decennial and off-cycle framing is shared;
the layer rows are per-city. When Conversion 2 (generated docs) is live, the per-metro layer
rows can be emitted from each fork's `metro-worksheet.json` — until then, hand-maintained,
and this note is the reminder.
