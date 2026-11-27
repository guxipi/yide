# 花坛灌木实验:同一个花坛,四种灌木做法,同机位出图。
# 用法: blender -b --factory-startup -P shrub_lab.py --python-exit-code 1 -- <outdir> [variants]
import bpy, bmesh, sys, os, math, json, random
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0].replace("\\", "/")
ONLY = argv[1].split(",") if len(argv) > 1 else None
os.makedirs(OUT, exist_ok=True)
GOLDEN = math.radians(137.5)
GREENS = [(0.10, 0.50, 0.08), (0.14, 0.60, 0.10), (0.07, 0.40, 0.09)]   # 线性,叶的固有色三档
CORE = (0.04, 0.22, 0.06)
NEW = (0.26, 0.66, 0.10)
OLD = (0.03, 0.26, 0.12)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.samples = 48
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.45, 0.52, 0.90, 1); bg.inputs[1].default_value = 0.55
    sun_d = bpy.data.lights.new("sun", 'SUN'); sun_d.energy = 3.2; sun_d.color = (1.0, 0.93, 0.82); sun_d.angle = math.radians(6)
    sun = bpy.data.objects.new("sun", sun_d); sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(38), 0, math.radians(215))
    return sc


def vcol_material(name="vc"):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes): nt.nodes.remove(n)
    a = nt.nodes.new('ShaderNodeAttribute'); a.attribute_name = "Col"
    d = nt.nodes.new('ShaderNodeBsdfDiffuse'); o = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(a.outputs['Color'], d.inputs['Color']); nt.links.new(d.outputs[0], o.inputs[0])
    return m


class Builder:
    """攒顶点 / 面 / 每面颜色 / 每顶点自定义法线(None = 用面法线)"""
    def __init__(self): self.v = []; self.f = []; self.fc = []; self.vn = []
    def add(self, verts, faces, col, normals=None):
        b = len(self.v)
        self.v += [tuple(p) for p in verts]
        self.vn += (list(normals) if normals is not None else [None] * len(verts))
        for f in faces: self.f.append(tuple(b + i for i in f)); self.fc.append(col)
    def to_object(self, name, mat, smooth):
        me = bpy.data.meshes.new(name); me.from_pydata(self.v, [], self.f); me.update()
        ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'CORNER')
        for p in me.polygons:
            p.use_smooth = smooth
            for li in p.loop_indices: ca.data[li].color = (*self.fc[p.index], 1.0)
        if any(n is not None for n in self.vn):
            ln = []
            for p in me.polygons:
                for li in p.loop_indices:
                    n = self.vn[me.loops[li].vertex_index]
                    ln.append(tuple(n) if n is not None else tuple(p.normal))
            me.normals_split_custom_set(ln)
        ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
        me.materials.append(mat)
        return ob


def box(B, c, s, col):
    cx, cy, cz = c; sx, sy, sz = (s[0] / 2, s[1] / 2, s[2] / 2)
    v = [(cx + dx * sx, cy + dy * sy, cz + dz * sz) for dz in (-1, 1) for dy in (-1, 1) for dx in (-1, 1)]
    B.add(v, [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)], col)


def ellipsoid(B, c, r, squash, col, seg=10, rings=6, sphere_normals=True):
    c = Vector(c); vs = []; ns = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        for j in range(seg):
            ph = 2 * math.pi * j / seg
            d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph), math.cos(th)))
            vs.append(c + Vector((d.x * r, d.y * r, d.z * r * squash))); ns.append(d)
    fs = []
    for i in range(rings):
        for j in range(seg):
            a = i * seg + j; b = i * seg + (j + 1) % seg
            fs.append((a, a + seg, b + seg, b))
    B.add(vs, fs, col, ns if sphere_normals else None)


def disc(B, c, r, h, col, seg=20):
    """现状的做法:一片光滑圆盘"""
    c = Vector(c); vs = [c + Vector((0, 0, h / 2)), c - Vector((0, 0, h / 2))]
    for z in (h / 2, -h / 2):
        for j in range(seg):
            ph = 2 * math.pi * j / seg; vs.append(c + Vector((math.cos(ph) * r, math.sin(ph) * r, z)))
    fs = []
    for j in range(seg):
        k = (j + 1) % seg
        fs += [(0, 2 + j, 2 + k), (1, 2 + seg + k, 2 + seg + j), (2 + j, 2 + seg + j, 2 + seg + k, 2 + k)]
    B.add(vs, fs, col)


