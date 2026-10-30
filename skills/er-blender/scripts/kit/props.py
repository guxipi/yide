"""J01 federal plug-in / prop kit (kit keys from J01_POI_design.json, sizes from j01_poi_components.csv).

Each builder(p, sx, h, sd) builds at the origin (footprint centred, sits on z = 0, front faces -Y).
Language: shell-white bodies, panel-grey frames, dark bases/bumpers, glow #8DFCF5 only as residual
strips/rings (<5% area, dead state = most glow off). No floors; bases sink 0.05-0.3 m into the ground.
"""
import math

import bmesh

import furniture as FUR


def _cyl_x(p, x0, x1, cy, cz, r, cid, seg=20, smooth=True):
    bm = p.bm
    a, b = [], []
    for i in range(seg):
        t = 2 * math.pi * i / seg
        y, z = cy + r * math.cos(t), cz + r * math.sin(t)
        a.append(bm.verts.new((x0, y, z)))
        b.append(bm.verts.new((x1, y, z)))
    faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    sides = [bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i])) for i in range(seg)]
    p._tag(faces + sides, cid)
    for f in sides:
        f.smooth = smooth


def _cyl_z(p, cx, cy, z0, z1, r, cid, seg=20):
    bm = p.bm
    a = [bm.verts.new((cx + r * math.cos(2 * math.pi * i / seg), cy + r * math.sin(2 * math.pi * i / seg), z0))
         for i in range(seg)]
    b = [bm.verts.new((v.co.x, v.co.y, z1)) for v in a]
    faces = [bm.faces.new(list(reversed(a))), bm.faces.new(b)]
    sides = [bm.faces.new((a[i], a[(i + 1) % seg], b[(i + 1) % seg], b[i])) for i in range(seg)]
    p._tag(faces + sides, cid)
    for f in sides:
        f.smooth = True


def _chamfer_box_x(p, x0, x1, y0, y1, z0, z1, ch, cid):
    """Box with its four long (X) edges chamfered (DNA2: rounded only on the long edges)."""
    prof = [(y0 + ch, z0), (y1 - ch, z0), (y1, z0 + ch), (y1, z1 - ch), (y1 - ch, z1), (y0 + ch, z1),
            (y0, z1 - ch), (y0, z0 + ch)]
    p.prism_x(x0, x1, prof, cid)


def _rock(p, cx, cy, cz, r, cid="rock"):
    """Rounded chunky ore lump (subdivided icosphere, smooth) for hopper fills."""
    bm = p.bm
    geom = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=r)
    vs = geom["verts"]
    for v in vs:
        v.co.x = cx + v.co.x * 1.1
        v.co.y = cy + v.co.y
        v.co.z = cz + v.co.z * 0.8
    faces = list({f for v in vs for f in v.link_faces})
    p._tag(faces, cid, smooth=True)


# ------------------------------------------------------------------ builders
def receiver(p, sx, h, sd):
    """接收货口插件: heavy cargo-port portal with floor guide rails; port mouth faces -Y."""
    hx, hy = sx / 2, sd / 2
    mw, mh = sx * 0.52, h * 0.62
    p.box(-hx, -hy, -0.1, -mw / 2, hy, h - 0.25, "shell")
    p.box(mw / 2, -hy, -0.1, hx, hy, h - 0.25, "shell")
    p.box(-mw / 2, -hy, mh, mw / 2, hy, h - 0.25, "shell")
    p.box(-mw / 2, hy - 0.4, -0.1, mw / 2, hy, mh, "panel")                 # back plate of the mouth
    # dark portal frame on the front face
    for a, b in ((-mw / 2 - 0.45, -mw / 2), (mw / 2, mw / 2 + 0.45)):
        p.box(a, -hy - 0.15, -0.1, b, -hy + 0.1, mh + 0.45, "panel")
    p.box(-mw / 2 - 0.45, -hy - 0.15, mh, mw / 2 + 0.45, -hy + 0.1, mh + 0.45, "panel")
    p.box(-hx - 0.05, -hy - 0.05, -0.1, hx + 0.05, hy + 0.05, 0.35, "dark")
    p.box(-hx - 0.04, -hy - 0.04, h - 0.25, hx + 0.04, hy + 0.04, h, "panel")   # one cap over the top
    # guide rails out of the mouth (sign of in/out direction)
    for x in (-mw / 2 + 0.35, mw / 2 - 0.35):
        p.box(x - 0.12, -hy - 1.2, 0.0, x + 0.12, hy - 0.4, 0.22, "dark")
    p.box(-0.5, -hy - 0.17, mh + 0.12, 0.5, -hy - 0.12, mh + 0.3, "glow")
    for x in (-hx, hx - 0.5):
        p.box(x - 0.04, -hy - 0.08, -0.1, x + 0.54, -hy + 0.5, 1.0, "dark")   # corner bumpers


