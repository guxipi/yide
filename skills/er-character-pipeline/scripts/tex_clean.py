"""Clean dirty skin patches in a Tripo base-colour texture (areas the four views never showed, e.g. the
underside / inside of the arms, get grey-brown smudges).

Pipeline (ported from the Wren gen-1 cleanup, 2026-10-07):
  1. classify triangles as SKIN by their mean colour in CIELAB (hue 35-62 deg, chroma > 30, L > 40), absorb
     small non-skin islands enclosed by skin, and grow skin into adjacent dark grey/brown triangles in the arm zone
     (the smudge itself fails the skin colour test);
  2. never touch protected areas: everything above --protect-z (head/face paint) and the hands;
  3. on skin texels, flag DIRT = darker than the local skin reference by > max(k*MAD, dmin) AND greyer than
     skin of that lightness should be (chroma/L below the expected curve); grow weak flags around strong seeds;
  4. fill flagged texels with push-pull inpainting from clean skin + transplanted high-pass detail from the nearest
     clean patch, feathered; never write across non-skin triangles (2-texel guard).
Outputs: <out>/basecolor_clean.png (same size as input), <out>/dirt_flags.png (magenta = filled, 2048 px),
<out>/tex_clean.json (pixel counts, coverage).

usage: py -3 tex_clean.py --mesh mesh.npz --tex basecolor_orig.png --out DIR [--dry] [--protect-z 0.76]
Gate: open dirt_flags.png - magenta only on skin smudges (not on clothes, eyes, mouth, hand creases); then render
the model with the clean texture (render_views.py / arm close-ups) next to the original. Coverage > 15% of skin
texels means the rule caught real paint: stop and tighten thresholds.
"""
import argparse
import json
import os

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

Image.MAX_IMAGE_PIXELS = None


def face_colours(TU, img):
    H, W = img.shape[:2]
    B = np.array([[1/3, 1/3, 1/3], [.6, .2, .2], [.2, .6, .2], [.2, .2, .6], [.45, .45, .1], [.45, .1, .45], [.1, .45, .45]])
    uv = np.einsum("kj,njc->nkc", B, TU)
    px = np.clip((uv[..., 0] % 1 * W).astype(int), 0, W - 1)
    py = np.clip(((1 - uv[..., 1] % 1) * H).astype(int), 0, H - 1)
    return img[py, px].astype(np.float32).mean(1)


def lab_of(rgb):
    return cv2.cvtColor((rgb / 255).astype(np.float32).reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3)


def adjacency(V, TI):
    key = np.round(V * 1e5).astype(np.int64)
    _, wid = np.unique(key, axis=0, return_inverse=True)
    T = wid.ravel()[TI]
    n = len(T)
    E = np.concatenate([np.sort(T[:, [0, 1]], 1), np.sort(T[:, [1, 2]], 1), np.sort(T[:, [2, 0]], 1)])
    F = np.tile(np.arange(n), 3)
    ek = E[:, 0] * 10 ** 7 + E[:, 1]
    o = np.argsort(ek)
    ek, F = ek[o], F[o]
    same = ek[1:] == ek[:-1]
    return F[:-1][same], F[1:][same]


