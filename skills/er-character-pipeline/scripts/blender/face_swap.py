"""Texture-swap face: put the visible face polygons on their own material + UVs that index a 4x3 expression
atlas, so Unity switches expressions by changing _BaseMap_ST offset (CharacterFaceController / WrenFaceController).

usage: blender -b --python face_swap.py -- --config char.json [--rig RIG.blend] [--atlas ATLAS.png]
       [--proj face_projection.json] [--out DIR] [--uv-space cell|atlas] [--grow 3]
Defaults: rig = {rig_dir}/{slug}_rig.blend, atlas/proj in {face_dir}, out = {rig_dir}.
Writes {slug}_rig_face.blend, {Name}.fbx (overwrites the rig-only FBX), {Name}_face_atlas.png, face_qa/*.png,
face_swap.json.

Selection (all gates measured on the rest-pose rig mesh itself, in the projection of face_render.py):
  normal faces the camera (n.y < -0.35) - side-facing socket corners allowed only inside the feature bands;
  every loop projects inside the crop box; polygon centre colour is not hair (cfg.face.hair_hue_ranges);
  first ray hit from the front (not occluded by fringe); then grow `--grow` adjacency rings inside the
  feature bands (closed-eye cells otherwise keep white sclera triangles at the eye corners - Wren r1 reject).
Back-of-head guard: drop only polygons whose normal points away from the area-weighted face normal (dot < 0).
Do NOT use a "behind the face centroid" depth rule: on Wren it removed 121 cheek/eye-corner polygons and the
closed-eye cells showed white sclera wedges again. Verify with face_qa/headback.png (no atlas paint on the back).
UV space:
  cell  (default, what WrenFaceController expects): u = (px-x0)/w in [0,1], v = 3 - (py-y0)/h in [2,3];
        material tiling (0.25, 1/3), offset per cell (0.25*col, -(1/3)*row).
  atlas: u in [0,0.25], v in [2/3,1]; tiling (1,1), offset per cell. (Only if the Unity controller is changed.)
"""
import colorsys
import json
import math
import os
import shutil
import sys

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bl  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _cfg import blender_args, load_cfg, out_path  # noqa: E402


