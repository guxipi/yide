"""Dump the textured mesh for texture cleanup: triangles, UVs, normals (normalized space: height 1, feet 0,
x centred, faces -Y) to <outdir>/mesh.npz and the base-colour image to <outdir>/basecolor_orig.png.

usage: blender -b --python tex_extract.py -- <textured.glb> <outdir>
Then: py -3 tex_clean.py --mesh <outdir>/mesh.npz --tex <outdir>/basecolor_orig.png --out <outdir>
NOTE: a cleaned texture belongs to THIS mesh's UVs. A re-generated or re-textured mesh (new Tripo
export) has different UVs - rerun extract + clean on it, never reuse the old cleaned PNG.
"""
import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args  # noqa: E402


def main():
    a = blender_args(sys.argv)
    if len(a) < 2 or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    src, out = a
    os.makedirs(out, exist_ok=True)
    _bl.load_any(src)
    o = _bl.main_mesh()
    d = o.data
    mw = o.matrix_world
    d.calc_loop_triangles()
    tris = d.loop_triangles
    uv = d.uv_layers.active.data
    V = np.array([(mw @ v.co)[:] for v in d.vertices])
    h = V[:, 2].max() - V[:, 2].min()
    V = V / h
    V[:, 2] -= V[:, 2].min()
    V[:, 0] -= (V[:, 0].max() + V[:, 0].min()) / 2
    n = len(tris)
    TI = np.zeros((n, 3), int)
    TU = np.zeros((n, 3, 2))
    TN = np.zeros((n, 3))
    for k, t in enumerate(tris):
        TI[k] = t.vertices
        TU[k] = [uv[l].uv[:] for l in t.loops]
        TN[k] = (mw.to_3x3() @ t.normal).normalized()[:]
    np.savez(os.path.join(out, "mesh.npz"), V=V, TI=TI, TU=TU, TN=TN)
    img = max((i for i in bpy.data.images if i.size[0] > 0), key=lambda i: i.size[0] * i.size[1])
    img.filepath_raw = os.path.join(out, "basecolor_orig.png")
    img.file_format = "PNG"
    img.save()
    print("DONE tris", n, "verts", len(V), "tex", tuple(img.size), "->", out)


main()
