"""lobes — 从参考轮廓切出边缘叶瓣的真实剖面,存库;再按库里的真实形状沿大轮廓重放。

库的结构:沿参考轮廓,相邻"谷点"之间切成一串段(叶瓣或平静段),按轮廓顺序保存。
每段:w 弦长、h 凸出高度、tip 最高点在弦上的位置(0-1)、profile(32 点,u 沿弦、v 沿外法线,都除以 w)。
place 时按库里的连续片段(runs)取,保留"成团、有层级"的节奏,不做均匀随机。
"""
import json, math
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks
from PIL import Image, ImageDraw
import refgeo as G

NP = 32  # profile 点数


def normals(p):
    t = np.roll(p, -1, 0) - np.roll(p, 1, 0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return t, np.stack([t[:, 1], -t[:, 0]], 1)


def base_curve(pts, sigma_pts):
    return np.stack([gaussian_filter1d(pts[:, i], sigma_pts, mode="wrap") for i in (0, 1)], 1)


def seg_profile(seg):
    """段点列 -> (w, h, tip, profile)。弦从首点到末点,法线取右手侧(逆时针轮廓的外侧)。"""
    a, b = seg[0], seg[-1]
    ch = b - a; w = float(np.linalg.norm(ch))
    if w < 1e-9:
        return None
    u = ch / w; n = np.array([u[1], -u[0]])
    uu = (seg - a) @ u / w; vv = (seg - a) @ n / w
    s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(seg, axis=0), axis=1))])
    t = np.linspace(0, s[-1], NP)
    prof = np.stack([np.interp(t, s, uu), np.interp(t, s, vv)], 1)
    prof[0] = (0, 0); prof[-1] = (1, 0)
    k = int(np.argmax(vv))
    return w, float(vv.max() * w), float(np.clip(uu[k], 0, 1)), prof


def extract(tr, base_frac=0.03, min_prom_rel=0.004, min_w=None, calm_ratio=0.08):
    """tr: refgeo.trace_contour 的结果。返回库 dict。"""
    pts, cut = tr["pts"], tr["cut"]; N = len(pts); step = tr["step"]
    sqa = math.sqrt(abs(tr["area"]))
    base = base_curve(pts, max(2.0, base_frac * N))
    _, nb = normals(base)
    d = np.einsum("ij,ij->i", pts - base, nb)
    d = gaussian_filter1d(d, 1.5, mode="wrap")
    min_w = min_w or 8 * step
    ext = np.concatenate([-d, -d, -d])
    pk, _ = find_peaks(ext, prominence=min_prom_rel * sqa, distance=max(2, int(min_w / step * 0.6)))
    val = sorted(set(int(i - N) % N for i in pk if N <= i < 2 * N))
    if len(val) < 4:
        raise SystemExit(f"只找到 {len(val)} 个谷点,轮廓太平或 --min-prom 太大")
    items, run, run_id = [], 0, 0
    for k in range(len(val)):
        i, j = val[k], val[(k + 1) % len(val)]
        idx = np.arange(i, j + 1 if j > i else j + N + 1) % N
        if cut[idx].any():
            run_id += 1; continue
        r = seg_profile(pts[idx])
        if r is None:
            continue
        w, h, tip, prof = r
        if w < min_w:
            continue
        if prof[:, 0].min() < -0.15 or prof[:, 0].max() > 1.15 or h / w > 1.5:  # 花苗/折叠等退化段,不入库
            run_id += 1; continue
        items.append(dict(w=w, h=h, tip=tip, calm=bool(h / w < calm_ratio), run=run_id, profile=prof.round(4).tolist()))
    if not items:
        raise SystemExit("没有可用段(全部碰到截断边)")
    # 谷点相对 base 的平均偏移:place 时把弦压在 base-inset 上才能保面积
    inset = float(np.mean(d[val]))
    m, _ = G.raster_shape(pts, step)
    lobes = [x for x in items if not x["calm"]]
    return dict(unit="m" if tr["scale"] else "px", step=step, sqrtA=sqa, inset=inset, base_frac=base_frac,
                ref_shape=m, n_valleys=len(val), items=items,
                stats=dict(n_lobes=len(lobes), n_calm=len(items) - len(lobes),
                           w_med=float(np.median([x["w"] for x in lobes])) if lobes else 0,
                           h_med=float(np.median([x["h"] for x in lobes])) if lobes else 0,
                           w_cv=G._cv([x["w"] for x in lobes]), h_cv=G._cv([x["h"] for x in lobes])),
                valleys=pts[val].round(4).tolist())


def montage(lib, path, tile=150):
    """拼图:每个段两行——上行按真实相对尺寸,下行归一化到同宽(看形状)。灰=平静段,绿=叶瓣。"""
    items = lib["items"]; wmax = max(x["w"] for x in items)
    cols = 8; rows = math.ceil(len(items) / cols)
    im = Image.new("RGB", (cols * tile, rows * tile * 2), (28, 28, 32)); d = ImageDraw.Draw(im)
    for idx, it in enumerate(items):
        r, c = divmod(idx, cols); prof = np.array(it["profile"])
        col = (110, 110, 120) if it["calm"] else (150, 215, 80)
        for row, s in ((0, tile * 0.8 / wmax * it["w"]), (1, tile * 0.8)):
            ox = c * tile + tile * 0.1; oy = (r * 2 + row) * tile + tile * 0.78
            d.polygon([(ox + u * s, oy - v * s) for u, v in prof], fill=col, outline=(240, 240, 200))
            d.line([(ox, oy), (ox + s, oy)], fill=(80, 80, 255))
        d.text((c * tile + 4, r * tile * 2 + 4), f"{idx} w{it['w']:.2f} h{it['h']:.2f}" + (" calm" if it["calm"] else ""), fill=(255, 255, 0))
    im.save(path)


