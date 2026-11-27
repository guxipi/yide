"""po_vertex: vertex-colour paint-over for buildings and props (er-blender references/00 + 08).

Standard = er-blender references/00-造型与笔触标准.md (勾哥 11-27, mo.co vehicle reference): clean base colour per part plus
SPARSE, flat, opaque, hard-edged hand-painted blocks that follow the structure; value only, the hue never moves; no AO,
no directional light, no environment tint (Unity LabLit + scene lights do all of that).
What vertex colour can express here (corner domain = one flat colour per face, hard edge to the neighbour face):
  strokes on bevels  whole connected bevel runs (narrow faces bending against a neighbour) lifted by `strip`; about
                     `strip_frac` of the runs are chosen, upward-facing runs first, a run is lit fully or not at all
                     (never per-face speckle). Not every edge gets a light line.
  planar highlights  optional (`plane_frac`, default 0): a few large faces lifted as a whole by `plane`.
  block variation    optional, only for palette classes named EXACTLY in `block_classes` (multi-block materials).
  gradient           optional (`grad`, default 0): one value ramp over the set; `bands` only at real geometric breaks.
Slanted rectangles / wedges inside a big face cannot be drawn in vertex colour without cutting the mesh: use the texture
route of 08 for those, do not densify the mesh for it.
Glass / screens / glow / decals / signs are skipped (texture route).

Library:  import po_vertex as PV; PV.paint(objs, cid_names, palette_hex, **cfg)  -> stats dict
CLI:      blender -b in.blend --factory-startup -P po_vertex.py --python-exit-code 1 -- --palette palette.json
              [--out out.blend] [--prefix SQ_] [--strip 1.07] [--strip_frac 0.4] [--plane 1.05] [--plane_frac 0]
              [--plane_min 0.25] [--bevel 0.08] [--block 0.05] [--block_classes floor_tile,stone] [--grad 0] [--bands 7.5,11.0]
              [--seed 0] [--skip glow_,glass,screen,decal,sign] [--stats stats.json]
palette.json = {class: "#RRGGBB"} in the order kitlib used for the 'cid' face attribute (K.CID = enumerate(palette)).
Col is rebuilt from the palette first, so running it twice gives the same result."""
import json
import math
import sys
import zlib

import bpy

DEFAULTS = dict(strip=1.07, strip_frac=0.4, strip_angle=8.0, bevel=0.08,
                plane=1.05, plane_frac=0.0, plane_min=0.25,
                block=0.05, block_min=4, block_classes=(),
                grad=0.0, grad_flat=0.0, bands=None, flat_h=0.35, seed=0,
                skip=("glow_", "glass", "screen", "decal", "sign"))
# No facing-dependent factors (top / side / underside): a darker underside is baked directional light, which LabLit adds
# again in Unity (11-27). Gradient off by default; when on, bands only at real geometric breaks (cornice / slab bands),
# a restart on a continuous wall face is a seam. Block variation only on classes named exactly (palette names are colour
# names; kitlib gives every box its own 'blk', so 'blk' alone does NOT mean "this is a block material").


