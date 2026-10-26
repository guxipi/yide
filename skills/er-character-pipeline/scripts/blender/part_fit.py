# blender -b --factory-startup -P part_fit.py -- --base <底模.glb> [--base-M <M.npy>] --part <部件.glb> [--part-M <M.npy>]
#        --out <适配后部件.glb> --report <report.json> [--clearance 0.25] [--smooth-iters 10] [--lambda 0.5] [--combo <组合.glb>] [--H <总高>] [--reproject 3]
# 发型/帽子类"叠在底模外"的件适配:底模和部件各自按 M 变到底模坐标(底模本身不动)。每个部件顶点到底模最近点 q、面法线 n,
# sd=(p-q)·n;δ0=max(0,c-sd)·n(只推不拉,c = clearance %H)。部件所有物体按位置焊接后一起做 uniform Laplacian 平滑位移向量,
# 每轮 δ += λ(邻居平均-δ),之后长度取 max(|δ0|,|δ|)(长度不回退)。H 默认 = 变换后底模的 z 范围,--H 可直接给。
# 平滑后再做 --reproject 轮补推:sd < 0.9c 的顶点沿当前最近面法线补到 c(平滑会带偏方向,不补会有个别顶点回到底模里面)。
# 输出 --out(适配后的部件,保留各物体和贴图),给了 --combo 再输出部件+底模组合。
import argparse
import json
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--base-M", default=None)
ap.add_argument("--part", required=True)
ap.add_argument("--part-M", default=None)
ap.add_argument("--out", required=True)
ap.add_argument("--report", required=True)
ap.add_argument("--clearance", type=float, default=0.25)
ap.add_argument("--smooth-iters", type=int, default=10)
ap.add_argument("--lambda", dest="lam", type=float, default=0.5)
ap.add_argument("--combo", default=None)
ap.add_argument("--H", type=float, default=None)
ap.add_argument("--reproject", type=int, default=3)  # 平滑后补推轮数;0 = 不补推(复现 10-26 原实验)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
MM = 18.0  # 1%H 换算成 mm,按 1.80 m 角色身高

bpy.ops.wm.read_factory_settings(use_empty=True)


def import_bake(path, M):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.data.transform(mw)
        o.data.transform(M)
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    return meshes


def export(path, objs):
    for o in bpy.data.objects:
        o.select_set(o in objs)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)