def crate(p, sx, h, sd):
    """制式货匣 (card PN cargo): white crate, two dark straps, dark corner caps."""
    hx, hy = sx / 2, sd / 2
    _chamfer_box_x(p, -hx + 0.05, hx - 0.05, -hy, hy, 0.0, h, 0.12, "shell")
    for x in (-hx * 0.45, hx * 0.45):
        p.box(x - 0.13, -hy - 0.04, -0.02, x + 0.13, hy + 0.04, h + 0.04, "panel")
        p.box(x - 0.18, -hy - 0.07, h * 0.42, x + 0.18, -hy - 0.02, h * 0.58, "dark")  # strap buckle
    for x in (-hx, hx - 0.32):
        for y in (-hy - 0.03, hy - 0.29):
            for z in (-0.02, h - 0.3):
                p.box(x, y, z, x + 0.32, y + 0.32, z + 0.32, "dark")


def medcase(p, sx, h, sd):
    """密封急救抽匣: sealed case, two drawers, small residual glow strip."""
    FUR.drawer(p, 0, 0, sx, h, sd)
    p.box(-0.3, -sd / 2 - 0.08, h - 0.32, 0.3, -sd / 2 - 0.03, h - 0.24, "glow")


def power_joint(p, sx, h, sd):
    """封闭能源脊接头: closed spine pipe stubs into a drum housing on short legs (dead: no glow)."""
    zc = h * 0.55
    r = min(sd, h) * 0.28
    _cyl_x(p, -sx / 2, sx / 2, 0, zc, r, "panel")
    _cyl_x(p, -0.55, 0.55, 0, zc, r * 1.55, "shell")
    for x in (-0.6, 0.6):
        _cyl_x(p, x - 0.08 if x < 0 else x, x if x < 0 else x + 0.08, 0, zc, r * 1.65, "dark")
    for x in (-sx / 2 + 0.25, sx / 2 - 0.25):
        _cyl_x(p, x - 0.1, x + 0.1, 0, zc, r * 1.2, "dark")
        p.box(x - 0.2, -0.35, -0.05, x + 0.2, 0.35, zc - r, "dark")       # short legs (0.5H rule)
        p.box(x - 0.35, -0.5, -0.05, x + 0.35, 0.5, 0.12, "dark")
    p.box(-0.3, -r * 1.55 - 0.05, zc - 0.05, 0.3, -r * 1.55 + 0.02, zc + 0.05, "seam")   # dead light line


