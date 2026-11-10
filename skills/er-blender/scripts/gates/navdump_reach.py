"""W1 寻路可达闸(闸门 1 引擎段):读 W1 里导出的真实 NavMesh 三角形,算从入口能走到哪里。

为什么有它:11-10 TS 在 W1 里逐门测「门两侧各 0.9 m 两个点 CalculatePath」16/16 全过,但用它自己导出的三角形一算,
失物招领一翼 + 室内楼梯脚 + 整个 2F 和入口根本不连通——门两侧两个点都在同一个孤岛里,逐门测法看不出来。
这个闸门只认一件事:从入口出发,每个房间探点 / 每扇门两侧 / 每个精英位都在同一块连通的 NavMesh 上。

输入:NavMesh.CalculateTriangulation() 导出的 JSON(TS / RES 的 Play 脚本 NavDump() 已有这个格式):
  {"tris": [[ax, ay, az, bx, by, bz, cx, cy, cz], ...], "doors": [[name, x0, y0, x1, y1, z], ...](可选)}
坐标用 POI 本地、Z 朝上(和 Blender 导出坐标一致,poi_nav_gate.py 的配置可以直接复用 seeds / probes / elites)。
相邻判定:两个三角形有一条边在平面上重叠(端点到对边距离 ≤ 5 cm)且高差 ≤ 0.4 m —— Detour 分 tile 后相邻
多边形的边常常不共用顶点(T 形接缝),只按共用顶点算会把整张网格切碎。

用法:python navdump_reach.py <navdump.json> <gate_config.json> [out_report.json]
配置字段:seeds(入口外的点,没有就用离 POI 最远的一圈地面三角形)、probes(房间名 → [x,y,z])、elites、
door_probe_offset(默认 0.9)。退出码 0 = 全部连通,3 = 有走不到的,1 = 出错。"""
import json
import math
import sys
from collections import defaultdict


