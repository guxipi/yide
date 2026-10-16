#!/usr/bin/env python3
"""refkit — 对标参考图的测量与并排工具(reference-replicate skill 配套)。

所有坐标都是原图像素。比例尺按"已知高度的物体"标定(一般用角色身高),
存在 <图片>.scale.json 里,后续 measure/grid 自动读取。

  py refkit.py scale   IMG --p1 x,y --p2 x,y --meters 1.8
  py refkit.py measure IMG --p1 x,y --p2 x,y           [可多组: --p1 .. --p2 .. 重复]
  py refkit.py crop    IMG --box x0,y0,x1,y1 --zoom 4 --out a.png [--grid 0.5]
  py refkit.py color   IMG --box x0,y0,x1,y1 [--k 3]
  py refkit.py sbs     A.png B.png --out sbs.png [--ha 120 --hb 95]
  py refkit.py flicker A.png B.png --out f.gif
  py refkit.py sheet   IMG --boxes "x0,y0,x1,y1;..." --zoom 3 --out sheet.png
  py refkit.py shape   MASK.png [--color #RRGGBB --tol 40] [--box ..]   形状自然度指标
  py refkit.py trace   IMG|MASK --pitch-px 65 --cell-m 1.58 --yx 0.92 [--box ..] --out o.txt   描轮廓到地面米
  py refkit.py lobes   IMG|MASK --pitch-px .. --cell-m .. --yx .. --out lib.json               切叶瓣形状库
  py refkit.py lobes place --lib lib.json --outline o.txt --out new.txt                        按库重放边缘
  py refkit.py regress --ref R.png --best B.png --new N.png [--new-color ..]                   退步拦截,退出码非 0=退步

grid:按比例尺每 N 米画一条细线(需先 scale),用于肉眼读尺寸。
sbs:--ha/--hb 是同一参照长度(如角色身高)在 A/B 里的像素,自动缩放到同比例再并排。
flicker:两张同尺寸对齐图交替的 GIF,看轮廓/位置差。
color:区域中位色 + k 簇(按亮度排序,一般是 暗/中/亮),输出 hex 与占比。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
from PIL import Image, ImageDraw
sys.stdout.reconfigure(encoding="utf-8")
import numpy as np


def pt(s):
    x, y = s.split(","); return float(x), float(y)


def box(s):
    v = [int(round(float(t))) for t in s.split(",")]; return tuple(v)


def scale_path(img):
    return img + ".scale.json"


def load_scale(img):
    p = scale_path(img)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8"))["m_per_px"]


def hexc(rgb):
    return "#%02X%02X%02X" % tuple(int(round(c)) for c in rgb[:3])


def cmd_scale(a):
    (x1, y1), (x2, y2) = pt(a.p1), pt(a.p2)
    px = math.hypot(x2 - x1, y2 - y1)
    mpp = a.meters / px
    json.dump({"m_per_px": mpp, "ref_px": px, "ref_m": a.meters, "p1": a.p1, "p2": a.p2,
               "note": a.note or ""}, open(scale_path(a.img), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"ref {px:.1f}px = {a.meters}m -> {mpp*100:.3f} cm/px ({1/mpp:.1f} px/m)")


def cmd_measure(a):
    mpp = load_scale(a.img)
    for s1, s2 in zip(a.p1, a.p2):
        (x1, y1), (x2, y2) = pt(s1), pt(s2)
        px = math.hypot(x2 - x1, y2 - y1)
        m = f" = {px*mpp:.3f} m" if mpp else " (未标定比例尺)"
        print(f"{s1} -> {s2}: {px:.1f}px{m}")


def draw_grid(im, origin, zoom, mpp, step_m):
    d = ImageDraw.Draw(im)
    step = step_m / mpp * zoom
    if step < 4:
        return
    W, H = im.size
    ox = (-origin[0] * zoom) % step
    oy = (-origin[1] * zoom) % step
    x = ox
    while x < W:
        d.line([(x, 0), (x, H)], fill=(0, 255, 255), width=1); x += step
    y = oy
    while y < H:
        d.line([(0, y), (W, y)], fill=(0, 255, 255), width=1); y += step
    d.text((4, 4), f"grid {step_m}m", fill=(0, 255, 255))


def cmd_crop(a):
    im = Image.open(a.img).convert("RGB")
    b = box(a.box)
    c = im.crop(b)
    c = c.resize((c.width * a.zoom, c.height * a.zoom), Image.NEAREST)
    if a.grid:
        mpp = load_scale(a.img)
        if not mpp:
            sys.exit("grid 需要先 scale")
        draw_grid(c, b[:2], a.zoom, mpp, a.grid)
    c.save(a.out); print(a.out, c.size)


def cmd_color(a):
    im = np.asarray(Image.open(a.img).convert("RGB")).astype(float)
    x0, y0, x1, y1 = box(a.box)
    px = im[y0:y1, x0:x1].reshape(-1, 3)
    med = np.median(px, axis=0)
    print(f"median {hexc(med)}  n={len(px)}")
    k = a.k
    lum = px @ np.array([0.299, 0.587, 0.114])
    cent = np.percentile(px, np.linspace(10, 90, k), axis=0) if k > 1 else med[None]
    order = np.argsort(lum)
    cent = np.array([px[order[int(len(px) * q)]] for q in np.linspace(0.1, 0.9, k)])
    for _ in range(15):
        lab = np.argmin(((px[:, None] - cent[None]) ** 2).sum(-1), axis=1)
        cent = np.array([px[lab == i].mean(0) if (lab == i).any() else cent[i] for i in range(k)])
    idx = np.argsort(cent @ np.array([0.299, 0.587, 0.114]))
    for i in idx:
        share = (lab == i).mean()
        L = cent[i] @ np.array([0.299, 0.587, 0.114]) / 255
        print(f"  {hexc(cent[i])}  {share*100:5.1f}%  L={L:.3f}")


def cmd_sbs(a):
    A = Image.open(a.a).convert("RGB"); B = Image.open(a.b).convert("RGB")
    if a.ha and a.hb:
        f = a.ha / a.hb
        B = B.resize((max(1, round(B.width * f)), max(1, round(B.height * f))), Image.LANCZOS)
    H = max(A.height, B.height)
    out = Image.new("RGB", (A.width + B.width + 8, H), (20, 20, 20))
    out.paste(A, (0, 0)); out.paste(B, (A.width + 8, 0))
    d = ImageDraw.Draw(out)
    d.text((6, 6), a.la, fill=(255, 255, 0)); d.text((A.width + 14, 6), a.lb, fill=(255, 255, 0))
    out.save(a.out); print(a.out, out.size)


def cmd_flicker(a):
    A = Image.open(a.a).convert("RGB"); B = Image.open(a.b).convert("RGB").resize(A.size, Image.LANCZOS)
    A.save(a.out, save_all=True, append_images=[B], duration=600, loop=0); print(a.out)


def cmd_sheet(a):
    im = Image.open(a.img).convert("RGB")
    tiles = []
    for s in a.boxes.split(";"):
        b = box(s); c = im.crop(b)
        tiles.append(c.resize((c.width * a.zoom, c.height * a.zoom), Image.NEAREST))
    W = sum(t.width for t in tiles) + 6 * (len(tiles) - 1); H = max(t.height for t in tiles)
    out = Image.new("RGB", (W, H), (20, 20, 20)); x = 0
    d = ImageDraw.Draw(out)
    for i, t in enumerate(tiles):
        out.paste(t, (x, 0)); d.text((x + 4, 4), str(i + 1), fill=(255, 255, 0)); x += t.width + 6
    out.save(a.out); print(a.out, out.size)


def _mask(path, color=None, tol=40):
    im = np.asarray(Image.open(path).convert("RGB")).astype(int)
    if color:
        c = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)])
        m = (np.abs(im - c).max(-1) <= tol)
    else:
        m = im.mean(-1) > 127
    return m.astype(np.uint8)


def cmd_shape(a):
    """自然度指标:实度(面积/凸包)、边界粗糙度、轮廓凸起的间距/大小变异系数。参考和我方各跑一次对比。"""
    import refgeo as G
    m = _mask(a.img, a.color, a.tol)
    if a.box:
        x0, y0, x1, y1 = box(a.box); z = np.zeros_like(m); z[y0:y1, x0:x1] = m[y0:y1, x0:x1]; m = z
    G.print_shape(G.shape_metrics(m))


def main():
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest="c", required=True)
    q = s.add_parser("scale"); q.add_argument("img"); q.add_argument("--p1", required=True); q.add_argument("--p2", required=True)
    q.add_argument("--meters", type=float, required=True); q.add_argument("--note"); q.set_defaults(f=cmd_scale)
    q = s.add_parser("measure"); q.add_argument("img"); q.add_argument("--p1", action="append", required=True)
    q.add_argument("--p2", action="append", required=True); q.set_defaults(f=cmd_measure)
    q = s.add_parser("crop"); q.add_argument("img"); q.add_argument("--box", required=True); q.add_argument("--zoom", type=int, default=4)
    q.add_argument("--grid", type=float); q.add_argument("--out", required=True); q.set_defaults(f=cmd_crop)
    q = s.add_parser("color"); q.add_argument("img"); q.add_argument("--box", required=True); q.add_argument("--k", type=int, default=3); q.set_defaults(f=cmd_color)
    q = s.add_parser("sbs"); q.add_argument("a"); q.add_argument("b"); q.add_argument("--out", required=True)
    q.add_argument("--ha", type=float); q.add_argument("--hb", type=float); q.add_argument("--la", default="OURS"); q.add_argument("--lb", default="REF"); q.set_defaults(f=cmd_sbs)
    q = s.add_parser("flicker"); q.add_argument("a"); q.add_argument("b"); q.add_argument("--out", required=True); q.set_defaults(f=cmd_flicker)
    q = s.add_parser("sheet"); q.add_argument("img"); q.add_argument("--boxes", required=True); q.add_argument("--zoom", type=int, default=3)
    q.add_argument("--out", required=True); q.set_defaults(f=cmd_sheet)
    q = s.add_parser("shape"); q.add_argument("img"); q.add_argument("--color"); q.add_argument("--tol", type=int, default=40)
    q.add_argument("--box"); q.set_defaults(f=cmd_shape)
    import cmds
    cmds.add_parsers(s)
    a = p.parse_args(); a.f(a)


if __name__ == "__main__":
    main()
