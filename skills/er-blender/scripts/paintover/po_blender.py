"""Paint-over pipeline, Blender side (Blender 5.1/5.2, background-safe). Shared by po_canvas / po_project / po_review.

Config (JSON, one per scene/set; see ../../references/08-手绘paintover.md and examples/):
  set            name; sheets are <set>_00.png ...
  groups         {"group": ["obj", ...]}            objects painted together (they occlude each other)
  group_prefixes ["RN_", ...]                        alternative: every mesh whose name starts with a prefix is its own group
  views          ["G", "E", "W"]                     G = game camera (fixed yaw, from -Y, pitch `pitch`); S N E W T = orthographic
  pitch          46                                  ER V5 game camera pitch
  ppm            70                                  pixels per metre for the main views
  side_ratio     0.6                                 density factor for E / W side views
  underlay       "col" | "material"                  vertex colour attribute 'Col', or the object's own base colour/texture
Painting is done by sol (po_prompts.py + run_codex.sh), not here.
"""
import json
import math
import os

import bpy
import numpy as np
from mathutils import Matrix, Vector

SHEET_W, SHEET_H = 1536, 1024     # the size image_gen returns for landscape
MARGIN = 36


def views(pitch_deg=46.0):
    p = math.radians(pitch_deg)
    return {
        "G": ((0.0, math.cos(p), -math.sin(p)), (1.0, 0.0, 0.0), (0.0, math.sin(p), math.cos(p))),
        "S": ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
        "N": ((0, -1, 0), (-1, 0, 0), (0, 0, 1)),
        "E": ((-1, 0, 0), (0, 1, 0), (0, 0, 1)),
        "W": ((1, 0, 0), (0, -1, 0), (0, 0, 1)),
        "T": ((0, 0, -1), (1, 0, 0), (0, 1, 0)),
    }


def load_cfg(path):
    cfg = json.load(open(path, encoding="utf-8"))
    cfg.setdefault("views", ["G", "E", "W"])
    cfg.setdefault("pitch", 46.0)
    cfg.setdefault("ppm", 70.0)
    cfg.setdefault("side_ratio", 0.6)
    cfg.setdefault("underlay", "col")
    return cfg


def resolve_groups(cfg):
    if "groups" in cfg:
        return {k: list(v) for k, v in cfg["groups"].items()}
    g = {}
    for o in bpy.data.objects:
        if o.type == "MESH" and any(o.name.startswith(p) for p in cfg.get("group_prefixes", [])):
            g[o.name] = [o.name]
    if not g:
        raise ValueError("no groups resolved from config")
    return g


def world_pts(objs):
    pts = []
    for o in objs:
        mw = o.matrix_world
        pts += [tuple(mw @ v.co) for v in o.data.vertices]
    return np.array(pts)


def _sock(node, ident):
    for x in list(node.inputs) + list(node.outputs):
        if x.identifier == ident:
            return x
    raise KeyError(ident)


def _ao_emission(nt, color_socket):
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.9
    ao.samples = 16
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = 0.72
    mr.inputs["To Max"].default_value = 1.0
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    _sock(mul, "Factor_Float").default_value = 1.0
    L = nt.links
    L.new(color_socket, ao.inputs["Color"])
    L.new(ao.outputs["AO"], mr.inputs["Value"])
    L.new(color_socket, _sock(mul, "A_Color"))
    L.new(mr.outputs["Result"], _sock(mul, "B_Color"))
    L.new(_sock(mul, "Result_Color"), em.inputs["Color"])
    L.new(em.outputs[0], out.inputs["Surface"])


def underlay_col():
    mat = bpy.data.materials.new("PO_Underlay")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "GEOMETRY"
    attr.attribute_name = "Col"
    _ao_emission(nt, attr.outputs["Color"])
    return mat


def underlay_from_material(src):
    """Copy of `src` whose Principled base colour (texture or value) feeds the AO x emission underlay."""
    mat = src.copy()
    mat.name = "PO_U_" + src.name
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    base = bsdf.inputs["Base Color"] if bsdf else None
    if base is not None and base.is_linked:
        sock = base.links[0].from_socket
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = tuple(base.default_value) if base is not None else (0.8, 0.8, 0.8, 1)
        sock = rgb.outputs[0]
    for n in list(nt.nodes):
        if n.type in ("OUTPUT_MATERIAL",):
            nt.nodes.remove(n)
    _ao_emission(nt, sock)
    return mat


