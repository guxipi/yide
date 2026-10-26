# blender -b --factory-startup -P head_shave.py -- --base <base.glb> --hair_mask <npy, 每个 base 三角形(glb 导入后 loop_triangles 顺序)是否头发>
#        --buzz <buzz.glb> --buzz_M <4x4 npy> --iters <N> --out <dir> [--out_name base_shaved.glb]
#        [--clamp brow|face_front] [--brow_luma 0.15] [--brow_margin_pct 0.3] [--analyze 40,80] [--no_build] [--export_parts]
# 剃头:老英雄底模保留定稿脸,只把头发区换成寸头生成的头皮(10-26 Coda 第六轮定案)。
#  1) base 按位置焊接(保留 corner normals);顶点 h0 = 1 只连头发面 / 0 只连非头发面 / 0.5 都连;
#     uniform Laplacian 扩散 N 轮(λ=0.5)。约束区里 h 必须 <0.5,不满足时在该区域每轮把 h 钳到 ≤0.45 再扩散。
#     --clamp brow(默认):约束区 = 脸前部(头部 z>0.86H、法线朝外、最前 35% 深度)且 z < z_brow_top + brow_margin_pct%H;
#       眉毛自动找:脸前部、非头发、贴图亮度(3 角最近像素平均,Rec.709)< brow_luma 的三角形按共点连通成块,
#       在 0.90H<质心 z<0.95H 的块里取中线左右各最大的一块;z_brow_top = 两块三角形质心 z 的最大值。
#     --clamp face_front:旧口径(10-26 第五轮,会把前额两角的卷发留在底模上,别用),约束区 = 脸前部且 z<hairline_pct%H。
#     --analyze 给出多档迭代数的 0.5 等值线统计。
#  2) 在 h 跨 0.5 的边上线性插值精确切分(切点 UV、custom normal 在每个面内按两端插值),删 h>0.5 一侧的面。
#  3) 寸头(buzz_M 变到 base)焊接后,每个顶点投到原 base(焊接后、未切)最近点,按重心插值取 h;同样在 0.5 处精确切,
#     留 h>0.5 一侧,再只留最大连通块。
#  4) 帽子主边界环吸附到 base 洞环折线最近点并沿帽子法线往里收 0.05%H,2%H 线性衰减;join 后 bmesh.ops.bridge_loops 桥接,
#     桥面 base 材质、UV 每个桥面从同一个 base 面取(跨 UV 缝取会在桥带拉出黑条);只对桥面顶点 + 两侧 1-ring 做 3 轮 uniform Laplacian(λ=0.5);
#     base 允许动的只有洞环和它的 1-ring。被动区域的 corner 法线重算,其余保留。
#  5) 量开放边、非流形边、桥面、接缝夹角、base 位移;导出 --out_name 和 build_report.json、场数据 field.npz。
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
ap.add_argument("--base"); ap.add_argument("--hair_mask"); ap.add_argument("--buzz"); ap.add_argument("--buzz_M")
ap.add_argument("--iters", type=int, default=40); ap.add_argument("--out")
ap.add_argument("--analyze", default=""); ap.add_argument("--no_build", action="store_true")
ap.add_argument("--hairline_pct", type=float, default=94.40)
ap.add_argument("--clamp", default="brow", choices=["brow", "face_front"])
ap.add_argument("--brow_luma", type=float, default=0.15); ap.add_argument("--brow_margin_pct", type=float, default=0.3)
ap.add_argument("--out_name", default="base_shaved.glb"); ap.add_argument("--export_parts", action="store_true")
A = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
os.makedirs(A.out, exist_ok=True)
H = 0.978851318359375
MM = 18.0
RAD = 0.02 * H
INSET = 0.0005 * H
rep = {"args": vars(A)}

bpy.ops.wm.read_factory_settings(use_empty=True)


def ctx(obj, sel=None):
    sel = sel or [obj]
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        o.select_set(o in sel)
    bpy.context.view_layer.objects.active = obj
    return {"object": obj, "active_object": obj, "selected_objects": sel, "selected_editable_objects": sel,
            "view_layer": bpy.context.view_layer, "scene": bpy.context.scene}


