"""ER prop review stage: fixed cameras, LabLit-preview / white / clay renders.

blender -b --factory-startup -P stage.py -- --in <glb|fbx> --out <dir> --label <name>
        [--mode lablit|white|clay] [--tex <basecolor.png>] [--yaw <deg>] [--res 640x480]

Frame: model is auto-turned so its longest horizontal axis lies on world X, then --yaw is added.
Views (camera azimuth 0 = camera on -Y looking +Y):
  g46   V5 game camera: perspective, pitch 46 deg down, vertical FOV 25 deg, azimuth 0
  top   orthographic straight down
  front orthographic from -Y (for a gun this is the side profile)
  side  orthographic from +X
  q34   perspective FOV 25, azimuth 45, pitch 25
Plus <label>_<mode>_g46_128.png: the g46 render scaled to 128 px wide ("game size").
Every render is composited over mid grey (sRGB 0.5); object masks are written to <out>/masks/.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _er_bl as er  # noqa: E402

GAME_PITCH_DEG = 46.0   # V5 gameplay camera pitch
GAME_VFOV_DEG = 25.0    # V5 gameplay camera vertical FOV
Q34_AZ_DEG, Q34_PITCH_DEG = 45.0, 25.0
FRAME_MARGIN = 1.08     # 8% breathing room around the tight vertex framing
BG_GREY = 0.5           # display-space background value
SMALL_W = 128           # "game size" thumbnail width
EEVEE_SAMPLES = 32

VIEWS = [
    # name, persp?, azimuth, pitch
    ("g46", True, 0.0, GAME_PITCH_DEG),
    ("top", False, 0.0, 90.0),
    ("front", False, 0.0, 0.0),
    ("side", False, 90.0, 0.0),
    ("q34", True, Q34_AZ_DEG, Q34_PITCH_DEG),
]


def parse(argv):
    a = {"mode": "lablit", "tex": None, "yaw": 0.0, "res": "640x480"}
    i = 0
    while i < len(argv):
        k = argv[i]
        if k in ("--in", "--out", "--label", "--mode", "--tex", "--yaw", "--res"):
            a[k[2:]] = argv[i + 1]
            i += 2
        else:
            raise ValueError("unknown arg " + k)
    for k in ("in", "out", "label"):
        if k not in a:
            raise ValueError("missing --" + k)
    if a["mode"] not in ("lablit", "white", "clay"):
        raise ValueError("bad --mode " + a["mode"])
    a["yaw"] = float(a["yaw"])
    w, h = a["res"].lower().split("x")
    a["w"], a["h"] = int(w), int(h)
    return a


def cam_rotation(azimuth_deg, pitch_deg):
    if pitch_deg >= 89.999:
        return Euler((0.0, 0.0, 0.0)).to_matrix()  # straight down, X right, Y up
    az, el = math.radians(azimuth_deg), math.radians(pitch_deg)
    to_cam = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
    return (-to_cam).to_track_quat("-Z", "Y").to_matrix()


def place_camera(cam, verts, persp, rot, w, h):
    right, up, back = rot.col[0], rot.col[1], rot.col[2]
    R = np.array([right[:], up[:], back[:]])
    lo, hi = verts.min(0), verts.max(0)
    c = (lo + hi) / 2.0
    local = (verts - c) @ R.T  # x, y, z(toward camera)
    cd = cam.data
    aspect = w / h
    if persp:
        cd.type = "PERSP"
        cd.sensor_fit = "VERTICAL"
        cd.angle_y = math.radians(GAME_VFOV_DEG)
        tv = math.tan(math.radians(GAME_VFOV_DEG) / 2.0) / FRAME_MARGIN
        th = tv * aspect
        D = float(np.max(np.maximum(np.abs(local[:, 0]) / th, np.abs(local[:, 1]) / tv) + local[:, 2]))
        pos = Vector(c) + back * D
    else:
        cd.type = "ORTHO"
        cd.sensor_fit = "AUTO"
        x0, x1 = local[:, 0].min(), local[:, 0].max()
        y0, y1 = local[:, 1].min(), local[:, 1].max()
        sx, sy = (x1 - x0), (y1 - y0)
        span = max(sx, sy * aspect) if aspect >= 1 else max(sx / aspect, sy)
        cd.ortho_scale = float(span * FRAME_MARGIN)
        depth = float(local[:, 2].max() - local[:, 2].min())
        pos = Vector(c) + right * float((x0 + x1) / 2) + up * float((y0 + y1) / 2) + back * (depth + 1.0)
    span_all = float(np.linalg.norm(hi - lo))
    cd.clip_start = span_all * 0.001
    cd.clip_end = span_all * 100.0 + 100.0
    cam.matrix_world = Matrix.Translation(pos) @ rot.to_4x4()


def setup_scene(scene, mode, w, h):
    engine = er.set_engine(scene, ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"])
    if engine.startswith("BLENDER_EEVEE"):
        scene.eevee.taa_render_samples = EEVEE_SAMPLES
    else:
        scene.cycles.samples = 32
    r = scene.render
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "8"
    vs = scene.view_settings
    vs.view_transform = "Standard"
    vs.look = "None"
    vs.exposure = 0.0
    vs.gamma = 1.0
    world = bpy.data.worlds.new("StageWorld")
    scene.world = world
    if world.node_tree is None:
        world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.214, 0.214, 0.214, 1.0)  # linear of sRGB 0.5
    bg.inputs["Strength"].default_value = 1.0 if mode == "clay" else 0.0
    if mode == "clay":
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 3.0
        sun.rotation_euler = er.SUN_DIR.to_track_quat("Z", "Y").to_euler()
        scene.collection.objects.link(sun)
    return engine


def composite(tmp_png, out_png, mask_png, small_png=None):
    img = bpy.data.images.load(tmp_png)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    a = px[..., 3:4]
    rgb = px[..., :3] * a + BG_GREY * (1.0 - a)
    out = np.concatenate([rgb, np.ones_like(a)], axis=2)
    o = bpy.data.images.new("comp", w, h, alpha=False)
    o.pixels.foreach_set(out.ravel())
    er.save_image_png(o, out_png)
    m = (a > 0.5).astype(np.float32)
    mimg = bpy.data.images.new("mask", w, h, alpha=False)
    mimg.pixels.foreach_set(np.concatenate([m, m, m, np.ones_like(a)], axis=2).ravel())
    er.save_image_png(mimg, mask_png)
    if small_png:
        sh = max(1, round(h * SMALL_W / w))
        o.scale(SMALL_W, sh)
        er.save_image_png(o, small_png)
    for im in (img, o, mimg):
        bpy.data.images.remove(im)


def main(argv):
    a = parse(argv)
    out = os.path.abspath(a["out"])
    os.makedirs(os.path.join(out, "masks"), exist_ok=True)
    er.reset_scene()
    scene = bpy.context.scene
    obj, rep = er.import_any(a["in"])
    info = er.inspect(obj)
    lo, hi = er.bbox(obj.data)
    d = hi - lo
    turn = 90.0 if d[1] > d[0] else 0.0
    yaw = turn + a["yaw"]
    if yaw:
        obj.data.transform(Matrix.Rotation(math.radians(yaw), 4, "Z"))
        er.origin_bottom_center(obj)
    if a["mode"] == "lablit":
        mats = er.make_lablit_preview(obj, base_image=a["tex"])
    elif a["mode"] == "white":
        mats = er.make_lablit_preview(obj, base_color=(1.0, 1.0, 1.0))
    else:
        mats = er.make_clay(obj)
    engine = setup_scene(scene, a["mode"], a["w"], a["h"])
    cam = bpy.data.objects.new("StageCam", bpy.data.cameras.new("StageCam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    verts = er.mesh_coords(obj.data)
    files = {}
    tmp = os.path.join(out, "masks", "_tmp_render.png")
    for name, persp, az, pitch in VIEWS:
        place_camera(cam, verts, persp, cam_rotation(az, pitch), a["w"], a["h"])
        scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        base = "%s_%s_%s" % (a["label"], a["mode"], name)
        png = os.path.join(out, base + ".png")
        small = os.path.join(out, base + "_128.png") if name == "g46" else None
        composite(tmp, png, os.path.join(out, "masks", base + "_mask.png"), small)
        files[name] = png
        if small:
            files["g46_128"] = small
    if os.path.exists(tmp):
        os.remove(tmp)
    er.emit({"ok": True, "label": a["label"], "mode": a["mode"], "engine": engine, "yaw_applied": yaw,
             "import": rep, "inspect": info, "materials": mats, "files": files})


if __name__ == "__main__":
    er.run_main(main)
