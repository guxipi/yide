"""Step 3.5 · per-material colour lock for registered paint-over sheets (run after po_register, before po_project).

py -3 po_colorlock.py <cfg.json> <work_dir> <sheet>[=cls,cls..] ...   (optional allowed palette classes per sheet)

sol keeps the layout but drifts the base colours (global hue / value shifts). This puts every material back on its
palette value while keeping sol's in-block shading (the big soft gradient and the light edge lines).
Palette = cfg field "palette": {class name: "#RRGGBB"}, the base colours actually written into the model (Col / notes).
For each sheet every pixel of reg/<sheet>.png is assigned to a palette class (inside the canvas mask by the canvas
underlay colour, outside it - UV padding - by the painted colour itself). Per class:
  - L follows the canvas (underlay value incl. its soft AO): the painted class mean L is shifted onto the canvas mean L;
  - a/b follow the palette: the class is moved onto the palette a/b, the hue wander around it compressed to 0.7;
  - neutral greys (palette colours whose R/G/B spread <= 8, e.g. #535556) are compressed to 0.35 so they stay neutral;
  - the class named "glow" is skipped (emissive strips / screens stay as painted);
  - classes with fewer than 200 pixels inside the mask are left alone.
Pass "=cls,cls" after a sheet to restrict it to the classes really on that sheet (stops e.g. beige corners being read
as yellow-brown). Backs up reg/<sheet>.png to reg/<sheet>_raw.png once and always works from that raw copy, so it can
be rerun. Prints one line: PO_JSON {sheet: {class: {px, shift_Lab}}}.
"""
import json
import os
import shutil
import sys

import cv2
import numpy as np

SKIP = {"glow"}
NEUTRAL_SPREAD = 8
K_NEUTRAL = 0.35
K_DEFAULT = 0.7


def lab(img_bgr):
    return cv2.cvtColor(img_bgr.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)


def rgb(hx):
    return int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)


def pal_lab(palette):
    names = list(palette)
    bgr = np.array([[rgb(palette[n])[::-1] for n in names]], np.uint8)
    return names, lab(bgr)[0]


def classify(L, names, P, allowed=None):
    # chroma-weighted nearest palette colour (L half weight: canvas AO / painted shading change L, not hue)
    d = ((L[..., None, 0] - P[None, None, :, 0]) * 0.5) ** 2 + (L[..., None, 1] - P[None, None, :, 1]) ** 2 + \
        (L[..., None, 2] - P[None, None, :, 2]) ** 2
    if allowed is not None:
        for i, n in enumerate(names):
            if n not in allowed:
                d[..., i] = 1e9
    return np.argmin(d, axis=-1)


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    palette = cfg.get("palette")
    if not palette:
        sys.exit("cfg has no \"palette\": add {class name: \"#RRGGBB\"} with the model's real base colours, "
                 "e.g. {\"shell\": \"#DCC8B3\", \"dark\": \"#535556\", \"glow\": \"#55FDFE\"}")
    W = sys.argv[2]
    names, P = pal_lab(palette)
    k_of = {n: (K_NEUTRAL if max(rgb(palette[n])) - min(rgb(palette[n])) <= NEUTRAL_SPREAD else K_DEFAULT)
            for n in names}
    report = {}
    for arg in sys.argv[3:]:
        sh, _, al = arg.partition("=")
        allowed = set(al.split(",")) if al else None
        if allowed and allowed - set(names):
            sys.exit("%s: classes not in palette: %s" % (sh, sorted(allowed - set(names))))
        rp = os.path.join(W, "reg", sh + ".png")
        raw = os.path.join(W, "reg", sh + "_raw.png")
        if not os.path.exists(raw):
            shutil.copy(rp, raw)
        reg = cv2.imread(raw, cv2.IMREAD_COLOR)
        can = cv2.imread(os.path.join(W, "canvas", sh + ".png"), cv2.IMREAD_COLOR)
        mask = cv2.imread(os.path.join(W, "canvas", sh + "_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        Lr, Lc = lab(reg), lab(can)
        cls = np.where(mask, classify(Lc, names, P, allowed), classify(Lr, names, P, allowed))
        out = Lr.copy()
        rep = {}
        for i, n in enumerate(names):
            m_in = mask & (cls == i)
            if n in SKIP or m_in.sum() < 200:
                continue
            # L from the canvas (keeps the underlay value incl. soft AO); a/b from the palette itself (canvas
            # class means get contaminated by neighbouring AO pixels, e.g. warm beige corners pulling grey yellow)
            tgt = np.array([Lc[m_in][:, 0].mean(), P[i][1], P[i][2]], np.float32)
            mean = Lr[m_in].mean(0)
            shift = tgt - mean
            m_all = cls == i
            out[m_all, 0] += shift[0]
            out[m_all, 1:] = tgt[1:] + (Lr[m_all, 1:] - mean[1:]) * k_of[n]
            rep[n] = {"px": int(m_in.sum()), "shift_Lab": [round(float(v), 2) for v in shift]}
        out[..., 0] = np.clip(out[..., 0], 0, 100)
        bgr = cv2.cvtColor(out, cv2.COLOR_LAB2BGR)
        cv2.imwrite(rp, np.clip(bgr * 255.0 + 0.5, 0, 255).astype(np.uint8))
        report[sh] = rep
    print("PO_JSON " + json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
