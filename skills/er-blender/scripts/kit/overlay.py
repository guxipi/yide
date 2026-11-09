#!/usr/bin/env python3
"""Blockout overlay (system Python: numpy + Pillow).  Puts a blockout render on top of a concept image.

One command per round:
  py overlay.py --ref concept.png --blend scene.blend --collection LH_Blockout --view top --out DIR
                [--frame x0,y0,x1,y1] [--pts "u,v=x,y;..."] [--check "name:u,v=x,y,z;..."]
                [--ref-mask "x,y;x,y;..." | --ref-mask mask.png] [--label r1]
Or reuse a render you already made with overlay_render.py:
  py overlay.py --ref concept.png --render DIR/L_top.png --out DIR ...   (reads DIR/L_top.json)

Correspondences (--pts): concept-image pixel  =  world ground point in metres (Blender X east, Y north,
z optional, default 0).  Pick features that sit on the ground and that both the concept and the design
data define: pad / plot corners, door sill ends, post feet.  2 points -> similarity, 3 -> affine,
4+ -> homography (exact for a ground plane seen in perspective).  They are saved next to the concept
as <concept>.overlay.json together with --ref-mask and --check, so later rounds only need --ref/--blend.

--check: named points above the ground ("tower_top:512,260=0,0,8") -> after the warp the script reports
how far the blockout's projection of that world point lands from where the concept draws it (px and
roughly in metres).  Heights only line up approximately when the concept was not drawn with our camera;
use them to catch "twice too tall", not 5 % errors.

--ref-mask: outline of the main mass in the concept (polygon in concept pixels, or a mask png). Gives
IoU / recall (how much of the concept mass the blockout covers) / precision.

Writes in --out:
  <label>_<view>_board.png   concept | concept + 55 % blockout | grey concept + magenta blockout edge
                             (+ cyan concept-mask edge), one row, with the numbers printed under it
  <label>_<view>_flicker.gif concept <-> concept with blockout
and prints one JSON line.  Exit code 0 even when IoU is low: judging is the agent's job.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
RENDER_PY = os.path.normpath(os.path.join(HERE, "..", "blender", "overlay_render.py"))
BLENDER_CANDIDATES = [os.environ.get("BLENDER", ""), r"F:\Apps\blender.exe",
                      r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
                      r"C:\Program Files\Blender Foundation\Blender 5.1\blender.exe"]


# ---------------------------------------------------------------- parsing
def parse_pts(s):
    """'u,v=x,y[,z];...' -> list of ((u,v),(x,y,z))."""
    out = []
    for item in [t for t in (s or "").split(";") if t.strip()]:
        a, b = item.split("=")
        u, v = (float(t) for t in a.split(","))
        w = [float(t) for t in b.split(",")]
        out.append(((u, v), (w[0], w[1], w[2] if len(w) > 2 else 0.0)))
    return out


def parse_checks(s):
    """'name:u,v=x,y,z[@fu,fv];...' -> (name, (u,v), (x,y,z), foot_uv or None).
    @fu,fv = concept pixel of the feature's foot on the correspondence plane (tower base centre, post foot):
    the concept height is then measured above the concept's own position instead of the design position."""
    out = []
    for item in [t for t in (s or "").split(";") if t.strip()]:
        name, rest = item.split(":", 1)
        foot = None
        if "@" in rest:
            rest, f = rest.split("@")
            foot = tuple(float(t) for t in f.split(","))
        out.append((name.strip(),) + parse_pts(rest)[0] + (foot,))
    return out


def ground_from_px(P, uv, z):
    """Concept pixel -> world (x, y) on the horizontal plane at height z."""
    P = np.asarray(P)
    Hz = np.c_[P[:, 0], P[:, 1], P[:, 2] * z + P[:, 3]]
    q = np.linalg.solve(Hz, [uv[0], uv[1], 1.0])
    return q[:2] / q[2]


def blender_exe():
    for p in BLENDER_CANDIDATES:
        if p and os.path.exists(p):
            return p
    p = shutil.which("blender")
    if p:
        return p
    raise SystemExit("Blender not found: set BLENDER=<path to blender.exe>")


