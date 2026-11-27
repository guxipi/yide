# 把标定货车导出给 Unity 实验用:网格(位置 / 面法线 / UV,已换成 Unity 坐标)和两张遮蔽图。
# 用法: blender -b --factory-startup -P ao_lab3_export.py --python-exit-code 1 -- <outdir>
# 产物: van.json、ao_contact.png(距离 0.15)、ao_form.png(距离 1.5、带地面、模糊过)
import bpy, sys, os, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
OUT = sys.argv[sys.argv.index("--") + 1].replace("\\", "/")
os.makedirs(OUT, exist_ok=True)
src = open(HERE + "/ao_lab.py", encoding="utf-8").read().split("CASES = [")[0]
ns = {"__name__": "ao_lab_lib"}
exec(compile(src, "ao_lab_lib", "exec"), ns)
reset, build, add_ground, unwrap, bake_ao = (ns[k] for k in ("reset", "build", "add_ground", "unwrap", "bake_ao"))
RES = ns["RES"]


def blur(a, r, n=2):
    for _ in range(n):
        c = np.cumsum(np.pad(a, ((r, r + 1), (0, 0)), mode='edge'), axis=0)
        a = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
        c = np.cumsum(np.pad(a, ((0, 0), (r, r + 1)), mode='edge'), axis=1)
        a = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    return a.astype(np.float32)


def save_grey(arr, path):
    im = bpy.data.images.new("o", RES, RES, alpha=False)
    im.colorspace_settings.name = 'Non-Color'
    rgba = np.concatenate([np.repeat(np.clip(arr, 0, 1)[..., None], 3, axis=2), np.ones((RES, RES, 1), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel())
    im.filepath_raw = path; im.file_format = 'PNG'; im.save()


reset()
van = build('shell')
add_ground()
unwrap(van)
_, contact = bake_ao(van, 0.15, 128, False, "contact")
_, form = bake_ao(van, 1.5, 128, False, "form")
save_grey(contact, OUT + "/ao_contact.png")
save_grey(blur(form, 6), OUT + "/ao_form.png")

me = van.data
me.calc_loop_triangles()
uv = me.uv_layers.active.data
pos, nrm, uvs, tris = [], [], [], []
for t in me.loop_triangles:
    n = me.polygons[t.polygon_index].normal
    base = len(pos) // 3
    for li in t.loops:
        v = me.vertices[me.loops[li].vertex_index].co
        pos += [round(v.x, 5), round(v.z, 5), round(v.y, 5)]          # Blender (x,y,z) → Unity (x,z,y)
        nrm += [round(n.x, 5), round(n.z, 5), round(n.y, 5)]
        uvs += [round(uv[li].uv.x, 6), round(uv[li].uv.y, 6)]
    tris += [base, base + 2, base + 1]                                # 换了手性,绕序反过来
json.dump(dict(pos=pos, nrm=nrm, uv=uvs, tri=tris), open(OUT + "/van.json", "w"))
print("EXPORT verts", len(pos) // 3, "tris", len(tris) // 3)
