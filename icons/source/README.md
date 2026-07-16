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

### Statewide county-seal batch → ../seals/*.png

The one-off Cook recipe above is now packaged into two reusable operator tools so
the `COUNTY_SEAL_URLS` map can grow without hand-writing render code each time:

- **SVG** originals → `node scripts/render_seal_svg.mjs <in.svg> <out.png> 128`
  (the recipe above, generalized; reproduces `cook-county.png` byte-for-byte).
- **Raster** originals (PNG/JPG/GIF/WEBP) → `python3 scripts/convert_raster_seal.py
  <in> <out.png> [--trim] [--knockout]` (Pillow: fit + centre on transparent 128×128;
  `--trim` drops a uniform border, `--knockout` clears a near-white field).

Each source below was pulled from Wikimedia Commons and is **cleanly licensed**
(public domain or an explicit free license). The full-resolution original is kept
here (as `<slug>-seal.<ext>`); only the derived `../seals/<slug>.png` ships. Every
image was hand-checked to be the correct county's seal before wiring it into
`COUNTY_SEAL_URLS`.

| County | Runtime PNG | Source (Wikimedia Commons) | License | Author / attribution |
|---|---|---|---|---|
| Hamilton | `../seals/hamilton.png` | [Seal of Hamilton County, Illinois.svg][s-hamilton] | Public domain | Unknown author |
| Kane | `../seals/kane.png` | [Seal of Kane County.jpg][s-kane] | Public domain | Unknown author |
| Lake | `../seals/lake.png` | [Seal of Lake County, Illinois.svg][s-lake] | Public domain | Randy Young (logo); SVG by Jack Ryan Morris; derivative by Flagvisioner |
| Macon | `../seals/macon.png` | [Seal of Macon County, Illinois.png][s-macon] | Public domain | Macon County, Illinois |
| Saline | `../seals/saline.png` | [Seal of Saline County, Illinois.svg][s-saline] | Public domain | Illinois Secretary of State |
| St. Clair | `../seals/st-clair.png` | [St Clair County IL Seal.svg][s-stclair] | CC BY-SA 4.0 | LBDesigns |
| Washington | `../seals/washington.png` | [Wash Co IL Seal in Color and Higher Quality.png][s-washington] | CC BY-SA 4.0 | Mrostrichman |
| Will | `../seals/will.png` | [Seal of Will County, Illinois.gif][s-will] | CC BY-SA 4.0 | AsburyWyatt |

The three **CC BY-SA 4.0** seals (St. Clair, Washington, Will) carry an
attribution + share-alike obligation: the author is credited above and the derived
PNG is offered under the same CC BY-SA 4.0 as its source. The rest are public
domain (no obligation). The Hamilton source filename misspells the county as
"Hamilon" on Commons — the seal art itself reads "Hamilton County."

`Seal of Lake County` and `Wash Co IL Seal` are square-format official seals;
they render correctly but the round marker (`border-radius:50%`) trims their
corners at display scale — the emblem stays recognizable.

The counties **not** yet covered — and why (mostly non-free/fair-use seals on
Wikipedia, or no seal image online at all) — are tracked in
[`docs/COUNTY_SEALS_REVIEW.md`](../../docs/COUNTY_SEALS_REVIEW.md).

[s-hamilton]: https://commons.wikimedia.org/wiki/File:Seal_of_Hamilon_County,_Illinois.svg
[s-kane]: https://commons.wikimedia.org/wiki/File:Seal_of_Kane_County.jpg
[s-lake]: https://commons.wikimedia.org/wiki/File:Seal_of_Lake_County,_Illinois.svg
[s-macon]: https://commons.wikimedia.org/wiki/File:Seal_of_Macon_County,_Illinois.png
[s-saline]: https://commons.wikimedia.org/wiki/File:Seal_of_Saline_County,_Illinois.svg
[s-stclair]: https://commons.wikimedia.org/wiki/File:St_Clair_County_IL_Seal.svg
[s-washington]: https://commons.wikimedia.org/wiki/File:Wash_Co_IL_Seal_in_Color_and_Higher_Quality.png
[s-will]: https://commons.wikimedia.org/wiki/File:Seal_of_Will_County,_Illinois.gif
