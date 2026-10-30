"""Review renders for kit buildings (Blender 5.2 EEVEE).

Shading = two-step toon approximating Unity LabLit: Diffuse BSDF (sun + cast shadows) -> Shader to RGB ->
constant ramp -> mix(base * cool shadow tint, base) -> Emission. Base colour comes from the 'Col' attribute.
Views:
  g46       V5 gameplay camera (pitch 46 deg, vertical FOV 25 deg) framing the whole building
  g46_game  V5 camera at game distance: ~14 m of ground across the frame, centred on the main entrance
  g46_128   g46_game scaled to 128 px wide
  q34       three-quarter perspective
  top       orthographic plan
Each view is rendered twice: roof on (everything) and roof off (Roof + Up hidden = the inside view).
A 1.52 m orange capsule (current in-game Wren height) stands outside the entrance as a ruler.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

SUN_DIR = Vector((-0.42, -0.62, 0.66)).normalized()    # light comes from south-west, above
SHADOW_TINT = (0.60, 0.62, 0.80)
GROUND = "#D9A56A"
VFOV = 25.0


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def toon_material(name, color=None, white=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "LINEAR"
    ramp.color_ramp.elements[0].position = 0.10
    ramp.color_ramp.elements[1].position = 0.16
    if white:
        base = nt.nodes.new("ShaderNodeRGB")
        base.outputs[0].default_value = (0.85, 0.85, 0.85, 1)
        bsock = base.outputs[0]
    elif color is not None:
        base = nt.nodes.new("ShaderNodeRGB")
        base.outputs[0].default_value = (*color, 1)
        bsock = base.outputs[0]
    else:
        base = nt.nodes.new("ShaderNodeAttribute")
        base.attribute_type = "GEOMETRY"
        base.attribute_name = "Col"
        bsock = base.outputs["Color"]
    shadow = nt.nodes.new("ShaderNodeMix")
    shadow.data_type = "RGBA"
    shadow.blend_type = "MULTIPLY"
    shadow.inputs[0].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    em = nt.nodes.new("ShaderNodeEmission")
    L = nt.links

    def sock(node, ident):
        for s in list(node.inputs) + list(node.outputs):
            if s.identifier == ident:
                return s
        raise KeyError(ident)

    sock(shadow, "B_Color").default_value = (*SHADOW_TINT, 1)
    L.new(bsock, sock(shadow, "A_Color"))
    L.new(dif.outputs[0], s2r.inputs[0])
    L.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    L.new(ramp.outputs["Color"], sock(mix, "Factor_Float"))
    L.new(sock(shadow, "Result_Color"), sock(mix, "A_Color"))
    L.new(bsock, sock(mix, "B_Color"))
    L.new(sock(mix, "Result_Color"), em.inputs["Color"])
    L.new(em.outputs[0], out.inputs["Surface"])
    return mat


def setup(scene, w, h):
    scene.render.engine = "BLENDER_EEVEE"
    scene.eevee.taa_render_samples = 48
    try:
        scene.eevee.use_shadows = True
    except AttributeError:
        pass
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = False
    r.image_settings.file_format = "PNG"
    vs = scene.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    world = bpy.data.worlds.new("W")
    scene.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*hexlin("#B9C4D6"), 1)
    bg.inputs["Strength"].default_value = 0.0
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 4.0
    sun.data.angle = math.radians(2.0)
    sun.rotation_euler = SUN_DIR.to_track_quat("Z", "Y").to_euler()
    scene.collection.objects.link(sun)


def add_ground(scene, size=600.0):
    me = bpy.data.meshes.new("Ground")
    s = size / 2
    me.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Ground", me)
    scene.collection.objects.link(ob)
    ob.data.materials.append(toon_material("GroundMat", color=hexlin(GROUND)))
    return ob


def add_ruler(scene, x, y, height=1.52):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.28, depth=height - 0.56, location=(x, y, (height) / 2))
    cyl = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.28, location=(x, y, height - 0.28))
    top = bpy.context.active_object
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.28, location=(x, y, 0.28))
    bot = bpy.context.active_object
    mat = toon_material("RulerMat", color=hexlin("#F08A3C"))
    for o in (cyl, top, bot):
        o.data.materials.append(mat)
        for p in o.data.polygons:
            p.use_smooth = True
        o.name = "Ruler_Wren_1p52"
    return [cyl, top, bot]


def cam_rot(az, pitch):
    if pitch >= 89.999:
        return Matrix.Identity(3)
    a, e = math.radians(az), math.radians(pitch)
    to_cam = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
    return (-to_cam).to_track_quat("-Z", "Y").to_matrix()


def place_frame(cam, pts, rot, w, h, persp=True, margin=1.08):
    import numpy as np
    right, up, back = rot.col[0], rot.col[1], rot.col[2]
    R = np.array([right[:], up[:], back[:]])
    P = np.array(pts)
    c = (P.min(0) + P.max(0)) / 2
    loc = (P - c) @ R.T
    cd = cam.data
    aspect = w / h
    if persp:
        cd.type = "PERSP"
        cd.sensor_fit = "VERTICAL"
        cd.angle_y = math.radians(VFOV)
        tv = math.tan(math.radians(VFOV) / 2) / margin
        th = tv * aspect
        D = float(np.max(np.maximum(np.abs(loc[:, 0]) / th, np.abs(loc[:, 1]) / tv) + loc[:, 2]))
        pos = Vector(c) + back * D
    else:
        cd.type = "ORTHO"
        x0, x1 = loc[:, 0].min(), loc[:, 0].max()
        y0, y1 = loc[:, 1].min(), loc[:, 1].max()
        cd.ortho_scale = float(max(x1 - x0, (y1 - y0) * aspect) * margin)
        pos = Vector(c) + right * float((x0 + x1) / 2) + up * float((y0 + y1) / 2) + back * 200
    cd.clip_start, cd.clip_end = 0.1, 1000
    cam.matrix_world = Matrix.Translation(pos) @ rot.to_4x4()


def place_game(cam, target, ground_width=14.0, w=1280, h=720):
    """V5 camera: pitch 46, vertical FOV 25, distance so ~ground_width m of ground spans the frame width."""
    rot = cam_rot(0, 46)
    cd = cam.data
    cd.type = "PERSP"
    cd.sensor_fit = "VERTICAL"
    cd.angle_y = math.radians(VFOV)
    th = math.tan(math.radians(VFOV) / 2) * (w / h)
    D = (ground_width / 2) / th
    back = rot.col[2]
    cam.matrix_world = Matrix.Translation(Vector(target) + back * D) @ rot.to_4x4()
    cd.clip_start, cd.clip_end = 0.1, 1000


def bbox_pts(objs):
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(tuple(o.matrix_world @ Vector(c)))
    return pts


def render_all(out, prefix, entrance=(-10.2, -6.3), ruler_at=(-10.2, -8.2)):
    scene = bpy.context.scene
    rdir = os.path.join(out, "renders")
    os.makedirs(rdir, exist_ok=True)
    W, H = 1600, 1000
    setup(scene, W, H)
    model = [o for o in scene.objects if o.type == "MESH" and o.name.startswith(prefix)]
    mat = toon_material("KitToon")
    white = toon_material("KitWhite", white=True)
    for o in model:
        o.data.materials.clear()
        o.data.materials.append(mat)
    add_ground(scene)
    add_ruler(scene, *ruler_at)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    pts = bbox_pts(model)
    hide_up = [o for o in model if "_Up" in o.name or "Roof" in o.name]
    files = []

    def shot(name, w=W, h=H):
        scene.render.resolution_x, scene.render.resolution_y = w, h
        p = os.path.join(rdir, "%s_%s.png" % (prefix, name))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)
        return p

    for state in ("roof_on", "roof_off"):
        for o in hide_up:
            o.hide_render = (state == "roof_off")
        place_frame(cam, pts, cam_rot(0, 46), W, H)
        shot("g46_" + state)
        place_frame(cam, pts, cam_rot(35, 32), W, H)
        shot("q34_" + state)
        place_game(cam, (entrance[0] + 3.0, entrance[1] + 3.0, 0.0), 14.0, 1280, 720)
        p = shot("g46game_" + state, 1280, 720)
        img = bpy.data.images.load(p)
        img.scale(128, 72)
        img.filepath_raw = p.replace(".png", "_128.png")
        img.file_format = "PNG"
        img.save()
        files.append(img.filepath_raw)
    for o in hide_up:
        o.hide_render = True
    place_frame(cam, pts, cam_rot(0, 90), W, H, persp=False)
    shot("top_roof_off")
    for o in hide_up:
        o.hide_render = False
    # shading-only check (facets / bevel reads)
    for o in model:
        o.data.materials.clear()
        o.data.materials.append(white)
    place_frame(cam, pts, cam_rot(35, 32), W, H)
    shot("q34_white")
    print("ER_JSON " + str({"renders": files}))
    return files


def render_simple(out, label, model, ruler_at, game_target, game_width=14.0, views=("g46", "q34", "q34b", "game")):
    """Generic review set for one kit object group (no roof states)."""
    scene = bpy.context.scene
    rdir = os.path.join(out, "renders")
    os.makedirs(rdir, exist_ok=True)
    W, H = 1600, 1000
    if scene.camera is None:
        setup(scene, W, H)
        add_ground(scene)
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam = scene.camera
    mat = bpy.data.materials.get("KitToon") or toon_material("KitToon")
    for o in model:
        o.data.materials.clear()
        o.data.materials.append(mat)
    rul = add_ruler(scene, *ruler_at) if ruler_at else []
    others = [o for o in scene.objects if o.type == "MESH" and o not in model and o.name != "Ground"
              and o not in rul]
    for o in others:
        o.hide_render = True
    pts = bbox_pts(model)
    files = []

    def shot(name, w=W, h=H):
        scene.render.resolution_x, scene.render.resolution_y = w, h
        p = os.path.join(rdir, "%s_%s.png" % (label, name))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)

    if "g46" in views:
        place_frame(cam, pts, cam_rot(0, 46), W, H)
        shot("g46")
    if "q34" in views:
        place_frame(cam, pts, cam_rot(35, 32), W, H)
        shot("q34")
    if "q34b" in views:
        place_frame(cam, pts, cam_rot(-140, 34), W, H)
        shot("q34back")
    if "game" in views:
        place_game(cam, game_target, game_width, 1280, 720)
        shot("g46game", 1280, 720)
    for o in rul:
        bpy.data.objects.remove(o)
    for o in others:
        o.hide_render = False
    return files


def toon_material_image(name, image, uv="PaintUV"):
    """Same two-step toon as toon_material, base colour from an image through a named UV map."""
    mat = toon_material(name, color=(1, 1, 1))
    nt = mat.node_tree
    rgb = next(n for n in nt.nodes if n.type == "RGB")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Linear"
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = uv
    nt.links.new(uvn.outputs[0], tex.inputs["Vector"])
    for link in list(nt.links):
        if link.from_node == rgb:
            nt.links.new(tex.outputs["Color"], link.to_socket)
    nt.nodes.remove(rgb)
    return mat


def render_painted(out, label, objs, image, game_target=None, game_width=14.0, ruler_at=None,
                   views=("q34", "g46", "game")):
    """Review renders of painted objects: slot 0 painted atlas, slot 1 vertex-colour toon."""
    scene = bpy.context.scene
    rdir = os.path.join(out, "renders")
    os.makedirs(rdir, exist_ok=True)
    W, H = 1600, 1000
    for o in scene.objects:
        if o.type == "MESH" and o not in objs:
            o.hide_render = True
    setup(scene, W, H)
    add_ground(scene)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    mp = toon_material_image("PaintToon", image)
    mv = toon_material("KitToon")
    for o in objs:
        # replace slots in place: materials.clear() would reset every face's material_index to 0
        while len(o.data.materials) < 2:
            o.data.materials.append(None)
        o.data.materials[0] = mp
        o.data.materials[1] = mv
    rul = add_ruler(scene, *ruler_at) if ruler_at else []
    pts = bbox_pts(objs)
    files = []

    def shot(name, w=W, h=H):
        scene.render.resolution_x, scene.render.resolution_y = w, h
        p = os.path.join(rdir, "%s_%s.png" % (label, name))
        scene.render.filepath = p
        bpy.ops.render.render(write_still=True)
        files.append(p)

    if "q34" in views:
        place_frame(cam, pts + bbox_pts(rul), cam_rot(35, 32), W, H)
        shot("painted_q34")
    if "g46" in views:
        place_frame(cam, pts + bbox_pts(rul), cam_rot(0, 46), W, H)
        shot("painted_g46")
    if "game" in views and game_target is not None:
        place_game(cam, game_target, game_width, 1280, 720)
        shot("painted_g46game", 1280, 720)
    print("ER_JSON " + str({"renders": files}))
    return files