def overlay(tr, lib, src, path, zoom=2):
    """在原图(或 mask)上描出轮廓,谷点红点、段交替着色。需要 trace 结果能回投到像素。"""
    sc = tr["scale"]
    im = Image.open(src).convert("RGB")
    pts = tr["pts"] + tr["offset"]
    if sc:
        px = np.array([sc.to_px(x, z) for x, z in pts])
    else:
        px = np.stack([pts[:, 0], -pts[:, 1]], 1)
    x0, y0 = np.floor(px.min(0) - 20).astype(int); x1, y1 = np.ceil(px.max(0) + 20).astype(int)
    x0, y0 = max(0, x0), max(0, y0)
    im = im.crop((x0, y0, x1, y1)); im = im.resize((im.width * zoom, im.height * zoom), Image.NEAREST)
    d = ImageDraw.Draw(im)
    P = lambda q: ((q[0] - x0) * zoom, (q[1] - y0) * zoom)
    val = np.array(lib["valleys"]) + tr["offset"]
    vpx = np.array([sc.to_px(x, z) for x, z in val]) if sc else np.stack([val[:, 0], -val[:, 1]], 1)
    d.line([P(p) for p in px] + [P(px[0])], fill=(255, 255, 0), width=1)
    for p in vpx:
        q = P(p); d.ellipse([q[0] - 3, q[1] - 3, q[0] + 3, q[1] + 3], outline=(255, 40, 40), width=2)
    im.save(path)


def place(lib, base_pts, cut, seed=0, size_mult=1.0, jitter=0.12, run_len=(4, 12), base_sigma_w=0.6,
          inset=None, mirror=True, fixed_run=None):
    """沿大轮廓(逆时针)按库里的真实形状重放边缘。返回 (pts, cut, info)。"""
    rng = np.random.default_rng(seed)
    N = len(base_pts)
    seg = np.linalg.norm(np.diff(np.vstack([base_pts, base_pts[:1]]), axis=0), axis=1)
    step = float(seg.mean())
    items = lib["items"]
    wmed = lib["stats"]["w_med"] * size_mult
    base = base_curve(base_pts, max(2.0, base_sigma_w * wmed / step))
    base_cut = cut
    sb = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(np.vstack([base, base[:1]]), axis=0), axis=1))])
    L = sb[-1]
    t, nb = normals(base)
    ext = lambda a: a  # noqa
    Bx = np.append(base[:, 0], base[0, 0]); Bz = np.append(base[:, 1], base[0, 1])
    Tx = np.append(t[:, 0], t[0, 0]); Tz = np.append(t[:, 1], t[0, 1])
    Nx = np.append(nb[:, 0], nb[0, 0]); Nz = np.append(nb[:, 1], nb[0, 1])
    cutarr = np.append(base_cut, base_cut[0]).astype(float)

    def at(a):
        a = np.clip(a, 0, L)
        return (np.array([np.interp(a, sb, Bx), np.interp(a, sb, Bz)]),
                np.array([np.interp(a, sb, Nx), np.interp(a, sb, Nz)]))
    inset = lib["inset"] if inset is None else inset
    # 库按 run 分组,runs 里的连续项保留原顺序
    runs = {}
    for it in items:
        runs.setdefault(it["run"], []).append(it)
    run_list = [r for r in runs.values() if len(r) >= 2] or list(runs.values())
    out, outcut, placed = [], [], []
    s = 0.0
    while s < L - 1e-6:
        r = run_list[rng.integers(len(run_list))] if fixed_run is None else run_list[fixed_run % len(run_list)]
        a0 = rng.integers(len(r)); n = int(rng.integers(run_len[0], run_len[1] + 1))
        seq = [(r[(a0 + k) % len(r)], False) for k in range(min(n, len(r)))]
        if mirror and rng.random() < 0.5:
            seq = [(it, True) for it, _ in seq[::-1]]
        jit = float(np.exp(rng.normal(0, jitter)))
        for it, mir in seq:
            if s >= L - 1e-6:
                break
            w = it["w"] * size_mult * jit
            if s + w > L - 0.4 * wmed:  # 收尾:拉伸到恰好闭合
                w = L - s
            prof = np.array(it["profile"]); h = it["h"] * size_mult * jit
            if mir:
                prof = prof[::-1].copy(); prof[:, 0] = 1 - prof[:, 0]
            a_mid = s + w / 2
            skip = np.interp(a_mid, sb, cutarr) > 0.5 or np.interp(s, sb, cutarr) > 0.5
            if skip:
                n_pt = max(2, int(w / step)); aa = np.linspace(s, s + w, n_pt, endpoint=False)
                for a in aa:
                    p, _ = at(a); out.append(p); outcut.append(1)
            else:
                # 弦压在 base-inset 上,profile 的 v 以 w 为单位;长宽比保持,w 被收尾拉伸时 v 同比
                f = w / max(it["w"] * size_mult * jit, 1e-9)
                for u, v in prof[:-1]:
                    p, nn = at(s + u * w)
                    out.append(p + nn * (v * it["w"] * size_mult * jit * (f if f < 1 else 1.0) + inset * size_mult))
                    outcut.append(0)
            placed.append(dict(s=round(s, 3), w=round(w, 3), h=round(h, 3), mirror=bool(mir)))
            s += w
    return np.array(out), np.array(outcut, dtype=bool), placed


def lib_to_json(lib, path):
    json.dump(lib, open(path, "w", encoding="utf-8"), ensure_ascii=False)
