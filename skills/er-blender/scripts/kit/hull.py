"""Broken federal 'horizontal hull' (横卧舱) generator for J01 hullN / hullM / hullW and hull ruins.

Design source (J01_POI_design.json rooms NC / MB / SWC): walk-through broken hull, 6.5 m breach at both short
ends, no roof over the passage, the tall shell stays on the far (north) side, equipment on one side band.
Look source: J01_PN_card_v3 (dark ribbed side walls, white chamfered end caps with dark corner bumpers,
glow ring on the end, chunky white legs with dark round pads, torn white roof skin with thickness).
23 总纲 DNA2: hull = long box, rounded only on the four long edges.

Local frame: X along the hull length, +Y = north (far side), Z up, origin at ground centre. No floor.
"""
import math
import random

import kitlib as K

WALL_T = 0.5
END_T = 1.0


def _jag_top(s0, s1, base, amp, rnd, step=(1.0, 2.2)):
    """Chunky broken top edge (mo.co / card read): flat plateaus joined by short 45-ish chamfers,
    the odd single notch; no sharp spikes. Returns [(s, z), ...] from s0 to s1."""
    pts = []
    s = s0
    z = base + rnd.uniform(-amp, amp) * 0.5
    pts.append((s, z))
    while s < s1 - 0.01:
        w = rnd.uniform(*step)
        s2 = min(s1, s + w)
        # plateau
        e = max(s, s2 - 0.3)
        pts.append((e, z))
        if rnd.random() < 0.18 and e - s > 1.2:
            m = (s + e) / 2
            pts[-1:] = [(m - 0.3, z), (m - 0.12, z - 0.35), (m + 0.12, z - 0.35), (m + 0.3, z), (e, z)]
        z2 = max(0.6, base + rnd.uniform(-amp, amp))
        pts.append((s2, z2))
        z = z2
        s = s2
    return pts


def jag_wall_x(part, x0, x1, y0, y1, z_bot, base, amp, cid, rnd):
    """Wall along X between y0..y1 whose top is a broken edge."""
    top = _jag_top(x0, x1, base, amp, rnd)
    prof = [(x0, z_bot), (x1, z_bot)] + list(reversed(top))
    part.prism_y(y0, y1, prof, cid)
    return top


def ribs_x(part, x0, x1, y_face, out_sign, z0, top_fn, spacing=2.4, w=0.32, proud=0.14):
    n = max(1, int(round((x1 - x0) / spacing)))
    for i in range(1, n):
        x = x0 + (x1 - x0) * i / n
        zt = top_fn(x) - 0.1
        if zt - z0 < 0.4:
            continue
        ya, yb = sorted((y_face, y_face + out_sign * proud))
        part.box(x - w / 2, ya - 0.02 * out_sign, z0, x + w / 2, yb, zt, "dark")


def _interp(top, s):
    for (a, za), (b, zb) in zip(top, top[1:]):
        if a <= s <= b:
            return za + (zb - za) * (s - a) / max(1e-6, b - a)
    return top[-1][1]


def roof_remnant(part, x0, x1, y_out, H, rnd, inward_sign, w_range=(1.2, 3.0), thick=0.55, r=0.4):
    """Torn white roof skin along the tall wall: rounded outer long edge, jagged inner edge in plan."""
    s = x0
    while s < x1 - 0.01:
        seg = min(x1, s + rnd.uniform(1.0, 2.4))
        w = rnd.uniform(*w_range)
        yo = y_out
        yi = y_out + inward_sign * w
        # (y, z) cross-section, rounded outer long edge (3-step arc), torn inner edge
        prof = [
            (yo, H - thick - 0.35),
            (yo, H - r),
            (yo + inward_sign * r * (1 - math.cos(math.radians(30))), H - r + r * math.sin(math.radians(30))),
            (yo + inward_sign * r * (1 - math.cos(math.radians(60))), H - r + r * math.sin(math.radians(60))),
            (yo + inward_sign * r, H),
            (yi, H),
            (yi - inward_sign * 0.18, H - thick),
            (yo + inward_sign * WALL_T, H - thick),
            (yo + inward_sign * WALL_T, H - thick - 0.35),
        ]
        if inward_sign > 0:
            prof = list(reversed(prof))
        smooth = [False] * len(prof)
        part.prism_x(s, seg, prof, "shell", smooth_mask=smooth)
        s = seg


