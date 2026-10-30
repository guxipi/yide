"""Step 4 · project registered paint-over sheets back onto the objects.

blender -b <scene.blend> --factory-startup -P po_project.py --python-exit-code 1 -- --cfg <cfg.json> --work <work_dir>
        [--save <out.blend>]        default: <scene>_painted.blend next to the input

Per face: candidate views where the WHOLE face projects inside one tile; pass 1 strict (face centre + most corner
samples see the camera), pass 2 lenient (centre only), pass 3 fallback (cfg.fallback, default on: no visibility,
best-facing view -> edge-on side faces take the neighbouring paint). Occlusion is tested per group only.
Long faces are first cut every cfg.cut_m (1 m) along world X and Y so every face fits in one tile.
Result: UV layer 'PaintUV', one atlas <work>/atlas_<set>.png (sheets in a grid, scaled by cfg.atlas_scale,
default 0.75), material slot 0 = painted atlas, slot 1 = the object's original first material for faces no
pass could map. NEVER call mesh.materials.clear() afterwards: it resets every face's material_index to 0.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def load_rgb(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1, :, :3]          # top-down


def build_atlas(paint, meta, scale):
    SW, SH = meta["sheet"]
    n = len(meta["sheets"])
    cols = 1 if n == 1 else (2 if n <= 4 else 3)
    rows = math.ceil(n / cols)
    tw, th = round(SW * scale), round(SH * scale)
    AW, AH = cols * tw, rows * th
    atlas = np.zeros((AH, AW, 3), np.float32)
    place = {}
    for i, sh in enumerate(meta["sheets"]):
        c, r = i % cols, i // cols
        src = load_rgb(os.path.join(paint, "reg", sh["name"] + ".png"))
        if scale != 1.0:
            # box downscale via numpy (area average on an integer grid is not guaranteed; use Blender scale)
            im = bpy.data.images.new("s", SW, SH, alpha=False)
            im.pixels.foreach_set(np.concatenate([src[::-1], np.ones((SH, SW, 1), np.float32)], 2).ravel())
            im.scale(tw, th)
            px = np.empty(tw * th * 4, np.float32)
            im.pixels.foreach_get(px)
            src = px.reshape(th, tw, 4)[::-1, :, :3]
            bpy.data.images.remove(im)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = src
        place[sh["name"]] = (c * tw, r * th, tw / SW)
    path = os.path.join(paint, "atlas_%s.png" % meta["set"])
    im = bpy.data.images.new("atlas_" + meta["set"], AW, AH, alpha=False)
    im.pixels.foreach_set(np.concatenate([atlas[::-1], np.ones((AH, AW, 1), np.float32)], 2).ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    return im, place, (AW, AH)


def tile_px(t, p):
    r, u = Vector(t["r"]), Vector(t["u"])
    vspan = t.get("v_span_m", t["v1"] - t["v0"])
    vtop = (t["v0"] + t["v1"]) / 2 + vspan / 2
    x = t["x0"] + (p.dot(r) - t["u0"]) / (t["u1"] - t["u0"]) * t["w"]
    y = t["y0"] + (vtop - p.dot(u)) / vspan * t["h"]
    return x, y


def cut_long_faces(o, cut_m):
    """Bisect along world X and Y planes every cut_m metres (shape unchanged)."""
    me = o.data
    mw = o.matrix_world
    inv = mw.inverted()
    nrm_m = mw.to_3x3().transposed()            # world normal -> local normal (for planes): n_l = M^T n_w
    bm = bmesh.new()
    bm.from_mesh(me)
    W = [mw @ v.co for v in bm.verts]
    for axis in (0, 1):
        lo, hi = min(p[axis] for p in W), max(p[axis] for p in W)
        x = math.floor(lo / cut_m) * cut_m + cut_m
        nw = Vector((1, 0, 0)) if axis == 0 else Vector((0, 1, 0))
        while x < hi:
            pw = Vector((x, 0, 0)) if axis == 0 else Vector((0, x, 0))
            geom = list(bm.verts) + list(bm.edges) + list(bm.faces)
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=inv @ pw, plane_no=(nrm_m @ nw).normalized())
            x += cut_m
    bm.to_mesh(me)
    bm.free()
    me.update()


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    opt = {a[i][2:]: a[i + 1] for i in range(0, len(a) - 1, 2) if a[i].startswith("--")}
    cfg = json.load(open(opt["cfg"], encoding="utf-8"))
    paint, set_name = opt["work"], cfg["set"]
    scale = float(cfg.get("atlas_scale", 0.75))
    meta = json.load(open(os.path.join(paint, "canvas", set_name + "_meta.json"), encoding="utf-8"))
    objs = [bpy.data.objects[n] for n in meta["objects"]]
    orig_mat = {o.name: (o.data.materials[0] if len(o.data.materials) else None) for o in objs}
    for o in objs:
        cut_long_faces(o, float(cfg.get("cut_m", 1.0)))
    atlas, place, (AW, AH) = build_atlas(paint, meta, scale)
    # occlusion BVH per group (a group = objects that belong together, e.g. hull shell + legs); sets made
    # with paint_canvas.py have no groups -> one group of all objects
    all_tiles = [(sh["name"], t) for sh in meta["sheets"] for t in sh["tiles"]]
    bvh_cache = {}

    def group_bvh(names):
        key = tuple(sorted(names))
        if key not in bvh_cache:
            verts, polys = [], []
            for n in key:
                ob = bpy.data.objects[n]
                base = len(verts)
                mw_ = ob.matrix_world
                verts += [mw_ @ v.co for v in ob.data.vertices]
                polys += [[base + i for i in p.vertices] for p in ob.data.polygons]
            bvh_cache[key] = BVHTree.FromPolygons(verts, polys, all_triangles=False, epsilon=0.0)
        return bvh_cache[key]
    mat_paint = bpy.data.materials.get("Painted_" + set_name) or bpy.data.materials.new("Painted_" + set_name)
    mat_paint.use_nodes = True
    nt = mat_paint.node_tree
    nt.nodes.clear()
    o_ = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = atlas
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "PaintUV"
    nt.links.new(uvn.outputs[0], tx.inputs["Vector"])
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs[0], o_.inputs["Surface"])
    mat_raw0 = bpy.data.materials.get("Unpainted") or bpy.data.materials.new("Unpainted")
    use_fallback = bool(cfg.get("fallback", True))
    stats = {}
    for o in objs:
        tiles = [(sn, t) for sn, t in all_tiles if o.name in t.get("group", meta["objects"])]
        grp = next((t["group"] for _, t in tiles if "group" in t), meta["objects"])
        bvh = group_bvh(grp)
        me = o.data
        mw = o.matrix_world
        nmat = mw.to_3x3().inverted().transposed()
        if "PaintUV" in me.uv_layers:
            me.uv_layers.remove(me.uv_layers["PaintUV"])
        uvl = me.uv_layers.new(name="PaintUV")
        me.uv_layers.active = uvl
        mat_raw = orig_mat.get(o.name) or mat_raw0
        me.materials.clear()
        me.materials.append(mat_paint)
        me.materials.append(mat_raw)
        n_paint = n_raw = 0
        for poly in me.polygons:
            c = mw @ poly.center
            nrm = (nmat @ poly.normal).normalized()
            samples = [c] + [c.lerp(mw @ me.vertices[vi].co, 0.6) for vi in poly.vertices][:4]
            best = None
            passes = (True, False, None) if use_fallback else (True, False)
            for strict in passes:
                bestd = 0.2 if strict is not None else -2.0
                for sname, t in tiles:
                    f = Vector(t["f"])
                    d = -nrm.dot(f)
                    if d <= bestd:
                        continue
                    pu = c.dot(Vector(t["r"]))
                    if not (t["u0"] + 0.05 <= pu <= t["u1"] - 0.05):
                        continue
                    inside = True
                    for vi in poly.vertices:
                        xx, yy = tile_px(t, mw @ me.vertices[vi].co)
                        if not (t["x0"] - 2 <= xx <= t["x0"] + t["w"] + 2 and t["y0"] - 2 <= yy <= t["y0"] + t["h"] + 2):
                            inside = False
                            break
                    if not inside:
                        continue
                    # centre must see the camera; strict pass also needs most corner samples to see it.
                    # fallback pass (strict None): no visibility test, the face takes the colour at its
                    # projected spot (edge-on side faces -> the neighbouring paint)
                    if strict is not None and bvh.ray_cast(c - f * 0.01, -f, 500.0)[0] is not None:
                        continue
                    if strict:
                        vis = sum(1 for s_ in samples[1:] if bvh.ray_cast(s_ - f * 0.01, -f, 500.0)[0] is None)
                        if vis < len(samples) - 2:
                            continue
                    edge = min(pu - t["u0"], t["u1"] - pu)
                    key = d + min(edge, 2.0) * 0.01
                    if key > bestd:
                        best, bestd = (sname, t), key
                if best is not None:
                    break
            if best is None:
                poly.material_index = 1
                n_raw += 1
                continue
            poly.material_index = 0
            n_paint += 1
            sname, t = best
            ox, oy, k = place[sname]
            for li in poly.loop_indices:
                p = mw @ me.vertices[me.loops[li].vertex_index].co
                x, y = tile_px(t, p)
                uvl.data[li].uv = ((ox + x * k) / AW, 1.0 - (oy + y * k) / AH)
        stats[o.name] = {"painted_faces": n_paint, "unpainted_faces": n_raw}
    outb = opt.get("save") or bpy.data.filepath.replace(".blend", "_painted.blend")
    atlas.filepath_raw = os.path.join(paint, "atlas_%s.png" % set_name)
    atlas.pack()
    bpy.ops.wm.save_as_mainfile(filepath=outb)
    tot_p = sum(v["painted_faces"] for v in stats.values())
    tot_r = sum(v["unpainted_faces"] for v in stats.values())
    print("PO_JSON " + json.dumps({"ok": True, "blend": outb, "atlas": [AW, AH], "painted_faces": tot_p,
                                   "unpainted_faces": tot_r, "faces": stats}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
