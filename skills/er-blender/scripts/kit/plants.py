"""Plant units for POI props (Blender, background-safe) - 11-09 PARK v0, NOT yet approved by 勾哥.

Add to any kitlib.Part (palette ids must exist in kitlib.PALETTE: leaf, leaf_dk, leaf_lt, yolk + petal colours):
  leaf(p, base, direction, length, width, cid)       pointed leaf (tapered ellipsoid)
  flower(p, center, r, petal_cid, heart, tilt)        five round petals + domed heart
  mound(p, cx, cy, z, rx, ry, h, n, seed, spill, leaf_scale)
                                                      green base mass (hides soil) + radial rosette of leaves;
                                                      spill > 0 hangs the outer ring over the rim, < 0 stands leaves up
  vine(p, start, drop, sway, n, seed)                 chain of small leaves hanging over an edge
Recipe that matched the PARK parts sheet best (round planter): soil ~6 cm below the rim, mound h ~0.36 m,
~85 leaves 0.42-0.58 m, flowers r 0.22-0.28 sitting ~0.2 m above the leaf surface. Troughs: two mound
passes (outer spill + inner upright), leaf size scaled by trough width (scale = clamp(width / 1.2, 0.5, 1)).
Finish plant Parts with bevel=0, ground_dark=False, jitter=0.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector


def blob(p, pos, radii, cid, rot=None, u=12, v=8, taper=0.0):
    """Smooth ellipsoid (leaf, petal, ball) at pos with semi-axes radii, rotated by matrix rot.
    taper > 0 pinches the +X end to a point (leaf tip)."""
    bm = p.bm
    ret = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=1.0)
    vs = ret["verts"]
    if taper:
        for vv in vs:
            k = 1.0 - taper * max(0.0, vv.co.x) ** 1.3
            vv.co.y *= k
            vv.co.z *= k
    m = Matrix.Translation(pos) @ (rot.to_4x4() if rot is not None else Matrix.Identity(4)) @ Matrix.Diagonal((*radii, 1.0))
    bmesh.ops.transform(bm, matrix=m, verts=vs)
    fs = list({f for vv in vs for f in vv.link_faces})
    p._tag(fs, cid, smooth=True)
    return fs


def leaf(p, base, direction, length, width, cid):
    d = Vector(direction).normalized()
    rot = d.to_track_quat("X", "Z").to_matrix()
    blob(p, Vector(base) + d * (length / 2), (length / 2, width / 2, width * 0.14), cid, rot, u=12, v=6, taper=0.85)


def flower(p, center, r, petal, heart="yolk", tilt=(0.0, 0.0)):
    """Five round petals + domed heart, facing up (tilted by tilt degrees about X/Y)."""
    rt = Matrix.Rotation(math.radians(tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y")
    c = Vector(center)
    ph = random.random() * math.tau
    for i in range(5):
        a = ph + math.tau * i / 5
        off = rt @ Vector((math.cos(a) * r * 0.55, math.sin(a) * r * 0.55, 0.0))
        prot = rt @ Matrix.Rotation(a, 3, "Z")
        blob(p, c + off, (r * 0.5, r * 0.42, r * 0.12), petal, prot, u=10, v=6)
    blob(p, c + rt @ Vector((0, 0, r * 0.08)), (r * 0.28, r * 0.28, r * 0.16), heart, rt, u=10, v=6)


def mound(p, cx, cy, z, rx, ry, h, n_leaves, seed, spill=0.0, leaf_scale=1.0):
    """Dome of leaves pointing outward / upward over a smooth green base mass (hides the soil);
    spill > 0 lets the outer ring hang over the rim."""
    rnd = random.Random(seed)
    blob(p, (cx, cy, z), (rx * 0.98, ry * 0.98, h * 0.85), "leaf_dk", u=24, v=12)
    for i in range(n_leaves):
        t = math.sqrt(rnd.random())
        a = rnd.random() * math.tau
        bx, by = cx + math.cos(a) * rx * t * 0.85, cy + math.sin(a) * ry * t * 0.85
        bz = z + h * (1 - t * t) * 0.9
        out = Vector((math.cos(a), math.sin(a), 0))
        up = 0.55 - t * (0.75 + spill)
        L = rnd.uniform(0.42, 0.58) * (1.0 + 0.15 * (1 - t)) * leaf_scale
        cid = rnd.choice(("leaf", "leaf", "leaf_dk", "leaf_lt"))
        leaf(p, (bx, by, bz), out + Vector((0, 0, up)), L, L * 0.5, cid)


def vine(p, start, drop, sway, n, seed):
    rnd = random.Random(seed)
    x, y, z = start
    for i in range(n):
        t = i / max(1, n - 1)
        px = x + sway[0] * math.sin(t * 2.2)
        py = y + sway[1] * t
        pz = z - drop * t
        side = 1 if i % 2 else -1
        leaf(p, (px, py, pz), (side * 0.7, -0.4, -0.25), rnd.uniform(0.12, 0.17), 0.1, "leaf_dk" if i % 3 else "leaf")