def load(path, name, M=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    mesh = [o for o in new if o.type == "MESH"][0]
    mw = mesh.matrix_world.copy()
    mesh.parent = None
    mesh.data.transform(mw)
    if M is not None:
        mesh.data.transform(M)
    mesh.matrix_world = Matrix.Identity(4)
    for o in new:
        if o is not mesh:
            bpy.data.objects.remove(o, do_unlink=True)
    mesh.name = name
    return mesh


def keep_normals(me):
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", n)
    a = me.attributes.new("_kn", "FLOAT_VECTOR", "CORNER")
    a.data.foreach_set("vector", n)


def restore_normals(me):
    a = me.attributes["_kn"]
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    a.data.foreach_get("vector", n)
    me.attributes.remove(me.attributes["_kn"])
    me.normals_split_custom_set(n.reshape(-1, 3).tolist())
    me.update()


def weld(me, dist=1e-6):
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(me)
    bm.free()
    me.update()


def tri_flag_to_face_attr(me, mask, name):
    me.calc_loop_triangles()
    assert len(me.loop_triangles) == len(mask) == len(me.polygons)
    p = np.empty(len(me.loop_triangles), np.int64)
    me.loop_triangles.foreach_get("polygon_index", p)
    f = np.zeros(len(me.polygons), np.int32)
    f[p] = mask.astype(np.int32)
    a = me.attributes.new(name, "INT", "FACE")
    a.data.foreach_set("value", f)


def coords(me):
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def mesh_arrays(me):
    co = coords(me)
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    e = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", e)
    return co, t.reshape(-1, 3), e.reshape(-1, 2)


def seg_nearest(P, A_, B_):
    AB = B_ - A_
    L2 = np.maximum((AB ** 2).sum(1), 1e-30)
    bq = np.zeros_like(P)
    bd = np.full(len(P), np.inf)
    for s in range(0, len(P), 256):
        p = P[s:s + 256]
        t = np.clip(((p[:, None, :] - A_[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        q = A_[None] + t[..., None] * AB[None]
        d = np.linalg.norm(p[:, None, :] - q, axis=2)
        k = d.argmin(1)
        bd[s:s + 256] = d[np.arange(len(p)), k]
        bq[s:s + 256] = q[np.arange(len(p)), k]
    return bq, bd


def st(v, scale=True):
    v = np.asarray(v, float)
    if scale:
        v = v / H * 100
    return {"mean": round(float(v.mean()), 4), "p95": round(float(np.percentile(v, 95)), 4), "max": round(float(v.max()), 4)}


def iso_lines(co, t, h, level=0.5):
    """三角网格上 h=level 等值线:返回点坐标、所在边 key、线段(点索引对)、每段所在三角形号"""
    key = {}
    pts = []
    segs = []
    seg_tri = []

    def pt(a, b):
        k = (min(a, b), max(a, b))
        if k not in key:
            ta = (level - h[a]) / (h[b] - h[a])
            key[k] = len(pts)
            pts.append(co[a] + ta * (co[b] - co[a]))
        return key[k]
    for fi, (a, b, c) in enumerate(t):
        cr = [(x, y) for x, y in ((a, b), (b, c), (c, a)) if (h[x] - level) * (h[y] - level) < 0]
        if len(cr) == 2:
            segs.append((pt(*cr[0]), pt(*cr[1])))
            seg_tri.append(fi)
    return np.array(pts), np.array(segs, np.int64).reshape(-1, 2), np.array(seg_tri, np.int64)


def chains(n, segs):
    adj = [[] for _ in range(n)]
    for a, b in segs:
        adj[a].append(b); adj[b].append(a)
    seen = np.zeros(n, bool)
    out = []
    for s in range(n):
        if seen[s] or not adj[s]:
            continue
        ch = [s]; seen[s] = True
        prev, cur = None, s
        while True:
            nx = [x for x in adj[cur] if x != prev and not seen[x]]
            if not nx:
                break
            prev, cur = cur, nx[0]
            ch.append(cur); seen[cur] = True
        closed = len(adj[s]) == 2 and s in adj[cur]
        out.append((ch, closed))
    return out, adj


def turn_count(P, chs, thr=60.0):
    n = 0
    angs = []
    for ch, closed in chs:
        m = len(ch)
        rng = range(m) if closed else range(1, m - 1)
        for i in rng:
            a, b, c = P[ch[i - 1]], P[ch[i]], P[ch[(i + 1) % m]]
            u, v = b - a, c - b
            nu, nv = np.linalg.norm(u), np.linalg.norm(v)
            if nu < 1e-12 or nv < 1e-12:
                continue
            ang = np.degrees(np.arccos(np.clip(np.dot(u, v) / nu / nv, -1, 1)))
            angs.append(ang)
            n += ang > thr
    return int(n), np.array(angs)


# ------------------------------------------------------------------ base + 场
base = load(A.base, os.path.splitext(A.out_name)[0])
orig_glb = coords(base.data).copy()
tri_flag_to_face_attr(base.data, np.load(A.hair_mask), "_hair")
keep_normals(base.data)
weld(base.data)
bco, btri, bedge = mesh_arrays(base.data)
fh = np.empty(len(base.data.polygons), np.int32)
base.data.attributes["_hair"].data.foreach_get("value", fh)
ptri = np.empty(len(base.data.loop_triangles), np.int64)
base.data.loop_triangles.foreach_get("polygon_index", ptri)
thair = fh[ptri].astype(bool)
nv = len(bco)
cnt_h = np.zeros(nv); cnt_n = np.zeros(nv)
for j in range(3):
    np.add.at(cnt_h, btri[thair, j], 1)
    np.add.at(cnt_n, btri[~thair, j], 1)
h0 = np.where(cnt_n == 0, 1.0, np.where(cnt_h == 0, 0.0, 0.5))
deg = np.bincount(bedge.ravel(), minlength=nv).astype(float)
# 脸前部(r1 定义,在 base 上算)
fn = np.cross(bco[btri[:, 1]] - bco[btri[:, 0]], bco[btri[:, 2]] - bco[btri[:, 0]])
vn = np.zeros((nv, 3))
for j in range(3):
    np.add.at(vn, btri[:, j], fn)
vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-20)
head = bco[:, 2] / H > 0.86
hc = (bco[head].min(0) + bco[head].max(0)) / 2
ymin, ymax = bco[head, 1].min(), bco[head, 1].max()
front_y = ymin + 0.35 * (ymax - ymin)
face_front = head & ((vn * (bco - hc)).sum(1) > 0) & (bco[:, 1] < front_y) & (bco[:, 2] < A.hairline_pct / 100 * H)
rep["face_front_verts"] = int(face_front.sum())
front_zone = head & ((vn * (bco - hc)).sum(1) > 0) & (bco[:, 1] < front_y)
if A.clamp == "face_front":
    clamp_zone = face_front
else:
    # 眉毛:脸前部、非头发、近黑三角形
    me_ = base.data
    img = None
    for m_ in me_.materials:
        if m_ and m_.node_tree:
            img = next((n_.image for n_ in m_.node_tree.nodes if n_.type == "TEX_IMAGE" and n_.image), None)
            if img:
                break
    iw, ih = img.size
    px = np.empty(iw * ih * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(ih, iw, 4)
    luv = np.empty(len(me_.loops) * 2)
    me_.uv_layers.active.data.foreach_get("uv", luv)
    luv = luv.reshape(-1, 2)
    lt_ = np.empty(len(me_.loop_triangles) * 3, np.int64)
    me_.loop_triangles.foreach_get("loops", lt_)
    tuv = luv[lt_.reshape(-1, 3)]
    xs = np.clip((tuv[..., 0] % 1.0 * iw).astype(int), 0, iw - 1)
    ys = np.clip((tuv[..., 1] % 1.0 * ih).astype(int), 0, ih - 1)
    lum = px[ys, xs, :3].mean(1) @ np.array([0.2126, 0.7152, 0.0722])
    tc = bco[btri].mean(1)
    tz = np.all(front_zone[btri], axis=1)
    cand = tz & ~thair & (lum < A.brow_luma)
    idx_ = np.nonzero(cand)[0]
    par = {}

    def fnd(a):
        while par.get(a, a) != a:
            a = par[a]
        return a
    for tt in idx_:
        a_, b_, c_ = (int(x) for x in btri[tt])
        ra = fnd(a_)
        rb = fnd(b_)
        if rb != ra:
            par[rb] = ra
        rc = fnd(c_)
        if rc != ra:
            par[rc] = ra
    lab_ = np.array([fnd(int(btri[tt][0])) for tt in idx_])
    blocks_ = []
    for r_ in np.unique(lab_):
        mm = idx_[lab_ == r_]
        blocks_.append({"tris": mm, "n": int(len(mm)), "cz": float(tc[mm, 2].mean()), "cx": float(tc[mm, 0].mean())})
    cxm = float(hc[0])
    band_ = [b for b in blocks_ if 0.90 * H < b["cz"] < 0.95 * H]
    left_ = max([b for b in band_ if b["cx"] < cxm], key=lambda b: b["n"])
    right_ = max([b for b in band_ if b["cx"] > cxm], key=lambda b: b["n"])
    brow_t = np.concatenate([left_["tris"], right_["tris"]])
    z_brow_top = float(tc[brow_t, 2].max())
    rep["brow"] = {"luma_thr": A.brow_luma, "dark_candidate_tris": int(cand.sum()),
                   "dark_blocks_top10": sorted([{"n": b["n"], "cz_%H": round(b["cz"] / H * 100, 2), "cx": round(b["cx"], 4)} for b in blocks_],
                                               key=lambda d: -d["n"])[:10],
                   "brow_left_tris": left_["n"], "brow_right_tris": right_["n"],
                   "brow_left_cz_%H": round(left_["cz"] / H * 100, 3), "brow_right_cz_%H": round(right_["cz"] / H * 100, 3),
                   "z_brow_top": z_brow_top, "z_brow_top_%H": round(z_brow_top / H * 100, 3),
                   "clamp_z_limit_%H": round(z_brow_top / H * 100 + A.brow_margin_pct, 3)}
    np.save(os.path.join(A.out, "brow_tri_centroids.npy"), tc[brow_t])
    clamp_zone = front_zone & (bco[:, 2] < z_brow_top + A.brow_margin_pct / 100 * H)
rep["clamp_mode"] = A.clamp
rep["clamp_zone_verts"] = int(clamp_zone.sum())
rep["h0_counts"] = {"1": int((h0 == 1).sum()), "0.5": int((h0 == 0.5).sum()), "0": int((h0 == 0).sum())}
# 原锯齿边界(头发面/非头发面之间的边)
bm = bmesh.new(); bm.from_mesh(base.data)
hl = bm.faces.layers.int.get("_hair")
jag = np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges
                if len(e.link_faces) == 2 and e.link_faces[0][hl] != e.link_faces[1][hl]])
bm.free()
rep["jagged_boundary_edges"] = int(len(jag))


def diffuse(n_it, clamp):
    h = h0.copy()
    for _ in range(n_it):
        acc = np.zeros(nv)
        np.add.at(acc, bedge[:, 0], h[bedge[:, 1]])
        np.add.at(acc, bedge[:, 1], h[bedge[:, 0]])
        h = h + 0.5 * (acc / np.maximum(deg, 1) - h)
        if clamp:
            h[clamp_zone] = np.minimum(h[clamp_zone], 0.45)
    h[np.abs(h - 0.5) < 1e-9] = 0.5 + 1e-6
    return h


def field(n_it):
    h = diffuse(n_it, False)
    viol = int((h[clamp_zone] >= 0.5).sum())
    clamped = viol > 0
    if clamped:
        h = diffuse(n_it, True)
    return h, viol, clamped


def iso_stats(h):
    P, S, _ = iso_lines(bco, btri, h)
    chs, _ = chains(len(P), S)
    nt, angs = turn_count(P, chs)
    _, d = seg_nearest(P, bco[jag[:, 0]], bco[jag[:, 1]])
    return {"iso_points": int(len(P)), "iso_chains": sorted([len(c) for c, _ in chs], reverse=True)[:10],
            "iso_chains_closed": int(sum(1 for _, cl in chs if cl)),
            "turn_gt60_verts": nt, "turn_deg": st(angs, False),
            "dist_to_jagged_%H": {"mean": round(float(d.mean() / H * 100), 4), "max": round(float(d.max() / H * 100), 4)},
            "clamp_zone_h_ge_0.5": int((h[clamp_zone] >= 0.5).sum()),
            "r1_face_front_h_ge_0.5(info)": int((h[face_front] >= 0.5).sum())}


if A.analyze:
    rep["analyze"] = {}
    for n_it in [int(x) for x in A.analyze.split(",")]:
        h, viol, cl = field(n_it)
        s = iso_stats(h)
        s.update({"clamp_zone_violations_unclamped": viol, "clamped": cl})
        su = iso_stats(diffuse(n_it, False))
        s["unclamped_turn_gt60_verts"] = su["turn_gt60_verts"]
        s["unclamped_dist_to_jagged_%H"] = su["dist_to_jagged_%H"]
        # 尖角落在哪:离脸前部顶点 <1%H 的尖角数(钳制边界附近)
        P_, S_, _ = iso_lines(bco, btri, h)
        chs_, _ = chains(len(P_), S_)
        ffk = KDTree(int(clamp_zone.sum()))
        for j_, p_ in enumerate(bco[clamp_zone]):
            ffk.insert(Vector(p_), j_)
        ffk.balance()
        near = 0
        seglen = []
        for ch_, cl_ in chs_:
            m_ = len(ch_)
            for i_ in range(m_):
                a_, b_, c_ = P_[ch_[i_ - 1]], P_[ch_[i_]], P_[ch_[(i_ + 1) % m_]]
                u_, v_ = b_ - a_, c_ - b_
                if np.linalg.norm(u_) < 1e-12 or np.linalg.norm(v_) < 1e-12:
                    continue
                ang_ = np.degrees(np.arccos(np.clip(u_ @ v_ / np.linalg.norm(u_) / np.linalg.norm(v_), -1, 1)))
                if ang_ > 60:
                    near += ffk.find(Vector(b_))[2] < 0.01 * H
                    seglen.append(min(np.linalg.norm(u_), np.linalg.norm(v_)) / H * 100)
        s["turn_gt60_near_clamp_zone_1%H"] = int(near)
        s["turn_gt60_shorter_adjacent_seg_%H"] = st(seglen, False) if seglen else None
        rep["analyze"][str(n_it)] = s
        print("ANALYZE", n_it, json.dumps(s))
    s0 = iso_stats(np.where(h0 > 0.5, 1.0, np.where(h0 < 0.5, 0.0, 0.5 + 1e-6)))
    rep["analyze"]["0 (raw h0)"] = s0
if A.no_build:
    json.dump(rep, open(os.path.join(A.out, "analyze_report.json"), "w"), indent=1)
    print("ANALYZE_DONE")
    sys.exit(0)

h, viol, clamped = field(A.iters)
rep["iters"] = A.iters
rep["clamp_zone_violations_unclamped"] = viol
rep["clamped"] = clamped
rep["iso"] = iso_stats(h)
P, S, Stri = iso_lines(bco, btri, h)
np.savez_compressed(os.path.join(A.out, "field.npz"), co=bco, h=h, h0=h0, tri=btri, iso_pts=P, iso_segs=S, iso_seg_tri=Stri,
                    jag=jag, face_front=face_front, clamp_zone=clamp_zone)
base_tree = BVHTree.FromPolygons([tuple(v) for v in bco], [tuple(f) for f in btri.tolist()], all_triangles=True)


# ------------------------------------------------------------------ 精确切
def cut(obj, hv, keep_low):
    """在 h 跨 0.5 的边上切分并删掉另一侧。返回 (新切点索引列表, 原顶点数)"""
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    hl_ = bm.verts.layers.float.new("_h")
    for v in bm.verts:
        v[hl_] = hv[v.index]
    uvl = bm.loops.layers.uv.active
    knl = bm.loops.layers.float_vector.get("_kn")
    n0 = len(bm.verts)
    cross = [e for e in bm.edges if (e.verts[0][hl_] - 0.5) * (e.verts[1][hl_] - 0.5) < 0]
    newv = []
    for e in cross:
        a, b = e.verts
        t = (0.5 - a[hl_]) / (b[hl_] - a[hl_])
        pa, pb = a.co.copy(), b.co.copy()
        _, v = bmesh.utils.edge_split(e, a, t)
        v.co = pa.lerp(pb, t)
        v[hl_] = 0.5
        for l in v.link_loops:
            lp, ln = l.link_loop_prev, l.link_loop_next
            dd = (ln.vert.co - lp.vert.co).length
            tt = (v.co - lp.vert.co).length / dd if dd > 0 else 0.5
            if uvl is not None:
                l[uvl].uv = lp[uvl].uv.lerp(ln[uvl].uv, tt)
            if knl is not None:
                nn = Vector(lp[knl]).lerp(Vector(ln[knl]), tt)
                l[knl] = nn.normalized() if nn.length > 0 else nn
        newv.append(v)
    nset = set(newv)
    for f in list(bm.faces):
        vs = [v for v in f.verts if v in nset]
        if len(vs) == 2 and len(f.verts) > 3:
            bmesh.utils.face_split(f, vs[0], vs[1])
    if keep_low:
        dead = [f for f in bm.faces if max(v[hl_] for v in f.verts) > 0.5 + 1e-9]
    else:
        dead = [f for f in bm.faces if min(v[hl_] for v in f.verts) < 0.5 - 1e-9]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 3])
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.verts.ensure_lookup_table()
    hv_out = np.array([v[hl_] for v in bm.verts])
    bm.verts.layers.float.remove(hl_)
    bm.to_mesh(me); bm.free(); me.update()
    return hv_out, len(cross)


pre_co = bco.copy()
hv_base, n_cross_base = cut(base, h, keep_low=True)
co_after = coords(base.data)
is_new = np.abs(hv_base - 0.5) < 1e-7
okd = KDTree(len(orig_glb))
for i, p in enumerate(orig_glb):
    okd.insert(Vector(p), i)
okd.balance()
rep["base_cut_edges"] = n_cross_base
rep["base_new_cut_verts"] = int(is_new.sum())
rep["base_kept_original_verts_max_dist_to_original_glb"] = float(max(okd.find(Vector(p))[2] for p in co_after[~is_new]))


def bloops(me):
    bm_ = bmesh.new(); bm_.from_mesh(me)
    be = [(e.verts[0].index, e.verts[1].index) for e in bm_.edges if e.is_boundary]
    bm_.free()
    adj = {}
    for a, b in be:
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, out = set(), []
    for s in adj:
        if s in seen:
            continue
        comp, stack = [], [s]
        seen.add(s)
        while stack:
            x = stack.pop(); comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y); stack.append(y)
        cs = set(comp)
        out.append({"verts": comp, "edges": [(a, b) for a, b in be if a in cs]})
    return out, adj


