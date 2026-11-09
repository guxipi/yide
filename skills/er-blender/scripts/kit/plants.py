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


# ------------------------------------------------------------------ low-poly units (11-09: 勾哥 要面数预算)
# Triangle cost: leaf_card 4, flower_star 20, dome(u=10) ~50, vine leaf 4. Use these for anything that ships;
# the blob versions above are only for look-dev renders.
def leaf_card(p, base, direction, length, width, cid, fold=0.25):
    """Pointed leaf as a folded diamond: base, tip and two side points lifted along the midrib (4 tris,
    both sides drawn so it reads from below too)."""
    d = Vector(direction).normalized()
    side = d.cross(Vector((0, 0, 1)))
    if side.length < 1e-4:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(d).normalized()
    b = Vector(base)
    t = b + d * length
    m = b + d * (length * 0.42)
    l_ = m + side * (width / 2) - up * (width * fold)
    r_ = m - side * (width / 2) - up * (width * fold)
    bm = p.bm
    vb, vt, vl, vr = (bm.verts.new(v) for v in (b, t, l_, r_))
    fs = [bm.faces.new((vb, vl, vt)), bm.faces.new((vb, vt, vr))]
    p._tag(fs, cid, smooth=True)
    return fs


def flower_star(p, center, r, petal, heart="yolk", tilt=(0.0, 0.0), petals=5):
    """Flat five-petal outline (3 verts per petal: two shoulders + rounded tip) fanned from the centre,
    plus a small raised heart. ~20 tris."""
    rt = Matrix.Rotation(math.radians(tilt[0]), 3, "X") @ Matrix.Rotation(math.radians(tilt[1]), 3, "Y")
    c = Vector(center)
    bm = p.bm
    ph = random.random() * math.tau
    ring = []
    for i in range(petals):
        a = ph + math.tau * i / petals
        for da, rr in ((-0.32, 0.72), (0.0, 1.0), (0.32, 0.72)):
            ring.append(c + rt @ Vector((math.cos(a + da) * r * rr, math.sin(a + da) * r * rr, 0.0)))
    for i in range(petals):                       # notch between petals
        pass
    vc = bm.verts.new(c + rt @ Vector((0, 0, r * 0.05)))
    vr = [bm.verts.new(v) for v in ring]
    fs = [bm.faces.new((vc, vr[i], vr[(i + 1) % len(vr)])) for i in range(len(vr))]
    p._tag(fs, petal, smooth=True)
    hc = [bm.verts.new(c + rt @ Vector((math.cos(math.tau * k / 5) * r * 0.26, math.sin(math.tau * k / 5) * r * 0.26, r * 0.1)))
          for k in range(5)]
    top = bm.verts.new(c + rt @ Vector((0, 0, r * 0.18)))
    hf = [bm.faces.new((top, hc[k], hc[(k + 1) % 5])) for k in range(5)]
    p._tag(hf, heart, smooth=True)
    return fs + hf


def dome(p, cx, cy, z, rx, ry, h, cid, u=10, v=3):
    """Low-poly half ellipsoid (foliage base mass that hides the soil)."""
    bm = p.bm
    rings = []
    for j in range(v):
        e = (math.pi / 2) * j / v
        rings.append([bm.verts.new((cx + rx * math.cos(e) * math.cos(math.tau * i / u),
                                    cy + ry * math.cos(e) * math.sin(math.tau * i / u), z + h * math.sin(e)))
                      for i in range(u)])
    top = bm.verts.new((cx, cy, z + h))
    fs = []
    for j in range(v - 1):
        a, b = rings[j], rings[j + 1]
        fs += [bm.faces.new((a[i], a[(i + 1) % u], b[(i + 1) % u], b[i])) for i in range(u)]
    fs += [bm.faces.new((rings[-1][i], rings[-1][(i + 1) % u], top)) for i in range(u)]
    p._tag(fs, cid, smooth=True)
    return fs


def mound_lp(p, cx, cy, z, rx, ry, h, n_leaves, seed, spill=0.0, leaf_scale=1.0):
    """Low-poly mound: dome + n folded leaf cards in a radial rosette (~50 + 4n tris)."""
    rnd = random.Random(seed)
    dome(p, cx, cy, z, rx * 0.98, ry * 0.98, h * 0.85, "leaf_dk")
    for i in range(n_leaves):
        t = math.sqrt((i + rnd.random()) / n_leaves)             # stratified: even coverage with few leaves
        a = rnd.random() * math.tau
        bx, by = cx + math.cos(a) * rx * t * 0.8, cy + math.sin(a) * ry * t * 0.8
        bz = z + h * (1 - t * t) * 0.85
        out = Vector((math.cos(a), math.sin(a), 0))
        upz = 0.55 - t * (0.75 + spill)
        L = rnd.uniform(0.5, 0.68) * leaf_scale
        cid = rnd.choice(("leaf", "leaf", "leaf_dk", "leaf_lt"))
        leaf_card(p, (bx, by, bz), out + Vector((0, 0, upz)), L, L * 0.55, cid)


def vine_lp(p, start, drop, n, seed):
    rnd = random.Random(seed)
    x, y, z = start
    for i in range(n):
        t = i / max(1, n - 1)
        side = 1 if i % 2 else -1
        leaf_card(p, (x + 0.03 * side, y, z - drop * t), (side * 0.7, -0.5, -0.3), rnd.uniform(0.13, 0.18), 0.1,
                  "leaf_dk" if i % 3 else "leaf")


def tris(obj):
    """Triangle count of an object's mesh (for the budget gate)."""
    obj.data.calc_loop_triangles()
    return len(obj.data.loop_triangles)
