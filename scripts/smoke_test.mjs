// Headless boot + behaviour smoke test, run in CI on every pull request
// (.github/workflows/smoke-test.yml). Serves the real index.html and drives it
// in Chromium via Playwright — the check the README's "Validation" section
// describes and that OPTIMIZATION_PLAYBOOK item 5 asked to actually commit.
//
// It deliberately depends only on the app shell (Leaflet from its CDN) and the
// same-origin data/app/*.json files — never on the live district APIs, which
// are flaky/blocked in CI. The three no-API layers (school board, IL Supreme
// Court, Board of Review) are the deterministic ground truth.
//
// Run locally against a static server:
//     python3 -m http.server 8000 &
//     npm install playwright && node scripts/smoke_test.mjs
// Configure the URL with BASE_URL (default http://localhost:8000/).

import { chromium } from "playwright";
import { readFileSync, existsSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

// Vendored Leaflet fallback for sandboxed environments (e.g. Claude Code web),
// where the browser (Chromium) cannot reach cdnjs.cloudflare.com — it does not
// use the agent HTTPS proxy, so the request resets and the app never boots
// ("L is not defined"). scripts/vendor_leaflet.sh populates this dir via curl,
// which *can* reach the CDN through the proxy; when present we serve Leaflet
// same-origin below so the app boots. Absent (production, GitHub Actions CI)
// the browser loads Leaflet straight from the CDN exactly as before.
const VENDOR_DIR = join(dirname(fileURLToPath(import.meta.url)), "vendor", "leaflet");
const VENDORED_LEAFLET =
  existsSync(join(VENDOR_DIR, "leaflet.js")) && existsSync(join(VENDOR_DIR, "leaflet.css"))
    ? { js: readFileSync(join(VENDOR_DIR, "leaflet.js")), css: readFileSync(join(VENDOR_DIR, "leaflet.css")) }
    : null;
if (VENDORED_LEAFLET) console.log("  (serving Leaflet from scripts/vendor/leaflet — CDN unreachable in this env)");

const BASE = process.env.BASE_URL || "http://localhost:8000/";
// ==== GENERATED:BEGIN smoke-config ====
const POINT = "41.88250,-87.62850"; // downtown Loop — inside Cook County
const OFFLINE = ["school-board", "il-supreme-court", "ccbr"];
const EXPECT_DISTRICT = { "school-board": "12", "il-supreme-court": "1", "ccbr": "3" };
const NEGATIVE_POINT = "41.70000,-87.10000"; // Lake Michigan, Indiana waters — outside all three anchor layers
const EXPECT_LAYERS = 33; // 18 base + police-beat (#43) + school-site (#45) + ccpsa-district-council + ward-precinct + 6 statewide local-gov layers (county, township, municipality, school districts x3 — TIGERweb) + will-county-board (per-county, coverage-gated) — live-verified 2026-07
// ==== GENERATED:END smoke-config ====
// Anchor layers that declare a location-relevance test (mod.coverage) HIDE at
// an out-of-coverage point instead of reporting an empty card — this list
// mirrors the fork's coverage declarations in index.html (school-board is
// Chicago-scoped via chicagoCoverage; ccbr is Cook-scoped via
// cookCountyCoverage). il-supreme-court declares none and keeps the honest
// "no district here" empty state at the negative point.
const NEGATIVE_HIDDEN = ["school-board", "ccbr"];
const BOOT_TIMEOUT = 45000; // Leaflet CDN + first paint on a cold CI runner
const QUERY_TIMEOUT = 25000;

const failures = [];
function check(name, ok, detail) {
  console.log(`  ${ok ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  if (!ok) failures.push(name);
}

// Each check runs in its own context with service workers BLOCKED. The app's
// SW serves data/app/* cache-first and — critically — its requests are not
// interceptable by page.route, so an active SW would defeat the failure
// injection in check 3 (it did, flakily, on the first CI run). The SW is a
// delivery optimization, not what this behaviour test targets, so we take it
// out of the picture; the app's layer behaviour is identical without it.
async function booted(context, url, routeFn) {
  const page = await context.newPage();
  if (VENDORED_LEAFLET) {
    await page.route("**/cdnjs.cloudflare.com/**/leaflet.js", (r) =>
      r.fulfill({ status: 200, contentType: "application/javascript", body: VENDORED_LEAFLET.js }));
    await page.route("**/cdnjs.cloudflare.com/**/leaflet.css", (r) =>
      r.fulfill({ status: 200, contentType: "text/css", body: VENDORED_LEAFLET.css }));
  }
  if (routeFn) await routeFn(page);
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => !!window.ChiExplorer, null, { timeout: BOOT_TIMEOUT });
  return page;
}

// Wait for a layer card to finish loading, then return its normalized text.
async function cardText(page, id) {
  await page
    .waitForFunction(
      (cid) => {
        const el = document.getElementById("card-" + cid);
        return el && !el.querySelector(".loading-row") &&
          (el.querySelector(".result-fields") || el.querySelector(".state-empty") ||
           el.classList.contains("state-empty") || el.classList.contains("state-error") || el.querySelector(".state-error"));
      },
      id,
      { timeout: QUERY_TIMEOUT }
    )
    .catch(() => {});
  return page.evaluate((cid) => {
    const el = document.getElementById("card-" + cid);
    if (!el) return { text: "(no card)", error: true, empty: false };
    return {
      text: el.innerText.replace(/\s+/g, " ").trim(),
      error: el.classList.contains("state-error") || !!el.querySelector(".state-error"),
      empty: el.classList.contains("state-empty") || !!el.querySelector(".state-empty"),
    };
  }, id);
}

const browser = await chromium.launch();
try {
  // 1. App boots and registers every layer.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, BASE);
    check("app boots (window.ChiExplorer exported)", true);
    const n = await page.evaluate(
      () => document.querySelectorAll('input[type=checkbox][id^="toggle-"]').length
    );
    check(`${EXPECT_LAYERS} layers registered`, n === EXPECT_LAYERS, `found ${n}`);
    await context.close();
  }

  // 2. The three no-API layers classify a known point against known ground
  //    truth, fetched from data/app/*.json.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, `${BASE}#point=${POINT}&layers=${OFFLINE.join(",")}`);
    for (const id of OFFLINE) {
      const info = await cardText(page, id);
      const m = /District\s+(\S+)/i.exec(info.text);
      const got = m ? m[1] : null;
      check(
        `${id} classifies point (District ${EXPECT_DISTRICT[id]})`,
        !info.error && got === EXPECT_DISTRICT[id],
        info.text.slice(0, 70)
      );
    }
    // Bonus: the school-board card joins its externalized member roster.
    const board = await cardText(page, "school-board");
    check("school-board joins member roster", /Board member/i.test(board.text), board.text.slice(0, 70));

    // Bonus: moving the selection re-classifies correctly. This exercises the
    // incremental-restyle fast path (P7) — same layers on, new point — where
    // updateLayerHighlight only flips the old/new matched paths instead of
    // re-styling every path. 41.99,-87.66 is school-board district 4 (vs 12 at
    // the Loop point above), and the matched-region highlight must move with it.
    const moved = await page.evaluate(async () => {
      window.ChiExplorer.setSelectedPoint(41.99, -87.66);
      const el = document.getElementById("card-school-board");
      for (let i = 0; i < 100; i++) {
        if (el && !el.querySelector(".loading-row") && /District\s+4\b/i.test(el.innerText)) break;
        await new Promise((r) => setTimeout(r, 100));
      }
      const highlights = document.querySelectorAll("#map .chi-region-highlight").length;
      return { text: el ? el.innerText.replace(/\s+/g, " ").trim() : "(no card)", highlights };
    });
    check(
      "point move re-classifies (District 12 -> 4) and re-highlights",
      /District\s+4\b/i.test(moved.text) && moved.highlights >= 1,
      `${moved.text.slice(0, 60)} | highlights=${moved.highlights}`
    );

    // Bonus: toggling one layer off/on must NOT disturb the other active layers'
    // highlights (P8). The opacity rescale on a count change now skips layers that
    // already show a selection highlight (their faded/highlight fill is
    // count-independent) instead of re-running the full highlight for every layer,
    // so the survivors' matched regions must stay lit exactly through the toggle.
    // With all three offline layers on and a point selected, drop ccbr: its single
    // highlight leaves, the other two stay untouched (before-1); re-add it and the
    // count returns to baseline. Re-adding it also exercises P11: ccbr's Leaflet
    // layer graph is released on toggle-off and rebuilt from the cached geojson on
    // toggle-on — the highlight can only reappear (afterOn === before) if that
    // rebuild produced a working, highlightable overlay with no refetch.
    const toggled = await page.evaluate(async () => {
      const wait = (ms) => new Promise((r) => setTimeout(r, ms));
      const count = () => document.querySelectorAll("#map .chi-region-highlight").length;
      const box = document.getElementById("toggle-ccbr");
      const before = count();
      box.click(); // ccbr off
      await wait(150);
      const afterOff = count();
      box.click(); // ccbr back on
      for (let i = 0; i < 100; i++) { if (count() >= before) break; await wait(100); }
      return { before, afterOff, afterOn: count() };
    });
    check(
      "layer toggle preserves other layers' highlights (opacity rescale, P8)",
      toggled.before >= 2 && toggled.afterOff === toggled.before - 1 && toggled.afterOn === toggled.before,
      `before=${toggled.before} afterOff=${toggled.afterOff} afterOn=${toggled.afterOn}`
    );
    await context.close();
  }

  // 2b. The negative ground-truth point (from the worksheet: a point outside
  //     every anchor layer). Anchors that declare a location-relevance test
  //     (mod.coverage — see NEGATIVE_HIDDEN above) HIDE there: the toggle
  //     block is suppressed, the query is skipped, and the layers= permalink
  //     is left intact (hide-only — state.layersOn is never mutated). Anchors
  //     without a coverage test keep the honest empty state — "no district
  //     here" as a statement of fact, not an error and not a wrong district.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    // chicagoCoverage's fallback leg consults the community-area dataset
    // (Socrata) after an ERSB miss. On a black-holed network (the sandboxed
    // dev env) that rejection is slow — through the loader's route retries —
    // which stalls the hide verdict past this check's wait. Abort it so the
    // fallback's own catch ("stand on the first tiling's verdict") runs
    // deterministically fast in every environment; the verdict here is
    // identical either way — the negative point is outside both tilings.
    const page = await booted(context, `${BASE}#point=${NEGATIVE_POINT}&layers=${OFFLINE.join(",")}`, async (p) => {
      await p.route("**data.cityofchicago.org**", (r) => r.abort());
    });
    for (const id of OFFLINE) {
      if (NEGATIVE_HIDDEN.includes(id)) {
        const hidden = await page
          .waitForFunction((cid) => {
            const box = document.getElementById("toggle-" + cid);
            const block = box && box.closest(".layer-block");
            return block && block.hidden === true;
          }, id, { timeout: QUERY_TIMEOUT })
          .then(() => true, () => false);
        const hashKeepsLayer = await page.evaluate((cid) => location.hash.includes(cid), id);
        // assert the invariant directly, not just its hash reflection: hide
        // must never mutate state.layersOn (that's what keeps permalinks and
        // reappear-on-return working)
        const stillOn = await page.evaluate((cid) => window.ChiExplorer.state.layersOn[cid] === true, id);
        check(
          `${id} hides at the negative point (out of coverage, permalink intact)`,
          hidden && hashKeepsLayer && stillOn,
          `hidden=${hidden} permalink=${hashKeepsLayer} layersOn=${stillOn}`
        );
      } else {
        const info = await cardText(page, id);
        check(
          `${id} reports no district at the negative point`,
          info.empty && !info.error,
          info.text.slice(0, 70)
        );
      }
    }
    await context.close();
  }

  // 3. A failing data source degrades to that layer's error card + Retry, in
  //    isolation — the app's per-layer failure-isolation rule.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(
      context,
      `${BASE}#point=${POINT}&layers=school-board,ccbr`,
      (p) => p.route("**/data/app/school-board-districts.json", (r) => r.fulfill({ status: 503, body: "down" }))
    );
    await page
      .waitForFunction(
        () => {
          const el = document.getElementById("card-school-board");
          return el && el.classList.contains("state-error");
        },
        null,
        { timeout: QUERY_TIMEOUT }
      )
      .catch(() => {});
    const res = await page.evaluate(() => {
      const sb = document.getElementById("card-school-board");
      const other = document.getElementById("card-ccbr");
      return {
        errored: !!sb && sb.classList.contains("state-error"),
        hasRetry: !!sb && !!sb.querySelector(".retry-btn"),
        otherOk: !!other && !other.classList.contains("state-error") && /District/i.test(other.innerText),
      };
    });
    check("failed layer shows error card + Retry", res.errored && res.hasRetry);
    check("failure is isolated (other layer still classifies)", res.otherOk);
    await context.close();
  }

  // 4. Overlay-load failure with NO point selected still surfaces (R5 / item 7).
  //    Toggle a layer via the permalink before any point is picked and fail its
  //    boundary fetch — the card must show an error + Retry (un-hidden), not
  //    fail silently the way it used to on 15 of 18 layers.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(
      context,
      `${BASE}#layers=school-board`,
      (p) => p.route("**/data/app/school-board-districts.json", (r) => r.fulfill({ status: 503, body: "down" }))
    );
    await page
      .waitForFunction(
        () => {
          const el = document.getElementById("card-school-board");
          return el && el.classList.contains("state-error");
        },
        null,
        { timeout: QUERY_TIMEOUT }
      )
      .catch(() => {});
    const res = await page.evaluate(() => {
      const el = document.getElementById("card-school-board");
      return {
        pointSelected: !!(window.ChiExplorer && window.ChiExplorer.state.selectedPoint),
        errored: !!el && el.classList.contains("state-error"),
        hasRetry: !!el && !!el.querySelector(".retry-btn"),
        visible: !!el && getComputedStyle(el).display !== "none",
      };
    });
    check(
      "pre-point overlay failure surfaces (not silent)",
      !res.pointSelected && res.errored && res.hasRetry && res.visible,
      `point=${res.pointSelected} err=${res.errored} retry=${res.hasRetry} visible=${res.visible}`
    );
    await context.close();
  }

  // 5. Base-map tile failure surfaces an honest, dismissible banner (R6 / item
  //    16), instead of a silently gray map. Fail the CARTO tile CDN and assert
  //    the banner appears, then that dismissing it hides it.
  {
    const context = await browser.newContext({ serviceWorkers: "block" });
    const page = await booted(context, BASE, (p) =>
      // regex, not a glob: the tile host is `a.basemaps.cartocdn.com` (a dot,
      // not a slash, before `basemaps`), which a `**/basemaps…` glob misses.
      p.route(/basemaps\.cartocdn\.com/, (r) => r.fulfill({ status: 503, body: "down" }))
    );
    await page
      .waitForFunction(() => {
        const el = document.getElementById("tile-banner");
        return el && !el.hidden;
      }, null, { timeout: QUERY_TIMEOUT })
      .catch(() => {});
    const shown = await page.evaluate(() => {
      const el = document.getElementById("tile-banner");
      return !!el && !el.hidden;
    });
    let hiddenAfterDismiss = null;
    if (shown) {
      await page.click("#tile-banner-dismiss");
      hiddenAfterDismiss = await page.evaluate(() => {
        const el = document.getElementById("tile-banner");
        return !!el && el.hidden;
      });
    }
    check("tile failure shows dismissible banner", shown && hiddenAfterDismiss === true, `shown=${shown} hiddenAfterDismiss=${hiddenAfterDismiss}`);
    await context.close();
  }
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(`\n${failures.length} smoke check(s) failed: ${failures.join(", ")}`);
  process.exit(1);
}
console.log("\nAll smoke checks passed.");
