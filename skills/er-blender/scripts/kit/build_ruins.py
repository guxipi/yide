"""Build the three J01 empty ruins (RN 海岸测候残站 / RE 林中检修驿 / RC 撤空分拨残场) from kit shells,
placed exactly on the design polygons in J01_POI_design.json (map metres; local origin = ruin center_map).

blender -b --factory-startup -P build_ruins.py --python-exit-code 1 -- --design <J01_POI_design.json> --out <dir> [--render]

Shell kinds (23 总纲 DNA2 base bodies):
  横卧舱  wall strip of a broken horizontal hull: dark ribbed outer slab, white inner panels, torn white roof
          shoulder riding the broken top, base skid; ends taper down (breaks).
  立筒    half shell of a polygonal tube: chunky flat white facets, dark ring bands, stepped broken top.
  平台    leftover foot plate of a platform: chamfered white slab with dark rim and an empty dark socket;
          names with 翘 / 顶起 are tilted (pushed up by roots).
No floors anywhere.
"""
import json
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hull as HU  # noqa: E402
import kitlib as K  # noqa: E402


def rect_of(ctrl):
    xs = [p[0] for p in ctrl]
    ys = [p[1] for p in ctrl]
    return min(xs), min(ys), max(xs), max(ys)


def circle3(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    return ux, uy


def wall_strip(part, x0, y0, x1, y1, H, out_sign, rnd):
    """Broken hull side shell inside the rectangle; outer face on out_sign side (+1 = +Y)."""
    T = 0.5
    if out_sign > 0:
        ya, yb = y1 - T, y1
        y_face = y1
    else:
        ya, yb = y0, y0 + T
        y_face = y0
    L = x1 - x0
    top = HU._jag_top(x0, x1, H - 0.5, 0.55, rnd, step=(1.2, 2.6))
    # ends fall away (break taper)
    tap = min(2.5, L * 0.25)
    top2 = []
    for s, z in top:
        k = min(1.0, (s - x0) / tap, (x1 - s) / tap)
        top2.append((s, max(1.2, z * (0.55 + 0.45 * k))))
    prof = [(x0, -0.3), (x1, -0.3)] + list(reversed(top2))
    part.prism_y(ya, yb, prof, "panel")
    part.box(x0, ya - 0.05, -0.3, x1, yb + 0.05, 0.45, "dark")
    HU.ribs_x(part, x0, x1, y_face, out_sign, 0.45, lambda x: HU._interp(top2, x), spacing=2.4)
    # inner white panel face
    yi = ya if out_sign > 0 else yb
    yi0, yi1 = sorted((yi, yi - out_sign * 0.04))
    s = x0 + 0.3
    while s < x1 - 0.3:
        e = min(x1 - 0.3, s + 2.4)
        zt = min(HU._interp(top2, s), HU._interp(top2, e)) - 0.4
        if zt > 1.0:
            part.box(s + 0.03, yi0, 0.5, e - 0.03, yi1, zt, "shell_in")
        s = e
    # inner dark frame ribs + rail at 1.2 m (same language as the hull interiors)
    HU.ribs_x(part, x0, x1, yi, -out_sign, 0.0, lambda x: HU._interp(top2, x) - 0.5, spacing=2.4, w=0.36, proud=0.16)
    ra, rb = sorted((yi, yi - out_sign * 0.14))
    part.box(x0 + 0.3, ra, 1.05, x1 - 0.3, rb, 1.3, "panel")
    # torn white roof shoulder on the plateaus, reaching inward over the strip depth
    depth = (y1 - y0) - T
    s = x0
    while s < x1 - 0.2:
        e = min(x1, s + rnd.uniform(1.0, 2.2))
        zt = min(HU._interp(top2, s), HU._interp(top2, e))
        if zt > 3.0 and rnd.random() < 0.8:
            w = rnd.uniform(0.6, 1.0) * depth + T
            if out_sign > 0:
                part.box(s, y1 - w, zt - 0.45, e, y1 + 0.08, zt + 0.1, "shell")
            else:
                part.box(s, y0 - 0.08, zt - 0.45, e, y0 + w, zt + 0.1, "shell")
        s = e


def tube_half(part, ctrl, H, rnd):
    n = len(ctrl) // 2
    outer, inner = ctrl[:n], ctrl[n:]
    c = circle3(outer[0], outer[n // 2], outer[-1])
    ro = math.dist(c, outer[0])
    ri = math.dist(c, inner[0])
    a0 = math.atan2(outer[0][1] - c[1], outer[0][0] - c[0])
    a1 = math.atan2(outer[-1][1] - c[1], outer[-1][0] - c[0])
    # go the short way round
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    nf = max(3, int(round(abs(da) / math.radians(30)) * 1))
    bm = part.bm
    for i in range(nf):
        t0 = a0 + da * i / nf
        t1 = a0 + da * (i + 1) / nf
        zt = max(1.0, H - rnd.uniform(0.0, 1.4) - (0.8 if i in (0, nf - 1) else 0.0))
        quad = [(c[0] + ri * math.cos(t0), c[1] + ri * math.sin(t0)), (c[0] + ro * math.cos(t0), c[1] + ro * math.sin(t0)),
                (c[0] + ro * math.cos(t1), c[1] + ro * math.sin(t1)), (c[0] + ri * math.cos(t1), c[1] + ri * math.sin(t1))]
        _prism_z(part, quad, -0.3, zt, "shell")
        # dark ring bands, slightly proud on the outer face
        for zb0, zb1 in ((-0.3, 0.5), (zt * 0.55, zt * 0.55 + 0.3)):
            if zb1 < zt - 0.2:
                r2 = ro + 0.08
                q2 = [(c[0] + (ro - 0.1) * math.cos(t0), c[1] + (ro - 0.1) * math.sin(t0)),
                      (c[0] + r2 * math.cos(t0), c[1] + r2 * math.sin(t0)),
                      (c[0] + r2 * math.cos(t1), c[1] + r2 * math.sin(t1)),
                      (c[0] + (ro - 0.1) * math.cos(t1), c[1] + (ro - 0.1) * math.sin(t1))]
                _prism_z(part, q2, zb0, zb1, "panel")
        # dark seam post between facets
        if i > 0:
            px, py = c[0] + (ro + 0.02) * math.cos(t0), c[1] + (ro + 0.02) * math.sin(t0)
            part.box(px - 0.14, py - 0.14, -0.3, px + 0.14, py + 0.14, zt - 0.1, "dark")
    return {"center": c, "ro": round(ro, 2), "ri": round(ri, 2), "facets": nf}


def _prism_z(part, poly, z0, z1, cid):
    bm = part.bm
    a = [bm.verts.new((x, y, z0)) for x, y in poly]
    b = [bm.verts.new((x, y, z1)) for x, y in poly]
    n = len(poly)
    faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    part._tag(faces, cid)


def foot_plate(part, x0, y0, x1, y1, h):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ch = min(0.25, h * 0.35)
    prof = [(y0, -0.3), (y1, -0.3), (y1, h - ch), (y1 - ch, h), (y0 + ch, h), (y0, h - ch)]
    part.prism_x(x0, x1, prof, "shell")
    part.box(x0 - 0.06, y0 - 0.06, -0.3, x1 + 0.06, y1 + 0.06, min(0.3, h * 0.45), "dark")
    # empty socket (the plug-in was taken away)
    part.box(cx - 0.55, cy - 0.55, h - 0.06, cx + 0.55, cy + 0.55, h + 0.05, "dark")
    part.box(cx - 0.35, cy - 0.35, h - 0.02, cx + 0.35, cy + 0.35, h + 0.07, "seam")


def build_ruin(ruin, rnd):
    cx, cy = ruin["center_map"]
    col = K.ensure_collection("Ruin_" + ruin["id"])
    mods = {m["id"]: m for m in ruin.get("modules", [])}
    made, info = [], {}
    for sh in ruin["shells"]:
        ctrl = [(x - cx, y - cy) for x, y in sh["controls"]]
        p = K.Part("%s_%s" % (ruin["id"], sh["id"].split("-", 1)[1].replace("-", "_")))
        H = sh["height_m"]
        if sh["kind"] == "横卧舱":
            x0, y0, x1, y1 = rect_of(ctrl)
            m = mods.get(sh["assembly_id"])
            if m:
                mx0, my0, mx1, my1 = rect_of([(x - cx, y - cy) for x, y in m["reference_envelope_controls"]])
                out = 1 if (y0 + y1) / 2 > (my0 + my1) / 2 else -1
            else:
                out = 1
            wall_strip(p, x0, y0, x1, y1, H, out, rnd)
            ob = p.finish(col, bevel=0.05, seed=rnd.randint(1, 999))
        elif sh["kind"] == "立筒":
            info[sh["id"]] = tube_half(p, ctrl, H, rnd)
            ob = p.finish(col, bevel=0.05, angle_deg=25, seed=rnd.randint(1, 999))
        else:
            x0, y0, x1, y1 = rect_of(ctrl)
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            foot_plate(p, x0 - mx, y0 - my, x1 - mx, y1 - my, H)
            ob = p.finish(col, bevel=0.04, seed=rnd.randint(1, 999))
            ob.location = (mx, my, 0)
            if "翘" in sh["name"] or "顶起" in sh["name"]:
                ob.rotation_euler = (math.radians(7), math.radians(-4), 0)
                ob.location.z = 0.25
        made.append(ob)
    return made, info


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    design = json.load(open(a[a.index("--design") + 1], encoding="utf-8"))
    out = a[a.index("--out") + 1]
    render = "--render" in a
    bpy.ops.wm.read_factory_settings(use_empty=True)
    import review
    rnd = random.Random(2026)
    rep = {}
    for ruin in design["empty_ruins"]:
        objs, info = build_ruin(ruin, rnd)
        rep[ruin["id"]] = {"objects": len(objs),
                           "tris": sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs), **info}
        if render:
            pts = review.bbox_pts(objs)
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            review.render_simple(out, "Ruin_" + ruin["id"], objs,
                                 ruler_at=((min(xs) + max(xs)) / 2, min(ys) - 2.0),
                                 game_target=((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, 0.0),
                                 game_width=24.0)
        for o in objs:
            o.hide_render = True
    blend = os.path.join(out, "blend", "J01_ruins.blend")
    for o in bpy.data.objects:
        o.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("ER_JSON " + json.dumps({"ok": True, "blend": blend, "ruins": rep}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
