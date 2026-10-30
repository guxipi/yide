"""Step 3 · register a sol paint-over back onto its canvas and pad it for UV use.

py -3 po_register.py <work_dir> <sheet> [<sheet> ...]      (or --set <set> for every sheet of canvas/<set>_meta.json)
Gate: verdict PASS = silhouette IoU after the affine fit >= 0.965 and Lab colour drift < 12; CHECK -> look at it,
usually rerun that sheet. The silhouette check cannot see shapes moved INSIDE the outline: always eyeball the
painted sheet next to its canvas (internal drift = ribs / seams in the wrong place).
Reads canvas/<sheet>.png + canvas/<sheet>_mask.png + img/<sheet>.png; writes reg/<sheet>.png and prints a JSON
report: IoU of silhouettes before/after an affine ECC fit, colour drift inside the silhouette, verdict.
Pixels inside the silhouette come from the painting; holes (green left inside) fall back to the underlay;
outside the silhouette the colours are extended 32 px (UV padding) so no green bleeds into the model.
"""
import json
import os
import sys

import cv2
import numpy as np


def key_mask(img):
    b, g, r = [img[..., i].astype(np.int32) for i in range(3)]
    bg = (g > 140) & (g - np.maximum(r, b) > 70)
    return (~bg).astype(np.float32)


def iou(a, b):
    a, b = a > 0.5, b > 0.5
    return float((a & b).sum() / max(1, (a | b).sum()))


def pad_out(img, mask, px=32):
    out = img.copy()
    m = (mask > 0.5).astype(np.uint8)
    for _ in range(px):
        dil = cv2.dilate(m, np.ones((3, 3), np.uint8))
        ring = (dil > 0) & (m == 0)
        if not ring.any():
            break
        blur = cv2.blur(out * m[..., None], (3, 3))
        wsum = cv2.blur(m.astype(np.float32), (3, 3))[..., None]
        fill = (blur / np.maximum(wsum, 1e-6)).astype(out.dtype)
        out[ring] = fill[ring]
        m = dil
    return out


def lab_mean(img, m):
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    sel = m > 0.5
    return lab[sel].mean(0)


def one(W, name):
    can = cv2.imread(os.path.join(W, "canvas", name + ".png"))
    m0 = cv2.imread(os.path.join(W, "canvas", name + "_mask.png"), cv2.IMREAD_GRAYSCALE).astype(np.float32) / 255
    pnt = cv2.imread(os.path.join(W, "img", name + ".png"))
    if pnt is None:
        return {"sheet": name, "iou_after": 0, "lab_drift": 0, "verdict": "MISSING img/%s.png (sol job not run or REJECTed)" % name}
    H, Wd = can.shape[:2]
    resized = pnt.shape[:2] != (H, Wd)
    if resized:
        pnt = cv2.resize(pnt, (Wd, H), interpolation=cv2.INTER_AREA)
    m1 = key_mask(pnt)
    iou0 = iou(m0, m1)
    warp = np.eye(2, 3, dtype=np.float32)
    t = cv2.GaussianBlur(m0, (0, 0), 6)
    s = cv2.GaussianBlur(m1, (0, 0), 6)
    try:
        _, warp = cv2.findTransformECC(t, s, warp, cv2.MOTION_AFFINE,
                                       (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error:
        pass
    flags = cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP
    pr = cv2.warpAffine(pnt, warp, (Wd, H), flags=flags, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 255, 0))
    m1r = key_mask(pr)
    iou1 = iou(m0, m1r)
    inside = m0 > 0.5
    hole = inside & (m1r < 0.5)
    out = pr.copy()
    out[hole] = can[hole]
    # trust only the eroded interior: anti-aliased silhouette edges carry green spill from the canvas
    m_in = cv2.erode((m0 > 0.5).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(np.float32)
    out[m_in < 0.5] = (0, 255, 0)
    # despill what is left inside: green may not exceed the larger of red / blue
    o = out.astype(np.int32)
    lim = np.maximum(o[..., 0], o[..., 2])
    core = cv2.erode((m0 > 0.5).astype(np.uint8), np.ones((23, 23), np.uint8))
    spill = (o[..., 1] > lim) & (m_in > 0.5) & (core == 0)      # only in the band next to the edge
    o[..., 1] = np.where(spill, lim, o[..., 1])
    out = o.astype(np.uint8)
    out = pad_out(out, m_in, 40)
    os.makedirs(os.path.join(W, "reg"), exist_ok=True)
    cv2.imwrite(os.path.join(W, "reg", name + ".png"), out)
    la, lb = lab_mean(can, m0), lab_mean(pr, m0 * (m1r > 0.5))
    drift = float(np.linalg.norm(la - lb) * 100 / 255)
    shift = float(np.hypot(warp[0, 2], warp[1, 2]))
    verdict = "PASS" if iou1 >= 0.965 and drift < 12 else "CHECK"
    return {"sheet": name, "resized": resized, "iou_before": round(iou0, 4), "iou_after": round(iou1, 4),
            "warp_shift_px": round(shift, 1), "warp_scale": [round(float(warp[0, 0]), 4), round(float(warp[1, 1]), 4)],
            "hole_px": int(hole.sum()), "lab_drift": round(drift, 2), "verdict": verdict}


if __name__ == "__main__":
    W = sys.argv[1]
    names = sys.argv[2:]
    if names[:1] == ["--set"]:
        meta = json.load(open(os.path.join(W, "canvas", names[1] + "_meta.json"), encoding="utf-8"))
        names = [s["name"] for s in meta["sheets"]]
    rep = [one(W, n) for n in names]
    for r in rep:
        print(r["sheet"], "iou", r["iou_after"], "drift", r["lab_drift"], r["verdict"])
    sys.exit(0 if all(r["verdict"] == "PASS" for r in rep) else 1)
