"""Assemble sol (codex image_gen) prompt files from templates + character config.

Every prompt starts with the same header that made sol behave on 2026-10-07:
"Use the built-in image_gen tool (not the CLI fallback) ... Save the result to ./<out> ... do not upscale".
The script only WRITES prompt files and prints the matching sol_image.sh command; it never calls sol.

Modes
  fourview  --view front|left|right|back --round r1 --n 2      new views (front: design sheet + format template; others: chosen front + design sheet [+ topdown])
  edit      --view V --input IMG --fixes FILE [--ref IMG2] --round r2 --n 2   image-edit corrections on a chosen view
  faceround --view front|left|right --input IMG --round fr --n 2               make the face round (front: whole view; side: head crop)
  struct    --view V --input IMG                                               structure reference (volumetric light) for Tripo geometry
  expr      --input FACE_FRONT_PNG                                             one prompt per expression in cfg.face.expressions (except neutral)

Output prompt files go to {workspace}/prompts/{slug}-<mode>-<view>-<round>-<n>.txt,
images to {out_dir}/sheet/ (fourview/edit/faceround), {out_dir}/struct/ (struct), {out_dir}/face/ (expr).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import SKILL_DIR, load_cfg, vault_path  # noqa: E402

T = os.path.join(SKILL_DIR, "templates")


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def header(out_rel, w, h, edit):
    verb = "EDIT the first attached image" if edit else "generate the image"
    return (f"Use the built-in image_gen tool (not the CLI fallback) to {verb}. One image_gen call. "
            f"Size {w}x{h} ({'portrait' if h > w else 'square'}), quality high. Save the result to ./{out_rel}, "
            f"then verify and report the real pixel dimensions (do not upscale). Do not touch any other file.\n\n")


def fill(text, mapping):
    for k, v in mapping.items():
        text = text.replace("{" + k + "}", str(v))
    return text


def rel_to_ws(cfg, p):
    r = os.path.relpath(p, cfg["workspace"]).replace("\\", "/")
    if r.startswith(".."):
        raise SystemExit(f"out_dir must be inside workspace (sol saves relative to it): {p}")
    return r


def write_prompt(cfg, name, text, out_img, refs):
    pdir = os.path.join(cfg["workspace"], "prompts")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(os.path.dirname(out_img), exist_ok=True)
    pp = os.path.join(pdir, name)
    with open(pp, "w", encoding="utf-8") as f:
        f.write(text)
    sh = os.path.join(SKILL_DIR, "scripts", "sol_image.sh")
    cmd = f'bash "{sh}" --ws "{cfg["workspace"]}" --prompt "{pp}"' + "".join(f' -i "{r}"' for r in refs if r)
    print("PROMPT", pp)
    print("IMAGE ", out_img)
    print("RUN   ", cmd)
    return pp


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["fourview", "edit", "faceround", "struct", "expr"])
    ap.add_argument("--config", required=True)
    ap.add_argument("--view", choices=["front", "left", "right", "back"])
    ap.add_argument("--round", default="r1")
    ap.add_argument("--n", type=int, default=1, help="how many candidate prompts (each = one image)")
    ap.add_argument("--input", help="image to edit / chosen front / face render")
    ap.add_argument("--fixes", help="text file with numbered fixes (edit mode)")
    ap.add_argument("--ref", action="append", default=[], help="extra reference images")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    fv = cfg.get("fourview", {})
    W, H = cfg["sheet"]["size"]
    slug, name = cfg["slug"], cfg["name"]
    d = cfg.get("design", {})
    design_sheet = vault_path(cfg, d.get("design_sheet"))
    topdown = vault_path(cfg, d.get("topdown"))
    common = {"NAME": name, "AGE": d.get("age", ""), "ONE_LINE": d.get("one_line", ""),
              "SKIN_EYES_HAIR": d.get("skin_eyes_hair", ""),
              "HEAD_RATIO_LO": cfg["sheet"]["head_ratio"][0], "HEAD_RATIO_HI": cfg["sheet"]["head_ratio"][1],
              "HEADS": f"{1/cfg['sheet']['head_ratio'][1]:.1f}-{1/cfg['sheet']['head_ratio'][0]:.1f}",
              "PROPORTION_NOTES": fv.get("proportion_notes", ""), "FACE_NOTES": fv.get("face_notes", ""),
              "IDENTITY_MARKERS": fv.get("identity_markers_en", ""), "VOLUME_LIST": fv.get("volume_list", "clothing and gear"),
              "EYE_STYLE": fv.get("eye_style", "irises with two small white catchlights"),
              "PERSONALITY_NOTE": fv.get("personality_note", "")}

    if a.mode == "fourview":
        if not a.view:
            ap.error("--view required")
        cb = fv.get("character_block")
        if not cb:
            raise SystemExit("config fourview.character_block not set (write it from templates/fourview/character_block.wren.txt)")
        cbp = cb if os.path.isabs(cb) else os.path.join(cfg["workspace"], cb)
        body = fill(read(os.path.join(T, "fourview", "body.txt")), dict(common, CHARACTER_BLOCK=read(cbp).strip()))
        views = json.loads(read(os.path.join(T, "fourview", "views.json")))
        vb = fill(views[a.view], dict(common, VIEW_NOTES=fv.get("view_notes", {}).get(a.view, "")))
        if a.view == "front":
            refs = [design_sheet, vault_path(cfg, d.get("format_template_front"))]
        else:
            if not a.input:
                raise SystemExit("--input <chosen front png> required for side/back views")
            refs = [a.input, design_sheet] + ([topdown] if a.view == "back" and topdown else [])
        for i in range(1, a.n + 1):
            out = os.path.join(cfg["out_dir"], "sheet", f"{slug}-{a.view}-{a.round}-{i}.png")
            text = header(rel_to_ws(cfg, out), W, H, False) + body + "\n" + vb + "\n"
            write_prompt(cfg, f"{slug}-fv-{a.view}-{a.round}-{i}.txt", text, out, refs + a.ref)

    elif a.mode == "edit":
        if not (a.view and a.input and a.fixes):
            ap.error("edit needs --view --input --fixes")
        fixes = read(a.fixes).strip()
        t = read(os.path.join(T, "fourview", "edit_fix.txt")).split("HOW TO WRITE")[0].rstrip() + "\n"
        for i in range(1, a.n + 1):
            out = os.path.join(cfg["out_dir"], "sheet", f"{slug}-{a.view}-{a.round}-{i}.png")
            text = header(rel_to_ws(cfg, out), W, H, True) + fill(t, dict(common, VIEW=a.view.upper(), FIXES=fixes))
            write_prompt(cfg, f"{slug}-edit-{a.view}-{a.round}-{i}.txt", text, out, [a.input] + a.ref)

    elif a.mode == "faceround":
        if not (a.view and a.input):
            ap.error("faceround needs --view --input")
        if a.view == "front":
            t = fill(read(os.path.join(T, "fourview", "face_round_front.txt")), common)
            refs, size = [a.input, design_sheet], (W, H)
        else:
            t = fill(read(os.path.join(T, "fourview", "face_round_profile.txt")),
                     dict(common, FACING="LEFT" if a.view == "left" else "RIGHT")).split("(Workflow:")[0]
            if not a.ref:
                raise SystemExit("side faceround: --input = head crop png, --ref = new front head crop png")
            refs, size = [a.input], (1024, 1024)
        for i in range(1, a.n + 1):
            out = os.path.join(cfg["out_dir"], "sheet", f"{slug}-{a.view}-face-{a.round}-{i}.png")
            text = header(rel_to_ws(cfg, out), size[0], size[1], True) + t
            write_prompt(cfg, f"{slug}-faceround-{a.view}-{a.round}-{i}.txt", text, out, refs + a.ref)

    elif a.mode == "struct":
        if not (a.view and a.input):
            ap.error("struct needs --view --input (the FINAL flat view)")
        out = os.path.join(cfg["out_dir"], "struct", f"{slug}-struct-{a.view}.png")
        text = header(rel_to_ws(cfg, out), W, H, True) + fill(read(os.path.join(T, "fourview", "structure_ref.txt")),
                                                             dict(common, VIEW=a.view))
        write_prompt(cfg, f"{slug}-struct-{a.view}.txt", text, out, [a.input])

    elif a.mode == "expr":
        if not a.input:
            ap.error("expr needs --input <face_front.png from face_render.py>")
        t = read(os.path.join(T, "face", "expression_common.txt"))
        for e in cfg["face"].get("expressions", []):
            if not e.get("desc"):
                continue
            out = os.path.join(cfg["out_dir"], "face", f"expr-{e['id']}.png")
            text = header(rel_to_ws(cfg, out), 1024, 1024, True) + fill(t, dict(common, DESC=e["desc"]))
            write_prompt(cfg, f"{slug}-expr-{e['id']}.txt", text, out, [a.input] + a.ref)


if __name__ == "__main__":
    main()
