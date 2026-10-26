"""Two-row board: model-sheet views (top) vs model renders (bottom), same order, labelled.
Also any list of images as one labelled row (--row).

usage:
  py -3 compare_board.py --refs DIR_OR_PATTERN --renders DIR --out board.png [--ref-prefix wren-tripo-] [--render-prefix render_]
  py -3 compare_board.py --row a.png b.png c.png --out row.png [--h 512]
Views: front left back right. Missing images are drawn as a red box (missing = gate fail).
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import glob
import os

from PIL import Image, ImageDraw

VIEWS = ["front", "left", "back", "right"]


def find(d, prefix, v):
    if os.path.isdir(d):
        c = glob.glob(os.path.join(d, f"{prefix}{v}*.png"))
        return c[0] if c else None
    return None


def tile(p, h):
    if p and os.path.exists(p):
        im = Image.open(p).convert("RGB")
        return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    im = Image.new("RGB", (h * 2 // 3, h), (90, 0, 0))
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--refs")
    ap.add_argument("--renders")
    ap.add_argument("--ref-prefix", default="")
    ap.add_argument("--render-prefix", default="render_")
    ap.add_argument("--row", nargs="*")
    ap.add_argument("--out", required=True)
    ap.add_argument("--h", type=int, default=768)
    a = ap.parse_args()
    rows = []
    if a.row:
        rows.append([(os.path.basename(p), p) for p in a.row])
    else:
        rows.append([(f"sheet {v}", find(a.refs, a.ref_prefix, v)) for v in VIEWS])
        rows.append([(f"model {v}", find(a.renders, a.render_prefix, v)) for v in VIEWS])
    tiles = [[(n, tile(p, a.h)) for n, p in r] for r in rows]
    W = max(sum(t.width for _, t in r) for r in tiles)
    b = Image.new("RGB", (W, len(tiles) * (a.h + 24)), (255, 255, 255))
    d = ImageDraw.Draw(b)
    for ri, r in enumerate(tiles):
        x = 0
        for n, t in r:
            b.paste(t, (x, ri * (a.h + 24) + 24))
            d.text((x + 6, ri * (a.h + 24) + 6), n, fill=(0, 0, 0))
            x += t.width
    b.save(a.out)
    print("board", a.out, b.size)


if __name__ == "__main__":
    main()