def anchor(p, sx, h, sd):
    """折断轨道锚标 (card PW): white square mast on a dark base, glow band, broken stepped top."""
    p.box(-sx / 2, -sd / 2, -0.1, sx / 2, sd / 2, 0.5, "dark")
    p.box(-sx * 0.36, -sd * 0.36, 0.5, sx * 0.36, sd * 0.36, 1.6, "dark")
    c = sx * 0.3
    p.box(-c, -c, 1.6, c, c, h - 0.8, "shell")
    p.box(-c - 0.04, -c - 0.04, h * 0.62, c + 0.04, c + 0.04, h * 0.62 + 0.28, "glow")
    # broken top: three stepped chunks
    p.box(-c, -c, h - 0.8, 0.05, c, h, "shell")
    p.box(0.05, -c, h - 0.8, c, 0.1, h - 0.35, "shell")
    for x, y in ((-sx / 2, -sd / 2), (sx / 2 - 0.4, -sd / 2), (-sx / 2, sd / 2 - 0.4), (sx / 2 - 0.4, sd / 2 - 0.4)):
        p.box(x, y, -0.1, x + 0.4, y + 0.4, 0.7, "panel")


def sample_grid(p, sx, h, sd):
    """分选样本格: framed cubby rack, 3 x 2 slots, sealed canisters in some slots (category read)."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx, -hy, -0.05, hx, hy, 0.25, "dark")
    p.box(-hx, hy - 0.12, 0.25, hx, hy, h, "shell_in")
    cols, rows = 3, 2
    for i in range(cols + 1):
        x = -hx + i * sx / cols
        p.box(x - 0.07, -hy, 0.25, x + 0.07, hy, h, "panel")
    for j in range(rows + 1):
        z = 0.25 + j * (h - 0.35) / rows
        p.box(-hx, -hy, z, hx, hy, z + 0.1, "shell")
    cw = sx / cols
    rh = (h - 0.35) / rows
    filled = [(0, 0), (1, 0), (2, 1), (0, 1)]
    for (i, j) in filled:
        x = -hx + (i + 0.5) * cw
        z = 0.35 + j * rh
        _cyl_z(p, x - cw * 0.18, -0.1, z, z + rh * 0.7, 0.2, "shell")
        _cyl_z(p, x + cw * 0.18, -0.1, z, z + rh * 0.7, 0.2, "shell")
        p.box(x - cw * 0.38, -hy - 0.02, z + rh * 0.7, x + cw * 0.38, -hy + 0.05, z + rh * 0.8, "dark")


def vending(p, sx, h, sd):
    """人员区售货机 (dead): tall shell cabinet, big dark screen, dispenser slot, dark kick plate."""
    hx, hy = sx / 2, sd / 2
    _chamfer_box_x(p, -hx, hx, -hy, hy, 0.15, h, 0.18, "shell")
    p.box(-hx - 0.04, -hy - 0.04, -0.05, hx + 0.04, hy + 0.04, 0.3, "dark")
    p.box(-hx + 0.25, -hy - 0.06, h * 0.32, hx - 0.25, -hy + 0.05, h - 0.35, "dark")    # dead screen
    p.box(-hx + 0.35, -hy - 0.08, h - 0.55, -hx + 0.95, -hy - 0.05, h - 0.47, "glow")  # residual blip
    p.box(-0.6, -hy - 0.05, 0.45, 0.6, -hy + 0.3, 0.9, "panel")                         # dispenser
    p.box(-0.5, -hy - 0.06, 0.52, 0.5, -hy + 0.32, 0.82, "dark")


def rest_pod(p, sx, h, sd):
    """停用休息舱: lying capsule, long edges rounded, round hatch ring on the front, dark cradle."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx + 0.3, -hy + 0.2, -0.05, hx - 0.3, hy - 0.2, 0.55, "dark")
    _chamfer_box_x(p, -hx, hx, -hy, hy, 0.5, h, 0.7, "shell")
    p.box(-hx - 0.05, -hy + 0.3, 0.45, -hx + 0.25, hy - 0.3, h - 0.3, "panel")
    p.box(hx - 0.25, -hy + 0.3, 0.45, hx + 0.05, hy - 0.3, h - 0.3, "panel")
    zc = 0.5 + (h - 0.5) / 2
    p.ring_y(0.3, -hy - 0.12, -hy + 0.02, zc, 1.0, 0.72, "panel", seg=28)
    p.cylinder_y(0.3, -hy - 0.04, -hy + 0.02, zc, 0.72, "dark", seg=28)
    p.box(0.05, -hy - 0.16, zc - 0.06, 0.55, -hy - 0.1, zc + 0.06, "seam")             # dead lock ring


