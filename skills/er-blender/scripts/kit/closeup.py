"""Close-up of one region of a prop at a given camera angle (same-region same-angle comparison with the card).
blender -b <blend> --factory-startup -P closeup.py -- --obj <name> --out <png> --box x0,y0,z0,x1,y1,z1 [--az -35 --pitch 38] [--atlas prefix]
box = region in object-local metres to frame."""
import os, sys
import bpy
from mathutils import Vector
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import review as R
a = sys.argv[sys.argv.index("--") + 1:]
o = {a[i][2:]: a[i + 1] for i in range(0, len(a) - 1, 2)}
ob = bpy.data.objects[o["obj"]]
scene = bpy.context.scene
for x in scene.objects:
    if x.type == "MESH":
        x.hide_render = x is not ob
R.setup(scene, 1200, 900)
R.add_ground(scene)
cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
scene.collection.objects.link(cam)
scene.camera = cam
kit = R.toon_material("KitToon")
mp = R.toon_material_image("PT", next(i for i in bpy.data.images if i.name.startswith(o["atlas"]))) if "atlas" in o else kit
while len(ob.data.materials) < 2:
    ob.data.materials.append(None)
ob.data.materials[0] = mp
ob.data.materials[1] = kit
b = [float(v) for v in o["box"].split(",")]
mw = ob.matrix_world
pts = [tuple(mw @ Vector((x, y, z))) for x in (b[0], b[3]) for y in (b[1], b[4]) for z in (b[2], b[5])]
R.place_frame(cam, pts, R.cam_rot(float(o.get("az", -35)), float(o.get("pitch", 38))), 1200, 900, margin=1.05)
scene.render.filepath = o["out"]
bpy.ops.render.render(write_still=True)