def main(argv):
    nav = json.load(open(argv[0], encoding="utf-8"))
    cfg = json.load(open(argv[1], encoding="utf-8"))
    out = argv[2] if len(argv) > 2 else None
    T = [t for t in nav["tris"] if len(t) == 9]
    if not T:
        raise SystemExit("no triangles")
    P = [[tuple(t[k:k + 3]) for k in (0, 3, 6)] for t in T]
    par = list(range(len(T)))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def near_seg(p, a, b, tol=0.05, ztol=0.4):
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = dx * dx + dy * dy
        if L < 1e-9:
            return False
        t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L
        if t < -0.01 or t > 1.01:
            return False
        qx, qy, qz = a[0] + t * dx, a[1] + t * dy, a[2] + t * (b[2] - a[2])
        return (p[0] - qx) ** 2 + (p[1] - qy) ** 2 < tol * tol and abs(p[2] - qz) < ztol

    # spatial hash on segment bounding boxes (0.5 m cells) so big dumps stay fast
    segs = [(i, P[i][a], P[i][b]) for i in range(len(T)) for a, b in ((0, 1), (1, 2), (2, 0))]
    grid = defaultdict(list)
    for s, (i, a, b) in enumerate(segs):
        for gx in range(int(math.floor(min(a[0], b[0]) / 0.5)), int(math.floor(max(a[0], b[0]) / 0.5)) + 1):
            for gy in range(int(math.floor(min(a[1], b[1]) / 0.5)), int(math.floor(max(a[1], b[1]) / 0.5)) + 1):
                grid[(gx, gy)].append(s)
    for bucket in grid.values():
        for x in range(len(bucket)):
            i, a, b = segs[bucket[x]]
            for y in range(x + 1, len(bucket)):
                j, c, d = segs[bucket[y]]
                if i == j or find(i) == find(j):
                    continue
                if near_seg(c, a, b) + near_seg(d, a, b) + near_seg(a, c, d) + near_seg(b, c, d) >= 2:
                    par[find(i)] = find(j)

    cen = [tuple(sum(t[k::3]) / 3 for k in range(3)) for t in T]
    area = [0.5 * abs((t[3] - t[0]) * (t[7] - t[1]) - (t[6] - t[0]) * (t[4] - t[1])) for t in T]

    def inside(px, py, t):
        ax, ay, bx, by, cx, cy = t[0], t[1], t[3], t[4], t[6], t[7]
        d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
        d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy)
        d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
        return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))

    def tri_at(x, y, z, snap=0.4):
        """Triangle under (x, y) nearest in height; else nearest centroid within snap (like SamplePosition radius 0.4)."""
        best = None
        for i, t in enumerate(T):
            if inside(x, y, t):
                h = (t[2] + t[5] + t[8]) / 3
                if abs(h - z) < 1.0 and (best is None or abs(h - z) < best[0]):
                    best = (abs(h - z), i)
        if best:
            return best[1]
        d = min(range(len(T)), key=lambda i: (cen[i][0] - x) ** 2 + (cen[i][1] - y) ** 2 + 4 * (cen[i][2] - z) ** 2)
        return d if math.dist(cen[d][:2], (x, y)) <= snap + 1.0 and abs(cen[d][2] - z) < 1.0 else -1

    comp_area = defaultdict(float)
    for i in range(len(T)):
        comp_area[find(i)] += area[i]
    if cfg.get("seeds"):
        seeds = [tri_at(*s) for s in cfg["seeds"]]
    else:
        cx = sum(c[0] for c in cen) / len(cen)
        cy = sum(c[1] for c in cen) / len(cen)
        far = sorted(range(len(T)), key=lambda i: -math.hypot(cen[i][0] - cx, cen[i][1] - cy))[:max(3, len(T) // 50)]
        seeds = far
    main_comps = {find(s) for s in seeds if s >= 0}

    def state(x, y, z):
        i = tri_at(x, y, z)
        if i < 0:
            return "no_navmesh"
        return "reach" if find(i) in main_comps else "island(%.1f m²)" % comp_area[find(i)]

    fails, res = [], {"probes": {}, "doors": {}, "elites": {}}
    for name, p in (cfg.get("probes") or {}).items():
        res["probes"][name] = state(*p)
    off = float(cfg.get("door_probe_offset", 0.9))
    for d in nav.get("doors", []):
        name, x0, y0, x1, y1, z = d[:6]
        cxm, cym = (x0 + x1) / 2, (y0 + y1) / 2
        nx, ny = (1, 0) if abs(x1 - x0) < abs(y1 - y0) else (0, 1)      # leaf box is thin across the wall
        res["doors"][name] = [state(cxm + nx * off, cym + ny * off, z), state(cxm - nx * off, cym - ny * off, z)]
    for k, p in enumerate(cfg.get("elites", [])):
        res["elites"][str(k)] = state(*p)
    for grp in ("probes", "elites"):
        for k, v in res[grp].items():
            if v != "reach":
                fails.append("%s %s:%s" % ({"probes": "探点", "elites": "精英位"}[grp], k, v))
    for k, (a, b) in res["doors"].items():
        if a != "reach" or b != "reach":
            fails.append("门 %s:两侧 %s / %s" % (k, a, b))
    comps = sorted(((round(a, 1), c in main_comps) for c, a in comp_area.items()), reverse=True)
    rep = {"gate": "navdump_reach", "pass": not fails, "fails": fails, "triangles": len(T),
           "components_m2_main_flag": comps[:12], "main_m2": round(sum(comp_area[c] for c in main_comps), 1), **res}
    if out:
        json.dump(rep, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ER_JSON", json.dumps({"pass": rep["pass"], "fails": fails[:40], "main_m2": rep["main_m2"], "components": comps[:6]}, ensure_ascii=False))
    return 0 if rep["pass"] else 3


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except SystemExit:
        raise
    except Exception as e:                                  # noqa: BLE001
        print("ER_JSON", json.dumps({"error": repr(e)}))
        sys.exit(1)
