"""Snap a Tripo base-colour texture to a clean flat palette (removes halos, smears, pink cast, soft baked shading).

Each covered texel is classed to the nearest palette colour (CIELAB); 'keep' classes (glow, screens) stay as
painted; a majority filter inside each UV triangle region removes 1-3 px halos; region rules decide what skin
may exist (hands only), then UV gutters are refilled from their own island (push-pull) so bilinear/mip
sampling never pulls another island's colour across a seam.

usage: py -3 tex_palette.py --mesh <dir>/mesh.npz --tex <dir>/basecolor_orig.png --out <dir>
         [--palette palette.json] [--keep-above-z 0.80] [--mode-k 7]
mesh.npz comes from blender/tex_extract.py (normalized: height 1, feet 0, faces -Y).
palette.json: {"name": {"rgb": [r,g,b], "keep": false, "region": "any|hands"}, ...}
Writes basecolor_palette.png, labels.png (debug colours) and prints class shares.
"""
import argparse
import json
import os

import cv2
import numpy as np

DEFAULT = {
    "white": {"rgb": [234, 230, 228]},
    "orange": {"rgb": [234, 96, 36]},
    "orange_dark": {"rgb": [170, 70, 30], "snap_to": "orange"},
    "char": {"rgb": [62, 60, 66]},
    "char_dark": {"rgb": [44, 43, 48]},
    "steel": {"rgb": [88, 86, 90]},
    "grey": {"rgb": [142, 138, 140]},
    "blue": {"rgb": [106, 120, 156]},
    "skin": {"rgb": [184, 110, 78], "region": "hands"},
    "skin_lt": {"rgb": [226, 150, 112], "region": "hands", "snap_to": "skin"},
    "cream": {"rgb": [236, 222, 206]},
    "pink": {"rgb": [214, 188, 184], "snap_to": "white"},
    "green": {"rgb": [38, 135, 38], "keep": True},
    "green_hi": {"rgb": [30, 213, 29], "keep": True},
    "cyan": {"rgb": [40, 220, 230], "keep": True},
    "hair": {"rgb": [86, 51, 33], "region": "head"},
}


def lab(rgb):
    return cv2.cvtColor(np.asarray(rgb, np.uint8).reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)


