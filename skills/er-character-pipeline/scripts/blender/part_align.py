# blender -b --factory-startup -P part_align.py -- --base <底模.glb> --src <来源整身.glb> --out <M.npy> --report <report.json>
#        [--bands 0-0.86] [--rigid] [--pants-core [半宽]] [--iters 60] [--samples 40000]
# 来源整身 -> 底模的点到面 ICP:先包围盒中心平移,再只用落在 --bands 高度区间里的来源顶点迭代。默认相似变换(统一缩放+旋转+平移),
# --rigid 退回刚体。输出 4x4 矩阵(p_base = M @ p_src,左上 3x3 已含缩放),报告 s、rot_deg、t(%H)和每个 band 双向 mean/p95/max(%H)。
# 高度分数 z = (z - 底模脚底) / H,H = 底模 z 范围;band 写 0 或 1 的一端不设限。--pants-core 给不碰 0 和 1 的中段 band 再加 |x-cx|<半宽(模型单位,默认 0.16;
# cx = 底模 0.3H~0.5H 顶点 x 的中位数),用来把垂在腿边的手排除掉。
# 上衣皮肤:--bands 0-0.15,0.18-0.50,0.87-1 --pants-core --rigid;发型皮肤:--bands 0-0.86。
import argparse
import json
import sys

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--src", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--report", required=True)
ap.add_argument("--bands", default="0-0.86")
ap.add_argument("--rigid", action="store_true")
ap.add_argument("--pants-core", nargs="?", type=float, const=0.16, default=None)
ap.add_argument("--iters", type=int, default=60)
ap.add_argument("--samples", type=int, default=40000)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
BANDS = [tuple(float(x) for x in b.split("-")) for b in args.bands.split(",")]


def load_mesh(path):
    """导入 glb,所有 mesh 物体的世界坐标顶点和三角形拼成一份(同 dump.py:不焊接,三角形取 loop_triangles)。"""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)
    cos, ts, off = [], [], 0
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        me = o.data
        mw = np.array(o.matrix_world)
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        me.calc_loop_triangles()
        t = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get("vertices", t)
        cos.append(co)
        ts.append(t.reshape(-1, 3) + off)
        off += len(co)
    return np.concatenate(cos), np.concatenate(ts)


bco, bt = load_mesh(args.base)
sco0, st0 = load_mesh(args.src)

zb = bco[:, 2].min()
H = float(bco[:, 2].max() - zb)
cx = float(np.median(bco[(bco[:, 2] > zb + 0.3 * H) & (bco[:, 2] < zb + 0.5 * H), 0]))


def band_masks(co):
    """每个 band 一个布尔掩码;下界 0 / 上界 1 不设限(来源比底模高或低出去的点也算);--pants-core 只作用在中段 band(下界 >0 且上界 <1)。"""
    z = (co[:, 2] - zb) / H
    out = {}
    for lo, hi in BANDS:
        m = np.ones(len(co), bool)
        if lo > 0:
            m &= z >= lo
        if hi < 1:
            m &= z <= hi
        if args.pants_core is not None and lo > 0 and hi < 1:
            m &= np.abs(co[:, 0] - cx) < args.pants_core
        out["%g-%g" % (lo, hi)] = m
    return out


def bvh(co, t):
    return BVHTree.FromPolygons([tuple(v) for v in co], [tuple(f) for f in t.tolist()], all_triangles=True)


def nearest(tree, pts):
    q = np.zeros_like(pts)
    n = np.zeros_like(pts)
    d = np.zeros(len(pts))
    for i, p in enumerate(pts):
        r = tree.find_nearest(Vector(p))
        q[i] = r[0]
        n[i] = r[1]
        d[i] = r[3]
    return q, n, d


def skew(k):
    return np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])


def rodrigues(w):
    th = np.linalg.norm(w)
    if th > 1e-12:
        K = skew(w / th)
        return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K, th
    return np.eye(3), th


