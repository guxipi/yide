"""Build the three J01 station hulls from the broken-hull kit and render reviews.

blender -b --factory-startup -P build_hulls.py --python-exit-code 1 -- --out <ArtWork dir> [--render]

Sizes from j01_poi_components.csv (X length, Y height, Z depth):
  NC-C01 破顶联络母舱   28 x 8   x 11.5   overturned (legs stick out north), equipment band north
  MB-C01 干样本走廊母舱 24 x 6.5 x 11.5   equipment band south
  SWC-C01 分选样本母舱  27 x 7.5 x 12     equipment band north
"""
import json
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull as HU  # noqa: E402
import kitlib as K  # noqa: E402

HULLS = [
    ("NC_HullN", 28.0, 11.5, 8.0, dict(seed=7, equip_side=1, overturned=True)),
    ("MB_HullM", 24.0, 11.5, 6.5, dict(seed=13, equip_side=-1, south_base=1.1, south_amp=0.4)),
    ("SWC_HullW", 27.0, 12.0, 7.5, dict(seed=21, equip_side=1)),
]


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[a.index("--out") + 1]
    render = "--render" in a
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import review
    report = {}
    built = []
    for name, L, D, H, kw in HULLS:
        col = K.ensure_collection(name)
        objs, info = HU.build_hull(name, L, D, H, col, **kw)
        tris = {o.name: sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs}
        report[name] = {"tris": tris, **info}
        if render:
            review.render_simple(out, name, objs, ruler_at=(-L / 2 - 2.0, -D / 2 - 1.5, ),
                                 game_target=(-L / 2 + 5.0, -D / 2 + 2.0, 0.0))
        built.append((objs, D))
    # lay the hulls out side by side for the saved blend
    off = 0.0
    for objs, D in built:
        for o in objs:
            o.location.y += off
        off += D + 12.0
    blend = os.path.join(out, "blend", "J01_hulls.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("ER_JSON " + json.dumps({"ok": True, "blend": blend, "hulls": report}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