def hexlin(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def _hash01(*keys):
    return (zlib.crc32("|".join(str(k) for k in keys).encode()) % 100003) / 100002.0


def _islands(me):
    """Face islands joined by shared edges -> (island id per polygon, island count, edge->faces map)."""
    emap = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            emap.setdefault(ek, []).append(p.index)
    isl = [-1] * len(me.polygons)
    n = 0
    for p in me.polygons:
        if isl[p.index] >= 0:
            continue
        stack = [p.index]
        isl[p.index] = n
        while stack:
            i = stack.pop()
            for ek in me.polygons[i].edge_keys:
                for j in emap[ek]:
                    if isl[j] < 0:
                        isl[j] = n
                        stack.append(j)
        n += 1
    return isl, n, emap


def paint(objs, cid_names, palette_hex, **cfg):
    c = dict(DEFAULTS)
    c.update({k: v for k, v in cfg.items() if v is not None})
    skip = tuple(c["skip"])
    block_classes = tuple(c["block_classes"])
    base = {k: hexlin(v) for k, v in palette_hex.items()}
    cmin = math.cos(math.radians(c["strip_angle"]))
    seed = int(c["seed"])
    st = dict(objects=0, faces=0, skipped_faces=0, strip_faces=0, strip_runs=0, strip_runs_lit=0, plane_faces=0,
              block_faces=0, blocks=0, flat_objects=0, unknown_cid=0)
    allz = [(o.matrix_world @ v.co).z for o in objs if o.type == "MESH" for v in o.data.vertices]
    gz0, gz1 = (min(allz), max(allz)) if allz else (0.0, 1.0)
    cuts = sorted(set([gz0, gz1] + [float(x) for x in (c["bands"] or []) if gz0 < float(x) < gz1]))

    def band_of(z):
        for k in range(len(cuts) - 1):
            if z <= cuts[k + 1] or k == len(cuts) - 2:
                return cuts[k], cuts[k + 1]
        return gz0, gz1
    for o in objs:
        if o.type != "MESH":
            continue
        me = o.data
        cid = me.attributes.get("cid")
        if cid is None or not me.polygons:
            continue
        col = me.color_attributes.get("Col")
        if col is None or col.domain != "CORNER":
            if col is not None:
                me.color_attributes.remove(col)
            col = me.color_attributes.new("Col", "FLOAT_COLOR", "CORNER")
        mw = o.matrix_world
        nm = mw.inverted_safe().transposed().to_3x3()
        wv = [mw @ v.co for v in me.vertices]
        zs = [q.z for q in wv]
        z0, z1 = min(zs), max(zs)
        flat = (z1 - z0) < c["flat_h"]
        axis = None
        if flat:
            xs, ys = [q.x for q in wv], [q.y for q in wv]
            axis = (0, min(xs), max(xs)) if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else (1, min(ys), max(ys))
            st["flat_objects"] += 1
        isl, nisl, emap = _islands(me)
        blk = None
        blk_attr = me.attributes.get("blk")
        if blk_attr is not None:
            vals = [blk_attr.data[k].value for k in range(len(me.polygons))]
            if len(set(vals)) >= c["block_min"]:
                blk = vals
        if blk is None and nisl >= c["block_min"]:
            blk = isl
        if blk is not None:
            st["blocks"] += len(set(blk))
        st["objects"] += 1
        fn = [(nm @ p.normal).normalized() for p in me.polygons]
        names = []
        for p in me.polygons:
            ci = cid.data[p.index].value
            names.append(cid_names[ci] if 0 <= ci < len(cid_names) else None)
        # pass 1: classify faces (bevel strip / big plane) on paintable faces
        strip, area = set(), {}
        for p in me.polygons:
            name = names[p.index]
            if not name or name not in base or name.startswith(skip):
                continue
            vs = [wv[v] for v in p.vertices]
            lmax = max((vs[k] - vs[(k + 1) % len(vs)]).length for k in range(len(vs)))
            aw = 0.0
            for k in range(1, len(vs) - 1):
                aw += ((vs[k] - vs[0]).cross(vs[k + 1] - vs[0])).length * 0.5
            area[p.index] = aw
            if aw / max(1e-9, lmax) <= 1.6 * c["bevel"]:
                if any(fn[q].dot(fn[p.index]) < cmin for ek in p.edge_keys for q in emap[ek] if q != p.index):
                    strip.add(p.index)
        # pass 2: bevel runs = strip faces joined across shared edges only when their long edges run the same way
        # (one run per bevelled edge; corner patches do not chain the whole box into one run) -> pick sparse runs,
        # upward-facing first, deterministic
        ldir = {}
        for f in strip:
            vs = [wv[v] for v in me.polygons[f].vertices]
            e = max(((vs[(k + 1) % len(vs)] - vs[k]) for k in range(len(vs))), key=lambda d: d.length)
            ldir[f] = e.normalized() if e.length > 1e-9 else e
        run_of, runs = {}, []
        for f0 in strip:
            if f0 in run_of:
                continue
            stack, members = [f0], []
            run_of[f0] = len(runs)
            while stack:
                f = stack.pop()
                members.append(f)
                for ek in me.polygons[f].edge_keys:
                    for q in emap[ek]:
                        if (q in strip and q not in run_of and names[q] == names[f]
                                and abs(ldir[q].dot(ldir[f])) > 0.95):
                            run_of[q] = len(runs)
                            stack.append(q)
            runs.append(members)
        lit_runs = set()
        if runs and c["strip_frac"] > 0:
            def score(r):
                nz = sum(fn[f].z for f in runs[r]) / len(runs[r])
                return (nz > 0.2, _hash01(seed, o.name, min(runs[r])))
            order = sorted(range(len(runs)), key=score, reverse=True)
            n_lit = int(round(c["strip_frac"] * len(runs)))
            lit_runs = set(order[:n_lit])
        st["strip_runs"] += len(runs)
        st["strip_runs_lit"] += len(lit_runs)
        for p in me.polygons:
            name = names[p.index]
            b = base.get(name) if name else None
            if b is None:
                st["unknown_cid"] += 1
                continue
            if name.startswith(skip):
                st["skipped_faces"] += 1
                continue
            f = 1.0
            if p.index in strip and run_of[p.index] in lit_runs:
                f *= c["strip"]
                st["strip_faces"] += 1
            elif (c["plane_frac"] > 0 and p.index not in strip and area.get(p.index, 0.0) >= c["plane_min"]
                  and _hash01(seed, "plane", o.name, p.index) < c["plane_frac"]):
                f *= c["plane"]
                st["plane_faces"] += 1
            if blk is not None and name in block_classes:
                f *= 1.0 + c["block"] * (2.0 * _hash01(seed, o.name, blk[p.index]) - 1.0)
                st["block_faces"] += 1
            vs = [wv[v] for v in p.vertices]
            if not flat and c["grad"]:
                lo, hi = band_of(sum(v.z for v in vs) / len(vs))
            for li in p.loop_indices:
                g = 1.0
                if flat and c["grad_flat"]:
                    v = wv[me.loops[li].vertex_index]
                    ax, amin, amax = axis
                    g = 1.0 - c["grad_flat"] * (1.0 - (v[ax] - amin) / max(1e-6, amax - amin))
                elif not flat and c["grad"]:
                    v = wv[me.loops[li].vertex_index]
                    g = 1.0 - c["grad"] * (1.0 - min(max((v.z - lo) / max(1e-6, hi - lo), 0.0), 1.0))
                kk = f * g
                rgb = [b[0] * kk, b[1] * kk, b[2] * kk]
                m = max(rgb)
                if m > 1.0:                                   # keep the hue: scale all channels, never clip one
                    rgb = [x / m for x in rgb]
                col.data[li].color = (rgb[0], rgb[1], rgb[2], 1.0)
            st["faces"] += 1
        me.color_attributes.active_color = col
        me.attributes.default_color_name = "Col"
    return st


def _cli():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    a = {}
    for i in range(0, len(argv) - 1, 2):
        a[argv[i].lstrip("-").replace("-", "_")] = argv[i + 1]
    pal = json.load(open(a.pop("palette"), encoding="utf-8"))
    names = list(pal.keys())
    pal_hex = {k: (v if isinstance(v, str) else v.get("hex", "#808080")) for k, v in pal.items()}
    out, stats_path, prefix = a.pop("out", None), a.pop("stats", None), a.pop("prefix", "")
    cfg = {k: (tuple(s for s in v.split(",") if s) if k in ("skip", "block_classes") else [float(x) for x in v.split(",") if x] if k == "bands" else float(v)) for k, v in a.items()}
    objs = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(prefix)]
    st = paint(objs, names, pal_hex, **cfg)
    if out:
        bpy.ops.wm.save_as_mainfile(filepath=out)
    if stats_path:
        json.dump(st, open(stats_path, "w", encoding="utf-8"), indent=1)
    print("ER_JSON", json.dumps(st))


if __name__ == "__main__":
    _cli()
