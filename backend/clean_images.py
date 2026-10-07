"""Make web copies of product photos with a white background.

74 of the 102 catalogue photos were exported with a solid black background
(or black side bars). On the white store design those look like black boxes.
This flood-fills near-black pixels *connected to the image border* with white,
so the garment itself (even a navy one) is untouched, and writes the result to
data/products_web/. Originals in data/products/ are never modified.

Run from backend/:
    ../.venv/bin/python clean_images.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from db import DATA_DIR, PRODUCTS_DIR

WEB_DIR = DATA_DIR / "products_web"
BLACK_MAX = 10  # a pixel counts as background if every channel is <= this
FILL_THRESH = 12  # flood-fill tolerance; higher values leak into very dark navy garments


HOLE_MAX = 8  # enclosed background must be (near) pure black
HOLE_MIN_AREA = 150  # ...and at least this many pixels, so tiny dark details are kept
HOLE_MAX_FRACTION = 0.012  # measured: real gaps <= 0.92% of the photo; shadow damage was 1.7%


def _count(im: Image.Image, color: tuple) -> int:
    return sum(1 for p in im.getdata() if p == color)


def _region_size(im: Image.Image, x: int, y: int, cap: int) -> int:
    """Size of the near-black region around (x, y), counting up to `cap`."""
    px, (w, h) = im.load(), im.size
    seen, stack = {(x, y)}, [(x, y)]
    while stack and len(seen) < cap:
        cx, cy = stack.pop()
        for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and max(px[nx, ny]) <= HOLE_MAX + 4:
                seen.add((nx, ny))
                stack.append((nx, ny))
    return len(seen)


def is_black_background(im: Image.Image) -> bool:
    w, h = im.size
    edge = [im.getpixel((x, y)) for x in range(0, w, 4) for y in (0, h - 1)]
    edge += [im.getpixel((x, y)) for y in range(0, h, 4) for x in (0, w - 1)]
    return sum(max(p) <= BLACK_MAX for p in edge) / len(edge) > 0.5


def whiten_background(im: Image.Image) -> Image.Image:
    w, h = im.size
    # Flood-fill a marker colour from every dark border pixel, then turn the marker white.
    marker = (255, 0, 255)
    work = im.copy()
    for x in range(0, w, 3):
        for y in (0, h - 1):
            if max(work.getpixel((x, y))) <= BLACK_MAX:
                ImageDraw.floodfill(work, (x, y), marker, thresh=FILL_THRESH)
    for y in range(0, h, 3):
        for x in (0, w - 1):
            if max(work.getpixel((x, y))) <= BLACK_MAX:
                ImageDraw.floodfill(work, (x, y), marker, thresh=FILL_THRESH)

    # Background trapped between arms and body isn't connected to the border. Fill
    # enclosed regions too, but only if they're pure black and big (dark navy fabric is never <= 8).
    holes = work.copy()
    px = holes.load()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            if max(px[x, y]) <= HOLE_MAX and _region_size(holes, x, y, HOLE_MIN_AREA) >= HOLE_MIN_AREA:
                ImageDraw.floodfill(holes, (x, y), marker, thresh=FILL_THRESH)
    # Real underarm gaps are <1% of the photo. More than that means we hit deep fabric
    # shadows (e.g. the very dark Basic Hoodie), so keep the border-only result.
    added = _count(holes, marker) - _count(work, marker)
    if added <= HOLE_MAX_FRACTION * w * h:
        work = holes

    # Mask of filled pixels, slightly grown + softened to hide JPEG fringe at the garment edge.
    mask = Image.new("L", (w, h), 0)
    src, dst = work.load(), mask.load()
    for y in range(h):
        for x in range(w):
            if src[x, y] == marker:
                dst[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    return Image.composite(Image.new("RGB", (w, h), (255, 255, 255)), im, mask)


def main() -> None:
    WEB_DIR.mkdir(exist_ok=True)
    cleaned = copied = 0
    for path in sorted(PRODUCTS_DIR.glob("*.jpg")):
        im = Image.open(path).convert("RGB")
        if is_black_background(im):
            whiten_background(im).save(WEB_DIR / path.name, quality=90)
            cleaned += 1
        else:
            im.save(WEB_DIR / path.name, quality=90)
            copied += 1
    print(f"{cleaned} photos cleaned, {copied} already white -> {WEB_DIR}")


if __name__ == "__main__":
    main()
