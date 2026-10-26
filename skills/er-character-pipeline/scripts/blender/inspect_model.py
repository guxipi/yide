"""Print what a Tripo download actually contains (use it on EVERY downloaded file before trusting it -
a late-landing older export once looked like the new rigged file but had no bones).

usage: blender -b --python inspect_model.py -- <file.glb|fbx|blend>
Prints: meshes (polys, verts, materials), armature (bone count, first names, non-mixamo bones), images
(size), actions (name, frame range) and the toe-forward direction. Ends with SUMMARY rigged=<bool>
anims=<n> tris=<n> tex=<WxH>.
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
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    _bl.load_any(a[0])
    tris = 0
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            t = sum(len(p.vertices) - 2 for p in o.data.polygons)
            tris += t
            print("MESH", o.name, "tris", t, "verts", len(o.data.vertices), "groups", len(o.vertex_groups),
                  "mats", [m.name for m in o.data.materials if m])
    arm = _bl.armature()
    if arm:
        names = [b.name for b in arm.data.bones]
        print("ARMATURE", arm.name, "bones", len(names), "scale", tuple(round(x, 4) for x in arm.scale))
        print("  first", names[:8])
        print("  non-mixamo", [n for n in names if not n.startswith("mixamorig")])
        f = _bl.toe_forward(arm)
        print("  toe_forward", None if f is None else tuple(round(x, 3) for x in f))
    tex = None
    for i in bpy.data.images:
        if i.size[0]:
            print("IMG", i.name, tuple(i.size))
            tex = tex or tuple(i.size)
    acts = [(x.name, tuple(round(v) for v in x.frame_range)) for x in bpy.data.actions]
    for n, r in acts:
        print("ACTION", n, r)
    print(f"SUMMARY rigged={arm is not None} anims={len(acts)} tris={tris} tex={tex}")


main()
