"""ER Blender shared helpers (Blender 5.1, background-safe).

Import from an entry script that lives in the same folder:
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import _er_bl as er
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

# LabLit preview constants (two-step ramp; mirrors the Unity LabLit look closely enough to judge faceting)
# fixed key light, stage frame (long axis = X, camera azimuth 0 sits on -Y): from above, slightly behind
# the -Y face so that the g46/front side face falls just into shadow and every rounded transition between
# top and side has to carry the terminator -> facets show up as a stair-stepped terminator.
SUN_DIR = Vector((-0.50, 0.30, 0.81)).normalized()
LIT_THRESHOLD = 0.0       # N.L value where shadow turns into light
LIT_SOFT = 0.08           # width of the terminator band in N.L units
SHADOW_TINT = (0.62, 0.66, 0.78)  # base * tint = shadow colour (cool shadow, no black)


# ---------------------------------------------------------------- cli / io
def script_args(argv=None):
    argv = sys.argv if argv is None else argv
    return argv[argv.index("--") + 1:] if "--" in argv else []


def emit(summary):
    """One-line JSON summary on stdout (prefixed so callers can grep it out of Blender noise)."""
    print("ER_JSON " + json.dumps(summary, ensure_ascii=False), flush=True)


def run_main(main):
    """Wrap an entry main(argv): any exception -> JSON error line + non-zero exit."""
    try:
        main(script_args())
    except SystemExit:
        raise
    except Exception as ex:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        emit({"ok": False, "error": "%s: %s" % (type(ex).__name__, ex)})
        sys.stdout.flush()
        os._exit(1)


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def enum_ids(rna_type, prop):
    return [e.identifier for e in rna_type.bl_rna.properties[prop].enum_items]


def set_engine(scene, preferred):
    """The static enum on RenderSettings lists only BLENDER_EEVEE in 5.1 (add-on engines such as CYCLES
    are dynamic), so try assigning and let TypeError tell us what is valid."""
    errors = []
    for name in preferred:
        try:
            scene.render.engine = name
            return name
        except TypeError as ex:
            errors.append(str(ex))
    raise RuntimeError("no engine among %s: %s" % (preferred, errors[-1] if errors else ""))


# ---------------------------------------------------------------- context
def ops_ctx(obj, others=()):
    """kwargs for bpy.context.temp_override(**ops_ctx(obj)) so object/bake/modifier ops run in -b."""
    sel = [obj] + [o for o in others if o is not obj]
    bpy.context.view_layer.update()  # objects removed via bpy.data leave None entries until the layer resyncs
    for o in bpy.context.view_layer.objects:
        if o is not None:
            o.select_set(o in sel)
    bpy.context.view_layer.objects.active = obj
    ctx = {
        "object": obj,
        "active_object": obj,
        "selected_objects": sel,
        "selected_editable_objects": sel,
        "view_layer": bpy.context.view_layer,
        "scene": bpy.context.scene,
    }
    win = bpy.context.window_manager.windows[0] if bpy.context.window_manager.windows else None
    if win is not None:
        ctx["window"] = win
    return ctx


# ---------------------------------------------------------------- mesh utils
def mesh_coords(me):
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def bbox(me):
    co = mesh_coords(me)
    return co.min(axis=0), co.max(axis=0)


def origin_bottom_center(obj):
    """Move mesh so the object origin sits at bbox bottom-centre (x/y centre, z min)."""
    lo, hi = bbox(obj.data)
    off = Vector((-(lo[0] + hi[0]) / 2.0, -(lo[1] + hi[1]) / 2.0, -lo[2]))
    obj.data.transform(Matrix.Translation(off))
    obj.matrix_world = Matrix.Identity(4)
    obj.data.update()
    return list(off)


def corner_normals(me):
    n = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", n)
    return n.reshape(-1, 3)


def weld(obj, dist=1e-5, keep_normals=True):
    """Merge-by-distance. Keeps the current per-corner shading (custom normals) through the weld.
    Returns number of vertices removed."""
    me = obj.data
    keep = None
    if keep_normals and len(me.loops):
        keep = corner_normals(me)
        a = me.attributes.new("_er_keep_n", "FLOAT_VECTOR", "CORNER")
        a.data.foreach_set("vector", keep.ravel())
    n0 = len(me.vertices)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(me)
    bm.free()
    if keep is not None:
        a = me.attributes["_er_keep_n"]
        n = np.empty(len(me.loops) * 3, dtype=np.float32)
        a.data.foreach_get("vector", n)
        me.attributes.remove(me.attributes["_er_keep_n"])
        me.normals_split_custom_set(n.reshape(-1, 3).tolist())
    me.update()
    return n0 - len(me.vertices)


def import_any(path, weld_dist=1e-5, keep_normals=True):
    """Import glb/gltf/fbx -> apply transforms -> join into ONE mesh -> weld -> origin bottom-centre.
    Non-mesh objects (empties, armatures) are deleted. Returns (obj, report)."""
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path, use_custom_normals=True)
    else:
        raise ValueError("unsupported file: " + path)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if not meshes:
        raise RuntimeError("no mesh in " + path)
    for o in meshes:
        if o.data.users > 1:
            o.data = o.data.copy()
        mw = o.matrix_world.copy()
        o.parent = None
        o.data.transform(mw)
        o.matrix_world = Matrix.Identity(4)
    dropped = [o.name for o in new if o.type != "MESH"]
    for o in [o for o in new if o.type != "MESH"]:
        bpy.data.objects.remove(o, do_unlink=True)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(**ops_ctx(obj, meshes)):
            bpy.ops.object.join()
    obj.name = os.path.splitext(os.path.basename(path))[0]
    pre = inspect(obj)
    welded = weld(obj, weld_dist, keep_normals) if weld_dist and weld_dist > 0 else 0
    origin_bottom_center(obj)
    return obj, {"joined_meshes": len(meshes), "dropped_non_mesh": dropped, "welded_verts": welded, "weld_dist": weld_dist,
                 "pre_weld_tris": pre["tris"], "pre_weld_degenerate_faces": pre["degenerate_faces"]}


def inspect(obj):
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    open_e = sum(1 for e in bm.edges if len(e.link_faces) == 1)
    nonman = sum(1 for e in bm.edges if len(e.link_faces) != 2)
    lo, hi = bbox(me)
    eps = float((hi - lo).max()) * 1e-5  # degenerate: a zero-length edge or near-zero area at 1e-5 of model size
    degen = sum(1 for f in bm.faces if f.calc_area() < eps * eps or
                any(e.calc_length() < eps for e in f.edges))
    bm.free()
    return {
        "tris": int(sum(len(p.vertices) - 2 for p in me.polygons)),
        "verts": len(me.vertices),
        "open_edges": open_e,
        "non_manifold_edges": nonman,
        "degenerate_faces": degen,
        "materials": len([s for s in obj.material_slots if s.material]),
        "uv_layers": len(me.uv_layers),
        "bbox": [round(float(v), 5) for v in (hi - lo)],
        "custom_normals": bool(me.has_custom_normals),
    }


# ---------------------------------------------------------------- materials
def new_material(name):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:  # 5.1: use_nodes is deprecated but still needed on some paths
        mat.use_nodes = True
    return mat


def find_tex_node(mat):
    """First image texture feeding the material (prefer the one wired to Base Color)."""
    if mat is None or mat.node_tree is None:
        return None
    nodes = mat.node_tree.nodes
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        sock = bsdf.inputs[0]
        if sock.is_linked and sock.links[0].from_node.type == "TEX_IMAGE":
            return sock.links[0].from_node
    return next((n for n in nodes if n.type == "TEX_IMAGE" and n.image), None)


def material_base_color(mat):
    if mat is None or mat.node_tree is None:
        return (0.8, 0.8, 0.8)
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        return tuple(mat.diffuse_color[:3])
    return tuple(bsdf.inputs[0].default_value[:3])


def _sock(node, ident):
    for s in list(node.inputs) + list(node.outputs):
        if s.identifier == ident:
            return s
    raise KeyError(ident)


def _lablit_material(name, image=None, interpolation="Linear", color=None):
    mat = new_material(name)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    dot.inputs[1].default_value = SUN_DIR
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.clamp = True
    mr.inputs["From Min"].default_value = LIT_THRESHOLD - LIT_SOFT / 2.0
    mr.inputs["From Max"].default_value = LIT_THRESHOLD + LIT_SOFT / 2.0
    mr.inputs["To Min"].default_value = 0.0
    mr.inputs["To Max"].default_value = 1.0
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    _sock(mul, "Factor_Float").default_value = 1.0
    _sock(mul, "B_Color").default_value = (*SHADOW_TINT, 1.0)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = interpolation
        base = tex.outputs["Color"]
    else:
        rgb = nt.nodes.new("ShaderNodeRGB")
        rgb.outputs[0].default_value = (*(color or (0.8, 0.8, 0.8)), 1.0)
        base = rgb.outputs[0]
    L = nt.links
    L.new(geo.outputs["Normal"], dot.inputs[0])
    L.new(dot.outputs["Value"], mr.inputs["Value"])
    L.new(base, _sock(mul, "A_Color"))
    L.new(mr.outputs["Result"], _sock(mix, "Factor_Float"))
    L.new(_sock(mul, "Result_Color"), _sock(mix, "A_Color"))
    L.new(base, _sock(mix, "B_Color"))
    L.new(_sock(mix, "Result_Color"), em.inputs["Color"])
    L.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def make_lablit_preview(obj, base_image=None, base_color=None):
    """Replace materials with an unlit Emission 'LabLit preview':
    N(world).SUN -> MapRange two-step -> Mix(base*SHADOW_TINT, base).
    base_image (bpy Image or path) / base_color override every slot; when both are None each slot
    keeps its own base texture (or its Principled base colour)."""
    if isinstance(base_image, str):
        base_image = bpy.data.images.load(base_image, check_existing=True)
    slots = list(obj.material_slots) or []
    if base_image is not None or base_color is not None or not slots:
        mat = _lablit_material("LabLitPreview", base_image, "Linear", base_color)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        return [mat.name]
    names = []
    for i, s in enumerate(slots):
        tn = find_tex_node(s.material)
        if tn is not None:
            mat = _lablit_material("LabLitPreview_%d" % i, tn.image, tn.interpolation)
        else:
            mat = _lablit_material("LabLitPreview_%d" % i, None, color=material_base_color(s.material))
        s.material = mat
        names.append(mat.name)
    return names


def make_clay(obj, color=(0.7, 0.7, 0.7)):
    mat = new_material("Clay")
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return [mat.name]


def save_image_png(img, path):
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
