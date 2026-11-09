"""Step 2 · colour-pass prompt files (painted by codex terra, 11-07).   py -3 po_prompts.py <cfg.json> <work_dir>

Finish = the mo.co CLEAR / LUMINOUS look (勾哥 2026-11-09: "这种写实的笔触已经作废了,我们要的是 moco 清透感笔触",
said looking at the old 06 guard-booth benchmark ref06_booth.png; the 11-04 "06 哨亭新版干净上色" benchmark is VOID).
Benchmark images: vault `013 美术/丛林Lab/贴图风格基准/moco清透感_20261109/` (README there). Lights are painted with their
halo on the surrounding surfaces (勾哥 11-09 「所有发光的地方都要有光效的 paint over」); NO ambient / environment
light and no glow without a source on the model itself (勾哥 11-09 「不要考虑环境光...不要给建筑或是物体加没有来由的光晕的颜色」).

Writes <work>/p_<sheet>.txt for every sheet in canvas/<set>_meta.json. References, in order:
  1   the canvas sheet itself (EDITED, layout kept)
  2-4 cfg.prompt.style_refs = the finish benchmark, three mo.co in-game crops: building facade, prop (red locker),
      light + halo (lava lamp). Default: the three files in 贴图风格基准/moco清透感_20261109/ (absolute paths if the
      vault sits on another drive). Surface treatment only - mo.co shapes / colours are never copied (拍板 #14).
  5   cfg.prompt.card (optional): this object's own approved scene painting / crop - read for colour layout only
Run each with:  bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh <work_dir> <sheet> <N>   (terra copy for paint-over)
N = number of references printed at the end (written to refcount_<set>.txt; default 4, 5 with card). 4 in parallel via
xargs -P 4 inside ONE run_in_background command; REJECT -> rerun once unchanged. After registration run po_colorlock.py.

cfg.prompt fields: what (what the sheet shows), colors (base colours to keep, e.g. "warm cream shell #DCC8B3,
grey frames #8A8E94, cyan light strip #55FDFE (glow)"), lights (optional: what glows and in which colour, e.g. "the
cyan strip above the window and the amber lamp by the door"), card + card_desc (optional), style_refs (optional,
up to 3 paths), extra (optional dict sheet_name -> extra instruction lines, e.g. "the dark square is a closed metal
hatch, NOT a window").
"""
import json
import os
import sys

VAULT_STD = "I:/My Drive/Obsidian/ExtractionRaider/01 - 星际拓荒重构/013 美术/丛林Lab/贴图风格基准/moco清透感_20261109"
DEFAULT_STYLE_REFS = [VAULT_STD + "/expedition_mocoref_清透感建筑立面_830x530.png",
                      VAULT_STD + "/expedition_mocoref_清透感道具红柜_380x380.png",
                      VAULT_STD + "/expedition_mocoref_清透感发光件熔岩灯光晕_380x360.png"]

BODY = """WHAT THIS IS: image 1 is a sheet of orthographic flat renders of 3D game models ({what}) laid out on a pure green #00FF00 background. It will be projected back onto the 3D models as their colour texture, so every pixel must stay where it is.{multi}

TASK: EDIT image 1 into a CLEAR, LUMINOUS stylized game texture in the look of the mobile game screenshots in images 2-4 (the game mo.co). This is a colour pass on top of the existing render, not a redraw.
- Keep EVERY shape, edge, opening, gap, seam and the outer silhouette at EXACTLY the same pixel position and size. Same framing, same scale, no perspective change, no camera move, do not crop, do not add or remove any part, paint nothing outside the existing silhouette.
- Keep the background flat pure #00FF00 everywhere outside the models.
- Keep each part's base colour: {colors}.
{extra}
FINISH: take ONLY the surface treatment of images 2-4 (image 2 = a building facade, image 3 = a red locker, image 4 = a pink lava lamp lighting the furniture around it). Never copy their shapes, objects, colours, lighting direction or the round UI buttons.
- Big clean colour areas: every panel and block is ONE clean, bright, saturated tone with only ONE very large, very soft gradient - a little lighter at its top, a little deeper and RICHER toward its bottom - like the brick wall in image 2 and the locker in image 3.
- Colours stay pure and luminous, as if the light comes from inside them. To darken a colour use the SAME hue, deeper and more saturated (red -> deep crimson, cream -> warm peach-tan, grey -> a slightly darker clean grey); never mix grey, brown or black into it. Keep every base colour at least as saturated as listed.
- Light colours are clean warm-tinted whites / creams like the window frames in image 2, not dirty beige. Dark parts (frames, trims, metal) are clean mid-dark tones, never near-black, never sooty grey.
- Edges: where a top edge or corner rounds over, a soft, slightly wide lighter band like the top rim of the locker in image 3. Not a thin hard line, no outline.
- Surfaces are smooth and uninterrupted: no panel seams, tile grid, stone joints, cracks or chips unless that line is real geometry already visible in image 1. Materials read through a few big clean shapes only: wood = separate planks, each one flat tone, thin plank gaps and a few nail dots like the floor in image 4 (no grain, no knots); cloth = soft big folds; metal = clean tone with the soft edge band.
- Occlusion: only a soft, narrow, deeper tint of the SAME hue in the tightest inner corners and right under overhangs. Never grey, never brown, never blue or violet.
- Window glass ONLY where the base colours list glass: clear saturated teal-blue, a bit lighter toward the top, one soft wide reflection; if the window is lit, a warm glow fills it. Solid panels, doors, plates and lids are NOT glass.
{lights}{card}
AVOID (this matters most): realistic or painterly rendering, brush strokes, visible strokes, stone / concrete texture, mottling, blotches, speckles, noise, grain, panel seams or grid lines that are not geometry, chipped edges, scratches, scuffs, dents, dust, dirt, stains, streaks, drips, grunge, wear, rust, ageing of any kind; greyish, muddy, washed-out or desaturated colours; near-black or sooty frames; thin hard highlight lines; black lines or outlines; directional sunlight, cast shadows, sky light (the game engine adds those; the light painted AROUND the model's own lamps and light strips is NOT sunlight and IS wanted); text, numbers, logos; changing any shape; anything outside the silhouettes; any colour other than the base colours, their lighter / deeper tones and the colour of the model's own lights spilling onto nearby surfaces."""

