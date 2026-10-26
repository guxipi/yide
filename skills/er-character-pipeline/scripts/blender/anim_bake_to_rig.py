"""Retarget the Tripo GLB actions onto the MODEL's armature by WORLD-space baking (per bone, per frame), then export a
skeleton-only FBX. anim_fbx2 copied local pose curves verbatim; local values are relative to each bone's rest frame, and
the model rig's rest frames differ from the GLB's (hips by 90 deg about X) -> RootQ came out -90 deg (body lying down).
Here: model bone world rotation = GLB bone world rotation * (rest-to-rest correction), hips position scaled by S.
usage: blender -b --python anim_fbx3.py -- rig_final.blend anims.glb out.fbx"""
import bpy, sys, os
from mathutils import Matrix
a = sys.argv[sys.argv.index("--") + 1:]
RIG, GLB, OUT = a
bpy.ops.wm.open_mainfile(filepath=RIG)
arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in list(bpy.data.objects):
    if o.type == "MESH": bpy.data.objects.remove(o, do_unlink=True)
model_hips_z = (arm.matrix_world @ arm.data.bones["mixamorig:Hips"].head_local).z
before = set(bpy.data.objects); acts_before = set(bpy.data.actions)
bpy.ops.import_scene.gltf(filepath=GLB)
src = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
A = src.matrix_world.copy()
src_hips_z = (A @ src.data.bones["mixamorig:Hips"].head_local).z
S = model_hips_z / src_hips_z
names = {"Boxer": "Rook_Boxer", "Casual": "Rook_Salute", "Relaxed": "Rook_Guard", "Standing,": "Rook_HeadScratch",
         "Stands with": "Rook_ArmsCross", "Stands tall": "Rook_ArmsFold", "Sitting": "Rook_PodSeat"}
exact = {"idle": "Rook_PIdle", "run": "Rook_PRun", "walk": "Rook_PWalk", "standing_relax": "Rook_PStandRelax",
         "cheer": "Rook_PCheer", "frustrated_01": "Rook_PFrustrated", "hit_to_body_01": "Rook_PHit"}
AW = arm.matrix_world.inverted()
bones = [b for b in arm.data.bones if b.name in src.data.bones]  # hierarchy order (parents first)
rest_m = {b.name: b.matrix_local.copy() for b in arm.data.bones}
fix = {}
for b in bones:
    rg = (A @ src.data.bones[b.name].matrix_local).to_quaternion()
    fix[b.name] = rg.inverted() @ (arm.matrix_world @ rest_m[b.name]).to_quaternion()
print("SCALE", round(S, 5), "hips fix", [round(x, 3) for x in fix["mixamorig:Hips"]])
new_actions = [x for x in bpy.data.actions if x not in acts_before]
arm.animation_data_create(); src.animation_data_create()
out = []
for act in new_actions:
    nm = exact.get(act.name) or next((v for k, v in names.items() if act.name.startswith(k)), None)
    if nm is None: continue
    src.animation_data.action = act
    if hasattr(src.animation_data, "action_slot") and act.slots: src.animation_data.action_slot = act.slots[0]
    f0, f1 = [int(round(x)) for x in act.frame_range]
    dst = bpy.data.actions.new(nm); dst.use_fake_user = True
    arm.animation_data.action = dst
    prevq = {}
    for f in range(f0, f1 + 1):
        bpy.context.scene.frame_set(f)
        pose = {}
        for b in bones:
            G = A @ src.pose.bones[b.name].matrix  # world
            q = G.to_quaternion() @ fix[b.name]
            t = G.translation * S if b.name == "mixamorig:Hips" else (arm.matrix_world @ rest_m[b.name]).translation
            M = AW @ (Matrix.Translation(t) @ q.to_matrix().to_4x4())  # armature space
            if b.parent and b.parent.name in pose:
                P = pose[b.parent.name] @ rest_m[b.parent.name].inverted() @ rest_m[b.name]
            else:
                P = rest_m[b.name]
            basis = P.inverted() @ M
            pose[b.name] = M
            pb = arm.pose.bones[b.name]; pb.rotation_mode = "QUATERNION"
            bq = basis.to_quaternion()
            if b.name in prevq and prevq[b.name].dot(bq) < 0: bq.negate()
            prevq[b.name] = bq
            pb.rotation_quaternion = bq
            pb.keyframe_insert("rotation_quaternion", frame=f - f0)
            if b.name == "mixamorig:Hips":
                pb.location = basis.translation
                pb.keyframe_insert("location", frame=f - f0)
    out.append(nm)
    print("BAKED", nm, f1 - f0 + 1)
for o in list(bpy.data.objects):
    if o.name != arm.name: bpy.data.objects.remove(o, do_unlink=True)
for x in list(bpy.data.actions):
    if x.name not in out: bpy.data.actions.remove(x)
arm.animation_data.action = None
for b in arm.pose.bones: b.matrix_basis.identity()
# 10-25 Vesper: bake_anim_simplify_factor must be 0 (the default 1.0 decimates curves -> 1.5 deg delta error, pitfall 124).
# Always keep the dummy Empty: Blender exports mesh and armature as sibling top-level nodes even when the mesh is parented,
# so the model FBX has two top-level nodes in Unity while a skeleton-only FBX has one and gets collapsed (pitfall 109/124).
# Name the armature here exactly like the model FBX armature object (Rook2: "Armature"; Vesper rig_build: "Vesper_Armature").
arm.name = "Armature"
# keep a second top-level object so Unity does not collapse the armature into the file root (the model FBX has
# Armature + mesh as two top-level nodes; the copied avatar expects Hips under a node named Armature with the 270deg X)
dummy = bpy.data.objects.new("Rook2", None); bpy.context.scene.collection.objects.link(dummy)
for o in bpy.data.objects: o.select_set(o == arm or o == dummy)
bpy.context.view_layer.objects.active = arm
bpy.ops.export_scene.fbx(filepath=os.path.abspath(OUT), use_selection=True, object_types={"ARMATURE", "EMPTY"}, apply_unit_scale=True,
                         apply_scale_options="FBX_SCALE_ALL", add_leaf_bones=False, bake_anim=True, bake_anim_use_all_actions=True,
                         bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, bake_anim_step=1.0, axis_forward="-Z", axis_up="Y")
print("WROTE", OUT, sorted(out))