# ---------------------------------------------------------------- geometry
def project(P, X):
    X = np.asarray(X, float)
    q = np.c_[X, np.ones(len(X))] @ np.asarray(P).T
    return q[:, :2] / q[:, 2:3]


def fit_transform(src, dst):
    """3x3 matrix mapping src px -> dst px. 2 pts similarity, 3 affine, 4+ homography (DLT)."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    n = len(src)
    if n < 2:
        raise SystemExit("need at least 2 --pts")
    if n == 2:
        s0, s1 = src
        d0, d1 = dst
        vs, vd = s1 - s0, d1 - d0
        k = np.hypot(*vd) / np.hypot(*vs)
        ang = math.atan2(vd[1], vd[0]) - math.atan2(vs[1], vs[0])
        c, s = k * math.cos(ang), k * math.sin(ang)
        M = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])
        t = d0 - M[:2, :2] @ s0
        M[0, 2], M[1, 2] = t
        return M, "similarity"
    if n == 3:
        A = np.c_[src, np.ones(3)]
        sol = np.linalg.solve(A, dst)  # 3x2
        M = np.eye(3)
        M[:2, :] = sol.T
        return M, "affine"
    rows = []
    for (x, y), (u, v) in zip(src, dst):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, vt = np.linalg.svd(np.array(rows))
    H = vt[-1].reshape(3, 3)
    return H / H[2, 2], "homography"


def calibrate_concept_camera(ref_uv, world, W, H_img):
    """Recover the concept image's pinhole camera from >=4 coplanar ground correspondences (all at the same z).
    Square pixels, principal point = image centre; focal from the orthogonality of the plane axes (Zhang).
    Returns dict(f, R, t, P, z0) or None when the view is too close to orthographic to solve."""
    z0 = float(np.mean(world[:, 2]))
    if len(ref_uv) < 4 or np.ptp(world[:, 2]) > 1e-3:
        return None
    Hw, _ = fit_transform(world[:, :2], ref_uv)          # world xy -> concept px
    T = np.array([[1, 0, -W / 2.0], [0, 1, -H_img / 2.0], [0, 0, 1]])
    Hc = T @ Hw                                            # principal point at origin
    h1, h2, h3 = Hc[:, 0], Hc[:, 1], Hc[:, 2]
    if abs(h1[2] * h2[2]) < 1e-12:
        return None
    f2a = -(h1[0] * h2[0] + h1[1] * h2[1]) / (h1[2] * h2[2])
    f2b = (h1[0] ** 2 + h1[1] ** 2 - h2[0] ** 2 - h2[1] ** 2) / (h2[2] ** 2 - h1[2] ** 2) if abs(h2[2] ** 2 - h1[2] ** 2) > 1e-12 else None
    cands = [f for f in (f2a, f2b) if f is not None and f > 0]
    if not cands:
        return None
    f = math.sqrt(sum(cands) / len(cands))
    Ki = np.diag([1 / f, 1 / f, 1.0])
    r1, r2 = Ki @ h1, Ki @ h2
    lam = 2.0 / (np.linalg.norm(r1) + np.linalg.norm(r2))
    r1, r2, t = r1 * lam, r2 * lam, Ki @ h3 * lam
    if t[2] < 0:                                           # camera must look at the plane from the front
        r1, r2, t = -r1, -r2, -t
    r3 = np.cross(r1, r2)
    U, _, Vt = np.linalg.svd(np.c_[r1, r2, r3])
    R = U @ Vt
    t = t - R @ np.array([0, 0, z0])                       # world z is absolute, the plane sat at z0
    K = np.array([[f, 0, W / 2.0], [0, f, H_img / 2.0], [0, 0, 1]])
    P = K @ np.c_[R, t]
    resid = np.hypot(*(project(P, world) - ref_uv).T).max()
    C = -R.T @ t
    pitch = math.degrees(math.asin(max(-1, min(1, -(R.T @ np.array([0, 0, 1.0]))[2]))))
    return {"f": f, "R": R, "t": t, "P": P, "resid": float(resid), "cam_pos": C.tolist(),
            "vfov_deg": math.degrees(2 * math.atan(H_img / 2.0 / f)), "pitch_deg": pitch}


def concept_height(P, xy, uv, z_lo=-2.0, z_hi=60.0):
    """Height z at ground position xy whose projection best matches concept pixel uv."""
    zs = np.linspace(z_lo, z_hi, 6201)
    q = project(P, np.c_[np.full_like(zs, xy[0]), np.full_like(zs, xy[1]), zs])
    i = int(np.argmin(np.hypot(q[:, 0] - uv[0], q[:, 1] - uv[1])))
    return float(zs[i]), float(np.hypot(q[i, 0] - uv[0], q[i, 1] - uv[1]))


def apply_h(H, pts):
    pts = np.asarray(pts, float)
    q = np.c_[pts, np.ones(len(pts))] @ H.T
    return q[:, :2] / q[:, 2:3]


def warp_rgba(img, H, size):
    """Warp img (render space) into ref space with H (render->ref)."""
    Hi = np.linalg.inv(H)
    Hi = Hi / Hi[2, 2]
    coeffs = tuple(Hi.flatten()[:8])
    return img.transform(size, Image.PERSPECTIVE, coeffs, Image.BILINEAR)


def poly_mask(size, poly):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon([tuple(p) for p in poly], fill=255)
    return np.array(m) > 127


def edge_of(mask, width=3):
    im = Image.fromarray((mask * 255).astype(np.uint8))
    dil = np.array(im.filter(ImageFilter.MaxFilter(width))) > 127
    ero = np.array(im.filter(ImageFilter.MinFilter(width))) > 127
    return dil & ~ero


def font(sz):
    for f in (r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--blend")
    ap.add_argument("--collection")
    ap.add_argument("--render", help="existing overlay_render.py png (json next to it)")
    ap.add_argument("--view", default="top", choices=["top", "g46", "cam", "concept"])
    ap.add_argument("--frame")
    ap.add_argument("--res", default="1024")
    ap.add_argument("--label", default="blockout")
    ap.add_argument("--pts")
    ap.add_argument("--check")
    ap.add_argument("--ref-mask")
    ap.add_argument("--alpha", type=float, default=0.75)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    # correspondences belong to the concept image (not to a view): saved next to it
    side = a.ref + ".overlay.json"
    saved = json.load(open(side, encoding="utf-8")) if os.path.exists(side) else {}
    if "pts" not in saved:  # early format kept one block per view
        saved.update(next((v for v in saved.values() if isinstance(v, dict) and v.get("pts")), {}))
    pts_s = a.pts if a.pts is not None else saved.get("pts")
    chk_s = a.check if a.check is not None else saved.get("check")
    msk_s = a.ref_mask if a.ref_mask is not None else saved.get("ref_mask")
    if not pts_s:
        raise SystemExit("no --pts and nothing saved in " + side)
    saved.update({k: v for k, v in (("pts", pts_s), ("check", chk_s), ("ref_mask", msk_s)) if v})
    json.dump(saved, open(side, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    ref = Image.open(a.ref).convert("RGB")
    W, Hh = ref.size
    pts = parse_pts(pts_s)
    ref_uv = np.array([p[0] for p in pts])
    world = np.array([p[1] for p in pts])
    cal = calibrate_concept_camera(ref_uv, world, W, Hh)
    if a.view == "concept" and cal is None:
        raise SystemExit("--view concept needs >=4 --pts on one ground plane (same z) in a perspective image")

    # render (or reuse)
    if a.render:
        rpng = a.render
    else:
        if not (a.blend and a.collection):
            raise SystemExit("give --render, or --blend and --collection")
        cmd = [blender_exe(), "-b", a.blend, "--factory-startup", "-P", RENDER_PY, "--python-exit-code", "1",
               "--", "--collection", a.collection, "--out", a.out, "--label", a.label, "--view", a.view,
               "--res", a.res]
        if a.frame:
            cmd += ["--frame", a.frame]
        if a.view == "concept":
            cj = os.path.join(a.out, "%s_concept_cam.json" % a.label)
            json.dump({"R": cal["R"].tolist(), "t": cal["t"].tolist(), "f": cal["f"], "w": W, "h": Hh},
                      open(cj, "w", encoding="utf-8"), indent=1)
            cmd += ["--camjson", cj]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        line = [l for l in p.stdout.splitlines() if l.startswith("ER_JSON ")]
        if p.returncode != 0 or not line:
            sys.stderr.write(p.stdout[-3000:] + p.stderr[-2000:])
            raise SystemExit("overlay_render failed")
        rpng = json.loads(line[-1][8:])["png"]
    meta = json.load(open(os.path.splitext(rpng)[0] + ".json", encoding="utf-8"))
    P = np.array(meta["P"])
    rnd = Image.open(rpng).convert("RGBA")

    rnd_uv = project(P, world)
    H, kind = fit_transform(rnd_uv, ref_uv)
    resid = np.hypot(*(apply_h(H, rnd_uv) - ref_uv).T)

    # ref pixels per metre around the correspondences (ground plane), for metre estimates
    c = world.mean(0)
    pm = apply_h(H, project(P, [c, c + [1, 0, 0], c + [0, 1, 0]]))
    px_per_m = float((np.hypot(*(pm[1] - pm[0])) + np.hypot(*(pm[2] - pm[0]))) / 2)

    warped = warp_rgba(rnd, H, (W, Hh))
    wa = np.array(warped)
    rmask = wa[:, :, 3] > 127

    metrics = {"view": a.view, "transform": kind, "n_pts": len(pts), "resid_px_max": round(float(resid.max()), 1),
               "ref_px_per_m": round(px_per_m, 1)}
    if cal:
        metrics["concept_camera"] = {"vfov_deg": round(cal["vfov_deg"], 1), "pitch_deg": round(cal["pitch_deg"], 1),
                                     "pos_m": [round(v, 1) for v in cal["cam_pos"]], "resid_px": round(cal["resid"], 1)}
    cmask = None
    if msk_s:
        if os.path.exists(msk_s):
            cm = Image.open(msk_s).convert("L").resize((W, Hh))
            cmask = np.array(cm) > 127
        else:
            cmask = poly_mask((W, Hh), [tuple(float(t) for t in q.split(",")) for q in msk_s.split(";") if q.strip()])
        inter = float((rmask & cmask).sum())
        uni = float((rmask | cmask).sum())
        metrics.update({"iou": round(inter / max(uni, 1), 3),
                        "recall": round(inter / max(float(cmask.sum()), 1), 3),
                        "precision": round(inter / max(float(rmask.sum()), 1), 3)})
    checks = []
    for name, (u, v), X, foot in parse_checks(chk_s):
        q = apply_h(H, project(P, [X]))[0]
        d = float(np.hypot(q[0] - u, q[1] - v))
        ck = {"name": name, "concept_px": [u, v], "blockout_px": [round(q[0]), round(q[1])],
              "off_px": round(d, 1), "off_m~": round(d / px_per_m, 2), "dy_px": round(float(q[1] - v), 1),
              "design_z": X[2]}
        if cal:
            z0 = float(np.mean(world[:, 2]))
            xy = ground_from_px(cal["P"], foot, z0) if foot else X[:2]
            zc, rr = concept_height(cal["P"], xy, (u, v))
            ck.update({"concept_z": round(zc, 2), "concept_z_fit_px": round(rr, 1),
                       "height_reliable": bool(rr <= 25 and cal["resid"] <= 15)})
            if foot:
                ck["concept_xy"] = [round(float(xy[0]), 2), round(float(xy[1]), 2)]
                ck["xy_off_m"] = round(float(np.hypot(xy[0] - X[0], xy[1] - X[1])), 2)
        checks.append(ck)
    metrics["checks"] = checks

    # ---- board
    base = ref.copy()
    over = Image.alpha_composite(ref.convert("RGBA"),
                                 Image.fromarray(np.dstack([wa[:, :, :3], (wa[:, :, 3] * a.alpha).astype(np.uint8)])))
    grey = np.array(ref.convert("L").convert("RGB")) * 0.6 + 100
    grey = grey.clip(0, 255).astype(np.uint8)
    # outline every part, not just the union: alpha edge + colour jumps inside the render
    rgb = wa[:, :, :3].astype(int)
    jump = np.zeros(rmask.shape, bool)
    jump[:, 1:] |= np.abs(rgb[:, 1:] - rgb[:, :-1]).sum(2) > 45
    jump[1:, :] |= np.abs(rgb[1:, :] - rgb[:-1, :]).sum(2) > 45
    jump &= rmask
    jump = np.array(Image.fromarray((jump * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 127
    e = edge_of(rmask, 5) | jump
    grey[e] = (255, 0, 200)
    if cmask is not None:
        grey[edge_of(cmask, 5)] = (0, 220, 255)
    gimg = Image.fromarray(grey)
    d = ImageDraw.Draw(gimg)
    for (u, v), r_ in zip(ref_uv, resid):
        d.ellipse((u - 7, v - 7, u + 7, v + 7), outline=(255, 230, 0), width=3)
    for ck in checks:
        u, v = ck["concept_px"]
        bu, bv = ck["blockout_px"]
        d.line((u, v, bu, bv), fill=(255, 80, 0), width=3)
        d.ellipse((u - 6, v - 6, u + 6, v + 6), fill=(0, 220, 255))
        d.ellipse((bu - 6, bv - 6, bu + 6, bv + 6), fill=(255, 0, 200))
        d.text((bu + 8, bv - 8), ck["name"], fill=(255, 255, 255), font=font(22))
    panels = [base, over.convert("RGB"), gimg]
    scale = min(1.0, 1800.0 / (3 * W))
    pw, ph = int(W * scale), int(Hh * scale)
    txt = "%s · %s · %d pts · resid max %.1f px · %.1f px/m" % (os.path.basename(a.ref), kind, len(pts),
                                                                resid.max(), px_per_m)
    if "iou" in metrics:
        txt += " · IoU %.2f  recall %.2f  precision %.2f" % (metrics["iou"], metrics["recall"], metrics["precision"])
    if cal:
        txt += " · concept cam: vFOV %.0f° pitch %.0f°" % (cal["vfov_deg"], cal["pitch_deg"])
    lines = [txt]
    for c_ in checks:
        ln = "%s: off %.1f px (~%.2f m)" % (c_["name"], c_["off_px"], c_["off_m~"])
        if "concept_z" in c_:
            ln += " · concept draws it at z %.1f m (design %.1f m, x%.2f; fit %.0f px)" % (
                c_["concept_z"], c_["design_z"], c_["concept_z"] / c_["design_z"] if c_["design_z"] else float("nan"),
                c_["concept_z_fit_px"]) + ("" if c_["height_reliable"] else " [UNRELIABLE: concept perspective inconsistent]")
        if "xy_off_m" in c_:
            ln += " · concept position (%.1f, %.1f), %.1f m from design" % (c_["concept_xy"][0], c_["concept_xy"][1],
                                                                          c_["xy_off_m"])
        lines.append(ln)
    fnt = font(20)
    maxw = pw * 3 + 0
    meas = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    wrapped = []
    for ln in lines:
        cur = ""
        for part in ln.split(" · "):
            cand = part if not cur else cur + " · " + part
            if cur and meas.textlength(cand, font=fnt) > maxw:
                wrapped.append(cur)
                cur = "    " + part
            else:
                cur = cand
        wrapped.append(cur)
    lines = wrapped
    board = Image.new("RGB", (pw * 3 + 20, ph + 40 + 30 * len(lines)), (30, 30, 34))
    for i, im in enumerate(panels):
        board.paste(im.resize((pw, ph), Image.LANCZOS), (5 + i * (pw + 5), 5))
    bd = ImageDraw.Draw(board)
    for i, ln in enumerate(lines):
        bd.text((10, ph + 15 + 30 * i), ln, fill=(235, 235, 235), font=fnt)
    stem = os.path.join(a.out, "%s_%s" % (a.label, a.view))
    board.save(stem + "_board.png")
    fl = [base.resize((pw, ph)), over.convert("RGB").resize((pw, ph))]
    fl[0].save(stem + "_flicker.gif", save_all=True, append_images=fl[1:], duration=600, loop=0)
    metrics.update({"board": stem + "_board.png", "flicker": stem + "_flicker.gif", "saved_pts": side})
    print(json.dumps(metrics, ensure_ascii=False))


if __name__ == "__main__":
    main()
