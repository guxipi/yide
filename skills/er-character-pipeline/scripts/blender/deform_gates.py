"""Posed-deformation gates for an ER character FBX (mixamorig skeleton), Blender 5.1 background.

usage: blender -b --factory-startup -P deform_gates_final.py -- --in <fbx> --out <dir> --label <name>
       [--poses rest,arms_down_10,...] [--no-render]
  --poses  comma-separated subset of the pose library (default: all 7 poses: rest, arms_down_10,
           arms_forward_90, arms_up_125, elbow_120_L, squat_knee_100, arm_up_125_L)

Poses each test pose by setting pose-bone matrices (no keyframes), reads the evaluated (depsgraph) mesh and
measures, per pose: edge strain p1/p99 + out-of-range edge count, joint band volume ratio, opposite-side leak
(one-sided poses), new self-intersecting triangle pairs, forearm/hand-in-torso %, squashed-edge per-mille.
Writes <out>/<label>_gates.json, one PNG per pose (front | left side, white clay, EEVEE, Standard) and prints
one JSON summary line. Exit code 1 if any gate FAILs.

GATES (only these two decide the exit code, only on arms_down_10 and elbow_120_L):
  arm_in_torso  FAIL when forearm/hand verts newly > 1% H inside the arm-less body exceed 15% on either side.
                Source: sambena/autorig-workbench arm_in_torso_pct definition, quality_score "good" edge 15.
                Measured 2026-10-26 (L/R %): arms_down_10 Tuba 30.36/13.55 (pitfall 77, render confirms the left
                forearm sinks into the belly), Wren 0/0, Rook2 0/0; elbow_120_L Tuba 21.42, Rook2 3.63, Wren 0.
  strain        FAIL when edges with posed/rest length outside 0.5..1.6 exceed max(10, 0.2% of live edges).
                Source: scenario bx_rig.deformation_report / flag_report. Measured (% of edges): arms_down_10
                Tuba 0.58, Wren 0.03, Rook2 0.02; elbow_120_L Tuba 0.24, Wren 0.05, Rook2 0.09 (small margin).
  Test angle is FIXED at 10 deg shoulder abduction - do not press the arms lower: Wren already reads 14.23% at
  5 deg and 64.71% at 0 deg (Tuba 52.17 at 5, 7.19 at 15; Rook2 13.49 at 0).
  Limitation: poses are absolute world directions, so the amount of rotation from rest depends on each model's
  rest A-pose (rest shoulder abduction from bone vectors: Tuba ~55 deg, Wren ~31, Rook2 ~24). arms_down_10 turns
  Tuba's arm ~45 deg but Rook2's only ~14 deg, which inflates Tuba's strain and self-intersection counts.

REPORT ONLY (in each pose's "report", never affect the exit code): self-intersection (every pose of all three
models adds 97-1716 pairs), joint volume (Wren 0.57 arms_up, Rook2 0.337 arms_forward: does not separate good
from bad), leak (0.0 everywhere; rig_audit cross_side already covers it), squash (max 0.754 per-mille), strain on
the large-range poses (Wren 1.72% squat ~ Tuba 1.69%), missing bones.

Metric code for strain / joint volume / leak / self-intersection is adapted from scenario-labs/skills
(MIT, Copyright (c) 2026 Scenario Inc.): scenario-blender-rigging/scripts/bx_rig.py deformation_report,
joint_region, _seg_dist, _dist_to_chain, flag_report and scenario-blender-expert/scripts/bx_audit.py
_self_intersections. arm_in_torso_pct and squash_permille follow the definitions in sambena/autorig-workbench
(GPL-3.0) steps/score.py; that code was NOT copied, only the definitions were re-implemented here.

Conventions (same as er-character-pipeline _bl.py): Z up, character faces -Y, character's own LEFT is +X.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

# ---------------------------------------------------------------- thresholds (H = rest mesh height)
# scenario bx_rig.deformation_report: an edge is "bad" when posed/rest length ratio is outside 0.5..1.6
STRAIN_LO, STRAIN_HI = 0.5, 1.6
# scenario bx_rig.flag_report: FAIL when bad edges > max(10, 0.2% of edges)
STRAIN_BAD_MIN, STRAIN_BAD_FRAC = 10, 0.002
# scenario bx_rig.flag_report: worst band along the limb < 0.85 = collapse (candy wrapper / pinch), > 1.25 = bulge
VOL_COLLAPSE, VOL_BULGE = 0.85, 1.25
# scenario bx_rig.joint_region: band = within 0.5 segment length of the joint, within 1.8 limb radii of the axis
JOINT_REACH, JOINT_RADII = 0.5, 1.8
# scenario bx_rig.deformation_report: "opposite side" = |x| beyond 0.04 H on the other half
LEAK_SIDE_X = 0.04
# scenario bx_rig.flag_report: FAIL when the opposite side moves more than 1e-3 H
LEAK_MAX = 1e-3
# scenario bx_rig.flag_report: FAIL when the pose adds any self-intersecting face pair (> 0)
SELF_ISECT_MAX = 0
# sambena score.py definitions: a forearm/hand vertex is "in the torso" when it is more than 1% H under the surface
# of the body without its arms; probe vertices within 3% H of that body at rest are dropped (joint skin, not the limb
# going in); the in/out test looks at most 6% H (or half the body's thinnest extent) from the surface
AIT_DEPTH, AIT_CLEAR, AIT_REACH = 0.01, 0.03, 0.06
AIT_PROBE_MAX = 3000
# sambena quality_score.CHECKS arm_in_torso_pct = (good 15, bad 60): FAIL above the "good" edge
AIT_MAX_PCT = 15.0
# sambena score.py: squashed = posed/rest length < 1/3 and rest length > 0.1% of size; live edge = rest > 0.01% size
SQUASH_RATIO, SQUASH_MIN_LEN, LIVE_MIN_LEN = 1.0 / 3.0, 0.001, 1e-4
# sambena quality_score.CHECKS squash_permille = (good 13, bad 30): FAIL above the "good" edge
SQUASH_MAX_PERMILLE = 13.0
# ER: only arm_in_torso (AIT_MAX_PCT) and strain (STRAIN_BAD_*) are gates, and only on these poses (see header).
# VOL_*, LEAK_MAX, SELF_ISECT_MAX and SQUASH_MAX_PERMILLE are the reference values written next to the numbers in
# each pose's "report" (as "*_over_ref") and do not affect the exit code.
GATE_POSES = ("arms_down_10", "elbow_120_L")


# ---------------------------------------------------------------- args / scene
def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"--render": True}
    i = 0
    while i < len(a):
        if a[i] == "--no-render":
            o["--render"] = False
            i += 1
        else:
            o[a[i]] = a[i + 1]
            i += 2
    return o


def evaluate():
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


def find_bone(arm, key):
    """Bone whose name without prefix ('mixamorig:', 'mixamorig1:', 'Armature|' ...) equals key."""
    for b in arm.pose.bones:
        if b.name.split(":")[-1].split("|")[-1] == key:
            return b
    for b in arm.pose.bones:
        if b.name.endswith(key) and not b.name.endswith("Fore" + key) and not b.name.endswith("Up" + key):
            return b
    return None


def world_axis_y(arm, pb):
    evaluate()
    return (arm.matrix_world.to_3x3() @ pb.matrix.col[1].xyz).normalized()


def rotate_world(arm, pb, q):
    """Rotate a pose bone by world-space quaternion q about its own head (bx_rig.rotate_world)."""
    evaluate()
    R = arm.matrix_world.to_3x3().normalized()
    qa = (R.inverted() @ q.to_matrix() @ R).to_4x4()
    M = pb.matrix.copy()
    t = M.translation.copy()
    from mathutils import Matrix
    pb.matrix = Matrix.Translation(t) @ qa @ Matrix.Translation(-t) @ M
    evaluate()


def aim(arm, pb, direction):
    """Swing the bone so its head->tail points along a world direction (bx_rig.aim)."""
    y = world_axis_y(arm, pb)
    rotate_world(arm, pb, y.rotation_difference(Vector(direction).normalized()))


def hinge_toward(arm, pb, deg, toward):
    """Rotate the bone deg degrees in the plane of its direction and `toward` (tail moves toward it)."""
    d = world_axis_y(arm, pb)
    t = Vector(toward).normalized()
    f = t - d * d.dot(t)
    if f.length < 1e-6:
        return
    axis = d.cross(f.normalized()).normalized()
    rotate_world(arm, pb, Quaternion(axis, math.radians(deg)))


def reset_pose(arm):
    from mathutils import Matrix
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    evaluate()


def sdir(side):
    return 1.0 if side == "L" else -1.0


def abduct(deg, s):
    """Upper-arm direction at `deg` shoulder abduction in the coronal plane (0 = straight down, 90 = T)."""
    r = math.radians(deg)
    return (sdir(s) * math.sin(r), 0.0, -math.cos(r))


# pose ops: ("aim", key, dir) | ("hinge", key, deg, toward). Arms are aimed as a straight line (upper arm, then
# forearm to the same direction); hands keep their rest relation to the forearm.
def arm_ops(s, direction):
    side = "Left" if s == "L" else "Right"
    return [("aim", side + "Arm", direction), ("aim", side + "ForeArm", direction)]


POSES = [
    {"name": "rest", "ops": []},
    {"name": "arms_down_10", "joints": ["shoulder.L", "shoulder.R"],
     "ops": arm_ops("L", abduct(10, "L")) + arm_ops("R", abduct(10, "R"))},
    {"name": "arms_forward_90", "joints": ["shoulder.L", "shoulder.R"],
     "ops": arm_ops("L", (0, -1, 0)) + arm_ops("R", (0, -1, 0))},
    {"name": "arms_up_125", "joints": ["shoulder.L", "shoulder.R"],
     "ops": arm_ops("L", abduct(125, "L")) + arm_ops("R", abduct(125, "R"))},
    {"name": "elbow_120_L", "side": "L", "joints": ["elbow.L"],
     "ops": [("hinge", "LeftForeArm", 120, (0, -1, 0))]},
    {"name": "squat_knee_100", "joints": ["knee.L", "knee.R", "hip.L", "hip.R"],
     "ops": [("hinge", "LeftUpLeg", 70, (0, -1, 0)), ("hinge", "RightUpLeg", 70, (0, -1, 0)),
             ("hinge", "LeftLeg", 100, (0, 1, 0)), ("hinge", "RightLeg", 100, (0, 1, 0))]},
    {"name": "arm_up_125_L", "side": "L", "joints": ["shoulder.L"],
     "ops": arm_ops("L", abduct(125, "L"))},
]

# joint frames (bx_rig.JOINTS mapped to mixamo): (proximal point, joint, distal point) as "bone:head|tail"
JOINTS = {}
for _s, _n in (("L", "Left"), ("R", "Right")):
    JOINTS["shoulder." + _s] = (_n + "Shoulder:head", _n + "Arm:head", _n + "Arm:tail")
    JOINTS["elbow." + _s] = (_n + "Arm:head", _n + "ForeArm:head", _n + "ForeArm:tail")
    JOINTS["hip." + _s] = ("Hips:head", _n + "UpLeg:head", _n + "UpLeg:tail")
    JOINTS["knee." + _s] = (_n + "UpLeg:head", _n + "Leg:head", _n + "Leg:tail")


def apply_pose(arm, spec):
    reset_pose(arm)
    skipped = []
    for op in spec["ops"]:
        pb = find_bone(arm, op[1])
        if pb is None:
            skipped.append(op[1])
            continue
        if op[0] == "aim":
            aim(arm, pb, op[2])
        elif op[0] == "hinge":
            hinge_toward(arm, pb, op[2], op[3])
    evaluate()
    return skipped


# ---------------------------------------------------------------- geometry helpers
def posed_coords(meshes):
    dg = evaluate()
    out = []
    for o in meshes:
        eo = o.evaluated_get(dg)
        me = eo.to_mesh()
        a = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", a)
        mw = np.array(eo.matrix_world)
        eo.to_mesh_clear()
        out.append(a.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
    return np.concatenate(out)


def point(arm, spec):
    key, end = spec.split(":")
    pb = find_bone(arm, key)
    if pb is None:
        return None
    return np.array(arm.matrix_world @ (pb.head if end == "head" else pb.tail))


def seg_dist(P, a, b):
    ab = b - a
    t = np.clip(((P - a) @ ab) / max(float(ab @ ab), 1e-12), 0, 1)
    return np.linalg.norm(P - (a + t[:, None] * ab), axis=1), t


def joint_frame(arm, j):
    pts = [point(arm, s) for s in JOINTS[j]]
    return None if any(p is None for p in pts) else pts


def joint_region(arm, V, j):
    fr = joint_frame(arm, j)
    if fr is None:
        return None, None
    a, jj, b = fr
    d1, t1 = seg_dist(V, a, jj)
    d2, t2 = seg_dist(V, jj, b)
    first = d1 <= d2
    d = np.where(first, d1, d2)
    s = np.where(first, t1 - 1.0, t2)
    band = np.abs(s) <= JOINT_REACH
    close = band & (np.abs(s) < 0.15)
    if close.sum() < 6:
        return None, None
    r0 = float(np.median(d[close]))
    sel = band & (d < JOINT_RADII * r0)
    return np.nonzero(sel)[0], fr


def dist_to_chain(P, fr):
    a, j, b = fr
    return np.minimum(seg_dist(P, a, j)[0], seg_dist(P, j, b)[0])


def tri_pairs(P, tris, weld):
    """Intersecting triangle pairs that share no (welded) vertex (bx_audit._self_intersections, as a set)."""
    tree = BVHTree.FromPolygons([tuple(x) for x in P], [tuple(int(i) for i in t) for t in tris], all_triangles=True)
    W = weld[tris]
    out = set()
    for a, b in tree.overlap(tree):
        if a >= b:
            continue
        if set(W[a]) & set(W[b]):
            continue
        out.add((a, b))
    return out


# ---------------------------------------------------------------- arm-in-torso (sambena definition, own code)
ARM_KEYS = ("Shoulder", "Arm", "ForeArm", "Hand")


def classify_bones(arm):
    """{bone: (part, side, distal)}; a bone with no arm word inherits its parent's class."""
    out = {}

    def own(name):
        n = name.split(":")[-1].split("|")[-1]
        for side, word in (("L", "Left"), ("R", "Right")):
            if n.startswith(word):
                rest = n[len(word):]
                if rest.startswith("ForeArm") or rest.startswith("Hand"):
                    return ("arm", side, True)
                if rest.startswith("Arm") or rest.startswith("Shoulder"):
                    return ("arm", side, False)
                return ("other", side, False)
        return None

    def res(b):
        if b.name in out:
            return out[b.name]
        c = own(b.name)
        if c is None:
            c = res(b.parent) if b.parent is not None else ("other", None, False)
        out[b.name] = c
        return c

    for b in arm.data.bones:
        res(b)
    return out