def main():
    a = blender_args(sys.argv)
    if not a or a[0] in ("-h", "--help"):
        print(__doc__)
        return
    o = dict(zip(a[0::2], a[1::2]))
    cfg = load_cfg(o.get("--config"))
    NAME, SLUG = cfg["name"], cfg["slug"]
    rigdir = out_path(cfg, cfg["files"].get("rig_dir", "rig"))
    facedir = out_path(cfg, cfg["files"].get("face_dir", "face"))
    rig = o.get("--rig") or os.path.join(rigdir, f"{SLUG}_rig.blend")
    atlas_src = o.get("--atlas") or os.path.join(facedir, f"{NAME}_face_atlas.png")
    projp = o.get("--proj") or os.path.join(facedir, "face_projection.json")
    out = o.get("--out") or rigdir
    uvspace = o.get("--uv-space", "cell")
    grow = int(o.get("--grow", 3))
    proj = json.load(open(projp, encoding="utf-8"))
    cz, S, R = proj["center_z"], proj["ortho_scale"], proj["res"]
    x0, y0, x1, y1 = proj["crop"]
    cw, ch = x1 - x0, y1 - y0
    eb, mb = proj["feature_bands"]["eyes_brows"], proj["feature_bands"]["mouth"]
    hair = cfg.get("face", {}).get("hair_hue_ranges", [])
    qa = os.path.join(out, "face_qa")
    os.makedirs(qa, exist_ok=True)

    def P(q):
        return (q.x / S * R + R / 2, R / 2 - (q.z - cz) / S * R)

    def in_bands(px, py):
        return (eb[0] <= px <= eb[2] and eb[1] <= py <= eb[3]) or (mb[0] <= px <= mb[2] and mb[1] <= py <= mb[3])

    _bl.load_any(rig)
    mesh = _bl.main_mesh()
    arm = _bl.armature()
    me = mesh.data
    mw = mesh.matrix_world
    base_mat = me.materials[0]
    tex = next(n for n in base_mat.node_tree.nodes if n.type == "TEX_IMAGE")
    base_img = tex.image
    base_img.pixels[0]
    BW, BH = base_img.size
    BP = list(base_img.pixels)
    uvl = me.uv_layers.active

    def rgb(uv):
        x = max(0, min(BW - 1, int((uv.x % 1.0) * (BW - 1) + .5)))
        y = max(0, min(BH - 1, int((uv.y % 1.0) * (BH - 1) + .5)))
        i = 4 * (y * BW + x)
        return BP[i:i + 3]

    def is_hair(c):
        h, s_, v = colorsys.rgb_to_hsv(*c)
        return v > .25 and s_ > .32 and any(lo < h < hi for lo, hi in hair)

    def is_face_surface(c):
        h, s_, v = colorsys.rgb_to_hsv(*c)
        return s_ < .30 or v < .24 or h < .13 or h > .985

    verts = [mw @ v.co for v in me.vertices]
    polys = [[me.loops[li].vertex_index for li in p.loop_indices] for p in me.polygons]
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)
    ymin = min(v.y for v in verts)
    selected, cand, centres = [], set(), {}
    occl_band = set()  # 10-08 Rook: eye-corner polys half hidden behind a fringe lock fail the centre ray test
    rej = {"normal": 0, "crop": 0, "hair": 0, "occluded": 0}
    for p in me.polygons:
        n = (mw.to_3x3() @ p.normal).normalized()
        pr = [P(verts[i]) for i in polys[p.index]]
        if not all(x0 <= px <= x1 and y0 <= py <= y1 for px, py in pr):
            rej["crop"] += 1
            continue
        pcx = sum(x for x, _ in pr) / len(pr)
        pcy = sum(y for _, y in pr) / len(pr)
        band = in_bands(pcx, pcy)
        if n.y >= -.35 and not band:
            rej["normal"] += 1
            continue
        uvs = [uvl.data[li].uv.copy() for li in p.loop_indices]
        cuv = sum(uvs, Vector((0, 0))) / len(uvs)
        samples = [rgb(u) for u in uvs] + [rgb(cuv)] + [rgb((uvs[i] + uvs[(i + 1) % len(uvs)]) * .5) for i in range(len(uvs))]
        if is_hair(rgb(cuv)):
            rej["hair"] += 1
            continue
        c = sum((verts[i] for i in polys[p.index]), Vector()) / len(polys[p.index])
        probes = [c] + ([c + (verts[i] - c) * .8 for i in polys[p.index]] if band else [])
        vis = False
        for q in probes:
            hit = bvh.ray_cast(Vector((q.x, ymin - .05, q.z)), Vector((0, 1, 0)), 2.0)
            if hit[0] is not None and hit[2] == p.index and (hit[0] - q).length < .002:
                vis = True
                break
        if not vis:
            rej["occluded"] += 1
            if band:
                occl_band.add(p.index)
                # sclera-white polys in the eye band (often a separate eyeball island, so adjacency growth never
                # reaches them) would show the baked eye white through every closed-eye cell
                cs = rgb(cuv); hh, ss, vv = colorsys.rgb_to_hsv(*cs)
                if ss < .18 and vv > .70 and c.y < ymin + .06:  # front of the face only (a helmet behind the head is white too)
                    selected.append(p.index)
            continue
        centres[p.index] = (pcx, pcy)
        if band:
            cand.add(p.index)
        if n.y < -.35 and all(is_face_surface(s_) for s_ in samples):
            selected.append(p.index)
    adj = {p.index: set() for p in me.polygons}
    ef = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            ef.setdefault(ek, []).append(p.index)
    for fs in ef.values():
        for x in fs:
            adj[x].update(y for y in fs if y != x)
    sel = set(selected) | cand
    # grow only into feature-band polygons: the visible candidates AND band polygons the ray test called occluded
    # (a fringe strand in front of an eye corner); without the second set --grow changes nothing (sel already has cand)
    growable = cand | occl_band
    for _ in range(grow):
        sel |= {nb for pi in tuple(sel) for nb in adj[pi] if nb in growable}
    # back-of-head guard
    fp = [me.polygons[i] for i in sel]
    cen = sum((mw @ p.center for p in fp), Vector()) / max(1, len(fp))
    fwd = sum(((mw.to_3x3() @ p.normal) * p.area for p in fp), Vector()).normalized()
    # Only polygons whose normal really turns away from the face (dot < 0) are dropped. The 2026-10-07 guard
    # (dot < 0.2 OR > 1 cm behind the face centroid) removed 121 cheek-side / eye-corner polygons and brought the
    # white sclera wedges back in every closed-eye cell of the shipped Wren - check face_qa/headback.png instead.
    back = {p.index for p in fp if (mw.to_3x3() @ p.normal).normalized().dot(fwd) < 0.0}
    sel -= back
    # --force-ellipses "cx,cy,rx,ry;..." (projection px) + --force-ymax Y (optional, 10-09 Tuba): deep eye sockets
    # under overhanging lids. The lid undersides, lash rims and lower-lid whites face up/down/back, so the normal test,
    # the ray test and the back guard all drop them and the baked open eye shows through every closed-eye cell.
    # Every polygon whose projection lies inside an eye ellipse and that sits in front of force_ymax is swapped too.
    fe = o.get("--force-ellipses")
    forced = set()
    if fe:
        ells = [tuple(float(v) for v in e.split(",")) for e in fe.split(";") if e.strip()]
        fy = float(o.get("--force-ymax", 9))
        for p in me.polygons:
            pr = [P(verts[i]) for i in polys[p.index]]
            if not all(x0 <= px <= x1 and y0 <= py <= y1 for px, py in pr):
                continue
            c = sum((verts[i] for i in polys[p.index]), Vector()) / len(polys[p.index])
            if c.y > fy:
                continue
            pcx = sum(x for x, _ in pr) / len(pr)
            pcy = sum(y for _, y in pr) / len(pr)
            if any(((pcx - ex) / rx) ** 2 + ((pcy - ey) / ry) ** 2 <= 1 for ex, ey, rx, ry in ells):
                forced.add(p.index)
        forced -= sel
        sel |= forced
    if not sel:
        raise SystemExit("face selection empty - check face_calib.png / projection")
    os.makedirs(out, exist_ok=True)
    atlas_dst = os.path.join(out, f"{NAME}_face_atlas.png")
    if os.path.abspath(atlas_src) != os.path.abspath(atlas_dst):
        shutil.copy2(atlas_src, atlas_dst)
    atlas = bpy.data.images.load(atlas_dst, check_existing=True)
    fm = bpy.data.materials.new(f"{NAME}Face")
    fm.use_nodes = True
    nt = fm.node_tree
    nt.nodes.clear()
    on = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = atlas
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = uvl.name
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "FaceCell"
    nt.links.new(uvn.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], tx.inputs["Vector"])
    nt.links.new(tx.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(bs.outputs[0], on.inputs["Surface"])
    me.materials.append(fm)
    slot = len(me.materials) - 1
    for pi in sel:
        p = me.polygons[pi]
        p.material_index = slot
        for li in p.loop_indices:
            px, py = P(verts[me.loops[li].vertex_index])
            u, t = (px - x0) / cw, (py - y0) / ch
            uvl.data[li].uv = (u, 3 - t) if uvspace == "cell" else (u * .25, 1 - t / 3)
    tiling = (0.25, 1 / 3) if uvspace == "cell" else (1, 1)
    mp.inputs["Scale"].default_value = (tiling[0], tiling[1], 1)
    if arm:
        for b in arm.pose.bones:
            b.matrix_basis.identity()
    blend = os.path.join(out, f"{SLUG}_rig_face.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    fbx = _bl.export_fbx(os.path.join(out, f"{NAME}.fbx"), deform_only=cfg.get("rig", {}).get("export_deform_only", False))

    # QA renders (unlit; not saved)
    _bl.setup_scene(1024, 1024, bg=(0.035, 0.035, 0.035))
    _bl.emission_from_basecolor()
    cam = _bl.OrthoCam()
    exprs = [e["id"] for e in cfg.get("face", {}).get("expressions", [])] or ["neutral"]
    for cell, eid in enumerate(exprs):
        col, row = cell % 4, cell // 4
        mp.inputs["Location"].default_value = (0.25 * col, -(1 / 3) * row, 0)
        cam.shot(os.path.join(qa, f"{eid}_front.png"), (0, 0, cz), (0, -1, 0), S)
        cam.shot(os.path.join(qa, f"{eid}_threequarter.png"), (0, 0, cz), (0.55, -1.5, 0.03), S * 1.1)
    gi = exprs.index("grin") if "grin" in exprs else 0
    mp.inputs["Location"].default_value = (0.25 * (gi % 4), -(1 / 3) * (gi // 4), 0)
    cam.shot(os.path.join(qa, "headback.png"), (0, 0, cz), (0, 1, 0.15), S * 1.6)
    cam.shot(os.path.join(qa, "full_front.png"), (0, 0, .5), (0, -1, 0), 1.08)
    cam.shot(os.path.join(qa, "top70.png"), (0, 0, .48), (0, -math.cos(math.radians(70)), math.sin(math.radians(70))), 1.15)
    rep = {"selected_polygons": len(sel), "forced_eye_polygons": len(forced), "back_of_head_removed": len(back), "rejected": rej, "uv_space": uvspace,
           "material_tiling": tiling, "cells": {e: [0.25 * (i % 4), -(1 / 3) * (i // 4)] for i, e in enumerate(exprs)},
           "blend": blend, "fbx": fbx, "atlas": atlas_dst, "qa_dir": qa}
    with open(os.path.join(out, "face_swap.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, indent=1)
    print("FACE_SWAP", json.dumps({k: rep[k] for k in ("selected_polygons", "forced_eye_polygons", "back_of_head_removed", "rejected", "uv_space")}))
    print("next: py -3 face_qa_sheet.py --config <cfg> --qa", qa)


main()
