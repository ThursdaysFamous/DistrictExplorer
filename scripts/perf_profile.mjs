// Chrome performance profiler for Chicago District Explorer — the reproducible
// harness behind docs/PERFORMANCE_ANALYSIS_2026-07.md. A companion to
// smoke_test.mjs (which gates *behaviour*); this one measures *performance*.
//
// It drives the real index.html in headless Chromium via Playwright + the
// Chrome DevTools Protocol and reports, all against the current working tree:
//   1. Cold-boot timing (median of N): FCP, time-to-app-ready, Chrome's own
//      ScriptDuration / RecalcStyle / Layout (Performance.getMetrics), long
//      tasks, JS heap, DOM nodes, and the boot resource waterfall.
//   2. Interaction paths, CPU-sampled (Profiler domain): click→classify, the
//      P7 incremental point-move, and cold vs warm layer toggles.
//   3. Footprint: JS heap / DOM nodes / SVG paths baseline vs three layers on,
//      and a pan-frame A/B that isolates the highlight drop-shadow cost (P9).
//   4. Pan/zoom reproject (the Round-3 canvas gate, §7): with the most same-
//      origin polygon paths reachable (anchors + pre-built legislative layers),
//      CPU-profile a pan and a zoom and compare pan-frame time at many vs few
//      paths — does SVG reproject dominate and scale with path count, or did
//      R2-5/R2-6 already flatten it? Decides whether canvas is worth the port.
//
// Like smoke_test.mjs it depends only on the app shell + the three same-origin
// no-API layers (school-board, il-supreme-court, ccbr) — never the live
// district APIs, which are flaky/blocked in CI and the sandbox. It serves the
// repo itself over a tiny gzip server (so transfer sizes mirror GitHub Pages)
// and, when scripts/vendor/leaflet is present (see vendor_leaflet.sh), serves
// Leaflet + a stub tile same-origin so the app boots without CDN egress.
//
//   bash scripts/vendor_leaflet.sh   # only needed in a CDN-blocked sandbox
//   node scripts/perf_profile.mjs    # writes perf-results.json + prints a summary
//
// NOTE ON ABSOLUTES: headless Chromium here rasterizes on software GL, so
// paint/pan wall-times are inflated vs real hardware. Boot script/compile,
// payload bytes, CPU-sample *shape*, and every A/B *ratio* are environment-
// independent; treat raw pan milliseconds as relative, not user-facing.

import { chromium } from "playwright";
import { createServer } from "http";
import { readFileSync, existsSync, writeFileSync } from "fs";
import { readFile as readFileP, stat as statP } from "fs/promises";
import { fileURLToPath } from "url";
import { dirname, join, extname, normalize } from "path";
import { gzipSync } from "zlib";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, "..");
const PORT = Number(process.env.PORT || 8137);
const BASE = `http://localhost:${PORT}/`;
const BOOT_RUNS = Number(process.env.BOOT_RUNS || 7);

// Ground truth mirrors smoke_test.mjs's GENERATED smoke-config (kept in sync by
// hand — this analysis tool isn't a generate_metro_files.py target, so no
// GENERATED region here). If the worksheet's anchor point/offline layers change,
// update these to match.
const POINT = "41.88250,-87.62850"; // downtown Loop — inside all three no-API layers
const OFFLINE = ["school-board", "il-supreme-court", "ccbr"];
const POINT2 = "41.99000,-87.66000"; // school-board D4 — the point-move target

const VDIR = join(REPO, "scripts", "vendor", "leaflet");
const LEAFLET = existsSync(join(VDIR, "leaflet.js")) && existsSync(join(VDIR, "leaflet.css"))
  ? { js: readFileSync(join(VDIR, "leaflet.js")), css: readFileSync(join(VDIR, "leaflet.css")) }
  : null;
if (LEAFLET) console.log("  (serving Leaflet from scripts/vendor/leaflet — CDN unreachable in this env)");
// 1x1 gray PNG for tiles (real CDN blocked in sandbox); keeps the map clean.
const TILE_PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC", "base64");

const median = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const max = (a) => Math.max(...a), min = (a) => Math.min(...a);
const r1 = (n) => Math.round(n * 10) / 10, r2 = (n) => Math.round(n * 100) / 100;

