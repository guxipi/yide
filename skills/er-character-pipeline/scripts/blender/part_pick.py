# blender -b --factory-startup -P part_pick.py -- --src <来源整身.glb> --seg <拆件.glb> --parts tripo_part_0,tripo_part_6,...
#        --out-mask <mask.npy> --out-glb <部件.glb> --report <report.json>
#        [--band-from <部件名> --band-zmin 0.90 [--band-lum auto|<阈值>] [--base <底模.glb> --M <M.npy>]]
#        [--clean-rib <部件名,...>]
# 从 Segment 拆件里挑部件:输出"来源整身上每个三角形是否属于这件"的掩码(按三角形质心最近邻把整身三角形对到拆件三角形)
# 和部件 glb(拆件原物体、原贴图,来源坐标)。
# --band-from:再从一个混合部件里抠一圈近黑色带(如头发带):质心高度分数 > --band-zmin 且贴图亮度 < 阈值的三角形,
#   按连通块只留"和 --parts 已选部件相接"的块和最大的块。亮度 = Rec.709 luma,部件自带贴图按每角 UV 最近像素采样后取平均。
#   auto 阈值 = 选中高度内亮度直方图(0.01 一格)3 格滑动平均在 [0.10,0.30] 里的谷底那格中点。
#   高度分数默认按来源整身自己的脚底和总高算;给了 --base 和 --M 就先用 M 变到底模坐标,按底模脚底和总高算。
# --clean-rib:这些罗纹件里贴图颜色"深色且 r>=b"或"肤色"的三角形不算本件,但只删连着本件原始边界的色块(不连边界的深色块是
#   罗纹槽阴影,放回);清完再去掉整件里 <50 个三角形的孤岛。颜色取整身贴图在三角形 UV 质心处的像素。
import argparse
import json
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.kdtree import KDTree

ap = argparse.ArgumentParser()
ap.add_argument("--src", required=True)
ap.add_argument("--seg", required=True)
ap.add_argument("--parts", required=True)
ap.add_argument("--out-mask", required=True)
ap.add_argument("--out-glb", required=True)
ap.add_argument("--report", required=True)
ap.add_argument("--band-from", default=None)
ap.add_argument("--band-zmin", type=float, default=0.90)
ap.add_argument("--band-lum", default="auto")
ap.add_argument("--base", default=None)
ap.add_argument("--M", default=None)
ap.add_argument("--clean-rib", default=None)
args = ap.parse_args(sys.argv[sys.argv.index("--") + 1:])
PARTS = [p for p in args.parts.split(",") if p]
RIB = [p for p in args.clean_rib.split(",") if p] if args.clean_rib else []
ISLAND_MIN = 50

bpy.ops.wm.read_factory_settings(use_empty=True)


def import_glb(path):
    """导入 glb,把世界矩阵烘进 mesh、去掉父级和非 mesh 物体,返回 mesh 物体列表(导入顺序)。"""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.context.scene.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in new:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    return meshes


def mesh_arrays(o):
    """顶点、三角形(loop_triangles)、每角 UV、材质号、三角形对应的 polygon 号。"""
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    me.calc_loop_triangles()
    lt = me.loop_triangles
    t = np.empty(len(lt) * 3, np.int64); lt.foreach_get("vertices", t)
    tl = np.empty(len(lt) * 3, np.int64); lt.foreach_get("loops", tl)
    mi = np.empty(len(lt), np.int64); lt.foreach_get("material_index", mi)
    pi = np.empty(len(lt), np.int64); lt.foreach_get("polygon_index", pi)
    uv = np.zeros((len(me.loops), 2))
    if me.uv_layers:
        u = np.empty(len(me.loops) * 2); me.uv_layers[0].data.foreach_get("uv", u); uv = u.reshape(-1, 2)
    return co.reshape(-1, 3), t.reshape(-1, 3), uv[tl.reshape(-1, 3)], mi, pi