def leaf_clump(B, rng, c, R, squash, n_leaves, leaf_len, leaf_w, sphere_normals, lift_deg=32, low=-0.30, normal_up_bias=0.25, irregular=False, soft=False):
    """一团叶:小尖叶按黄金角螺旋铺在一个压扁的球面上,叶尖朝外朝下,像瓦片一样一层压一层。
    每片叶 4 个三角(中脉略拱)。sphere_normals=True 时法线取「从团心指向顶点」,整团按一个球受光。"""
    c = Vector(c); up = Vector((0, 0, 1)); lift = math.radians(lift_deg)
    for i in range(n_leaves):
        z = 1 - (1 - low) * (i + 0.5) / n_leaves
        if irregular: z = max(low, min(1.0, z + rng.uniform(-0.06, 0.06)))
        rad = math.sqrt(max(0.0, 1 - z * z)); ph = i * GOLDEN + (rng.uniform(-0.5, 0.5) if irregular else 0.0)
        d = Vector((rad * math.cos(ph), rad * math.sin(ph), z))
        t = d * d.dot(up) - up
        if t.length < 1e-3: t = Vector((math.cos(ph), math.sin(ph), 0))
        t.normalize()
        yaw = rng.uniform(-0.35, 0.35)
        t = (Matrix.Rotation(yaw, 3, d) @ t).normalized()
        lf = math.radians(rng.uniform(14, 58)) if irregular else (math.radians(rng.uniform(16, 34)) if soft else lift)
        l = (math.cos(lf) * t + math.sin(lf) * d).normalized()
        n = (d - l * d.dot(l)).normalized(); s = l.cross(n).normalized()
        L = leaf_len * (rng.uniform(0.62, 1.45) if irregular else rng.uniform(0.78, 1.22)); W = leaf_w * rng.uniform(0.85, 1.15)
        if irregular and rng.random() < 0.06: L *= 1.5   # 少数几片飘出去,打破圆轮廓
        base = c + Vector((d.x * R, d.y * R, d.z * R * squash)) * 0.74
        mid = base + l * (L * 0.42)
        vs = [base, mid - s * (W / 2), mid + s * (W / 2), base + l * L, mid + n * (W * 0.22)]
        col = GREENS[rng.randrange(3)]
        if soft:
            hh = max(0.0, min(1.0, (z - low) / (1 - low) + rng.uniform(-0.18, 0.18)))
            col = tuple(OLD[k] + (NEW[k] - OLD[k]) * hh * hh for k in range(3))
        if irregular and z > 0.55 and rng.random() < 0.6: col = NEW   # 顶上的新叶偏黄绿(固有色差异,不是烘光)
        if sphere_normals:
            ns = []
            for p in vs:
                q = p - c; q.z /= max(squash, 1e-3)
                ns.append((q.normalized() + up * normal_up_bias).normalized())
        else:
            ns = None
        B.add(vs, [(0, 4, 1), (0, 2, 4), (1, 4, 3), (4, 2, 3)], col, ns)   # 绕序要让几何法线朝外:朝里时渲染器把看得见的一面当背面,会把自定义法线翻进去,整团发黑