def loop_turns(co, lp, adj):
    order = [lp["verts"][0]]
    prev = None
    while True:
        nx = [x for x in adj[order[-1]] if x != prev]
        if not nx or nx[0] == order[0]:
            break
        prev = order[-1]
        order.append(nx[0])
        if len(order) > len(lp["verts"]) + 2:
            break
    _, angs = turn_count(co, [(order, True)])
    return angs


hl_list, hadj = bloops(base.data)
rep["hole_loops"] = sorted([len(l["verts"]) for l in hl_list], reverse=True)
deg_ok = all(len(v) == 2 for v in hadj.values())
rep["hole_loops_simple(all boundary verts degree 2)"] = deg_ok
hole = max(hl_list, key=lambda l: len(l["edges"]))
ang = loop_turns(co_after, hole, hadj)
rep["hole_loop_turn_deg"] = st(ang, False)
rep["hole_loop_turn_gt60"] = int((ang > 60).sum())
rep["hole_loop_turn_gt90"] = int((ang > 90).sum())
hole_v = np.array(sorted(hole["verts"]))
hole_e = np.array(hole["edges"])
rep["hole_loop_z_%H"] = [round(float(co_after[hole_v, 2].min() / H * 100), 3), round(float(co_after[hole_v, 2].max() / H * 100), 3)]
bm = bmesh.new(); bm.from_mesh(base.data); bm.verts.ensure_lookup_table()
allowed = set(int(i) for i in hole_v)
for i in hole_v:
    for e in bm.verts[int(i)].link_edges:
        allowed.add(e.other_vert(bm.verts[int(i)]).index)
