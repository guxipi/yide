"""Face/head geometry gate: clay (and optionally unlit) renders of the head from the angles where a bad
face shows up. This is the check that catches "snake face" (flat face plane, deep eye sockets, V chin)
which unlit texture renders hide.

usage: blender -b --python clay_face.py -- <model> <outdir> [--head-ratio 0.21] [--center-z Z] [--scale S]
       [--also-unlit 1]
Writes clay_{front,left,34,34high,top70,high45,under}.png + clay_body.png (1024 px).
Head centre: Head bone (centre = head.z + 0.41*bone length, frame = 1.25*bone length) when the model is
rigged, otherwise from the bbox and the sheet's head ratio. --center-z/--scale are in normalized units
(height 1.0, feet 0) and override the guess.
Gate (Opus looks, compare with the previous mesh and the design sheet close-up side by side):
  front: round cheeks, U jaw, short round chin; left (profile): nose bridge + lips + round chin visible,
  cheek bulges forward, eye sits on the front plane; top70: face does not taper into a V; under: no
  deep socket holes.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args  # noqa: E402


def main():
    a = blender_args(sys.argv)
    if len(a) < 2 or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    model, out = a[0], a[1]
    o = dict(zip(a[2::2], a[3::2]))
    os.makedirs(out, exist_ok=True)
    _bl.load_any(model)
    meshes = _bl.all_meshes(10)
    ctr, H, mn, mx = _bl.normalize_view_only(meshes)
    arm = _bl.armature()
    hb = arm.data.bones.get("mixamorig:Head") if arm else None
    if "--center-z" in o:
        cz = mn.z + float(o["--center-z"]) * H
        sc = float(o.get("--scale", 0.2)) * H
    elif hb is not None:
        h0 = (arm.matrix_world @ hb.head_local).z
        h1 = (arm.matrix_world @ hb.tail_local).z
        L = h1 - h0
        cz, sc = h0 + 0.41 * L, 1.25 * L
    else:
        hr = float(o.get("--head-ratio", 0.21))
        cz, sc = mn.z + H * (1 - hr * 0.55), H * hr * 0.97
    if "--scale" in o and "--center-z" not in o:
        sc = float(o["--scale"]) * H
    print("HEAD_CENTER_Z", round(cz, 4), "FRAME", round(sc, 4), "H", round(H, 4))
    target = (ctr.x, ctr.y, cz)
    _bl.setup_scene(1024, 1024, bg=(0.3, 0.3, 0.3))
    unlit = o.get("--also-unlit") == "1"
    cam = _bl.OrthoCam()
    if unlit:
        _bl.emission_from_basecolor()
        for v in ("front", "left", "34", "top70"):
            cam.shot(os.path.join(out, f"tex_{v}.png"), target, _bl.DIRS[v], sc * (1.15 if v == "top70" else 1.0))
    _bl.clay_all()
    for v in ("front", "left", "34", "34high", "top70", "high45", "under"):
        cam.shot(os.path.join(out, f"clay_{v}.png"), target, _bl.DIRS[v], sc * (1.15 if v in ("top70", "34high") else 1.0))
    cam.shot(os.path.join(out, "clay_body.png"), (ctr.x, ctr.y, ctr.z), _bl.DIRS["front"], H * 1.05)
    print("WROTE", out)


main()