def slot_image(o, i):
    """材质槽 i 的底色贴图(同 dump.py 的取法),返回 uint8 RGB 数组,行 0 = 贴图顶边(和 PIL 读 PNG 一致)。"""
    if i >= len(o.material_slots) or o.material_slots[i].material is None:
        return None
    mat = o.material_slots[i].material
    img = None
    if mat.node_tree:
        for nd in mat.node_tree.nodes:
            if nd.type == "BSDF_PRINCIPLED":
                l = nd.inputs["Base Color"].links
                if l and l[0].from_node.type == "TEX_IMAGE":
                    img = l[0].from_node.image
        if img is None:
            img = next((nd.image for nd in mat.node_tree.nodes if nd.type == "TEX_IMAGE" and nd.image), None)
    if img is None:
        return None
    w, h = img.size
    px = np.empty(w * h * img.channels, np.float32)
    img.pixels.foreach_get(px)
    return np.round(px.reshape(h, w, img.channels)[::-1, :, :3] * 255).astype(np.int64)


def sample(im, uv):
    h, w = im.shape[:2]
    return im[np.clip(((1 - uv[..., 1]) * h).astype(int), 0, h - 1), np.clip((uv[..., 0] * w).astype(int), 0, w - 1)]


def components(n, a, b):
    """无向图连通块(并查集,向量化挂根+路径压缩),返回 0..k-1 的块号。"""
    p = np.arange(n)
    while True:
        pa, pb = p[a], p[b]
        if (pa == pb).all():
            break
        np.minimum.at(p, np.maximum(pa, pb), np.minimum(pa, pb))
        while True:
            pp = p[p]
            if (pp == p).all():
                break
            p = pp
    _, lab = np.unique(p, return_inverse=True)
    return lab.ravel()


def tri_components(tw, nv):
    """三角形按共享(焊接后)顶点连通:三角形节点 + 顶点节点的二部图。"""
    nf = len(tw)
    a = np.repeat(np.arange(nf), 3)
    b = tw.ravel() + nf
    return components(nf + nv, a, b)[:nf]


def weld_ids(co, tol):
    _, inv = np.unique(np.round(co / tol).astype(np.int64), axis=0, return_inverse=True)
    return inv.ravel()


def kd_of(pts):
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(Vector(p), i)
    kd.balance()
    return kd


rep = {"src": args.src, "seg": args.seg, "parts": PARTS}

# ------------------------------------------------ 底模高度基准(可选)
Mb = None
if args.base:
    assert args.M, "--base 要和 --M 一起给"
    bobjs = import_glb(args.base)
    bz = np.concatenate([mesh_arrays(o)[0][:, 2] for o in bobjs])
    for o in bobjs:
        bpy.data.objects.remove(o, do_unlink=True)
    Mb = np.load(args.M)

# ------------------------------------------------ 来源整身
src_objs = import_glb(args.src)
sco, stri, stuv, smi, simg = [], [], [], [], []
off = 0
for o in src_objs:
    co, t, tuv, mi, _ = mesh_arrays(o)
    sco.append(co); stri.append(t + off); stuv.append(tuv); smi.append(mi)
    simg.append([slot_image(o, i) for i in range(max(1, len(o.material_slots)))] if RIB else None)
    off += len(co)
sobj_of_tri = np.concatenate([np.full(len(t), k) for k, t in enumerate(stri)])
sco, stri, stuv, smi = np.concatenate(sco), np.concatenate(stri), np.concatenate(stuv), np.concatenate(smi)
for o in src_objs:
    bpy.data.objects.remove(o, do_unlink=True)
if Mb is not None:
    zb, H = float(bz.min()), float(bz.max() - bz.min())
    rep["z_frame"] = "base (via --M)"
else:
    zb, H = float(sco[:, 2].min()), float(np.ptp(sco[:, 2]))
    rep["z_frame"] = "src"
rep["z_foot"], rep["H"] = zb, H

# ------------------------------------------------ 拆件
seg_objs = import_glb(args.seg)
names = [o.name for o in seg_objs]
for p in PARTS + RIB + ([args.band_from] if args.band_from else []):
    assert p in names, "拆件里没有 %s" % p
seg = {}
cents, slab, sloc = [], [], []
for k, o in enumerate(seg_objs):
    co, t, tuv, mi, pi = mesh_arrays(o)
    seg[o.name] = {"co": co, "t": t, "tuv": tuv, "mi": mi, "pi": pi}
    cents.append(co[t].mean(1)); slab.append(np.full(len(t), k)); sloc.append(np.arange(len(t)))