def apply_underlay(cfg, objs):
    if cfg["underlay"] == "col":
        mat = underlay_col()
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)
        return
    cache = {}
    for o in objs:
        for i, s in enumerate(o.material_slots):
            if s.material is None:
                continue
            if s.material.name not in cache:
                cache[s.material.name] = underlay_from_material(s.material)
            o.data.materials[i] = cache[s.material.name]


def setup_canvas_render(scene):
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 32
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("W")
    scene.world.use_nodes = True
    next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND").inputs["Strength"].default_value = 0.0
    cam = bpy.data.objects.new("PO_Cam", bpy.data.cameras.new("PO_Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def tile_spec(objs, view, vdefs, pad_m=0.3):
    f, r, u = (Vector(x) for x in vdefs[view])
    P = world_pts(objs)
    pu, pv, pf = P @ np.array(r[:]), P @ np.array(u[:]), P @ np.array(f[:])
    return {"view": view, "f": list(f), "r": list(r), "u": list(u),
            "u0": float(pu.min() - pad_m), "u1": float(pu.max() + pad_m),
            "v0": float(pv.min() - pad_m), "v1": float(pv.max() + pad_m),
            "depth_min": float(pf.min() - 5.0), "depth_max": float(pf.max() + 5.0)}


def render_tile(scene, cam, t, path):
    f, r, u = Vector(t["f"]), Vector(t["r"]), Vector(t["u"])
    uc, vc = (t["u0"] + t["u1"]) / 2, (t["v0"] + t["v1"]) / 2
    cam.matrix_world = Matrix.Translation(r * uc + u * vc + f * t["depth_min"]) @ Matrix((r, u, -f)).transposed().to_4x4()
    cd = cam.data
    cd.type = "ORTHO"
    cd.sensor_fit = "HORIZONTAL"
    cd.ortho_scale = t["u1"] - t["u0"]
    cd.clip_start = 0.01
    cd.clip_end = t["depth_max"] - t["depth_min"] + 10
    scene.render.resolution_x, scene.render.resolution_y = t["w"], t["h"]
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    t["v_span_m"] = (t["u1"] - t["u0"]) * t["h"] / t["w"]


def _img_to_np(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[::-1]


def save_np(arr, path):
    hh, ww = arr.shape[:2]
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    im = bpy.data.images.new("po_o", ww, hh, alpha=False)
    im.pixels.foreach_set(np.concatenate([arr[..., :3], np.ones((hh, ww, 1), np.float32)], 2)[::-1].ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def compose(sheet_path, mask_path, tiles):
    sheet = np.zeros((SHEET_H, SHEET_W, 3), np.float32)
    sheet[..., 1] = 1.0                                     # pure green #00FF00
    mask = np.zeros((SHEET_H, SHEET_W), np.float32)
    for t in tiles:
        px = _img_to_np(t["tmp"])
        h, w = px.shape[:2]
        a = px[..., 3:4]
        y0, x0 = t["y0"], t["x0"]
        reg = sheet[y0:y0 + h, x0:x0 + w]
        reg[:] = px[..., :3] * a + reg * (1 - a)
        mask[y0:y0 + h, x0:x0 + w] = np.maximum(mask[y0:y0 + h, x0:x0 + w], a[..., 0])
    save_np(sheet, sheet_path)
    save_np(mask, mask_path)


def pack(tiles):
    """First-fit decreasing-height shelf packing onto SHEET_W x SHEET_H sheets."""
    tiles.sort(key=lambda t: (-t["h"], -t["w"]))
    sheets = []
    limx, limy = SHEET_W - MARGIN, SHEET_H - MARGIN
    for t in tiles:
        placed = False
        for sh in sheets:
            for row in sh["rows"]:
                if t["h"] <= row[1] and row[2] + t["w"] <= limx:
                    t["x0"], t["y0"] = row[2], row[0]
                    row[2] += t["w"] + MARGIN
                    placed = True
                    break
            if not placed and sh["y_free"] + t["h"] <= limy:
                sh["rows"].append([sh["y_free"], t["h"], MARGIN + t["w"] + MARGIN])
                t["x0"], t["y0"] = MARGIN, sh["y_free"]
                sh["y_free"] += t["h"] + MARGIN
                placed = True
            if placed:
                sh["tiles"].append(t)
                break
        if not placed:
            t["x0"], t["y0"] = MARGIN, MARGIN
            sheets.append({"rows": [[MARGIN, t["h"], MARGIN + t["w"] + MARGIN]], "y_free": MARGIN + t["h"] + MARGIN,
                           "tiles": [t]})
    return [s["tiles"] for s in sheets]