bm.free()
allowed = np.array(sorted(allowed))
nbv = len(co_after)
rep["base_verts_after_cut"] = nbv
rep["allowed_base_verts"] = int(len(allowed))
rep["allowed_original_(non-cut)_verts"] = int((~is_new[allowed]).sum())

# ------------------------------------------------------------------ 帽子
cap = load(A.buzz, "cap", Matrix(np.load(A.buzz_M).tolist()))
keep_normals(cap.data)
weld(cap.data)
cco = coords(cap.data)
hc_ = np.zeros(len(cco))
for i, p in enumerate(cco):
    q, _, fi, _ = base_tree.find_nearest(Vector(p))
    a, b, c = btri[fi]
    T = np.array([bco[a], bco[b], bco[c]])
    v0, v1, v2 = T[1] - T[0], T[2] - T[0], np.array(q) - T[0]
    d00, d01, d11, d20, d21 = v0 @ v0, v0 @ v1, v1 @ v1, v2 @ v0, v2 @ v1
    den = d00 * d11 - d01 * d01
    w1 = (d11 * d20 - d01 * d21) / den if den else 0.0
    w2 = (d00 * d21 - d01 * d20) / den if den else 0.0
    hc_[i] = (1 - w1 - w2) * h[a] + w1 * h[b] + w2 * h[c]
