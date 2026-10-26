"""Numeric self-check for model-sheet candidates (four-view) + head ruler crops + contact board.

usage:
  py -3 sheet_check.py --config char.json --view front  img1.png img2.png ...      # candidates (generation state)
  py -3 sheet_check.py --config char.json --final  front.png left.png back.png right.png   # after sheet_finalize.py
Options: --head HFRAC WFRAC (ruler crop size, default 0.3 0.6), --out DIR (default {out_dir}/check)

Gates (printed as PASS/FAIL per image; the decision is still: look at the contact board + head crops):
  candidate: bbox height 0.85-0.95 of canvas; 0 dark pixels in the 10 rows under the soles;
             front: >=3 mask segments on rows 0.45/0.48/0.50 (arms off the body);
             left: skin centroid offset/bbox width < -0.10 (faces image-left); right: > +0.10; back: |offset| < 0.03
  final:     corner mean == bg exactly, corner std == 0, bbox height == target_h_ratio +-0.005, dark under soles == 0
Head ratio (crown->chin / total) is NOT automated (hair ties, hats and tails fool every mask): read it on the ruler crop.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import load_cfg  # noqa: E402

ROWS = [0.45, 0.48, 0.50, 0.52, 0.55]


def segments(row):
    r = row.astype(np.int8)
    return int(r[0]) + int(np.sum(np.diff(r) == 1))


def measure(path, bg_target, thresh, hfrac, wfrac, outdir):
    img = Image.open(path).convert("RGB")
    a = np.asarray(img).astype(np.float32)
    h, w, _ = a.shape
    corners = [a[:20, :20], a[:20, -20:], a[-20:, :20], a[-20:, -20:]]
    cm = np.array([c.reshape(-1, 3).mean(0) for c in corners])
    cs = np.array([c.reshape(-1, 3).std(0) for c in corners])
    bg = cm.mean(0)
    mask = np.abs(a - bg).max(2) > thresh
    ys, xs = np.where(mask)
    if len(ys) == 0:
        return {"file": path, "error": "empty mask"}
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    segs = {f: segments(mask[int(round(f * h))]) for f in ROWS}
    sole = a[y1 + 1:min(h, y1 + 11)]
    dark = int((sole.max(2) < 8).sum()) if sole.size else 0
    bh, bw = y1 - y0 + 1, x1 - x0 + 1
    # ruler crop of the head
    m = int(bw * (1 - wfrac) / 2)
    cx0, cx1, cy0, cy1 = x0 + m, x1 - m, y0, y0 + int(bh * hfrac)
    crop = img.crop((cx0, cy0, cx1 + 1, cy1 + 1)).resize(((cx1 - cx0 + 1) * 2, (cy1 - cy0 + 1) * 2), Image.NEAREST)
    d = ImageDraw.Draw(crop)
    for yy in range(0, cy1 - cy0 + 1, 10):
        major = yy % 50 == 0
        d.line([(0, yy * 2), (40 if major else 16, yy * 2)], fill=(255, 0, 0), width=1)
        if major:
            d.text((44, yy * 2 - 6), f"{yy}px ({yy / bh:.3f}H)", fill=(255, 0, 0))
    os.makedirs(outdir, exist_ok=True)
    hp = os.path.join(outdir, os.path.splitext(os.path.basename(path))[0] + "-head.png")
    crop.save(hp)
    # facing: warm skin pixels in the band 12-20% below the bbox top
    fy0, fy1 = y0 + int(bh * 0.12), y0 + int(bh * 0.20)
    band = a[fy0:fy1]
    R, G, B = band[..., 0], band[..., 1], band[..., 2]
    skin = mask[fy0:fy1] & (R > G) & (G > B) & (R - B > 40)
    skin_n = int(skin.sum())
    off = float(np.where(skin)[1].mean() - (x0 + x1) / 2) / bw if skin_n else None
    return {"file": path, "size": [w, h], "corner_mean": cm.mean(0).round(2).tolist(),
            "corner_minus_bg": (cm.mean(0) - bg_target).round(2).tolist(), "corner_std_max": round(float(cs.max()), 3),
            "exact_bg_ratio": round(float((a == bg_target).all(2).mean()), 4),
            "bbox": [x0, y0, x1, y1], "bbox_h_ratio": round(bh / h, 4), "segments": segs,
            "dark_below_sole": dark, "skin_px": skin_n, "skin_offset_rel": None if off is None else round(off, 4),
            "head_crop": hp}


def gates(r, view, final, cfg):
    g = {}
    if final:
        s = cfg["sheet"]
        g["corners_exact_bg"] = max(abs(v) for v in r["corner_minus_bg"]) < 0.01 and r["corner_std_max"] < 0.01
        g["bbox_h"] = abs(r["bbox_h_ratio"] - s["target_h_ratio"]) <= 0.005
        g["no_floor_shadow"] = r["dark_below_sole"] == 0
        return g
    g["bbox_h_0.85_0.95"] = 0.85 <= r["bbox_h_ratio"] <= 0.95
    g["no_floor_shadow"] = r["dark_below_sole"] == 0
    if view == "front":
        g["arms_off_body"] = min(r["segments"][0.45], r["segments"][0.48], r["segments"][0.50]) >= 3
    o = r["skin_offset_rel"]
    if view == "left":
        g["faces_image_left"] = o is not None and o < -0.10
    if view == "right":
        g["faces_image_right"] = o is not None and o > 0.10
    if view == "back":
        g["back_symmetric"] = o is None or abs(o) < 0.03
    return g


def board(paths, outp, bg=(255, 255, 255)):
    ims = [Image.open(p).convert("RGB") for p in paths]
    ims = [im.resize((round(im.width * 1024 / im.height), 1024), Image.LANCZOS) for im in ims]
    b = Image.new("RGB", (sum(i.width for i in ims), 1048), bg)
    d = ImageDraw.Draw(b)
    x = 0
    for p, im in zip(paths, ims):
        b.paste(im, (x, 24))
        d.text((x + 6, 4), os.path.basename(p), fill=(0, 0, 0))
        x += im.width
    b.save(outp)
    return outp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--view", choices=["front", "left", "right", "back"])
    ap.add_argument("--final", action="store_true", help="images are front left back right finals")
    ap.add_argument("--head", nargs=2, type=float, default=[0.3, 0.6])
    ap.add_argument("--out")
    ap.add_argument("images", nargs="+")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    outdir = a.out or os.path.join(cfg["out_dir"], "check")
    views = ["front", "left", "back", "right"] if a.final else [a.view] * len(a.images)
    if not a.final and not a.view:
        ap.error("--view required for candidates")
    res, allpass = [], True
    for p, v in zip(a.images, views):
        r = measure(p, cfg["sheet"]["bg"], cfg["sheet"]["mask_thresh"], a.head[0], a.head[1], outdir)
        r["view"] = v
        r["gates"] = gates(r, v, a.final, cfg) if "error" not in r else {"readable": False}
        allpass &= all(r["gates"].values())
        res.append(r)
        print(f"== {os.path.basename(p)} [{v}] " + " ".join(f"{k}={'PASS' if ok else 'FAIL'}" for k, ok in r["gates"].items()))
        print("   " + json.dumps({k: r[k] for k in ("bbox_h_ratio", "corner_minus_bg", "segments", "dark_below_sole", "skin_offset_rel") if k in r}))
    tag = "final" if a.final else f"{a.view}"
    bp = board(a.images, os.path.join(outdir, f"{cfg['slug']}-{tag}-contact.png"))
    jp = os.path.join(outdir, f"{cfg['slug']}-{tag}-check.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, default=str)
    print("contact:", bp)
    print("json:", jp)
    print("ALL_NUMERIC_GATES", "PASS" if allpass else "FAIL", "(still open the contact board and head crops before picking)")


if __name__ == "__main__":
    main()
