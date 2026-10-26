"""Turn a Tripo Mixamo auto-rig into a game-ready humanoid rig + secondary chains, driven by the character config.

usage: blender -b --python rig_build.py -- --config char.json [--src rig.glb] [--out DIR] [--texture clean.png]
       [--tex-size 2048] [--no-renders]
Defaults: --src = files.rig_glb, --out = {out_dir}/{files.rig_dir or 'rig'}.
Outputs: <Name>.fbx (Unity), <slug>_rig.blend (rest pose), <Name>_basecolor.png, deform/<pose>_{front,threequarter}.png,
         rig_build.json (counts + per-pose stretch metrics). Then run:
         blender -b --python rig_audit.py -- <out>/<slug>_rig.blend <out>/audit.json
         py -3 deform_sheet.py --dir <out>/deform --out <out>/deform_sheet.png --crops <out>/deform_crops.png

What it does (each step exists because something broke on Wren/Rook):
  - deletes extra meshes (Tripo ships a 42/80-vertex Icosphere), bakes height 1.0 / feet z=0 / x centred into data
  - checks the toe direction is -Y (Tripo web GLBs face -Y)
  - mirrors every Left/Right bone pair to the average (Rook: arms 16% different), zero roll, straight spine,
    ToeBase moved to the ball of the foot (toe_ball_fraction of heel->toe; Tripo puts it mid-foot)
  - keeps Tripo's body weights (they beat our re-skins on shoulders/hips/boots) and only rewrites:
      chains (hair tails, fringe ...): vertices in a region -> weights by position along the chain polyline
      skirt ring: vertices classified by FABRIC COLOUR incl. shadowed inner fabric (low-saturation rule) +
        neighbour majority vote; their body part goes to the Hips ONLY (thigh weights shred the skirt)
      rigid parts (backpack/tank): 100% on their own bone
      straps: torso/rigid/clavicle only, and only vertices the arms do NOT drive (else sleeve shards)
  - removes cross-side leakage, thigh weights above the hip, far-away body weights; max 4 influences;
    then seam smoothing: weights diffuse across every rule boundary + co-located (UV-split) vertices share weights
  - adds a non-deform *_Tip bone at the end of every secondary chain so a SpringBone on the last link has a child
  - Prop_R (non-deform) under the right hand
  - exports FBX with apply_scale_options=FBX_SCALE_ALL (no 100x armature root in Unity)
  - poses 9 deformation tests, renders them and computes edge-stretch (robust: tiny rest edges ignored)
"""
import colorsys
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args, file_path, load_cfg, out_path  # noqa: E402

ARMKEYS = ("Arm", "ForeArm", "Hand")
LIMBS_R = ("RightArm", "RightForeArm", "RightHand", "RightUpLeg", "RightLeg", "RightFoot")
HEAD_KEEP = ("mixamorig:Head", "mixamorig:HeadTop_End")
LIMBS_L = ("LeftArm", "LeftForeArm", "LeftHand", "LeftUpLeg", "LeftLeg", "LeftFoot")


