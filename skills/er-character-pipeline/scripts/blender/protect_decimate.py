"""Face/hand-protected decimate for a whole-body character mesh (Blender 5.1, background, self-contained).

Usage
    blender -b --factory-startup -P protect_decimate.py -- --in <glb|fbx> --out <glb> --target 58000
            [--method meshopt|collapse] [--head-share 0.193] [--meshopt-js <path to meshopt_simplifier.js or meshoptimizer/index.js>]
            [--hand-radius 0.45] [--no-protect] [--no-xfer] [--no-weld] [--debug-png <path>] [--log <json>]

Default --method meshopt (10-26 round 3 winner "R3h"): body by meshoptimizer, head by Blender collapse
    Needs node. meshoptimizer 1.3.0 (MIT) simplifier is vendored at vendor/meshoptimizer-1.3.0/meshopt_simplifier.js
    (default --meshopt-js, no npm install needed) and is driven by meshopt_simplify.mjs next to this script.
    a. after steps 1-3 below, the welded mesh is split per corner into (vertex, uv, normal, material) vertices;
       meshoptimizer simplifyWithAttributes (attribute weights normal 1.0, uv 0.5, target_error 1.0) runs with
       ALL head verts + face-front + hand verts locked, target = target - head_share*target + head tris.
       It keeps a subset of the original vertices (no position averaging), so clothing creases, piping and buckle
       rims stay where they were instead of being melted by quadric placement.
    b. the result is rebuilt (UV + material per corner), re-welded, then step 4's DECIMATE collapse (symmetry X)
       runs on the head only (vertex group = head verts not touching body / face-front / hand triangles; verts
       outside the group have weight 0 = never collapse) down to --target. Collapse's placement keeps curly hair,
       jaw and ear silhouettes smooth; meshopt alone made them spiky (Coda face SSIM 0.928 vs 0.973).
    c. steps 4b-6 as below.
    Coda 10-26 (58k): upper-body clay SSIM vs 200k 0.938 (collapse 0.884), legs 0.943 (0.912), face 0.975 (0.973);
    the white smear on the back-left buckle in collapse is gone.
--method collapse = the previous 10-26 "V3" recipe, steps 1-6:
    1. Import, bake object transforms into ONE mesh (armatures / empties / vertex groups dropped: the input is an
       unrigged generation, e.g. Tripo H3.1 whole body at ~200k tris). Model must stand Z-up and face -Y
       (glTF / Tripo default after Blender import).
    2. Weld (merge by distance, 1e-5 x model size). Only geometry is merged; UVs stay per-loop and the custom
       normals are re-applied, so UV seams stop being open boundaries the decimator would pull apart
       (10-26 test without weld: 18,787 open edges after decimate, 13,613 still open after re-welding).
    3. Geometric regions (numpy, no armature needed), all in the model's own frame:
       H = bbox height, zb = bbox bottom, cx = median x of verts between 0.45H and 0.70H.
       chin line : (a) narrowest row of the FRONT silhouette (x-z projection of all triangles, 2000 rows/H) inside
                   0.70H..0.93H, run measured through the body-centre column -> anchor;
                   (b) side profile = front-most y of the centre strip |x-cx| < 0.03H in 0.0025H bins; going up, the
                   LOWEST forward step f(z) - f(z+0.01H) >= 0.025H inside [anchor - 0.05H, anchor + 0.02H] is the
                   underside of the chin; chin_z = middle of that step. (a) alone lands on the upper lip of a
                   thick-necked male (Coda: 0.853H vs real chin 0.825H); (b) agrees with (a) on Wren (0.803/0.806).
       head      : triangles with centroid z >= chin_z.   head_h = top - chin_z.
       face-front: head triangles with normal.y <= -0.35, centroid in the front half of the head depth,
                   |x - head bbox centre| <= 0.30 head width, z <= chin_z + 0.68 head_h (cuts the hair cap).
                   Bangs lying over the face are included (geometry cannot tell them apart).
       hands     : per side, tip = vert with |x-cx| > 0.6 max|x-cx| and z in 0.30H..0.75H farthest (x-z) from
                   (cx, chin_z); region = triangles with centroid within --hand-radius x head_h of the tip.
    4. DECIMATE collapse, symmetry X, ratio bisected on the evaluated triangle count (tol 0.5%).
       Protection = vertex group (face-front + hand verts, weight pw) with invert_vertex_group=True:
       Blender's decimate treats EFFECTIVE weight 0 as "never collapse", so weight 1 + invert = hard protect;
       without invert the circled region is the one decimated hardest (verified 10-26 on Harrow/Coda).
       If the protected triangles exceed 40% of --target, a warning is printed and pw = 0.99 (effective 0.01 =
       soft protect) is used instead; logged as protect_mode "soft".
    4b. mesh.validate() right after the collapse (it can leave duplicate faces; Coda: 2) so the reported count is
       what lands in the glb (the glTF exporter would otherwise validate() silently and warn "not valid").
    5. DATA_TRANSFER custom normals from the pre-decimation (welded) mesh: Nearest Face Interpolated, mix 1.0.
    6. Export glb (materials/textures as imported). One line `PROTECT_DECIMATE {json}` on stdout; exit 1 on failure.

10-26 Coda measurement (coda_h31_200k_tex4k.glb, Tripo H3.1, 4K)
    194,895 -> 57,999 tris; face-front 2,458 -> 2,464; hands 7,883 -> 7,883; head 22,903 -> 11,108;
    open edges after weld 91 (same as source); vs the 200k source: SSIM face 0.973, SSIM g46 0.965,
    silhouette IoU front 0.9985. Same-budget 60k direct generation had face-front 782, head 6,205.
"""
import json
import math
import os
import subprocess
import sys
import tempfile
import time

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

