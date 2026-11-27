# AO 实验三:第三层「自上而下的光照渐变」怎么来。在标定货车上比五种来源,
# 量侧壁从上到下的剖面和顶面的平整度,再和贴缝 + 形体两层叠起来出并排板。
# 用法: blender -b --factory-startup -P ao_lab3.py --python-exit-code 1 -- <outdir>
import bpy, sys, os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
OUT = sys.argv[sys.argv.index("--") + 1].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)

src = open(HERE + "/ao_lab.py", encoding="utf-8").read().split("CASES = [")[0]
ns = {"__name__": "ao_lab_lib"}
exec(compile(src, "ao_lab_lib", "exec"), ns)
reset, build, add_ground, unwrap, bake_ao, render, select_only = (
    ns[k] for k in ("reset", "build", "add_ground", "unwrap", "bake_ao", "render", "select_only"))
RES, TILE = ns["RES"], ns["TILE"]

ALBEDO = np.array([0.80, 0.80, 0.80], dtype=np.float32)    # 白厢体(线性)
SHADE = np.array([0.42, 0.45, 0.66], dtype=np.float32)     # 参考侧壁 底/顶 的线性三通道比
Z_BOT, Z_TOP = 0.40, 2.30                                  # 货箱侧壁的高度范围


def blur(a, r, n=2):
    for _ in range(n):
        c = np.cumsum(np.pad(a, ((r, r + 1), (0, 0)), mode='edge'), axis=0)
        a = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
        c = np.cumsum(np.pad(a, ((0, 0), (r, r + 1)), mode='edge'), axis=1)
        a = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return a.astype(np.float32)


def new_img(name):
    img = bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=True)
    img.colorspace_settings.name = 'Non-Color'
    return img


def set_mat(ob, kind, img, color=(0.8, 0.8, 0.8)):
    mat = bpy.data.materials.new(img.name if img else "m")
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    if kind == 'diffuse':
        sh = nt.nodes.new('ShaderNodeBsdfDiffuse')
        sh.inputs[0].default_value = (*color, 1)
        nt.links.new(sh.outputs[0], out.inputs[0])
    else:  # 'pos': 把世界坐标编码进自发光
        geo = nt.nodes.new('ShaderNodeNewGeometry')
        vm = nt.nodes.new('ShaderNodeVectorMath'); vm.operation = 'MULTIPLY_ADD'
        vm.inputs[1].default_value = (0.1, 0.1, 0.1); vm.inputs[2].default_value = (0.5, 0.5, 0.5)
        em = nt.nodes.new('ShaderNodeEmission')
        nt.links.new(geo.outputs['Position'], vm.inputs[0])
        nt.links.new(vm.outputs[0], em.inputs[0])
        nt.links.new(em.outputs[0], out.inputs[0])
    if img is not None:
        tex = nt.nodes.new('ShaderNodeTexImage'); tex.image = img; nt.nodes.active = tex
    ob.data.materials.clear(); ob.data.materials.append(mat)


def px(img, ch=None):
    a = np.array(img.pixels[:], dtype=np.float32).reshape(RES, RES, 4)
    return a[:, :, :3] if ch is None else a[:, :, ch]


def bake(ob, btype, samples, **kw):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    select_only(ob)
    r = bpy.ops.object.bake(type=btype, margin=8, use_clear=True, **kw)
    assert 'FINISHED' in r, r


def world(v):
    bg = next(n for n in bpy.context.scene.world.node_tree.nodes if n.type == 'BACKGROUND')
    bg.inputs[0].default_value = (v, v, v, 1); bg.inputs[1].default_value = 1.0


sc = reset()
sc.cycles.max_bounces = 3
van = build('shell')
g = add_ground()
unwrap(van)

# 每个贴图像素的世界坐标和法线,用来按面、按高度取剖面
ip = new_img("pos"); set_mat(van, 'pos', ip); bake(van, 'EMIT', 1)
P = (px(ip) - 0.5) * 10.0
inn = new_img("nrm"); set_mat(van, 'diffuse', inn); bake(van, 'NORMAL', 1, normal_space='OBJECT')
N = px(inn) * 2.0 - 1.0