def get_co(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def get_tris(me):
    me.calc_loop_triangles()
    a = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", a)
    return a.reshape(-1, 3)


def mat(path):
    return Matrix(np.load(path).tolist()) if path else Matrix.Identity(4)


part = sorted(import_bake(args.part, mat(args.part_M)), key=lambda o: o.name)
base = import_bake(args.base, mat(args.base_M))
for o in base:
    o.name = "base_" + o.name

bcos, bts, off = [], [], 0
for o in base:
    c, t = get_co(o.data), get_tris(o.data)
    bcos.append(c); bts.append(t + off); off += len(c)
bco, bt = np.concatenate(bcos), np.concatenate(bts)
H = args.H if args.H else float(np.ptp(bco[:, 2]))
CLR = args.clearance / 100 * H
tree = BVHTree.FromPolygons([tuple(v) for v in bco], [tuple(f) for f in bt.tolist()], all_triangles=True)
rep = {"base": args.base, "base_M": args.base_M, "part": args.part, "part_M": args.part_M, "H": H,
       "H_source": "--H" if args.H else "base z range", "clearance_c_%H": args.clearance,
       "smooth_iters": args.smooth_iters, "lambda": args.lam,
       "part_objects_tris": {o.name: len(o.data.polygons) for o in part}}
rep["part_tris_total"] = sum(rep["part_objects_tris"].values())

# 部件所有物体按位置焊接
cos, tris, off, spans = [], [], 0, []
for o in part:
    c, t = get_co(o.data), get_tris(o.data)
    cos.append(c); tris.append(t + off); spans.append((o, off, off + len(c))); off += len(c)
co = np.concatenate(cos); tr = np.concatenate(tris)
_, wid = np.unique(np.round(co / 1e-6).astype(np.int64), axis=0, return_inverse=True)
wid = wid.ravel()
nw = int(wid.max()) + 1
wco = np.zeros((nw, 3)); wco[wid] = co
owner = np.full(nw, -1); multi = np.zeros(nw, bool)
for k, (o, a, b) in enumerate(spans):
    ids = np.unique(wid[a:b]); multi[ids[owner[ids] >= 0]] = True; owner[ids] = k
rep["part_verts_split"] = int(len(co)); rep["part_verts_welded"] = nw
rep["welded_verts_shared_between_objects"] = int(multi.sum())
tw = wid[tr]
e = np.concatenate([tw[:, [0, 1]], tw[:, [1, 2]], tw[:, [2, 0]]])
e = np.unique(np.sort(e, 1), axis=0)
e = e[e[:, 0] != e[:, 1]]
deg = np.bincount(e.ravel(), minlength=nw).astype(float)

# 只推不拉 + 平滑位移场
sd = np.zeros(nw); nrm = np.zeros((nw, 3))
for i in range(nw):
    q, n, _, _ = tree.find_nearest(Vector(wco[i]))
    nrm[i] = n
    sd[i] = (Vector(wco[i]) - q).dot(n)
d0 = np.maximum(0.0, CLR - sd)[:, None] * nrm
L0 = np.linalg.norm(d0, axis=1)
d = d0.copy()
for it in range(args.smooth_iters):
    acc = np.zeros((nw, 3))
    np.add.at(acc, e[:, 0], d[e[:, 1]])
    np.add.at(acc, e[:, 1], d[e[:, 0]])
    avg = np.where(deg[:, None] > 0, acc / np.maximum(deg, 1)[:, None], d)
    d = d + args.lam * (avg - d)
    Ls = np.linalg.norm(d, axis=1)
    fix = Ls < L0
    d[fix] = np.where(Ls[fix, None] > 0, d[fix] / np.maximum(Ls[fix, None], 1e-30) * L0[fix, None], d0[fix])
L = np.linalg.norm(d, axis=1)


def dist(v):
    v = v / H * 100
    if len(v) == 0:
        return None
    q = {"mean": float(v.mean()), "p50": float(np.percentile(v, 50)), "p95": float(np.percentile(v, 95)), "max": float(v.max())}
    return {k: {"%H": round(x, 4), "mm": round(x * MM, 2)} for k, x in q.items()}


rep["sd_before_%H"] = {"min": float(sd.min() / H * 100), "p5": float(np.percentile(sd, 5) / H * 100),
                       "p50": float(np.percentile(sd, 50) / H * 100),
                       "frac_below_0": float((sd < 0).mean()), "frac_below_c": float((sd < CLR).mean())}
rep["pushed_by_rule_delta0>0"] = {"n": int((L0 > 0).sum()), "pct": round(100 * float((L0 > 0).mean()), 2)}
rep["moved_after_smoothing_|delta|>0"] = {"n": int((L > 1e-12).sum()), "pct": round(100 * float((L > 1e-12).mean()), 2)}
rep["disp_delta0_on_pushed"] = dist(L0[L0 > 0])
rep["disp_final_on_moved"] = dist(L[L > 1e-12])
rep["disp_final_over_all_part_verts"] = dist(L)


def signed(pts):
    s = np.zeros(len(pts)); nn = np.zeros((len(pts), 3))
    for i, p in enumerate(pts):
        q, n, _, _ = tree.find_nearest(Vector(p))
        nn[i] = n
        s[i] = (Vector(p) - q).dot(n)
    return s, nn


# 再投影:平滑会把位移方向带偏,个别顶点又回到 c 以内甚至底模里面;只对这些顶点沿当前最近面法线补推到 c
sd2, n2 = signed(wco + d)
rep["reproject"] = []
for it in range(args.reproject):
    bad = sd2 < CLR * 0.9
    if not bad.any():
        break
    d[bad] += (CLR - sd2[bad])[:, None] * n2[bad]
    sd2, n2 = signed(wco + d)
    rep["reproject"].append({"pass": it + 1, "fixed_verts": int(bad.sum()),
                             "below_0_after": int((sd2 < 0).sum())})
newco = wco + d
rep["sd_after_%H"] = {"min": float(sd2.min() / H * 100), "p5": float(np.percentile(sd2, 5) / H * 100),
                      "p50": float(np.percentile(sd2, 50) / H * 100), "frac_below_0": float((sd2 < 0).mean()),
                      "frac_below_c_minus_1e-3%H": float((sd2 < CLR - 1e-5 * H).mean())}
for o, a, b in spans:
    o.data.vertices.foreach_set("co", (co[a:b] + d[wid[a:b]]).ravel())
    o.data.update()
export(args.out, part)
if args.combo:
    export(args.combo, part + base)
rep["out"], rep["combo"] = args.out, args.combo
json.dump(rep, open(args.report, "w"), indent=1)
print("PART_FIT_DONE", json.dumps(rep))
