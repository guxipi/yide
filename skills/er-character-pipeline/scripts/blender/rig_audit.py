"""Numeric rig audit (research doc section 11 checklist, items 2-7) for a rigged GLB/FBX/blend.

usage: blender -b --python rig_audit.py -- <rig.blend|glb|fbx> <out.json>
Prints a PASS/FAIL line per gate and RIG_AUDIT PASS|FAIL. Secondary vertices = any vertex weighted to a
non-mixamorig bone (hair/skirt/rigid chains); they and the Head bone (a thin line inside a big skull+hair
volume) are exempt from the far-from-bone rule. A back-of-head vertex 100% on Neck IS reported (that was a
real Wren bug: the back of the head did not follow head turns).

Gates (normalized height 1.0):
  max influences <= 4; weight sums 0.999-1.001; verts with max weight < 0.5 < 10%;
  far body weights (>=0.1 from a bone > 12% height away, non-secondary) <= 0.1% of verts (heel/collar
  vertices whose nearest bone is itself ~12% away; thousands = a real bug); cross-side == 0;
  UpLeg weight above hip == 0; zero-weight deform bones == 0;
  mirrored bone length difference < 2%, mirrored head error < 0.005; spine lean < 3 deg;
  ToeBase at 0.6-0.8 of heel->toe; clavicle head not on the Neck head (> 0.005);
  armature object scale == 1 (otherwise the FBX root carries the scale into Unity).
Elbow/knee position vs. the mesh bend is NOT measured numerically - check the deform sheet.
"""
import json
import math
import os
import sys

from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args  # noqa: E402


def segdist(p, a, b):
    ab = b - a
    if ab.length_squared == 0:
        return (p - a).length
    return (p - (a + ab * max(0, min(1, (p - a).dot(ab) / ab.length_squared)))).length


def vangle(v):
    return math.degrees(math.acos(max(-1, min(1, abs(v.normalized().z))))) if v.length else 0


