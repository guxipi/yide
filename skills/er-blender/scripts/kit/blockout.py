"""Blockout from a parts list (the "拆解单"), step 2 of the 15-minute POI round.

blender -b --factory-startup -P blockout.py -- --parts parts.json --out scene.blend [--collection NAME]

parts.json:
{
  "poi": "LH", "collection": "LH_Blockout",
  "units": "metres, local: x east, y north, z up (Blender axes)",
  "parts": [
    {"id": 1, "name": "台基", "why": "灯塔和搜点站的平台", "cell": "C5-F7", "count": 1,
     "shape": "box", "at": [0, 0], "size": [9, 9, 0.3], "z0": 0, "color": "#C9C4BE"},
    {"id": 2, "name": "灯塔筒", "shape": "cyl", "at": [0, 0], "size": [2.4, 2.4, 5.5], "z0": 0.3},
    {"id": 7, "name": "系缆桩", "shape": "cyl", "at": [[4, -3], [6, -1], [7, 1]], "size": [0.4, 0.4, 0.6]},
    {"id": 9, "name": "门", "shape": "box", "at": [0, 1.2], "size": [0.9, 0.2, 2.0], "z0": 0.3, "rot": 0}
  ],
  "absent": ["台基四周没有栏杆", "塔身没有第二扇门"]
}
  shape  box | cyl (vertical cylinder; size = [dx, dy, height]) | slab (alias of box)
  at     [x, y] centre of the footprint, or a list of centres for repeated parts
  z0     bottom height (default 0); rot = yaw in degrees about Z (default 0); tilt = [rx, ry] degrees
  color  optional sRGB hex for the vertex colour (default light grey); every part gets its own object
         named "<id>_<name>" so overlay boards and Unity can address it.
"why", "cell", "count" and "absent" are not used for geometry: they are the parts list a reviewer
reads before the blockout is trusted (see references/07 "15 分钟一轮").
Prints one JSON line with object count and overall bbox.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blender"))
import _er_bl as er  # noqa: E402


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def parse(argv):
    a = {"collection": None}
    i = 0
    while i < len(argv):
        k = argv[i]
        if k in ("--parts", "--out", "--collection"):
            a[k[2:]] = argv[i + 1]
            i += 2
        else:
            raise ValueError("unknown arg " + k)
    for k in ("parts", "out"):
        if k not in a:
            raise ValueError("missing --" + k)
    return a


def make_part(name, shape, size, col_lin):
    bm = bmesh.new()
    sx, sy, sz = size
    if shape in ("box", "slab"):
        bmesh.ops.create_cube(bm, size=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    elif shape == "cyl":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.5, depth=1.0)
        bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    else:
        raise ValueError("bad shape " + shape)
    bmesh.ops.translate(bm, vec=(0, 0, sz / 2.0), verts=bm.verts)  # origin at the bottom
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    attr = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    for d in attr.data:
        d.color = (col_lin[0], col_lin[1], col_lin[2], 1.0)
    me.color_attributes.active_color = attr
    for p in me.polygons:
        p.use_smooth = shape == "cyl"
    return me


def main(argv):
    a = parse(argv)
    spec = json.load(open(a["parts"], encoding="utf-8"))
    er.reset_scene()
    cname = a["collection"] or spec.get("collection") or (spec.get("poi", "POI") + "_Blockout")
    col = bpy.data.collections.new(cname)
    bpy.context.scene.collection.children.link(col)
    n = 0
    lo = [1e9] * 3
    hi = [-1e9] * 3
    for p in spec["parts"]:
        ats = p["at"]
        if ats and not isinstance(ats[0], (list, tuple)):
            ats = [ats]
        c = hexlin(p.get("color", "#D8D8D8"))
        for k, at in enumerate(ats):
            name = "%s_%s%s" % (p["id"], p["name"], "_%d" % (k + 1) if len(ats) > 1 else "")
            me = make_part(name, p.get("shape", "box"), p["size"], c)
            ob = bpy.data.objects.new(name, me)
            col.objects.link(ob)
            tilt = p.get("tilt", [0, 0])
            ob.matrix_world = (Matrix.Translation((at[0], at[1], p.get("z0", 0.0)))
                               @ Euler((math.radians(tilt[0]), math.radians(tilt[1]),
                                        math.radians(p.get("rot", 0.0)))).to_matrix().to_4x4())
            bpy.context.view_layer.update()
            for v in ob.bound_box:
                w = ob.matrix_world @ __import__("mathutils").Vector(v)
                for i in range(3):
                    lo[i] = min(lo[i], w[i])
                    hi[i] = max(hi[i], w[i])
            n += 1
    os.makedirs(os.path.dirname(os.path.abspath(a["out"])), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a["out"]))
    er.emit({"blend": os.path.abspath(a["out"]), "collection": cname, "objects": n,
             "bbox_lo": [round(t, 2) for t in lo], "bbox_hi": [round(t, 2) for t in hi],
             "absent": spec.get("absent", [])})


if __name__ == "__main__":
    er.run_main(main)