hc_[np.abs(hc_ - 0.5) < 1e-9] = 0.5 + 1e-6
_, n_cross_cap = cut(cap, hc_, keep_low=False)
rep["cap_cut_edges"] = n_cross_cap
# 最大连通块
bm = bmesh.new(); bm.from_mesh(cap.data); bm.faces.ensure_lookup_table()
comp = {}
seen = set()
blocks = []
for f in bm.faces:
    if f.index in seen:
        continue
    stack = [f]; seen.add(f.index); blk = []
    while stack:
        x = stack.pop(); blk.append(x)
        for e in x.edges:
            for g in e.link_faces:
                if g.index not in seen:
                    seen.add(g.index); stack.append(g)
    blocks.append(blk)
blocks.sort(key=len, reverse=True)
rep["cap_blocks"] = [len(b) for b in blocks[:10]]
bmesh.ops.delete(bm, geom=[f for b in blocks[1:] for f in b], context="FACES")
bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
bm.to_mesh(cap.data); bm.free(); cap.data.update()
rep["cap_tris"] = len(cap.data.polygons)
cl, cadj = bloops(cap.data)
rep["cap_loops"] = sorted([len(l["verts"]) for l in cl], reverse=True)
main = max(cl, key=lambda l: len(l["edges"]))
# 帽子内部的小环(切线在帽子里围出的小洞):按环顶点顺序建面补上并三角化,UV/法线取该顶点在相邻帽子面上的值
small = [l for l in cl if l is not main]
if small:
    bm = bmesh.new(); bm.from_mesh(cap.data); bm.verts.ensure_lookup_table()
    uvc = bm.loops.layers.uv.active
    knc = bm.loops.layers.float_vector.get("_kn")
    vmap = {i: bm.verts[i] for l in small for i in l["verts"]}
    nf = 0
    for l in small:
        adj_ = {}
        for a_, b_ in l["edges"]:
            adj_.setdefault(a_, []).append(b_); adj_.setdefault(b_, []).append(a_)
        order = [l["edges"][0][0]]
        while len(order) < len(l["verts"]):
            order.append([x for x in adj_[order[-1]] if x not in order][0])
        f0 = bm.faces.new([vmap[i] for i in order])
        bmesh.ops.recalc_face_normals(bm, faces=list({f0} | {g for v in f0.verts for g in v.link_faces}))
        f0.smooth = True
        for lo in f0.loops:
            other = [x for x in lo.vert.link_loops if x.face is not f0]
            if other:
                lo[uvc].uv = other[0][uvc].uv.copy()
                if knc is not None:
                    lo[knc] = other[0][knc]
        tri = bmesh.ops.triangulate(bm, faces=[f0])
        nf += len(tri["faces"])
    bm.to_mesh(cap.data); bm.free(); cap.data.update()
    rep["cap_small_loops_filled_tris"] = nf
    rep["cap_tris_after_fill"] = len(cap.data.polygons)
    cl, cadj = bloops(cap.data)
    rep["cap_loops_after_fill"] = sorted([len(l["verts"]) for l in cl], reverse=True)
    main = max(cl, key=lambda l: len(l["edges"]))
