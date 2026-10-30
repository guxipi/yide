"""Step 1 · paint-over canvases.

blender -b <scene.blend> --factory-startup -P po_canvas.py --python-exit-code 1 -- --cfg <cfg.json> --out <work_dir>

Per group and per view one tile (only that group's objects rendered), fixed pixel density, tiles wider than a
sheet cut into chunks along the view's right axis with 0.6 m overlap, first-fit packed onto 1536x1024 sheets.
Underlay = base colour x soft AO, no directional light, pure #00FF00 background.
Writes <work>/canvas/<set>_NN.png, <set>_NN_mask.png and <work>/canvas/<set>_meta.json.
"""
import json
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import po_blender as P  # noqa: E402


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    cfg = P.load_cfg(a[a.index("--cfg") + 1])
    out = a[a.index("--out") + 1]
    scene = bpy.context.scene
    groups = P.resolve_groups(cfg)
    vdefs = P.views(cfg["pitch"])
    all_objs = sorted({n for g in groups.values() for n in g})
    P.apply_underlay(cfg, [bpy.data.objects[n] for n in all_objs])
    cam = P.setup_canvas_render(scene)
    maxw, maxh = P.SHEET_W - 2 * P.MARGIN, P.SHEET_H - 2 * P.MARGIN
    tiles = []
    for gname, names in groups.items():
        objs = [bpy.data.objects[n] for n in names]
        for v in cfg["views"]:
            t = P.tile_spec(objs, v, vdefs)
            wm, hm = t["u1"] - t["u0"], t["v1"] - t["v0"]
            vp = cfg["ppm"] * (cfg["side_ratio"] if v in ("E", "W") and "G" in cfg["views"] else 1.0)
            if wm * vp < 30 and v != cfg["views"][0]:
                continue
            if hm * vp > maxh:
                raise ValueError("tile too tall for a sheet: %s %s (%.0f px) -> lower ppm" % (gname, v, hm * vp))
            n = max(1, math.ceil(wm * vp / maxw))
            step = wm / n
            for i in range(n):
                c0 = t["u0"] + i * step - (0.6 if i else 0)
                c1 = t["u0"] + (i + 1) * step + (0.6 if i < n - 1 else 0)
                tt = dict(t)
                tt.update({"u0": c0, "u1": c1, "group": names, "gname": gname, "px_per_m": vp,
                           "w": round((c1 - c0) * vp), "h": round(hm * vp)})
                tiles.append(tt)
    sheets = P.pack(tiles)
    cdir = os.path.join(out, "canvas")
    os.makedirs(os.path.join(cdir, "_tmp"), exist_ok=True)
    meta = {"set": cfg["set"], "objects": all_objs, "sheet": [P.SHEET_W, P.SHEET_H], "pitch": cfg["pitch"],
            "sheets": []}
    meshes = [o for o in scene.objects if o.type == "MESH"]
    for si, st in enumerate(sheets):
        name = "%s_%02d" % (cfg["set"], si)
        for i, t in enumerate(st):
            for o in meshes:
                o.hide_render = o.name not in t["group"]
            t["tmp"] = os.path.join(cdir, "_tmp", "%s_%d.png" % (name, i))
            P.render_tile(scene, cam, t, t["tmp"])
        P.compose(os.path.join(cdir, name + ".png"), os.path.join(cdir, name + "_mask.png"), st)
        for t in st:
            t.pop("tmp", None)
        meta["sheets"].append({"name": name, "tiles": st, "contents": sorted({t["gname"] for t in st})})
    with open(os.path.join(cdir, cfg["set"] + "_meta.json"), "w", encoding="utf-8") as fp:
        json.dump(meta, fp, indent=1, ensure_ascii=False)
    print("PO_JSON " + json.dumps({"ok": True, "set": cfg["set"], "tiles": len(tiles),
                                   "sheets": [s["name"] for s in meta["sheets"]]}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