// ---- tiny gzip static server (mirrors GitHub Pages delivery) ----
const TYPES = { ".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8", ".mjs": "application/javascript; charset=utf-8", ".json": "application/json; charset=utf-8", ".css": "text/css; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml", ".webmanifest": "application/manifest+json", ".txt": "text/plain; charset=utf-8", ".xml": "application/xml" };
const GZIP = new Set([".html", ".js", ".mjs", ".json", ".css", ".svg", ".webmanifest", ".txt", ".xml"]);
function startServer(root, port) {
  const server = createServer(async (req, res) => {
    try {
      let path = decodeURIComponent(req.url.split("?")[0]);
      if (path === "/") path = "/index.html";
      const full = normalize(join(root, path));
      if (!full.startsWith(root)) { res.writeHead(403); res.end(); return; }
      const st = await statP(full).catch(() => null);
      if (!st || !st.isFile()) { res.writeHead(404); res.end(); return; }
      const ext = extname(full).toLowerCase();
      let body = await readFileP(full);
      const headers = { "Content-Type": TYPES[ext] || "application/octet-stream", "Cache-Control": "no-cache" };
      if ((req.headers["accept-encoding"] || "").includes("gzip") && GZIP.has(ext)) {
        body = gzipSync(body, { level: 9 }); headers["Content-Encoding"] = "gzip"; headers["Vary"] = "Accept-Encoding";
      }
      headers["Content-Length"] = body.length;
      res.writeHead(200, headers); res.end(body);
    } catch (e) { res.writeHead(500); res.end(String(e)); }
  });
  return new Promise((resolve) => server.listen(port, () => resolve(server)));
}

