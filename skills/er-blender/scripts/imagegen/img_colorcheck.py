# -*- coding: utf-8 -*-
"""ER 生图铁规 0 · 回图颜色检查(11-10 勾哥:主体什么颜色就是什么颜色;灯光不许把楼体染成淡紫灰;少用粉紫,男性向)。

两项判定(Lab 空间,忽略近白背景和近黑描边):
  1. 整图偏色:低彩度像素(C* < 10,= 本该中性的混凝土 / 灰钢 / 白墙 / 石板)的 a*/b* 中位数偏离 0
     → 偏紫(b* < -3 且 a* > 2)或任意方向 |ab| > 阈值 = 有光色罩在中性物体上。
  2. 粉紫占比:色相 285°–350°(紫 / 品红 / 粉)且 C* > 15 的像素占前景 > 阈值(默认 6 %)。
退出码 0 = 全过;1 = 有图不过(逐张打印数值)。
python img_colorcheck.py img/*.png [--cast 6] [--pink 0.06]
"""
import argparse
import sys
from pathlib import Path
import numpy as np
from PIL import Image


def srgb_to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return 116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])


def check(path, cast_lim, pink_lim):
    im = np.asarray(Image.open(path).convert("RGB"), dtype=np.float64)
    if im.shape[0] * im.shape[1] > 1_500_000:
        im = im[::2, ::2]
    L, a, b = srgb_to_lab(im)
    C = np.hypot(a, b)
    fg = (L > 12) & ~((L > 93) & (C < 4))
    neutral = fg & (C < 10) & (L > 35)
    am = float(np.median(a[neutral])) if neutral.sum() > 500 else 0.0
    bm = float(np.median(b[neutral])) if neutral.sum() > 500 else 0.0
    hue = (np.degrees(np.arctan2(b, a)) + 360) % 360
    pr = float((fg & (C > 15) & (hue >= 285) & (hue <= 350)).sum() / max(fg.sum(), 1))
    errs = []
    if (bm < -3 and am > 2) or np.hypot(am, bm) > cast_lim:
        errs.append(f"中性物体被染色:中位 a*={am:+.1f} b*={bm:+.1f}" + (" (偏紫)" if bm < -3 and am > 2 else ""))
    if pr > pink_lim:
        errs.append(f"粉紫占前景 {pr * 100:.1f}% > {pink_lim * 100:.0f}%")
    return errs, am, bm, pr


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--cast", type=float, default=6.0)
    ap.add_argument("--pink", type=float, default=0.06)
    A = ap.parse_args()
    files = [f for g in A.images for f in (sorted(Path().glob(g)) if any(c in g for c in "*?[") else [Path(g)])]
    bad = 0
    for f in files:
        e, am, bm, pr = check(f, A.cast, A.pink)
        print(f"{'✗' if e else '✓'} {f}  中性 a*={am:+.1f} b*={bm:+.1f}  粉紫 {pr * 100:.1f}%" + ("  ← " + ";".join(e) if e else ""))
        bad += bool(e)
    print(f"{len(files) - bad}/{len(files)} 过铁规 0")
    sys.exit(1 if bad else 0)
