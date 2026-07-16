// Render an SVG seal to a square transparent PNG at map-marker scale, using the
// pre-installed Chromium via Playwright (the repo ships no SVG rasterizer). This
// is the same recipe documented in icons/source/README.md for the Cook County
// seal, generalized to take input/output/size on argv so it can be reused for
// every county seal we ship.
//
//   node scripts/render_seal_svg.mjs <in.svg> <out.png> [size=128]
import { chromium } from "playwright";
import { readFileSync } from "node:fs";

const [, , inPath, outPath, sizeArg] = process.argv;
if (!inPath || !outPath) {
  console.error("usage: node scripts/render_seal_svg.mjs <in.svg> <out.png> [size]");
  process.exit(2);
}
const size = parseInt(sizeArg || "128", 10);
const svg = readFileSync(inPath, "utf8");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
await page.setContent(
  `<!doctype html><style>*{margin:0;padding:0}html,body{background:transparent}
   #b{width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center}
   #b svg{width:${size}px;height:${size}px}</style><div id="b">${svg}</div>`,
  { waitUntil: "networkidle" }
);
await (await page.$("#b")).screenshot({ path: outPath, omitBackground: true });
await browser.close();
console.log("wrote", outPath, size + "x" + size);
