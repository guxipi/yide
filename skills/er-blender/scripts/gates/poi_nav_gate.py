"""POI 离线寻路闸(闸门 1 离线段):在 Blender 里按 W1 的 NavMesh 参数模拟一遍 Recast,装机前判通行。

为什么有它:11-10 五个中 POI 各写了一份量梯宽 / 门宽 / 净区的脚本,口径互相打架(门口净区方向反了、挡路高度五种、
精英位四种算法),楼梯太窄、暗室零三角、门两侧不通都要等进 W1 烘完才发现。这个闸门用同一份阈值表
(同目录 thresholds.json,口径改了只改那张表),离线就能报出来,过不了不申请 W1 锁。

做法(近似 Recast,参数取自 W1 ProjectSettings/NavMeshAreas.asset):
  1. 每个 cell(默认 1/6 m)从上往下打射线,记所有朝上的面(坡度 ≤ 45°)当候选地面;没有建模的 1F 地坪 / 楼外地面
     用 ground_z 虚拟地面补(重烘才生成地坪,模型里没有)。
  2. 候选地面头顶 2 m 内有东西 = 不可走;离地 0.85–1.9 m 范围内 cell 半宽里有几何 = 不可走(墙、柜、栏杆)。
     比台阶高度 0.75 低的东西不算障碍,它的顶面本身就是一层地面(和 Recast 一样,床、矮箱能踩上去)。
  3. 4 邻 cell 高差 ≤ 0.75 算连通;按 agent 半径 0.5 从边界往里腐蚀;小于 2 m² 的连通块剪掉。
  4. 从楼外地面(或配置的 seeds)出发能到的块 = 可达。
报告:每扇门(从门扇物件自动推出位置和朝向)两侧是否可达且连通、门洞净宽 / 净高 / 门楣、门口两侧净区被家具占比;
精英位离寻路面边缘的距离;各楼层走不到的地面(房间整块不可达、暗室被剪掉都会出现在这里);每层一张俯视图。

用法:
  blender -b <POI>.blend --factory-startup -P poi_nav_gate.py --python-exit-code 1 -- <gate_config.json> <out_dir>
退出码 0 = 过,3 = 不过(报告里 fails 写原因),1 = 脚本出错。
配置字段见同目录 README.md 和 examples/。坐标一律是 .blend 里的世界坐标(Z 朝上)。"""
import heapq
import json
import math
import os
import re
import struct
import sys
import zlib
from collections import deque

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
argv = sys.argv[sys.argv.index("--") + 1:]
CFG = json.load(open(argv[0], encoding="utf-8"))
OUT = argv[1]
os.makedirs(OUT, exist_ok=True)
TH = json.load(open(CFG.get("thresholds") or os.path.join(HERE, "thresholds.json"), encoding="utf-8"))
AG = TH["agent"]
CELL = float(CFG.get("cell", AG["cell"]))
RAD, HGT, CLIMB = AG["radius"], AG["height"], AG["climb"]
COS_SLOPE = math.cos(math.radians(AG["slope_deg"]))
MIN_REGION = AG["min_region_area_m2"]
DT = TH["door"]
FLOORS = [float(z) for z in CFG["floors"]]
GROUND_Z = CFG.get("ground_z", 0.0)
LEAF_RE = re.compile(CFG["door_leaf_regex"]) if CFG.get("door_leaf_regex") else None
IGNORE_RE = re.compile(CFG["ignore_regex"]) if CFG.get("ignore_regex") else None
STRUCT_RE = re.compile(CFG["structure_regex"]) if CFG.get("structure_regex") else None   # walls / windows / floors: not furniture in door zones
DOWN, UP = Vector((0, 0, -1)), Vector((0, 0, 1))


def vmin(a, b):
    return Vector((min(a.x, b.x), min(a.y, b.y), min(a.z, b.z)))


def vmax(a, b):
    return Vector((max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)))


def chain_match(o, rx):
    while o is not None:
        if rx.search(o.name):
            return True
        o = o.parent
    return False


def top_match(o, rx):
    """Top-most object in the parent chain whose name matches (a door leaf and its glass child count as one leaf)."""
    top = None
    while o is not None:
        if rx.search(o.name):
            top = o
        o = o.parent
    return top


