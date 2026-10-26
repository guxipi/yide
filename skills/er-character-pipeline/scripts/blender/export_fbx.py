"""Re-export a rig .blend to a Unity FBX the one correct way (rest pose, FBX_SCALE_ALL, -Z forward / Y up,
no leaf bones, textures referenced next to the FBX) and verify the round trip.

usage: blender -b --python export_fbx.py -- <rig.blend> <out.fbx> [--deform-only 0|1]
After export the FBX is re-imported into an empty scene and checked:
  armature object scale == 1 (else Unity gets a 100x root and hand-mounted guns become 100x),
  height ~= 1.0, bone count, material names (Unity remap keys) printed.
Prints FBX_CHECK PASS|FAIL.
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
    if len(a) < 2 or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    src, dst = a[0], a[1]
    o = dict(zip(a[2::2], a[3::2]))
    _bl.load_any(src)
    _bl.export_fbx(dst, deform_only=o.get("--deform-only", "0") == "1")
    _bl.reset()
    bpy.ops.import_scene.fbx(filepath=os.path.abspath(dst))
    arm = _bl.armature()
    ms = _bl.all_meshes(10)
    _, H, _, _ = _bl.normalize_view_only(ms)
    sc = tuple(round(x, 4) for x in arm.scale) if arm else None
    mats = sorted({m.name for ob in ms for m in ob.data.materials if m})
    ok = arm is not None and all(abs(x - 1) < 1e-3 for x in arm.scale) and abs(H - 1.0) < 0.02
    print("FBX", dst)
    print("ARMATURE_SCALE", sc, "BONES", len(arm.data.bones) if arm else 0, "HEIGHT", round(H, 4))
    print("MATERIALS", mats, "(these names are the Unity importer remap keys)")
    print("FBX_CHECK", "PASS" if ok else "FAIL")


main()
