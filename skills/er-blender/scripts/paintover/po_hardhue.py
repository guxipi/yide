# -*- coding: utf-8 -*-
"""Step 3.5 · hard hue lock for registered paint-over sheets (run after po_register, before po_project).

py -3 po_hardhue.py <work_dir> <sheet> [<sheet> ...] [--t 24]

勾哥 11-09 (WS1): 「为什么墙上有粉色的 HUE?我要说多少遍 paintover hue 不是你要考虑的事情」 - terra painted a pink wash /
cream drift across the walls; paint-over may only add VALUE, never hue. Matching the average hex is not enough: sample
both ends of the same face, a visible hue difference means the lock did not hold.

Every pixel inside the canvas mask takes the canvas a/b (= approved no-hue base colour + own-light spill baked into the
underlay) and keeps the painted L. Pixels whose painted a/b is far from the canvas (dE_ab > T, i.e. the model's own
lights: red beacon, light strips, seams, screens) keep their painted colour. Backs up reg/<sheet>.png to
reg/<sheet>_prehue.png once and always starts from that copy, so it can be rerun. Replaces po_colorlock as the default
lock (its per-class hard split cut wedge edges into soft halos); after this the in-engine gain must be recalibrated.
Ported from ArtWork/J01v7_WS1_20261109/gen/po_hardhue.py.
"""
import os
import shutil
import sys

import cv2
import numpy as np


def main(argv):
    T = 24.0
    if "--t" in argv:
        i = argv.index("--t")
        T = float(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    if len(argv) < 2:
        sys.exit(__doc__)
    work, sheets = argv[0], argv[1:]
    for sh in sheets:
        reg = os.path.join(work, "reg", sh + ".png")
        bak = os.path.join(work, "reg", sh + "_prehue.png")
        if not os.path.exists(bak):
            shutil.copy(reg, bak)
        pr = cv2.imread(bak).astype(np.float32) / 255.0
        cv_ = cv2.imread(os.path.join(work, "canvas", sh + ".png")).astype(np.float32) / 255.0
        mask = cv2.imread(os.path.join(work, "canvas", sh + "_mask.png"), 0) > 127
        Lp, Lc = cv2.cvtColor(pr, cv2.COLOR_BGR2LAB), cv2.cvtColor(cv_, cv2.COLOR_BGR2LAB)
        d = np.linalg.norm(Lp[..., 1:] - Lc[..., 1:], axis=-1)
        lock = mask & (d <= T)
        out = Lp.copy()
        out[lock, 1:] = Lc[lock, 1:]
        rgb = np.clip(cv2.cvtColor(out, cv2.COLOR_LAB2BGR) * 255, 0, 255).astype(np.uint8)
        cv2.imwrite(reg, rgb)
        n = max(1, mask.sum())
        print(sh, "locked %.1f%% of model px, kept as own light %.1f%%" % (100 * lock.sum() / n, 100 * (mask & ~lock).sum() / n))


if __name__ == "__main__":
    main(sys.argv[1:])
