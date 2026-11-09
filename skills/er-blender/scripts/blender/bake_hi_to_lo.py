"""Bake a high-poly look-dev model's colour onto a low-poly shipping mesh (Cycles, selected-to-active).

Use when an item's detail (leaves, flowers, block joints, vines) cannot fit the triangle budget
(看板硬口径 S <= 300 / M <= 1200, 11-09 勾哥「高模烘到低模」). Generalised from the one-off
ArtWork/ExpeditionPOI/_Flora/gen/refine_flora.py (Tripo hi -> lo, DIFFUSE colour bake).

Library (import from a build script that already made both meshes):
    import bake_hi_to_lo as B
    img = B.bake_color(hi_objs, lo_obj, size=1024, png="out/round_col.png", extrusion=0.6, ray=1.2)
    B.preview_material(lo_obj, img)        # lo now shows the baked texture (Workbench TEXTURE / EEVEE)

Hi objects that carry kitlib's "Col" vertex colour (and no material) get a temporary emission material
reading it, so the bake is pure albedo (no lighting): Unity LabLit lights the low mesh itself.
Hi objects that already have materials (Tripo textures) are baked with DIFFUSE / COLOR instead.
Rays start `extrusion` metres outside the low surface and travel `ray` metres inward: the low mesh must
envelope the hi detail (flowers sticking out above a foliage dome need extrusion >= their height above it).
Background-safe (temp_override via _er_bl.ops_ctx).
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _er_bl as er  # noqa: E402


def vcol_emit_material(name="ER_VColEmit", attr="Col"):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    at = nt.nodes.new("ShaderNodeAttribute")
    at.attribute_name = attr
    nt.links.new(at.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return m


def uv_unwrap(obj, angle=66.0, margin=0.02):
    with bpy.context.temp_override(**er.ops_ctx(obj)):
        bpy.ops.object.mode_set(mode="EDIT")
        try:
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin)
        finally:
            bpy.ops.object.mode_set(mode="OBJECT")
    if not obj.data.uv_layers:
        raise RuntimeError("smart_project produced no UV layer on " + obj.name)


def _bake_target(lo, img):
    m = bpy.data.materials.new(lo.name + "_Bake")
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    lo.data.materials.clear()
    lo.data.materials.append(m)
    return m


def bake_color(hi_objs, lo, size=1024, png=None, extrusion=0.5, ray=1.0, margin=8):
    sc = bpy.context.scene
    prev_engine = sc.render.engine
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 1
    vcol = all(len(o.data.materials) == 0 and "Col" in o.data.color_attributes for o in hi_objs)
    saved = {}
    if vcol:
        em = vcol_emit_material()
        for o in hi_objs:
            saved[o.name] = list(o.data.materials)
            o.data.materials.clear()
            o.data.materials.append(em)
    for o in hi_objs:
        o.hide_render = False
    if not lo.data.uv_layers:
        uv_unwrap(lo)
    img = bpy.data.images.new(lo.name + "_col", size, size, alpha=False)
    _bake_target(lo, img)
    kw = dict(use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=ray, margin=margin, use_clear=True)
    with bpy.context.temp_override(**er.ops_ctx(lo, hi_objs)):
        if vcol:
            r = bpy.ops.object.bake(type="EMIT", **kw)
        else:
            r = bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, **kw)
    if "FINISHED" not in r:
        raise RuntimeError("bake failed: %s" % r)
    if png:
        os.makedirs(os.path.dirname(os.path.abspath(png)), exist_ok=True)
        img.filepath_raw = png
        img.file_format = "PNG"
        img.save()
    for name, mats in saved.items():
        o = bpy.data.objects[name]
        o.data.materials.clear()
        for m in mats:
            o.data.materials.append(m)
    sc.render.engine = prev_engine
    return img


def preview_material(lo, img):
    """Image -> Base Color of a principled BSDF (Workbench TEXTURE mode reads the active image node)."""
    m = bpy.data.materials.new(lo.name + "_Baked")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.nodes.active = tex
    lo.data.materials.clear()
    lo.data.materials.append(m)
    return m
