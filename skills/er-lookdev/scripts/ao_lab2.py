# AO 实验二:两层叠加、归一化的坏处、灰乘 vs 带色遮蔽。复用 ao_lab.py 的建模和烘焙。
# 用法: blender -b --factory-startup -P ao_lab2.py --python-exit-code 1 -- <outdir>
import bpy, sys, os, json, importlib.util
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
OUT = sys.argv[sys.argv.index("--") + 1].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)

src = open(HERE + "/ao_lab.py", encoding="utf-8").read().split("CASES = [")[0]
ns = {"__name__": "ao_lab_lib"}
exec(compile(src, "ao_lab_lib", "exec"), ns)
reset, build, add_ground, unwrap, bake_ao, render = (ns[k] for k in ("reset", "build", "add_ground", "unwrap", "bake_ao", "render"))
RES, TILE = ns["RES"], ns["TILE"]

ALBEDO = np.array([0.80, 0.60, 0.10], dtype=np.float32)   # 出租车黄(线性)
TINT = np.array([0.62, 0.58, 0.80], dtype=np.float32)     # 淡紫


def blur(a, r, n=2):
    for _ in range(n):
        c = np.cumsum(np.pad(a, ((r, r + 1), (0, 0)), mode='edge'), axis=0)
        a = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
        c = np.cumsum(np.pad(a, ((0, 0), (r, r + 1)), mode='edge'), axis=1)
        a = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return a.astype(np.float32)


def multibounce(x, alb):
    x = x[..., None]
    a = 2.0404 * alb - 0.3324; b = -4.7951 * alb + 0.6417; c = 2.7552 * alb + 0.6903
    return np.maximum(x, ((x * a + b) * x + c) * x)


reset()
van = build('shell')
g = add_ground()
unwrap(van)
_, contact = bake_ao(van, 0.15, 128, False, "contact")
img, form = bake_ao(van, 1.5, 128, False, "form")
form_b = blur(form, 6)
combo = contact * (0.5 + 0.5 * form_b)
lo, hi = np.percentile(form[form > 1e-4], 5), np.percentile(form[form > 1e-4], 95)
normalized = np.clip((form - lo) / max(hi - lo, 1e-4), 0, 1)
grey = ALBEDO * combo[..., None]
mb = multibounce(combo, ALBEDO)
tinted = ALBEDO * (TINT + (1 - TINT) * mb)

VARIANTS = [
    ("1_contact_d0.15", contact), ("2_form_d1.5", form), ("3_form_blur", form_b), ("4_combo", combo),
    ("5_form_normalized", normalized), ("6_albedo_x_grey_ao", grey), ("7_albedo_multibounce", ALBEDO * mb),
    ("8_albedo_multibounce_lilac", tinted),
]

# 预览:图像按 sRGB 解释,屏幕值 = 存的值(不被线性→sRGB 再提亮)
img.colorspace_settings.name = 'sRGB'
tiles = []
stats = {}
for name, arr in VARIANTS:
    rgb = arr if arr.ndim == 3 else np.repeat(arr[..., None], 3, axis=2)
    rgba = np.concatenate([rgb, np.ones((RES, RES, 1), np.float32)], axis=2)
    img.pixels.foreach_set(rgba.ravel())
    img.update()
    p = OUT + "/view_" + name + ".png"
    render(p, g)
    tiles.append(p)
    used = rgb[contact > 1e-4]
    dark = used[used.mean(axis=1) < np.percentile(used.mean(axis=1), 10)]
    mx, mn = dark.max(axis=1), dark.min(axis=1)
    stats[name] = dict(mean=round(float(used.mean()), 3),
                       dark10_rgb=[round(float(v), 3) for v in dark.mean(axis=0)],
                       dark10_sat=round(float(((mx - mn) / np.maximum(mx, 1e-4)).mean()), 3))
    print("CASE", name, json.dumps(stats[name]))

arrs = []
for p in tiles:
    im = bpy.data.images.load(p)
    arrs.append(np.array(im.pixels[:], dtype=np.float32).reshape(TILE[1], TILE[0], 4))
board = np.concatenate([np.concatenate(arrs[4:8], axis=1), np.concatenate(arrs[0:4], axis=1)], axis=0)
bi = bpy.data.images.new("board", TILE[0] * 4, TILE[1] * 2, alpha=True)
bi.pixels.foreach_set(board.ravel())
bi.filepath_raw = OUT + "/board2.png"; bi.file_format = 'PNG'; bi.save()
json.dump(stats, open(OUT + "/results2.json", "w"), indent=1)
print("RESULT", json.dumps(stats))