cco = coords(cap.data)
rep["cap_loop_turn_deg"] = st(loop_turns(cco, main, cadj), False)
cn = np.empty(len(cco) * 3); cap.data.vertices.foreach_get("normal", cn); cn = cn.reshape(-1, 3)
cb = np.array(sorted(main["verts"]))
q, d0 = seg_nearest(cco[cb], co_after[hole_e[:, 0]], co_after[hole_e[:, 1]])
disp = (q - cn[cb] * INSET) - cco[cb]
rep["gap_before_cap_to_hole_%H"] = st(d0)
kd = KDTree(len(cb))
for j, i in enumerate(cb):
    kd.insert(Vector(cco[i]), j)
kd.balance()
new = cco.copy(); mv = np.zeros(len(cco))
for i, p in enumerate(cco):
    _, j, d = kd.find(Vector(p))
    if d < RAD:
        w = 1 - d / RAD
        new[i] = p + disp[j] * w
        mv[i] = np.linalg.norm(disp[j]) * w
cap.data.vertices.foreach_set("co", new.ravel()); cap.data.update()
rep["cap_verts_moved_by_snap"] = int((mv > 0).sum())
rep["cap_snap_max_disp_%H"] = round(float(mv.max() / H * 100), 4)

# ------------------------------------------------------------------ join + bridge
with bpy.context.temp_override(**ctx(base, [base, cap])):
    bpy.ops.object.join()