# ---------------------------------------------------------------- geometry
dg = bpy.context.evaluated_depsgraph_get()
verts, polys, leaf_boxes = [], [], {}
fverts, fpolys = [], []
leaf_geo = {}
skip_hidden = CFG.get("skip_hidden_render", True)
for o in bpy.context.scene.objects:
    if o.type not in ("MESH", "CURVE") or (skip_hidden and o.hide_render):
        continue
    if IGNORE_RE and chain_match(o, IGNORE_RE):
        continue
    ev = o.evaluated_get(dg)
    try:
        me = ev.to_mesh()
    except RuntimeError:
        continue
    if me is None:
        continue
    mw = ev.matrix_world
    wv = [mw @ v.co for v in me.vertices]
    leaf = top_match(o, LEAF_RE) if LEAF_RE else None
    if leaf is not None:                                  # door leaves swing: Unity installers mark them ignoreFromBuild
        key = leaf.name.split("__")[0]                   # "X__glass" panes belong to leaf X even when not parented to it
        b = leaf_boxes.setdefault(key, [Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))])
        for v in wv:
            b[0], b[1] = vmin(b[0], v), vmax(b[1], v)
        leaf_geo.setdefault(key, []).append((wv, [list(p.vertices) for p in me.polygons], bool(STRUCT_RE and chain_match(o, STRUCT_RE))))
    else:
        base = len(verts)
        verts += wv
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        if not (STRUCT_RE and chain_match(o, STRUCT_RE)):
            fb = len(fverts)
            fverts += wv
            fpolys += [[fb + i for i in p.vertices] for p in me.polygons]
    ev.to_mesh_clear()
# only full-height leaves are room doors; cabinet / locker / safe doors stay solid (they are furniture in the bake)
MIN_LEAF_H = float(CFG.get("door_min_leaf_height", 1.7))
for key in [k for k, (a, b) in leaf_boxes.items() if b.z - a.z < MIN_LEAF_H]:
    for wv, pl, st in leaf_geo.pop(key, []):
        base = len(verts)
        verts += wv
        polys += [[base + i for i in q] for q in pl]
        if not st:
            fb = len(fverts)
            fverts += wv
            fpolys += [[fb + i for i in q] for q in pl]
    del leaf_boxes[key]
if not polys:
    raise SystemExit("no geometry")
bvh = BVHTree.FromPolygons(verts, polys)
fbvh = BVHTree.FromPolygons(fverts, fpolys) if fpolys else None
lo = Vector((min(v.x for v in verts), min(v.y for v in verts), min(v.z for v in verts)))
hi = Vector((max(v.x for v in verts), max(v.y for v in verts), max(v.z for v in verts)))
pad = float(CFG.get("pad", 4.0))
X0, Y0, X1, Y1 = CFG.get("bounds") or (lo.x - pad, lo.y - pad, hi.x + pad, hi.y + pad)
ZTOP, ZBOT = hi.z + 1.0, min(lo.z, GROUND_Z if GROUND_Z is not None else lo.z) - 1.0
NX, NY = int(math.ceil((X1 - X0) / CELL)), int(math.ceil((Y1 - Y0) / CELL))
RN = CELL * 0.55


def cxy(i, j):
    return X0 + (i + 0.5) * CELL, Y0 + (j + 0.5) * CELL


def ij(x, y):
    return int((x - X0) / CELL), int((y - Y0) / CELL)


def blocked_at(x, y, h, heights):
    up = bvh.ray_cast(Vector((x, y, h + 0.02)), UP, HGT)
    if up[0] is not None and up[3] < HGT - 0.02:
        return True
    return any(bvh.find_nearest(Vector((x, y, h + hb)), RN)[0] is not None for hb in heights)


# ---------------------------------------------------------------- 1. walkable spans
BODY = (CLIMB + 0.1, (CLIMB + HGT) / 2, HGT - 0.1)
nodes_h, nodes_ij, cellnodes = [], [], {}
for i in range(NX):
    for j in range(NY):
        x, y = cxy(i, j)
        levels, o = [], Vector((x, y, ZTOP))
        for _ in range(24):
            hit = bvh.ray_cast(o, DOWN, o.z - ZBOT)
            if hit[0] is None:
                break
            if hit[1].z > COS_SLOPE:
                levels.append(hit[0].z)
            o = Vector((x, y, hit[0].z - 1e-3))
        if GROUND_Z is not None and not any(abs(h - GROUND_Z) < 0.3 for h in levels) and (not levels or min(levels) > GROUND_Z):
            levels.append(GROUND_Z)
        ids = []
        for h in sorted(levels):
            if ids and h - nodes_h[ids[-1]] < 0.05:
                continue
            if blocked_at(x, y, h, BODY):
                continue
            ids.append(len(nodes_h))
            nodes_h.append(h)
            nodes_ij.append((i, j))
        if ids:
            cellnodes[(i, j)] = ids