cents, slab, sloc = np.concatenate(cents), np.concatenate(slab), np.concatenate(sloc)
seg_start = {nm: int(np.nonzero(slab == k)[0][0]) if (slab == k).any() else 0 for k, nm in enumerate(names)}

# 整身三角形 -> 拆件三角形(质心最近邻)
kd = kd_of(cents)
scent = sco[stri].mean(1)
nn = np.zeros(len(stri), np.int64)
dmap = np.zeros(len(stri))
for i, p in enumerate(scent):
    _, j, d = kd.find(Vector(p))
    nn[i] = j
    dmap[i] = d
rep["src_tris"], rep["seg_tris"] = int(len(stri)), int(len(cents))
rep["map_centroid_err_max"] = float(dmap.max())
rep["map_seg_tris_hit_more_than_once"] = int((np.bincount(nn, minlength=len(cents)) > 1).sum())

seg_sel = np.isin(slab, [names.index(p) for p in PARTS])
rep["part_tris"] = {p: int((slab == names.index(p)).sum()) for p in PARTS}
rep["parts_tris_total"] = int(seg_sel.sum())

# ------------------------------------------------ 混合部件里抠色带
if args.band_from:
    bf = seg[args.band_from]
    bobj = seg_objs[names.index(args.band_from)]
    co = bf["co"] if Mb is None else bf["co"] @ Mb[:3, :3].T + Mb[:3, 3]
    t = bf["t"]
    c = np.zeros((len(t), 3))
    for mi in np.unique(bf["mi"]):
        imi = slot_image(bobj, int(mi))
        sel = bf["mi"] == mi
        c[sel] = sample(imi.astype(float) / 255, bf["tuv"][sel]).mean(1)
    L = 0.2126 * c[:, 0] + 0.7152 * c[:, 1] + 0.0722 * c[:, 2]
    zc = (co[t].mean(1)[:, 2] - zb) / H
    zsel = zc > args.band_zmin
    hist, edges = np.histogram(L[zsel], bins=100, range=(0, 1))
    if args.band_lum == "auto":
        sm = np.convolve(hist, np.ones(3) / 3, mode="same")
        lo, hi = 10, 30
        k = lo + int(np.argmin(sm[lo:hi + 1]))
        thr = float(edges[k] + 0.005)
    else:
        thr = float(args.band_lum)
    band = zsel & (L < thr)
    # 连通块(按位置焊接顶点,共享顶点即相连)
    sel = np.nonzero(band)[0]
    wid = weld_ids(co, 1e-6)
    cc = tri_components(wid[t[sel]], int(wid.max()) + 1)
    # 和已选部件相接:色带三角形的顶点到已选部件顶点距离 < 1e-6
    pco = np.concatenate([seg[p]["co"] for p in PARTS])
    if Mb is not None:
        pco = pco @ Mb[:3, :3].T + Mb[:3, 3]
    kdp = kd_of(pco)
    vtouch = np.array([kdp.find(Vector(v))[2] < 1e-6 for v in co[t[sel]].reshape(-1, 3)]).reshape(-1, 3).any(1)
    cnt = np.bincount(cc)
    largest = int(cnt.argmax())
    keep_cc = sorted(set([largest] + [int(k) for k in np.unique(cc[vtouch])]))
    keep = np.isin(cc, keep_cc)
    band2 = np.zeros(len(t), bool)
    band2[sel[keep]] = True
    seg_sel[seg_start[args.band_from] + np.nonzero(band2)[0]] = True
    P = co[t[sel]].mean(1)
    rep["band"] = {"from": args.band_from, "zmin": args.band_zmin, "lum_mode": args.band_lum, "threshold_L": thr,
                   "part_tris": int(len(t)), "tris_z_gt_zmin": int(zsel.sum()), "hist_bin_0.01": hist.tolist(),
                   "tris_dark_in_z": int(band.sum()),
                   "components": [{"cc": int(k), "tris": int(cnt[k]), "touch_parts_tris": int(vtouch[cc == k].sum()),
                                   "zmax_frac": round(float(P[cc == k, 2].max() - zb) / H, 4), "kept": k in keep_cc}
                                  for k in np.argsort(-cnt)],
                   "band_tris": int(band2.sum()), "removed_by_components": int(band.sum() - band2.sum())}