me = base.data
bm = bmesh.new(); bm.from_mesh(me)
bm.verts.ensure_lookup_table(); bm.edges.ensure_lookup_table()
uv = bm.loops.layers.uv.active
knl = bm.loops.layers.float_vector.get("_kn")
hole_edges = [bm.edges.get((bm.verts[int(a)], bm.verts[int(b)])) for a, b in hole_e]
cap_edges = [bm.edges.get((bm.verts[nbv + int(a)], bm.verts[nbv + int(b)])) for a, b in main["edges"]]
assert all(hole_edges) and all(cap_edges)
hole_uv = {}
for i in hole_v:
    for l in bm.verts[int(i)].link_loops:
        hole_uv[int(i)] = l[uv].uv.copy()
        break
res = bmesh.ops.bridge_loops(bm, edges=hole_edges + cap_edges, use_pairs=False, use_cyclic=False, use_merge=False,
                             merge_factor=0.5, twist_offset=0)
bridge = list(res["faces"])
rep["bridge_method"] = "bmesh.ops.bridge_loops(use_pairs=False, use_cyclic=False, use_merge=False)"
bm.verts.ensure_lookup_table()
hkd = KDTree(len(hole_v))
for i in hole_v:
    hkd.insert(bm.verts[int(i)].co, int(i))
hkd.balance()
# 桥面 UV:取 base 端。为避免 UV 缝两侧取到不同 UV 岛(会在桥面上拉出跨岛的黑条),
# 每个桥面从"同一个 base 面"取 UV:桥面含一条洞边时取洞边另一侧的 base 面;只含一个洞顶点时取该顶点上一个贴洞边的 base 面。
bfs = set(bridge)
hset = set(int(i) for i in hole_v)
for f in bridge:
    f.material_index = 0
    f.smooth = True
for f in bridge:
    hv_ = [v for v in f.verts if v.index in hset]
    src = None
    for e in f.edges:
        if e.verts[0].index in hset and e.verts[1].index in hset:
            src = [g for g in e.link_faces if g not in bfs]
            src = src[0] if src else None
            break
    if src is None and hv_:
        for e in hv_[0].link_edges:
            cand = [g for g in e.link_faces if g not in bfs]
            if len(cand) == 1 and any(g in bfs for g in e.link_faces):
                src = cand[0]
                break
        if src is None:
            src = [g for g in hv_[0].link_faces if g not in bfs][0]
    suv = {l.vert.index: l[uv].uv.copy() for l in src.loops} if src is not None else {}
    for l in f.loops:
        vi = l.vert.index
        if vi in suv:
            l[uv].uv = suv[vi]
        elif suv:
            near = min((x for x in src.verts if x.index in suv and x.index in hset), key=lambda x: (x.co - l.vert.co).length,
                       default=None)
            l[uv].uv = suv[near.index] if near is not None else hole_uv[hkd.find(l.vert.co)[1]]
        else:
            l[uv].uv = hole_uv[vi if vi in hole_uv else hkd.find(l.vert.co)[1]]
rep["bridge_faces"] = len(bridge)
rep["bridge_tris"] = int(sum(len(f.verts) - 2 for f in bridge))
bverts = {v.index for f in bridge for v in f.verts}
aset = set(int(a) for a in allowed)
region = set(bverts) | aset
for i in cb:
    v = bm.verts[nbv + int(i)]
    region.add(v.index)
    for e in v.link_edges:
        region.add(e.other_vert(v).index)