def dominant_bones(meshes):
    dom = []
    for o in meshes:
        names = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            best, bw = "", 0.0
            for g in v.groups:
                if g.weight > bw and g.group in names:
                    best, bw = names[g.group], g.weight
            dom.append(best)
    return dom


class ArmInTorso:
    def __init__(self, rest, tris, dom, cls, H):
        self.H = H
        part = np.array([cls.get(d, ("other", None, False))[0] for d in dom])
        side = np.array([cls.get(d, ("other", None, False))[1] or "" for d in dom])
        dist = np.array([cls.get(d, ("other", None, False))[2] for d in dom])
        self.target = np.nonzero(part != "arm")[0]
        keep = np.full(len(rest), -1)
        keep[self.target] = np.arange(len(self.target))
        kt = keep[tris]
        self.ttris = kt[(kt >= 0).all(axis=1)]
        q = rest[self.target]
        t = self.ttris
        n = np.cross(q[t[:, 1]] - q[t[:, 0]], q[t[:, 2]] - q[t[:, 0]])
        c = (q[t[:, 0]] + q[t[:, 1]] + q[t[:, 2]]) / 3 - q.mean(axis=0)
        self.sign = 1.0 if float(np.sum(n * c)) >= 0 else -1.0
        self.reach = min(0.5 * float(np.ptp(q, axis=0).min()), AIT_REACH * H)
        tree = self._tree(rest)
        self.probes, self.before = {}, {}
        for s in ("L", "R"):
            idx = np.nonzero((part == "arm") & dist & (side == s))[0]
            if len(idx) > AIT_PROBE_MAX:
                idx = idx[np.linspace(0, len(idx) - 1, AIT_PROBE_MAX).astype(int)]
            far = np.array([tree.find_nearest(Vector(rest[i]), AIT_CLEAR * H)[0] is None for i in idx], bool)
            self.before[s] = int(len(idx))
            idx = idx[far]
            if len(idx) >= 10:
                self.probes[s] = idx
        self.rest_in = {s: self._inside(rest, idx, tree) for s, idx in self.probes.items()}
        self.info = {"target_verts": int(len(self.target)), "sign": self.sign, "reach_H": round(self.reach / H, 4),
                     "probes_before_clear": self.before, "probes": {s: int(len(i)) for s, i in self.probes.items()},
                     "rest_inside": {s: int(v.sum()) for s, v in self.rest_in.items()}}

    def _tree(self, P):
        return BVHTree.FromPolygons([tuple(x) for x in P[self.target]], [tuple(int(i) for i in f) for f in self.ttris],
                                    all_triangles=True)

    def _inside(self, P, idx, tree):
        out = np.zeros(len(idx), bool)
        for k, i in enumerate(idx):
            loc, nor, _, _ = tree.find_nearest(Vector(P[i]), self.reach)
            if loc is None:
                continue
            out[k] = self.sign * (Vector(P[i]) - loc).dot(nor) < -AIT_DEPTH * self.H
        return out

    def measure(self, P):
        tree = self._tree(P)
        r = {}
        for s, idx in self.probes.items():
            new = self._inside(P, idx, tree) & ~self.rest_in[s]
            r[s] = round(100.0 * float(new.mean()), 2)
        return r