def clamp_seat(p, sx, h, sd):
    """已拆固定器接口座: low seat block with an empty saddle and two opened clamp bands."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx, -hy, -0.1, hx, hy, h * 0.42, "panel")
    p.box(-hx - 0.05, -hy - 0.05, -0.1, hx + 0.05, hy + 0.05, 0.3, "dark")
    p.box(-hx + 0.3, -hy + 0.3, h * 0.42, hx - 0.3, hy - 0.3, h * 0.48, "seam")          # pressed outline
    for x in (-hx * 0.55, hx * 0.55):
        p.box(x - 0.2, -hy + 0.35, h * 0.42, x + 0.2, hy - 0.35, h * 0.7, "dark")
        p.box(x - 0.09, -hy + 0.3, h * 0.7, x + 0.09, -hy + 0.5, h, "shell")
        p.box(x - 0.09, -hy + 0.3, h - 0.15, x + 0.09, 0.1, h, "shell")
    p.box(-0.25, hy - 0.2, h * 0.42, 0.25, hy + 0.05, h * 0.62, "dark")                   # data port


def spool(p, sx, h, sd):
    """封闭牵引卷盘: the drum is fully enclosed (no visible cable or drum, not a winch). Long white
    housing with rounded long edges, dark end discs show where the drum axle sits, dark plinth."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx, -hy, -0.1, hx, hy, 0.4, "dark")
    _chamfer_box_x(p, -hx + 0.35, hx - 0.35, -hy + 0.1, hy - 0.1, 0.4, h, 0.55, "shell")
    zc = (h + 0.4) / 2
    r = min(sd, h - 0.4) * 0.36
    for x0, x1 in ((-hx + 0.1, -hx + 0.35), (hx - 0.35, hx - 0.1)):
        _cyl_x(p, x0, x1, 0, zc, r, "dark", seg=24)
    for x in (-hx * 0.45, hx * 0.45):
        p.box(x - 0.16, -hy + 0.04, 0.4, x + 0.16, hy - 0.04, h + 0.04, "panel")      # bands
    p.box(-0.9, -hy + 0.06, zc - 0.35, 0.9, -hy + 0.12, zc + 0.35, "panel")           # service hatch
    p.box(-0.5, -hy + 0.02, zc - 0.05, 0.5, -hy + 0.07, zc + 0.05, "seam")


def pump(p, sx, h, sd):
    """停机取样泵壳 (card PM): two white chamfered housings split by a gap (the root goes through),
    dark plinth with feet, side elbow intake with flange, front vent panel, dead glow shaft ring."""
    hx, hy = sx / 2, sd / 2
    gap = 0.8
    p.box(-hx, -hy, -0.1, hx, hy, 0.45, "dark")
    for x in (-hx, hx - 0.7):
        p.box(x - 0.1, -hy - 0.15, -0.1, x + 0.8, hy + 0.15, 0.7, "dark")
    for a, b in ((-hx + 0.2, -gap / 2), (gap / 2, hx - 0.2)):
        _chamfer_box_x(p, a, b, -hy + 0.2, hy - 0.2, 0.45, h, 0.35, "shell")
        p.box((a + b) / 2 - 0.35, -0.4, h - 0.02, (a + b) / 2 + 0.35, 0.4, h + 0.22, "panel")   # lifting lugs
    _cyl_x(p, -gap / 2 - 0.05, gap / 2 + 0.05, 0, h * 0.45, 0.42, "dark")                         # shaft
    _cyl_x(p, -0.12, 0.12, 0, h * 0.45, 0.46, "glow")
    p.box(-hx + 0.6, -hy + 0.1, h * 0.3, -gap / 2 - 0.5, -hy + 0.22, h * 0.7, "panel")            # vent panel
    for z in (h * 0.42, h * 0.55):
        p.box(-hx + 0.8, -hy + 0.05, z, -gap / 2 - 0.7, -hy + 0.12, z + 0.07, "dark")
    # elbow intake on the west end (wet side)
    _cyl_x(p, -hx - 0.9, -hx + 0.25, 0, h * 0.5, 0.42, "panel")
    _cyl_x(p, -hx - 0.05, -hx + 0.2, 0, h * 0.5, 0.6, "dark")
    _cyl_z(p, -hx - 0.75, 0, 0.0, h * 0.5 + 0.2, 0.42, "panel")
    p.box(-hx - 1.25, -0.6, -0.1, -hx - 0.25, 0.6, 0.35, "dark")