def end_block(part, x_end, sgn, y0, y1, z_top, top_jag=None, glow=False, rnd=None):
    """White end-cap jamb block at one short end (x_end = outer face), chamfered vertical corners,
    dark corner bumpers, dark inset panel (+ glow ring) on the end face."""
    xa, xb = (x_end - sgn * END_T, x_end)
    xa, xb = min(xa, xb), max(xa, xb)
    if top_jag is None:
        part.box(xa, y0, 0.0 - 0.3, xb, y1, z_top, "shell")
    else:
        top = _jag_top(y0, y1, z_top, top_jag, rnd)
        prof = [(y0, -0.3), (y1, -0.3)] + list(reversed(top))
        part.prism_x(xa, xb, prof, "shell")
    zt = z_top if top_jag is None else z_top - top_jag
    # dark corner bumpers on the outer vertical edges
    xo0, xo1 = (x_end - sgn * 0.55, x_end + sgn * 0.12)
    xo0, xo1 = min(xo0, xo1), max(xo0, xo1)
    for yy in (y0, y1):
        part.box(xo0, yy - 0.3, -0.3, xo1, yy + 0.3, min(1.4, zt), "dark")
        if zt > 3.0:
            part.box(xo0, yy - 0.3, zt - 1.2, xo1, yy + 0.3, zt + 0.05, "dark")
    if zt > 3.0 and (y1 - y0) > 2.2:
        # inset panel on the end face
        xf0, xf1 = (x_end, x_end + sgn * 0.08)
        xf0, xf1 = min(xf0, xf1), max(xf0, xf1)
        part.box(xf0, y0 + 0.55, 1.6, xf1, y1 - 0.55, zt - 1.4, "panel")
        if glow:
            ring_x(part, x_end + sgn * 0.08, sgn, (y0 + y1) / 2, (1.6 + zt - 1.4) / 2, 0.45, 0.3)


def ring_x(part, x_face, sgn, yc, zc, ro, ri, seg=24):
    bm = part.bm
    x0, x1 = x_face, x_face + sgn * 0.05
    oa, ob, ia, ib = [], [], [], []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        c, s = math.cos(t), math.sin(t)
        oa.append(bm.verts.new((x0, yc + ro * c, zc + ro * s)))
        ob.append(bm.verts.new((x1, yc + ro * c, zc + ro * s)))
        ia.append(bm.verts.new((x0, yc + ri * c, zc + ri * s)))
        ib.append(bm.verts.new((x1, yc + ri * c, zc + ri * s)))
    fs = []
    for i in range(seg):
        j = (i + 1) % seg
        fs.append(bm.faces.new((oa[i], oa[j], ia[j], ia[i])))
        fs.append(bm.faces.new((ob[j], ob[i], ib[i], ib[j])))
        fs.append(bm.faces.new((oa[j], oa[i], ob[i], ob[j])))
        fs.append(bm.faces.new((ia[i], ia[j], ib[j], ib[i])))
    part._tag(fs, "glow", smooth=True)


def leg(part, x, y_face, out_sign, z, size=1.1, pad_r=0.42):
    """Drop leg sticking out of a wall face: white block + dark round pad (card PN)."""
    ya, yb = sorted((y_face, y_face + out_sign * 0.8))
    part.box(x - size / 2, ya, z - size / 2, x + size / 2, yb, z + size / 2, "shell")
    y0 = y_face + out_sign * 0.8
    yc0, yc1 = sorted((y0, y0 + out_sign * 0.28))
    part.cylinder_y(x, yc0, yc1, z, pad_r, "dark", seg=20)
    yd0, yd1 = sorted((y0 + out_sign * 0.28, y0 + out_sign * 0.34))
    part.cylinder_y(x, yd0, yd1, z, pad_r * 0.55, "panel", seg=16)


