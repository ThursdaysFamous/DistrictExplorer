# icons/source — provenance for derived marker art

This directory holds the full-resolution originals the runtime marker icons in
`icons/` are derived from. Like `data/source`, it is **excluded from the Pages
deploy** (see `.github/workflows/deploy-pages.yml`) — only the derived, right-sized
runtime asset ships.

## chicago-water-taxi-logo.jpg → ../water-taxi.png

`chicago-water-taxi-logo.jpg` is the Chicago Water Taxi seal as supplied: an
840×480 baseline JPEG (RGB, no alpha) with the circular logo centered on a
checkerboard "transparency" backdrop that was baked into the pixels.

`../water-taxi.png` is derived from it: the circular seal (center ≈ (420, 240),
radius ≈ 200 px) is cropped out, a circular alpha mask drops the checkerboard to
true transparency, and the result is downscaled to a crisp 128×128 PNG for use as
the selected-point map marker when a point lands on water.

To regenerate (requires Pillow):

```python
from PIL import Image, ImageDraw
im = Image.open('chicago-water-taxi-logo.jpg').convert('RGB')
cx, cy, r = 420, 240, 200
crop = im.crop((cx-r, cy-r, cx+r, cy+r)).convert('RGBA')
S, size, inset = 4, 400, 1
mask = Image.new('L', (size*S, size*S), 0)
ImageDraw.Draw(mask).ellipse((inset*S, inset*S, (size-inset)*S, (size-inset)*S), fill=255)
crop.putalpha(mask.resize((size, size), Image.LANCZOS))
crop.resize((128, 128), Image.LANCZOS).save('../water-taxi.png')
```

## County seals (`../seals/<county>.png`)

When the selected point is in a county but outside the City of Chicago, the
marker becomes that county's seal (see `selectPointMarker` in `index.html`,
keyed by the `COUNTY_SEAL_URLS` map). Counties with no seal shipped yet fall
back to a plain county-name badge — so seals are additive: drop a derived PNG in
`../seals/` and add one line to `COUNTY_SEAL_URLS`.

Ship **only cleanly-licensed** seals (public domain or an explicit free
license), and keep the full-resolution original here for provenance.

### cook-county-seal.svg → ../seals/cook-county.png

`cook-county-seal.svg` is the Seal of Cook County, Illinois from Wikimedia
Commons ([File:Seal of Cook County, Illinois.svg][cook]) — **public domain**
(the Commons record lists License: pd, Copyrighted: false, author "Cook
County"). `../seals/cook-county.png` is a 128×128 transparent-background
rasterization for use at map-marker scale.

[cook]: https://commons.wikimedia.org/wiki/File:Seal_of_Cook_County,_Illinois.svg

The repo has no SVG rasterizer (rsvg/inkscape/ImageMagick/cairosvg absent), but
Chromium is available via Playwright — regenerate by rendering the SVG in a
128×128 transparent viewport and screenshotting it:

```js
// node (from repo root, so playwright resolves): renders an SVG to a PNG
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
const size = 128, svg = readFileSync("icons/source/cook-county-seal.svg", "utf8");
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: size, height: size }, deviceScaleFactor: 1 });
await p.setContent(`<!doctype html><style>*{margin:0;padding:0}html,body{background:transparent}
  #b{width:${size}px;height:${size}px;display:flex;align-items:center;justify-content:center}
  #b svg{width:${size}px;height:${size}px}</style><div id="b">${svg}</div>`, { waitUntil: "networkidle" });
await (await p.$("#b")).screenshot({ path: "icons/seals/cook-county.png", omitBackground: true });
await b.close();
```