# 1) 包围盒中心平移;参与 ICP 的点按平移后的位置判 band
t0 = (bco.min(0) + bco.max(0)) / 2 - (sco0.min(0) + sco0.max(0)) / 2
s, Rm, tv = 1.0, np.eye(3), t0.copy()
tb = bvh(bco, bt)
common = np.zeros(len(sco0), bool)
for m in band_masks(sco0 + t0).values():
    common |= m
idx = np.nonzero(common)[0]
rng = np.random.default_rng(0)
samp = idx if len(idx) <= args.samples else rng.choice(idx, args.samples, replace=False)

# 2) 点到面 ICP
hist = []
for it in range(args.iters):
    P = s * sco0[samp] @ Rm.T + tv
    Q, N, d = nearest(tb, P)
    keep = d < max(3.0 * np.median(d), 0.002 * H)
    p, q, n = P[keep], Q[keep], N[keep]
    b = ((q - p) * n).sum(1)
    if args.rigid:
        # 刚体:在原点线性化,x' = dR x + dt
        A = np.hstack([np.cross(p, n), n])
        x, *_ = np.linalg.lstsq(A, b, rcond=None)
        w, dt, ds = x[:3], x[3:], 0.0
        dR, th = rodrigues(w)
        Rm = dR @ Rm
        tv = dR @ tv + dt
    else:
        # 相似:在当前点集质心 c 处线性化,x' = (1+ds) dR (x - c) + c + dt
        c = p.mean(0)
        pc = p - c
        A = np.hstack([np.cross(pc, n), n, (pc * n).sum(1, keepdims=True)])
        x, *_ = np.linalg.lstsq(A, b, rcond=None)
        w, dt, ds = x[:3], x[3:6], x[6]
        dR, th = rodrigues(w)
        s = s * (1 + ds)
        Rm = dR @ Rm
        tv = (1 + ds) * dR @ (tv - c) + c + dt
    hist.append((it, float(np.mean(d[keep]) / H * 100), int(keep.sum()), float(th), float(ds),
                 float(np.linalg.norm(dt) / H * 100)))
    if th < 1e-6 and abs(ds) < 1e-7 and np.linalg.norm(dt) < 1e-6 * H:
        break

M = np.eye(4)
M[:3, :3] = s * Rm
M[:3, 3] = tv
np.save(args.out, M)

# 3) 指标:两方向,单位 %H;band 按对齐后的位置判
sco = s * sco0 @ Rm.T + tv
ts_ = bvh(sco, st0)
rs, rb = band_masks(sco), band_masks(bco)
_, _, d_sb = nearest(tb, sco)
_, _, d_bs = nearest(ts_, bco)


def stat(d):
    d = d / H * 100
    if len(d) == 0:
        return {"n": 0}
    return {"n": int(len(d)), "mean": round(float(d.mean()), 4), "p95": round(float(np.percentile(d, 95)), 4),
            "max": round(float(d.max()), 4)}


rep = {"base": args.base, "src": args.src, "mode": "rigid" if args.rigid else "similarity", "bands": args.bands,
       "pants_core_halfwidth": args.pants_core, "H_base": H, "H_src": float(np.ptp(sco0[:, 2])), "cx": cx,
       "bbox_shift": t0.tolist(), "scale_s": float(s), "R": Rm.tolist(), "t": tv.tolist(),
       "t_%H": (tv / H * 100).tolist(), "t_norm_%H": float(np.linalg.norm(tv) / H * 100),
       "rot_deg": float(np.degrees(np.arccos(np.clip((np.trace(Rm) - 1) / 2, -1, 1)))),
       "icp_samples": int(len(samp)), "icp_iters": len(hist), "icp_hist_first_last": [hist[0], hist[-1]],
       "per_band_%H": {}}
for k in rs:
    rep["per_band_%H"][k] = {"src_to_base": stat(d_sb[rs[k]]), "base_to_src": stat(d_bs[rb[k]])}
json.dump(rep, open(args.report, "w"), indent=1)
print("PART_ALIGN_DONE", json.dumps(rep))
