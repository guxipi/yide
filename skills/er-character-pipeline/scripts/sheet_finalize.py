"""Finalize the chosen four views: flood-fill the background to exactly bg (only the region connected
to the canvas edge, so grey inside the character survives), crop the figure bbox, scale it to
target_h_ratio of the canvas, centre horizontally, soles on the same line. Writes a contact sheet.

usage:
  py -3 sheet_finalize.py --config char.json front=PATH left=PATH back=PATH right=PATH [--out DIR]
         [--hue-fix VIEW --hue-src LO HI --hue-target DEG]      optional: shift hue of pixels in [LO,HI] deg on VIEW
Defaults: out = {out_dir}/final, file names {slug}-tripo-{view}.png.
Before using --hue-fix, MEASURE: Wren's "too cyan" canister had the same hue as the side view - the
difference was saturation/value. Print HSV medians of both crops first (crop_compare.py --hsv).
After this run: sheet_check.py --final ... must print ALL_NUMERIC_GATES PASS.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import load_cfg  # noqa: E402

VIEWS = ("front", "left", "back", "right")


def hue_fix(img, lo, hi, target):
    hsv = np.asarray(img.convert("HSV")).astype(np.float32) / 255.0
    deg = hsv[..., 0] * 360
    mask = (deg >= lo) & (deg <= hi) & (hsv[..., 1] > 0.35) & (hsv[..., 2] > 0.35)
    if not mask.any():
        print("hue-fix: no pixels in range, skipped")
        return img
    delta = target - float(np.median(deg[mask]))
    sh = hsv.copy()
    sh[..., 0] = ((deg + delta) % 360) / 360
    rgb = np.asarray(Image.fromarray((sh * 255).round().clip(0, 255).astype(np.uint8), "HSV").convert("RGB")).astype(np.float32)
    wgt = np.asarray(Image.fromarray((mask * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2))).astype(np.float32)[..., None] / 255
    orig = np.asarray(img.convert("RGB")).astype(np.float32)
    print(f"hue-fix: {int(mask.sum())} px, delta {delta:.2f} deg")
    return Image.fromarray((orig * (1 - wgt) + rgb * wgt).round().clip(0, 255).astype(np.uint8))


def finalize(img, W, H, bg, thresh, target_h, top):
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    cm = np.array([c.reshape(-1, 3).mean(0) for c in (a[:20, :20], a[:20, -20:], a[-20:, :20], a[-20:, -20:])]).mean(0)
    near = np.abs(a - cm).max(2) <= thresh
    lab, _ = ndimage.label(near)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    bgm = np.isin(lab, edge[edge > 0])
    a[bgm] = bg
    ys, xs = np.where(~bgm)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    crop = Image.fromarray(a.astype(np.uint8)).crop((x0, y0, x1 + 1, y1 + 1))
    th = int(round(target_h * H))
    s = th / crop.height
    nw = round(crop.width * s)
    crop = crop.resize((nw, th), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (bg, bg, bg))
    canvas.paste(crop, (round(W / 2 - nw / 2), top))
    return canvas, {"src_bbox": [int(x0), int(y0), int(x1), int(y1)], "scale": round(s, 4)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out")
    ap.add_argument("--hue-fix", choices=VIEWS)
    ap.add_argument("--hue-src", nargs=2, type=float)
    ap.add_argument("--hue-target", type=float)
    ap.add_argument("picks", nargs="+", help="view=path for all four views")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    s = cfg["sheet"]
    W, H = s["size"]
    picks = dict(p.split("=", 1) for p in a.picks)
    missing = [v for v in VIEWS if v not in picks]
    if missing:
        raise SystemExit(f"missing views: {missing}")
    out = a.out or os.path.join(cfg["out_dir"], "final")
    os.makedirs(out, exist_ok=True)
    finals = []
    for v in VIEWS:
        im = Image.open(picks[v]).convert("RGB")
        if im.size != (W, H):
            raise SystemExit(f"{v}: size {im.size} != {(W, H)}")
        if a.hue_fix == v:
            im = hue_fix(im, a.hue_src[0], a.hue_src[1], a.hue_target)
        f, info = finalize(im, W, H, s["bg"], s["mask_thresh"], s["target_h_ratio"], s["top"])
        p = os.path.join(out, f"{cfg['slug']}-tripo-{v}.png")
        f.save(p)
        finals.append(f)
        print(v, p, info)
    ims = [im.resize((round(W * 1024 / H), 1024), Image.LANCZOS) for im in finals]
    b = Image.new("RGB", (sum(i.width for i in ims), 1024), (s["bg"],) * 3)
    x = 0
    for im in ims:
        b.paste(im, (x, 0))
        x += im.width
    cp = os.path.join(out, f"{cfg['slug']}-tripo-contact.png")
    b.save(cp)
    print("contact:", cp)
    print("next: py -3 sheet_check.py --config ... --final " + " ".join(os.path.join(out, f"{cfg['slug']}-tripo-{v}.png") for v in VIEWS))


if __name__ == "__main__":
    main()