N = len(nodes_h)


def link(n, di, dj):
    """Neighbour node within climb height; -1 = wall / drop / nothing, -2 = outside the grid (open ground, not a border)."""
    i, j = nodes_ij[n]
    if not (0 <= i + di < NX and 0 <= j + dj < NY):
        return -2
    best, bd = -1, CLIMB + 1e-6
    for m in cellnodes.get((i + di, j + dj), ()):
        d = abs(nodes_h[m] - nodes_h[n])
        if d <= bd:
            best, bd = m, d
    return best


D4 = ((1, 0), (-1, 0), (0, 1), (0, -1))
DD = ((1, 1), (1, -1), (-1, 1), (-1, -1))
nb4 = [[link(n, di, dj) for di, dj in D4] for n in range(N)]
nbd = [[link(n, di, dj) for di, dj in DD] for n in range(N)]


def dijkstra(sources, allowed):
    dist = [math.inf] * N
    pq = []
    for s in sources:
        dist[s] = 0.0
        pq.append((0.0, s))
    heapq.heapify(pq)
    while pq:
        d, n = heapq.heappop(pq)
        if d > dist[n]:
            continue
        for k, m in enumerate(nb4[n] + nbd[n]):
            if m < 0 or not allowed[m]:
                continue
            nd = d + (1.0 if k < 4 else 1.41421356)
            if nd < dist[m]:
                dist[m] = nd
                heapq.heappush(pq, (nd, m))
    return dist


# ---------------------------------------------------------------- 2. erode, components, prune
allw = [True] * N
border = [n for n in range(N) if -1 in nb4[n]]
edge_cells = dijkstra(border, allw)
edge_m = [(d + 0.5) * CELL for d in edge_cells]
eroded = [e >= RAD - 1e-6 for e in edge_m]
comp = [-1] * N
comps = []
for s in range(N):
    if not eroded[s] or comp[s] >= 0:
        continue
    cid, q, members = len(comps), deque([s]), []
    comp[s] = cid
    while q:
        n = q.popleft()
        members.append(n)
        for m in nb4[n]:
            if m >= 0 and eroded[m] and comp[m] < 0:
                comp[m] = cid
                q.append(m)
    comps.append(members)
area = [len(c) * CELL * CELL for c in comps]
pruned = [a < MIN_REGION for a in area]


def node_at(x, y, z, tol=0.6, search=0):
    i0, j0 = ij(x, y)
    best, bd = -1, 1e9
    for di in range(-search, search + 1):
        for dj in range(-search, search + 1):
            for m in cellnodes.get((i0 + di, j0 + dj), ()):
                d = abs(nodes_h[m] - z) + 0.01 * (abs(di) + abs(dj))
                if abs(nodes_h[m] - z) < tol and d < bd:
                    best, bd = m, d
    return best


seeds = []
if CFG.get("seeds"):
    for x, y, z in CFG["seeds"]:
        n = node_at(x, y, z, 0.6, 3)
        if n >= 0:
            seeds.append(n)
else:
    g = GROUND_Z if GROUND_Z is not None else min(FLOORS)
    for n in range(N):
        i, j = nodes_ij[n]
        if (i < 3 or j < 3 or i >= NX - 3 or j >= NY - 3) and abs(nodes_h[n] - g) < 0.5:
            seeds.append(n)
reach_comps = {comp[s] for s in seeds if comp[s] >= 0 and not pruned[comp[s]]}
reach = [comp[n] in reach_comps for n in range(N)]


def status(n):
    if n < 0:
        return "no_floor"
    if not eroded[n]:
        return "edge_margin" if any(reach[m] for m in nb4[n] if m >= 0) else "not_on_nav"
    if pruned[comp[n]]:
        return "pruned_small_region"
    return "reach" if reach[n] else "island"


# ---------------------------------------------------------------- 3. floor area the navmesh cannot cover
cover = dijkstra([n for n in range(N) if reach[n]], allw)
cover_m = [d * CELL for d in cover]
NOWALK = CFG.get("not_walkable_boxes", [])          # [[x0, y0, x1, y1, zlo, zhi], ...] spaces that are not meant to be walked (closed bus, sealed shaft)


