"""Side-by-side crop board (the review rule: every revision is compared on pixels with the previous one,
never ticked off against the prompt's intent).

usage:
  py -3 crop_compare.py --box x0 y0 x1 y1 --out board.png a.png b.png [c.png ...] [--scale 2] [--hsv]
  py -3 crop_compare.py --box x0 y0 x1 y1 --save-crop head_crop.png --size 1024 view.png   # crop for a head edit
--box is in pixels of each input (all inputs must share the canvas size), or fractions if all values <= 1.
--hsv prints median H(deg)/S/V of saturated pixels inside the box for each image (measure before "fixing" a colour).
--save-crop writes the box of the single input resized to --size x --size, and a .box.txt next to it for sheet_paste.py.
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import os

import numpy as np
from PIL import Image, ImageDraw


def box_px(box, w, h):
    if all(v <= 1.0 for v in box):
        return (int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h))
    return tuple(int(v) for v in box)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--box", nargs=4, type=float, required=True)
    ap.add_argument("--out")
    ap.add_argument("--scale", type=float, default=2.0)
    ap.add_argument("--hsv", action="store_true")
    ap.add_argument("--save-crop")
    ap.add_argument("--size", type=int, default=1024)
    ap.add_argument("images", nargs="+")
    a = ap.parse_args()
    if a.save_crop:
        im = Image.open(a.images[0]).convert("RGB")
        b = box_px(a.box, *im.size)
        im.crop(b).resize((a.size, a.size), Image.LANCZOS).save(a.save_crop)
        with open(os.path.splitext(a.save_crop)[0] + ".box.txt", "w") as f:
            f.write(",".join(map(str, b)))
        print("crop", a.save_crop, "box", b)
        return
    crops = []
    for p in a.images:
        im = Image.open(p).convert("RGB")
        b = box_px(a.box, *im.size)
        c = im.crop(b)
        if a.hsv:
            hsv = np.asarray(c.convert("HSV")).astype(np.float32) / 255
            m = (hsv[..., 1] > 0.2) & (hsv[..., 2] > 0.3)
            if m.any():
                print(f"{os.path.basename(p)}: H {np.median(hsv[..., 0][m]) * 360:.1f}deg S {np.median(hsv[..., 1][m]):.2f} V {np.median(hsv[..., 2][m]):.2f} (n={int(m.sum())})")
        crops.append((os.path.basename(p), c.resize((int(c.width * a.scale), int(c.height * a.scale)), Image.NEAREST)))
    if a.out:
        W = sum(c.width for _, c in crops) + 10 * (len(crops) - 1)
        Hh = max(c.height for _, c in crops) + 24
        bd = Image.new("RGB", (W, Hh), (255, 255, 255))
        d = ImageDraw.Draw(bd)
        x = 0
        for n, c in crops:
            bd.paste(c, (x, 24))
            d.text((x + 4, 6), n, fill=(0, 0, 0))
            x += c.width + 10
        bd.save(a.out)
        print("board", a.out)


if __name__ == "__main__":
    main()
