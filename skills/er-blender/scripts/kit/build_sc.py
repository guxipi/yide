"""Build the J01 barge-workshop SC covered house ("潮损检修周转屋") from kit parts, driven by pilot.json.

blender -b --factory-startup -P build_sc.py --python-exit-code 1 -- --pilot <pilot.json> --out <ArtWork dir> [--render]

v2 (2026-10-30): massing follows the passed concept card J01_PS_card_v2 — low 2 m wall to the spring line,
near-semicircular barrel vault on top (total height of the shell 8.2 m, ribs to ~8.5 m, = pilot size 8.5 m).
Room layout, wall runs, door positions/sizes and furniture come from pilot.json unchanged. The two 4 m
outside doors do not fit under the low eave, so each becomes a "人口" portal plug-in block (23 总纲 DNA2).

Collections (also object-name prefixes):
  SC_Low        everything below the 1.2 m cutaway line
  SC_Up         wall / portal / frame parts above 1.2 m (hidden when the camera looks inside)
  SC_Roof       vault skin, ribs, gable infills (fade together when the player is inside)
  SC_Doors      closed elite doors (H-E, C-E, D-E)
  SC_Furniture  the 10 interior fixtures
No floor and no plinth: walls sit straight on the ground and sink 0.3 m below it.
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kitlib as K  # noqa: E402
import furniture as FUR  # noqa: E402

EXT_T = 0.4
SPRING = 2.0          # exterior wall top = vault spring line
INT_T, INT_H = 0.25, 3.2
CUT = 1.2
SINK = 0.3
VAULT_OVER = 0.2      # vault outer half-span beyond the wall outer face
VAULT_RISE = 6.2
END_EAVE = 0.15       # vault overhang past the gable walls
ROOF_T = 0.3
RIB_W, RIB_PROUD = 0.65, 0.28
PIL_PROUD = 0.26
PANEL_TARGET = 2.4
GAP = 0.05
SEAM_DEPTH = 0.035
PORTAL_OUT = 0.8      # portal block depth outside the wall face
PORTAL_TOP = 5.4


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    o = {"render": False}
    i = 0
    while i < len(a):
        if a[i] == "--render":
            o["render"] = True
            i += 1
        else:
            o[a[i][2:]] = a[i + 1]
            i += 2
    return o


class WallFrame:
    """(s along wall, t across wall, z) -> Blender XYZ.  axis 'x': wall along X at y=c (t -> +Y);
    axis 'y': wall along Y at x=c (t -> +X)."""

    def __init__(self, axis, c):
        self.axis, self.c = axis, c

    def box(self, part, s0, s1, t0, t1, z0, z1, cid):
        if self.axis == "x":
            return part.box(s0, self.c + t0, z0, s1, self.c + t1, z1, cid)
        return part.box(self.c + t0, s0, z0, self.c + t1, s1, z1, cid)

    def xyz(self, s, t, z):
        return (s, self.c + t, z) if self.axis == "x" else (self.c + t, s, z)


def split_z(lo, up, fn, z0, z1):
    if z0 < CUT:
        fn(lo, z0, min(z1, CUT))
    if z1 > CUT:
        fn(up, max(z0, CUT), z1)


def sbox(lo, up, f, s0, s1, t0, t1, z0, z1, cid):
    split_z(lo, up, lambda p, a, b: f.box(p, s0, s1, t0, t1, a, b, cid), z0, z1)


def panel_runs(s0, s1, target):
    n = max(1, int(round((s1 - s0) / target)))
    w = (s1 - s0) / n
    return [(s0 + i * w, s0 + (i + 1) * w) for i in range(n)]


# ------------------------------------------------------------------ walls
def ext_wall(lo, up, axis, s0, s1, c):
    f = WallFrame(axis, c)
    h = EXT_T / 2
    sbox(lo, up, f, s0, s1, -h + SEAM_DEPTH, h - SEAM_DEPTH, -SINK, 1.6, "seam")
    runs = panel_runs(s0, s1, PANEL_TARGET)
    for i, (a, b) in enumerate(runs):
        a2 = a + (GAP / 2 if i > 0 else 0)
        b2 = b - (GAP / 2 if i < len(runs) - 1 else 0)
        sbox(lo, up, f, a2, b2, -h, h, 0.35, 1.6, "shell")
    f.box(lo, s0, s1, -h - 0.05, h + 0.05, -SINK, 0.4, "dark")      # skirt
    f.box(lo, s0, s1, -h - 0.04, h + 0.04, 1.04, CUT, "panel")       # waist trim
    f.box(up, s0, s1, -h - 0.08, h + 0.08, 1.6, SPRING, "panel")     # spring band (card: dark band)


def int_wall(lo, up, axis, s0, s1, c):
    f = WallFrame(axis, c)
    h = INT_T / 2
    sbox(lo, up, f, s0, s1, -h + 0.025, h - 0.025, -SINK, 3.05, "seam")
    runs = panel_runs(s0, s1, 2.0)
    for i, (a, b) in enumerate(runs):
        a2 = a + (GAP / 2 if i > 0 else 0)
        b2 = b - (GAP / 2 if i < len(runs) - 1 else 0)
        sbox(lo, up, f, a2, b2, -h, h, 0.2, 3.05, "shell_in")
    f.box(lo, s0, s1, -h - 0.03, h + 0.03, -SINK, 0.2, "dark")
    f.box(lo, s0, s1, -h - 0.03, h + 0.03, 1.08, CUT, "panel")
    f.box(up, s0, s1, -h - 0.04, h + 0.04, 3.05, INT_H, "dark")


def int_door_frame(lo, up, axis, s_c, width, height, c):
    f = WallFrame(axis, c)
    h = INT_T / 2
    pw = 0.18
    s0, s1 = s_c - width / 2, s_c + width / 2
    for a, b in ((s0 - pw, s0), (s1, s1 + pw)):
        sbox(lo, up, f, a, b, -h - 0.06, h + 0.06, -SINK, height, "panel")
    f.box(up, s0 - pw, s1 + pw, -h - 0.06, h + 0.06, height, INT_H, "panel")


def portal(lo, up, axis, s_c, width, height, c, out_sign, emblem=False):
    """'人口' plug-in: a block standing proud of the wall with a framed passage (23 总纲 DNA2)."""
    f = WallFrame(axis, c)
    h = EXT_T / 2
    t_front = out_sign * (h + PORTAL_OUT)
    t_back = -out_sign * (h - 0.05)
    ta, tb = sorted((t_front, t_back))
    pw, lh, cheek = 0.55, 0.7, 0.3
    s0, s1 = s_c - width / 2, s_c + width / 2
    e0, e1 = s0 - pw - cheek, s1 + pw + cheek
    for a, b in ((e0, s0), (s1, e1)):
        sbox(lo, up, f, a, b, ta, tb, 0.35, height, "shell")
        f.box(lo, a - 0.03, b + 0.03, ta - 0.05 * out_sign * 0 - 0.05, tb + 0.05, -SINK, 0.4, "dark")
        f.box(lo, a - 0.03, b + 0.03, ta - 0.04, tb + 0.04, 1.04, CUT, "panel")
    f.box(up, e0, e1, ta, tb, height, PORTAL_TOP, "shell")                       # top block
    f.box(up, e0 - 0.06, e1 + 0.06, ta - 0.06, tb + 0.06, PORTAL_TOP, PORTAL_TOP + 0.22, "panel")  # cap
    # front frame (proud of the portal face)
    tf0, tf1 = sorted((t_front, t_front + out_sign * 0.2))
    for a, b in ((s0 - pw, s0), (s1, s1 + pw)):
        sbox(lo, up, f, a, b, tf0, tf1, -SINK, height, "panel")
        f.box(lo, a - 0.08, b + 0.08, tf0 - 0.08, tf1 + 0.08, -SINK, 0.55, "dark")  # frame feet
    f.box(up, s0 - pw, s1 + pw, tf0, tf1, height, height + lh, "panel")       # lintel
    if emblem and axis == "x":
        zc = (height + lh + PORTAL_TOP) / 2
        y_face = c + t_front
        sg = out_sign
        up.box(s_c - 0.34, y_face, zc - 0.32, s_c + 0.34, y_face + sg * 0.08, zc + 0.32, "panel")
        y0 = y_face + sg * 0.08
        up.ring_y(s_c, y0 + sg * 0.05, y0 - 0.01 * sg, zc, 0.25, 0.16, "glow")
    # passage cutter for the vault skin (Blender coords)
    p0 = f.xyz(s0, min(ta, tb) - 0.3, -0.5)
    p1 = f.xyz(s1, max(ta, tb) + 0.3, height)
    return (min(p0[0], p1[0]), min(p0[1], p1[1]), p0[2], max(p0[0], p1[0]), max(p0[1], p1[1]), p1[2]), (e0, e1)


def post(lo, up, x, y, size, z1, cid="panel"):
    split_z(lo, up, lambda p, a, b: p.box(x - size / 2, y - size / 2, a, x + size / 2, y + size / 2, b, cid),
            -SINK, z1)


def pilaster(lo, up, s, c, out_sign):
    f = WallFrame("x", c)
    h = EXT_T / 2
    t0, t1 = (h - 0.03, h + PIL_PROUD) if out_sign > 0 else (-h - PIL_PROUD, -h + 0.03)
    sbox(lo, up, f, s - RIB_W / 2, s + RIB_W / 2, t0, t1, -SINK, SPRING + 0.05, "panel")
    foot(lo, s, c, out_sign)


def foot(lo, s, c, out_sign):
    """Buttress foot under a rib: 1.0 wide, 0.7 out, 1.1 tall, chamfered outer top edge, bolt plate."""
    h = EXT_T / 2
    w, d, hh, ch = 1.0, 0.7, 1.1, 0.3
    t0, t1 = out_sign * h, out_sign * (h + d)
    prof = [(c + t0, -SINK), (c + t1, -SINK), (c + t1, hh - ch), (c + t1 - out_sign * ch, hh), (c + t0, hh)]
    lo.prism_x(s - w / 2, s + w / 2, prof, "dark")
    y_face = c + t1
    lo.box(s - 0.18, y_face, 0.34, s + 0.18, y_face + out_sign * 0.05, 0.66, "panel")


# ------------------------------------------------------------------ roof
def gable_piece(part, xa, xb, ya, yb, zbot, half, cid="shell"):
    """Infill between z = zbot and the vault's outer arc over y in [ya, yb] (clipped to where arc > zbot)."""
    lim = None
    R = (half * half + VAULT_RISE * VAULT_RISE) / (2 * VAULT_RISE)
    cz = SPRING + VAULT_RISE - R
    if zbot + 0.08 > cz:
        lim = math.sqrt(max(0.0, R * R - (zbot + 0.08 - cz) ** 2))
        ya, yb = max(ya, -lim), min(yb, lim)
    if yb - ya < 0.05:
        return
    m = max(4, int((yb - ya) / 0.4))
    pts = [(ya + (yb - ya) * i / m, None) for i in range(m + 1)]
    pts = [(y, K.arc_z(y, half, SPRING, VAULT_RISE) - 0.03) for y, _ in pts]
    prof = [(ya, zbot), (yb, zbot)] + list(reversed(pts))
    part.prism_x(xa, xb, prof, cid)


