"""Step 2 · colour-pass prompt files (painted by codex terra, 11-07).   py -3 po_prompts.py <cfg.json> <work_dir>

CANVAS ONLY (勾哥 2026-11-09 evening, WS2: 「明明好好的航空灰,为什么带了紫调?不要给 paintover 生图的时候喂 moco 的图」
「参考图什么色,paintover 就应该是什么色」「不要有环境光的 hue」). terra gets exactly ONE image - the canvas sheet - and
edits it in place. The mo.co clarity finish (vault 013 美术/AI记忆/feedback-paintover-moco-clarity-benchmark-20261109:
clean flat tone, no seams / strokes) is described in words only. NO BAKED SHADING (勾哥 11-09, LOG: 「阴影 hue 都不是你
操心的事情」): every part is one flat base colour edge to edge - no gradient, no AO / inner-corner darkening, no edge band,
no shadow; the engine does all light and shade. Every base colour = the canvas colour = the no-hue concept colour (勾哥 11-09 「颜色从没有 hue 的概念图取」).
Lights: only the model's own emitters, only right beside them (勾哥 11-09 「不要考虑环境光...不要给建筑或是物体加没有来由
的光晕的颜色」). After registration run po_hardhue.py (paint-over may add VALUE only, never hue).
Ported from ArtWork/J01v7_WS2_20261109/gen/ws2_po_prompts.py.

Writes <work>/p_<sheet>.txt for every sheet in canvas/<set>_meta.json, joblist_<set>.txt and refcount_<set>.txt (= 1).
Run each with:  bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh <work_dir> <sheet> 1   (terra copy for paint-over)
4 in parallel via xargs -P 4 inside ONE run_in_background command; REJECT -> rerun once unchanged.

cfg.prompt fields: what (what the sheet shows), colors (base colours to keep, e.g. "aviation grey shell #B9BCC0,
steel door #8A8E94, cyan light strip #55FDFE (glow)"; pale low-saturation colours such as concrete get a COLOUR LOCK
line in extra: "#CCAFA5 stays this exact colour, NOT salmon / pink"), lights (optional: the model's own emitters and
where they sit, e.g. "the red lamp on the cap top, centred, about 2/3 down from the top edge"), extra (optional dict
sheet_name -> extra instruction lines, e.g. "the dark square is a closed metal hatch, NOT a window").
REMOVED (exit with an error): style_refs and card (no reference images of any kind, 11-09), marks (no weathering, 11-04).
"""
import json
import os
import sys

BODY = """WHAT THIS IS: image 1 is a sheet of orthographic flat renders of 3D game models ({what}) laid out on a pure green #00FF00 background. It will be projected back onto the 3D models as their colour texture, so every pixel must stay where it is.{multi}

TASK: EDIT image 1 into a clean, clear stylized mobile-game texture. This is a light colour pass on top of the existing render, not a redraw.
- Keep EVERY shape, edge, opening, gap, seam and the outer silhouette at EXACTLY the same pixel position and size. Same framing, same scale, no perspective change, no camera move, do not crop, do not add or remove any part, paint nothing outside the existing silhouette.
- Keep the background flat pure #00FF00 everywhere outside the models.
- COLOURS ARE ALREADY CORRECT IN IMAGE 1: keep every part exactly the hue and saturation it has in image 1 ({colors}). Do not warm it, cool it, tint it or push it toward pink, purple, violet, lilac or blue; neutral greys stay neutral grey.
{extra}
FINISH (clean and clear, flat colour only):
- every panel and block is ONE completely flat colour, the same from edge to edge: no gradient, no lighter top or darker bottom, no ambient occlusion, no darkening in inner corners, under overhangs or where parts meet, no shadow of any kind, no lighter band along edges, no highlight, no outline. ALL light and shade comes from the game engine, not from this texture;
- surfaces are smooth and uninterrupted: no panel seams, grids, stone joints, cracks or chips unless the line is real geometry already visible in image 1; wood = separate planks, each one flat tone, thin plank gaps only (no grain, no knots);
- glass only where listed: one flat colour, no reflection.
{lights}
AVOID: any gradient, shading, ambient occlusion or shadow; realistic or painterly rendering, brush strokes, texture, mottling, noise, grain, grunge, dirt, wear, rust, ageing; any colour cast or tint (pink, purple, violet, warm orange, blue); ambient, sky or environment light; directional sunlight and cast shadows (the game engine adds lighting); coloured glows or halos on anything that is not right next to one of the model's own lights; black lines; text, numbers, logos; changing any shape; anything outside the silhouettes."""

