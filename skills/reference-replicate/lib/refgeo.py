"""refgeo — refkit 的几何公共件:掩膜、轮廓、透视反算到地面、shape 指标。

单位约定:传了 Scale 就是地面米(x 右、z 屏幕上方),没传就是原图像素(z=-y)。
轮廓一律逆时针(z 向上的坐标里面积为正),外法线 = (tz, -tx)。
"""
import math
import numpy as np
from PIL import Image


# ---------------------------------------------------------------- 掩膜
def load_mask(path, color=None, tol=40, box=None):
    """图片 -> 0/1 掩膜。color=#RRGGBB 走颜色阈值(最大通道差<=tol),否则按灰度>127。box 之外清零。"""
    im = np.asarray(Image.open(path).convert("RGB")).astype(int)
    if color:
        c = np.array([int(color[i:i + 2], 16) for i in (1, 3, 5)])
        m = (np.abs(im - c).max(-1) <= tol)
    else:
        m = im.mean(-1) > 127
    m = m.astype(np.uint8)
    if box:
        x0, y0, x1, y1 = box
        z = np.zeros_like(m); z[y0:y1, x0:x1] = m[y0:y1, x0:x1]; m = z
    return m


def largest_component(m):
    import cv2
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        raise SystemExit("掩膜为空")
    k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return (lab == k).astype(np.uint8)


def fill_holes(m):
    import cv2
    ff = m.copy(); h, w = m.shape
    cv2.floodFill(ff, np.zeros((h + 2, w + 2), np.uint8), (0, 0), 1)
    return m | (1 - ff)


# ---------------------------------------------------------------- shape 指标(refkit shape / regress 共用)
def _cv(v):
    return float(np.std(v) / np.mean(v)) if len(v) > 1 and np.mean(v) > 0 else float("nan")


def shape_metrics(m):
    """m: 0/1 掩膜(取最大连通域)。返回 dict:area per_rel solidity mid fine peaks gap_cv size_cv。"""
    import cv2
    m = largest_component(m)
    cs, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    area = cv2.contourArea(c.astype(np.float32)); hull = cv2.convexHull(c.astype(np.float32))
    solidity = area / cv2.contourArea(hull)
    per = cv2.arcLength(c.astype(np.float32), True)

    def smooth(pts, w):
        w = max(1, int(w)); k_ = np.ones(2 * w + 1) / (2 * w + 1)
        return np.stack([np.convolve(np.r_[pts[-w:, i], pts[:, i], pts[:w, i]], k_, "valid") for i in (0, 1)], 1)
    L = math.sqrt(area)
    s_big = smooth(c, len(c) * 0.04); s_small = smooth(c, len(c) * 0.006)
    d_mid = np.linalg.norm(s_small - s_big, axis=1); d_fine = np.linalg.norm(c - s_small, axis=1)
    cen = c.mean(0)
    out = np.sign(np.einsum("ij,ij->i", s_small - s_big, s_small - cen)) * d_mid
    peaks = [i for i in range(len(out)) if out[i] > 0.15 * out.max() and out[i] == out[max(0, i - 6):i + 7].max()]
    gaps = np.diff(peaks + [peaks[0] + len(c)]) if len(peaks) > 2 else np.array([0])
    sizes = out[peaks] if peaks else np.array([0])
    return dict(area=float(area), per_rel=per / L, solidity=float(solidity),
                mid=float(d_mid.mean() / L * 100), fine=float(d_fine.mean() / L * 100),
                peaks=len(peaks), gap_cv=_cv(gaps), size_cv=_cv(sizes))


def print_shape(r):
    print(f"面积 {r['area']:.0f}px  周长/√面积 {r['per_rel']:.2f}  实度(面积/凸包) {r['solidity']:.3f}")
    print(f"中尺度起伏 均值 {r['mid']:.2f}%√A  细尺度 {r['fine']:.2f}%√A")
    print(f"凸起 {r['peaks']} 个  间距CV {r['gap_cv']:.2f}  大小CV {r['size_cv']:.2f}  (均匀排列≈0.1,自然≥0.35)")