PROTECT_SHARE_MAX = 0.40
SOFT_PW = 0.99


# ------------------------------------------------------------------ cli / io
def parse_args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    here = os.path.dirname(os.path.abspath(__file__))
    o = {"hand_radius": 0.45, "protect": True, "xfer": True, "weld": True, "debug_png": None, "log": None,
         "method": "meshopt", "head_share": 0.193,
         "meshopt_js": os.path.join(here, "vendor", "meshoptimizer-1.3.0", "meshopt_simplifier.js")}
    i = 0
    while i < len(a):
        k = a[i]
        if k in ("--no-protect", "--no-xfer", "--no-weld"):
            o[k[5:]] = False
            i += 1
        elif k in ("--in", "--out", "--target", "--hand-radius", "--debug-png", "--log", "--method", "--head-share",
                   "--meshopt-js"):
            o[k[2:].replace("-", "_")] = a[i + 1]
            i += 2
        else:
            raise ValueError("unknown arg " + k)
    for k in ("in", "out", "target"):
        if k not in o:
            raise ValueError("missing --" + k)
    o["target"] = int(o["target"])
    o["hand_radius"] = float(o["hand_radius"])
    o["head_share"] = float(o["head_share"])
    if o["method"] not in ("meshopt", "collapse"):
        raise ValueError("--method must be meshopt or collapse")
    return o


# ------------------------------------------------------------------ blender helpers
def ops_ctx(obj, others=()):
    sel = [obj] + [o for o in others if o is not obj]
    bpy.context.view_layer.update()
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(o in sel)
    bpy.context.view_layer.objects.active = obj
    c = {"object": obj, "active_object": obj, "selected_objects": sel, "selected_editable_objects": sel,
         "view_layer": bpy.context.view_layer, "scene": bpy.context.scene}
    wm = bpy.context.window_manager
    if wm.windows:
        c["window"] = wm.windows[0]
    return c


def mesh_coords(me):
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def tris_of(me):
    me.calc_loop_triangles()
    t = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", t)
    return t.reshape(-1, 3)


