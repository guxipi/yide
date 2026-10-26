"""Per-texel 3D position / normal / triangle map for a textured mesh (barycentric, not centroid), so texture fixes
can be written as 3D rules (stripes, seams, region masks) instead of hand-picking UV islands.

usage: py -3 tex_posmap.py --mesh <dir>/mesh.npz --size 2048 --out <dir>/posmap.npz
mesh.npz from blender/tex_extract.py (normalized: height 1, feet 0, x centred, faces -Y).
Output: tri (H,W) int32 (-1 = gutter), pos (H,W,3) float32, nrm (H,W,3) float32.
"""
import argparse

import numpy as np


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mesh", required=True)
    ap.add_argument("--size", type=int, default=2048)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = np.load(a.mesh)
    V, TI, TU, TN = d["V"], d["TI"], d["TU"], d["TN"]
    H = W = a.size
    tri = np.full((H, W), -1, np.int32)
    pos = np.zeros((H, W, 3), np.float32)
    nrm = np.zeros((H, W, 3), np.float32)
    P = np.stack([TU[..., 0] % 1 * W - 0.5, (1 - TU[..., 1] % 1) * H - 0.5], -1)  # pixel-centre coords
    for i in range(len(TI)):
        p = P[i]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, W - 1), min(y1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        ys, xs = np.mgrid[y0:y1 + 1, x0:x1 + 1]
        (ax, ay), (bx, by), (cx, cy) = p
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        w0 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        w1 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
        if not m.any():
            continue
        yy, xx = ys[m], xs[m]
        tri[yy, xx] = i
        pv = V[TI[i]]
        pos[yy, xx] = (w0[m, None] * pv[0] + w1[m, None] * pv[1] + w2[m, None] * pv[2])
        nrm[yy, xx] = TN[i]
    np.savez_compressed(a.out, tri=tri, pos=pos, nrm=nrm)
    print("POSMAP covered", float((tri >= 0).mean()), "->", a.out)


if __name__ == "__main__":
    main()
