"""trace / lobes / regress 三个命令的实现(refkit.py 只做参数解析和分发)。"""
import json, os, sys
import numpy as np
from PIL import Image, ImageDraw
import refgeo as G
import lobes as LB


def _trace_from_args(a, step=None):
    sc = G.Scale.from_args(a)
    if sc is None:
        print("提示:没给 --pitch-px/--cell-m,输出单位是原图像素(z=-y),不做透视反算", file=sys.stderr)
    m = G.load_mask(a.img, a.color, a.tol)
    tr = G.trace_contour(m, G.parse_box(a.box), sc, a.sigma, step if step else a.step, not a.no_fill, not a.no_center)
    return sc, tr


def cmd_trace(a):
    """掩膜/颜色阈值 -> 贴地轮廓点列 txt(x z cut)+ 叠图预览。"""
    sc, tr = _trace_from_args(a)
    unit = "m" if sc else "px"
    hdr = (f"# traced from {os.path.basename(a.img)}" + (f" box {a.box}" if a.box else "")
           + f", gaussian sigma {a.sigma:g}px, step {tr['step']:.4f}{unit}; "
           + (sc.describe() if sc else "px units, z=-y") + "; cols x z cut(1=框/图边截断,非真实边)")
    G.write_outline(a.out, tr, hdr)
    w = float(np.ptp(tr["pts"][:, 0])); d = float(np.ptp(tr["pts"][:, 1]))
    print(json.dumps(dict(n=len(tr["pts"]), perim=round(tr["perim"], 2), area=round(tr["area"], 2),
                          w=round(w, 2), d=round(d, 2), cutpts=int(tr["cut"].sum()), unit=unit)))
    if a.compare:
        ref, _ = G.read_outline(a.compare)
        c1, c2, hd = G.chamfer(tr["pts"], ref); ra = abs(G.poly_area(ref))
        print(f"对比 {os.path.basename(a.compare)}: n {len(ref)} area {ra:.2f} (新/旧 {tr['area']/ra:.3f})  "
              f"bbox 新 {w:.2f}x{d:.2f} 旧 {np.ptp(ref[:,0]):.2f}x{np.ptp(ref[:,1]):.2f}  "
              f"点到线平均距 {c1:.3f}/{c2:.3f}{unit} 最大 {hd:.3f}{unit}")
    if a.preview:
        src = Image.open(a.img).convert("RGB"); pts = tr["pts"] + tr["offset"]
        px = np.array([sc.to_px(x, z) for x, z in pts]) if sc else np.stack([pts[:, 0], -pts[:, 1]], 1)
        x0, y0 = np.maximum(0, np.floor(px.min(0) - 20)).astype(int); x1, y1 = np.ceil(px.max(0) + 20).astype(int)
        z = 2; im = src.crop((x0, y0, x1, y1)).resize(((x1 - x0) * z, (y1 - y0) * z), Image.NEAREST)
        d_ = ImageDraw.Draw(im); P = [((q[0] - x0) * z, (q[1] - y0) * z) for q in px]
        d_.line(P + [P[0]], fill=(255, 230, 0), width=2)
        for q, cf in zip(P, tr["cut"]):
            if cf:
                d_.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], fill=(255, 40, 40))
        plan = G.draw_plan(tr["pts"], tr["cut"], im.height, grid=1.0 if sc else None)
        out = Image.new("RGB", (im.width + plan.width + 8, im.height), (10, 10, 10))
        out.paste(im, (0, 0)); out.paste(plan, (im.width + 8, 0)); out.save(a.preview); print(a.preview, out.size)


def cmd_lobes(a):
    if a.img == "place":
        return cmd_lobes_place(a)
    if not a.out:
        sys.exit("lobes 需要 --out lib.json")
    sc, tr = _trace_from_args(a)
    lib = LB.extract(tr, a.base_frac, a.min_prom, a.min_w)
    LB.lib_to_json(lib, a.out); st = lib["stats"]
    print(f"{a.out}: {st['n_lobes']} 叶瓣 + {st['n_calm']} 平静段 (谷点 {lib['n_valleys']}), 单位 {lib['unit']}, "
          f"w 中位 {st['w_med']:.3f} h 中位 {st['h_med']:.3f} wCV {st['w_cv']:.2f} hCV {st['h_cv']:.2f} inset {lib['inset']:.4f}")
    base = os.path.splitext(a.out)[0]
    mp = a.montage or base + "_montage.png"; op = a.overlay or base + "_overlay.png"
    LB.montage(lib, mp); LB.overlay(tr, lib, a.img, op); print(mp); print(op)