def bush(B, rng, c, R, variant):
    c = Vector(c)
    if variant == 'G':
        for k in range(5):
            f = 1.0 if k == 0 else rng.uniform(0.62, 0.85)
            ang = k * 1.6 + rng.uniform(-0.4, 0.4); off = 0 if k == 0 else R * rng.uniform(0.55, 0.8)
            r = R * f; cc = c + Vector((math.cos(ang) * off, math.sin(ang) * off, r * 0.50))
            ellipsoid(B, cc, r * 0.86, 0.85, CORE, seg=8, rings=5)
            leaf_clump(B, rng, cc, r, 0.85, int(70 + 70 * f), r * 0.40, r * 0.24, True, low=-0.15, normal_up_bias=0.45, soft=True)
        return
    if variant in ('E', 'F'):
        n = 5 if variant == 'E' else 4
        for k in range(n):
            f = 1.0 if k == 0 else rng.uniform(0.5, 0.78)
            ang = rng.uniform(0, 6.28); off = 0 if k == 0 else R * rng.uniform(0.55, 0.85)
            r = R * f; cc = c + Vector((math.cos(ang) * off, math.sin(ang) * off, r * 0.42))
            ellipsoid(B, cc, r * 0.82, 0.8, CORE, seg=8, rings=5)
            if variant == 'E': leaf_clump(B, rng, cc, r, 0.8, int(60 + 80 * f), r * 0.46, r * 0.20, True, irregular=True)
            else: leaf_clump(B, rng, cc, r, 0.8, int(34 + 44 * f), r * 0.58, r * 0.27, True, irregular=True)
        return
    lobes = [(Vector((0, 0, 0)), 1.0), (Vector((R * 0.75, R * 0.25, -R * 0.12)), 0.72), (Vector((-R * 0.55, R * 0.6, -R * 0.18)), 0.62)]
    rot = Matrix.Rotation(rng.uniform(0, 6.28), 3, 'Z')
    if variant == 'A':
        for k, (o, f) in enumerate(lobes):
            disc(B, c + rot @ o + Vector((0, 0, R * 0.18 + k * R * 0.16)), R * f * 0.95, R * 0.20, GREENS[1])
        return
    for o, f in lobes:
        cc = c + rot @ o + Vector((0, 0, R * f * 0.45)); r = R * f
        if variant == 'B':
            leaf_clump(B, rng, cc, r, 0.8, 70, r * 0.62, r * 0.30, False)
        elif variant == 'C':
            ellipsoid(B, cc, r * 0.80, 0.8, CORE)
            leaf_clump(B, rng, cc, r, 0.8, 70, r * 0.62, r * 0.30, True)
        elif variant == 'D':
            ellipsoid(B, cc, r * 0.84, 0.8, CORE)
            leaf_clump(B, rng, cc, r, 0.8, 150, r * 0.40, r * 0.17, True)


def planter(B):
    box(B, (0, 0, 0.10), (3.4, 3.4, 0.20), (0.55, 0.55, 0.58))      # 石圈
    box(B, (0, 0, 0.19), (3.0, 3.0, 0.06), (0.12, 0.07, 0.05))      # 土
    box(B, (0, 0, 0.55), (1.3, 1.3, 0.75), (0.33, 0.36, 0.42))      # 基座
    box(B, (0, 0, 0.98), (1.1, 1.1, 0.12), (0.38, 0.41, 0.47))


SPOTS = [(-1.1, -1.1, 0.42), (0.0, -1.2, 0.36), (1.1, -1.1, 0.44), (-1.15, 0.0, 0.40), (1.15, 0.05, 0.38), (-1.1, 1.1, 0.42), (1.1, 1.1, 0.40)]


def render(path, w, h, ortho_scale=None, target=(0, 0, 0.4), dist=30.0, pitch=55.0, fov=25.0):
    sc = bpy.context.scene
    cd = bpy.data.cameras.new("cam"); cam = bpy.data.objects.new("cam", cd); sc.collection.objects.link(cam)
    cd.sensor_fit = 'VERTICAL'; cd.angle = math.radians(fov)
    p = math.radians(pitch); tgt = Vector(target)
    cam.location = tgt + Vector((0, -math.cos(p) * dist, math.sin(p) * dist))
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    sc.render.resolution_x, sc.render.resolution_y = w, h; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)


stats = {}
for variant in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
    if ONLY and variant not in ONLY: continue
    reset()
    mat = vcol_material()
    G = Builder(); box(G, (0, 0, -0.05), (40, 40, 0.1), (0.50, 0.42, 0.36)); G.to_object("ground", mat, False)
    P = Builder(); planter(P); P.to_object("planter", mat, False)
    rng = random.Random(7)
    S = Builder()
    for (x, y, R) in SPOTS: bush(S, rng, (x, y, 0.22), R * (1.25 if variant == 'G' else 1.0), variant)
    ob = S.to_object("shrubs", mat, variant in ('C', 'D', 'E', 'F', 'G'))
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    stats[variant] = dict(tris_total=tris, tris_per_bush=round(tris / len(SPOTS)))
    # 游戏镜头:花坛在画面里约 330 px 宽(和勾哥截图同量级);近景同机位 3 倍像素
    render(OUT + "/game_%s.png" % variant, 360, 380, dist=10.5)
    render(OUT + "/near_%s.png" % variant, 1080, 1140, dist=10.5)
    print("CASE", variant, json.dumps(stats[variant]))
json.dump(stats, open(OUT + "/stats.json", "w"), indent=1)
print("RESULT", json.dumps(stats))