LAYERS = {}

# A 白色天穹的漫反射烘焙(关 Color,直接 + 间接),地面深色
set_mat(g, 'diffuse', None, (0.05, 0.05, 0.05)); world(1.0)
ia = new_img("sky_dark"); set_mat(van, 'diffuse', ia)
bake(van, 'DIFFUSE', 128, pass_filter={'DIRECT', 'INDIRECT'}); LAYERS["A_sky_groundDark"] = px(ia, 0)
# B 同上,地面中灰(看地面反弹把下半截抬亮多少)
set_mat(g, 'diffuse', None, (0.5, 0.5, 0.5))
ib = new_img("sky_mid"); set_mat(van, 'diffuse', ib)
bake(van, 'DIFFUSE', 128, pass_filter={'DIRECT', 'INDIRECT'}); LAYERS["B_sky_groundMid"] = px(ib, 0)
# C Dota 配方:头顶一盏点光,不投影、不带遮蔽、只要直接光。高度取车高的约 4 倍
world(0.0)
ld = bpy.data.lights.new("top", 'POINT'); ld.energy = 1000; ld.shadow_soft_size = 0.1
ld.use_shadow = False
lo = bpy.data.objects.new("top", ld); lo.location = (0, 0.4, 10.0); sc.collection.objects.link(lo)
ic = new_img("pt"); set_mat(van, 'diffuse', ic)
bake(van, "DIFFUSE", 16, pass_filter={"DIRECT"}); LAYERS["C_pointTop_h10"] = px(ic, 0)
bpy.data.objects.remove(lo)
world(0.5)
# D 不烘:按世界高度的线性渐变(shader 里一行就能算)
LAYERS["D_heightLinear"] = np.clip((P[:, :, 2] - Z_BOT) / (Z_TOP - Z_BOT), 0, 1)
# E 第二层本身:带地面的大距离遮蔽
_, contact = bake_ao(van, 0.15, 128, False, "contact")
_, form15 = bake_ao(van, 1.5, 128, False, "form15")
img, form30 = bake_ao(van, 3.0, 128, False, "form30")
LAYERS["E_ao_d1.5_ground"] = form15
LAYERS["F_ao_d3.0_ground"] = form30

used = contact > 1e-4
wall = used & (np.abs(N[:, :, 0]) > 0.9) & (np.abs(np.abs(P[:, :, 0]) - 1.0) < 0.03) & (P[:, :, 1] > -0.3) & (P[:, :, 1] < 0.5)
top = used & (N[:, :, 2] > 0.9) & (P[:, :, 2] > 2.36) & (P[:, :, 2] < 2.42)       # 顶板上表面
bins = np.linspace(Z_BOT, Z_TOP, 11)


def profile(a):
    out = []
    for i in range(10):
        m = wall & (P[:, :, 2] >= bins[i]) & (P[:, :, 2] < bins[i + 1])
        out.append(float(a[m].mean()) if m.any() else float('nan'))
    return out[::-1]  # 从上到下


def srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


stats = {"wall_texels": int(wall.sum()), "top_texels": int(top.sum())}
for k, a in LAYERS.items():
    pr = profile(a)
    t = a[top]
    stats[k] = dict(wall_top_to_bottom=[round(v / max(pr[0], 1e-6), 3) for v in pr],
                    wall_top_abs=round(pr[0], 4), roof_plate_mean=round(float(t.mean()), 4),
                    roof_p05_over_p95=round(float(np.percentile(t, 5) / max(np.percentile(t, 95), 1e-6)), 3),
                    wall_top_over_roof=round(pr[0] / max(float(t.mean()), 1e-6), 3))
    print("LAYER", k, json.dumps(stats[k]))

