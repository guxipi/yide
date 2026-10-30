"""Flat / painted review of ONE small prop: 3/4 like the card, 46 deg game, low side.
blender -b <blend> --factory-startup -P solo_view.py --python-exit-code 1 -- --obj <name> --out <png prefix> [--atlas <image name prefix>]"""
import os, sys
import bpy
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review as R
a = sys.argv[sys.argv.index("--") + 1:]
name = a[a.index("--obj") + 1]
out = a[a.index("--out") + 1]
atl = a[a.index("--atlas") + 1] if "--atlas" in a else None
scene = bpy.context.scene
ob = bpy.data.objects[name]
for o in scene.objects:
    if o.type == "MESH":
        o.hide_render = o is not ob
R.setup(scene, 1200, 900)
R.add_ground(scene)
rul = R.add_ruler(scene, ob.location.x - 1.4, ob.location.y + 0.9)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
kit = R.toon_material("KitToon")
mp = R.toon_material_image("PaintToon", next(i for i in bpy.data.images if i.name.startswith(atl))) if atl else kit
while len(ob.data.materials) < 2:
    ob.data.materials.append(None)
ob.data.materials[0] = mp
ob.data.materials[1] = kit
bpy.context.view_layer.update()
pts = R.bbox_pts([ob])
for tag, az, pitch in (("card", -30, 38), ("g46", 0, 46), ("side", 80, 20)):
    R.place_frame(cam, pts, R.cam_rot(az, pitch), 1200, 900, margin=1.25)
    scene.render.filepath = "%s_%s.png" % (out, tag)
    bpy.ops.render.render(write_still=True)
