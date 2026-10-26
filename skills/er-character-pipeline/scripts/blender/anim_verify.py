"""Verify a baked animation FBX against the source GLB: for each action, sample frames, compare every shared bone's
world-space direction (head->tail) and the hips world position (scaled). Prints max/mean angle error per action.
usage: blender -b --python anim_verify.py -- anims.glb baked.fbx"""
import bpy, sys, math
a = sys.argv[sys.argv.index("--") + 1:]
GLB, FBX = a
bpy.ops.wm.read_factory_settings(use_empty=True)
before = set(bpy.data.objects); acts0 = set(bpy.data.actions)
bpy.ops.import_scene.gltf(filepath=GLB)
src = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
src_acts = [x for x in bpy.data.actions if x not in acts0]
before = set(bpy.data.objects); acts1 = set(bpy.data.actions)
bpy.ops.import_scene.fbx(filepath=FBX)
dst = next(o for o in bpy.data.objects if o not in before and o.type == "ARMATURE")
dst_acts = [x for x in bpy.data.actions if x not in acts1]
names = {"Boxer": "Rook_Boxer", "Casual": "Rook_Salute", "Relaxed": "Rook_Guard", "Standing,": "Rook_HeadScratch",
         "Stands with": "Rook_ArmsCross", "Stands tall": "Rook_ArmsFold", "Sitting": "Rook_PodSeat"}
exact = {"idle": "Rook_PIdle", "run": "Rook_PRun", "walk": "Rook_PWalk", "standing_relax": "Rook_PStandRelax",
         "cheer": "Rook_PCheer", "frustrated_01": "Rook_PFrustrated", "hit_to_body_01": "Rook_PHit"}
def target_name(n):
    return exact.get(n) or next((v for k, v in names.items() if n.startswith(k)), None)
src.animation_data_create(); dst.animation_data_create()
def set_act(o, act):
    o.animation_data.action = act
    if hasattr(o.animation_data, "action_slot") and act.slots: o.animation_data.action_slot = act.slots[0]
bones = [b.name for b in src.data.bones if b.name in dst.data.bones]
sh = (src.matrix_world @ src.data.bones["mixamorig:Hips"].head_local).z
dh = (dst.matrix_world @ dst.data.bones["mixamorig:Hips"].head_local).z
S = dh / sh
worst = 0.0
worst_d = 0.0
# delta mode (10-25): compare world-space rotation relative to each armature's OWN rest (pose_world @ rest_world^-1).
# After rig_build re-aims bones (straight spine, toe ball, mirror) the head->tail direction differs by a constant angle
# even though the baked motion is identical; the delta is what the mesh sees. VERIFY_DELTA is the gate, boneDir informational.
rs = {b: (src.matrix_world @ src.data.bones[b].matrix_local).to_quaternion().inverted() for b in bones}
rd = {b: (dst.matrix_world @ dst.data.bones[b].matrix_local).to_quaternion().inverted() for b in bones}
for act in src_acts:
    nm = target_name(act.name)
    dact = next((x for x in dst_acts if x.name.endswith(nm)), None) if nm else None
    if dact is None: print("SKIP", act.name, "->", nm); continue
    set_act(src, act); set_act(dst, dact)
    f0, f1 = [int(round(x)) for x in act.frame_range]
    errs = []; perr = 0.0; derrs = []; dbone = {}
    for f in range(f0, f1 + 1, max(1, (f1 - f0) // 12)):
        bpy.context.scene.frame_set(f)  # source at frame f
        VS = {b: ((src.matrix_world @ src.pose.bones[b].tail) - (src.matrix_world @ src.pose.bones[b].head)) for b in bones}
        hs = (src.matrix_world @ src.pose.bones["mixamorig:Hips"].head) * S
        DS = {b: (src.matrix_world @ src.pose.bones[b].matrix).to_quaternion() @ rs[b] for b in bones}
        bpy.context.scene.frame_set(f + 1)  # FBX import starts at frame 1: baked frame f lives at f+1
        for b in bones:
            vd = (dst.matrix_world @ dst.pose.bones[b].tail) - (dst.matrix_world @ dst.pose.bones[b].head)
            if VS[b].length < 1e-6 or vd.length < 1e-6: continue
            errs.append(math.degrees(VS[b].angle(vd)))
        for b in bones:
            dd = (dst.matrix_world @ dst.pose.bones[b].matrix).to_quaternion() @ rd[b]
            e = math.degrees(DS[b].rotation_difference(dd).angle)
            e = min(e, 360.0 - e)
            derrs.append(e); dbone[b] = max(dbone.get(b, 0.0), e)
        hd = dst.matrix_world @ dst.pose.bones["mixamorig:Hips"].head
        perr = max(perr, (hs - hd).length)
    mx = max(errs); worst = max(worst, mx)
    dmx = max(derrs); worst_d = max(worst_d, dmx)
    print(f"{nm:18s} frames={f1-f0+1:4d} boneDirErr max={mx:6.2f} deg mean={sum(errs)/len(errs):5.2f} deg  hipsPosErr max={perr:.4f} m")
    top5 = sorted(dbone.items(), key=lambda x: -x[1])[:5]
    print(f"DELTA {nm:18s} worst={dmx:6.3f} deg mean={sum(derrs)/len(derrs):6.3f} deg  top5=" + ", ".join(f"{a.replace('mixamorig:', '')}={v:.3f}" for a, v in top5))
print("VERIFY", "PASS" if worst < 1.0 else "FAIL", f"worst={worst:.2f} deg (boneDir, informational)")
print("VERIFY_DELTA", "PASS" if worst_d < 1.0 else "FAIL", f"worst={worst_d:.3f} deg (gate < 1.0)")