NO_AMBIENT = """- NO ENVIRONMENT LIGHT: do not paint ambient, sky, sunset or bounce light or any coloured atmosphere. The ONLY light you may paint comes from a light source that is part of this model (listed below); every surface that is not right beside one keeps its plain base colour.
"""
LIGHTS = """- OWN LIGHTS ONLY: {lights}. Each light itself is bright: an almost-white core fading to its saturated colour at the rim. Its light tints ONLY the surfaces directly beside it (within about one metre) and only where image 1 already shows a faint tint of that colour; nothing else gets any glow. A light that is its own separate object (a strip, a lamp) is painted on that object only: on the wall behind it paint just the faint halo, never a second copy of the light.
"""
NO_LIGHTS = """- This sheet has NO light sources: paint NO glow, halo or light tint anywhere.
"""
LIGHTS_DEFAULT = "every light strip, lamp, screen, sign and lit window among the base colours (the parts marked glow / light)"
MULTI = (" The sheet holds SEVERAL SEPARATE views laid out side by side; each view is one part seen straight on "
         "(some from the game camera angle, some from the side or back). Paint each view as its own object and keep the green gaps between them.")


def head(refl, out):
    return ("Do not read or load any skill. Call image_gen with referenced_image_paths set to EXACTLY "
            + json.dumps(refl, ensure_ascii=False) + " and pass the instructions below to image_gen verbatim.\n\n"
            "Use the built-in image_gen tool (not a CLI fallback). Generate ONE image, landscape 1536x1024, quality high, "
            "by EDITING image 1 (keep its exact layout). "
            f"Save it to ./img/{out}.png, then report the real pixel size. Do not touch any other file.\n\n")


def main():
    sys.stderr.reconfigure(encoding="utf-8")
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    W = os.path.abspath(sys.argv[2]).replace(os.sep, "/")
    pr = cfg["prompt"]
    if "marks" in pr:
        sys.exit("prompt.marks is gone (no weathering on J01 buildings since 2026-11-04) - delete it from the config")
    for k in ("style_refs", "card"):
        if k in pr:
            sys.exit("prompt.%s is gone: paint-over gets the canvas ONLY (勾哥 11-09: 不要给 paintover 生图喂 moco 的图 /"
                     " 参考图什么色 paintover 就什么色; parts sheets carry a warm-pink cast that terra copies)."
                     " Delete it from the config; write colours into prompt.colors and layout notes into prompt.extra" % k)
    if pr.get("lights") or "glow" in (cfg.get("palette") or {}):
        lights = NO_AMBIENT + LIGHTS.format(lights=pr.get("lights") or LIGHTS_DEFAULT)
    else:
        lights = NO_AMBIENT + NO_LIGHTS
    extra = pr.get("extra", {})
    meta = json.load(open(os.path.join(W, "canvas", cfg["set"] + "_meta.json"), encoding="utf-8"))
    names = []
    for sh in meta["sheets"]:
        n = sh["name"]
        multi = MULTI if len(sh["tiles"]) > 1 else ""
        ex = extra.get(n, "")
        ex = ("- " + ex.strip().lstrip("- ") + "\n") if ex else ""
        txt = head([W + "/canvas/" + n + ".png"], n) + BODY.format(
            what=pr["what"], multi=multi, colors=pr["colors"], extra=ex, lights=lights)
        open(os.path.join(W, "p_%s.txt" % n), "w", encoding="utf-8", newline="\n").write(txt)
        names.append(n)
    os.makedirs(os.path.join(W, "img"), exist_ok=True)
    # LF only: xargs on Git Bash keeps the trailing \r of CRLF lines -> every job name breaks
    open(os.path.join(W, "joblist_%s.txt" % cfg["set"]), "w", newline="\n").write("\n".join(names) + "\n")
    open(os.path.join(W, "refcount_%s.txt" % cfg["set"]), "w", newline="\n").write("1\n")
    print("\n".join(names))
    print("refs per job (run_codex.sh last arg): 1")


if __name__ == "__main__":
    main()
