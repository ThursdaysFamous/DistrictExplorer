#!/usr/bin/env python3
"""Convert a raster seal image (PNG/JPG/GIF/WEBP) to a 128x128 transparent PNG at
map-marker scale, matching the SVG pipeline (scripts/render_seal_svg.mjs) so every
county seal ships at the same size the marker CSS expects.

The county-seal marker (index.html makeCountySealDivIcon) draws the image on a
42px white circle and clips it round (border-radius:50%), so a seal that already
sits on a white/near-white field looks cleanest with that field knocked out to
transparency — pass --knockout to do that (tolerance-based flood from the border
is avoided; we use a simple near-white alpha so we never eat white *inside* the
seal art). Without --knockout the source is only fit + centered (safe default).

  python3 scripts/convert_raster_seal.py <in> <out.png> [--knockout] [--trim] [--size N]
"""
import sys, argparse
from PIL import Image, ImageChops

def autotrim(im):
    """Trim a uniform border (whatever the corner pixel is) so the seal fills the frame."""
    rgb = im.convert("RGB")
    bg = Image.new("RGB", im.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, bg)
    bbox = diff.getbbox()
    return im.crop(bbox) if bbox else im

def knockout_white(im, thresh=238):
    """Make near-white pixels transparent. Conservative threshold so colored seal
    art is untouched; only the surrounding white field drops out."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= thresh and g >= thresh and b >= thresh:
                px[x, y] = (r, g, b, 0)
    return im

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--knockout", action="store_true")
    ap.add_argument("--trim", action="store_true")
    ap.add_argument("--size", type=int, default=128)
    a = ap.parse_args()

    im = Image.open(a.inp)
    # GIF/palette → RGBA (preserve any transparency)
    im = im.convert("RGBA")
    if a.trim:
        im = autotrim(im)
    if a.knockout:
        im = knockout_white(im)

    # fit within size×size preserving aspect, center on transparent canvas
    S = a.size
    im.thumbnail((S, S), Image.LANCZOS)
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    canvas.paste(im, ((S - im.width) // 2, (S - im.height) // 2), im)
    canvas.save(a.out)
    print(f"wrote {a.out} {S}x{S} (from {a.inp})")

if __name__ == "__main__":
    main()