def build_roof(skin, ribs, gable, x0, x1, half_in, rib_xs, cutters, east_portal_span):
    half = half_in + VAULT_OVER
    prof, mask, R, cz = K.vault_profile(half, SPRING, VAULT_RISE, ROOF_T, 40)
    skin.prism_x(x0 - END_EAVE, x1 + END_EAVE, prof, "shell", smooth_mask=mask)
    a0 = math.asin(min(1.0, half / R))
    n = 40
    band = []
    for i in range(n + 1):
        t = -a0 + 2 * a0 * i / n
        band.append(((R + RIB_PROUD) * math.sin(t), cz + (R + RIB_PROUD) * math.cos(t)))
    for i in range(n, -1, -1):
        t = -a0 + 2 * a0 * i / n
        band.append(((R - 0.03) * math.sin(t), cz + (R - 0.03) * math.cos(t)))
    band = list(reversed(band))
    bmask = [True] * len(band)
    for xr in rib_xs:
        xa = max(x0 - END_EAVE, xr - RIB_W / 2)
        xb = min(x1 + END_EAVE, xr + RIB_W / 2)
        ribs.prism_x(xa, xb, band, "panel", smooth_mask=bmask)
        ztop = cz + R + RIB_PROUD
        ribs.box(max(x0 - END_EAVE, xr - 0.45), -0.6, ztop - 0.14, min(x1 + END_EAVE, xr + 0.45), 0.6, ztop + 0.16,
                 "panel")
    # faint lengthwise panel seams on the skin, between the ribs (concept card panel rows)
    for ang in (-62, -38, -14, 14, 38, 62):
        t = math.radians(ang)
        dt = 0.05 / R
        seam = []
        for k in range(3):
            tt = t - dt + dt * k
            seam.append(((R + 0.025) * math.sin(tt), cz + (R + 0.025) * math.cos(tt)))
        for k in range(2, -1, -1):
            tt = t - dt + dt * k
            seam.append(((R - 0.02) * math.sin(tt), cz + (R - 0.02) * math.cos(tt)))
        seam = list(reversed(seam))
        for a, b in zip(rib_xs[:-1], rib_xs[1:]):
            ribs.prism_x(a + RIB_W / 2 - 0.02, b - RIB_W / 2 + 0.02, seam, "shell_seam",
                         smooth_mask=[True] * len(seam))
    for xr in rib_xs[1:-1]:
        for sg in (-1, 1):
            y = sg * (half_in + 0.08)
            ribs.box(xr - 0.42, y - 0.3, SPRING - 0.25, xr + 0.42, y + 0.3, SPRING + 0.3, "dark")
    # gables: west full, east around the side portal
    gable_piece(gable, x0, x0 + EXT_T, -half_in, half_in, 1.6, half)
    e0, e1 = east_portal_span
    gable_piece(gable, x1 - EXT_T, x1, e1, half_in, 1.6, half)
    gable_piece(gable, x1 - EXT_T, x1, -half_in, e0, 1.6, half)
    gable_piece(gable, x1 - EXT_T, x1, e0, e1, PORTAL_TOP + 0.22, half)


