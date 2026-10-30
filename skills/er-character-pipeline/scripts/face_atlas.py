"""Build the 4x3 expression atlas from the face renders + sol expression edits, and check that sol only
changed the eyes/brows/mouth.

usage: py -3 face_atlas.py --config char.json [--dir FACE_DIR] [--proj face_projection.json]
Inputs in FACE_DIR: face_front.png (neutral, from face_render.py) and expr-<id>.png for every expression id in
cfg.face.expressions (order = atlas cell order, left->right, top->bottom, max 12).
Outputs: {Name}_face_atlas.png (2048x1152, cell 512x384), expr_contact.png (crops side by side, labelled),
         atlas.json (cell order + per-expression drift numbers).
Gate (per expression): sol repaints the WHOLE image, so pixel differences are everywhere and say nothing.
What matters is whether the face moved. The script measures the translation of each expression against
neutral by phase correlation on the crop box:
  |shift| <= 12 px -> registered (the crop window follows the measured shift, reported), PASS
  |shift|  > 12 px or size != 1024 -> FAIL, regenerate that expression from the CURRENT face_front.png
(Wren's accepted expressions measured 0.3-1.7 px x / 6.6-7.7 px y against a re-rendered base: the base had
been rendered with a slightly different camera. Re-using expressions across a re-render costs ~7 px.)
Then the main session looks at expr_contact.png: same painted style, eyes inside the sockets, mouth centred, no blush/
symbols, expressions read at a glance; closed-eye cells really closed.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import load_cfg, out_path  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--dir")
    ap.add_argument("--proj")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    d = a.dir or out_path(cfg, cfg["files"].get("face_dir", "face"))
    proj = json.load(open(a.proj or os.path.join(d, "face_projection.json"), encoding="utf-8"))
    x0, y0, x1, y1 = proj["crop"]
    cw, chh = proj["cell"]
    gx, gy = proj["grid"]
    bands = list(proj["feature_bands"].values())
    exprs = [e["id"] for e in cfg["face"]["expressions"]]
    std = ["neutral", "blink", "half", "grin", "happy", "smug", "jealous", "angry", "sad", "focus", "ko"]
    if exprs != std[:len(exprs)]:
        print("WARNING: expression ids/order differ from the controller enum " + ",".join(std) +
              " - Unity would show the wrong cell. Keep the 11 standard slots and only change each slot's description"
              " (an old character's 'grin' can be a small tight smile).")
    if len(exprs) > gx * gy:
        raise SystemExit("more expressions than atlas cells")
    files = {e: os.path.join(d, "face_front.png" if e == "neutral" else f"expr-{e}.png") for e in exprs}
    miss = [f for f in files.values() if not os.path.exists(f)]
    if miss:
        raise SystemExit(f"missing: {miss}")
    def grey(img):
        return cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY).astype(np.float32)[y0:y1, x0:x1]
    nimg = Image.open(files["neutral"]).convert("RGB")
    ng = grey(nimg)
    win = cv2.createHanningWindow((ng.shape[1], ng.shape[0]), cv2.CV_32F)
    atlas = Image.new("RGB", (gx * cw, gy * chh), (128, 128, 128))
    rep, ok, tiles = {}, True, []
    for i, e in enumerate(exprs):
        im = Image.open(files[e]).convert("RGB")
        r = {"size": list(im.size)}
        if im.size != (proj["res"], proj["res"]):
            r["gate"] = False
            ok = False
            rep[e] = r
            print(f"{e}: FAIL size {im.size}")
            continue
        (dx, dy), peak = (0.0, 0.0), 1.0
        if e != "neutral":
            (dx, dy), peak = cv2.phaseCorrelate(ng, grey(im), win)
        r["shift_px"] = [round(dx, 2), round(dy, 2)]
        r["peak"] = round(float(peak), 3)
        r["gate"] = abs(dx) <= 12 and abs(dy) <= 12
        ok &= r["gate"]
        rep[e] = r
        box = (x0 + dx, y0 + dy, x1 + dx, y1 + dy)
        cell = im.transform((x1 - x0, y1 - y0), Image.AFFINE, (1, 0, box[0], 0, 1, box[1]), resample=Image.BICUBIC).resize((cw, chh), Image.LANCZOS)
        atlas.paste(cell, ((i % gx) * cw, (i // gx) * chh))
        tiles.append((e, cell))
        print(f"{e}: {'PASS' if r['gate'] else 'FAIL'} shift {r['shift_px']} px (registered)")
    ap_ = os.path.join(d, f"{cfg['name']}_face_atlas.png")
    atlas.save(ap_)
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 340, rows * 280), (20, 20, 24))
    dr = ImageDraw.Draw(sheet)
    for i, (e, t) in enumerate(tiles):
        x, y = (i % cols) * 340, (i // cols) * 280
        sheet.paste(t.resize((336, 252)), (x, y))
        dr.text((x + 6, y + 256), e, fill=(240, 240, 240))
    sheet.save(os.path.join(d, "expr_contact.png"))
    json.dump({"order": exprs, "cells": {e: i for i, e in enumerate(exprs)}, "checks": rep}, open(os.path.join(d, "atlas.json"), "w"), indent=1, default=str)
    print("atlas", ap_)
    print("ATLAS_GATES", "PASS" if ok else "FAIL")


if __name__ == "__main__":
    main()