# 合成:t = 贴缝 × (形体混一半) × 第三层;颜色 = 固有色 × lerp(阴影色, 1, t)
two = contact * (0.5 + 0.5 * blur(form15, 6))
h = LAYERS["D_heightLinear"]
f15 = blur(form15, 6)
ptn = LAYERS["C_pointTop_h10"]; ptn = np.clip(ptn / np.percentile(ptn[used], 99), 0, 1)
COMPS = {
    "1_two_layers": two,                                            # 第二轮的两层配方
    "2_two_x_heightLinear": two * (0.45 + 0.55 * h),                # 加线性高度渐变,最低压到 0.45
    "3_two_x_pointTop": two * (0.3 + 0.7 * ptn),                    # 加 Dota 式头顶点光
    "4_contact_x_groundAO_pow3": contact * np.power(f15, 3.0),      # 带地面的形体遮蔽加重(gamma 3),不另加层
    "5_two_x_heightLowerHalf": two * (0.12 + 0.88 * np.clip(h / 0.6, 0, 1) ** 1.5),   # 高度渐变只作用在下六成
}
# 参考侧壁(白厢体,车窗和海报之间那一列)从上到下 10 个采样的屏幕明度,归一到最上一格
REF_WALL = [1.0, 0.967, 0.945, 0.956, 0.941, 0.855, 0.833, 0.788, 0.754, 0.708]
REF_ROOF_P05_P95 = 0.93


def colour(t, tint):
    t = t[..., None]
    lin = ALBEDO * (tint + (1 - tint) * t) if tint is not None else ALBEDO * t
    return srgb(lin)


def norm_layer(a):
    return srgb(np.repeat((a / np.percentile(a[used], 99))[..., None], 3, axis=2))


VARIANTS = [("A_sky_dome", norm_layer(LAYERS["A_sky_groundDark"])), ("C_point_top", norm_layer(LAYERS["C_pointTop_h10"])),
            ("D_height_linear", norm_layer(LAYERS["D_heightLinear"])), ("E_ao_d1.5_ground", norm_layer(LAYERS["E_ao_d1.5_ground"])),
            ("H1_two_layers_lilac", colour(COMPS["1_two_layers"], SHADE)),
            ("H4_contact_x_groundAO_pow3_lilac", colour(COMPS["4_contact_x_groundAO_pow3"], SHADE)),
            ("H5_two_x_heightLowerHalf_lilac", colour(COMPS["5_two_x_heightLowerHalf"], SHADE)),
            ("G5_same_but_grey_multiply", colour(COMPS["5_two_x_heightLowerHalf"], None))]

for k, t in COMPS.items():
    c = colour(t, SHADE)
    lum = 0.2126 * c[:, :, 0] + 0.7152 * c[:, :, 1] + 0.0722 * c[:, :, 2]
    pr = profile(lum)
    prn = [v / pr[0] for v in pr]
    tt = lum[top]
    stats["comp_" + k] = dict(wall_displayL_norm=[round(v, 3) for v in prn],
                              rms_vs_ref=round(float(np.sqrt(np.mean((np.array(prn) - np.array(REF_WALL)) ** 2))), 3),
                              roof_displayL_mean=round(float(tt.mean()), 3),
                              roof_p05_over_p95=round(float(np.percentile(tt, 5) / np.percentile(tt, 95)), 3))
    print("COMP", k, json.dumps(stats["comp_" + k]))
stats["ref"] = dict(wall_displayL_norm=REF_WALL, roof_p05_over_p95=REF_ROOF_P05_P95)

img.colorspace_settings.name = 'sRGB'
tiles = []
for name, rgb in VARIANTS:
    rgba = np.concatenate([rgb, np.ones((RES, RES, 1), np.float32)], axis=2)
    img.pixels.foreach_set(rgba.ravel()); img.update()
    p = OUT + "/view3_" + name + ".png"
    render(p, g)
    tiles.append(p)

arrs = []
for p in tiles:
    im = bpy.data.images.load(p)
    arrs.append(np.array(im.pixels[:], dtype=np.float32).reshape(TILE[1], TILE[0], 4))
board = np.concatenate([np.concatenate(arrs[4:8], axis=1), np.concatenate(arrs[0:4], axis=1)], axis=0)
bi = bpy.data.images.new("board", TILE[0] * 4, TILE[1] * 2, alpha=True)
bi.pixels.foreach_set(board.ravel())
bi.filepath_raw = OUT + "/board3.png"; bi.file_format = 'PNG'; bi.save()
json.dump(stats, open(OUT + "/results3.json", "w"), indent=1)
print("RESULT", json.dumps(stats))
