"""Blockout overlay, step 1 (Blender side): render one collection + export the camera projection.

blender -b <scene.blend> --factory-startup -P overlay_render.py -- --collection <name> --out <dir>
        [--label L] [--view top|g46|cam] [--frame x0,y0,x1,y1] [--res 1024] [--color vertex|single]

  --frame   world-ground rectangle in metres (Blender X east, Y north) that must fill the picture;
            default = XY bounding box of the collection + 1 m.
  --view    top = orthographic straight down, north up; image aspect = frame aspect, width = --res px.
            concept = the concept image's own camera (--camjson written by overlay.py from >=4 ground
            correspondences): heights and positions then line up with the concept pixel for pixel.
            g46 = V5 game camera (perspective, pitch 46 deg from the south, vertical FOV 25 deg),
            portrait 2:3, width = --res px, framed so the frame rectangle + the collection fit.
            cam = use the .blend's active camera as is (e.g. one matched to a concept image).
  --color   vertex = show the kitlib "Col" vertex colours; single = flat light grey.

Only objects inside --collection (and its children) are rendered, on a transparent background
(alpha = silhouette).  Workbench engine: about 1 s per view.

Writes <out>/<label>_<view>.png (RGBA) and <out>/<label>_<view>.json:
  {"P": 3x4 matrix world(x,y,z,1) -> pixel (u,v,w), u right, v down, "w","h","frame","view"}
overlay.py reads that json to put the render on top of a concept image.
Prints one JSON line; non-zero exit on failure.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _er_bl as er  # noqa: E402
from stage import GAME_PITCH_DEG, GAME_VFOV_DEG, cam_rotation  # noqa: E402


def parse(argv):
    a = {"label": "blockout", "view": "top", "frame": None, "res": "1024", "color": "vertex", "camjson": None}
    i = 0
    while i < len(argv):
        k = argv[i]
        if k in ("--collection", "--out", "--label", "--view", "--frame", "--res", "--color", "--camjson"):
            a[k[2:]] = argv[i + 1]
            i += 2
        else:
            raise ValueError("unknown arg " + k)
    for k in ("collection", "out"):
        if k not in a:
            raise ValueError("missing --" + k)
    if a["view"] not in ("top", "g46", "cam", "concept"):
        raise ValueError("bad --view " + a["view"])
    a["res"] = int(a["res"])
    if a["frame"]:
        a["frame"] = [float(t) for t in a["frame"].split(",")]
    return a


def collection_objects(col):
    out = list(col.objects)
    for ch in col.children:
        out += collection_objects(ch)
    return out


def world_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        pts += [tuple(mw @ v.co) for v in me.vertices]
        ev.to_mesh_clear()
    return np.array(pts, dtype=float)


def solve_projection(cam, scene, w, h, lo, hi):
    """Fit the 3x4 world->pixel matrix by DLT on samples projected with world_to_camera_view (exact for
    pinhole and orthographic cameras)."""
    rng = np.random.default_rng(0)
    span = np.maximum(hi - lo, 1.0)
    X = lo - 0.25 * span + rng.random((64, 3)) * 1.5 * span
    rows, uv = [], []
    for p in X:
        c = world_to_camera_view(scene, cam, Vector(p))
        if c.z <= 0:
            continue
        u, v = c.x * w, (1.0 - c.y) * h
        P4 = [p[0], p[1], p[2], 1.0]
        rows.append(P4 + [0, 0, 0, 0] + [-u * t for t in P4])
        rows.append([0, 0, 0, 0] + P4 + [-v * t for t in P4])
        uv.append((u, v))
    A = np.array(rows)
    _, _, vt = np.linalg.svd(A)
    P = vt[-1].reshape(3, 4)
    # residual check
    Xh = np.c_[X[: len(uv)], np.ones(len(uv))]
    q = Xh @ P.T
    err = np.abs(q[:, :2] / q[:, 2:3] - np.array(uv)).max()
    return P / np.linalg.norm(P), float(err)


def main(argv):
    a = parse(argv)
    scene = bpy.context.scene
    col = bpy.data.collections.get(a["collection"])
    if col is None:
        raise ValueError("collection not found: " + a["collection"])
    keep = set(collection_objects(col))
    for o in scene.objects:
        if o.type in ("MESH", "CURVE", "SURFACE", "META", "FONT") and o not in keep:
            o.hide_render = True
    verts = world_verts(keep)
    if len(verts) == 0:
        raise ValueError("collection has no mesh vertices")
    lo, hi = verts.min(0), verts.max(0)
    fr = a["frame"] or [lo[0] - 1, lo[1] - 1, hi[0] + 1, hi[1] + 1]
    x0, y0, x1, y1 = fr
    fw, fh = x1 - x0, y1 - y0

    r = scene.render
    r.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "VERTEX" if a["color"] == "vertex" else "SINGLE"
    sh.single_color = (0.8, 0.8, 0.8)
    sh.show_cavity = False
    sh.show_shadows = False
    r.film_transparent = True
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"

    if a["view"] == "cam":
        cam = scene.camera
        if cam is None:
            raise ValueError("--view cam but the scene has no active camera")
        w, h = r.resolution_x * r.resolution_percentage // 100, r.resolution_y * r.resolution_percentage // 100
    else:
        cam = bpy.data.objects.new("OverlayCam", bpy.data.cameras.new("OverlayCam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
        if a["view"] == "top":
            w = a["res"]
            h = max(1, int(round(w * fh / fw)))
            cam.data.type = "ORTHO"
            cam.data.sensor_fit = "HORIZONTAL"
            cam.data.ortho_scale = fw
            cam.matrix_world = Matrix.Translation(((x0 + x1) / 2, (y0 + y1) / 2, hi[2] + 50.0))
            cam.data.clip_start, cam.data.clip_end = 0.1, hi[2] - lo[2] + 200.0
        elif a["view"] == "concept":
            # pinhole camera recovered from the concept image by overlay.py (OpenCV convention: x right,
            # y down, z forward; world->camera X_c = R X + t); principal point = image centre
            cj = json.load(open(a["camjson"], encoding="utf-8"))
            R, t = np.array(cj["R"]), np.array(cj["t"])
            w, h = int(cj["w"]), int(cj["h"])
            C = -R.T @ t
            rot = Matrix((R.T @ np.diag([1.0, -1.0, -1.0])).tolist())
            cam.data.type = "PERSP"
            cam.data.sensor_fit = "VERTICAL"
            cam.data.angle_y = 2.0 * math.atan(h / 2.0 / cj["f"])
            cam.matrix_world = Matrix.Translation(Vector(C.tolist())) @ rot.to_4x4()
            cam.data.clip_start, cam.data.clip_end = 0.1, float(np.linalg.norm(C)) * 4 + 200.0
        else:  # g46
            w = a["res"]
            h = int(round(w * 1.5))
            rot = cam_rotation(0.0, GAME_PITCH_DEG)
            cam.data.type = "PERSP"
            cam.data.sensor_fit = "VERTICAL"
            cam.data.angle_y = math.radians(GAME_VFOV_DEG)
            right, up, back = rot.col[0], rot.col[1], rot.col[2]
            fit = [(x0, y0, 0), (x1, y0, 0), (x0, y1, 0), (x1, y1, 0),
                   (x0, y0, hi[2]), (x1, y0, hi[2]), (x0, y1, hi[2]), (x1, y1, hi[2])]
            fit = np.array(fit, dtype=float)
            c = fit.mean(0)
            R = np.array([right[:], up[:], back[:]])
            loc = (fit - c) @ R.T
            tv = math.tan(math.radians(GAME_VFOV_DEG) / 2.0) / 1.04
            th = tv * w / h
            D = float(np.max(np.maximum(np.abs(loc[:, 0]) / th, np.abs(loc[:, 1]) / tv) + loc[:, 2]))
            cam.matrix_world = Matrix.Translation(Vector(c) + back * D) @ rot.to_4x4()
            cam.data.clip_start, cam.data.clip_end = 0.1, D * 4 + 100.0
        r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100

    bpy.context.view_layer.update()
    P, err = solve_projection(cam, scene, w, h, np.minimum(lo, [x0, y0, 0]), np.maximum(hi, [x1, y1, 1]))
    os.makedirs(a["out"], exist_ok=True)
    stem = os.path.join(a["out"], "%s_%s" % (a["label"], a["view"]))
    r.filepath = stem + ".png"
    bpy.ops.render.render(write_still=True)
    meta = {"P": P.tolist(), "w": w, "h": h, "frame": [x0, y0, x1, y1], "view": a["view"],
            "collection": a["collection"], "bbox": [lo.tolist(), hi.tolist()], "fit_err_px": err}
    with open(stem + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    er.emit({"png": stem + ".png", "json": stem + ".json", "w": w, "h": h, "fit_err_px": round(err, 4),
             "objects": len(keep), "bbox_m": [round(float(t), 2) for t in (hi - lo)]})


if __name__ == "__main__":
    er.run_main(main)