// Intercept every out-of-sandbox host; serve Leaflet + tiles locally, drop the rest.
async function wire(page) {
  if (LEAFLET) {
    await page.route(/cdnjs\.cloudflare\.com\/.*leaflet\.js/, (r) => r.fulfill({ status: 200, contentType: "application/javascript", body: LEAFLET.js }));
    await page.route(/cdnjs\.cloudflare\.com\/.*leaflet\.css/, (r) => r.fulfill({ status: 200, contentType: "text/css", body: LEAFLET.css }));
  }
  await page.route(/basemaps\.cartocdn\.com/, (r) => r.fulfill({ status: 200, contentType: "image/png", body: TILE_PNG }));
  await page.route(/fonts\.googleapis\.com|fonts\.gstatic\.com/, (r) => r.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.route(/gc\.zgo\.at|zgo\.at/, (r) => r.fulfill({ status: 200, contentType: "application/javascript", body: "" }));
  await page.route(/data\.cityofchicago\.org|arcgis|tigerweb|census\.gov|nominatim|photon\.komoot|cookcountyil/, (r) => r.abort());
}

// Boot-time observers, installed before any app script runs: capture the exact
// moment the app assigns window.ChiExplorer (end of the boot IIFE) and collect
// long tasks; expose a card-ready waiter for the interaction phases.
const INIT = `
  window.__lt = [];
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push({ start: e.startTime, dur: e.duration }); }).observe({ type: "longtask", buffered: true }); } catch (e) {}
  window.__readyTs = null;
  (function () { var _chi; Object.defineProperty(window, "ChiExplorer", { configurable: true,
    get: function () { return _chi; },
    set: function (v) { if (window.__readyTs === null) window.__readyTs = performance.now(); _chi = v; } }); })();
  window.__waitCards = async function (ids) {
    var done = function () { return ids.every(function (id) { var el = document.getElementById("card-" + id);
      return el && !el.querySelector(".loading-row") && (el.querySelector(".result-fields") || el.querySelector(".state-empty") ||
        el.classList.contains("state-empty") || el.classList.contains("state-error") || el.querySelector(".state-error")); }); };
    var t0 = performance.now();
    for (var i = 0; i < 300; i++) { if (done()) break; await new Promise(function (r) { setTimeout(r, 20); }); }
    return performance.now() - t0;
  };
`;

// Self time per node ≈ hitCount × samplingInterval; (idle)/(program)/(root) is
// the sampler catching the thread doing nothing real (async waits, CDP RPC) —
// excluded from "active CPU" so the number is JS work, not window length.
function aggregateProfile(profile, intervalUs) {
  const IDLE = new Set(["(idle)", "(program)", "(root)"]);
  const byFn = new Map();
  let activeUs = 0, idleUs = 0;
  for (const node of profile.nodes) {
    const self = (node.hitCount || 0) * intervalUs;
    if (!self) continue;
    const f = node.callFrame, name = f.functionName || "(anonymous)";
    if (IDLE.has(name)) { idleUs += self; continue; }
    activeUs += self;
    const loc = f.url ? `${f.url.split("/").pop()}:${f.lineNumber + 1}` : "(native)";
    byFn.set(`${name}@${loc}`, (byFn.get(`${name}@${loc}`) || 0) + self);
  }
  const top = [...byFn.entries()].map(([k, us]) => ({ fn: k, ms: r2(us / 1000), pct: activeUs ? Math.round((us / activeUs) * 100) : 0 }))
    .sort((a, b) => b.ms - a.ms).slice(0, 12);
  return { cpuActiveMs: r2(activeUs / 1000), cpuIdleMs: r2(idleUs / 1000), top };
}

async function profileInteraction(page, cdp, pageFn, arg) {
  const intervalUs = 100;
  await cdp.send("Profiler.enable");
  await cdp.send("Profiler.setSamplingInterval", { interval: intervalUs });
  await cdp.send("Profiler.start");
  const wallMs = await page.evaluate(pageFn, arg);
  const { profile } = await cdp.send("Profiler.stop");
  await cdp.send("Profiler.disable");
  return { wallMs: r2(wallMs), ...aggregateProfile(profile, intervalUs) };
}

const VIEWPORT = { width: 1280, height: 900 };
const newCtx = (browser) => browser.newContext({ serviceWorkers: "block", viewport: VIEWPORT });
async function bootPage(ctx) {
  const page = await ctx.newPage();
  await page.addInitScript(INIT);
  await wire(page);
  return page;
}

const results = { meta: {
  when: new Date().toISOString().slice(0, 19) + "Z", bootRuns: BOOT_RUNS, point: POINT, offlineLayers: OFFLINE,
  caveats: "Headless Chromium, software GL (no GPU raster) — absolute paint/pan times inflated; use A/B ratios. Live-API layers unreachable, so interactions use the three same-origin no-API layers. Boot script/compile + payload bytes are environment-independent.",
} };

const server = await startServer(REPO, PORT);
const browser = await chromium.launch({ args: ["--no-sandbox"] });
try {
  // ===== PHASE 1 — COLD BOOT (median of N) =====
  console.log(`\n[1/5] Cold boot × ${BOOT_RUNS} …`);
  const B = { ttReady: [], domContentLoaded: [], loadEvent: [], firstPaint: [], firstContentfulPaint: [], domInteractive: [],
    scriptDurationMs: [], v8CompileMs: [], recalcStyleMs: [], layoutMs: [], jsHeapMB: [], domNodes: [], jsEventListeners: [],
    longtaskCount: [], longtaskTotalMs: [], longtaskMaxMs: [] };
  let bootResources = null;
  for (let run = 0; run < BOOT_RUNS; run++) {
    const ctx = await newCtx(browser);
    const page = await bootPage(ctx);
    const cdp = await ctx.newCDPSession(page);
    await cdp.send("Performance.enable");
    await page.goto(BASE, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await page.waitForTimeout(300);
    const t = await page.evaluate(() => {
      const nav = performance.getEntriesByType("navigation")[0] || {};
      const paints = {}; for (const p of performance.getEntriesByType("paint")) paints[p.name] = p.startTime;
      return { ttReady: window.__readyTs, dcl: nav.domContentLoadedEventEnd, load: nav.loadEventEnd, di: nav.domInteractive,
        fp: paints["first-paint"] || 0, fcp: paints["first-contentful-paint"] || 0, lt: window.__lt || [] };
    });
    const m = Object.fromEntries((await cdp.send("Performance.getMetrics")).metrics.map((x) => [x.name, x.value]));
    if (run === 0) bootResources = await page.evaluate(() => performance.getEntriesByType("resource").map((r) => ({
      name: r.name.replace(location.origin, ""), type: r.initiatorType, transfer: r.transferSize, decoded: r.decodedBodySize, dur: Math.round(r.duration) })));
    B.ttReady.push(t.ttReady); B.domContentLoaded.push(t.dcl); B.loadEvent.push(t.load); B.domInteractive.push(t.di);
    B.firstPaint.push(t.fp); B.firstContentfulPaint.push(t.fcp);
    B.scriptDurationMs.push((m.ScriptDuration || 0) * 1000); B.v8CompileMs.push((m.V8CompileDuration || 0) * 1000);
    B.recalcStyleMs.push((m.RecalcStyleDuration || 0) * 1000); B.layoutMs.push((m.LayoutDuration || 0) * 1000);
    B.jsHeapMB.push((m.JSHeapUsedSize || 0) / 1048576); B.domNodes.push(m.Nodes || 0); B.jsEventListeners.push(m.JSEventListeners || 0);
    B.longtaskCount.push(t.lt.length); B.longtaskTotalMs.push(t.lt.reduce((s, x) => s + x.dur, 0)); B.longtaskMaxMs.push(t.lt.length ? max(t.lt.map((x) => x.dur)) : 0);
    process.stdout.write(`  run ${run + 1}: ready ${r1(t.ttReady)}  FCP ${r1(t.fcp)}  script ${r1((m.ScriptDuration || 0) * 1000)}  heap ${r1((m.JSHeapUsedSize || 0) / 1048576)}MB\n`);
    await cdp.detach(); await ctx.close();
  }
  const S = (a) => ({ median: r1(median(a)), min: r1(min(a)), max: r1(max(a)) });
  results.boot = { timeToAppReady_ms: S(B.ttReady), domContentLoaded_ms: S(B.domContentLoaded), loadEvent_ms: S(B.loadEvent),
    domInteractive_ms: S(B.domInteractive), firstPaint_ms: S(B.firstPaint), firstContentfulPaint_ms: S(B.firstContentfulPaint),
    scriptDuration_ms: S(B.scriptDurationMs), v8Compile_ms: S(B.v8CompileMs), recalcStyle_ms: S(B.recalcStyleMs), layout_ms: S(B.layoutMs),
    jsHeap_MB: S(B.jsHeapMB), domNodes: S(B.domNodes), jsEventListeners: S(B.jsEventListeners),
    longtask_count: S(B.longtaskCount), longtask_total_ms: S(B.longtaskTotalMs), longtask_max_ms: S(B.longtaskMaxMs) };
  results.bootResources = bootResources;

  // ===== PHASE 2 — INTERACTION (CPU profiled) =====
  console.log(`\n[2/5] Click→classify + point-move (CPU profiled) …`);
  {
    const ctx = await newCtx(browser); const page = await bootPage(ctx); const cdp = await ctx.newCDPSession(page);
    await page.goto(`${BASE}#layers=${OFFLINE.join(",")}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await page.waitForTimeout(1500);
    const firstClassify = await profileInteraction(page, cdp, async (a) => {
      const [lat, lng] = a.point.split(",").map(Number); const t0 = performance.now();
      window.ChiExplorer.setSelectedPoint(lat, lng); await window.__waitCards(a.ids); return performance.now() - t0;
    }, { point: POINT, ids: OFFLINE });
    const pointMove = await profileInteraction(page, cdp, async (a) => {
      const [lat, lng] = a.point.split(",").map(Number); const t0 = performance.now();
      window.ChiExplorer.setSelectedPoint(lat, lng);
      const el = document.getElementById("card-school-board");
      for (let i = 0; i < 300; i++) { if (el && !el.querySelector(".loading-row")) break; await new Promise((r) => setTimeout(r, 20)); }
      return performance.now() - t0;
    }, { point: POINT2 });
    // steady-state hops, all downtown (in-coverage) so no coverage-miss async skew
    const hops = [];
    for (const p of [POINT, "41.8900,-87.6300", "41.8750,-87.6250", "41.8950,-87.6350", "41.8800,-87.6280", POINT]) {
      const ms = await page.evaluate(async (pt) => {
        const [lat, lng] = pt.split(",").map(Number); const t0 = performance.now();
        window.ChiExplorer.setSelectedPoint(lat, lng);
        const el = document.getElementById("card-school-board");
        for (let i = 0; i < 300; i++) { if (el && !el.querySelector(".loading-row")) break; await new Promise((r) => setTimeout(r, 16)); }
        return performance.now() - t0;
      }, p);
      hops.push(r2(ms));
    }
    results.interaction = { firstClassify_wallMs: firstClassify.wallMs, firstClassify_cpuActiveMs: firstClassify.cpuActiveMs, firstClassify_topFns: firstClassify.top,
      pointMove_wallMs: pointMove.wallMs, pointMove_cpuActiveMs: pointMove.cpuActiveMs, pointMove_topFns: pointMove.top,
      repeatedHops_wallMs: hops, repeatedHops_median_ms: r2(median(hops)) };
    console.log(`  first classify ${firstClassify.wallMs}ms/${firstClassify.cpuActiveMs}ms-cpu; point-move ${pointMove.wallMs}ms/${pointMove.cpuActiveMs}ms-cpu; hops median ${r2(median(hops))}ms`);
    await cdp.detach(); await ctx.close();
  }

  // ===== PHASE 3 — LAYER TOGGLE (cold vs warm) =====
  console.log(`\n[3/5] Layer toggle latency …`);
  {
    const ctx = await newCtx(browser); const page = await bootPage(ctx); const cdp = await ctx.newCDPSession(page);
    await page.goto(`${BASE}#point=${POINT}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await page.waitForTimeout(400);
    const coldToggle = await profileInteraction(page, cdp, async () => {
      const box = document.getElementById("toggle-school-board"); const t0 = performance.now(); box.click();
      const el = document.getElementById("card-school-board");
      for (let i = 0; i < 400; i++) { if (el && !el.querySelector(".loading-row") && document.querySelectorAll("#map path").length > 2) break; await new Promise((r) => setTimeout(r, 10)); }
      return performance.now() - t0;
    }, null);
    const offT = [], onT = [];
    for (let i = 0; i < 5; i++) {
      offT.push(r2(await page.evaluate(async () => { const b = document.getElementById("toggle-school-board"); const t0 = performance.now(); b.click(); await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))); return performance.now() - t0; })));
      onT.push(r2(await page.evaluate(async () => { const b = document.getElementById("toggle-school-board"); const t0 = performance.now(); b.click(); for (let i = 0; i < 200; i++) { if (document.querySelectorAll("#map path").length > 2) break; await new Promise((r) => setTimeout(r, 8)); } return performance.now() - t0; })));
    }
    results.toggle = { coldToggleOn_wallMs: coldToggle.wallMs, coldToggleOn_cpuActiveMs: coldToggle.cpuActiveMs, coldToggleOn_topFns: coldToggle.top,
      warmToggleOff_ms: { median: r2(median(offT)), runs: offT }, warmToggleOn_ms: { median: r2(median(onT)), runs: onT } };
    console.log(`  cold toggle-on ${coldToggle.wallMs}ms/${coldToggle.cpuActiveMs}ms-cpu; warm off ${r2(median(offT))}ms on ${r2(median(onT))}ms`);
    await cdp.detach(); await ctx.close();
  }

  // ===== PHASE 4 — FOOTPRINT + pan A/B =====
  console.log(`\n[4/5] Footprint + pan A/B …`);
  {
    const ctxA = await newCtx(browser); const pageA = await bootPage(ctxA); const cdpA = await ctxA.newCDPSession(pageA);
    await cdpA.send("Performance.enable");
    await pageA.goto(BASE, { waitUntil: "domcontentloaded" });
    await pageA.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await pageA.waitForTimeout(600);
    const base = Object.fromEntries((await cdpA.send("Performance.getMetrics")).metrics.map((x) => [x.name, x.value]));
    const baseDom = await pageA.evaluate(() => ({ nodes: document.querySelectorAll("*").length, paths: document.querySelectorAll("#map path").length }));
    const layersRegistered = await pageA.evaluate(() => document.querySelectorAll('input[type=checkbox][id^="toggle-"]').length);
    await cdpA.detach(); await ctxA.close();

    const ctxB = await newCtx(browser); const pageB = await bootPage(ctxB); const cdpB = await ctxB.newCDPSession(pageB);
    await cdpB.send("Performance.enable");
    await pageB.goto(`${BASE}#point=${POINT}&layers=${OFFLINE.join(",")}`, { waitUntil: "domcontentloaded" });
    await pageB.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await pageB.evaluate((ids) => window.__waitCards(ids), OFFLINE);
    await pageB.waitForTimeout(1200);
    const loaded = Object.fromEntries((await cdpB.send("Performance.getMetrics")).metrics.map((x) => [x.name, x.value]));
    const dom = await pageB.evaluate(() => {
      const hi = [...document.querySelectorAll("#map .chi-region-highlight")];
      let filterPx = 0; for (const p of hi) { const b = p.getBoundingClientRect(); filterPx += Math.round(b.width * b.height); }
      let ds = 0; for (const s of document.styleSheets) { try { for (const r of s.cssRules) if (/drop-shadow/.test(r.cssText)) ds++; } catch (e) {} }
      return { nodes: document.querySelectorAll("*").length, mapPaths: document.querySelectorAll("#map path").length,
        svgEls: document.querySelectorAll("#map svg").length, highlights: hi.length, highlightFilterPx: filterPx, dropShadowRules: ds };
    });
    const panRun = () => pageB.evaluate(async () => {
      const frames = []; let last = performance.now(); const map = window.ChiExplorer && window.ChiExplorer.map;
      return await new Promise((resolve) => { let n = 0;
        function step() { const now = performance.now(); frames.push(now - last); last = now; if (map) map.panBy([6, 4], { animate: false }); if (++n < 60) requestAnimationFrame(step); else resolve(frames.slice(2)); }
        requestAnimationFrame(() => { last = performance.now(); requestAnimationFrame(step); }); });
    });
    const panOn = await panRun();
    await pageB.evaluate(() => { const s = document.createElement("style"); s.textContent = ".chi-region-highlight{filter:none !important;}"; document.head.appendChild(s); });
    await pageB.waitForTimeout(200);
    const panOff = await panRun();
    const panSorted = [...panOn].sort((a, b) => a - b);
    results.footprint = {
      baseline: { jsHeap_MB: r2(base.JSHeapUsedSize / 1048576), domNodes: base.Nodes, mapPaths: baseDom.paths },
      threeLayersOn: { jsHeap_MB: r2(loaded.JSHeapUsedSize / 1048576), domNodes: loaded.Nodes, mapPaths: dom.mapPaths, svgElements: dom.svgEls, highlightedRegions: dom.highlights, highlightFilterMegapixels: r2(dom.highlightFilterPx / 1e6) },
      layersRegistered, dropShadowCssRules: dom.dropShadowRules,
      deltaHeap_MB: r2((loaded.JSHeapUsedSize - base.JSHeapUsedSize) / 1048576), deltaNodes: loaded.Nodes - base.Nodes,
      panFrameTime_ms: { filterOn: { median: r2(median(panOn)), p95: r2(panSorted[Math.floor(panSorted.length * 0.95)] || 0), max: r2(max(panOn)) },
        filterOff: { median: r2(median(panOff)), max: r2(max(panOff)) },
        note: "software rendering inflates absolutes; the on-vs-off delta isolates the drop-shadow filter cost (P9)" } };
    console.log(`  heap ${r2(base.JSHeapUsedSize / 1048576)}→${r2(loaded.JSHeapUsedSize / 1048576)}MB, nodes ${base.Nodes}→${loaded.Nodes}, paths ${dom.mapPaths}, ${layersRegistered} layers registered`);
    console.log(`  pan frame filter-ON ${r2(median(panOn))}ms vs OFF ${r2(median(panOff))}ms`);
    await pageB.screenshot({ path: join(HERE, "..", "docs", "perf-app-screenshot.png") }).catch(() => {});
    await cdpB.detach(); await ctxB.close();
  }

  // ===== PHASE 5 — PAN/ZOOM REPROJECT (canvas gate, §7 R3 Phase 0) =====
  // Does SVG path reproject/repaint dominate pan/zoom, and scale with rendered
  // path count? Loads the SAME-ORIGIN polygon layers only (3 anchors + the 3
  // pre-built legislative layers — the most paths reachable without live APIs),
  // CPU-profiles a pan and a zoom, then compares pan-frame time at many vs few
  // paths. Leaflet reproject topping the CPU + many >> few => canvas (§7 Phase 1)
  // is justified; a flat profile => R2-5/R2-6 already handled it.
  console.log(`\n[5/5] Pan/zoom reproject (canvas gate) …`);
  {
    const MANY = ["school-board", "il-supreme-court", "ccbr", "congress", "il-senate", "il-house"];
    const LEGIS = ["congress", "il-senate", "il-house"];
    const ctx = await newCtx(browser); const page = await bootPage(ctx); const cdp = await ctx.newCDPSession(page);
    await page.goto(`${BASE}#point=${POINT}&layers=${MANY.join(",")}`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => window.__readyTs !== null, null, { timeout: 45000 });
    await page.evaluate((ids) => window.__waitCards(ids), MANY);
    await page.waitForTimeout(800); // let every overlay paint its paths
    const pathsMany = await page.evaluate(() => document.querySelectorAll("#map path").length);

    // panBy shifts the pane transform + repaints; setZoom reprojects EVERY path
    // (the canvas-sensitive worst case). Both CPU-sampled so the top frames show
    // whether Leaflet reproject (_update / project / _updatePath / pointsToPath)
    // leads the work — the signal that canvas would remove.
    const panProf = await profileInteraction(page, cdp, async () => {
      const map = window.ChiExplorer.map; const t0 = performance.now();
      for (let i = 0; i < 40; i++) { map.panBy([8, 5], { animate: false }); await new Promise((r) => requestAnimationFrame(r)); }
      return performance.now() - t0;
    }, null);
    const zoomProf = await profileInteraction(page, cdp, async () => {
      const map = window.ChiExplorer.map; const z0 = map.getZoom(); const t0 = performance.now();
      for (let i = 0; i < 6; i++) { map.setZoom(z0 + 1, { animate: false }); map.setZoom(z0, { animate: false }); await new Promise((r) => requestAnimationFrame(r)); }
      return performance.now() - t0;
    }, null);

    const panFrames = () => page.evaluate(async () => {
      const map = window.ChiExplorer.map; const frames = []; let last = performance.now();
      return await new Promise((resolve) => { let n = 0;
        function step() { const now = performance.now(); frames.push(now - last); last = now; map.panBy([6, 4], { animate: false }); if (++n < 50) requestAnimationFrame(step); else resolve(frames.slice(2)); }
        requestAnimationFrame(() => { last = performance.now(); requestAnimationFrame(step); }); });
    });
    const panMany = await panFrames();
    // drop the 3 legislative layers -> back to the ~28 anchor paths (the scaling A/B)
    await page.evaluate((ids) => ids.forEach((id) => { const b = document.getElementById("toggle-" + id); if (b && b.checked) b.click(); }), LEGIS);
    await page.waitForTimeout(500);
    const pathsFew = await page.evaluate(() => document.querySelectorAll("#map path").length);
    const panFew = await panFrames();

    const p95 = (a) => { const s = [...a].sort((x, y) => x - y); return r2(s[Math.floor(s.length * 0.95)] || 0); };
    const perPathUs = pathsMany > pathsFew ? r2((median(panMany) - median(panFew)) / (pathsMany - pathsFew) * 1000) : null; // marginal µs/path/frame
    results.panZoomReproject = {
      pathsMany, pathsFew,
      pan_cpuActiveMs: panProf.cpuActiveMs, pan_wallMs: panProf.wallMs, pan_topFns: panProf.top,
      zoom_cpuActiveMs: zoomProf.cpuActiveMs, zoom_wallMs: zoomProf.wallMs, zoom_topFns: zoomProf.top,
      panFrame_manyPaths_ms: { median: r2(median(panMany)), p95: p95(panMany), max: r2(max(panMany)) },
      panFrame_fewPaths_ms: { median: r2(median(panFew)), p95: p95(panFew), max: r2(max(panFew)) },
      panFrame_marginal_us_per_path: perPathUs,
      note: "Same-origin polygon layers only (no live APIs). Software GL inflates absolute frame ms — the many-vs-few ratio and the CPU top-fn shape are the environment-independent signals. Reproject leading pan/zoom CPU + many >> few => canvas (§7 Phase 1) justified; a flat profile => R2-5/R2-6 already handled it.",
    };
    console.log(`  paths ${pathsMany} (few ${pathsFew}); pan ${panProf.cpuActiveMs}ms-cpu, zoom ${zoomProf.cpuActiveMs}ms-cpu`);
    console.log(`  pan-frame many ${r2(median(panMany))}ms vs few ${r2(median(panFew))}ms (median); marginal ${perPathUs}µs/path`);
    console.log(`  pan top: ${panProf.top.slice(0, 3).map((t) => `${t.fn} ${t.ms}ms`).join(" | ")}`);
    console.log(`  zoom top: ${zoomProf.top.slice(0, 3).map((t) => `${t.fn} ${t.ms}ms`).join(" | ")}`);
    await cdp.detach(); await ctx.close();
  }

  const out = join(REPO, "perf-results.json");
  writeFileSync(out, JSON.stringify(results, null, 2));
  console.log(`\n✅ Wrote ${out}`);
} finally {
  await browser.close();
  server.close();
}