# ---------------------------------------------------------------- 比例标定
class Scale:
    """屏幕像素 -> 地面米。同深度单元节距 pitch_px(px)= cell_m(米);y/x 比 yx(由同深度方单元 y/x 节距比得,≈sin 局部俯角)。"""

    def __init__(self, pitch_px, cell_m, yx=1.0):
        self.pitch_px, self.cell_m, self.yx = float(pitch_px), float(cell_m), float(yx)
        self.k = self.cell_m / self.pitch_px  # 米/像素(x 方向)

    def to_ground(self, px, py):
        return px * self.k, -py * self.k / self.yx

    def to_px(self, gx, gz):
        return gx / self.k, -gz * self.yx / self.k

    @classmethod
    def from_args(cls, a):
        if a.pitch_px is None or a.cell_m is None:
            return None
        yx = a.yx
        if a.pitch_deg is not None:
            yx = math.sin(math.radians(a.pitch_deg))
        return cls(a.pitch_px, a.cell_m, yx if yx else 1.0)

    def describe(self):
        return f"px->m: x/{self.pitch_px:g}*{self.cell_m:g}, z/({self.pitch_px:g}*{self.yx:g})*{self.cell_m:g}"


def add_scale_args(q):
    q.add_argument("--pitch-px", type=float, help="同深度单元(砖/地块)x 节距,像素")
    q.add_argument("--cell-m", type=float, help="该单元的米数")
    q.add_argument("--yx", type=float, default=1.0, help="y/x 比(同深度方单元 y 节距÷x 节距),默认 1=不压缩")
    q.add_argument("--pitch-deg", type=float, help="局部俯角(度),给了就 yx=sin(俯角),覆盖 --yx")


def add_mask_args(q):
    q.add_argument("img", help="参考图(配 --color)或现成 mask png")
    q.add_argument("--color", help="颜色阈值 #RRGGBB;不给则按灰度>127 当 mask")
    q.add_argument("--tol", type=int, default=40)
    q.add_argument("--box", help="只截取 x0,y0,x1,y1(原图像素)这一段;被框边截断的轮廓点标 cut=1")


def parse_box(s):
    return tuple(int(round(float(t))) for t in s.split(",")) if s else None


# ---------------------------------------------------------------- 轮廓 -> 地面点列
def resample_closed(pts, flag, step):
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)]); L = s[-1]
    n = max(8, int(round(L / step))); t = np.linspace(0, L, n, endpoint=False)
    xs = np.interp(t, s, np.append(pts[:, 0], pts[0, 0])); zs = np.interp(t, s, np.append(pts[:, 1], pts[0, 1]))
    fl = np.interp(t, s, np.append(flag, flag[0])) > 0.5
    return np.stack([xs, zs], 1), fl, L


def poly_area(p):
    x, z = p[:, 0], p[:, 1]
    return 0.5 * float(np.dot(x, np.roll(z, -1)) - np.dot(z, np.roll(x, -1)))