def build_hull(prefix, L, D, H, collection, seed=1, passage=6.5, equip_side=1, overturned=False,
               south_base=1.6, south_amp=0.6):
    """Returns the created objects. equip_side: +1 equipment band north, -1 south (passage shifts away)."""
    rnd = random.Random(seed)
    hx, hy = L / 2, D / 2
    band = (D - passage)
    # passage position: the equipment band takes ~65% of the leftover depth
    big = band * 0.65
    if equip_side > 0:
        p0, p1 = -hy + (band - big), -hy + (band - big) + passage
    else:
        p0, p1 = -hy + big, -hy + big + passage
    shell = K.Part(prefix + "_Shell")
    legs = K.Part(prefix + "_Legs")
    xi0, xi1 = -hx + END_T, hx - END_T

    # ---- north tall wall (far side), dark ribbed
    yN0, yN1 = hy - WALL_T, hy
    shell.box(xi0, yN0, -0.3, xi1, yN1, H - 0.55, "panel")
    shell.box(xi0, yN0 - 0.04, -0.3, xi1, yN1 + 0.06, 0.45, "dark")                    # base skid
    ribs_x(shell, xi0, xi1, yN1, 1, 0.45, lambda x: H - 0.55)
    # inner face: white panels between dark frame ribs, rails at 1.2 m and under the roof remnant
    shell.box(xi0, yN0 - 0.03, 0.45, xi1, yN0 + 0.01, H - 0.9, "shell_in")
    ribs_x(shell, xi0, xi1, yN0 - 0.02, -1, 0.0, lambda x: H - 0.9, spacing=2.4, w=0.36, proud=0.16)
    shell.box(xi0, yN0 - 0.14, 1.05, xi1, yN0, 1.3, "panel")
    shell.box(xi0, yN0 - 0.14, H - 1.6, xi1, yN0, H - 1.35, "panel")
    roof_remnant(shell, xi0 - 0.2, xi1 + 0.2, hy, H, rnd, -1, w_range=(2.2, 3.8))

    # ---- south low broken wall (camera side)
    yS0, yS1 = -hy, -hy + WALL_T
    top = jag_wall_x(shell, xi0, xi1, yS0, yS1, -0.3, south_base, south_amp, "panel", rnd)
    shell.box(xi0, yS0 - 0.06, -0.3, xi1, yS1 + 0.04, 0.45, "dark")
    ribs_x(shell, xi0, xi1, yS0, -1, 0.45, lambda x: _interp(top, x), spacing=2.4)
    # white torn skin chunks riding on the low wall top (card: broken white skin with thickness)
    s = xi0
    while s < xi1 - 0.5:
        e = min(xi1, s + rnd.uniform(1.0, 2.2))
        if rnd.random() < 0.55:
            zt = min(_interp(top, s), _interp(top, e))
            shell.box(s + 0.05, yS0 - 0.08, zt - 0.35, e - 0.05, yS1 + 0.25, zt + 0.12, "shell")
        s = e

    # ---- ends: jamb blocks either side of the 6.5 m breach, no lintel (no roof over the passage)
    for x_end, sg in ((-hx, -1), (hx, 1)):
        end_block(shell, x_end, sg, p1, hy, H, glow=(sg < 0))
        end_block(shell, x_end, sg, -hy, p0, 3.6, top_jag=1.0, rnd=rnd)

    # ---- legs: along the outer base of both long walls (upright) or sticking out north (overturned)
    if overturned:
        for x in (xi0 + 2.0, 0.0, xi1 - 2.0):
            leg(legs, x, hy + 0.06, 1, 1.4)
            leg(legs, x, hy + 0.06, 1, H - 2.0)
    else:
        for x in (xi0 + 1.2, xi1 - 1.2):
            leg(legs, x, hy + 0.06, 1, 0.75, size=1.0, pad_r=0.38)
            leg(legs, x, -hy - 0.06, -1, 0.75, size=1.0, pad_r=0.38)
    objs = [shell.finish(collection, bevel=0.05, seed=seed), legs.finish(collection, bevel=0.04, seed=seed + 1)]
    return objs, {"passage_y": [round(p0, 2), round(p1, 2)]}
