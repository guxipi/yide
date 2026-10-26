"""Shared Blender helpers (import from scripts in this folder: sys.path.insert(0, dirname(__file__))).

Conventions used by every script of this skill (Blender space):
  Z up, character height 1.0, feet at z=0, x centred, character faces -Y, character's own LEFT is +X.
Tripo web GLB exports already face -Y; armature-based checks re-verify with the toe direction.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_any(path):
    """Import glb/gltf/fbx or open a .blend. Returns list of objects in the scene."""
    p = path.lower()
    if p.endswith(".blend"):
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        reset()
        if p.endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=path)
        else:
            bpy.ops.import_scene.gltf(filepath=path)
    # the glTF importer adds an Icosphere as the bone display shape; it wrecks bbox framing (height 2.0)
    shapes = {pb.custom_shape for o in bpy.context.scene.objects if o.type == "ARMATURE" for pb in o.pose.bones if pb.custom_shape}
    for o in shapes:
        bpy.data.objects.remove(o, do_unlink=True)
    return list(bpy.context.scene.objects)


def main_mesh():
    ms = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    return max(ms, key=lambda o: len(o.data.vertices)) if ms else None


def all_meshes(min_verts=100):
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and len(o.data.vertices) >= min_verts]


def armature():
    return next((o for o in bpy.context.scene.objects if o.type == "ARMATURE"), None)


def world_bbox(objs):
    mn = Vector((1e9,) * 3)
    mx = Vector((-1e9,) * 3)
    for o in objs:
        if o.type != "MESH":
            continue
        for v in o.data.vertices:
            w = o.matrix_world @ v.co
            mn = Vector(map(min, mn, w))
            mx = Vector(map(max, mx, w))
    return mn, mx


def normalize_view_only(objs):
    """Return (centre, height) to frame cameras without touching data (for imported GLBs)."""
    mn, mx = world_bbox(objs)
    return (mn + mx) / 2, mx.z - mn.z, mn, mx


def toe_forward(arm):
    """Unit vector of the feet's forward direction from mixamo Foot->ToeBase, or None."""
    if arm is None:
        return None
    b = arm.data.bones
    acc = Vector((0, 0, 0))
    for s in ("Left", "Right"):
        f, t = b.get(f"mixamorig:{s}Foot"), b.get(f"mixamorig:{s}ToeBase")
        if f and t:
            d = (arm.matrix_world @ t.tail_local) - (arm.matrix_world @ f.head_local)
            d.z = 0
            acc += d
    return acc.normalized() if acc.length > 1e-6 else None


def set_engine(scene):
    ids = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for e in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        if e in ids:
            scene.render.engine = e
            return e


def setup_scene(res_x, res_y, bg=(0.25, 0.25, 0.25), strength=1.0):
    sc = bpy.context.scene
    set_engine(sc)
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("qa_world")
    sc.world = w
    w.use_nodes = True
    bgn = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bgn.inputs[0].default_value = (*bg, 1)
    bgn.inputs[1].default_value = strength
    return sc


def emission_from_basecolor():
    """Unlit look: route each material's base-colour source into an Emission shader (judge the texture itself)."""
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None)
        if out is None:
            continue
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        tex = next((n for n in nt.nodes if n.type == "TEX_IMAGE"), None)
        src = None
        if bsdf is not None and bsdf.inputs["Base Color"].links:
            src = bsdf.inputs["Base Color"].links[0].from_socket
        elif tex is not None:
            src = tex.outputs["Color"]
        em = nt.nodes.new("ShaderNodeEmission")
        if src is not None:
            nt.links.new(src, em.inputs[0])
        elif bsdf is not None:
            em.inputs[0].default_value = bsdf.inputs["Base Color"].default_value
        for l in list(out.inputs["Surface"].links):
            nt.links.remove(l)
        nt.links.new(em.outputs[0], out.inputs["Surface"])


def clay_all(color=(0.75, 0.72, 0.70)):
    clay = bpy.data.materials.new("qa_clay")
    clay.use_nodes = True
    b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = 0.6
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(clay)
    L = bpy.data.lights.new("qa_sun", "SUN")
    L.energy = 3
    lo = bpy.data.objects.new("qa_sun", L)
    bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler = (0.6, 0.3, 0.4)


class OrthoCam:
    def __init__(self):
        sc = bpy.context.scene
        self.cam = bpy.data.cameras.new("qa_cam")
        self.cam.type = "ORTHO"
        self.obj = bpy.data.objects.new("qa_cam", self.cam)
        sc.collection.objects.link(self.obj)
        sc.camera = self.obj

    def shot(self, path, target, direction, scale, dist=4.0):
        """direction = vector from target TOWARDS the camera."""
        self.cam.ortho_scale = scale
        d = Vector(direction).normalized()
        self.obj.location = Vector(target) + d * dist
        self.obj.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        bpy.context.scene.render.filepath = os.path.abspath(path)
        bpy.ops.render.render(write_still=True)
        return path


# camera directions (from target towards camera) for a character facing -Y
DIRS = {
    "front": (0, -1, 0),
    "back": (0, 1, 0),
    "left": (1, 0, 0),      # shows the character's own LEFT side (+X): face points image-left
    "right": (-1, 0, 0),
    "34": (0.6, -1, 0.1),
    "34high": (0.6, -0.8, 0.7),
    "top70": (0, -math.cos(math.radians(70)), math.sin(math.radians(70))),
    "high45": (0, -0.7, 0.7),
    "under": (0, -0.8, -0.6),
}


def normalize_rig_data(arm, mesh):
    """Bake scale/translation into data: height 1.0, feet z=0, x centred. Object transforms end as identity scale."""
    for o in (arm, mesh):
        if o is None:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    pts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    h = max(p.z for p in pts) - min(p.z for p in pts)
    s = Matrix.Scale(1.0 / h, 4)
    mesh.data.transform(s)
    if arm:
        arm.data.transform(s)
    pts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    off = Vector((-(min(p.x for p in pts) + max(p.x for p in pts)) / 2, 0, -min(p.z for p in pts)))
    t = Matrix.Translation(off)
    mesh.data.transform(t)
    if arm:
        arm.data.transform(t)
    return h


def export_fbx(path, deform_only=False):
    """FBX for Unity. apply_scale_options='FBX_SCALE_ALL' is mandatory: without it the armature root
    carries scale 100 in Unity and anything parented to a hand bone (guns) becomes 100x (giant gun in the
    Gear-tab preview, 2026-10-07)."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    for o in bpy.context.scene.objects:
        o.select_set(o.type in ("MESH", "ARMATURE"))
    arm = armature()
    if arm:
        bpy.context.view_layer.objects.active = arm
        for b in arm.pose.bones:
            b.matrix_basis = Matrix.Identity(4)
    bpy.ops.export_scene.fbx(filepath=os.path.abspath(path), use_selection=True, object_types={"ARMATURE", "MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_ALL", add_leaf_bones=False,
                             bake_anim=False, axis_forward="-Z", axis_up="Y", path_mode="RELATIVE",
                             embed_textures=False, use_armature_deform_only=deform_only)
    return path