def boxed(n):
    x, y = cxy(*nodes_ij[n])
    return any(b[0] <= x <= b[2] and b[1] <= y <= b[3] and b[4] <= nodes_h[n] <= b[5] for b in NOWALK)


unc = [(cover_m[n] > RAD + CELL) and any(abs(nodes_h[n] - f) < 0.6 for f in FLOORS) and not boxed(n) for n in range(N)]
seen, uncovered = [False] * N, []
for s in range(N):
    if not unc[s] or seen[s]:
        continue
    q, mem = deque([s]), []
    seen[s] = True
    while q:
        n = q.popleft()
        mem.append(n)
        for m in nb4[n]:
            if m >= 0 and unc[m] and not seen[m]:
                seen[m] = True
                q.append(m)
    a = len(mem) * CELL * CELL
    if a >= float(CFG.get("uncovered_min_m2", 1.5)):
        xs = [cxy(*nodes_ij[m]) for m in mem]
        cx = sum(p[0] for p in xs) / len(xs)
        cy = sum(p[1] for p in xs) / len(xs)
        hz = sorted(nodes_h[m] for m in mem)[len(mem) // 2]
        uncovered.append({"centroid": [round(cx, 2), round(cy, 2), round(hz, 2)], "area_m2": round(a, 2), "states": sorted({status(m) for m in mem})})
uncovered.sort(key=lambda u: -u["area_m2"])


# ---------------------------------------------------------------- 4. doors (from leaf boxes)
def gap(x, y, d, z0, top=1.9, rmax=3.0):
    best = 2 * rmax
    for k in range(5):
        o = Vector((x, y, z0 + 0.3 + k * (top - 0.3) / 4))
        a = bvh.ray_cast(o, d, rmax)[3] or rmax
        b = bvh.ray_cast(o, -d, rmax)[3] or rmax
        best = min(best, a + b)
    return round(best, 2)


leaves = []
for name, (a, b) in leaf_boxes.items():
    ax = "x" if (b.x - a.x) >= (b.y - a.y) else "y"
    leaves.append({"names": [name], "lo": a.copy(), "hi": b.copy(), "axis": ax})
merged = True
while merged:                                              # double doors: two leaves side by side in one opening
    merged = False
    for p in leaves:
        for q in leaves:
            if p is q or p["axis"] != q["axis"]:
                continue
            k = 1 if p["axis"] == "x" else 0                # normal coordinate
            w = 0 if p["axis"] == "x" else 1                # along-wall coordinate
            pc, qc = (p["lo"][k] + p["hi"][k]) / 2, (q["lo"][k] + q["hi"][k]) / 2
            if abs(pc - qc) < 0.2 and abs(p["lo"].z - q["lo"].z) < 0.2 and max(p["lo"][w], q["lo"][w]) - min(p["hi"][w], q["hi"][w]) < 0.3:
                p["names"] += q["names"]
                p["lo"], p["hi"] = vmin(p["lo"], q["lo"]), vmax(p["hi"], q["hi"])
                leaves.remove(q)
                merged = True
                break
        if merged:
            break

_B0, _B1 = DT.get("block_band", [0.05, 2.0])
ZONE_H = (_B0 + RN, 0.5, 1.0, 1.5, _B1 - RN)   # sample spheres stay inside block_band: rugs / doormats / floor decals (top < 0.05) are not furniture
waive = set(CFG.get("waive_zone", []))
doors = []
for d in leaves:
    c = (d["lo"] + d["hi"]) / 2
    z0 = d["lo"].z
    fl = node_at(c.x, c.y, z0, 0.5, 4)
    fz = nodes_h[fl] if fl >= 0 else (GROUND_Z if GROUND_Z is not None and abs(z0 - GROUND_Z) < 0.5 else z0)
    wall = Vector((1, 0, 0)) if d["axis"] == "x" else Vector((0, 1, 0))
    nrm = Vector((0, 1, 0)) if d["axis"] == "x" else Vector((1, 0, 0))
    width = gap(c.x, c.y, wall, fz)
    hit = bvh.ray_cast(Vector((c.x, c.y, fz + 0.05)), UP, 6.0)
    height = round(hit[3] + 0.05, 2) if hit[0] is not None else None
    lintel = None
    if hit[0] is not None:
        h2 = bvh.ray_cast(hit[0] + UP * 1e-3, UP, 6.0)
        lintel = round(h2[0].z - hit[0].z, 2) if h2[0] is not None else 0.0
    sides = {}
    for s, tag in ((1, "+"), (-1, "-")):
        p = c + nrm * (s * DT["probe_offset"])
        sides[tag] = status(node_at(p.x, p.y, fz, 0.6, 1))
        n_all = n_blk = 0                                  # furniture-free zone: door width along the wall x zone_depth
        half = width / 2 - RN * 1.2                       # stay inside the opening: the jambs themselves are not furniture
        u = -half
        while u <= half + 1e-6:
            v = DT["zone_offset"]
            while v <= DT["zone_offset"] + DT["zone_depth"] + 1e-6:
                q = c + wall * u + nrm * (s * v)
                n_all += 1
                if fbvh and any(fbvh.find_nearest(Vector((q.x, q.y, fz + hb)), RN)[0] is not None for hb in ZONE_H):
                    n_blk += 1
                v += CELL
            u += CELL
        sides["zone" + tag] = round(n_blk / max(1, n_all), 3)
    nm = "+".join(sorted(d["names"]))
    fails = []
    if not (sides["+"] == "reach" and sides["-"] == "reach"):
        fails.append("两侧不通(%s / %s)" % (sides["+"], sides["-"]))
    if width < DT["min_width"] - 0.005:
        fails.append("门洞净宽 %.2f < %.2f" % (width, DT["min_width"]))
    if height is None:
        fails.append("门洞上方没有墙(门高过墙,或墙在烘焙里被排除)")
    elif height < DT["min_height"] - 0.005:
        fails.append("门洞净高 %.2f < %.2f" % (height, DT["min_height"]))
    if lintel is not None and lintel < DT["min_lintel_above"] - 0.005:
        fails.append("门顶墙楣 %.2f < %.2f(门不许齐墙顶或冒出墙)" % (lintel, DT["min_lintel_above"]))
    if nm not in waive:
        for tag in "+-":
            if sides["zone" + tag] > DT["zone_max_blocked_share"]:
                fails.append("门口%s侧净区被占 %.0f%%" % (tag, 100 * sides["zone" + tag]))
    doors.append({"door": nm, "at": [round(c.x, 2), round(c.y, 2), round(fz, 2)], "wall_axis": d["axis"], "width": width, "height": height,
                  "lintel_above": lintel, "side_plus": sides["+"], "side_minus": sides["-"], "zone_plus": sides["zone+"], "zone_minus": sides["zone-"],
                  "pass": not fails, "fails": fails})

# ---------------------------------------------------------------- 5. elites and probes
elites = []
for k, (x, y, z) in enumerate(CFG.get("elites", [])):
    n = node_at(x, y, z, 0.6, 3)
    st = status(n)
    e = round(edge_m[n] - RAD, 2) if n >= 0 and st == "reach" else None
    ok = e is not None and e >= TH["elite"]["min_edge_distance"] - 0.005
    best = None
    if not ok:                                             # nearest spot that would pass, within 4 m
        i0, j0 = ij(x, y)
        r = int(4.0 / CELL)
        cand = []
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                for m in cellnodes.get((i0 + di, j0 + dj), ()):
                    if reach[m] and abs(nodes_h[m] - z) < 0.6 and edge_m[m] - RAD >= TH["elite"]["min_edge_distance"]:
                        px, py = cxy(*nodes_ij[m])
                        cand.append((math.hypot(px - x, py - y), m))
        if cand:
            dmin, m = min(cand)
            best = {"at": [round(v, 2) for v in cxy(*nodes_ij[m])] + [round(nodes_h[m], 2)], "move_m": round(dmin, 2), "edge": round(edge_m[m] - RAD, 2)}
    elites.append({"elite": k, "at": [x, y, z], "state": st, "edge_distance": e, "pass": ok, "nearest_passing": best})

probes = {}
for name, (x, y, z) in (CFG.get("probes") or {}).items():
    probes[name] = status(node_at(x, y, z, 0.6, 2))

# ---------------------------------------------------------------- 6. verdict, report, images
fails = []
for d in doors:
    fails += ["门 %s:%s" % (d["door"], f) for f in d["fails"]]
for e in elites:
    if not e["pass"]:
        fails.append("精英位 %d:%s,离边 %s < %.1f" % (e["elite"], e["state"], e["edge_distance"], TH["elite"]["min_edge_distance"]))
for name, st in probes.items():
    if st != "reach":
        fails.append("探点 %s:%s" % (name, st))
for u in uncovered:
    if u["area_m2"] >= MIN_REGION:
        fails.append("走不到的地面 %.1f m² @ %s(%s)" % (u["area_m2"], u["centroid"], ",".join(u["states"])))
per_floor, state_m2 = {}, {}
for f in FLOORS:
    sc = {}
    for n in range(N):
        if abs(nodes_h[n] - f) < 0.6:
            st = status(n)
            sc[st] = sc.get(st, 0) + 1
    state_m2["%.2f" % f] = {k: round(v * CELL * CELL, 1) for k, v in sorted(sc.items())}
    per_floor["%.2f" % f] = round(sum(1 for n in range(N) if reach[n] and abs(nodes_h[n] - f) < 0.6) * CELL * CELL, 1)
    if per_floor["%.2f" % f] < 1.0:
        fails.append("楼层 z=%.2f 没有可达寻路面" % f)


def png(path, w, h, rgb):
    raw = b"".join(b"\x00" + bytes(rgb[r * w * 3:(r + 1) * w * 3]) for r in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


SC = int(CFG.get("image_scale", 3))
COLS = {"reach": (70, 185, 95), "edge_margin": (40, 105, 60), "island": (160, 80, 210), "pruned_small_region": (230, 140, 40), "not_on_nav": (150, 60, 60)}
images = []
for f in FLOORS:
    W, H = NX * SC, NY * SC
    buf = bytearray(W * H * 3)

    def put(i, j, col, r=0):
        for di in range(-r, r + 1):
            for dj in range(-r, r + 1):
                ii, jj = i + di, j + dj
                if 0 <= ii < NX and 0 <= jj < NY:
                    for a in range(SC):
                        for b in range(SC):
                            o = (((NY - 1 - jj) * SC + b) * W + ii * SC + a) * 3
                            buf[o:o + 3] = bytes(col)

    for (i, j), ids in cellnodes.items():
        m = min(ids, key=lambda n: abs(nodes_h[n] - f))
        if abs(nodes_h[m] - f) > 0.6:
            put(i, j, (60, 60, 66))
            continue
        st = status(m)
        col = COLS.get(st, (60, 60, 66))
        if unc[m] and st != "reach":
            col = (225, 55, 50)
        put(i, j, col)
    for d in doors:
        if abs(d["at"][2] - f) < 0.6:
            put(*ij(d["at"][0], d["at"][1]), (250, 220, 40) if d["pass"] else (235, 60, 220), 1)
    for e in elites:
        if abs(e["at"][2] - f) < 0.6:
            put(*ij(e["at"][0], e["at"][1]), (60, 220, 240) if e["pass"] else (255, 30, 30), 2)
    p = os.path.join(OUT, "nav_z%+.2f.png" % f)
    png(p, W, H, buf)
    images.append(p)

ok = not fails
rep = {"gate": "poi_nav_gate", "thresholds": TH["version"], "poi": CFG.get("poi"), "pass": ok, "fails": fails,
       "grid": {"cell": CELL, "nx": NX, "ny": NY, "bounds": [round(v, 2) for v in (X0, Y0, X1, Y1)], "nodes": N},
       "reachable_m2_per_floor": per_floor, "state_m2_per_floor": state_m2, "doors": doors, "elites": elites, "probes": probes, "uncovered": uncovered[:30],
       "legend": "绿 = 可达寻路面;深绿 = 腐蚀边(半径 0.5 内);紫 = 腐蚀后不连通的孤岛;红 = 寻路盖不到的地面;橙 = 小于 2 m² 被剪;黄点 = 门过,品红 = 门不过;青 = 精英位过,红 = 不过",
       "images": images}
if CFG.get("dump_nodes"):
    with open(os.path.join(OUT, "nav_nodes.json"), "w", encoding="utf-8") as fh:
        json.dump({"cell": CELL, "x0": X0, "y0": Y0, "nodes": [[nodes_ij[n][0], nodes_ij[n][1], round(nodes_h[n], 3), status(n)] for n in range(N)]}, fh)
with open(os.path.join(OUT, "nav_gate_report.json"), "w", encoding="utf-8") as fh:
    json.dump(rep, fh, ensure_ascii=False, indent=1)
print("ER_JSON", json.dumps({"pass": ok, "fails": fails[:40], "doors": len(doors), "report": os.path.join(OUT, "nav_gate_report.json")}, ensure_ascii=False))
sys.stdout.flush()
os._exit(0 if ok else 3)