def tri_geom(co, t):
    p0, p1, p2 = co[t[:, 0]], co[t[:, 1]], co[t[:, 2]]
    n = np.cross(p1 - p0, p2 - p0)
    n = n / np.maximum(np.linalg.norm(n, axis=1), 1e-20)[:, None]
    return (p0 + p1 + p2) / 3.0, n


def load_model(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, use_custom_normals=True)
    else:
        raise ValueError("unsupported input " + path)
    objs = list(bpy.context.scene.objects)
    meshes = [o for o in objs if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh in " + path)
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()
        mw = o.matrix_world.copy()
        o.modifiers.clear()
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    for o in objs:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(**ops_ctx(obj, meshes)):
            bpy.ops.object.join()
    for vg in list(obj.vertex_groups):
        obj.vertex_groups.remove(vg)
    return obj


def weld(obj, dist):
    """merge by distance; per-corner normals carried through as a corner attribute and re-applied."""
    me = obj.data
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", n)
    a = me.attributes.new("_keep_n", "FLOAT_VECTOR", "CORNER")
    a.data.foreach_set("vector", n)
    n0 = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(me)
    bm.free()
    a = me.attributes["_keep_n"]
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    a.data.foreach_get("vector", n)
    me.attributes.remove(me.attributes["_keep_n"])
    me.normals_split_custom_set(n.reshape(-1, 3).tolist())
    me.update()
    return n0 - len(me.vertices)


def open_edges(me, weld_dist):
    bm = bmesh.new()
    bm.from_mesh(me)
    raw = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld_dist)
    welded = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return raw, welded, nm