def raster(TU, sel, H, W):
    R = np.zeros((H, W), np.uint8)
    for i in np.where(sel)[0]:
        p = np.stack([TU[i, :, 0] % 1 * W, (1 - TU[i, :, 1] % 1) * H], 1)
        cv2.fillPoly(R, [np.round(p * 16).astype(np.int32)], 1, shift=4)
    return R > 0


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
    ap.add_argument("--dry", action="store_true", help="detect + flag image only, no fill")
    ap.add_argument("--skin-hue", nargs=2, type=float, default=[35, 62])
    ap.add_argument("--skin-chroma", type=float, default=30)
    ap.add_argument("--skin-L", type=float, default=40)
    ap.add_argument("--protect-z", type=float, default=0.76, help="normalized height above which nothing is touched (head)")
    ap.add_argument("--hand-x", type=float, default=0.21, help="|x| beyond which ... ")
    ap.add_argument("--hand-z", type=float, default=0.48, help="... and below which = hands (protected)")
    ap.add_argument("--arm-x", type=float, default=0.13, help="arm zone: |x| > this ...")
    ap.add_argument("--arm-z", nargs=2, type=float, default=[0.38, 0.66], help="... and z in this range")
    ap.add_argument("--k-hi", type=float, default=3.0); ap.add_argument("--dmin-hi", type=float, default=12)
    ap.add_argument("--g-hi", type=float, default=0.10); ap.add_argument("--k-lo", type=float, default=1.5)
    ap.add_argument("--dmin-lo", type=float, default=5); ap.add_argument("--g-lo", type=float, default=0.04)
    ap.add_argument("--g-comp", type=float, default=0.06)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    m = np.load(a.mesh)
    V, TI, TU = m["V"], m["TI"], m["TU"]
    im = np.asarray(Image.open(a.tex).convert("RGB"))
    H, W = im.shape[:2]
    f = W / 8192.0  # pixel parameters were tuned at 8K
    pxs = lambda v: max(1, int(round(v * f)))

    # 1. skin triangles
    lab = lab_of(face_colours(TU, im))
    L, ch, hue = lab[:, 0], np.hypot(lab[:, 1], lab[:, 2]), np.degrees(np.arctan2(lab[:, 2], lab[:, 1]))
    skin = (hue > a.skin_hue[0]) & (hue < a.skin_hue[1]) & (ch > a.skin_chroma) & (L > a.skin_L)
    fa, fb = adjacency(V, TI)
    n = len(TI)
    ns = ~skin
    sel = ns[fa] & ns[fb]
    A = coo_matrix((np.ones(sel.sum()), (fa[sel], fb[sel])), shape=(n, n))
    _, comp = connected_components(A, directed=False)
    area = 0.5 * np.linalg.norm(np.cross(V[TI[:, 1]] - V[TI[:, 0]], V[TI[:, 2]] - V[TI[:, 0]]), axis=1)
    carea = np.bincount(comp, weights=area * ns)
    small = (carea > 0) & (carea < 4e-4)
    skin = skin | (ns & small[comp])
    C = V[TI].mean(1)
    # grow skin into dark smudged triangles next to skin inside the arm zone (the smudge itself is too dark /
    # too grey to pass the skin colour test - without this step the worst elbow patches are never touched)
    from scipy.sparse import csr_matrix
    M = csr_matrix((np.ones(2 * len(fa)), (np.r_[fa, fb], np.r_[fb, fa])), shape=(n, n))
    zone = (np.abs(C[:, 0]) > a.arm_x) & (C[:, 2] > a.arm_z[0]) & (C[:, 2] < a.arm_z[1])
    dirtcol = zone & ~skin & (hue > -60) & (hue < 65) & (L < 70) & ~((ch > 25) & (hue < 20))
    cur, added = skin.copy(), np.zeros(n, bool)
    for _ in range(8):
        new = ((M @ cur.astype(float)) > 0) & dirtcol & ~cur
        added |= new
        cur |= new
    skin = skin | added
    print(f"skin grown into {int(added.sum())} dark arm-zone triangles")
    protect = (C[:, 2] > a.protect_z) | ((np.abs(C[:, 0]) > a.hand_x) & (C[:, 2] < a.hand_z))
    work = skin & ~protect
    print(f"triangles {n}, skin {int(skin.sum())}, workable skin {int(work.sum())}")

    # 2. texel masks
    SK = raster(TU, work, H, W)
    SK &= cv2.erode(SK.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    NS = cv2.dilate(raster(TU, ~skin, H, W).astype(np.uint8), np.ones((5, 5), np.uint8)) > 0

    # 3. detection
    labi = cv2.cvtColor(im.astype(np.float32) / 255, cv2.COLOR_RGB2LAB)
    Lp = labi[..., 0].copy()
    cl = np.hypot(labi[..., 1], labi[..., 2]) / np.maximum(Lp, 1)
    del labi
    s = 2048
    L2 = cv2.resize(Lp, (s, s), interpolation=cv2.INTER_AREA)
    sk2 = cv2.resize(SK.astype(np.float32), (s, s), interpolation=cv2.INTER_AREA) > 0.99

    def nb(v, w):
        return cv2.GaussianBlur(v * w, (0, 0), 20) / np.maximum(cv2.GaussianBlur(w, (0, 0), 20), 1e-4)
    w = sk2.astype(np.float32)
    for _ in range(3):
        Lr = nb(L2, w)
        md = np.maximum(nb(np.abs(L2 - Lr), w), 2.0)
        w = (sk2 & (L2 > Lr - 2.5 * md)).astype(np.float32)
    Lref = cv2.resize(Lr, (W, H), interpolation=cv2.INTER_LINEAR)
    mad = cv2.resize(md, (W, H), interpolation=cv2.INTER_LINEAR)
    d = Lref - Lp
    g = np.clip(0.67 + 0.008 * (72 - Lp), 0.6, 1.0) - cl
    op = pxs(9) | 1
    seed = SK & (d > np.maximum(a.k_hi * mad, a.dmin_hi)) & (g > a.g_hi)
    seed = cv2.morphologyEx(seed.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (op, op)))
    seed |= (SK & (cl < 0.5) & (d > 6)).astype(np.uint8)
    lo = SK & (d > np.maximum(a.k_lo * mad, a.dmin_lo)) & (g > a.g_lo)
    gr = pxs(48)
    reach = cv2.dilate(seed, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gr + 1, 2 * gr + 1))) > 0
    cand = ((lo & reach) | (seed > 0)).astype(np.uint8)
    nl, lbl = cv2.connectedComponents(cand, connectivity=8)
    keep = np.zeros(nl, bool)
    keep[np.unique(lbl[seed > 0])] = True
    keep[0] = False
    labs = np.where(keep)[0]
    if len(labs):
        med = np.zeros(nl)
        med[labs] = ndimage.median(g, lbl, labs)
        keep &= med > a.g_comp
    D = keep[lbl].astype(np.uint8)
    D = cv2.morphologyEx(D, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (pxs(9) | 1,) * 2))
    D = (D.astype(bool) & SK).astype(np.uint8)
    cover = float(D.sum()) / max(1, int(SK.sum()))
    vis = im.copy()
    vis[cv2.dilate(D, np.ones((3, 3), np.uint8)) > 0] = (255, 0, 255)
    Image.fromarray(vis).resize((2048, 2048), Image.NEAREST).save(os.path.join(a.out, "dirt_flags.png"))
    stats = {"tex": [W, H], "skin_texels": int(SK.sum()), "dirt_texels": int(D.sum()), "dirt_cover_of_skin": round(cover, 4)}
    print("detect", stats)
    if a.dry:
        json.dump(stats, open(os.path.join(a.out, "tex_clean.json"), "w"), indent=1)
        return

    # 4. fill
    el = lambda r: cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    dil, guard, feather = pxs(10), pxs(6), max(2, pxs(6))
    M = (cv2.dilate(D, el(dil)) > 0) & ~NS
    K = SK & ~(cv2.dilate(D, el(dil + guard)) > 0)
    out = im.copy()
    F = im.astype(np.float32)
    ncomp, lb, st, _ = cv2.connectedComponentsWithStats(M.astype(np.uint8), connectivity=8)
    pad = pxs(128)
    for k in range(1, ncomp):
        x, y, w_, h_, _ = st[k]
        x0, y0, x1, y1 = max(0, x - pad), max(0, y - pad), min(W, x + w_ + pad), min(H, y + h_ + pad)
        sub = F[y0:y1, x0:x1]
        mk = lb[y0:y1, x0:x1] == k
        kn = K[y0:y1, x0:x1].astype(np.float32)
        if kn.sum() < 10:
            continue
        base = cv2.GaussianBlur(pushpull(sub.copy(), kn), (0, 0), 2)
        ys, xs = np.nonzero(mk)
        det = np.zeros_like(sub)
        best = None
        for r in range(pxs(10), pxs(600), max(1, pxs(6))):
            for ang in np.linspace(0, 2 * np.pi, 36, endpoint=False):
                dx, dy = int(round(r * np.cos(ang))), int(round(r * np.sin(ang)))
                yy, xx = ys + y0 + dy, xs + x0 + dx
                if yy.min() < 0 or xx.min() < 0 or yy.max() >= H or xx.max() >= W:
                    continue
                if K[yy, xx].mean() > 0.995:
                    best = (dx, dy)
                    break
            if best:
                break
        if best:
            dx, dy = best
            yy, xx = ys + y0 + dy, xs + x0 + dx
            ya, xa = max(0, yy.min() - 20), max(0, xx.min() - 20)
            win = F[ya:yy.max() + 21, xa:xx.max() + 21]
            hp = win - cv2.GaussianBlur(win, (0, 0), 3.0)
            det[ys, xs] = hp[yy - ya, xx - xa]
        fillv = base + 0.7 * det
        wgt = np.clip(cv2.distanceTransform(mk.astype(np.uint8), cv2.DIST_L2, 3) / feather, 0, 1)[..., None]
        res = sub * (1 - wgt) + fillv * wgt
        o = out[y0:y1, x0:x1]
        o[mk] = np.clip(res[mk] + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(out).save(os.path.join(a.out, "basecolor_clean.png"))
    stats["changed_texels"] = int(np.any(out != im, axis=2).sum())
    stats["fill_regions"] = int(ncomp - 1)
    json.dump(stats, open(os.path.join(a.out, "tex_clean.json"), "w"), indent=1)
    print("filled", stats, "->", os.path.join(a.out, "basecolor_clean.png"))


if __name__ == "__main__":
    main()