def bench(p, sx, h, sd):
    """分体维修台: two split benches with a gap, tool rail above the back."""
    half = sx / 2 - 0.3
    FUR.repair(p, -sx / 4 - 0.15, 0, half, min(1.3, h), sd)
    FUR.repair(p, sx / 4 + 0.15, 0, half, min(1.3, h), sd)
    p.box(-sx / 2, sd / 2 - 0.12, 0.95, sx / 2, sd / 2, h, "panel")
    for x in (-sx * 0.3, -sx * 0.1, sx * 0.15, sx * 0.35):
        p.box(x - 0.06, sd / 2 - 0.3, h * 0.6, x + 0.06, sd / 2 - 0.12, h - 0.15, "dark")


def weigh(p, sx, h, sd):
    """断秤接收台 (card PW): low plate platform with tiles, corner bumpers, two hoppers in front
    (one full of ore lumps, one empty)."""
    hx, hy = sx / 2, sd / 2
    pd = sd * 0.62                       # platform depth (back part), hoppers in front
    y0 = hy - pd
    p.box(-hx, y0, -0.1, hx, hy, h * 0.55, "shell")
    p.box(-hx - 0.05, y0 - 0.05, -0.1, hx + 0.05, hy + 0.05, 0.3, "dark")
    for i in range(4):
        x = -hx + 0.3 + i * (sx - 0.6) / 4
        for j, cid in ((0, "panel"), (1, "shell_in")):
            yy = y0 + 0.3 + j * (pd - 0.6) / 2
            p.box(x + 0.04, yy + 0.04, h * 0.55, x + (sx - 0.6) / 4 - 0.04, yy + (pd - 0.6) / 2 - 0.04,
                  h * 0.55 + 0.05, cid if (i + j) % 2 == 0 else "shell")
    for x in (-hx, hx - 0.6):
        for y in (y0, hy - 0.6):
            p.box(x - 0.05, y - 0.05, h * 0.55 - 0.1, x + 0.65, y + 0.65, h * 0.55 + 0.2, "dark")
    # hoppers
    hw = sx * 0.3
    for k, xc in enumerate((-hx + hw / 2 + 0.2, -hx + hw * 1.5 + 0.45)):
        ya, yb = -hy, y0 - 0.1
        hh = h * 0.85
        p.box(xc - hw / 2, ya, -0.1, xc + hw / 2, yb, 0.25, "dark")
        for (a, b, c, d) in ((xc - hw / 2, xc - hw / 2 + 0.18, ya, yb), (xc + hw / 2 - 0.18, xc + hw / 2, ya, yb),
                             (xc - hw / 2, xc + hw / 2, ya, ya + 0.18), (xc - hw / 2, xc + hw / 2, yb - 0.18, yb)):
            p.box(a, c, 0.25, b, d, hh, "shell")
        p.box(xc - hw / 2 + 0.18, ya + 0.18, 0.25, xc + hw / 2 - 0.18, yb - 0.18, 0.35, "seam")
        for x in (xc - hw / 2 + 0.05, xc + hw / 2 - 0.3):
            p.box(x, ya - 0.06, 0.1, x + 0.25, ya + 0.02, hh - 0.05, "dark")                 # straps
        if k == 0:
            import random
            rnd = random.Random(5)
            for _ in range(9):
                _rock(p, xc + rnd.uniform(-hw / 2 + 0.5, hw / 2 - 0.5), rnd.uniform(ya + 0.5, yb - 0.5),
                      hh - 0.25 + rnd.uniform(-0.1, 0.1), rnd.uniform(0.3, 0.5))