def cmd_lobes_place(a):
    lib = json.load(open(a.lib, encoding="utf-8"))
    if a.outline.lower().endswith(".txt"):
        pts, cut = G.read_outline(a.outline)
        if G.poly_area(pts) < 0:
            pts, cut = pts[::-1], cut[::-1]
        pts, cut, _ = G.resample_closed(pts, cut.astype(float), lib["step"])
    else:
        sc = G.Scale.from_args(a)
        tr = G.trace_contour(G.load_mask(a.outline, a.color, a.tol), G.parse_box(a.box), sc, a.sigma, lib["step"])
        pts, cut = tr["pts"], tr["cut"]
    out, ocut, info = LB.place(lib, pts, cut, a.seed, a.size_mult, a.jitter, (a.run_min, a.run_max),
                               a.base_sigma_w, a.inset, not a.no_mirror)
    unit = lib["unit"]
    G.write_outline(a.out, dict(pts=out, cut=ocut),
                    f"# lobes place from {os.path.basename(a.lib)} on {os.path.basename(a.outline)}, seed {a.seed}, size_mult {a.size_mult:g}, {unit}; cols x z cut")
    res = lib["step"]
    m_new, _ = G.raster_shape(out, res); m_in, _ = G.raster_shape(pts, res); m_ref = lib["ref_shape"]
    print(f"{a.out}: {len(info)} 段, {len(out)} 点, 面积 {abs(G.poly_area(out)):.2f} (输入 {abs(G.poly_area(pts)):.2f})")
    for name, r in (("库来源参考", m_ref), ("输入大轮廓", m_in), ("重放结果", m_new)):
        print(f"  {name:6s} 实度 {r['solidity']:.3f} 细尺度 {r['fine']:.2f} 凸起 {r['peaks']:3d} 间距CV {r['gap_cv']:.2f} 大小CV {r['size_cv']:.2f}")
    if a.preview:
        h = 560; g = 1.0 if unit == "m" else None
        A = G.draw_plan(pts, cut, h, grid=g, color=(120, 120, 255)); B = G.draw_plan(out, ocut, h, grid=g)
        im = Image.new("RGB", (A.width + B.width + 8, h), (10, 10, 10)); im.paste(A, (0, 0)); im.paste(B, (A.width + 8, 0))
        im.save(a.preview); print(a.preview)


def cmd_regress(a):
    """新版 vs 当前最好版 vs 参考的 shape 指标。退步(任一项)退出码 1;--gate 时绝对门槛不过退出码 2。"""
    R = {}
    for k in ("ref", "best", "new"):
        p = getattr(a, k)
        if p:
            R[k] = G.shape_metrics(G.load_mask(p, getattr(a, k + "_color"), a.tol, G.parse_box(getattr(a, k + "_box"))))
    if "ref" not in R or "new" not in R:
        sys.exit("至少要 --ref 和 --new")
    rows = [("实度", "solidity", "{:.3f}"), ("细尺度%√A", "fine", "{:.2f}"), ("中尺度%√A", "mid", "{:.2f}"),
            ("凸起数", "peaks", "{:.0f}"), ("间距CV", "gap_cv", "{:.2f}"), ("大小CV", "size_cv", "{:.2f}")]
    names = [k for k in ("ref", "best", "new") if k in R]
    print("指标".ljust(10) + "".join(n.rjust(10) for n in names))
    for lab, key, f in rows:
        print(lab.ljust(8) + "".join(f.format(R[n][key]).rjust(10) for n in names))
    ref, new = R["ref"], R["new"]; reasons, warns = [], []
    if "best" in R:
        best = R["best"]
        dn, db = abs(new["solidity"] - ref["solidity"]), abs(best["solidity"] - ref["solidity"])
        if dn > db + a.eps_solid:
            reasons.append(f"实度离参考更远 (差 {dn:.3f} > 最好版 {db:.3f})")
        if new["size_cv"] < best["size_cv"] * (1 - a.eps_rel):
            reasons.append(f"凸起大小CV 更低 ({new['size_cv']:.2f} < {best['size_cv']:.2f})")
        if new["fine"] < best["fine"] * (1 - a.eps_rel):
            reasons.append(f"细尺度更低 ({new['fine']:.2f} < {best['fine']:.2f})")
    if abs(new["solidity"] - ref["solidity"]) > 0.05:
        warns.append(f"实度与参考差 {abs(new['solidity']-ref['solidity']):.3f} > 0.05")
    if new["size_cv"] < 0.8 * ref["size_cv"]:
        warns.append(f"大小CV {new['size_cv']:.2f} < 参考 0.8 倍 ({0.8*ref['size_cv']:.2f})")
    if new["fine"] < 0.5 * ref["fine"]:
        warns.append(f"细尺度 {new['fine']:.2f} < 参考一半 ({0.5*ref['fine']:.2f})")
    for w_ in warns:
        print("  门槛未过:", w_)
    if reasons:
        print("结果: 退步 —— 不交")
        for r_ in reasons:
            print("  -", r_)
        sys.exit(1)
    if warns and a.gate:
        print("结果: 未退步,但绝对门槛不过(--gate)"); sys.exit(2)
    print("结果: 未退步" + ("" if "best" in R else "(没给 --best,只做了绝对门槛提示)"))