mask = seg_sel[nn]
rep["mask_tris_before_clean"] = int(mask.sum())

# ------------------------------------------------ 罗纹件清理
if RIB:
    col = np.zeros((len(stri), 3), np.int64)
    c = stuv.mean(1)
    for k in np.unique(sobj_of_tri):
        for mi in np.unique(smi[sobj_of_tri == k]):
            sel = (sobj_of_tri == k) & (smi == mi)
            col[sel] = sample(simg[k][int(mi)], c[sel])
    r, g, b = col[:, 0], col[:, 1], col[:, 2]
    dark = (np.maximum(np.maximum(r, g), b) < 100) & (r >= b)
    skin = (r > 120) & (g / np.maximum(r, 1) < 0.52) & (b < 70)
    lab = slab[nn]
    rib = mask & np.isin(lab, [names.index(p) for p in RIB])
    drop = rib & (dark | skin)
    inv = weld_ids(sco, 1e-5)
    nv0 = int(inv.max()) + 1
    tj = inv[stri[mask]]
    e = np.sort(np.concatenate([tj[:, [0, 1]], tj[:, [1, 2]], tj[:, [2, 0]]]), 1)
    ue, ce = np.unique(e, axis=0, return_counts=True)
    onb = np.zeros(nv0, bool)
    onb[ue[ce == 1].ravel()] = True
    di = np.nonzero(drop)[0]
    td = inv[stri[di]]
    dc = tri_components(td, nv0)
    touch = np.zeros(dc.max() + 1 if len(dc) else 0, bool)
    np.logical_or.at(touch, np.repeat(dc, 3), onb[td.ravel()])
    restored = ~touch[dc]
    drop[di[restored]] = False
    m = mask & ~drop
    idx = np.nonzero(m)[0]
    fc = tri_components(inv[stri[idx]], nv0)
    u, cntc = np.unique(fc, return_counts=True)
    small = np.isin(fc, u[cntc < ISLAND_MIN])
    m[idx[small]] = False
    rep["clean_rib"] = {"rib_parts": RIB, "mask_tris_before": int(mask.sum()),
                        "dropped_rib_dark_or_skin_touching_boundary": int(drop.sum()),
                        "restored_inner_dark": int(restored.sum()),
                        "dropped_by_part": {p: int((drop & (lab == names.index(p))).sum()) for p in RIB},
                        "islands_lt%d" % ISLAND_MIN: int(small.sum()), "components_kept": int((cntc >= ISLAND_MIN).sum()),
                        "mask_tris_after": int(m.sum())}
    gone = np.nonzero(mask & ~m)[0]
    seg_sel[nn[gone]] = False
    mask = m

np.save(args.out_mask, mask)
rep["mask_tris"] = int(mask.sum())

# ------------------------------------------------ 部件 glb(拆件物体,来源坐标)
keep_names = PARTS + ([args.band_from] if args.band_from and args.band_from not in PARTS else [])
out_objs = []
for k, o in enumerate(seg_objs):
    if o.name not in keep_names:
        bpy.data.objects.remove(o, do_unlink=True)
        continue
    loc = seg_sel[slab == k]
    pi = seg[o.name]["pi"]
    drop_p = sorted(set(pi[~loc].tolist()))
    if drop_p:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.faces[i] for i in drop_p], context="FACES")
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    if o.name == args.band_from and o.name not in PARTS:
        o.name = args.band_from + "_band"
    out_objs.append(o)
rep["out_objects_tris"] = {o.name: len(o.data.polygons) for o in out_objs}
rep["out_tris_total"] = int(sum(rep["out_objects_tris"].values()))
for o in bpy.data.objects:
    o.select_set(o in out_objs)
bpy.ops.export_scene.gltf(filepath=args.out_glb, export_format="GLB", use_selection=True)
rep["out_mask"], rep["out_glb"] = args.out_mask, args.out_glb
json.dump(rep, open(args.report, "w"), indent=1)
print("PART_PICK_DONE", json.dumps({k: v for k, v in rep.items() if k != "band"}))