def eval_tris(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    eo = obj.evaluated_get(dg)
    me = eo.to_mesh()
    n = int(sum(len(p.vertices) - 2 for p in me.polygons))
    eo.to_mesh_clear()
    return n


def apply_mod(obj, mod):
    with bpy.context.temp_override(**ops_ctx(obj)):
        bpy.ops.object.modifier_apply(modifier=mod.name)


# ------------------------------------------------------------------ regions
def bary_samples(P, step):
    """points covering every 2D triangle P[k] (k,3,2) with spacing <= step (barycentric lattice per triangle)."""
    e = np.stack([np.linalg.norm(P[:, 1] - P[:, 0], axis=1), np.linalg.norm(P[:, 2] - P[:, 1], axis=1),
                  np.linalg.norm(P[:, 0] - P[:, 2], axis=1)], 1).max(1)
    s = np.maximum(1, np.ceil(e / step * 1.5)).astype(np.int64)
    out = []
    for sv in np.unique(s):
        idx = np.nonzero(s == sv)[0]
        ii, jj = np.meshgrid(np.arange(sv + 1), np.arange(sv + 1), indexing="ij")
        m = ii + jj <= sv
        b1, b2 = ii[m] / sv, jj[m] / sv
        b0 = 1.0 - b1 - b2
        Q = P[idx]
        pts = (b0[None, :, None] * Q[:, None, 0] + b1[None, :, None] * Q[:, None, 1] + b2[None, :, None] * Q[:, None, 2])
        out.append(pts.reshape(-1, 2))
    return np.concatenate(out) if out else np.zeros((0, 2))


def front_neck_anchor(co, t, zb, H, cx):
    """spec rule: narrowest row (run through the centre column) of the front silhouette inside 0.70H..0.93H."""
    rows = 2000
    px = H / (rows - 1)
    z0, z1 = zb + 0.70 * H, zb + 0.93 * H
    tz = co[t][:, :, 2]
    band = (tz.max(1) >= z0) & (tz.min(1) <= z1)
    P = co[t[band]][:, :, [0, 2]]
    pts = bary_samples(P, px)
    xlo = co[:, 0].min()
    W = int((co[:, 0].max() - xlo) / px) + 3
    r = np.round((pts[:, 1] - zb) / px).astype(np.int64)
    c = np.round((pts[:, 0] - xlo) / px).astype(np.int64) + 1
    ok = (r >= 0) & (r < rows)
    grid = np.zeros((rows, W), bool)
    grid[r[ok], c[ok]] = True
    ccol = int(round((cx - xlo) / px)) + 1
    best, best_z = None, None
    for ri in range(int(math.floor((z0 - zb) / px)), int(math.ceil((z1 - zb) / px)) + 1):
        row = grid[ri]
        if not row[ccol]:
            continue
        left = row[:ccol][::-1]
        right = row[ccol + 1:]
        a = int(np.argmin(left)) if not left.all() else len(left)
        b = int(np.argmin(right)) if not right.all() else len(right)
        w = a + b + 1
        if best is None or w < best:
            best, best_z = w, zb + ri * px
    return best_z, best * px


def regions(obj, hand_radius):
    co = mesh_coords(obj.data)
    t = tris_of(obj.data)
    zb, zt = co[:, 2].min(), co[:, 2].max()
    H = float(zt - zb)
    band = (co[:, 2] >= zb + 0.45 * H) & (co[:, 2] <= zb + 0.70 * H)
    cx = float(np.median(co[band, 0]))
    anchor, neck_w = front_neck_anchor(co, t, zb, H, cx)
    bz, k = 0.0025 * H, 4
    zs = anchor + np.arange(-0.05, 0.02, 0.0025) * H
    strip = np.abs(co[:, 0] - cx) < 0.03 * H
    prof = []
    for z in zs:
        m = strip & (co[:, 2] >= z) & (co[:, 2] < z + bz)
        prof.append(co[m, 1].min() if m.any() else np.nan)
    prof = np.array(prof)
    jump = prof[:-k] - prof[k:]
    okj = np.nonzero(np.nan_to_num(jump, nan=-1.0) >= 0.025 * H)[0]
    chin_rule = "side_profile_step" if len(okj) else "largest_step_fallback"
    ij = int(okj[0]) if len(okj) else int(np.nanargmax(jump))
    chin_z = float(zs[ij] + (k + 1) * bz / 2.0)
    hv = co[co[:, 2] >= chin_z]
    hlo, hhi = hv.min(0), hv.max(0)
    head_h = float(hhi[2] - chin_z)
    R = {"H": H, "z_bottom": float(zb), "cx": cx, "chin_z": chin_z, "chin_frac": (chin_z - zb) / H,
         "chin_anchor_front_silhouette_frac": (anchor - zb) / H, "chin_rule": chin_rule,
         "head_height": head_h, "head_frac": head_h / H, "head_bbox": [hlo.tolist(), hhi.tolist()],
         "face": {"min_fwd": 0.35, "y_max": float(hlo[1] + 0.5 * (hhi[1] - hlo[1])),
                  "x_c": float((hlo[0] + hhi[0]) / 2), "x_half": float(0.30 * (hhi[0] - hlo[0])),
                  "z_max": float(chin_z + 0.68 * head_h)},
         "hand_radius_factor": hand_radius, "hands": []}
    neck = np.array([cx, 0.0, chin_z])
    xm = np.abs(co[:, 0] - cx).max()
    for sign in (-1, 1):
        cand = (sign * (co[:, 0] - cx) > 0.6 * xm) & (co[:, 2] >= zb + 0.30 * H) & (co[:, 2] <= zb + 0.75 * H)
        cv = co[cand]
        if not len(cv):
            raise RuntimeError("no hand candidates on side %+d" % sign)
        tip = cv[np.argmax(np.linalg.norm((cv - neck)[:, [0, 2]], axis=1))]
        R["hands"].append({"side": "+x" if sign > 0 else "-x", "tip": tip.tolist(), "radius": hand_radius * head_h})
    return R


def region_masks(co, t, R):
    cen, n = tri_geom(co, t)
    head = cen[:, 2] >= R["chin_z"]
    f = R["face"]
    face = (head & (n[:, 1] <= -f["min_fwd"]) & (cen[:, 1] <= f["y_max"])
            & (np.abs(cen[:, 0] - f["x_c"]) <= f["x_half"]) & (cen[:, 2] <= f["z_max"]))
    hands = np.zeros(len(t), bool)
    for h in R["hands"]:
        hands |= np.linalg.norm(cen - np.array(h["tip"]), axis=1) <= h["radius"]
    return head, face, hands


def counts(obj, R):
    co, t = mesh_coords(obj.data), tris_of(obj.data)
    head, face, hands = region_masks(co, t, R)
    return {"head_tris": int(head.sum()), "face_front_tris": int(face.sum()), "hand_tris": int(hands.sum())}


def debug_png(obj, R, path, rows=1400):
    """front view, z-buffered point splat; grey body, green head, red face-front, blue hands, magenta chin line,
    yellow front-silhouette anchor. Written with bpy images (no PIL needed)."""
    co, t = mesh_coords(obj.data), tris_of(obj.data)
    head, face, hands = region_masks(co, t, R)
    cen, n = tri_geom(co, t)
    vis = n[:, 1] < 0.05
    H, zb = R["H"], R["z_bottom"]
    px = H / (rows - 1)
    xlo = co[:, 0].min()
    W = int((co[:, 0].max() - xlo) / px) + 3
    col = np.tile(np.array([0.78, 0.78, 0.78]), (len(t), 1))
    col[head] = (0.59, 0.90, 0.47)
    col[hands] = (0.35, 0.78, 1.0)
    col[face] = (1.0, 0.47, 0.35)
    col = col * np.clip(0.35 + 0.65 * np.maximum(-n[:, 1], 0), 0, 1)[:, None]
    img = np.full((rows, W, 3), 0.5)
    ids = np.nonzero(vis)[0]
    P = co[t[ids]][:, :, [0, 2]]
    D = co[t[ids]][:, :, 1]
    pts, dep, own = [], [], []
    # reuse the lattice sampler, carrying depth and triangle id through a third/fourth coordinate
    P4 = np.concatenate([P, D[:, :, None], np.repeat(ids[:, None, None].astype(np.float64), 3, axis=1)], axis=2)
    e = np.stack([np.linalg.norm(P[:, 1] - P[:, 0], axis=1), np.linalg.norm(P[:, 2] - P[:, 1], axis=1),
                  np.linalg.norm(P[:, 0] - P[:, 2], axis=1)], 1).max(1)
    s = np.maximum(1, np.ceil(e / px * 1.5)).astype(np.int64)
    for sv in np.unique(s):
        idx = np.nonzero(s == sv)[0]
        ii, jj = np.meshgrid(np.arange(sv + 1), np.arange(sv + 1), indexing="ij")
        m = ii + jj <= sv
        b1, b2 = ii[m] / sv, jj[m] / sv
        b0 = 1.0 - b1 - b2
        Q = P4[idx]
        q = (b0[None, :, None] * Q[:, None, 0] + b1[None, :, None] * Q[:, None, 1] + b2[None, :, None] * Q[:, None, 2]).reshape(-1, 4)
        pts.append(q[:, :2])
        dep.append(q[:, 2])
        own.append(np.rint(q[:, 3]).astype(np.int64))
    pts, dep, own = np.concatenate(pts), np.concatenate(dep), np.concatenate(own)
    order = np.argsort(-dep, kind="stable")  # far first, front last (last write wins)
    r = np.round((pts[order, 1] - zb) / px).astype(np.int64)
    c = np.round((pts[order, 0] - xlo) / px).astype(np.int64) + 1
    ok = (r >= 0) & (r < rows) & (c >= 0) & (c < W)
    img[r[ok], c[ok]] = col[own[order][ok]]
    for z, cc in ((R["chin_z"], (1.0, 0.0, 1.0)), (zb + R["chin_anchor_front_silhouette_frac"] * H, (1.0, 1.0, 0.0))):
        ri = int(round((z - zb) / px))
        img[max(ri - 1, 0):ri + 1, :] = cc
    rgba = np.concatenate([img, np.ones((rows, W, 1))], axis=2).astype(np.float32)
    im = bpy.data.images.new("protect_debug", W, rows, alpha=False)
    im.pixels.foreach_set(rgba.ravel())  # bpy image rows are bottom-up, same as z-up rows here
    im.filepath_raw = os.path.abspath(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


# ------------------------------------------------------------------ meshopt body pass + head-only collapse
def meshopt_body(obj, R, a, weld_dist, log):
    """meshoptimizer simplifyWithAttributes on the welded mesh with all head + face-front + hand verts locked;
    replaces obj.data with the rebuilt (UV / material per corner, re-welded) result. Head stays at full count."""
    if not os.path.exists(a["meshopt_js"]):
        raise RuntimeError("meshoptimizer not found at %s: the vendored copy should be at vendor/meshoptimizer-1.3.0/ "
                           "next to %s; pass --meshopt-js to use another copy"
                           % (a["meshopt_js"], os.path.abspath(__file__)))
    me = obj.data
    co, t = mesh_coords(me), tris_of(me)
    nt = len(t)
    lt_loops = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get("loops", lt_loops)
    lt_mat = np.empty(nt, np.int64)
    me.loop_triangles.foreach_get("material_index", lt_mat)
    nrm = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(-1, 3)
    if len(me.uv_layers) != 1:
        raise RuntimeError("meshopt path expects exactly one UV layer, got %d" % len(me.uv_layers))
    uvname = me.uv_layers[0].name
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].uv.foreach_get("vector", uv)
    uv = uv.reshape(-1, 2)
    cv, cm = t.ravel(), np.repeat(lt_mat, 3)
    key = np.column_stack([cv, np.round(uv[lt_loops] * 1e6).astype(np.int64),
                           np.round(nrm[lt_loops] * 1e4).astype(np.int64), cm])
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    sv = cv[first]
    s_pos = co[sv].astype(np.float32)
    s_uv = uv[lt_loops[first]]
    s_m = cm[first]
    head, face, hands = region_masks(co, t, R)
    prot = face | hands if a["protect"] else np.zeros(nt, bool)
    share = float(prot.sum()) / a["target"]
    if share > PROTECT_SHARE_MAX:
        raise RuntimeError("protected tris %d = %.1f%% of target > %d%%: use --method collapse (soft protect)"
                           % (int(prot.sum()), share * 100, int(PROTECT_SHARE_MAX * 100)))
    vm = np.zeros(len(co), bool)
    vm[t[prot | head].ravel()] = True
    head_budget = int(round(a["head_share"] * a["target"]))
    target1 = a["target"] - head_budget + int(head.sum())
    with tempfile.TemporaryDirectory() as w:
        inv.ravel().astype(np.uint32).tofile(os.path.join(w, "idx.u32"))
        s_pos.tofile(os.path.join(w, "pos.f32"))
        np.concatenate([nrm[lt_loops[first]], s_uv], axis=1).astype(np.float32).tofile(os.path.join(w, "attr.f32"))
        vm[sv].astype(np.uint8).tofile(os.path.join(w, "lock.u8"))
        with open(os.path.join(w, "params.json"), "w") as f:
            json.dump({"attr_stride": 5, "attr_weights": [1.0, 1.0, 1.0, 0.5, 0.5],
                       "target_index_count": target1 * 3, "target_error": 1.0}, f)
        js = os.path.join(os.path.dirname(os.path.abspath(__file__)), "meshopt_simplify.mjs")
        p = subprocess.run(["node", js, w, a["meshopt_js"]], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("meshopt_simplify.mjs failed: " + p.stdout + p.stderr)
        with open(os.path.join(w, "out.json")) as f:
            log["meshopt"] = json.load(f)
        oi = np.fromfile(os.path.join(w, "out_idx.u32"), dtype=np.uint32).astype(np.int64)
    used, rem = np.unique(oi, return_inverse=True)
    f3 = rem.reshape(-1, 3)
    me2 = bpy.data.meshes.new(me.name)
    me2.from_pydata(s_pos[used].astype(np.float64).tolist(), [], f3.tolist())
    me2.uv_layers.new(name=uvname).uv.foreach_set("vector", s_uv[used][f3.ravel()].ravel())
    me2.polygons.foreach_set("material_index", s_m[used][f3[:, 0]].astype(np.int32))
    for m in me.materials:
        me2.materials.append(m)
    bm = bmesh.new()
    bm.from_mesh(me2)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=weld_dist)
    bm.to_mesh(me2)
    bm.free()
    me2.shade_smooth()
    obj.data = me2
    me2.validate(verbose=True, clean_customdata=False)
    log.update({"head_budget": head_budget, "meshopt_target_tris": target1, "after_meshopt_tris": eval_tris(obj),
                "protect_mode": "lock", "protect_tris": int(prot.sum()), "protect_share_of_target": round(share, 4)})


def head_decimate(obj, R, protect, log):
    """collapse modifier on head verts only (group weight 1, no invert); verts touching body / face-front / hand
    triangles are left out of the group = weight 0 = never collapse (Blender 5.1, measured 10-26)."""
    co, t = mesh_coords(obj.data), tris_of(obj.data)
    head, face, hands = region_masks(co, t, R)
    keep = np.zeros(len(co), bool)
    keep[t[~head | ((face | hands) if protect else np.zeros(len(t), bool))].ravel()] = True
    vg = obj.vertex_groups.new(name="__head")
    vg.add(np.nonzero(~keep)[0].tolist(), 1.0, "REPLACE")
    dec = obj.modifiers.new("Decimate", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.use_symmetry = True
    dec.symmetry_axis = "X"
    dec.vertex_group = vg.name
    dec.invert_vertex_group = False
    log["head_free_verts"] = int((~keep).sum())
    return dec


# ------------------------------------------------------------------ main
def main():
    a = parse_args()
    t0 = time.time()
    obj = load_model(os.path.abspath(a["in"]))
    co = mesh_coords(obj.data)
    size = float(np.ptp(co, axis=0).max())
    weld_dist = 1e-5 * size
    log = {"in": os.path.abspath(a["in"]), "target": a["target"], "protect": a["protect"], "weld": a["weld"],
           "xfer": a["xfer"], "warnings": []}
    R = regions(obj, a["hand_radius"])
    if abs(R["cx"]) > 0.02 * R["H"]:
        log["warnings"].append("body centre x=%.4f is off the origin; decimate symmetry X works about x=0" % R["cx"])
    log["regions"] = {k: R[k] for k in ("chin_frac", "chin_anchor_front_silhouette_frac", "chin_rule", "head_frac",
                                        "hand_radius_factor")}
    log["orig"] = {"tris": eval_tris(obj), **counts(obj, R)}
    log["weld_removed_verts"] = weld(obj, weld_dist) if a["weld"] else 0
    src = None
    if a["xfer"]:
        src = obj.copy()
        src.data = obj.data.copy()
        bpy.context.scene.collection.objects.link(src)
    log["method"] = a["method"]
    log["protect_share_of_target"] = 0.0
    if a["method"] == "meshopt":
        meshopt_body(obj, R, a, weld_dist, log)
        dec = head_decimate(obj, R, a["protect"], log)
        start_tris = log["after_meshopt_tris"]
    else:
        dec = obj.modifiers.new("Decimate", "DECIMATE")
        dec.decimate_type = "COLLAPSE"
        dec.use_symmetry = True
        dec.symmetry_axis = "X"
        start_tris = log["orig"]["tris"]
        if a["protect"]:
            cv, tv = mesh_coords(obj.data), tris_of(obj.data)
            _, face, hands = region_masks(cv, tv, R)
            prot = face | hands
            share = float(prot.sum()) / a["target"]
            pw, mode = 1.0, "hard"
            if share > PROTECT_SHARE_MAX:
                pw, mode = SOFT_PW, "soft"
                msg = "protected tris %d = %.1f%% of target > %d%%: soft protect pw=%.2f" % (
                    int(prot.sum()), share * 100, int(PROTECT_SHARE_MAX * 100), SOFT_PW)
                print("WARNING " + msg, flush=True)
                log["warnings"].append(msg)
            vm = np.zeros(len(cv), bool)
            vm[tv[prot].ravel()] = True
            vg = obj.vertex_groups.new(name="__protect")
            vg.add(np.nonzero(vm)[0].tolist(), pw, "REPLACE")
            dec.vertex_group = vg.name
            dec.vertex_group_factor = 1.0
            dec.invert_vertex_group = True
            log.update({"protect_mode": mode, "protect_weight": pw, "protect_tris": int(prot.sum()),
                        "protect_share_of_target": round(share, 4)})
    lo, hi = 0.0, 1.0
    r = min(1.0, a["target"] / max(start_tris, 1))
    tol = max(1, int(a["target"] * 0.005))
    for _ in range(22):
        dec.ratio = r
        n = eval_tris(obj)
        if abs(n - a["target"]) <= tol:
            break
        if n > a["target"]:
            hi = r
        else:
            lo = r
        r = (lo + hi) / 2.0
    log["ratio"] = round(dec.ratio, 6)
    apply_mod(obj, dec)
    for g in ("__protect", "__head"):
        if g in obj.vertex_groups:
            obj.vertex_groups.remove(obj.vertex_groups[g])
    # collapse can leave a few duplicate faces (Coda 10-26: 2); the glTF exporter would silently validate() them away
    log["validate_fixed"] = bool(obj.data.validate(verbose=True, clean_customdata=False))
    if src is not None:
        dt = obj.modifiers.new("NormalXfer", "DATA_TRANSFER")
        dt.object = src
        dt.use_loop_data = True
        dt.data_types_loops = {"CUSTOM_NORMAL"}
        dt.loop_mapping = "POLYINTERP_NEAREST"
        dt.mix_mode = "REPLACE"
        dt.mix_factor = 1.0
        apply_mod(obj, dt)
        bpy.data.objects.remove(src, do_unlink=True)
    raw_open, welded_open, nm = open_edges(obj.data, weld_dist)
    log["result"] = {"tris": eval_tris(obj), **counts(obj, R), "open_edges_raw": raw_open,
                     "open_edges_welded": welded_open, "non_manifold_edges_welded": nm,
                     "custom_normals": bool(obj.data.has_custom_normals)}
    if a["debug_png"]:
        debug_png(obj, R, a["debug_png"])
        log["debug_png"] = os.path.abspath(a["debug_png"])
    out = os.path.abspath(a["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with bpy.context.temp_override(**ops_ctx(obj)):
        bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True, export_normals=True,
                                  export_texcoords=True, export_materials="EXPORT", export_image_format="AUTO")
    log["out"] = out
    log["seconds"] = round(time.time() - t0, 1)
    if a["log"]:
        with open(a["log"], "w", encoding="utf-8") as f:
            json.dump({**log, "regions_full": R}, f, indent=1)
    res = log["result"]
    print("PROTECT_DECIMATE " + json.dumps({
        "method": log["method"], "tris": res["tris"], "head_tris": res["head_tris"], "face_front_tris": res["face_front_tris"],
        "hand_tris": res["hand_tris"], "orig": log["orig"], "protect_mode": log.get("protect_mode"),
        "protect_share_of_target": log["protect_share_of_target"], "weld_removed_verts": log["weld_removed_verts"],
        "open_edges_welded": res["open_edges_welded"], "custom_normals": res["custom_normals"],
        "validate_fixed": log["validate_fixed"],
        "chin_frac": round(R["chin_frac"], 4), "chin_rule": R["chin_rule"], "hand_radius": a["hand_radius"],
        "warnings": log["warnings"], "seconds": log["seconds"], "out": out}), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)