def trace_contour(m, box=None, scale=None, sigma=1.0, step=None, fill=True, center=True):
    """掩膜 -> 贴地轮廓。返回 dict(pts, cut, perim, area, offset, scale)。pts 逆时针,单位见模块说明。"""
    import cv2
    from scipy.ndimage import gaussian_filter1d
    full = largest_component(m)
    if fill:
        full = fill_holes(full)
    h, w = full.shape
    part = full
    if box:
        x0, y0, x1, y1 = box
        part = np.zeros_like(full); part[y0:y1, x0:x1] = full[y0:y1, x0:x1]
        part = largest_component(part)
    cs, _ = cv2.findContours(part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=cv2.contourArea)[:, 0, :].astype(float)
    # cut 标记:贴着框边/图边,且边外一侧原掩膜仍有像素(=被截断);图边一律算截断。用平滑前的点判断
    cut = np.zeros(len(c))
    sides = [(0, -1, 0), (0, 1, w - 1), (1, -1, 0), (1, 1, h - 1)]
    if box:
        x0, y0, x1, y1 = box
        sides += [(0, -1, x0), (0, 1, x1 - 1), (1, -1, y0), (1, 1, y1 - 1)]
    for ax, sg, pos in sides:
        near = np.abs(c[:, ax] - pos) < 1.5
        if (ax, sg, pos) in [(0, -1, 0), (0, 1, w - 1), (1, -1, 0), (1, 1, h - 1)]:
            cut[near] = 1; continue
        for i in np.nonzero(near)[0]:
            xo, yo = int(c[i, 0]), int(c[i, 1])
            xo, yo = (xo + 2 * sg, yo) if ax == 0 else (xo, yo + 2 * sg)
            if 0 <= xo < w and 0 <= yo < h and full[yo, xo]:
                cut[i] = 1
    if sigma > 0:
        c = np.stack([gaussian_filter1d(c[:, 0], sigma, mode="wrap"), gaussian_filter1d(c[:, 1], sigma, mode="wrap")], 1)
    if scale:
        gx, gz = scale.to_ground(c[:, 0], c[:, 1])
    else:
        gx, gz = c[:, 0], -c[:, 1]
    pts = np.stack([gx, gz], 1)
    off = pts.mean(0) if center else np.zeros(2)
    pts = pts - off
    if poly_area(pts) < 0:
        pts = pts[::-1]; cut = cut[::-1]
    if step is None:
        step = scale.k if scale else 1.0
    pts, fl, L = resample_closed(pts, cut, step)
    return dict(pts=pts, cut=fl, perim=L, area=poly_area(pts), offset=off, scale=scale, step=step)


def write_outline(path, t, header):
    with open(path, "w", encoding="utf-8") as f:
        f.write(header.rstrip("\n") + "\n")
        for (a, b), cf in zip(t["pts"], t["cut"]):
            f.write(f"{a:.4f} {b:.4f} {int(cf)}\n")


def read_outline(path):
    rows = [ln.split() for ln in open(path, encoding="utf-8") if ln.strip() and not ln.startswith("#")]
    a = np.array([[float(r[0]), float(r[1]), float(r[2]) if len(r) > 2 else 0.0] for r in rows])
    return a[:, :2], a[:, 2] > 0.5


def raster_shape(pts, res):
    """地面点列栅格化(res 米/像素)后跑 shape_metrics,供地面空间里的前后对比。"""
    import cv2
    mn = pts.min(0) - 5 * res
    ij = np.round((pts - mn) / res).astype(np.int32)
    W, H = ij.max(0) + 6
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.stack([ij[:, 0], H - 1 - ij[:, 1]], 1)], 1)
    return shape_metrics(m), m


def chamfer(a, b):
    from scipy.spatial import cKDTree
    d1 = cKDTree(b).query(a)[0]; d2 = cKDTree(a).query(b)[0]
    return float(d1.mean()), float(d2.mean()), float(max(d1.max(), d2.max()))


def draw_plan(pts, cut, h, pad=24, grid=None, color=(255, 220, 0)):
    """地面点列画成高 h 的平面图(PIL RGB),带米制网格;cut 点红色。"""
    from PIL import Image, ImageDraw
    mn, mx = pts.min(0), pts.max(0); span = mx - mn
    sc = (h - 2 * pad) / max(span[1], 1e-6)
    W = int(span[0] * sc + 2 * pad)
    im = Image.new("RGB", (W, h), (24, 24, 28)); d = ImageDraw.Draw(im)

    def P(p):
        return (pad + (p[0] - mn[0]) * sc, h - pad - (p[1] - mn[1]) * sc)
    if grid:
        g = math.floor(mn[0] / grid) * grid
        while g <= mx[0]:
            x = P((g, 0))[0]; d.line([(x, 0), (x, h)], fill=(50, 50, 58)); g += grid
        g = math.floor(mn[1] / grid) * grid
        while g <= mx[1]:
            y = P((0, g))[1]; d.line([(0, y), (W, y)], fill=(50, 50, 58)); g += grid
    xy = [P(p) for p in pts]
    d.line(xy + [xy[0]], fill=color, width=2)
    for p, cf in zip(xy, cut):
        if cf:
            d.ellipse([p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2], fill=(255, 40, 40))
    return im