def add_parsers(s):
    q = s.add_parser("trace"); G.add_mask_args(q); G.add_scale_args(q)
    q.add_argument("--sigma", type=float, default=1.0, help="轮廓 gaussian 平滑(像素),默认 1 只去 mask 台阶")
    q.add_argument("--step", type=float, help="输出点距(米;无标定则像素),默认 1 像素对应的长度")
    q.add_argument("--no-fill", action="store_true", help="不填洞(默认填,花丛等内部洞不算边)")
    q.add_argument("--no-center", action="store_true")
    q.add_argument("--out", required=True); q.add_argument("--preview"); q.add_argument("--compare", help="对比已有 x z cut txt")
    q.set_defaults(f=cmd_trace)
    q = s.add_parser("lobes"); q.add_argument("img", help="参考图/mask;写 place 进入重放模式")
    q.add_argument("--color"); q.add_argument("--tol", type=int, default=40); q.add_argument("--box"); G.add_scale_args(q)
    q.add_argument("--sigma", type=float, default=0.8); q.add_argument("--step", type=float)
    q.add_argument("--no-fill", action="store_true"); q.add_argument("--no-center", action="store_true")
    q.add_argument("--out"); q.add_argument("--montage"); q.add_argument("--overlay")
    q.add_argument("--base-frac", type=float, default=0.03, help="大轮廓基线平滑半窗,占周长比例")
    q.add_argument("--min-prom", type=float, default=0.004, help="谷点最小显著度,占 √面积 比例")
    q.add_argument("--min-w", type=float, help="最小段宽(单位同输出)")
    q.add_argument("--lib"); q.add_argument("--outline", help="place 用:大轮廓 txt 或 mask png"); q.add_argument("--seed", type=int, default=0)
    q.add_argument("--size-mult", type=float, default=1.0)
    q.add_argument("--jitter", type=float, default=0.12, help="每个 run 的整体大小 lognormal 抖动")
    q.add_argument("--run-min", type=int, default=4); q.add_argument("--run-max", type=int, default=12)
    q.add_argument("--base-sigma-w", type=float, default=0.6, help="place 基线平滑,单位=叶瓣宽中位数")
    q.add_argument("--inset", type=float); q.add_argument("--no-mirror", action="store_true"); q.add_argument("--preview")
    q.set_defaults(f=cmd_lobes)
    q = s.add_parser("regress")
    for k in ("ref", "best", "new"):
        q.add_argument("--" + k); q.add_argument(f"--{k}-color"); q.add_argument(f"--{k}-box")
    q.add_argument("--tol", type=int, default=40); q.add_argument("--eps-solid", type=float, default=0.01)
    q.add_argument("--eps-rel", type=float, default=0.05, help="CV/细尺度相对最好版的容差"); q.add_argument("--gate", action="store_true")
    q.set_defaults(f=cmd_regress)