def pushpull(img, w):
    if min(img.shape[:2]) <= 2 or w.min() > 0:
        return img
    h, wd = img.shape[:2]
    a = cv2.resize(img * w[..., None], ((wd + 1) // 2, (h + 1) // 2), interpolation=cv2.INTER_AREA)
    b = cv2.resize(w, ((wd + 1) // 2, (h + 1) // 2), interpolation=cv2.INTER_AREA)
    sm = np.where(b[..., None] > 1e-6, a / np.maximum(b[..., None], 1e-6), 0)
    coarse = pushpull(sm, (b > 1e-6).astype(np.float32))
    up = cv2.resize(coarse, (wd, h), interpolation=cv2.INTER_LINEAR)
    return np.where(w[..., None] > 0, img, up)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--tex", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--palette")
    ap.add_argument("--keep-above-z", type=float, default=0.80, help="texels of triangles above this height (head) stay as painted")
    ap.add_argument("--hand-x", type=float, default=0.17, help="hands: |x| beyond this ...")
    ap.add_argument("--hand-z", type=float, default=0.50, help="... and below this height")
    ap.add_argument("--mode-k", type=int, default=7, help="majority filter window (odd)")
    ap.add_argument("--speck-px", type=int, default=40, help="isolated islands smaller than this take their surround's class (0 = off)")
    a = ap.parse_args()

    pal = json.load(open(a.palette)) if a.palette else DEFAULT
    names = list(pal)
    P = lab([pal[n]["rgb"] for n in names])
    d = np.load(a.mesh)
    V, TI, TU = d["V"], d["TI"], d["TU"]
    img = cv2.imread(a.tex)[:, :, ::-1].copy()
    H, W = img.shape[:2]

    tri = np.full((H, W), -1, np.int32)
    for i in range(len(TU)):
        p = np.stack([TU[i, :, 0] % 1 * W, (1 - TU[i, :, 1] % 1) * H], 1)
        cv2.fillPoly(tri, [np.round(p * 16).astype(np.int32)], int(i), shift=4)
    cov = tri >= 0
    C = V[TI].mean(1)  # triangle centroids, normalized space
    cz = np.where(cov, C[np.maximum(tri, 0), 2], 0)
    cx = np.where(cov, np.abs(C[np.maximum(tri, 0), 0]), 0)
    head = cov & (cz > a.keep_above_z)
    hands = cov & (cx > a.hand_x) & (cz < a.hand_z)

    L = cv2.cvtColor(img, cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    allowed = np.ones((H * W, len(names)), bool)
    for k, n in enumerate(names):
        r = pal[n].get("region", "any")
        if r == "hands":
            allowed[:, k] = hands.ravel()
        elif r == "head":
            allowed[:, k] = head.ravel()
    dist = ((L[:, None, :] - P[None]) ** 2).sum(2)
    dist[~allowed] = 1e12
    lbl = dist.argmin(1).reshape(H, W).astype(np.int32)
    # snap_to: shading variants collapse onto their base class
    for k, n in enumerate(names):
        t = pal[n].get("snap_to")
        if t:
            lbl[lbl == k] = names.index(t)

    # majority filter, per class one-hot box sums; only over covered texels
    keep = np.zeros(len(names), bool)
    for k, n in enumerate(names):
        keep[k] = bool(pal[n].get("keep"))
    votes = np.zeros((H, W, len(names)), np.float32)
    for k in range(len(names)):
        m = ((lbl == k) & cov).astype(np.float32)
        votes[..., k] = cv2.boxFilter(m, -1, (a.mode_k, a.mode_k), normalize=False)
    maj = votes.argmax(2)
    # keep-classes (glow detail) are never voted away and never spread
    lbl2 = np.where(keep[lbl], lbl, np.where(keep[maj], lbl, maj))
    # specks: tiny isolated islands of one class (red dots, scribbles, stray orange in the backpack) take the
    # colour that surrounds them
    if a.speck_px > 0:
        kern = np.ones((5, 5), np.uint8)
        for k in range(len(names)):
            if keep[k]:
                continue
            m = ((lbl2 == k) & cov).astype(np.uint8)
            n, cc, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
            for c in range(1, n):
                if st[c, cv2.CC_STAT_AREA] >= a.speck_px:
                    continue
                x0, y0, w, h = st[c, :4]
                sl = (slice(max(y0 - 3, 0), y0 + h + 3), slice(max(x0 - 3, 0), x0 + w + 3))
                blob = (cc[sl] == c).astype(np.uint8)
                ring = (cv2.dilate(blob, kern) > 0) & (blob == 0) & cov[sl]
                if not ring.any():
                    continue
                vals = np.bincount(lbl2[sl][ring], minlength=len(names))
                vals[k] = 0
                if vals.max() == 0:
                    continue
                sub = lbl2[sl]
                sub[blob > 0] = vals.argmax()

    out = np.zeros_like(img)
    for k, n in enumerate(names):
        out[lbl2 == k] = pal[n]["rgb"]
    keepmask = keep[lbl2] | head | ~cov
    out[keepmask] = img[keepmask]
    # refill gutters from covered texels only (stop cross-island bleed)
    fill = pushpull(out.astype(np.float32), cov.astype(np.float32))
    out = np.where(cov[..., None], out, np.clip(fill, 0, 255)).astype(np.uint8)

    os.makedirs(a.out, exist_ok=True)
    cv2.imwrite(os.path.join(a.out, "basecolor_palette.png"), out[:, :, ::-1])
    dbg = np.zeros_like(img)
    for k, n in enumerate(names):
        dbg[lbl2 == k] = pal[n]["rgb"]
    dbg[~cov] = 0
    cv2.imwrite(os.path.join(a.out, "labels.png"), dbg[:, :, ::-1])
    tot = cov.sum()
    print("PALETTE", ", ".join(f"{n} {((lbl2 == k) & cov).sum() / tot:.3f}" for k, n in enumerate(names)))
    print("changed texels", float((np.abs(out.astype(int) - img.astype(int)).sum(2) > 30)[cov].mean()))


if __name__ == "__main__":
    main()