def parse():
    a = blender_args(sys.argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    o = {}
    i = 0
    while i < len(a):
        if a[i] == "--no-renders":
            o["no_renders"] = True
            i += 1
        else:
            o[a[i].lstrip("-").replace("-", "_")] = a[i + 1]
            i += 2
    return o


def in_region(p, r, side=1):
    if not r:
        return False
    if "any" in r:  # union of boxes (Vesper v4 long back hair: depth threshold changes with height)
        return any(in_region(p, sub, side) for sub in r["any"])
    for ax in ("x", "y", "z"):
        if ax in r:
            lo, hi = r[ax]
            v = getattr(p, ax)
            if ax == "x" and side < 0:
                lo, hi = -hi, -lo
            if not (lo < v < hi):
                return False
    if "absx" in r and not (r["absx"][0] <= abs(p.x) < r["absx"][1]):
        return False
    return True


def poly_param(p, pts):
    """Position of p along a polyline: segment index + t (0..len-1)."""
    best = (1e9, 0.0)
    for k in range(len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        ab = b - a
        t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
        d = (p - (a + ab * t)).length
        if d < best[0]:
            best = (d, k + t)
    return best[1]


def chain_weights(u, names, scale=1.0):
    nb = len(names)
    u = max(0.0, min(nb - 1e-3, u))
    k = int(u)
    f = u - k
    w = {names[k]: scale * (1 - f)}
    if k + 1 < nb:
        w[names[k + 1]] = w.get(names[k + 1], 0) + scale * f
    return w


def main():
    o = parse()
    cfg = load_cfg(o.get("config"))
    rc = cfg["rig"]
    src = o.get("src") or file_path(cfg, "rig_glb")
    out = o.get("out") or out_path(cfg, cfg["files"].get("rig_dir", "rig"))
    os.makedirs(os.path.join(out, "deform"), exist_ok=True)
    NAME, SLUG = cfg["name"], cfg["slug"]
    head_bones = rc.get("head_bones", ["mixamorig:Head", "mixamorig:HeadTop_End", "mixamorig:Neck"])

    _bl.load_any(src)
    arm = _bl.armature()
    mesh = _bl.main_mesh()
    if arm is None:
        raise SystemExit("no armature in " + src + " (rig it on Tripo first: Humanoid / Mixamo)")
    removed = [ob.name for ob in list(bpy.data.objects) if ob.type == "MESH" and ob != mesh]
    for ob in list(bpy.data.objects):
        if ob.type == "MESH" and ob != mesh:
            bpy.data.objects.remove(ob, do_unlink=True)
    arm.name, mesh.name = f"{NAME}_Armature", NAME
    print("REMOVED_MESHES", removed)

    # --- normalize (same two-pass approach that worked on Wren) ---
    # 10-24 Coda: Tripo's rig GLB can parent the mesh to the armature AND sit centred on the origin (feet at -0.53);
    # scaling/moving both objects then transforms the child twice (feet ended at z=0.55). Detach for the normalize,
    # re-parent afterwards. Unparented GLBs (Wren/Tuba) take the old path unchanged.
    mesh_par = mesh.parent
    if mesh_par is not None:
        mw_ = mesh.matrix_world.copy()
        mesh.parent = None
        mesh.matrix_world = mw_
    pts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    s = 1 / (max(p.z for p in pts) - min(p.z for p in pts))
    for ob in (arm, mesh):
        bpy.ops.object.select_all(action="DESELECT")
        ob.scale *= s
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    pts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    off = Vector((-(min(p.x for p in pts) + max(p.x for p in pts)) / 2, 0, -min(p.z for p in pts)))
    for ob in (arm, mesh):
        bpy.ops.object.select_all(action="DESELECT")
        ob.location += off
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    if mesh_par is not None:
        mesh.parent = arm
        mesh.matrix_parent_inverse = arm.matrix_world.inverted()
    fwd = _bl.toe_forward(arm)
    print("TOE_FORWARD", None if fwd is None else tuple(round(x, 3) for x in fwd))
    if fwd is not None and fwd.dot(Vector((0, -1, 0))) < 0.9:
        ang = math.atan2(fwd.x, -fwd.y)  # rotate so that fwd -> -Y
        R = Matrix.Rotation(ang, 4, "Z")
        mesh.data.transform(R)
        arm.data.transform(R)
        print("ROTATED_TO_MINUS_Y deg", round(math.degrees(ang), 1))

    # --- skeleton fixes ---
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    # rig.mirror_skip (optional, 10-09 Tuba): bone-name substrings that keep Tripo's own placement instead of the
    # left/right average. Tuba's mechanical right arm is bigger and mounted higher than his organic left arm; the
    # average moved the mech shoulder pivot 5% of the height off the shell.
    msk = rc.get("mirror_skip", [])
    for ln in [b.name for b in eb if "Left" in b.name]:
        rn = ln.replace("Left", "Right")
        if rn not in eb or any(k in ln for k in msk):
            continue
        L, R_ = eb[ln], eb[rn]
        hh = (L.head + Vector((-R_.head.x, R_.head.y, R_.head.z))) / 2
        tt = (L.tail + Vector((-R_.tail.x, R_.tail.y, R_.tail.z))) / 2
        L.head, L.tail = hh, tt
        R_.head, R_.tail = Vector((-hh.x, hh.y, hh.z)), Vector((-tt.x, tt.y, tt.z))
        L.roll = R_.roll = 0
    for n in (("mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2") if rc.get("straighten_spine", True) else ()):
        if n in eb:
            b = eb[n]
            b.tail.x, b.tail.y = b.head.x, b.head.y
    if rc.get("straighten_legs", True):
        for side in ("Left", "Right"):
            u, l = eb.get(f"mixamorig:{side}UpLeg"), eb.get(f"mixamorig:{side}Leg")
            if u and l:
                sign = 1 if side == "Left" else -1
                u.tail.x = u.head.x + sign * .006
                u.tail.y = u.head.y
                l.head = u.tail.copy()
    wp = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    fy = [p.y for p in wp if p.z < .12]
    heel, toe = max(fy), min(fy)
    ball = heel - rc.get("toe_ball_fraction", 0.70) * (heel - toe)
    for side in ("Left", "Right"):
        f, t = eb.get(f"mixamorig:{side}Foot"), eb.get(f"mixamorig:{side}ToeBase")
        if f and t:
            delta = t.tail - t.head
            f.tail.y = ball
            t.head = f.tail.copy()
            t.tail = t.head + delta

    # rig.bone_overrides {bone: {head, tail}} (optional, 10-09 Tuba): Tripo placed the mechanical arm's elbow/wrist
    # 11 cm off the machine's joint hubs (measured from the dark hub rings), so the hard-bound panels bent in the wrong
    # place. Joints go where the mesh's pivots are; connected neighbours follow.
    w2l = arm.matrix_world.inverted()  # overrides are in the normalized WORLD space the probes measure in
    _mz = [(mesh.matrix_world @ v.co).z for v in mesh.data.vertices]
    _hips = eb["mixamorig:Hips"].head.copy()
    print("ARM_WORLD_SCALE", tuple(round(x, 4) for x in arm.matrix_world.to_scale()), "MESH_H", round(max(_mz) - min(_mz), 4), "HIPS", tuple(round(x, 4) for x in _hips))
    for bn, ov in rc.get("bone_overrides", {}).items():
        b = eb.get(bn)
        if b is None:
            continue
        # the rig is renormalized once more at the end (the mesh is still 1.11 tall here: it inherited the armature
        # scale), so map final-space numbers into the current space: x mh, feet at min z
        _mh, _z0 = max(_mz) - min(_mz), min(_mz)
        ov = {k_: w2l @ (Vector(v_) * _mh + Vector((0, 0, _z0))) for k_, v_ in ov.items()}
        if "head" in ov:
            b.head = Vector(ov["head"])
            if b.parent is not None and b.use_connect:
                b.parent.tail = b.head.copy()
        if "tail" in ov:
            b.tail = Vector(ov["tail"])
            for c in b.children:
                if c.use_connect:
                    c.head = b.tail.copy()
    # rig.finger_mirror {side, scale} (optional, 10-09 Tuba): Tripo laid the mechanical hand's finger bones out back to
    # front (index behind little finger) -> the gun pose computed the palm facing outward = reverse grip. Rebuild that
    # hand's finger chains from the other hand's layout: mirrored, scaled, rotated onto this hand's direction.
    fm = rc.get("finger_mirror")
    if fm:
        dst = fm["side"]
        srcs = "Left" if dst == "Right" else "Right"
        hs_, hd_ = eb[f"mixamorig:{srcs}Hand"], eb[f"mixamorig:{dst}Hand"]
        mir = lambda v: Vector((-v.x, v.y, v.z))
        q = mir(hs_.tail - hs_.head).normalized().rotation_difference((hd_.tail - hd_.head).normalized())
        k = fm.get("scale", 1.0)
        for b in [b for b in eb if b.name.startswith(f"mixamorig:{srcs}Hand") and b.name != f"mixamorig:{srcs}Hand"]:
            t = eb.get(b.name.replace(srcs, dst))
            if t is None:
                continue
            t.use_connect = False
            t.head = hd_.head + q @ (mir(b.head - hs_.head) * k)
            t.tail = hd_.head + q @ (mir(b.tail - hs_.head) * k)
            t.roll = 0

    def add_chain(names, points, parent, tip=True):
        prev = eb[parent]
        for n, pa, pb in zip(names, points[:-1], points[1:]):
            q = eb.new(n)
            q.head, q.tail, q.parent, q.use_deform, q.roll = Vector(pa), Vector(pb), prev, True, 0
            prev = q
        if tip and rc.get("add_chain_tips", True):
            d = Vector(points[-1]) - Vector(points[-2])
            q = eb.new(names[-1] + "_Tip")
            q.head, q.tail, q.parent, q.use_deform = Vector(points[-1]), Vector(points[-1]) + d * 0.35, prev, False

    chains = []  # (spec, side, names, points)
    for c in rc.get("chains", []):
        sides = [("L", 1), ("R", -1)] if c.get("mirror") else [("", 1)]
        for sname, sgn in sides:
            nm = c["name"].replace("{S}", sname)
            ptsc = [Vector((p[0] * sgn, p[1], p[2])) for p in c["points"]]
            names = [f"{nm}_{i:02d}" for i in range(1, c["bones"] + 1)]
            if len(ptsc) != c["bones"] + 1:
                raise SystemExit(f"chain {nm}: points must be bones+1")
            add_chain(names, ptsc, c["parent"])
            chains.append((c, sgn, names, ptsc))
    sk = rc.get("skirt")
    skirt_names = []
    if sk:
        cx, cy = sk["center_xy"]
        rx, ry = sk["ring_radius_xy"]
        for i in range(sk["sectors"]):
            a = 2 * math.pi * i / sk["sectors"]
            x, y = rx * math.sin(a), cy + ry * math.cos(a)
            p3 = [(cx + x * f, y * f, z) for f, z in zip(sk["flare"], sk["ring_z"])]
            names = [f"{sk['name']}_{i:02d}_{j:02d}" for j in range(1, len(p3))]
            add_chain(names, p3, sk["parent"])
            skirt_names.append(names)
    # rig.sleeve_chain (optional, 10-08 Vesper wide haori sleeves): a short chain hanging from the forearm that
    # carries the loose cuff part of the sleeve, so a SpringBone can let it drape when the arm lifts. It runs along
    # the forearm from s=start (s: 0 shoulder, 1 elbow, 2 wrist) to s=end past the wrist, where the cuff ends.
    sc_ = rc.get("sleeve_chain")
    sleeve_chains = {}  # side -> (names, points)
    if sc_:
        for side, sname in (("Left", "L"), ("Right", "R")):
            e0, e1 = eb[f"mixamorig:{side}ForeArm"].head.copy(), eb[f"mixamorig:{side}ForeArm"].tail.copy()
            d = e1 - e0
            ss = [sc_["start"]] + [sc_["start"] + (sc_["end"] - sc_["start"]) * (k + 1) / sc_["bones"] for k in range(sc_["bones"])]
            cp = [e0 + d * (s_ - 1) for s_ in ss]
            names = [f"{sc_.get('name', 'Sleeve_{S}').replace('{S}', sname)}_{k:02d}" for k in range(1, sc_["bones"] + 1)]
            add_chain(names, [tuple(p) for p in cp], f"mixamorig:{side}ForeArm")
            sleeve_chains[side] = (names, cp)
    for rg in rc.get("rigid", []):
        add_chain([rg["bone"]], [rg["head"], rg["tail"]], rg["parent"])
    hand = eb.get("mixamorig:RightHand")
    if hand and rc.get("prop_bone"):
        p = eb.new(rc["prop_bone"])
        p.head = (hand.head + hand.tail) / 2
        p.tail = p.head + Vector((0, -.055, 0))
        p.parent, p.use_deform = hand, False
    for b in eb:
        if b.name.endswith("_End") or (b.name.endswith("4") and "Hand" in b.name):
            b.use_deform = False
    bpy.ops.object.mode_set(mode="OBJECT")

    # --- weights ---
    bones = {b.name: b for b in arm.data.bones}
    idx = {g.index: g.name for g in mesh.vertex_groups}
    pts = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    hipz = (arm.matrix_world @ bones["mixamorig:Hips"].head_local).z
    data = [{idx[g.group]: g.weight for g in v.groups if g.group in idx and g.weight > 1e-7} for v in mesh.data.vertices]
    ORIG = [dict(d) for d in data]  # Tripo's own weights, for rules that need the original limb ownership
    for n in bones:
        if mesh.vertex_groups.get(n) is None:
            mesh.vertex_groups.new(name=n)

    tex_path = o.get("texture")
    if tex_path:
        img = bpy.data.images.load(os.path.abspath(tex_path), check_existing=False)
        texsrc = "given: " + tex_path
    else:
        img = max((x for x in bpy.data.images if x.size[0] > 0), key=lambda x: x.size[0] * x.size[1])
        texsrc = f"embedded {img.name} {tuple(img.size)}"
    IW, IH = img.size
    PX = list(img.pixels)
    uvl = mesh.data.uv_layers.active.data
    vuv = [None] * len(mesh.data.vertices)
    for lp in mesh.data.loops:
        if vuv[lp.vertex_index] is None:
            vuv[lp.vertex_index] = uvl[lp.index].uv.copy()

    def vcol(i):
        u = vuv[i]
        if u is None:
            return (0, 0, 0)
        x = min(IW - 1, max(0, int((u.x % 1) * IW)))
        y = min(IH - 1, max(0, int((u.y % 1) * IH)))
        k = (y * IW + x) * 4
        return PX[k], PX[k + 1], PX[k + 2]

    # rig.garment_arm_strip {region, v_max, s_max, to} (optional, 10-09 Vesper v4): a SLEEVELESS top's fabric around the
    # armhole gets Tripo arm weight and is dragged up like a sleeve when the arms lift. Fabric picked by colour (dark,
    # low saturation) inside a torso region loses all arm weight to the spine; the bare skin keeps following the arm.
    gas = rc.get("garment_arm_strip")

    # colour test is optional (v_max/s_max); absx_fade [x0, x1] keeps arm weight in proportion beyond x0 (full at x1) so the
    # armhole edge is a soft band, not a tear. Vesper v4: the charcoal jacket is too close to the black top in colour,
    # so the top is picked by position (inside the shoulder joints) instead.
    def garment_strip_hit(i, pt):
        if not gas or not in_region(pt, gas["region"]):
            return False
        h_, s_, v_ = colorsys.rgb_to_hsv(*vcol(i))
        if gas.get("skip_s_min") is not None and s_ >= gas["skip_s_min"] and gas.get("skip_hue", [0, 1])[0] <= h_ <= gas.get("skip_hue", [0, 1])[1]:
            return False  # e.g. the jacket's saturated indigo lining that hugs the torso stays with the arm
        return v_ <= gas.get("v_max", 1.0) and s_ <= gas.get("s_max", 1.0)

    def garment_strip_apply(w, pt):
        fx = gas.get("absx_fade")
        keep = 0.0 if not fx else smooth01(fx[0], fx[1], abs(pt.x))
        # absx_fade_z_min (optional, 10-09 Harrow): the soft armhole band only above this height; below the armpit a
        # sleeveless vest's side panels keep no arm weight at all (the sleeve under it is told apart by colour)
        if fx and gas.get("absx_fade_z_min") is not None and pt.z < gas["absx_fade_z_min"]:
            keep = 0.0
        # arm_dist_keep [d_full, d_none] (optional, 10-09 Harrow): Tripo welds the vest armhole to the sleeve under it;
        # fabric this close to an arm bone keeps its arm weight in proportion, so the weld band bends instead of tearing
        ad = gas.get("arm_dist_keep")
        if ad and pt.z > gas.get("arm_dist_z_min", -1):   # only around the armhole, not where the A-pose elbow hangs
            d_ = min(segdist(pt, a_seg, b_seg) for a_seg, b_seg in arm_segs)
            kd_ = max(0.0, min(1.0, (ad[1] - d_) / (ad[1] - ad[0])))
            keep = max(keep, kd_ * kd_ * (3 - 2 * kd_))
        if keep >= 1.0:
            return w
        mv = sum(v * (1 - keep) for n, v in w.items() if any(k in n for k in ARMKEYS))
        w = {n: (v * keep if any(k in n for k in ARMKEYS) else v) for n, v in w.items()}
        # nearest spine segment by height (a single target bone puts the lower fabric > 12% from it = far weights)
        to = "mixamorig:Spine"
        for zt, bn in gas.get("spine_by_z", [[0.68, "mixamorig:Spine1"], [0.76, "mixamorig:Spine2"]]):
            if pt.z > zt:
                to = bn
        w[to] = w.get(to, 0) + mv
        return w

    # rig.colour_lock [ {region, hsv: [[h0_deg, h1_deg, s_min, v_min, v_max], ...], to_by_z, post} ] (optional,
    # 10-09 Harrow): a cross-body sling / belt picked by its leather colour gets Tripo arm and thigh weight and is
    # dragged into a big flap when an arm lifts or a leg strides. Every arm/leg weight on those vertices moves to the
    # torso bone at that height (to_by_z: [[z_from, bone], ...], highest matching z_from wins).
    clr = rc.get("colour_lock") or []

    def colour_lock_rule(i, pt):
        for rule in clr:
            if not in_region(pt, rule["region"]):
                continue
            c_ = vcol(i); mx_, mn_ = max(c_), min(c_)
            sat_ = (mx_ - mn_) / (mx_ + 1e-6)
            if mx_ == mn_:
                hue_ = 0.0
            elif mx_ == c_[0]:
                hue_ = (60 * (c_[1] - c_[2]) / (mx_ - mn_)) % 360
            elif mx_ == c_[1]:
                hue_ = 60 * (c_[2] - c_[0]) / (mx_ - mn_) + 120
            else:
                hue_ = 60 * (c_[0] - c_[1]) / (mx_ - mn_) + 240
            if any(h0 <= hue_ <= h1 and sat_ >= s0 and v0 <= mx_ <= v1 for h0, h1, s0, v0, v1 in rule["hsv"]):
                return rule
        return None

    def colour_lock_apply(w, pt, rule):
        # gloves are leather too: anything the hand drives is left alone
        if sum(v for n, v in w.items() if "Hand" in n) > rule.get("hand_max", 0.15):
            return w
        fa_ = rule.get("forearm_dist")          # forearm skin in shadow: judged by distance to the forearm bone, not
        if fa_ and min(segdist(pt, arm.matrix_world @ bones[n].head_local, arm.matrix_world @ bones[n].tail_local)   # by
                       for n in ("mixamorig:LeftForeArm", "mixamorig:RightForeArm") if n in bones) < fa_:     # weight
            return w
        to = rule["to_by_z"][0][1]
        for zt, bn in rule["to_by_z"]:
            if pt.z >= zt:
                to = bn
        # rule.shoulders (optional, 10-09 Harrow stand collar): clavicle weights move too
        def lim_(n):
            return any(k in n for k in ARMKEYS) or "Leg" in n or "Foot" in n or "Toe" in n or (rule.get("shoulders") and "Shoulder" in n)
        mv = sum(v for n, v in w.items() if lim_(n))
        if mv <= 0:
            return w
        w = {n: v for n, v in w.items() if not lim_(n)}
        w[to] = w.get(to, 0) + mv
        return w

    SKIRT = [False] * len(pts)
    if sk:
        cr = sk["colour_rule"]

        def is_fabric(c):
            mx, mn = max(c), min(c)
            sat = (mx - mn) / (mx + 1e-6)
            # colour_rule.r_minus_g_min (optional, 10-09 Tuba): leather apron = red clearly above green (the green hide
            # and the cream belly in the same band fail it)
            return (mx > cr["v_min"] and (sat >= cr.get("also_sat_min", 9) or (sat < cr["sat_max"] and c[0] >= c[2] + cr["r_minus_b_min"]
                    and c[0] <= c[2] + cr.get("r_minus_b_max", 9))) and c[0] >= c[1] + cr.get("r_minus_g_min", -9))
        nbrs = [[] for _ in pts]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            nbrs[a_].append(b_)
            nbrs[b_].append(a_)
        band = [(sk["band_z"][0] < p.z < sk["band_z"][1] and math.hypot(p.x - sk["center_xy"][0], p.y - sk["center_xy"][1]) > sk["radial_min"]) for p in pts]
        if sk.get("thin_max") is not None:
            from mathutils.bvhtree import BVHTree
            bvh_ = BVHTree.FromPolygons(pts, [tuple(f_.vertices) for f_ in mesh.data.polygons])
            nmat_ = mesh.matrix_world.to_3x3().inverted().transposed()
            thick_ = []
            for i, v_ in enumerate(mesh.data.vertices):
                d_ = -(nmat_ @ v_.normal).normalized()
                h_ = bvh_.ray_cast(pts[i] + d_ * 0.001, d_)
                thick_.append(h_[3] + 0.001 if h_[0] is not None else float("inf"))
            lab = [band[i] and thick_[i] <= sk["thin_max"] for i in range(len(pts))]
        else:
            lab = [band[i] and is_fabric(vcol(i)) for i in range(len(pts))]
        for _ in range(sk.get("vote_iters", 4)):
            new = list(lab)
            for i in range(len(pts)):
                if not band[i] or not nbrs[i]:
                    continue
                k = sum(1 for j in nbrs[i] if lab[j])
                new[i] = k * 2 > len(nbrs[i]) or (lab[i] and k * 3 >= len(nbrs[i]))
            lab = new
        SKIRT = lab
        print("SKIRT_CLASSIFY", json.dumps({"band": sum(band), "fabric": sum(1 for i in range(len(pts)) if band[i] and is_fabric(vcol(i))), "after_vote": sum(lab)}))

    def segdist(p, a_, b_):
        ab = b_ - a_
        if ab.length_squared < 1e-12:
            return (p - a_).length
        return (p - (a_ + ab * max(0, min(1, (p - a_).dot(ab) / ab.length_squared)))).length

    arm_segs = [(arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local)
                for n, b in bones.items() if n.startswith("mixamorig:") and any(k in n for k in ARMKEYS)]
    # rig.sleeve_flood (optional, wide sleeves on a long coat - Vesper): find each sleeve by MESH CONNECTIVITY,
    # flooding from the vertices around the forearm below z_cap (the armhole). Position rules could not separate the
    # inner sleeve panel from the coat side (it hangs right next to it) and a soft blend left that panel at the hip
    # when the arm lifted (a black blade in the Gear page idle).
    SLEEVE = set()
    HANDV = set()
    sf = rc.get("sleeve_flood")
    if sf:
        enb = [[] for _ in pts]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            enb[a_].append(b_)
            enb[b_].append(a_)
        # sleeve_flood.sides (optional, 10-09 Tuba): only these arms (his mechanical right arm keeps Tripo + hard_skin)
        for side in sf.get("sides", ["Left", "Right"]):
            fa = [s for n, s in zip([n for n, b in bones.items() if n.startswith("mixamorig:") and any(k in n for k in ARMKEYS)], arm_segs)
                  if n.startswith(f"mixamorig:{side}ForeArm")]
            sgn_ok = (lambda x: x > 0) if side == "Left" else (lambda x: x < 0)
            sidesegs = [sg for n, sg in zip([n for n, b in bones.items() if n.startswith("mixamorig:") and any(k in n for k in ARMKEYS)], arm_segs)
                        if n.startswith(f"mixamorig:{side}")]
            seeds = [i for i, p in enumerate(pts) if p.z < sf["z_cap"] and abs(p.x) > sf.get("seed_absx", 0.12)
                     and sgn_ok(p.x) and min(segdist(p, a_s, b_s) for a_s, b_s in fa) < sf.get("seed_dist", 0.05)]
            stack, seen = list(seeds), set(seeds)
            while stack:
                v = stack.pop()
                for j in enb[v]:
                    # sleeve_flood.max_dist (optional, 10-09 Tuba): stay within this distance of the arm bones (his hand
                    # is welded to a cloth flap and the belly side; the flood used to run into them)
                    # sleeve_flood.exclude_white (10-09 Tuba): the tucked white cloth touches the hand; never flood into it
                    if sf.get("exclude_white") and min(vcol(j)) > 0.62:
                        continue
                    if j not in seen and pts[j].z < sf["z_cap"] and sgn_ok(pts[j].x) and (
                            "max_dist" not in sf or min(segdist(pts[j], a_s, b_s) for a_s, b_s in sidesegs) < sf["max_dist"]):
                        seen.add(j)
                        stack.append(j)
            SLEEVE |= seen
        if sf.get("exclude_hand"):
            # the flood runs through the wrist into the hand; hands keep Tripo's own weights (10-08 Vesper)
            hand_v = {i for i in SLEEVE if data[i] and "Hand" in max(data[i], key=data[i].get)}
            SLEEVE -= hand_v
            HANDV |= hand_v
            print("SLEEVE_FLOOD_HAND_EXCLUDED", len(hand_v))
        print("SLEEVE_FLOOD", len(SLEEVE))

    def arm_param(p, side):
        """s along shoulder->elbow->wrist: 0..1 upper arm, 1..2 forearm, > 2 past the wrist (cuff)."""
        a0 = arm.matrix_world @ bones[f"mixamorig:{side}Arm"].head_local
        a1 = arm.matrix_world @ bones[f"mixamorig:{side}ForeArm"].head_local
        a2 = arm.matrix_world @ bones[f"mixamorig:{side}ForeArm"].tail_local
        best = None
        for k, (x0, x1) in enumerate(((a0, a1), (a1, a2))):
            ab = x1 - x0
            t = (p - x0).dot(ab) / ab.length_squared
            tc = max(0.0, min(1.0, t))
            dd = (p - (x0 + ab * tc)).length
            if best is None or dd < best[0]:
                best = (dd, k + (t if k == 1 and t > 1 else tc))
        return best[1]

    def smooth01(e0, e1, x):
        t = max(0.0, min(1.0, (x - e0) / (e1 - e0)))
        return t * t * (3 - 2 * t)
    # colour_lock.vote (optional): per-vertex texel colour misses the sling's shadowed edges, so half the strap stayed
    # on the arm and tore into strands. Seed by colour, then neighbour-majority votes over the mesh (UV-split copies
    # count as neighbours) fill the holes so the whole strap is locked as one piece.
    CL_MEMBER = {}
    if clr:
        cadj = [set() for _ in pts]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            cadj[a_].add(b_); cadj[b_].add(a_)
        ckey = {}
        for vi, v in enumerate(mesh.data.vertices):
            ckey.setdefault(tuple(round(c, 5) for c in v.co), []).append(vi)
        for g_ in ckey.values():
            for vi in g_:
                cadj[vi].update(x for x in g_ if x != vi)
        for ri, rule in enumerate(clr):
            inreg = [in_region(pts[i], rule["region"]) for i in range(len(pts))]
            lab = [inreg[i] and colour_lock_rule(i, pts[i]) is rule for i in range(len(pts))]
            for _ in range(int(rule.get("vote", 0))):
                new = list(lab)
                for i in range(len(pts)):
                    if not inreg[i] or not cadj[i]:
                        continue
                    k = sum(1 for j in cadj[i] if lab[j])
                    new[i] = k * 2 >= len(cadj[i]) or (lab[i] and k * 4 >= len(cadj[i]))
                lab = new
            for i in range(len(pts)):
                if lab[i]:
                    CL_MEMBER.setdefault(i, rule)
        print("COLOUR_LOCK_MEMBERS", len(CL_MEMBER))

    counts = {"chains": {}, "skirt": 0, "rigid": 0, "straps": 0}
    TAG = ["body"] * len(pts)
    secondary = set()
    measured = set()  # secondary but still inside the body stretch gate (sleeve chain: not exempt from the audit)
    rigid_idx = set()
    rigid = rc.get("rigid", [])
    st = rc.get("straps")
    rigid_bone = st.get("rigid") if st else None
    for i, (pt, w) in enumerate(zip(pts, data)):
        orig = dict(w)
        armw = sum(v for n, v in w.items() if any(k in n for k in ARMKEYS))
        headish = sum(v for n, v in w.items() if n in head_bones)
        done = False
        for c, sgn, names, cpts in chains:
            req = c.get("require", {})
            reqb = head_bones if req.get("bones") == "head_bones" else req.get("bones", [])
            if reqb and sum(orig.get(n, 0) for n in reqb) < req.get("min", 0):
                continue
            if not in_region(pt, c["region"], sgn):
                continue
            u = poly_param(pt, cpts)
            if c.get("mode", "full") == "partial":
                pw = c.get("parent_weight", 0.8)
                w = {c["parent"]: pw}
                for n, v in chain_weights(u, names, 1 - pw).items():
                    w[n] = w.get(n, 0) + v
            else:
                w = chain_weights(u, names)
            counts["chains"][names[0]] = counts["chains"].get(names[0], 0) + 1
            TAG[i] = "chain"
            secondary.add(i)
            done = True
            break
        # skirt.arm_keep_radius (optional): hands hanging inside the skirt band (Vesper's long coat) stay on their arm
        # bones, judged by distance to the arm bone segments, NOT by Tripo's arm weight (Tripo smears arm weight
        # over the whole coat panel next to the hand, which is exactly what tears the coat when the arms lift)
        if not done and sk and SKIRT[i] and i not in SLEEVE and not (sk.get("arm_keep_radius") and min(
                segdist(pt, a_seg, b_seg) for a_seg, b_seg in arm_segs) < sk["arm_keep_radius"]):
            a_ = math.atan2(pt.x - sk["center_xy"][0], pt.y - sk["center_xy"][1]) % (2 * math.pi)
            q = a_ / (2 * math.pi / sk["sectors"])
            s0 = int(math.floor(q)) % sk["sectors"]
            s1 = (s0 + 1) % sk["sectors"]
            af = q - math.floor(q)
            z0, z1 = sk["ring_z"][0], sk["ring_z"][-1]
            nb = len(sk["ring_z"]) - 1
            u = max(0, min(1, (z0 - pt.z) / (z0 - z1))) * nb
            hw = sk.get("hips_weight", 0.45)
            w = {sk["parent"]: hw}
            for sec, aw in ((s0, 1 - af), (s1, af)):
                for n, v in chain_weights(u, skirt_names[sec], (1 - hw) * aw).items():
                    w[n] = w.get(n, 0) + v
            if sk.get("top_ramp"):
                # skirt.top_ramp (optional, 10-08 Vesper long coat): the coat continues above the ring top, so a hard
                # switch to Hips+ring at z0 is a weight cliff across the whole coat. Fade in from the vertex's own torso
                # weights (arm weight -> Spine, leg weight -> Hips) over top_ramp below z0.
                t_ = max(0.0, min(1.0, (z0 - pt.z) / sk["top_ramp"]))
                t_ = t_ * t_ * (3 - 2 * t_)
                if t_ < 1:
                    tw = {}
                    for n, v in orig.items():
                        if any(k in n for k in ARMKEYS):
                            n = "mixamorig:Spine"
                        elif "Leg" in n or "Foot" in n:
                            n = "mixamorig:Hips"
                        tw[n] = tw.get(n, 0) + v
                    tt_ = sum(tw.values()) or 1
                    w = {n: t_ * w.get(n, 0) + (1 - t_) * tw.get(n, 0) / tt_ for n in set(w) | set(tw)}
            counts["skirt"] += 1
            TAG[i] = "skirt"
            secondary.add(i)
        hit_rigid = False
        for rg in rigid:
            cap = rg.get("capsule_radius")  # long diagonal parts (a rifle across the back): distance to the bone segment
            if cap and segdist(pt, Vector(rg["head"]), Vector(rg["tail"])) > cap:
                continue
            # rigid.skip_hair (optional, 10-08 Rook): a helmet behind the head overlaps the back hair; vertices whose
            # texture is warm dark brown (hair) stay on the head instead of being welded to the helmet bone.
            sh = rg.get("skip_hair")
            if sh:
                c_ = vcol(i); mx_, mn_ = max(c_), min(c_); sat_ = (mx_ - mn_) / (mx_ + 1e-6)
                if mx_ < sh.get("v_max", 0.6) and sat_ > sh.get("s_min", 0.3) and c_[0] > c_[2]:
                    continue
            # rigid.hsv_any (optional, 10-09 Tuba): only vertices whose texture colour matches one of
            # [h_min_deg, h_max_deg, s_min, v_min] (the brass scale on the hip, not the apron/belly in the same box)
            hv = rg.get("hsv_any")
            if hv:
                c_ = vcol(i); mx_, mn_ = max(c_), min(c_)
                sat_ = (mx_ - mn_) / (mx_ + 1e-6)
                if mx_ == mn_:
                    hue_ = 0.0
                elif mx_ == c_[0]:
                    hue_ = (60 * (c_[1] - c_[2]) / (mx_ - mn_)) % 360
                elif mx_ == c_[1]:
                    hue_ = 60 * (c_[2] - c_[0]) / (mx_ - mn_) + 120
                else:
                    hue_ = 60 * (c_[0] - c_[1]) / (mx_ - mn_) + 240
                if not any(h0 <= hue_ <= h1 and sat_ >= s0 and mx_ >= v0 for h0, h1, s0, v0 in hv):
                    continue
            if in_region(pt, rg["region"]) and headish < rg.get("max_head", 0.2):
                w = {rg["bone"]: 1.0}
                counts["rigid"] += 1
                TAG[i] = "rigid"
                secondary.add(i)
                rigid_idx.add(i)
                hit_rigid = True
                break
        if not hit_rigid and st:
            torso = sum(w.get(n, 0) for n in ("mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:LeftShoulder", "mixamorig:RightShoulder"))
            if in_region(pt, st["region"]) and headish < st.get("max_head", 0.2) and armw < st.get("max_arm", 0.3):
                removed_w = sum(w.pop(n, 0) for n in list(w) if "Arm" in n or "ForeArm" in n)
                if removed_w or torso > .15:
                    clav = f"mixamorig:{'Left' if pt.x > 0 else 'Right'}Shoulder"
                    z0, zr = st.get("clav_ramp_z", [0.55, 0.24])
                    zf = max(0, min(1, (pt.z - z0) / zr))
                    sw = st["weights"]
                    w = {"mixamorig:Spine2": sw["mixamorig:Spine2"], rigid_bone: sw["rigid"], clav: sw["clavicle"] * zf}
                    counts["straps"] += 1
                    TAG[i] = "strap"
                    secondary.add(i)
            elif (st.get("shell_region") and in_region(pt, st["shell_region"]) and headish < st.get("max_head", 0.2)
                  and armw < st.get("max_arm", 0.3)
                  and sum(v for n, v in orig.items() if any(k in n for k in ("Spine", "Shoulder", "Arm"))) > st.get("shell_min_torso", 0.12)):
                w = {"mixamorig:Spine2": st["shell_weights"]["mixamorig:Spine2"], rigid_bone: st["shell_weights"]["rigid"]}
                counts["straps"] += 1
                TAG[i] = "strap"
                secondary.add(i)
        # rig.torso_arm_strip (optional): torso garment (a long open coat) between armpit and waist carries Tripo arm
        # weight and spikes out when the elbows bend; strip arm weight from vertices inside the torso width that are
        # not close to any arm bone. Wide sleeves sit outside |x| > absx_max and keep their arm weights.
        # Soft, not a hard cut: a hard boundary tears the armpit (half the vertices on Spine, their neighbours on the arm).
        tas = rc.get("torso_arm_strip")
        if sf and i not in secondary:
            if i in SLEEVE:
                keepw = {n: v for n, v in orig.items() if any(k in n for k in ARMKEYS) or "Shoulder" in n}
                rw = sf.get("reweight")
                if rw:
                    # 10-08 Vesper: Tripo smears ~50% upper-arm weight down the whole wide sleeve to the cuff, so the
                    # lower sleeve tears when the elbow bends and sits > 12% from its bone. Weight the sleeve by its
                    # position along the arm instead: upper arm -> Arm, forearm -> ForeArm, a smooth elbow band; near
                    # the armhole fade back to Tripo's own (shoulder) weights so the coat body joint is unchanged.
                    side = "Left" if pt.x > 0 else "Right"
                    s_ = arm_param(pt, side)
                    f = smooth01(1 - rw["elbow_blend"], 1 + rw["elbow_blend"], s_)
                    base = {f"mixamorig:{side}Arm": 1 - f, f"mixamorig:{side}ForeArm": f}
                    k_ = smooth01(rw["top_blend"][0], rw["top_blend"][1], s_)
                    nat = keepw or base
                    nt_ = sum(nat.values()) or 1
                    w = {n: (1 - k_) * nat.get(n, 0) / nt_ + k_ * base.get(n, 0) for n in set(nat) | set(base)}
                    if sc_ and side in sleeve_chains and s_ > sc_["start"]:
                        names, cp = sleeve_chains[side]
                        g_ = smooth01(sc_["start"], sc_["full"], s_)
                        pw = sc_.get("parent_weight", 0.4)
                        cw = {f"mixamorig:{side}ForeArm": pw}
                        for n, v in chain_weights(poly_param(pt, cp), names, 1 - pw).items():
                            cw[n] = cw.get(n, 0) + v
                        w = {n: (1 - g_) * w.get(n, 0) + g_ * cw.get(n, 0) for n in set(w) | set(cw)}
                        if g_ > 0:
                            secondary.add(i)
                            measured.add(i)
                            counts["sleeve_chain"] = counts.get("sleeve_chain", 0) + 1
                            TAG[i] = "sleeve_chain"
                    counts["sleeve"] = counts.get("sleeve", 0) + 1
                    if TAG[i] != "sleeve_chain":
                        TAG[i] = "sleeve"
                elif keepw:
                    w = keepw
                    counts["sleeve"] = counts.get("sleeve", 0) + 1
                    TAG[i] = "sleeve"
            elif i not in HANDV and sf["torso_z"][0] < pt.z < sf["torso_z"][1] and any(any(k in n for k in ARMKEYS) for n in w)                     and ("Left" if pt.x > 0 else "Right") in sf.get("sides", ["Left", "Right"])                     and not (sf.get("keep_hand_dominant") and orig and "Hand" in max(orig, key=orig.get) and min(vcol(i)) < 0.62):
                # sleeve_flood.keep_hand_dominant (10-09 Tuba): the palm side touching the belly was missed by the flood,
                # stripped, and opened black holes in the hand as soon as the elbow moved
                # sleeve_flood.torso_fade (optional) [z_full, z_none]: strip fully below z_full, fade to Tripo's own
                # weights at z_none (the armpit), so the armhole joint stays Tripo's smooth native blend.
                tf = sf.get("torso_fade")
                keep_ = 0.0 if not tf else max(0.0, min(1.0, (pt.z - tf[0]) / (tf[1] - tf[0])))
                keep_ = keep_ * keep_ * (3 - 2 * keep_)
                # what is kept follows the UPPER arm only: the coat side hangs next to the forearm/hand and Tripo gives
                # it forearm weight, which is what spiked it out when the elbows bent
                armtot = sum(v for n, v in w.items() if any(k in n for k in ARMKEYS))
                moved = armtot * (1 - keep_)
                w = {n: v for n, v in w.items() if not any(k in n for k in ARMKEYS)}
                if keep_ > 0:
                    ua_ = f"mixamorig:{'Left' if pt.x > 0 else 'Right'}Arm"
                    w[ua_] = w.get(ua_, 0) + armtot * keep_
                tb = "mixamorig:Spine1" if pt.z > sf.get("spine_split_z", 0.62) else "mixamorig:Spine"
                if pt.z < sf.get("hips_split_z", -1):  # 10-09 Tuba: belt-level items follow the Hips like the apron
                    tb = "mixamorig:Hips"
                w[tb] = w.get(tb, 0) + moved
                counts["coat_arm_strip"] = counts.get("coat_arm_strip", 0) + 1
                TAG[i] = "coat_strip"
        elif tas and i not in secondary and tas["z"][0] < pt.z < tas["z"][1] and any(any(k in n for k in ARMKEYS) for n in w):
            d = min(segdist(pt, a_seg, b_seg) for a_seg, b_seg in arm_segs)
            d0, d1 = tas["arm_dist"] if "arm_dist" in tas else (tas["min_arm_dist"] - 0.02, tas["min_arm_dist"] + 0.03)
            x0, x1 = tas["absx"] if "absx" in tas else (tas["absx_max"] - 0.03, tas["absx_max"] + 0.02)
            keep = max(max(0.0, min(1.0, (d1 - d) / (d1 - d0))), max(0.0, min(1.0, (abs(pt.x) - x0) / (x1 - x0))))
            armnow = sum(v for n, v in w.items() if any(k in n for k in ARMKEYS))
            if keep >= 1.0 and tas.get("sleeve_full_arm") and pt.z < tas["sleeve_full_arm"]["z_max"] \
                    and armnow >= tas["sleeve_full_arm"].get("min_arm", 0.25):
                # wide sleeve outside the torso: torso/hip weight stretches it into strands when the arm lifts
                w = {n: v for n, v in w.items() if any(k in n for k in ARMKEYS)}
                counts["sleeve_full_arm"] = counts.get("sleeve_full_arm", 0) + 1
            elif keep < 1.0:
                torso_bone = "mixamorig:Spine1" if pt.z > tas.get("spine_split_z", 0.62) else "mixamorig:Spine"
                moved = 0.0
                for n in list(w):
                    if any(k in n for k in ARMKEYS):
                        moved += w[n] * (1 - keep)
                        w[n] *= keep
                w[torso_bone] = w.get(torso_bone, 0) + moved
                counts["torso_arm_strip"] = counts.get("torso_arm_strip", 0) + 1
                TAG[i] = "torso_strip"
        if i not in secondary and garment_strip_hit(i, pt) and any(any(k in n for k in ARMKEYS) for n in w):
            w = garment_strip_apply(w, pt)
            counts["garment_arm_strip"] = counts.get("garment_arm_strip", 0) + 1
            TAG[i] = "garment_strip"
        if clr and i not in secondary:
            rl_ = CL_MEMBER.get(i)
            if rl_:
                w = colour_lock_apply(w, pt, rl_)
                counts["colour_lock"] = counts.get("colour_lock", 0) + 1
                TAG[i] = "colour_lock"
        for n in list(w):
            if pt.x > .01 and any(k in n for k in LIMBS_R):
                w.pop(n)
            elif pt.x < -.01 and any(k in n for k in LIMBS_L):
                w.pop(n)
            if pt.z > hipz + .01 and "UpLeg" in n:
                w.pop(n, None)
        # rig.upleg_cut [z_none, z_full] (optional, 10-09 Tuba): a huge belly over very short legs. Tripo spreads thigh
        # weight up to the middle of the belly, so a 30 deg stride tore the belly and the apron. Fade UpLeg weight to the
        # Hips between z_none (leg keeps all) and z_full (none left). Secondary parts (tail chain, rigid) are untouched.
        uc = rc.get("upleg_cut")
        if uc and i not in secondary:
            t_ = max(0.0, min(1.0, (pt.z - uc[0]) / (uc[1] - uc[0])))
            t_ = t_ * t_ * (3 - 2 * t_)
            if t_ > 0:
                mv = 0.0
                for n in [n for n in w if "UpLeg" in n]:
                    mv += w[n] * t_
                    w[n] *= (1 - t_)
                if mv:
                    w["mixamorig:Hips"] = w.get("mixamorig:Hips", 0) + mv
        if i not in secondary:
            # Far-weight prune, repeated after renormalising (a 0.08 weight becomes 0.3 once its neighbours go).
            # The Head bone is a thin line at the front of the skull, so big hair / the back of the head is
            # legitimately > 12% away from it: never prune HEAD_KEEP (Wren g2 bug: 1.9k back-of-head vertices lost
            # their Head weight and ended 100% on Neck -> the back of the head ignored head turns).
            for _ in range(3):
                w = {n: v for n, v in w.items() if v > 1e-6}
                tot = sum(w.values()) or 1
                far = [n for n, v in w.items() if n not in HEAD_KEEP and v / tot >= .1 and n in bones
                       and segdist(pt, arm.matrix_world @ bones[n].head_local, arm.matrix_world @ bones[n].tail_local)
                       > (rc.get("far_dist_torso", .12) if ("Spine" in n or n == "mixamorig:Hips") else .12)]
                # far_dist_torso (optional, 10-09 Harrow): a big hunched torso is wider than 12% of the height from the
                # spine line, the prune dropped Spine and the fallback below put the vest side back on the ARM (spikes)
                if not far:
                    break
                for n in far:
                    w.pop(n)
        w = {n: v for n, v in w.items() if v > 1e-6}
        if not w:  # everything pruned: nearest of the vertex's original bones (not Hips, not blindly the dominant one)
            cand = [n for n in orig if n in bones] or [n for n in bones if n.startswith("mixamorig") and bones[n].use_deform]
            w = {min(cand, key=lambda n: segdist(pt, arm.matrix_world @ bones[n].head_local, arm.matrix_world @ bones[n].tail_local)): 1}
        tot = sum(w.values())
        data[i] = {n: v / tot for n, v in w.items()}

    # rigid.grow_rings (optional, 10-09 Tuba): a colour-picked rigid part misses its shaded/dark pixels (thin rods,
    # the dark side of a pan); grow it through mesh edges inside its region.
    gr_specs = [rg for rg in rigid if rg.get("grow_rings")]
    if gr_specs:
        gadj = [[] for _ in pts]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            gadj[a_].append(b_)
            gadj[b_].append(a_)
        for rg in gr_specs:
            cur = {i for i in rigid_idx if data[i].get(rg["bone"], 0) >= 1.0}
            for _ in range(rg["grow_rings"]):
                nxt = {j for i in cur for j in gadj[i] if j not in rigid_idx and in_region(pts[j], rg["region"])}
                for j in nxt:
                    data[j] = {rg["bone"]: 1.0}
                    rigid_idx.add(j)
                    secondary.add(j)
                    TAG[j] = "rigid"
                cur |= nxt
            counts["rigid_grown_" + rg["bone"]] = len(cur)

    # rig.hard_skin (optional, 10-09 Tuba): rigid mechanical limbs. Inside `region`, vertices whose weight is mostly
    # (>= min_share) on bones matching `bones` (substring match) go 100% to the strongest of those bones and are kept
    # out of the seam smoothing like rigid parts. Tripo's soft elbow blend bent the machine-arm panels like rubber.
    # hard_skin regions/spheres are given in the FINAL normalized space (what the probes measure); the mesh here is
    # still un-renormalized (Tuba: 1.11 tall), so compare in final space
    _hmax = max(p_.z for p_ in pts) or 1.0
    LOCK_HARD = [False] * len(pts)
    for hs in rc.get("hard_skin", []):
        nh = 0
        for i, pt in enumerate(pts):
            ptf = pt / _hmax if hs.get("final_space") else pt
            if i in secondary or not in_region(ptf, hs["region"]):
                continue
            sph = hs.get("sphere")  # [cx, cy, cz, r]: only inside this ball (the round machine shoulder cap)
            if sph and (ptf - Vector(sph[:3])).length > sph[3]:
                continue
            m_ = {n: v for n, v in data[i].items() if any(k in n for k in hs["bones"])}
            if hs.get("min_share", 0.5) > 0 and (not m_ or sum(m_.values()) < hs.get("min_share", 0.5)):
                continue
            if not m_:
                m_ = {hs.get("to_bone", "mixamorig:Hips"): 1.0}
            hv = hs.get("hsv_any")  # [h0, h1, s_min, v_min, v_max] colour gate (10-09 Tuba: the machine shoulder cap)
            if hv:
                c_ = vcol(i)
                hh, ss, vv = colorsys.rgb_to_hsv(*c_)
                if not any(h0 <= hh * 360 <= h1 and ss >= s0 and v0 <= vv <= v1 and (v1 > 0.5 or ss < 0.25) for h0, h1, s0, v0, v1 in hv):
                    continue
            dom = max(m_, key=m_.get)
            if hs.get("to_bone"):
                data[i] = {hs["to_bone"]: 1.0}
                rigid_idx.add(i)
                TAG[i] = "hard"
                LOCK_HARD[i] = bool(hs.get("lock"))
                nh += 1
                continue
            # rigid_fingers: a machine hand is one block (its finger panels tore away from the palm when fingers curled)
            is_finger = any(k in dom for k in ("Thumb", "Index", "Middle", "Ring", "Pinky"))
            if hs.get("rigid_fingers") and is_finger and arm_param(pt, "Left" if pt.x > 0 else "Right") >= hs.get("finger_min_s", 1.8):
                # a finger is part of the fist block, whatever its position along the arm (the machine thumb sits
                # beside the wrist; position split put it on the forearm and it stuck out like a rod in the grip)
                dom = dom.split("Hand")[0] + "Hand"
            elif hs.get("by_segment") and (not is_finger or hs.get("rigid_fingers")):
                # by_segment (10-09 Tuba): rigid machine arm split by position along shoulder->elbow->wrist, not by
                # Tripo's dominant weight (that left forearm panels on the upper arm -> shredded when the elbow bent)
                side = "Left" if pt.x > 0 else "Right"
                s_ = arm_param(pt, side)
                dom = f"mixamorig:{side}" + ("Arm" if s_ < 1.0 else ("ForeArm" if s_ < hs.get("wrist_s", 1.92) else "Hand"))
            data[i] = {dom: 1.0}
            rigid_idx.add(i)
            TAG[i] = "hard"
            LOCK_HARD[i] = bool(hs.get("lock"))
            nh += 1
        counts.setdefault("hard_skin", []).append(nh)
    # rig.hard_skin_vote N (optional, 10-09 Tuba): majority vote among hard-bound neighbours, N rounds. Removes the
    # single-bone islands the position split leaves at a machine joint (each one tears into a spike when it bends).
    hv_n = int(rc.get("hard_skin_vote", 0))
    if hv_n:
        hadj = {}
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            if TAG[a_] == "hard" and TAG[b_] == "hard":
                hadj.setdefault(a_, []).append(b_)
                hadj.setdefault(b_, []).append(a_)
        locked = {i for i in range(len(pts)) if TAG[i] == "hard" and LOCK_HARD[i]}
        flips = 0
        for _ in range(hv_n):
            new = {}
            for i, nb in hadj.items():
                if i in locked:
                    continue
                cnt = {}
                for j in nb:
                    b_ = next(iter(data[j]))
                    cnt[b_] = cnt.get(b_, 0) + 1
                top = max(cnt, key=cnt.get)
                if top != next(iter(data[i])) and cnt[top] * 2 > len(nb):
                    new[i] = top
            for i, b_ in new.items():
                data[i] = {b_: 1.0}
            flips += len(new)
        counts["hard_skin_vote_flips"] = flips

    # --- Seam smoothing (Wren 10-08). Every rule above assigns weights per vertex, so neighbouring vertices on
    # either side of a rule boundary (skirt|thigh, hair|neck, strap|sleeve, hip cut) jump from one bone set to
    # another. Idle hides it; walk/jump/crouch rotate the joints far enough to tear those edges open (white slits
    # at the skirt hem and thigh tops). Diffuse weights across a band around every jump, and give co-located
    # vertices (glTF splits vertices on UV seams) one shared weight so seams cannot open. Rigid parts stay rigid.
    # The old "dominant weight >= 0.5" gate is gone: forcing a 0.5 floor re-created a step at every blend.
    ws = rc.get("weight_smooth", {})
    if ws.get("enabled", True):
        nv = len(data)
        adj = [set() for _ in range(nv)]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            adj[a_].add(b_)
            adj[b_].add(a_)
        buckets = {}
        for vi, v in enumerate(mesh.data.vertices):
            buckets.setdefault(tuple(round(c, 5) for c in v.co), []).append(vi)
        coloc = [g for g in buckets.values() if len(g) > 1]
        for g in coloc:
            for vi in g:
                adj[vi].update(x for x in g if x != vi)
        def l1(a_, b_):
            return sum(abs(a_.get(n, 0) - b_.get(n, 0)) for n in set(a_) | set(b_))
        # weight_smooth.near_weld (optional, 10-08 Vesper): Tripo leaves slits where two garment panels touch without
        # sharing vertices (sleeve front against the coat lapel). Different weights on the two lips open the slit when
        # the arm moves and the coat interior + outline hull show through as a black wedge. Treat vertices of different
        # rule regions closer than `radius` as neighbours so the weights diffuse across the slit.
        nw_ = ws.get("near_weld")
        if nw_:
            from mathutils.kdtree import KDTree
            kd = KDTree(nv)
            for vi, v in enumerate(mesh.data.vertices):
                kd.insert(v.co, vi)
            kd.balance()
            tg_ = set(nw_.get("tags", []))
            # pairs (optional): only weld these tag pairs; default = any two different tags from `tags`
            pr_ = {frozenset(p_) for p_ in nw_.get("pairs", [])}
            tg_ |= {t for p_ in pr_ for t in p_}
            nlinks = 0
            for vi, v in enumerate(mesh.data.vertices):
                if TAG[vi] not in tg_ or vi in rigid_idx:
                    continue
                for co, j, dd in kd.find_range(v.co, nw_["radius"]):
                    if j == vi or j in adj[vi] or j in rigid_idx or TAG[j] not in tg_:
                        continue
                    same = TAG[j] == TAG[vi]
                    # same_tag (optional, list of tags): also weld slits inside those regions (a garment folded against
                    # itself). Never the body: it would glue fingers and the inner thighs together.
                    if (same and TAG[vi] in nw_.get("same_tag", [])) or (not same and (not pr_ or frozenset((TAG[vi], TAG[j])) in pr_)):
                        adj[vi].add(j)
                        adj[j].add(vi)
                        nlinks += 1
            counts["near_weld_links"] = nlinks
        jump = float(ws.get("jump", 0.35))
        band = {vi for vi in range(nv) if vi not in rigid_idx and any(l1(data[vi], data[j]) > jump for j in adj[vi])}
        for _ in range(int(ws.get("band_rings", 5))):
            band |= {j for vi in list(band) for j in adj[vi] if j not in rigid_idx}
        alpha = float(ws.get("alpha", 0.5))
        # weight_smooth.rank (optional, 10-08 Vesper): {rule tag: rank}. A vertex only averages neighbours with its own
        # tag or a LOWER rank, so the blend across a boundary happens on the higher-rank side. Layered clothes need
        # this: Tripo welds the long coat to the trousers and the sleeve to the coat body, and two-sided diffusion
        # pushed coat Hips weight into the thighs and spine weight into the sleeves (squat/run/arms-up p99 1.5 -> 2.7).
        # No rank map = everyone equal = the Wren behaviour.
        rk = ws.get("rank")
        if rk:
            rkv = [rk.get(t, 0) for t in TAG]
            for vi in range(nv):
                adj[vi] = {j for j in adj[vi] if rkv[j] <= rkv[vi]}
            counts["smooth_rank"] = rk

        def diffuse(bnd, iters):
            for _ in range(iters):
                new = {}
                for vi in bnd:
                    nb = [j for j in adj[vi]]
                    if not nb:
                        continue
                    acc = {}
                    for j in nb:
                        for n, v in data[j].items():
                            acc[n] = acc.get(n, 0) + v / len(nb)
                    mix = {n: (1 - alpha) * data[vi].get(n, 0) + alpha * acc.get(n, 0) for n in set(data[vi]) | set(acc)}
                    new[vi] = mix
                for vi, w in new.items():
                    data[vi] = w
        diffuse(band, int(ws.get("iterations", 12)))
        # weight_smooth.extra_passes (optional, 10-08 Vesper): wider smoothing only inside some rule regions. Cloth that
        # is outside the body stretch gate (coat ring, hair) can take a wide blend at no cost, while the body joints
        # (armpit) must keep the narrow default: a wide linear blend under a 125 deg arm lift stretches MORE edges.
        for xp in ws.get("extra_passes", []):
            tg = set(xp["tags"])
            zr = xp.get("z", [-9, 9])
            inz = [zr[0] < pts[vi].z < zr[1] for vi in range(nv)]
            xb = {vi for vi in range(nv) if TAG[vi] in tg and inz[vi] and vi not in rigid_idx
                  and any(l1(data[vi], data[j]) > float(xp.get("jump", jump)) for j in adj[vi])}
            for _ in range(int(xp.get("band_rings", 10))):
                xb |= {j for vi in list(xb) for j in adj[vi] if TAG[j] in tg and inz[j] and j not in rigid_idx}
            diffuse(xb, int(xp.get("iterations", 40)))
            counts.setdefault("extra_band", []).append(len(xb))
        for g in coloc:
            if any(vi in rigid_idx for vi in g):
                continue
            acc = {}
            for vi in g:
                for n, v in data[vi].items():
                    acc[n] = acc.get(n, 0) + v / len(g)
            for vi in g:
                data[vi] = dict(acc)
        counts["smooth_band"] = len(band)
        counts["colocated_groups"] = len(coloc)
    for i in range(len(data)):
        # Diffusion must not undo the hard anatomical rules: no opposite-side limbs, no thigh above the hip.
        # Faded, not cut: a hard cut here re-creates the very step the smoothing just removed.
        pt = pts[i]
        for n in list(data[i]):
            f = 1.0
            if (pt.x > 0 and any(k in n for k in LIMBS_R)) or (pt.x < 0 and any(k in n for k in LIMBS_L)):
                f = min(f, max(0.0, 1 - (abs(pt.x) - .002) / .008))
            if "UpLeg" in n and pt.z > hipz:
                f = min(f, max(0.0, 1 - (pt.z - hipz) / .01))
            uc_ = rc.get("upleg_cut")
            if uc_ and "UpLeg" in n and i not in rigid_idx and TAG[i] != "chain":
                t_ = max(0.0, min(1.0, (pt.z - uc_[0]) / (uc_[1] - uc_[0])))
                f = min(f, 1 - t_ * t_ * (3 - 2 * t_))
            if f <= 0:
                lost = data[i].pop(n)
                if uc_ and "UpLeg" in n:
                    data[i]["mixamorig:Hips"] = data[i].get("mixamorig:Hips", 0) + lost
            elif f < 1:
                if uc_ and "UpLeg" in n:
                    data[i]["mixamorig:Hips"] = data[i].get("mixamorig:Hips", 0) + data[i][n] * (1 - f)
                data[i][n] *= f
        # rig.torso_arm_strip.post (optional, 10-09 Tuba): re-apply the arm strip after the seam smoothing, which
        # otherwise diffuses arm weight back onto the belly side / the cloth next to a hand hanging close to the body.
        # rig.spine_to_hips [z_full, z_none] (optional, 10-09 Tuba): below z_full every Spine/Spine1/Spine2 weight moves
        # to the Hips, fading out by z_none. The belt line (cloth, pouch, scale) then turns with the apron instead of
        # being sheared between the twisting belly and the hips; the twist spreads over the upper belly instead.
        s2h = rc.get("spine_to_hips")
        if s2h and i not in rigid_idx and TAG[i] not in ("chain", "rigid"):
            t_ = max(0.0, min(1.0, (s2h[1] - pt.z) / (s2h[1] - s2h[0])))
            t_ = t_ * t_ * (3 - 2 * t_)
            if t_ > 0:
                mv_ = 0.0
                for n in [n for n in data[i] if n in ("mixamorig:Spine", "mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:LeftShoulder", "mixamorig:RightShoulder")]:
                    mv_ += data[i][n] * t_
                    data[i][n] *= (1 - t_)
                if mv_:
                    data[i]["mixamorig:Hips"] = data[i].get("mixamorig:Hips", 0) + mv_
        # rig.arm_far_strip {dist, sides, hips_split_z} (optional, 10-09 Tuba): last word on arm weight. Seam smoothing
        # diffuses thumb/arm weight into the cloth the rest-pose hand touches; any arm/hand weight on a vertex farther
        # than `dist` from that side's arm bones goes to the Hips (below hips_split_z) or the Spine.
        afs = rc.get("arm_far_strip")
        if afs and i not in rigid_idx and TAG[i] != "chain":
            sd_ = "Left" if pt.x > 0 else "Right"
            if sd_ in afs.get("sides", ["Left", "Right"]):
                armn = [n for n in data[i] if n.startswith(f"mixamorig:{sd_}") and any(k in n for k in ARMKEYS)]
                # restore_dist (10-09 Tuba): a vertex Tripo itself gave to this arm (dominant bone) is arm skin even when a
                # thick arm puts it beyond `dist` (or an earlier strip took all its arm weight); give it its original weights
                od_ = max(ORIG[i], key=ORIG[i].get) if ORIG[i] else ""
                own = od_.startswith(f"mixamorig:{sd_}") and any(k in od_ for k in ARMKEYS)
                if armn or (own and afs.get("restore_dist")):
                    dd_ = min(segdist(pt, arm.matrix_world @ bones[n].head_local, arm.matrix_world @ bones[n].tail_local)
                              for n in bones if n.startswith(f"mixamorig:{sd_}") and any(k in n for k in ARMKEYS))
                    if own and afs.get("restore_dist") and dd_ < afs["restore_dist"]:
                        data[i] = {n: v for n, v in ORIG[i].items()
                                   if not ((pt.x > 0 and any(k in n for k in LIMBS_R)) or (pt.x < 0 and any(k in n for k in LIMBS_L)))}
                        TAG[i] = "arm_restored"
                    elif armn and dd_ > afs["dist"]:
                        tb_ = "mixamorig:Hips" if pt.z < afs.get("hips_split_z", 0.46) else "mixamorig:Spine1"
                        data[i][tb_] = data[i].get(tb_, 0) + sum(data[i].pop(n) for n in armn)
        sf_ = rc.get("sleeve_flood")
        if sf_ and sf_.get("post") and TAG[i] == "coat_strip" and any(any(k in n for k in ARMKEYS) for n in data[i]):
            tf_ = sf_.get("torso_fade")
            keep = 0.0 if not tf_ else max(0.0, min(1.0, (pt.z - tf_[0]) / (tf_[1] - tf_[0])))
            keep = keep * keep * (3 - 2 * keep)
            tb_ = "mixamorig:Spine1" if pt.z > sf_.get("spine_split_z", 0.62) else "mixamorig:Spine"
            if pt.z < sf_.get("hips_split_z", -1):
                tb_ = "mixamorig:Hips"
            mv_ = 0.0
            for n in list(data[i]):
                if any(k in n for k in ARMKEYS):
                    mv_ += data[i][n] * (1 - keep)
                    data[i][n] *= keep
            data[i][tb_] = data[i].get(tb_, 0) + mv_
        tas_ = rc.get("torso_arm_strip")
        if tas_ and tas_.get("post") and i not in rigid_idx and TAG[i] not in ("chain", "rigid")                 and tas_["z"][0] < pt.z < tas_["z"][1] and any(any(k in n for k in ARMKEYS) for n in data[i]):
            d = min(segdist(pt, a_seg, b_seg) for a_seg, b_seg in arm_segs)
            d0, d1 = tas_["arm_dist"]
            x0, x1 = tas_["absx"]
            keep = max(max(0.0, min(1.0, (d1 - d) / (d1 - d0))), max(0.0, min(1.0, (abs(pt.x) - x0) / (x1 - x0))))
            if keep < 1.0:
                tb_ = "mixamorig:Spine1" if pt.z > tas_.get("spine_split_z", 0.62) else "mixamorig:Spine"
                mv_ = 0.0
                for n in list(data[i]):
                    if any(k in n for k in ARMKEYS):
                        mv_ += data[i][n] * (1 - keep)
                        data[i][n] *= keep
                data[i][tb_] = data[i].get(tb_, 0) + mv_
        # garment_arm_strip.post: seam smoothing diffuses arm weight back into the fabric; strip it again
        if gas and gas.get("post") and TAG[i] not in ("chain", "rigid") and garment_strip_hit(i, pt) \
                and any(any(k in n for k in ARMKEYS) for n in data[i]):
            data[i] = garment_strip_apply(data[i], pt)
            TAG[i] = "garment_strip"
        if clr and TAG[i] == "colour_lock":
            rl_ = CL_MEMBER.get(i)
            if rl_ and rl_.get("post", True):
                data[i] = colour_lock_apply(data[i], pt, rl_)
        if not data[i]:
            data[i] = {"mixamorig:Hips": 1.0}
        w = dict(sorted(((n, v) for n, v in data[i].items() if v > 1e-4), key=lambda x: x[1], reverse=True)[:4])
        tot = sum(w.values()) or 1
        data[i] = {n: v / tot for n, v in w.items()}
    # rig.post_smooth {z_min, rings, iterations} (optional, 10-09 Tuba): the post rules above (arm restore / far strip)
    # run after the seam smoothing and cut new weight steps across the shoulder blade (black tear on the back when the
    # arm swung forward). Diffuse once more around the vertices they touched, above z_min only (keeps cloth at the hip clean).
    ps = rc.get("post_smooth")
    if ps:
        nv = len(data)
        padj = [set() for _ in range(nv)]
        for e in mesh.data.edges:
            a_, b_ = e.vertices
            padj[a_].add(b_)
            padj[b_].add(a_)
        pkey = {}
        for vi, v in enumerate(mesh.data.vertices):
            pkey.setdefault(tuple(round(c, 5) for c in v.co), []).append(vi)
        for g_ in pkey.values():
            for vi in g_:
                padj[vi].update(x for x in g_ if x != vi)
        okz = [pts[vi].z > ps.get("z_min", 0.5) and vi not in rigid_idx and TAG[vi] != "chain" for vi in range(nv)]
        st_ = set(ps.get("seed_tags", ["arm_restored"]))  # 10-09 Vesper v4 adds "garment_strip"
        pb_ = {vi for vi in range(nv) if okz[vi] and TAG[vi] in st_}
        pb_ |= {vi for vi in range(nv) if okz[vi] and any(okz[j] and TAG[j] in st_ for j in padj[vi])}
        for _ in range(int(ps.get("rings", 4))):
            pb_ |= {j for vi in list(pb_) for j in padj[vi] if okz[j]}
        for _ in range(int(ps.get("iterations", 8))):
            new = {}
            for vi in pb_:
                acc = {}
                for j in padj[vi]:
                    for n, v in data[j].items():
                        acc[n] = acc.get(n, 0) + v / len(padj[vi])
                new[vi] = {n: 0.5 * data[vi].get(n, 0) + 0.5 * acc.get(n, 0) for n in set(data[vi]) | set(acc)}
            for vi, w in new.items():
                w = dict(sorted(((n, v) for n, v in w.items() if v > 1e-4), key=lambda x: x[1], reverse=True)[:4])
                tot = sum(w.values()) or 1
                data[vi] = {n: v / tot for n, v in w.items()}
        # co-located (UV-split) copies must end identical again: colour-picked post rules read a different texel per copy
        for g_ in pkey.values():
            if len(g_) > 1 and (ps.get("unify_all") or any(vi in pb_ for vi in g_)):   # unify_all: 10-09 Harrow
                acc = {}
                for vi in g_:
                    for n, v in data[vi].items():
                        acc[n] = acc.get(n, 0) + v / len(g_)
                w = dict(sorted(((n, v) for n, v in acc.items() if v > 1e-4), key=lambda x: x[1], reverse=True)[:4])
                tot = sum(w.values()) or 1
                for vi in g_:
                    data[vi] = {n: v / tot for n, v in w.items()}
        counts["post_smooth_band"] = len(pb_)
    for g in mesh.vertex_groups:
        g.remove(range(len(mesh.data.vertices)))
    for i, w in enumerate(data):
        for n, v in w.items():
            mesh.vertex_groups[n].add([i], v, "REPLACE")
    # rig.split_welds {region, arm_min, arm_max} (optional, 10-09 Harrow): Tripo welds the A-pose inner elbow to the
    # vest side it touches. Whatever the weights, the shared edges stretch into long spikes when the arm moves. Edges
    # between an arm-dominant vertex (arm >= arm_min) and a torso vertex (arm <= arm_max) inside the region are split.
    sw_ = rc.get("split_welds")
    if sw_:
        import bmesh
        def armw_(i):
            return sum(v for n, v in data[i].items() if any(k in n for k in ARMKEYS))
        bm_ = bmesh.new(); bm_.from_mesh(mesh.data); bm_.edges.ensure_lookup_table()
        bm_.faces.ensure_lookup_table()
        # faces spanning an arm-dominant and a torso vertex are the weld itself: delete them (hidden in the A-pose gap)
        cut = [f_ for f_ in bm_.faces
               if all(in_region(pts[v_.index], sw_["region"]) for v_ in f_.verts)
               and ((max(armw_(v_.index) for v_ in f_.verts) >= sw_.get("arm_min", 0.6)
                     and min(armw_(v_.index) for v_ in f_.verts) <= sw_.get("arm_max", 0.15))
                    or (sw_.get("arm_jump") and max(armw_(v_.index) for v_ in f_.verts)
                        - min(armw_(v_.index) for v_ in f_.verts) >= sw_["arm_jump"]))]
        if cut:
            bmesh.ops.delete(bm_, geom=cut, context="FACES_ONLY")
            bm_.edges.ensure_lookup_table()
            loose_ = [e_ for e_ in bm_.edges if not e_.link_faces]
            if loose_:   # their edges too (vertex indices must stay stable, so vertices are kept)
                bmesh.ops.delete(bm_, geom=loose_, context="EDGES")
        bm_.to_mesh(mesh.data); bm_.free(); mesh.data.update()
        extra_ = len(mesh.data.vertices) - len(TAG)
        if extra_ > 0:   # split_edges appends duplicated vertices (weights copied): keep per-vertex lists aligned
            TAG.extend(["body"] * extra_)
            gnm_ = {g.index: g.name for g in mesh.vertex_groups}
            for k in range(len(data), len(mesh.data.vertices)):
                data.append({gnm_[g.group]: g.weight for g in mesh.data.vertices[k].groups if g.weight > 0})
            pts.extend(mesh.matrix_world @ mesh.data.vertices[k].co for k in range(len(pts), len(mesh.data.vertices)))
        counts["split_welds"] = len(cut)
        print("SPLIT_WELDS faces", len(cut))
    used = {n for w in data for n, v in w.items() if v > 1e-6}
    demoted = []
    for b in arm.data.bones:
        if b.use_deform and b.name not in used:
            b.use_deform = False
            demoted.append(b.name)
    print("COUNTS", json.dumps(counts))
    if o.get("dump_labels"):
        with open(o["dump_labels"], "w") as f_:
            json.dump({"tag": TAG, "secondary": sorted(secondary), "measured": sorted(measured)}, f_)
    print("DEMOTED_UNWEIGHTED_DEFORM_BONES", demoted)

    # exact 1.0 m / feet at 0 after all edits
    raw = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    sm = Matrix.Scale(1 / (max(p.z for p in raw) - min(p.z for p in raw)), 4)
    mesh.data.transform(sm)
    arm.data.transform(sm)
    raw = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    tm = Matrix.Translation((0, 0, -min(p.z for p in raw)))
    mesh.data.transform(tm)
    arm.data.transform(tm)

    # texture + a real Principled material (what the FBX carries)
    tsize = int(o.get("tex_size", 2048))
    dst = os.path.join(out, f"{NAME}_basecolor.png")
    img.filepath_raw = dst
    img.file_format = "PNG"
    if img.size[0] != tsize:
        img.scale(tsize, tsize)
    img.save()
    mat = mesh.data.materials[0] if mesh.data.materials else bpy.data.materials.new(f"{NAME}_mat")
    if not mesh.data.materials:
        mesh.data.materials.append(mat)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    on = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs[0], on.inputs[0])
    print("MATERIAL_NAME", mat.name, "(Unity remap key - changes with every Tripo export)")

    for b in arm.pose.bones:
        b.matrix_basis = Matrix.Identity(4)
    blend = os.path.join(out, f"{SLUG}_rig.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    fbx = _bl.export_fbx(os.path.join(out, f"{NAME}.fbx"), deform_only=rc.get("export_deform_only", False))
    print("SAVED", blend, fbx)

    # --- deformation tests ---
    sg = rc.get("stretch_gate", {})

    def clear_pose():
        for b in arm.pose.bones:
            b.matrix_basis = Matrix.Identity(4)

    def rot(n, ax, d):
        if n not in arm.pose.bones:
            return
        b = arm.pose.bones[n]
        b.rotation_mode = "XYZ"
        setattr(b.rotation_euler, ax, getattr(b.rotation_euler, ax) + math.radians(d))

    def rot_global(n, ax, d, axis_vec=None):
        if n not in arm.pose.bones:
            return
        b = arm.pose.bones[n]
        vec = axis_vec or {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}[ax]
        rq = b.bone.matrix_local.to_quaternion()
        b.rotation_mode = "QUATERNION"
        b.rotation_quaternion = rq.inverted() @ Quaternion(vec, math.radians(d)) @ rq

    def pose(name):
        clear_pose()
        if name == "arms_overhead":
            rot_global("mixamorig:LeftArm", "y", -125); rot_global("mixamorig:RightArm", "y", 125)
        elif name == "arms_forward_90":
            rot("mixamorig:LeftArm", "x", -90); rot("mixamorig:RightArm", "x", -90)
        elif name == "elbows_bent_120":
            rot_global("mixamorig:LeftForeArm", "y", -120); rot_global("mixamorig:RightForeArm", "y", 120)
        elif name == "deep_squat":
            for s_ in ("Left", "Right"):
                rot(f"mixamorig:{s_}UpLeg", "x", -70); rot(f"mixamorig:{s_}Leg", "x", 110); rot(f"mixamorig:{s_}Foot", "x", -40)
            arm.pose.bones["mixamorig:Hips"].location.z = -.16
        elif name == "running_stride":
            rot("mixamorig:LeftUpLeg", "x", -42); rot("mixamorig:RightUpLeg", "x", 38); rot("mixamorig:RightLeg", "x", 58)
            rot("mixamorig:LeftArm", "x", 38); rot("mixamorig:RightArm", "x", -38)
        elif name == "torso_twist_35":
            rot_global("mixamorig:Spine1", "z", 15); rot_global("mixamorig:Spine2", "z", 20)
        elif name == "head_turn_40":
            rot_global("mixamorig:Head", "z", 40)
        elif name == "chains_outward_40":
            for c, sgn, names, _ in chains:
                rot_global(names[0], "y", -40 * sgn)
        elif name == "skirt_lift_30" and sk:
            for i in range(sk["sectors"]):
                a_ = 2 * math.pi * i / sk["sectors"]
                ax = Vector((math.cos(a_), -math.sin(a_), 0))
                for n in skirt_names[i]:
                    rot_global(n, None, 30 / len(skirt_names[i]), axis_vec=ax)

    poses = ["arms_overhead", "arms_forward_90", "elbows_bent_120", "deep_squat", "running_stride", "torso_twist_35", "head_turn_40"]
    if chains:
        poses.append("chains_outward_40")
    if sk:
        poses.append("skirt_lift_30")
    rest = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    edges = [tuple(e.vertices) for e in mesh.data.edges]
    restlen = [(rest[b] - rest[a]).length for a, b in edges]
    med = sorted(restlen)[len(restlen) // 2]
    minlen = med * sg.get("min_rest_edge_frac", 0.25)
    metrics = {}
    renders = "no_renders" not in o
    if renders:
        sc = _bl.setup_scene(1024, 1024, bg=(0.04, 0.04, 0.04))
        _bl.emission_from_basecolor()
        cam = _bl.OrthoCam()
    for pn in poses:
        pose(pn)
        bpy.context.view_layer.update()
        ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
        pos = [mesh.matrix_world @ v.co for v in ev.data.vertices]
        body, allr, inc = [], [], [0.0] * len(pos)
        for (a_, b_), rl in zip(edges, restlen):
            if rl < minlen:
                continue
            q = (pos[b_] - pos[a_]).length / rl
            allr.append(q)
            inc[a_] = max(inc[a_], q)
            inc[b_] = max(inc[b_], q)
            if (a_ not in secondary or a_ in measured) and (b_ not in secondary or b_ in measured):
                body.append(q)

        def pct(v, p):
            v = sorted(v)
            return v[min(len(v) - 1, int((len(v) - 1) * p))] if v else 1.0
        worst = []
        for vi in sorted(range(len(inc)), key=lambda x: inc[x], reverse=True)[:5]:
            worst.append({"vertex": vi, "ratio": round(inc[vi], 3), "bone": max(data[vi].items(), key=lambda x: x[1])[0]})
        metrics[pn] = {"all_p99": round(pct(allr, .99), 4), "body_p99": round(pct(body, .99), 4), "body_p999": round(pct(body, .999), 4),
                       "body_max": round(max(body) if body else 1, 4), "body_min": round(min(body) if body else 1, 4), "worst": worst,
                       "pass_p99": pct(body, .99) <= sg.get("body_p99_max", 1.75)}
        if renders:
            for vn, ang in (("front", 0), ("threequarter", math.radians(35))):
                cam.shot(os.path.join(out, "deform", f"{pn}_{vn}.png"), (0, 0, .5), (math.sin(ang), -math.cos(ang), 0.0), 1.18)
    clear_pose()
    rep = {"src": src, "texture": texsrc, "counts": counts, "demoted": demoted, "removed_meshes": removed,
           "material_name": mat.name, "fbx": fbx, "blend": blend, "metrics": metrics,
           "gate_body_p99_all_pass": all(m["pass_p99"] for m in metrics.values())}
    with open(os.path.join(out, "rig_build.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print("METRICS", json.dumps({k: (v["body_p99"], v["pass_p99"]) for k, v in metrics.items()}))
    print("RIG_BUILD_DONE", os.path.join(out, "rig_build.json"))


main()