LIGHTS = """- LIGHTS - paint every light, glowing like image 4: {lights}. Each light itself is bright: an almost-white core fading to its saturated colour at its rim, never flat. ITS LIGHT IS PAINTED ONTO EVERYTHING AROUND IT that faces it (walls, piers, roof edges, poles, frames, floor), the way the pink lamp in image 4 tints the table, the armchair and the floor: those surfaces shift toward the light's colour and get brighter - strongest right next to the light, fading out smoothly within about 2-3 m (roughly the height of a door). The glow keeps its colour and never washes out to flat white; a sign or screen keeps its picture colours readable.
"""
NO_AMBIENT = """- ONLY THE MODEL'S OWN LIGHTS: do not paint environment light, ambient light, sky light, sunset light, bounce light or coloured atmosphere of any kind. The ONLY light you may paint is light coming from a light source that is part of this model (listed below). A surface that has no such light source right next to it keeps its plain base colour - no coloured glow, halo, rim tint or haze from nowhere.
"""
NO_LIGHTS = """- This sheet has NO light sources: paint NO glow, halo or light tint anywhere.
"""
LIGHTS_DEFAULT = "every light strip, lamp, screen, sign and lit window among the base colours (the parts marked glow / light)"

MULTI = (" The sheet holds SEVERAL SEPARATE views laid out side by side; each view is one part seen straight on "
         "(some from the game camera angle, some from the side). Paint each view as its own object and keep the green gaps between them.")
CARD = ("- Image {n} is {card_desc}: use it only to check which part gets which colour and where the lights are. Do NOT copy "
        "its brushwork, texture or any wear; the finish comes from images 2-4.\n")


def head(refl, out):
    return ("Do not read or load any skill. Call image_gen with referenced_image_paths set to EXACTLY "
            + json.dumps(refl, ensure_ascii=False) + " and pass the instructions below to image_gen verbatim.\n\n"
            "Use the built-in image_gen tool (not a CLI fallback). Generate ONE image, landscape 1536x1024, quality high, "
            "by EDITING image 1 (keep its exact layout). "
            f"Save it to ./img/{out}.png, then report the real pixel size. Do not touch any other file.\n\n")


def main():
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    W = os.path.abspath(sys.argv[2]).replace(os.sep, "/")
    pr = cfg["prompt"]
    if "marks" in pr:
        sys.exit("prompt.marks is gone (no weathering on J01 buildings since 2026-11-04) - delete it from the config")
    refs = list(pr.get("style_refs") or DEFAULT_STYLE_REFS)[:3]
    if any("ref06" in os.path.basename(r) for r in refs):
        sys.exit("style_refs points at the 06 guard booth (ref06_*): VOID since 2026-11-09 (勾哥: 写实笔触作废, 要 mo.co 清透感)."
                 " Delete prompt.style_refs from the config to use the mo.co clarity benchmark")
    card = ""
    if pr.get("card"):
        refs.append(pr["card"])
        card = CARD.format(n=len(refs) + 1, card_desc=pr.get("card_desc", "the approved scene painting of this same object"))
    if pr.get("lights") or "glow" in (cfg.get("palette") or {}):
        lights = NO_AMBIENT + LIGHTS.format(lights=pr.get("lights") or LIGHTS_DEFAULT)
    else:
        lights = NO_AMBIENT + NO_LIGHTS
    for r in refs:
        if not os.path.exists(r):
            sys.exit("missing reference: " + r)
    extra = pr.get("extra", {})
    meta = json.load(open(os.path.join(W, "canvas", cfg["set"] + "_meta.json"), encoding="utf-8"))
    names = []
    for sh in meta["sheets"]:
        n = sh["name"]
        multi = MULTI if len(sh["tiles"]) > 1 else ""
        ex = extra.get(n, "")
        ex = ("- " + ex.strip().lstrip("- ") + "\n") if ex else ""
        txt = head([W + "/canvas/" + n + ".png"] + refs, n) + BODY.format(
            what=pr["what"], multi=multi, colors=pr["colors"], extra=ex, lights=lights, card=card)
        open(os.path.join(W, "p_%s.txt" % n), "w", encoding="utf-8").write(txt)
        names.append(n)
    os.makedirs(os.path.join(W, "img"), exist_ok=True)
    # LF only: xargs on Git Bash keeps the trailing \r of CRLF lines -> every job name breaks
    open(os.path.join(W, "joblist_%s.txt" % cfg["set"]), "w", newline="\n").write("\n".join(names) + "\n")
    nref = 1 + len(refs)
    open(os.path.join(W, "refcount_%s.txt" % cfg["set"]), "w", newline="\n").write("%d\n" % nref)
    print("\n".join(names))
    print("refs per job (run_codex.sh last arg): %d" % nref)


if __name__ == "__main__":
    main()
