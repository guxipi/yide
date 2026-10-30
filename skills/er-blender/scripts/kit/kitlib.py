"""J01 federal building kit: shared helpers (Blender 5.2, background-safe).

Coordinate convention (matches pilot.json "local"):
    pilot local x  -> Blender X (east)
    pilot local z  -> Blender Y (north)
    height         -> Blender Z (up)
Every part is built as an accumulation of boxes / extruded profiles in one bmesh, each face tagged with a
palette id ("cid" face attribute). finish() bevels with a modifier, applies it, and writes the colour
attribute "Col" (linear float colour) from the palette plus a little ground darkening and per-block jitter.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector


# ------------------------------------------------------------------ palette (sRGB hex, converted to linear)
def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hexlin(h):
    h = h.lstrip("#")
    return tuple(_lin(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


PALETTE = {
    "shell": "#C6CFDD",      # federal shell white
    "shell_in": "#B7C0CF",   # interior wall face, a touch darker
    "panel": "#606F84",      # ribs, frames, trims
    "dark": "#465C6D",       # feet, skirts, door leaves
    "glow": "#8DFCF5",       # residual screen / ring (<=5% area)
    "seam": "#8E9BB0",       # recessed backer behind panel gaps (kept light: no dark outline lines)
    "shell_seam": "#A9B4C6",  # faint lengthwise panel lines on the vault skin
    "rock": "#B8665A",       # ore lumps (card PW hopper)
    "wood": "#C8743A",
    "strap": "#7D8A6A",
}
CID = {k: i for i, k in enumerate(PALETTE)}
COLORS = [hexlin(PALETTE[k]) for k in PALETTE]


# ------------------------------------------------------------------ builder
class Part:
    """Accumulates geometry for one exported object."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.cid = self.bm.faces.layers.int.new("cid")
        self.blk = self.bm.faces.layers.int.new("blk")   # block index -> colour jitter
        self.nblk = 0

    def _tag(self, faces, cid, smooth=False):
        # block key from the face centroid footprint (ignores Z) so a block split at the cutaway line
        # keeps one jitter value on both halves
        cx = sum(v.co.x for f in faces for v in f.verts) / max(1, sum(len(f.verts) for f in faces))
        cy = sum(v.co.y for f in faces for v in f.verts) / max(1, sum(len(f.verts) for f in faces))
        b = (int(round(cx * 10)) * 73856093 ^ int(round(cy * 10)) * 19349663 ^ CID[cid] * 83492791) & 0x7FFFFFFF
        for f in faces:
            f[self.cid] = CID[cid]
            f[self.blk] = b
            f.smooth = smooth
        return faces

    def box(self, x0, y0, z0, x1, y1, z1, cid):
        """Axis-aligned box from min corner to max corner (Blender coords)."""
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        if z1 < z0:
            z0, z1 = z1, z0
        bm = self.bm
        v = [bm.verts.new(p) for p in (
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1))]
        idx = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        faces = [bm.faces.new([v[i] for i in q]) for q in idx]
        return self._tag(faces, cid)

    def cbox(self, cx, cy, cz0, sx, sy, sz, cid):
        """Box centred in X/Y, sitting on z = cz0."""
        return self.box(cx - sx / 2, cy - sy / 2, cz0, cx + sx / 2, cy + sy / 2, cz0 + sz, cid)

    def prism_x(self, x0, x1, profile, cid, smooth_mask=None):
        """Extrude a closed YZ profile [(y, z), ...] (CCW seen from +X) along X from x0 to x1.
        smooth_mask[i] True -> side face i (between profile[i] and profile[i+1]) is shaded smooth."""
        bm = self.bm
        n = len(profile)
        a = [bm.verts.new((x0, y, z)) for y, z in profile]
        b = [bm.verts.new((x1, y, z)) for y, z in profile]
        faces = []
        faces.append(bm.faces.new(list(reversed(a))))
        faces.append(bm.faces.new(b))
        sides = []
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((a[i], a[j], b[j], b[i]))
            sides.append(f)
        self._tag(faces + sides, cid)
        if smooth_mask:
            for i, f in enumerate(sides):
                f.smooth = bool(smooth_mask[i])
        return faces + sides

    def prism_y(self, y0, y1, profile, cid, smooth_mask=None):
        """Extrude a closed XZ profile [(x, z), ...] along Y from y0 to y1."""
        bm = self.bm
        n = len(profile)
        a = [bm.verts.new((x, y0, z)) for x, z in profile]
        b = [bm.verts.new((x, y1, z)) for x, z in profile]
        faces = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
        sides = []
        for i in range(n):
            j = (i + 1) % n
            sides.append(bm.faces.new((a[j], a[i], b[i], b[j])))
        self._tag(faces + sides, cid)
        if smooth_mask:
            for i, f in enumerate(sides):
                f.smooth = bool(smooth_mask[i])
        return faces + sides

    def cylinder_y(self, cx, y0, y1, cz, r, cid, seg=16):
        """Cylinder along Y axis (e.g. a bolt / ring plate facing -Y)."""
        bm = self.bm
        a, b = [], []
        for i in range(seg):
            t = 2 * math.pi * i / seg
            x, z = cx + r * math.cos(t), cz + r * math.sin(t)
            a.append(bm.verts.new((x, y0, z)))
            b.append(bm.verts.new((x, y1, z)))
        faces = [bm.faces.new(a), bm.faces.new(list(reversed(b)))]
        sides = [bm.faces.new((a[i], b[i], b[(i + 1) % seg], a[(i + 1) % seg])) for i in range(seg)]
        self._tag(faces + sides, cid)
        for f in sides:
            f.smooth = True
        return faces + sides

    def ring_y(self, cx, y0, y1, cz, r_out, r_in, cid, seg=24):
        """Flat ring (annulus) extruded along Y, facing -Y."""
        bm = self.bm
        oa, ob, ia, ib = [], [], [], []
        for i in range(seg):
            t = 2 * math.pi * i / seg
            c, s = math.cos(t), math.sin(t)
            oa.append(bm.verts.new((cx + r_out * c, y0, cz + r_out * s)))
            ob.append(bm.verts.new((cx + r_out * c, y1, cz + r_out * s)))
            ia.append(bm.verts.new((cx + r_in * c, y0, cz + r_in * s)))
            ib.append(bm.verts.new((cx + r_in * c, y1, cz + r_in * s)))
        fs = []
        for i in range(seg):
            j = (i + 1) % seg
            fs.append(bm.faces.new((oa[i], oa[j], ia[j], ia[i])))      # front (-Y)
            fs.append(bm.faces.new((ob[j], ob[i], ib[i], ib[j])))      # back
            fs.append(bm.faces.new((oa[j], oa[i], ob[i], ob[j])))      # outer side
            fs.append(bm.faces.new((ia[i], ia[j], ib[j], ib[i])))      # inner side
        self._tag(fs, cid, smooth=True)
        return fs

    # -------------------------------------------------------------- finish
    def finish(self, collection, bevel=0.03, segments=2, angle_deg=35.0, ground_dark=True, jitter=0.03,
               seed=1, location=(0, 0, 0), cutters=()):
        """cutters: [(x0, y0, z0, x1, y1, z1), ...] boxes subtracted (Boolean EXACT) before the bevel."""
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        obj = bpy.data.objects.new(self.name, me)
        collection.objects.link(obj)
        tmp = []
        for i, (x0, y0, z0, x1, y1, z1) in enumerate(cutters):
            cm = bpy.data.meshes.new("_cut")
            cm.from_pydata([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
                            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], [],
                           [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])
            co = bpy.data.objects.new("_cut%d" % i, cm)
            collection.objects.link(co)
            co.hide_render = True
            tmp.append(co)
            bm_ = obj.modifiers.new("Cut%d" % i, "BOOLEAN")
            bm_.operation = "DIFFERENCE"
            bm_.object = co
            try:
                bm_.solver = "EXACT"
            except TypeError:
                pass
        if bevel > 0 or tmp:
            if bevel > 0:
                mod = obj.modifiers.new("Bevel", "BEVEL")
                mod.width = bevel
                mod.segments = segments
                mod.limit_method = "ANGLE"
                mod.angle_limit = math.radians(angle_deg)
                mod.use_clamp_overlap = True
                mod.harden_normals = True
            dg = bpy.context.evaluated_depsgraph_get()
            ev = obj.evaluated_get(dg)
            new = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
            obj.modifiers.clear()
            old = obj.data
            obj.data = new
            bpy.data.meshes.remove(old)
            new.name = self.name
            for co in tmp:
                m_ = co.data
                bpy.data.objects.remove(co)
                bpy.data.meshes.remove(m_)
        write_colors(obj.data, ground_dark=ground_dark, jitter=jitter, seed=seed)
        obj.location = location
        return obj


