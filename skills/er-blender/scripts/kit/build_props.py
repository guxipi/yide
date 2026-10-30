"""Build the J01 federal prop kit (16 kit keys) and render one review image per prop + a 46 deg lineup.

blender -b --factory-startup -P build_props.py --python-exit-code 1 -- --out <dir> [--render]
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitlib as K  # noqa: E402
import props as PR  # noqa: E402


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[a.index("--out") + 1]
    render = "--render" in a
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import review
    col = K.ensure_collection("J01_Props")
    made = {}
    for key, (fn, (sx, h, sd)) in PR.PROPS.items():
        p = K.Part("J01P_" + key)
        fn(p, sx, h, sd)
        o = p.finish(col, bevel=0.03, seed=len(made) + 3)
        made[key] = o
    rep = {k: {"tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
               "dims": [round(v, 2) for v in o.dimensions]} for k, o in made.items()}
    if render:
        scene = bpy.context.scene
        review.setup(scene, 900, 700)
        review.add_ground(scene)
        cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
        scene.collection.objects.link(cam)
        scene.camera = cam
        mat = review.toon_material("KitToon")
        rul = review.add_ruler(scene, 0, 0)
        for o in made.values():
            o.data.materials.clear()
            o.data.materials.append(mat)
            o.hide_render = True
        rdir = os.path.join(out, "renders", "props")
        os.makedirs(rdir, exist_ok=True)
        for key, o in made.items():
            o.hide_render = False
            sx = o.dimensions.x
            for r in rul:
                r.location.x = -sx / 2 - 0.9
                r.location.y = -o.dimensions.y / 2 - 0.4
            pts = review.bbox_pts([o] + rul)
            review.place_frame(cam, pts, review.cam_rot(30, 34), 900, 700, margin=1.15)
            scene.render.resolution_x, scene.render.resolution_y = 900, 700
            scene.render.filepath = os.path.join(rdir, "%s.png" % key)
            bpy.ops.render.render(write_still=True)
            o.hide_render = True
        # lineup at V5 46 deg game camera, 4 per row
        keys = list(made)
        x = 0.0
        row_y = 0.0
        for i, key in enumerate(keys):
            o = made[key]
            if i % 4 == 0 and i:
                row_y += 7.5
                x = 0.0
            o.location = (x + o.dimensions.x / 2, row_y, 0)
            x += o.dimensions.x + 2.0
            o.hide_render = False
        for r in rul:
            r.location = (-1.5, 0, r.location.z)
        pts = review.bbox_pts(list(made.values()))
        review.place_frame(cam, pts, review.cam_rot(0, 46), 1600, 1000, margin=1.05)
        scene.render.resolution_x, scene.render.resolution_y = 1600, 1000
        scene.render.filepath = os.path.join(out, "renders", "Props_lineup_g46.png")
        bpy.ops.render.render(write_still=True)
    blend = os.path.join(out, "blend", "J01_props.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("ER_JSON " + json.dumps({"ok": True, "blend": blend, "props": rep}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
