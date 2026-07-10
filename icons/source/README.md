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