# ---------------------------------------------------------------- render
def setup_render(meshes):
    sc = bpy.context.scene
    ids = [i.identifier for i in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    eng = next((e for e in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT") if e in ids), ids[0])
    sc.render.engine = eng
    sc.render.resolution_x = sc.render.resolution_y = 640
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.new("dg_world")
    sc.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.32, 0.32, 0.34, 1)
    bg.inputs[1].default_value = 0.8
    clay = bpy.data.materials.new("dg_clay")
    clay.use_nodes = True
    b = next(n for n in clay.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.9, 0.9, 0.9, 1)
    b.inputs["Roughness"].default_value = 0.7
    for o in meshes:
        o.data.materials.clear()
        o.data.materials.append(clay)
    # key from front-above (travels +Y), fill from the character's left (+X) for the side view
    for nm, en, rot in (("dg_key", 3.0, (math.radians(50), 0, math.radians(-25))),
                        ("dg_fill", 1.5, (math.radians(60), 0, math.radians(90)))):
        L = bpy.data.lights.new(nm, "SUN")
        L.energy = en
        lo = bpy.data.objects.new(nm, L)
        sc.collection.objects.link(lo)
        lo.rotation_euler = rot
    cam = bpy.data.cameras.new("dg_cam")
    cam.type = "ORTHO"
    co = bpy.data.objects.new("dg_cam", cam)
    sc.collection.objects.link(co)
    sc.camera = co
    return eng, co


def render_pose(co, P, path):
    mn, mx = P.min(0), P.max(0)
    c = Vector(((mn + mx) / 2).tolist())
    imgs = []
    for tag, d, ext in (("front", Vector((0, -1, 0)), max(mx[0] - mn[0], mx[2] - mn[2])),
                        ("side", Vector((1, 0, 0)), max(mx[1] - mn[1], mx[2] - mn[2]))):
        co.data.ortho_scale = float(ext) * 1.1
        co.location = c + d * 5.0
        co.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        co.data.clip_end = 20
        tmp = path[:-4] + "_" + tag + ".png"
        bpy.context.scene.render.filepath = tmp
        bpy.ops.render.render(write_still=True)
        imgs.append(tmp)
    arrs = []
    for p in imgs:
        im = bpy.data.images.load(p)
        a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        arrs.append(a.reshape(im.size[1], im.size[0], 4))
        bpy.data.images.remove(im)
    both = np.concatenate(arrs, axis=1)
    out = bpy.data.images.new("dg_pair", both.shape[1], both.shape[0], alpha=True)
    out.pixels.foreach_set(both.ravel())
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    for p in imgs:
        os.remove(p)


# ---------------------------------------------------------------- main
def main():
    o = args()
    src, outd, label = o["--in"], o["--out"], o["--label"]
    os.makedirs(outd, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    arm = next(x for x in bpy.context.scene.objects if x.type == "ARMATURE")
    meshes = [x for x in bpy.context.scene.objects if x.type == "MESH" and any(m.type == "ARMATURE" for m in x.modifiers)]
    for x in meshes:
        for m in x.modifiers:
            if m.type in ("SUBSURF", "MULTIRES"):
                m.show_viewport = False
    reset_pose(arm)
    rest = posed_coords(meshes)
    H = float(np.ptp(rest[:, 2]))
    size = float(np.ptp(rest, axis=0).max())
    # topology (concatenated over skinned meshes)
    edges, tris, off = [], [], 0
    for x in meshes:
        e = np.empty(len(x.data.edges) * 2, dtype=np.int64)
        x.data.edges.foreach_get("vertices", e)
        edges.append(e.reshape(-1, 2) + off)
        x.data.calc_loop_triangles()
        t = np.empty(len(x.data.loop_triangles) * 3, dtype=np.int64)
        x.data.loop_triangles.foreach_get("vertices", t)
        tris.append(t.reshape(-1, 3) + off)
        off += len(x.data.vertices)
    edges, tris = np.concatenate(edges), np.concatenate(tris)
    L0 = np.linalg.norm(rest[edges[:, 0]] - rest[edges[:, 1]], axis=1)
    live = L0 > LIVE_MIN_LEN * size
    ed, L0 = edges[live], L0[live]
    sq_ok = L0 > SQUASH_MIN_LEN * size
    # weld map for self-intersection adjacency (UV-split co-located vertices count as shared)
    key = np.round(rest / (1e-5 * H)).astype(np.int64)
    _, weld = np.unique(key, axis=0, return_inverse=True)
    weld = weld.ravel()
    si_rest = tri_pairs(rest, tris, weld)
    regions = {}
    for j in JOINTS:
        idx, fr = joint_region(arm, rest, j)
        if idx is not None and len(idx):
            regions[j] = (idx, fr)
    cls = classify_bones(arm)
    ait = ArmInTorso(rest, tris, dominant_bones(meshes), cls, H)
    eng, cam = (None, None)
    rdir = os.path.join(outd, label + "_renders")
    if o["--render"]:
        os.makedirs(rdir, exist_ok=True)
        eng, cam = setup_render(meshes)
    rep = {"input": src, "label": label, "height": round(H, 5), "verts": int(len(rest)), "tris": int(len(tris)),
           "edges_live": int(len(ed)), "rest_self_isect_pairs": len(si_rest), "render_engine": eng,
           "joint_band_verts": {j: int(len(v[0])) for j, v in regions.items()}, "arm_in_torso_setup": ait.info,
           "bones_matched": {k: (find_bone(arm, k).name if find_bone(arm, k) else None)
                             for k in ("Hips", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftUpLeg", "LeftLeg",
                                       "RightArm", "RightForeArm", "RightUpLeg", "RightLeg")},
           "thresholds": {"gate": {"strain_range": [STRAIN_LO, STRAIN_HI],
                                   "strain_bad_fail": f"> max({STRAIN_BAD_MIN}, {STRAIN_BAD_FRAC} * edges)",
                                   "arm_in_torso_max_pct": AIT_MAX_PCT},
                          "report_ref": {"vol_collapse": VOL_COLLAPSE, "vol_bulge": VOL_BULGE, "leak_max_H": LEAK_MAX,
                                         "self_isect_new_max": SELF_ISECT_MAX,
                                         "squash_max_permille": SQUASH_MAX_PERMILLE}},
           "poses": {}}
    names = [n.strip() for n in o["--poses"].split(",")] if o.get("--poses") else [p["name"] for p in POSES]
    unknown = [n for n in names if n not in {p["name"] for p in POSES}]
    if unknown:
        raise SystemExit(f"unknown poses {unknown}; library: {[p['name'] for p in POSES]}")
    rep["poses_run"] = names
    rep["gate_poses"] = list(GATE_POSES)
    fails = []
    try:
        for p in (q for q in POSES if q["name"] in names):
            skipped = apply_pose(arm, p)
            P = posed_coords(meshes)
            ratio = np.linalg.norm(P[ed[:, 0]] - P[ed[:, 1]], axis=1) / L0
            bad = int(((ratio < STRAIN_LO) | (ratio > STRAIN_HI)).sum())
            sq = int((sq_ok & (ratio < SQUASH_RATIO)).sum())
            r = {"skipped": skipped,
                 "strain_p1": round(float(np.percentile(ratio, 1)), 3),
                 "strain_p99": round(float(np.percentile(ratio, 99)), 3),
                 "strain_bad": bad,
                 "squash_permille": round(1000.0 * sq / max(len(ed), 1), 3)}
            if p.get("side") in ("L", "R"):
                other = rest[:, 0] < -LEAK_SIDE_X * H if p["side"] == "L" else rest[:, 0] > LEAK_SIDE_X * H
                disp = np.linalg.norm(P[other] - rest[other], axis=1)
                r["leak_H"] = round(float(disp.max() / H), 5)
                r["leak_verts_over"] = int((disp > LEAK_MAX * H).sum())
            si = tri_pairs(P, tris, weld)
            r["self_isect_new"] = len(si - si_rest)
            r["self_isect_count_diff"] = len(si) - len(si_rest)
            jr = {}
            for j in p.get("joints", []):
                if j not in regions:
                    jr[j] = None
                    continue
                idx, fr0 = regions[j]
                fr1 = joint_frame(arm, j)
                d0 = dist_to_chain(rest[idx], fr0)
                d1 = dist_to_chain(P[idx], fr1)
                vol = float((d1 ** 2).mean() / max((d0 ** 2).mean(), 1e-12))
                a, jj, b = fr0
                da, ta = seg_dist(rest[idx], a, jj)
                db, tb = seg_dist(rest[idx], jj, b)
                s = np.where(da <= db, ta - 1.0, tb)
                bands = []
                for lo_, hi_ in zip(np.linspace(-1, 1, 9)[:-1], np.linspace(-1, 1, 9)[1:]):
                    m = (s >= lo_) & (s < hi_)
                    if m.sum() >= 6:
                        bands.append(float((d1[m] ** 2).mean() / max((d0[m] ** 2).mean(), 1e-12)))
                jr[j] = {"volume": round(vol, 3), "min_ring": round(min(bands), 3) if bands else None,
                         "max_ring": round(max(bands), 3) if bands else None}
            r["joints"] = jr
            r["arm_in_torso_pct"] = ait.measure(P)
            strain_ok = bad <= max(STRAIN_BAD_MIN, STRAIN_BAD_FRAC * len(ed))
            over = {
                "squash_over_ref": r["squash_permille"] > SQUASH_MAX_PERMILLE,
                "self_isect_over_ref": r["self_isect_new"] > SELF_ISECT_MAX,
                "volume_over_ref": not all(v is None or ((v["min_ring"] is None or v["min_ring"] >= VOL_COLLAPSE) and
                                                         (v["max_ring"] is None or v["max_ring"] <= VOL_BULGE)) for v in jr.values()),
            }
            if "leak_H" in r:
                over["leak_over_ref"] = r["leak_H"] > LEAK_MAX
            g = {}
            if p["name"] in GATE_POSES:
                g["arm_in_torso"] = max(r["arm_in_torso_pct"].values(), default=0) <= AIT_MAX_PCT
                g["strain"] = strain_ok
                gated = {"strain_bad": bad, "strain_bad_pct": round(100.0 * bad / max(len(ed), 1), 3),
                         "arm_in_torso_pct": r["arm_in_torso_pct"]}
            else:
                over["strain_over_ref"] = not strain_ok
                gated = {}
            rpt = {k: v for k, v in r.items() if k not in gated}
            rpt["strain_bad_pct"] = round(100.0 * bad / max(len(ed), 1), 3)
            rpt.update(over)
            r = {"gates": g, "gate_values": gated, "report": rpt}
            for k, v in g.items():
                if not v:
                    fails.append(p["name"] + "/" + k)
            if cam is not None:
                render_pose(cam, P, os.path.join(rdir, f"{label}_{p['name']}.png"))
            rep["poses"][p["name"]] = r
            print("POSE", p["name"], json.dumps(r), "FAIL" if not all(g.values()) else ("PASS" if g else "REPORT"))
    finally:
        reset_pose(arm)
    rep["fails"] = fails
    rep["result"] = "FAIL" if fails else "PASS"
    outp = os.path.join(outd, label + "_gates.json")
    with open(outp, "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print("DEFORM_GATES " + json.dumps({"label": label, "result": rep["result"], "fails": fails, "json": outp}))
    sys.stdout.flush()
    return 1 if fails else 0


if __name__ == "__main__":
    _code = main()
    sys.stdout.flush()
    os._exit(_code)
