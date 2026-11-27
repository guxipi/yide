# AO 烘焙实验:同一辆标定货车,换距离 / 地面 / 合壳 / 采样与降噪,出并排板和数字
# 用法: blender -b --factory-startup -P ao_lab.py --python-exit-code 1 -- <outdir>
import bpy, bmesh, sys, json, math, os
import numpy as np
from mathutils import Vector, Matrix

OUT = sys.argv[sys.argv.index("--") + 1].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
RES = 1024
TILE = (560, 420)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.view_settings.view_transform = 'Standard'
    w = bpy.data.worlds.new("W")
    sc.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (0.5, 0.5, 0.5, 1)
    return sc


def box(bm, c, s):
    m = Matrix.Translation(Vector(c)) @ Matrix.Diagonal(Vector((s[0], s[1], s[2], 1)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def cyl_x(bm, c, r, w):
    m = Matrix.Translation(Vector(c)) @ Matrix.Rotation(math.radians(90), 4, 'Y')
    bmesh.ops.create_cone(bm, cap_ends=True, segments=20, radius1=r, radius2=r, depth=w, matrix=m)


PARTS = []  # (kind, center, size)
PARTS.append(('box', (0, 0.4, 1.35), (2.0, 3.2, 1.9)))      # 货箱
PARTS.append(('box', (0, -1.75, 1.0), (1.9, 1.3, 1.2)))     # 车头(插进货箱 0.2)
PARTS.append(('box', (0, -2.45, 0.55), (2.05, 0.3, 0.3)))   # 保险杠(插进车头)
PARTS.append(('box', (0, 0.4, 2.34), (1.3, 2.2, 0.10)))     # 顶板(压进车顶 0.02)
for sx in (-0.8, 0.8):
    PARTS.append(('box', (sx, 0.4, 2.52), (0.07, 2.9, 0.07)))            # 行李架横杆
    for y in (-0.9, 0.4, 1.7):
        PARTS.append(('box', (sx, y, 2.40), (0.07, 0.07, 0.24)))          # 立柱(插进车顶)
for sx in (-0.95, 0.95):
    for y in (-1.6, 1.3):
        PARTS.append(('cyl', (sx, y, 0.42), (0.42, 0.34)))                # 轮子(一半插进车身)


def part_obj(i, p):
    bm = bmesh.new()
    if p[0] == 'box':
        box(bm, p[1], p[2])
    else:
        cyl_x(bm, p[1], p[2][0], p[2][1])
    me = bpy.data.meshes.new("p%d" % i)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("p%d" % i, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def build(variant):
    obs = [part_obj(i, p) for i, p in enumerate(PARTS)]
    if variant == 'raw':
        bm = bmesh.new()
        for ob in obs:
            bm.from_mesh(ob.data)
        me = bpy.data.meshes.new("van")
        bm.to_mesh(me); bm.free()
    else:  # shell: 逐件布尔并集,内部面和穿插都消掉
        base = obs[0]
        for ob in obs[1:]:
            md = base.modifiers.new("u", 'BOOLEAN')
            md.operation = 'UNION'
            md.object = ob
            md.solver = 'EXACT'
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(base.evaluated_get(dg))
        me.name = "van"
    for ob in obs:
        bpy.data.objects.remove(ob)
    van = bpy.data.objects.new("van", me)
    bpy.context.scene.collection.objects.link(van)
    return van


def add_ground():
    bm = bmesh.new()
    box(bm, (0, 0, -0.05), (40, 40, 0.1))
    me = bpy.data.meshes.new("ground")
    bm.to_mesh(me); bm.free()
    g = bpy.data.objects.new("ground", me)
    bpy.context.scene.collection.objects.link(g)
    return g


def select_only(ob):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob


def unwrap(ob):
    select_only(ob)
    bpy.ops.object.mode_set(mode='EDIT')
    try:
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.02)
    finally:
        bpy.ops.object.mode_set(mode='OBJECT')
    assert len(ob.data.uv_layers) > 0, "no uv"


def bake_ao(ob, dist, samples, denoise, name):
    sc = bpy.context.scene
    img = bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    tex = nt.nodes.new('ShaderNodeTexImage')
    tex.image = img
    nt.nodes.active = tex
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    sc.world.light_settings.distance = dist
    sc.cycles.samples = samples
    sc.cycles.use_denoising = denoise
    select_only(ob)
    r = bpy.ops.object.bake(type='AO', margin=8, use_clear=True)
    assert 'FINISHED' in r, r
    px = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)[:, :, 0]
    # 给预览换成自发光材质
    for n in list(nt.nodes):
        if n.type != 'TEX_IMAGE':
            nt.nodes.remove(n)
    em = nt.nodes.new('ShaderNodeEmission')
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    nt.links.new(tex.outputs[0], em.inputs[0])
    nt.links.new(em.outputs[0], out.inputs[0])
    return img, px


def stats(px):
    # 占用像素:烘到的地方不是纯 0 也不是清空色;用 >0 的粗略判
    used = px[px > 1e-4]
    blur = (px[:-2, 1:-1] + px[2:, 1:-1] + px[1:-1, :-2] + px[1:-1, 2:] + px[1:-1, 1:-1]) / 5.0
    grain = float(np.mean(np.abs(px[1:-1, 1:-1] - blur)))
    return dict(mean=round(float(used.mean()), 3), p05=round(float(np.percentile(used, 5)), 3),
                p50=round(float(np.percentile(used, 50)), 3), p95=round(float(np.percentile(used, 95)), 3),
                dark_frac=round(float((px < 0.15).mean()), 3), grain=round(grain, 5))


def render(path, ground=None):
    sc = bpy.context.scene
    cam_d = bpy.data.cameras.new("cam"); cam_d.lens = 60
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    loc = Vector((5.2, -6.4, 7.2)); tgt = Vector((0, -0.1, 1.3))
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat('-Z', 'Y').to_euler()
    sc.camera = cam
    if ground is not None:
        gm = bpy.data.materials.new("g"); gm.use_nodes = True
        nt = gm.node_tree
        for n in list(nt.nodes):
            nt.nodes.remove(n)
        em = nt.nodes.new('ShaderNodeEmission'); em.inputs[0].default_value = (0.5, 0.5, 0.5, 1)
        out = nt.nodes.new('ShaderNodeOutputMaterial'); nt.links.new(em.outputs[0], out.inputs[0])
        ground.data.materials.clear(); ground.data.materials.append(gm)
    sc.render.resolution_x, sc.render.resolution_y = TILE
    sc.render.resolution_percentage = 100
    sc.cycles.samples = 8
    sc.cycles.use_denoising = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


CASES = [
    # tag, variant, dist, ground, samples, denoise
    ("A_raw_d0.2", 'raw', 0.2, False, 64, False),
    ("B_raw_d0.6", 'raw', 0.6, False, 64, False),
    ("C_raw_d1.4", 'raw', 1.4, False, 64, False),
    ("D_raw_d3.0", 'raw', 3.0, False, 64, False),
    ("E_raw_d1.4_ground", 'raw', 1.4, True, 64, False),
    ("F_shell_d1.4_ground", 'shell', 1.4, True, 64, False),
    ("G_shell_d1.4_s8", 'shell', 1.4, True, 8, False),
    ("H_shell_d1.4_s8_denoise", 'shell', 1.4, True, 8, True),
]

results = {}
tiles = []
for tag, variant, dist, ground, samples, denoise in CASES:
    reset()
    van = build(variant)
    g = add_ground() if ground else None
    unwrap(van)
    img, px = bake_ao(van, dist, samples, denoise, tag)
    st = stats(px)
    st.update(tris=sum(len(p.vertices) - 2 for p in van.data.polygons))
    results[tag] = st
    img.filepath_raw = OUT + "/ao_" + tag + ".png"
    img.file_format = 'PNG'
    img.save()
    p = OUT + "/view_" + tag + ".png"
    render(p, g)
    tiles.append(p)
    print("CASE", tag, json.dumps(st))

# 拼 4x2 并排板
reset()
arrs = []
for p in tiles:
    im = bpy.data.images.load(p)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(TILE[1], TILE[0], 4)
    arrs.append(a)
rows = [np.concatenate(arrs[0:4], axis=1), np.concatenate(arrs[4:8], axis=1)]
board = np.concatenate([rows[1], rows[0]], axis=0)  # 图像原点在左下,第一排放上面
bi = bpy.data.images.new("board", TILE[0] * 4, TILE[1] * 2, alpha=True)
bi.pixels.foreach_set(board.ravel())
bi.filepath_raw = OUT + "/board.png"; bi.file_format = 'PNG'; bi.save()
with open(OUT + "/results.json", "w") as f:
    json.dump(results, f, indent=1)
print("RESULT", json.dumps(results))
