"""Geometry fixes on a Tripo rig GLB before rig_build (10-08 Rook: Tripo keeps sharpening hair clumps into needle
spikes and drops the broken-nose hump even when the references show them). Keeps UVs and skin weights.
usage: blender -b --python head_fix.py -- <in.glb> <out.glb> [--hair-iters 25] [--hair-hue 8,34] [--hair-vmax 0.55]
       [--hump x,y,z,depth,radius] [--drop-small 0] [--report]
- hair: vertices whose texture colour is warm dark brown, above --hair-zmin (normalised height), excluding skin (bright);
  Taubin smoothing (lambda 0.5 / mu -0.53) with the hair border pinned -> spikes become blunt, volume kept.
- hump: push vertices near (x,y,z) (normalised: height 1, feet 0, x centred, face -Y) forward (-Y) by depth with a
  gaussian falloff of radius -> a broken-nose bump on the bridge.
- drop-small N: delete loose parts with fewer than N vertices (Tripo adds stray cables/coils).
Normalised coords are derived from the mesh bbox the same way rig_build does."""
import sys, os, math, colorsys
import bpy, bmesh, numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]
src, dst = a[0], a[1]
def opt(k, d):
    return a[a.index(k) + 1] if k in a else d
iters = int(opt('--hair-iters', 25)); hue = [float(x) for x in opt('--hair-hue', '8,34').split(',')]
vmax = float(opt('--hair-vmax', 0.55)); zmin = float(opt('--hair-zmin', 0.80)); hump = opt('--hump', None)
drop = int(opt('--drop-small', 0))
bpy.ops.wm.read_factory_settings(use_empty=True); bpy.ops.import_scene.gltf(filepath=src)
mesh = max([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: len(o.data.vertices))
M = mesh.matrix_world; Mi = M.inverted()
W = np.array([tuple(M @ v.co) for v in mesh.data.vertices]); z0 = W[:, 2].min(); H = W[:, 2].max() - z0; xc = (W[:, 0].min() + W[:, 0].max()) / 2
N = np.column_stack([(W[:, 0] - xc) / H, W[:, 1] / H, (W[:, 2] - z0) / H])
img = max((x for x in bpy.data.images if x.size[0] > 0), key=lambda x: x.size[0] * x.size[1]); IW, IH = img.size
px = np.array(img.pixels[:]).reshape(IH, IW, 4)
uv = mesh.data.uv_layers.active.data; vuv = [None] * len(W)
for lp in mesh.data.loops:
    if vuv[lp.vertex_index] is None: vuv[lp.vertex_index] = uv[lp.index].uv
adj = [set() for _ in range(len(W))]
for e in mesh.data.edges:
    i, j = e.vertices; adj[i].add(j); adj[j].add(i)
rep = {}
if drop:
    comp = [-1] * len(W); c = 0; sizes = []
    for s in range(len(W)):
        if comp[s] >= 0: continue
        st = [s]; comp[s] = c; n = 0
        while st:
            v = st.pop(); n += 1
            for u in adj[v]:
                if comp[u] < 0: comp[u] = c; st.append(u)
        sizes.append(n); c += 1
    small = {k for k, n in enumerate(sizes) if n < drop}
    rep['components'] = len(sizes); rep['dropped'] = [(k, sizes[k]) for k in small]
hair = np.zeros(len(W), bool)
for i in range(len(W)):
    if N[i, 2] < zmin or vuv[i] is None: continue
    u, v = vuv[i]; r, g, b = px[min(IH - 1, int(v * IH)), min(IW - 1, int(u * IW)), :3]
    h, s, val = colorsys.rgb_to_hsv(r, g, b)
    if hue[0] <= h * 360 <= hue[1] and s > 0.25 and val < vmax: hair[i] = True
# keep only hair vertices whose neighbours are mostly hair (removes stray brows/skin shadow), grow 1 ring for tips
core = np.array([hair[i] and sum(hair[j] for j in adj[i]) >= max(1, len(adj[i]) // 2) for i in range(len(W))])
border = np.array([core[i] and any(not core[j] for j in adj[i]) for i in range(len(W))])
move = np.where(core & ~border)[0]; rep['hair_vertices'] = int(core.sum()); rep['hair_moving'] = len(move)
P = W.copy()
for it in range(iters * 2):
    lam = 0.5 if it % 2 == 0 else -0.53
    avg = np.array([P[list(adj[i])].mean(0) if adj[i] else P[i] for i in move])
    P[move] = P[move] + lam * (avg - P[move])
disp = np.linalg.norm(P - W, axis=1) / H; rep['hair_max_move'] = float(disp.max()); rep['hair_p95_move'] = float(np.percentile(disp[move], 95)) if len(move) else 0
if hump:
    hx, hy, hz, depth, rad = [float(x) for x in hump.split(',')]
    d2 = ((N[:, 0] - hx) ** 2 + (N[:, 1] - hy) ** 2 * 0.25 + (N[:, 2] - hz) ** 2)
    w = np.exp(-d2 / (2 * rad * rad)); w[N[:, 1] > hy + 0.02] = 0
    P[:, 1] -= w * depth * H; rep['hump_moved'] = int((w > 0.05).sum())
for i, v in enumerate(mesh.data.vertices):
    v.co = Mi @ Vector(P[i])
if drop and rep['dropped']:
    bm = bmesh.new(); bm.from_mesh(mesh.data); bm.verts.ensure_lookup_table()
    kill = [bm.verts[i] for i in range(len(W)) if comp[i] in small]
    bmesh.ops.delete(bm, geom=kill, context='VERTS'); bm.to_mesh(mesh.data); bm.free()
mesh.data.update()
for o in bpy.data.objects: o.select_set(True)
os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
bpy.ops.export_scene.gltf(filepath=dst, export_format='GLB', export_skins=True, export_animations=False)
print('HEAD_FIX', rep)