region = {i for i in region if i >= nbv or i in aset}
rep["smooth_region_verts"] = len(region)
pre_bridge = np.array([bm.verts[i].co[:] for i in range(nbv)])
reg = sorted(region)
for _ in range(3):
    newp = {}
    for i in reg:
        v = bm.verts[i]
        nb = [e.other_vert(v).co for e in v.link_edges]
        if nb:
            newp[i] = v.co + 0.5 * (sum(nb, Vector((0, 0, 0))) / len(nb) - v.co)
    for i, p in newp.items():
        bm.verts[i].co = p
bm.normal_update()
rep["open_edges"] = sum(1 for e in bm.edges if e.is_boundary)
rep["non_manifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold)
bf = set(bridge)
blen = [e.calc_length() for f in bridge for e in f.edges]
rep["bridge_longest_edge_%H"] = round(max(blen) / H * 100, 4)
rep["bridge_edge_len_%H"] = st(blen)
ab, ac = [], []
for e in bm.edges:
    lf = e.link_faces
    if len(lf) != 2 or ((lf[0] in bf) == (lf[1] in bf)):
        continue
    o = lf[1] if lf[0] in bf else lf[0]
    x = float(np.degrees(lf[0].normal.angle(lf[1].normal))) if lf[0].normal.length and lf[1].normal.length else 0.0
    (ab if o.material_index == 0 else ac).append(x)
rep["seam_angle_bridge_vs_base_deg"] = dict(st(ab, False), n=len(ab))
rep["seam_angle_bridge_vs_cap_deg"] = dict(st(ac, False), n=len(ac))
rep["seam_angle_all_deg"] = dict(st(ab + ac, False), n=len(ab) + len(ac))
rep["seam_edges_angle_gt_90"] = int(sum(1 for x in ab + ac if x > 90))
post = np.array([bm.verts[i].co[:] for i in range(nbv)])
dmove = np.linalg.norm(post - pre_bridge, axis=1)
am = np.zeros(nbv, bool); am[allowed] = True
rep["allowed_base_verts_moved"] = int((dmove[am] > 0).sum())
rep["allowed_base_max_disp_%H"] = round(float(dmove[am].max() / H * 100), 4)
rep["allowed_base_max_disp_mm"] = round(float(dmove[am].max() / H * 100 * MM), 3)
rep["nonallowed_base_max_disp_vs_precut"] = float(dmove[~am].max())
orig_mask = ~am & ~is_new
rep["nonallowed_base_max_dist_to_original_glb_verts"] = float(max(okd.find(Vector(p))[2] for p in post[orig_mask]))
bm.faces.index_update()
bridge_idx = [f.index for f in bridge]
bm.to_mesh(me); bm.free()
kn = np.empty(len(me.loops) * 3, dtype=np.float32)
me.attributes["_kn"].data.foreach_get("vector", kn); kn = kn.reshape(-1, 3)
me.attributes.remove(me.attributes["_kn"])
if "_hair" in me.attributes:
    me.attributes.remove(me.attributes["_hair"])
lv = np.empty(len(me.loops), np.int64); me.loops.foreach_get("vertex_index", lv)
vn_ = np.empty(len(me.vertices) * 3, dtype=np.float32); me.vertex_normals.foreach_get("vector", vn_); vn_ = vn_.reshape(-1, 3)
rm = np.zeros(len(me.vertices), bool); rm[list(region | bverts)] = True
use = rm[lv] | (np.linalg.norm(kn, axis=1) < 0.5)
kn[use] = vn_[lv[use]]
rep["corners_with_recomputed_normals"] = int(use.sum())
me.normals_split_custom_set(kn.tolist()); me.update()
rep["final_faces_by_material"] = np.bincount([p.material_index for p in me.polygons]).tolist()
with bpy.context.temp_override(**ctx(base)):
    bpy.ops.export_scene.gltf(filepath=os.path.join(A.out, A.out_name), export_format="GLB", use_selection=True)
if A.export_parts:
    # 诊断用:按 base 保留面 / 桥面 / 帽子 拆成三个物体另存 parts.glb(主产物已先导出,不受影响)
    cap_mat = me.materials[1].name
    me.materials.append(bpy.data.materials.new("bridge_id"))
    mi_ = np.array([p.material_index for p in me.polygons])
    mi_[bridge_idx] = len(me.materials) - 1
    me.polygons.foreach_set("material_index", mi_)
    me.update()
    with bpy.context.temp_override(**ctx(base)):
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.separate(type="MATERIAL")
        bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.data.objects if o.type == "MESH"]
    for o in parts:
        mn = {o.material_slots[p.material_index].material.name for p in o.data.polygons}
        o.name = "part_bridge" if "bridge_id" in mn else ("part_cap" if cap_mat in mn else "part_base_kept")
    rep["parts"] = {o.name: len(o.data.polygons) for o in parts}
    with bpy.context.temp_override(**ctx(parts[0], parts)):
        bpy.ops.export_scene.gltf(filepath=os.path.join(A.out, "parts.glb"), export_format="GLB", use_selection=True)
print("BUILD", json.dumps(rep))
json.dump(rep, open(os.path.join(A.out, "build_report.json"), "w"), indent=1)
