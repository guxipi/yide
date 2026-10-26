"""Silhouette agreement between two images of the same view (flat model sheet vs its structure reference, or two
candidate rounds). The structure reference must ONLY add volumetric shading - if sol moved the outline, Tripo
builds a different body than the texture sheet will paint.

usage: py -3 silhouette_iou.py --bg 138 --thresh 18 A.png B.png [--out diff.png]
Prints IOU and the bbox of both masks. Gate for a structure reference: IOU >= 0.93 (hair pulled off the cheeks
legitimately changes a few percent; much lower = re-generate). diff.png: red = only in A, green = only in B.
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
from PIL import Image
from scipy import ndimage


def mask(p, bg, th):
    a = np.asarray(Image.open(p).convert("RGB")).astype(np.float32)
    corners = np.array([c.reshape(-1, 3).mean(0) for c in (a[:20, :20], a[:20, -20:], a[-20:, :20], a[-20:, -20:])]).mean(0)
    near = np.abs(a - corners).max(2) <= th
    lab, _ = ndimage.label(near)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    return ~np.isin(lab, edge[edge > 0])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--bg", type=float, default=138)
    ap.add_argument("--thresh", type=float, default=18)
    ap.add_argument("--out")
    ap.add_argument("--gate", type=float, default=0.93)
    x = ap.parse_args()
    A, B = mask(x.a, x.bg, x.thresh), mask(x.b, x.bg, x.thresh)
    if A.shape != B.shape:
        raise SystemExit(f"size mismatch {A.shape} vs {B.shape}")
    iou = float((A & B).sum()) / max(1, float((A | B).sum()))
    bb = lambda m: (lambda ys, xs: (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))(*np.where(m))
    print(f"IOU {iou:.4f}  bboxA {bb(A)}  bboxB {bb(B)}  {'PASS' if iou >= x.gate else 'FAIL'} (gate {x.gate})")
    if x.out:
        v = np.zeros(A.shape + (3,), np.uint8)
        v[A & B] = (90, 90, 90)
        v[A & ~B] = (255, 0, 0)
        v[B & ~A] = (0, 255, 0)
        Image.fromarray(v).save(x.out)


if __name__ == "__main__":
    main()