def leaf(doors, axis, s_c, width, c, height=2.75):
    f = WallFrame(axis, c)
    s0, s1 = s_c - width / 2, s_c + width / 2
    f.box(doors, s0, s1, -0.07, 0.07, 0.0, height, "dark")
    f.box(doors, s0 + 0.18, s1 - 0.18, -0.1, 0.1, 0.35, height - 0.35, "panel")
    f.box(doors, s_c - 0.32, s_c + 0.32, -0.12, 0.12, 1.45, 1.55, "glow")


def segment_endpoints(w):
    (cx, cz), (sx, sy, sz) = w["center_local"], w["size_xyz_m"]
    if sx >= sz:
        return "x", cx - sx / 2, cx + sx / 2, cz
    return "y", cz - sz / 2, cz + sz / 2, cx


def build(pilot):
    col_lo = K.ensure_collection("SC_Low")
    col_up = K.ensure_collection("SC_Up")
    col_roof = K.ensure_collection("SC_Roof")
    col_doors = K.ensure_collection("SC_Doors")
    col_f = K.ensure_collection("SC_Furniture")
    sx, _, sz = pilot["size_xyz_m"]
    hx, hy = sx / 2, sz / 2
    doors = {d["id"]: d for d in pilot["doors"]}
    made = []

    # ---- exterior shell
    lo = K.Part("SC_ExtWalls_Low")
    up = K.Part("SC_ExtWalls_Up")
    for w in pilot["wall_segments"]:
        if w["size_xyz_m"][1] < 5.0:
            continue
        axis, s0, s1, c = segment_endpoints(w)
        ext_wall(lo, up, axis, s0, s1, c)
    od, sd = doors["OUT-IN"], doors["SIDE-OUT"]
    cut_s, _ = portal(lo, up, "x", od["center_local"][0], od["width_m"], od["height_m"], od["center_local"][1], -1,
                      emblem=True)
    cut_e, east_span = portal(lo, up, "y", sd["center_local"][1], sd["width_m"], sd["height_m"],
                              sd["center_local"][0], 1)
    rib_xs = [-hx, -hx / 2, 0.0, hx / 2, hx]
    for x in (-hx, hx):
        for y in (-hy, hy):
            post(lo, up, x - math.copysign(0.05, x), y - math.copysign(0.05, y), 0.9, SPRING + 0.05)
    for xr in rib_xs[1:-1]:
        pilaster(lo, up, xr, -hy + EXT_T / 2, -1)
        pilaster(lo, up, xr, hy - EXT_T / 2, 1)
    for x in (-hx + 0.95, hx - 0.95):
        foot(lo, x, -hy + EXT_T / 2, -1)
        foot(lo, x, hy - EXT_T / 2, 1)
    made += [lo.finish(col_lo, bevel=0.035, seed=11), up.finish(col_up, bevel=0.035, ground_dark=False, seed=12)]

    # ---- interior walls
    ilo = K.Part("SC_IntWalls_Low")
    iup = K.Part("SC_IntWalls_Up")
    segs = []
    for w in pilot["wall_segments"]:
        if w["size_xyz_m"][1] >= 5.0:
            continue
        axis, s0, s1, c = segment_endpoints(w)
        segs.append((axis, s0, s1, c))
        int_wall(ilo, iup, axis, s0, s1, c)
    frame_pts = []
    for d in pilot["doors"]:
        if d["id"] in ("OUT-IN", "SIDE-OUT"):
            continue
        cx, cz = d["center_local"]
        if d["axis"] == "z":
            int_door_frame(ilo, iup, "x", cx, d["width_m"], d["height_m"], cz)
            frame_pts += [(cx - d["width_m"] / 2, cz), (cx + d["width_m"] / 2, cz)]
        else:
            int_door_frame(ilo, iup, "y", cz, d["width_m"], d["height_m"], cx)
            frame_pts += [(cx, cz - d["width_m"] / 2), (cx, cz + d["width_m"] / 2)]
    pts = []
    for axis, s0, s1, c in segs:
        for s in (s0, s1):
            pts.append((s, c) if axis == "x" else (c, s))
    for _, a0, a1, yc in [s for s in segs if s[0] == "x"]:
        for _, b0, b1, xc in [s for s in segs if s[0] == "y"]:
            if a0 - 0.01 <= xc <= a1 + 0.01 and b0 - 0.01 <= yc <= b1 + 0.01:
                pts.append((xc, yc))
    uniq = []
    for p in pts:
        if abs(p[0]) > hx - EXT_T - 0.05 or abs(p[1]) > hy - EXT_T - 0.05:
            continue
        if any(abs(p[0] - q[0]) < 0.3 and abs(p[1] - q[1]) < 0.3 for q in frame_pts):
            continue
        if any(abs(p[0] - q[0]) < 0.05 and abs(p[1] - q[1]) < 0.05 for q in uniq):
            continue
        uniq.append(p)
    for x, y in uniq:
        post(ilo, iup, x, y, 0.36, INT_H + 0.1)
    made += [ilo.finish(col_lo, bevel=0.025, seed=21), iup.finish(col_up, bevel=0.025, ground_dark=False, seed=22)]

    # ---- roof
    skin, ribs, gable = K.Part("SC_Roof_Skin"), K.Part("SC_Roof_Ribs"), K.Part("SC_Roof_Gables")
    build_roof(skin, ribs, gable, -hx, hx, hy, rib_xs, [cut_s, cut_e], east_span)
    made.append(skin.finish(col_roof, bevel=0.04, ground_dark=False, seed=31, cutters=[cut_s]))
    made.append(ribs.finish(col_roof, bevel=0.04, ground_dark=False, seed=32))
    made.append(gable.finish(col_roof, bevel=0.035, ground_dark=False, seed=33))

    # ---- closed elite doors
    for did in ("H-E", "C-E", "D-E"):
        d = doors[did]
        p = K.Part("SC_DoorLeaf_" + did)
        cx, cz = d["center_local"]
        if d["axis"] == "z":
            leaf(p, "x", cx, d["width_m"], cz)
        else:
            leaf(p, "y", cz, d["width_m"], cx)
        made.append(p.finish(col_doors, bevel=0.02, seed=41))

    # ---- furniture
    for fdef in pilot["furniture"]:
        p = K.Part("SC_F_" + fdef["id"])
        cx, cy = fdef["center_local"]
        fx, fh, fd = fdef["size_xyz_m"]
        FUR.BUILDERS[fdef["kind"]](p, cx, cy, fx, fh, fd)
        made.append(p.finish(col_f, bevel=0.018, seed=51))
    return made, {"junction_posts": len(uniq)}


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def main():
    o = args()
    pilot = json.load(open(o["pilot"], encoding="utf-8"))
    out = o["out"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    made, info = build(pilot)
    stats = {ob.name: tri_count(ob) for ob in made}
    os.makedirs(os.path.join(out, "blend"), exist_ok=True)
    blend = os.path.join(out, "blend", "SC_covered_house.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend)
    print("ER_JSON " + json.dumps({"ok": True, "blend": blend, "tris": stats, "total": sum(stats.values()), **info}))
    if o["render"]:
        import review
        review.render_all(out, "SC")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