def timber(p, sx, h, sd):
    """解捆边料托 (card PS timber): strapped plank bundle on a dark pallet skid, top straps undone."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx + 0.2, -hy, -0.05, hx - 0.2, hy, 0.25, "dark")
    rows, cols = 3, 5
    pw = (sd - 0.2) / cols
    ph = (h - 0.35) / rows
    import random
    rnd = random.Random(3)
    for r in range(rows):
        for c in range(cols):
            if r == rows - 1 and c in (0, 4):
                continue                                                   # unbundled: top corners gone
            y = -hy + 0.1 + c * pw
            z = 0.25 + r * ph
            dx = rnd.uniform(-0.25, 0.25)
            p.box(-hx + dx, y + 0.02, z + 0.02, hx + dx, y + pw - 0.02, z + ph - 0.02, "wood")
    for x in (-hx * 0.5, hx * 0.5):
        p.box(x - 0.2, -hy - 0.05, 0.2, x + 0.2, hy + 0.05, h - ph + 0.06, "strap")


def berth(p, sx, h, sd):
    """旧守卫归位接口: large U cradle for the old guard (crab armour interface), dead socket plate."""
    hx, hy = sx / 2, sd / 2
    p.box(-hx, -hy, -0.1, hx, hy, 0.5, "dark")
    for x in (-hx, hx - 1.4):
        _chamfer_box_x(p, x, x + 1.4, -hy + 0.2, hy - 0.2, 0.5, h - 0.3, 0.3, "shell")
        p.box(x - 0.05, -hy + 0.1, h - 0.4, x + 1.45, hy - 0.1, h, "panel")
    p.box(-hx + 1.4, hy - 1.0, 0.5, hx - 1.4, hy - 0.2, h * 0.55, "shell")        # back plate
    p.box(-1.2, hy - 1.06, 0.9, 1.2, hy - 0.98, h * 0.5, "panel")
    p.ring_y(0.0, hy - 1.12, hy - 1.04, h * 0.33, 0.55, 0.38, "seam", seg=24)       # dead socket
    for x in (-hx + 1.6, hx - 1.6):
        p.box(x - 0.3, -hy + 0.3, 0.5, x + 0.3, hy - 1.0, 0.8, "panel")                  # guide shoes


def tool(p, sx, h, sd):
    FUR.drawer(p, 0, 0, sx, h, sd)


# kit key -> (builder, (X, H, Z)) ; sizes = j01_poi_components.csv
PROPS = {
    "receiver": (receiver, (7.0, 3.1, 3.0)),
    "cargo": (crate, (2.4, 1.8, 1.8)),
    "med": (medcase, (2.2, 1.6, 1.5)),
    "power": (power_joint, (2.5, 1.8, 1.8)),
    "anchor": (anchor, (2.0, 7.0, 2.0)),
    "sample": (sample_grid, (3.6, 2.2, 1.8)),
    "vending": (vending, (2.5, 3.1, 2.0)),
    "rest": (rest_pod, (5.0, 3.7, 3.0)),
    "clamp": (clamp_seat, (3.8, 1.8, 2.8)),
    "spool": (spool, (5.0, 3.0, 3.0)),
    "pump": (pump, (5.5, 3.8, 4.0)),
    "bench": (bench, (6.0, 2.1, 2.4)),
    "weigh": (weigh, (8.0, 1.5, 4.0)),
    "timber": (timber, (7.0, 2.0, 3.5)),
    "berth": (berth, (9.0, 3.0, 5.0)),
    "tool": (tool, (2.8, 1.5, 1.6)),
}
