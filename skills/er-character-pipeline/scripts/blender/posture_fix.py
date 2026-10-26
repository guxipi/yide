"""Fix a hunched / short-necked / long-armed Tripo body by posing the rig and baking that pose as the new rest pose
(10-08 Rook: head pushed forward of the chest, sloping shoulders hiding the neck, forearms ~7% of height too long).
Mesh, UVs, weights and face material are kept; only vertex positions and bone rest positions change.
usage: blender -b --python posture_fix.py -- <in.blend> <out.blend> [--head-back DEG] [--neck-back DEG]
       [--neck-len S] [--shoulder-up DEG] [--forearm S] [--hand S] [--upperarm S] [--chest-up DEG] [--shoulder-out D]
  --shoulder-out D: move each upper-arm joint D (height units) straight outward = wider shoulders, arm length unchanged
    (10-08 Rook: the bigger 5.5-heads head made the shoulders read narrow, 1.72 head widths vs the handbook's 1.96)
  rotations are about the world X axis (character faces -Y; positive = tip the top backward) or, for shoulders,
  about the world Y axis (positive = raise the arm end); S = scale of the bone along its length (1 = unchanged).
Prints bone heights before/after. Then re-run rig_audit / deform tests / face QA on the output, and export_fbx."""
import sys, math, bpy
from mathutils import Matrix, Quaternion, Vector
a = sys.argv[sys.argv.index('--') + 1:]
src, dst = a[0], a[1]
def opt(k, d): return float(a[a.index(k) + 1]) if k in a else d
P = dict(head=opt('--head-back', 0), neck=opt('--neck-back', 0), necklen=opt('--neck-len', 1), sh=opt('--shoulder-up', 0),
         fore=opt('--forearm', 1), hand=opt('--hand', 1), upper=opt('--upperarm', 1), chest=opt('--chest-up', 0),
         out=opt('--shoulder-out', 0))
bpy.ops.wm.open_mainfile(filepath=src)
arm = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]
meshes = [o for o in bpy.data.objects if o.type == 'MESH' and any(m.type == 'ARMATURE' for m in o.modifiers)]
def J(n): return arm.matrix_world @ arm.data.bones['mixamorig:' + n].head_local
def report(tag):
    s = ' '.join(f"{n}={J(n).z:.3f}/{J(n).y:+.3f}" for n in ['Spine2', 'Neck', 'Head', 'LeftArm', 'LeftHand'])
    tip = arm.matrix_world @ arm.data.bones['mixamorig:HeadTop_End'].head_local
    print(f'{tag}: {s} HeadTop={tip.z:.3f}/{tip.y:+.3f}')
report('BEFORE')
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='POSE')
for b in arm.pose.bones: b.matrix_basis = Matrix.Identity(4)
def rot(n, axis, deg):
    if not deg or ('mixamorig:' + n) not in arm.pose.bones: return
    b = arm.pose.bones['mixamorig:' + n]; rq = b.bone.matrix_local.to_quaternion()
    b.rotation_mode = 'QUATERNION'; b.rotation_quaternion = (rq.inverted() @ Quaternion(axis, math.radians(deg)) @ rq) @ b.rotation_quaternion
def scl(n, s):
    if s == 1 or ('mixamorig:' + n) not in arm.pose.bones: return
    b = arm.pose.bones['mixamorig:' + n]; b.scale = Vector((1, s, 1))  # bone Y = along the bone
X = Vector((1, 0, 0))
# a +angle about +X tips +Z toward -Y (the face side) = forward; flip so positive arguments lean BACK
back = lambda d: -d
rot('Spine2', X, back(P['chest']))          # open the chest (top backward)
rot('Neck', X, back(P['neck'])); rot('Head', X, back(P['head']))
scl('Neck', P['necklen'])
# pose-bone scale is inherited by children: undo it on the Head so only the neck gets longer
if P['necklen'] != 1: arm.pose.bones['mixamorig:Head'].scale = Vector((1 / P['necklen'], 1 / P['necklen'], 1 / P['necklen']))
for side, sg in (('Left', 1), ('Right', -1)):
    rot(side + 'Shoulder', Vector((0, 1, 0)), -sg * P['sh'])
    # chain scales multiply down the arm: compensate so each factor applies to its own segment only
    if P['out']:
        b = arm.pose.bones['mixamorig:' + side + 'Arm']
        if b.bone.use_connect:
            raise SystemExit(side + 'Arm is connected to its shoulder bone: --shoulder-out cannot move it')
        b.location = b.bone.matrix_local.to_3x3().inverted() @ Vector((sg * P['out'], 0, 0))
    scl(side + 'Arm', P['upper'])
    scl(side + 'ForeArm', P['fore'] / P['upper'])
    scl(side + 'Hand', P['hand'] / P['fore'])
    # fingers keep their size
    for b in arm.pose.bones:
        if b.parent and b.parent.name == 'mixamorig:' + side + 'Hand': b.scale = Vector((1 / P['hand'],) * 3)
bpy.context.view_layer.update()
# bake the pose into the meshes, then make it the rest pose
bpy.ops.object.mode_set(mode='OBJECT')
for o in meshes:
    bpy.context.view_layer.objects.active = o
    mod = next(m for m in o.modifiers if m.type == 'ARMATURE'); name = mod.name
    bpy.ops.object.modifier_copy(modifier=name)
    bpy.ops.object.modifier_apply(modifier=name)  # applies the posed copy order-safe: original applied, copy remains
    copy = next(m for m in o.modifiers if m.type == 'ARMATURE'); copy.name = name
bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='POSE')
bpy.ops.pose.armature_apply(selected=False)
# scaled bones: armature_apply bakes scale into bone length; child bones keep their heads at the baked positions
bpy.ops.object.mode_set(mode='OBJECT')
# re-ground: feet back on z=0, height back to 1.0 is NOT forced (a longer neck may make him slightly taller)
zs = [ (o.matrix_world @ v.co).z for o in meshes for v in o.data.vertices ]
dz = -min(zs)
if abs(dz) > 1e-5:
    for o in meshes + [arm]: o.location.z += dz
report('AFTER')
print('HEIGHT', round(max(zs) - min(zs), 4))
bpy.ops.wm.save_as_mainfile(filepath=dst)
print('POSTURE_FIX_SAVED', dst)
