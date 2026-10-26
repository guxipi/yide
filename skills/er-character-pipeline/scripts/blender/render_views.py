"""Orthographic QA renders of a model, framed exactly like the model sheet (figure = 0.88 of image height).

usage: blender -b --python render_views.py -- <model.glb|fbx|blend> <outdir> [--mode unlit|clay]
       [--views front,left,back,right] [--res 1024x1536] [--prefix render_]
       [--texture PNG]   swap the base-colour image (e.g. compare basecolor_orig vs basecolor_clean)
       [--target x,y,z --scale S]   close-up in normalized units (height 1, feet 0), e.g. the arm undersides:
       --views under,right,back --target 0.2,0,0.55 --scale 0.35 --res 1024x1024 --prefix armL_
  unlit = emission from the base colour (judge the painted texture itself, no lighting)
  clay  = grey clay + one sun (judge geometry: face depth, chin, cheeks, pleats, thin parts)
Prints BBOX / TRIS / IMAGES. The model is NOT modified. View names follow the sheet convention
(left = character's own left side to camera, face points image-left).
Next: py -3 compare_board.py --refs <final four-view dir> --renders <outdir> --out board.png
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args  # noqa: E402


def main():
    a = blender_args(sys.argv)
    if not a or a[0] in ("-h", "--help") or len(a) < 2:
        print(__doc__)
        return
    model, out = a[0], a[1]
    opts = dict(zip(a[2::2], a[3::2]))
    mode = opts.get("--mode", "unlit")
    views = opts.get("--views", "front,left,back,right").split(",")
    rx, ry = (int(v) for v in opts.get("--res", "1024x1536").split("x"))
    prefix = opts.get("--prefix", "render_")
    os.makedirs(out, exist_ok=True)
    _bl.load_any(model)
    meshes = _bl.all_meshes(10)
    ctr, H, mn, mx = _bl.normalize_view_only(meshes)
    print("BBOX", tuple(round(v, 3) for v in mn), tuple(round(v, 3) for v in mx), "height", round(H, 4))
    print("TRIS", sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in meshes), "MESHES", [o.name for o in meshes])
    for i in bpy.data.images:
        if i.size[0]:
            print("IMG", i.name, tuple(i.size))
    arm = _bl.armature()
    fwd = _bl.toe_forward(arm)
    if fwd is not None:
        print("TOE_FORWARD", tuple(round(v, 3) for v in fwd), "(expected ~(0,-1,0))")
    if "--texture" in opts:
        big = max((i for i in bpy.data.images if i.size[0]), key=lambda i: i.size[0] * i.size[1])
        new = bpy.data.images.load(os.path.abspath(opts["--texture"]))
        for m in bpy.data.materials:
            if m.use_nodes:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image == big:
                        n.image = new
        print("TEXTURE_SWAPPED", big.name, "->", new.filepath)
    sc = _bl.setup_scene(rx, ry, bg=(0.25, 0.25, 0.25))
    if mode == "clay":
        _bl.clay_all()
    else:
        _bl.emission_from_basecolor()
    cam = _bl.OrthoCam()
    scale = H / 0.88 * max(1.0, rx / ry)
    target = (ctr.x, ctr.y, ctr.z)
    if "--target" in opts:
        tx, ty, tz = (float(v) for v in opts["--target"].split(","))
        target = (mn.x + (mx.x - mn.x) / 2 + tx * H, ctr.y + ty * H, mn.z + tz * H)
        scale = float(opts.get("--scale", 0.35)) * H
    for v in views:
        p = cam.shot(os.path.join(out, f"{prefix}{v}.png"), target, _bl.DIRS[v], scale, dist=max(mx - mn) * 3)
        print("WROTE", p)


main()