def write_colors(me, ground_dark=True, jitter=0.03, seed=1):
    """Colour attribute 'Col' (corner domain, linear float) from face 'cid' + 'blk' attributes."""
    cid = me.attributes.get("cid")
    blk = me.attributes.get("blk")
    if "Col" in me.color_attributes:
        me.color_attributes.remove(me.color_attributes["Col"])
    col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
    jit = {}
    verts = me.vertices
    for poly in me.polygons:
        c = COLORS[cid.data[poly.index].value] if cid else COLORS[0]
        b = blk.data[poly.index].value if blk else 0
        if b not in jit:
            jit[b] = 1.0 + jitter * (((b * 2654435761) % 2001) / 1000.0 - 1.0)
        k = jit[b]
        for li in poly.loop_indices:
            z = verts[me.loops[li].vertex_index].co.z
            g = 1.0
            if ground_dark:
                g = 0.80 + 0.20 * min(1.0, max(0.0, z / 0.9))
            col.data[li].color = (c[0] * k * g, c[1] * k * g, c[2] * k * g, 1.0)
    me.color_attributes.active_color = col
    me.attributes.default_color_name = "Col"


def ensure_collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(col)
    return col


def vault_profile(half_span, spring_z, rise, thick, nseg):
    """Closed YZ profile of a segmental barrel vault (outer arc then inner arc back).
    Returns (profile, smooth_mask)."""
    c = half_span
    R = (c * c + rise * rise) / (2 * rise)
    cz = spring_z + rise - R
    a0 = math.asin(c / R)
    outer, inner = [], []
    for i in range(nseg + 1):
        t = -a0 + 2 * a0 * i / nseg
        outer.append((R * math.sin(t), cz + R * math.cos(t)))
    Ri = R - thick
    for i in range(nseg, -1, -1):
        t = -a0 + 2 * a0 * i / nseg
        y = Ri * math.sin(t)
        inner.append((y, cz + Ri * math.cos(t)))
    prof = outer + inner
    # sides: outer arc segs (smooth), end cap (flat), inner arc (smooth), end cap (flat)
    mask = [True] * nseg + [False] + [True] * nseg + [False]
    # profile must be CCW seen from +X (Y right, Z up): outer goes from -y to +y along the top = clockwise.
    prof = list(reversed(prof))
    mask = list(reversed(mask[:-1])) + [mask[-1]]
    return prof, mask, R, cz


def arc_z(y, half_span, spring_z, rise):
    c = half_span
    R = (c * c + rise * rise) / (2 * rise)
    cz = spring_z + rise - R
    return cz + math.sqrt(max(0.0, R * R - y * y))
