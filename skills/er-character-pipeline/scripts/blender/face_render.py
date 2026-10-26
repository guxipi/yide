"""Render the base face image the expressions are painted on, and write the projection every later step
re-uses (face_projection.json) - so the atlas, the UVs and the QA renders can never disagree.

usage: blender -b --python face_render.py -- --config char.json [--rig RIG.blend] [--out DIR]
       [--center-z Z] [--scale S]
Default rig = {out_dir}/{rig_dir}/{slug}_rig.blend, out = {out_dir}/{face_dir}.
Writes face_front.png (1024, unlit texture, grey bg), face_34.png, face_calib.png (front + crop rectangle +
feature bands drawn as coloured lines) and face_projection.json.
Projection (normalized rig space): camera looks along +Y at (0, *, center_z), ortho_scale S;
  px = x/S*1024 + 512 ; py = 512 - (z - center_z)/S*1024 ; crop = [128,352,896,928] (768x576 -> 512x384 cell)
Default centre/scale from the Head bone: center_z = head + 0.41*L, S = 0.99*L (Wren: 0.8826 / 0.163).
GATE: open face_calib.png - both eyebrows, both eyes, the mouth and the chin must be INSIDE the white crop box,
eyes inside the green band, mouth inside the blue band. Otherwise re-run with --center-z/--scale.
Regenerate this (and every expression) whenever the face mesh changes - expressions painted on an old face
render land on the wrong geometry.
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args, load_cfg, out_path  # noqa: E402

CROP = [128, 352, 896, 928]
BANDS = {"eyes_brows": [205, 365, 819, 675], "mouth": [300, 590, 724, 805]}


def main():
    a = blender_args(sys.argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    o = dict(zip(a[0::2], a[1::2]))
    cfg = load_cfg(o.get("--config"))
    rig = o.get("--rig") or out_path(cfg, cfg["files"].get("rig_dir", "rig"), f"{cfg['slug']}_rig.blend")
    out = o.get("--out") or out_path(cfg, cfg["files"].get("face_dir", "face"))
    os.makedirs(out, exist_ok=True)
    _bl.load_any(rig)
    arm = _bl.armature()
    fc = cfg.get("face", {})
    if arm is not None and "mixamorig:Head" in arm.data.bones:
        hb = arm.data.bones["mixamorig:Head"]
        h0 = (arm.matrix_world @ hb.head_local).z
        L = (arm.matrix_world @ hb.tail_local).z - h0
        cz = float(o.get("--center-z") or fc.get("center_z") or (h0 + 0.41 * L))
        S = float(o.get("--scale") or fc.get("ortho_scale") or (0.99 * L))
    else:
        # unrigged head mesh (separate-head route, 10-24 Vesper): no Head bone to derive the framing from,
        # so --center-z/--scale (or cfg face.center_z/ortho_scale) are mandatory. Coordinates are the blend's own.
        cz = o.get("--center-z") or fc.get("center_z")
        S = o.get("--scale") or fc.get("ortho_scale")
        if cz is None or S is None:
            raise SystemExit("no armature with mixamorig:Head: pass --center-z and --scale (blend coordinates)")
        cz, S = float(cz), float(S)
        L = 0.0
    proj = {"rig": rig, "center_z": cz, "ortho_scale": S, "res": 1024, "crop": CROP, "grid": [4, 3], "cell": [512, 384],
            "feature_bands": BANDS, "camera": "looks along +Y from -Y, ortho",
            "formula": "px = x/S*1024+512 ; py = 512-(z-center_z)/S*1024"}
    _bl.setup_scene(1024, 1024, bg=(0.25, 0.25, 0.25))
    _bl.emission_from_basecolor()
    cam = _bl.OrthoCam()
    cam.shot(os.path.join(out, "face_front.png"), (0, 0, cz), (0, -1, 0), S)
    cam.shot(os.path.join(out, "face_34.png"), (0, 0, cz), (-0.6, -1, 0), S * 1.125)
    with open(os.path.join(out, "face_projection.json"), "w", encoding="utf-8") as f:
        json.dump(proj, f, indent=1)
    # calibration overlay drawn in Blender's own image API (no PIL inside Blender)
    img = bpy.data.images.load(os.path.join(out, "face_front.png"))
    W, H = img.size
    px = list(img.pixels)

    def rect(box, col):
        x0, y0, x1, y1 = box
        for x in range(x0, x1):
            for y in (y0, y1 - 1):
                k = ((H - 1 - y) * W + x) * 4
                px[k:k + 3] = col
        for y in range(y0, y1):
            for x in (x0, x1 - 1):
                k = ((H - 1 - y) * W + x) * 4
                px[k:k + 3] = col
    rect(CROP, [1, 1, 1])
    rect(BANDS["eyes_brows"], [0, 1, 0])
    rect(BANDS["mouth"], [0, 0.4, 1])
    img.pixels = px
    img.filepath_raw = os.path.join(out, "face_calib.png")
    img.file_format = "PNG"
    img.save()
    print("FACE_PROJECTION", json.dumps({"center_z": round(cz, 4), "ortho_scale": round(S, 4), "head_bone_len": round(L, 4)}))
    print("WROTE", out)


main()
