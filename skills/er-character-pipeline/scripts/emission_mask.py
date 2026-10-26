"""Emission mask for glowing parts (Wren: the mint canister) from the FINAL base-colour texture by hue.

usage: py -3 emission_mask.py --config char.json --tex Name_basecolor.png --out Name_emission.png [--preview prev.png]
Uses cfg.emission: hue_deg [lo,hi], s_min, v_min, size. Prints coverage (fraction of texels).
Rules: regenerate whenever the base texture changes (a new Tripo export = new UVs = the old mask lights the
wrong texels). Gate: coverage roughly equals the glowing part's share of the texture (Wren 3.4%); the preview
(mask in magenta over the texture) shows ONLY the glowing part - the lime jacket must stay out (hue window).
If cfg.emission is null the character has no glow: skip this step.
"""
import argparse
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import load_cfg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--tex", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--preview")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    e = cfg.get("emission")
    if not e:
        print("cfg.emission is null - no emission for this character")
        return
    im = Image.open(a.tex).convert("RGB")
    x = np.asarray(im).astype(float) / 255
    mx, mn = x.max(2), x.min(2)
    d = mx - mn + 1e-6
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.where(mx == g, 60 * ((b - r) / d) + 120, np.where(mx == r, (60 * ((g - b) / d)) % 360, 60 * ((r - g) / d) + 240))
    s = d / (mx + 1e-6)
    m = (h > e["hue_deg"][0]) & (h < e["hue_deg"][1]) & (s > e["s_min"]) & (mx > e["v_min"])
    size = e.get("size", 1024)
    Image.fromarray((m * 255).astype(np.uint8)).resize((size, size), Image.BILINEAR).save(a.out)
    print("coverage", round(float(m.mean()), 4), "->", a.out, "| Unity _EmissionColor", e.get("color"))
    if a.preview:
        p = np.asarray(im).copy()
        p[m] = (255, 0, 255)
        Image.fromarray(p).resize((1024, 1024)).save(a.preview)
        print("preview", a.preview)


if __name__ == "__main__":
    main()
