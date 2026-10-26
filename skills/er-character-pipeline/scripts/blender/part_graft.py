# blender -b --factory-startup -P part_graft.py -- --base <底模.glb> --src <来源整身.glb> --M <M.npy> --mask <mask.npy>
#        --out <组合.glb> --report <report.json> [--margin 1.0] [--snap|--no-snap] [--falloff 2.0] [--push 0.15]
# 上衣/下装类"盖住底模"的件贴回:整身按 M 变到底模坐标,按掩码切出件;删底模被件盖住的面(离件边界 < margin 的留作裙边);
# 件边界环吸附到底模保留面(周围 falloff 内线性衰减跟随);底模穿出件外的点推到件面内 push。底模身体不做别的改动。
# 删面判据:底模每个面的质心在对齐后的整身上找最近表面点,该点所在三角形属于件、且离件边界 >= margin → 删。
# 输出 --out(底模剪过 + 件吸附后合成一个物体,两材质)和同目录 <out 名>_piece.glb(单独件)。
# 边界环按长度从长到短命名 loop_0..n,报告每个环的质心高度分数(按底模脚底和总高)、缝隙和穿模。单位一律 %H(H = 底模 z 范围)。
import argparse
import json
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True)
ap.add_argument("--src", required=True)
ap.add_argument("--M", required=True)
ap.add_argument("--mask", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--report", required=True)
ap.add_argument("--margin", type=float, default=1.0)
ap.add_argument("--snap", dest="snap", action="store_true", default=True)
ap.add_argument("--no-snap", dest="snap", action="store_false")
ap.add_argument("--falloff", type=float, default=2.0)
ap.add_argument("--push", type=float, default=0.15)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
MARGIN, SNAP = args.margin, args.snap
M = Matrix(np.load(args.M).tolist())
is_pc = np.load(args.mask).astype(bool)
PIECE_OUT = os.path.splitext(args.out)[0] + "_piece.glb"

bpy.ops.wm.read_factory_settings(use_empty=True)


def ctx(obj, sel=None):
    sel = sel or [obj]
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(o in sel)
    bpy.context.view_layer.objects.active = obj
    return {"object": obj, "active_object": obj, "selected_objects": sel, "selected_editable_objects": sel,
            "view_layer": bpy.context.view_layer, "scene": bpy.context.scene}


def load(path, name):
    """导入 glb,世界矩阵烘进 mesh;多个 mesh 物体合成一个。"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for mesh in meshes:
        mw = mesh.matrix_world.copy()
        mesh.parent = None
        mesh.data.transform(mw)
        mesh.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    mesh = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(**ctx(mesh, meshes)):
            bpy.ops.object.join()
    mesh.name = name
    return mesh


def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def weld(obj, dist=1e-5):
    """按位置焊接,保留原拐角法线。"""
    me = obj.data
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", n)
    a = me.attributes.new("_kn", "FLOAT_VECTOR", "CORNER")
    a.data.foreach_set("vector", n)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(me)
    bm.free()
    a = me.attributes["_kn"]
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    a.data.foreach_get("vector", n)
    me.attributes.remove(me.attributes["_kn"])
    me.normals_split_custom_set(n.reshape(-1, 3).tolist())
    me.update()


def delete_faces(obj, mask):
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.faces[i] for i in np.nonzero(mask)[0]], context="FACES")
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def bvh_of(obj):
    me = obj.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def boundary_loops(obj):
    """开放边连成的环,按长度从长到短排。"""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    be = [e for e in bm.edges if e.is_boundary]
    adj = {}
    for e in be:
        a, b = e.verts[0].index, e.verts[1].index
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    co = {v.index: v.co.copy() for v in bm.verts}
    bm.free()
    seen, loops = set(), []
    for s in adj:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        L = sum((co[a] - co[b]).length for a in comp for b in adj[a] if a < b)
        loops.append({"verts": comp, "len": L, "c": np.mean([co[i] for i in comp], 0)})
    return sorted(loops, key=lambda l: -l["len"])


# ------------------------------------------------ 载入
base = load(args.base, "base")
sfull = load(args.src, "src_full")
sfull.data.transform(M)
assert len(sfull.data.polygons) == len(is_pc), (len(sfull.data.polygons), len(is_pc))
bco = coords(base.data)
H = float(bco[:, 2].max() - bco[:, 2].min())
zb = float(bco[:, 2].min())
PUSH = args.push / 100 * H
tree_full = bvh_of(sfull)
pc = sfull.copy()
pc.data = sfull.data.copy()
bpy.context.scene.collection.objects.link(pc)
delete_faces(pc, ~is_pc)
pc.name = "piece"
weld(pc)
_jb = coords(pc.data)
_bl = boundary_loops(pc)
_bp = np.concatenate([_jb[l["verts"]] for l in _bl])
kd_b = KDTree(len(_bp))
for i, p in enumerate(_bp):
    kd_b.insert(Vector(p), i)
kd_b.balance()

# ------------------------------------------------ 删底模被盖住的面
bc = np.empty(len(base.data.polygons) * 3)
base.data.polygons.foreach_get("center", bc)
bc = bc.reshape(-1, 3)
cover = np.zeros(len(bc), bool)
dnear = np.zeros(len(bc))
for i, p in enumerate(bc):
    r = tree_full.find_nearest(Vector(p))
    cover[i] = is_pc[r[2]] and (MARGIN <= 0 or kd_b.find(r[0])[2] >= MARGIN / 100 * H)
    dnear[i] = r[3]
rep = {"base": args.base, "src": args.src, "M": args.M, "mask": args.mask, "margin_%H": MARGIN, "snap": SNAP,
       "falloff_%H": args.falloff, "push_%H": args.push, "H": H, "mask_tris": int(is_pc.sum()),
       "base_tris": len(bc), "base_tris_deleted": int(cover.sum()),
       "deleted_dist_to_piece_%H": {"mean": float(dnear[cover].mean() / H * 100) if cover.any() else 0.0,
                                    "max": float(dnear[cover].max() / H * 100) if cover.any() else 0.0}}
delete_faces(base, cover)
rep["base_tris_kept"] = len(base.data.polygons)

bpy.data.objects.remove(sfull, do_unlink=True)
rep["piece_tris"] = len(pc.data.polygons)
weld(base)


def measure(tag):
    """缝隙:件每条边界环的顶点 -> 底模保留面最近距离;穿模:被件盖住那类底模顶点在件面外侧(离件边界 >0.15%H 处)。"""
    tb = bvh_of(base)
    tj = bvh_of(pc)
    loops = boundary_loops(pc)
    jco = coords(pc.data)
    out = {"loops": {}}
    for k, l in enumerate(loops):
        d = np.array([tb.find_nearest(Vector(jco[i]))[3] for i in l["verts"]])
        out["loops"]["loop_%d" % k] = {"loop_verts": len(l["verts"]), "loop_len_%H": round(l["len"] / H * 100, 2),
                                       "centroid_z_frac": round(float((l["c"][2] - zb) / H), 4),
                                       "centroid": [round(float(x), 4) for x in l["c"]],
                                       "gap_mean_%H": round(float(d.mean() / H * 100), 3),
                                       "gap_p95_%H": round(float(np.percentile(d, 95) / H * 100), 3),
                                       "gap_max_%H": round(float(d.max() / H * 100), 3)}
    # 穿模
    bnd = np.concatenate([jco[l["verts"]] for l in loops]) if loops else np.zeros((0, 3))
    kd = KDTree(len(bnd))
    for i, p in enumerate(bnd):
        kd.insert(Vector(p), i)
    kd.balance()
    bco2 = coords(base.data)
    pokes = []
    for i, v in enumerate(bco2):
        # 只查"裙边"顶点:它在整身上的最近点属于件(即被件盖住的那类底模),其余部位不算
        if not is_pc[tree_full.find_nearest(Vector(v))[2]]:
            continue
        q, n, fi, d = tj.find_nearest(Vector(v), 0.03 * H)
        if q is None:
            continue
        s = (Vector(v) - q).dot(n)
        if s > 1e-4 * H:
            db = kd.find(q)[2]
            if db > 0.0015 * H:
                pokes.append((i, s, q, n))
    depth = np.array([p[1] for p in pokes]) if pokes else np.zeros(0)
    out["poke_verts"] = len(pokes)
    out["poke_max_%H"] = round(float(depth.max() / H * 100), 3) if len(depth) else 0.0
    if len(pokes):
        pz = np.array([bco2[p[0]][2] for p in pokes])
        out["poke_z_%H_range"] = [round(float((pz.min() - zb) / H * 100), 1), round(float((pz.max() - zb) / H * 100), 1)]
    rep[tag] = out
    return loops, pokes


def export(objs, path):
    with bpy.context.temp_override(**ctx(objs[0], objs)):
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True)


loops_raw, pokes = measure("raw")

# ------------------------------------------------ 修
# (a) 穿模:底模顶点推到件面内 push(只动穿出点)。(b) 缝隙:件边界环顶点吸附到底模保留面最近点,
#     周围 falloff 内的件顶点按 (1-d/falloff) 线性衰减跟着移(底模身体不动,底模是多套衣服共用的)。
me = base.data
for i, s, q, n in pokes:
    me.vertices[i].co = q - n * PUSH
me.update()
tb = bvh_of(base)
jme = pc.data
moved, maxsnap = 0, 0.0
if SNAP and loops_raw:
    jco = coords(jme)
    disp_pts, disp = [], []
    for l in loops_raw:
        for i in l["verts"]:
            q = tb.find_nearest(Vector(jco[i]))[0]
            disp_pts.append(jco[i])
            disp.append(np.array(q) - jco[i])
    disp_pts = np.array(disp_pts)
    disp = np.array(disp)
    kd = KDTree(len(disp_pts))
    for i, p in enumerate(disp_pts):
        kd.insert(Vector(p), i)
    kd.balance()
    R = args.falloff / 100 * H
    newco = jco.copy()
    for i, p in enumerate(jco):
        co_, j, d = kd.find(Vector(p))
        if d < R:
            newco[i] = p + disp[j] * (1 - d / R)
            moved += 1
    jme.vertices.foreach_set("co", newco.ravel())
    jme.update()
    maxsnap = float(np.linalg.norm(disp, axis=1).max() / H * 100)
rep["fix"] = {"pushed_base_verts": len(pokes), "piece_verts_moved": moved, "falloff_%H": args.falloff if SNAP else 0,
              "max_snap_%H": round(maxsnap, 3)}
if SNAP:  # 吸附后件边缘往里收了一点,裙边可能又穿出:再推一遍
    _, pokes2 = measure("after_snap")
    for i, s_, q, n in pokes2:
        me.vertices[i].co = q - n * PUSH
    me.update()
    rep["fix"]["pushed_base_verts_after_snap"] = len(pokes2)
measure("fixed")
export([pc], PIECE_OUT)
with bpy.context.temp_override(**ctx(base, [base, pc])):
    bpy.ops.object.join()
rep["combo_tris"] = len(base.data.polygons)
rep["combo_materials"] = len(base.data.materials)
export([base], args.out)
rep["out"], rep["out_piece"] = args.out, PIECE_OUT
json.dump(rep, open(args.report, "w"), indent=1)
print("PART_GRAFT_DONE", json.dumps(rep))