def main():
    a = blender_args(sys.argv)
    if len(a) < 2 or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    src, outp = a[0], a[1]
    _bl.load_any(src)
    arm = _bl.armature()
    mesh = _bl.main_mesh()
    mw, aw = mesh.matrix_world, arm.matrix_world
    pts = [mw @ v.co for v in mesh.data.vertices]
    zmin, zmax = min(p.z for p in pts), max(p.z for p in pts)
    h = zmax - zmin
    bones = {b.name: b for b in arm.data.bones}
    J = lambda n: aw @ bones["mixamorig:" + n].head_local
    pairs = []
    for n, b in bones.items():
        if "Left" in n and n.replace("Left", "Right") in bones:
            r = bones[n.replace("Left", "Right")]
            l0, l1, r0, r1 = aw @ b.head_local, aw @ b.tail_local, aw @ r.head_local, aw @ r.tail_local
            ll, rl = (l1 - l0).length, (r1 - r0).length
            pairs.append({"pair": n, "len_diff_pct": round(abs(ll - rl) / max(ll, rl, 1e-9) * 100, 3),
                          "mirror_err": round((l0 - Vector((-r0.x, r0.y, r0.z))).length / h, 5)})
    g = {gg.index: gg.name for gg in mesh.vertex_groups}
    hist, sums, low, cross, above, far = {}, [], 0, set(), set(), set()
    hipz = J("Hips").z
    for v, p in zip(mesh.data.vertices, pts):
        ws = [(g[x.group], x.weight) for x in v.groups if x.weight > 1e-6 and x.group in g]
        hist[len(ws)] = hist.get(len(ws), 0) + 1
        sums.append(sum(w for _, w in ws))
        if ws and max(w for _, w in ws) < .5:
            low += 1
        sec = any(not n.startswith("mixamorig") for n, w in ws)
        for n, w in ws:
            if w < .1:
                continue
            if p.x > .01 * h and any(k in n for k in ("RightArm", "RightForeArm", "RightHand", "RightUpLeg", "RightLeg", "RightFoot")):
                cross.add(v.index)
            if p.x < -.01 * h and any(k in n for k in ("LeftArm", "LeftForeArm", "LeftHand", "LeftUpLeg", "LeftLeg", "LeftFoot")):
                cross.add(v.index)
            if p.z > hipz + .01 * h and "UpLeg" in n:
                above.add(v.index)
            if not sec and n not in ("mixamorig:Head", "mixamorig:HeadTop_End") and n in bones and segdist(p, aw @ bones[n].head_local, aw @ bones[n].tail_local) > .12 * h:
                far.add(v.index)
    # Seam jumps (10-08): neighbouring or co-located (UV-split) vertices whose weight sets differ a lot tear
    # open in big motions (walk/jump/crouch) even when idle looks fine. Count edges with L1 weight jump > 0.6.
    wd = [{g[x.group]: x.weight for x in v.groups if x.weight > 1e-6 and x.group in g} for v in mesh.data.vertices]
    def l1(a_, b_):
        return sum(abs(a_.get(n, 0) - b_.get(n, 0)) for n in set(a_) | set(b_))
    pairs_e = [tuple(e.vertices) for e in mesh.data.edges]
    buckets = {}
    for v in mesh.data.vertices:
        buckets.setdefault(tuple(round(c, 5) for c in v.co), []).append(v.index)
    coloc_pairs = [(gr[0], x) for gr in buckets.values() if len(gr) > 1 for x in gr[1:]]
    def hard_ok(a_, b_):
        # Expected hard edges: a rigid part (one non-mixamo bone at 1.0) or finger-against-finger in a mitten hand.
        for w_ in (wd[a_], wd[b_]):
            if len(w_) == 1 and not next(iter(w_)).startswith("mixamorig"):
                return True
        ta, tb = max(wd[a_], key=wd[a_].get, default=""), max(wd[b_], key=wd[b_].get, default="")
        return "Hand" in ta and "Hand" in tb
    seam_edges = sum(1 for a_, b_ in pairs_e if l1(wd[a_], wd[b_]) > .6 and not hard_ok(a_, b_))
    seam_coloc = sum(1 for a_, b_ in coloc_pairs if l1(wd[a_], wd[b_]) > .05)
    used = {g[x.group] for v in mesh.data.vertices for x in v.groups if x.weight > 1e-6 and x.group in g}
    zero = [b.name for b in bones.values() if b.use_deform and b.name not in used]
    fy = [p.y for p in pts if p.z < zmin + .12 * h]
    heel, toe = max(fy), min(fy)
    tb = (J("LeftToeBase").y + J("RightToeBase").y) / 2
    toe_frac = (heel - tb) / max(heel - toe, 1e-9)
    spine = max(vangle(aw @ bones["mixamorig:" + n].tail_local - aw @ bones["mixamorig:" + n].head_local) for n in ("Spine", "Spine1", "Spine2"))
    clav = min((J("LeftShoulder") - J("Neck")).length, (J("RightShoulder") - J("Neck")).length) / h
    rep = {
        "input": src, "height": round(h, 5), "bones": len(bones), "verts": len(pts),
        "tris": sum(len(p.vertices) - 2 for p in mesh.data.polygons),
        "armature_scale": [round(x, 4) for x in arm.scale],
        "influence_hist": hist, "weight_sum": [round(min(sums), 5), round(max(sums), 5)],
        "frac_max_below_0_5": round(low / len(pts), 4), "far_body": len(far), "far_body_sample": sorted(far)[:20], "cross_side": len(cross),
        "upleg_above_hip": len(above), "zero_weight_deform": zero,
        "worst_pair_len_diff_pct": max((p["len_diff_pct"] for p in pairs), default=0),
        "worst_pair_mirror_err": max((p["mirror_err"] for p in pairs), default=0),
        "spine_lean_deg": round(spine, 3), "toe_frac": round(toe_frac, 3), "clavicle_neck_sep": round(clav, 4),
        "seam_jump_edges": seam_edges, "edges": len(pairs_e), "seam_coloc_split": seam_coloc,
        "secondary_bones": sorted(n for n in bones if not n.startswith("mixamorig")),
    }
    gates = {
        "max_influences<=4": max(hist) <= 4,
        "weight_sum_1": 0.999 <= rep["weight_sum"][0] and rep["weight_sum"][1] <= 1.001,
        "seam_jump_edges<=0.3%": rep["seam_jump_edges"] <= 0.003 * rep["edges"],
        "seam_coloc_split==0": rep["seam_coloc_split"] == 0,
        "far_body<=0.1%": rep["far_body"] <= 0.001 * len(pts),
        "cross_side==0": rep["cross_side"] == 0,
        "upleg_above_hip==0": rep["upleg_above_hip"] == 0,
        "zero_weight_deform==0": not zero,
        "mirror_len<2%": rep["worst_pair_len_diff_pct"] < 2,
        "mirror_pos<0.005": rep["worst_pair_mirror_err"] < 0.005,
        "spine_lean<3": spine < 3,
        "toe_0.6-0.8": 0.6 <= toe_frac <= 0.8,
        "clavicle_off_neck": clav > 0.005,
        "armature_scale_1": all(abs(x - 1) < 1e-3 for x in arm.scale),
    }
    rep["gates"] = gates
    os.makedirs(os.path.dirname(os.path.abspath(outp)), exist_ok=True)
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    for k, v in gates.items():
        print(("PASS " if v else "FAIL ") + k)
    print(json.dumps({k: rep[k] for k in ("height", "tris", "frac_max_below_0_5", "seam_jump_edges", "seam_coloc_split", "far_body", "cross_side", "upleg_above_hip", "worst_pair_len_diff_pct", "spine_lean_deg", "toe_frac")}))
    print("RIG_AUDIT", "PASS" if all(gates.values()) else "FAIL", outp)


main()
