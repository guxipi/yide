"""po_vertex: building paint-over in vertex colour (the mo.co brushwork route).

勾哥 11-11:「认真提取 moco 建筑的笔触，我认为现在 ER 建筑的笔触非常难看」-> 选「改走顶点色」->「按照 moco 的做法来做 SQ」.
Rules = vault 01 - 星际拓荒重构/013 美术/丛林Lab/specs/spec_建筑笔触_moco提取.md (B1 / B2 / B4 / B7 / B8):
  B1  one base colour per face + one big gradient along the form (one continuous gradient over the set, optional restarts at geometric bands; long axis on flat parts)
  B2  a soft light band on every exposed bevel strip (narrow face that bends against a neighbour; +6 % default)
  B4  block-to-block value variation for multi-block materials (kitlib 'blk' ids, else mesh islands), clean inside a block
  B7  no seams: everything is computed on the mesh, nothing is projected
  B8  value only: every corner colour is a scalar multiple of the base colour (hue never moves); no AO, no corner darkening
Glass / screens / glow / decals / signs are skipped (they keep their own route: glass + screens still get painted art).
Strength defaults follow LF 11-11 (lf_export.py 2c, measured on LF_exterior_r4): gradient -10 % bottom of a storey,
sides x0.96, undersides x0.86, upward shoulders x1.04. Bevel-strip test from Mines gen_common/vcol_rules.py.

Library:  import po_vertex as PV; PV.paint(objs, cid_names, palette_hex, **cfg)  -> stats dict
CLI:      blender -b in.blend --factory-startup -P po_vertex.py --python-exit-code 1 -- --palette palette.json
              [--out out.blend] [--prefix SQ_] [--grad 0.10] [--grad_flat 0.06] [--bands 7.5,11.0] [--bevel 0.08]
              [--strip 1.06] [--block 0.05] [--block_classes floor_tile,stone] [--skip glow_,glass,screen,decal,sign]
              [--stats stats.json]
palette.json = {class: "#RRGGBB"} in the order kitlib used for the 'cid' face attribute (K.CID = enumerate(palette)).
Col is rebuilt from the palette first, so running it twice gives the same result."""
import json
import math
import sys
import zlib

import bpy

DEFAULTS = dict(grad=0.10, grad_flat=0.06, bands=None, flat_h=0.35, top=1.0, shoulder=1.04, side=0.96, under=0.86,
                bevel=0.08, strip=1.06, strip_angle=8.0, block=0.05, block_min=4,
                block_classes=(),
                skip=("glow_", "glass", "screen", "decal", "sign"))
# B1 bands: None = ONE continuous gradient over the whole set (min..max z of every object passed in), so walls split
# into several objects / reveal groups stay continuous. Give bands=[z, ...] (world z) only at real geometric breaks
# (cornice / slab bands): the gradient restarts there, and a restart on a continuous wall face is a seam (11-11 SQ test:
# fixed 3.5 m storeys drew horizontal steps across plain walls).
# B4 only on multi-block materials, opt-in: faces whose palette class is listed EXACTLY in block_classes (palette names
# are colour names like 'slate_blue', so never guess the material from the name). Block ids = kitlib 'blk' if present,
# else mesh islands. kitlib gives every box its own 'blk', so 'blk' alone does NOT mean "this is a block material".
# Off by default. Cast walls built from several separate boxes must NOT get per-island offsets (11-11 test on SQ HQ:
# island offsets drew a new seam across a continuous wall = breaks B7).


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
    base = {k: hexlin(v) for k, v in palette_hex.items()}
    cmin = math.cos(math.radians(c["strip_angle"]))
    st = dict(objects=0, faces=0, skipped_faces=0, strip_faces=0, blocks=0, flat_objects=0, unknown_cid=0)
    allz = [(o.matrix_world @ v.co).z for o in objs if o.type == "MESH" for v in o.data.vertices]
    gz0, gz1 = (min(allz), max(allz)) if allz else (0.0, 1.0)
    cuts = sorted(set([gz0, gz1] + [float(b) for b in (c["bands"] or []) if gz0 < float(b) < gz1]))

    def band_of(z):
        for i in range(len(cuts) - 1):
            if z <= cuts[i + 1] or i == len(cuts) - 2:
                return cuts[i], cuts[i + 1]
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
        zs = [p.z for p in wv]
        z0, z1 = min(zs), max(zs)
        flat = (z1 - z0) < c["flat_h"]
        axis = None
        if flat:
            xs, ys = [p.x for p in wv], [p.y for p in wv]
            axis = (0, min(xs), max(xs)) if (max(xs) - min(xs)) >= (max(ys) - min(ys)) else (1, min(ys), max(ys))
            st["flat_objects"] += 1
        isl, nisl, emap = _islands(me)
        blk = None
        blk_attr = me.attributes.get("blk")
        if blk_attr is not None:
            vals = [blk_attr.data[i].value for i in range(len(me.polygons))]
            if len(set(vals)) >= c["block_min"]:
                blk = vals
        if blk is None and nisl >= c["block_min"]:
            blk = isl
        if blk is not None:
            st["blocks"] += len(set(blk))
        st["objects"] += 1
        fn = [(nm @ p.normal).normalized() for p in me.polygons]
        for p in me.polygons:
            ci = cid.data[p.index].value
            name = cid_names[ci] if 0 <= ci < len(cid_names) else None
            b = base.get(name) if name else None
            if b is None:
                st["unknown_cid"] += 1
                continue
            if name.startswith(skip):
                st["skipped_faces"] += 1
                continue
            nz = fn[p.index].z
            f = c["top"] if nz >= 0.85 else c["shoulder"] if nz > 0.3 else c["side"] if nz >= -0.3 else c["under"]
            vs = [wv[v] for v in p.vertices]
            # B2: bevel strip = narrow face (area / longest edge <= 1.6 x bevel) that bends against an edge neighbour
            lmax = max((vs[k] - vs[(k + 1) % len(vs)]).length for k in range(len(vs)))
            area_w = 0.0
            for k in range(1, len(vs) - 1):
                area_w += ((vs[k] - vs[0]).cross(vs[k + 1] - vs[0])).length * 0.5
            if area_w / max(1e-9, lmax) <= 1.6 * c["bevel"] and nz > -0.3:
                if any(fn[q].dot(fn[p.index]) < cmin for ek in p.edge_keys for q in emap[ek] if q != p.index):
                    f *= c["strip"]
                    st["strip_faces"] += 1
            # B4: one value offset per block
            if blk is not None and name in c["block_classes"]:
                f *= 1.0 + c["block"] * (2.0 * _hash01(o.name, blk[p.index]) - 1.0)
                st["block_faces"] = st.get("block_faces", 0) + 1
            # B1: storey band of this face (tall parts) or the long axis (flat parts)
            if not flat:
                lo, hi = band_of(sum(v.z for v in vs) / len(vs))
            for li in p.loop_indices:
                v = wv[me.loops[li].vertex_index]
                if flat:
                    a, amin, amax = axis
                    t = (v[a] - amin) / max(1e-6, amax - amin)
                    g = 1.0 - c["grad_flat"] * (1.0 - t)
                else:
                    t = min(max((v.z - lo) / max(1e-6, hi - lo), 0.0), 1.0)
                    g = 1.0 - c["grad"] * (1.0 - t)
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
