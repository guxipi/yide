"""Paste an edited crop (e.g. a re-drawn head) back into the full view with a feathered edge.

usage: py -3 sheet_paste.py --base view.png --crop edited.png --box x0 y0 x1 y1 --out view_new.png [--feather 12]
The box is the one crop_compare.py --save-crop wrote into <crop>.box.txt. Afterwards re-run
sheet_finalize.py (background/alignment) and put old/new side by side with crop_compare.py.
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PIL import Image, ImageDraw, ImageFilter


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--crop", required=True)
    ap.add_argument("--box", nargs=4, type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--feather", type=int, default=12)
    a = ap.parse_args()
    base = Image.open(a.base).convert("RGB")
    x0, y0, x1, y1 = a.box
    c = Image.open(a.crop).convert("RGB").resize((x1 - x0, y1 - y0), Image.LANCZOS)
    m = Image.new("L", c.size, 0)
    f = a.feather
    ImageDraw.Draw(m).rectangle([f, f, c.width - 1 - f, c.height - 1 - f], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(f / 2))
    base.paste(c, (x0, y0), m)
    base.save(a.out)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
