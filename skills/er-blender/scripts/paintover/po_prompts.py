"""Step 2 · colour-pass prompt files (painted by codex terra, 11-07).   py -3 po_prompts.py <cfg.json> <work_dir>

Finish = er-blender references/00-造型与笔触标准.md (勾哥 11-27, mo.co vehicle reference): keep the 3D volume, add a FEW
broad, flat, opaque, hard-edged hand-painted blocks (slanted rectangles, wedges, short bars, local planar highlights) that
follow the structure and bevels, leave large quiet areas, matte, low noise. Value changes only, in the SAME hue as image 1.
Colour vs light: image 1 (the canvas) carries each part's designed base colour (= the no-hue concept colour); terra may not
add AO, cast shadow, directional light, environment / sky / bounce tint, warm highlights, blue-violet shadows or a colour
grade - Unity LabLit and the scene lights do that. Designed multi-colour parts, logos and decals stay as they are.
Lights: only the model's own emitters, painted on themselves only (iron rule 0, 11-10).
After registration run po_hardhue.py (puts the canvas a/b back pixel by pixel, keeps the painted value = the strokes).

Writes <work>/p_<sheet>.txt for every sheet in canvas/<set>_meta.json, joblist_<set>.txt and refcount_<set>.txt.
Run each with:  bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh <work_dir> <sheet> <N>   (CODEX_MODEL=gpt-6.1-terra)
4 in parallel via xargs -P 4 inside ONE run_in_background command; REJECT -> rerun once unchanged.

cfg.prompt fields: what (what the sheet shows), colors (base colours to keep, e.g. "white shell #E8E8E6 (neutral white),
steel door #8A8E94 (neutral grey), cyan light strip #55FDFE (glow)"; pale low-saturation colours get a COLOUR LOCK line in
extra), lights (optional: the model's own emitters and where they sit), extra (optional dict sheet_name -> extra lines).
card (optional): this object's OWN approved parts-sheet / design cell, a path string (all sheets) or dict sheet_name -> path;
  used only for WHERE strokes sit and how sparse they are.
style_refs (optional): list of brushwork reference images (mo.co, first choice vault 013 美术/mo.co截图/车辆语言基准_20261127/),
  used only for the SHAPE, SIZE, SPACING and placement of the strokes; never their colours, tint, lighting or environment.
N = 1 (canvas) + 1 if card + len(style_refs); one N per set.
REMOVED (exit with an error): marks (weathering).
"""
import json
import os
import sys

BODY = """WHAT THIS IS: image 1 is a sheet of orthographic flat renders of 3D game models ({what}) laid out on a pure green #00FF00 background. It will be projected back onto the 3D models as their colour texture, so every pixel must stay where it is.{multi}

TASK: EDIT image 1 into a stylized mobile-game texture. This is a light hand-painted pass on top of the existing render, not a redraw.
- Keep EVERY shape, edge, opening, gap, seam and the outer silhouette at EXACTLY the same pixel position and size. Same framing, same scale, no perspective change, no camera move, do not crop, do not add or remove any part, paint nothing outside the existing silhouette.
- Keep the background flat pure #00FF00 everywhere outside the models.
- BASE COLOUR ONLY: every part keeps its own base colour exactly as in image 1 ({colors}). Do not warm it, cool it, tint it or push it toward pink, purple, violet, lilac or blue; white stays neutral white and grey stays neutral grey. Parts that have different colours in image 1 keep their different colours (logos, decals and two-colour parts stay as they are). Each part's overall colour stays the colour of image 1.
{extra}
FINISH (hand-painted, sparse, keep the 3D volume):
- add a FEW broad, flat, opaque brush blocks with clean, slightly hand-made edges: slanted rectangles, wedges, short bars and small flat lighter patches on a plane;
- place them along the structure: beside a bevel, near a corner or fold, along a panel edge or a rail; never as random dots or spots;
- each block is the SAME colour as the surface under it, only a little lighter or a little deeper; a hard edge between a block and the base colour on the same face is fine;
- leave most of every surface as quiet plain base colour; matte, low texture noise;
- not every edge gets a highlight: no continuous light line or outline around the edges;
- surfaces stay clean: no panel seams, grids, stone joints, cracks or chips unless the line is real geometry already visible in image 1; wood = separate planks, each one flat tone with a few brush blocks, thin plank gaps only (no grain, no knots);
- NO BAKED LIGHT: no ambient occlusion, no darkening in inner corners, under overhangs or where parts meet, no cast shadow, no directional sun shading; the game engine adds all light and shade;
- glass only where listed: flat glass colour with one or two slanted flat lighter blocks.
{lights}
AVOID: ambient occlusion, darkened inner corners or overhang undersides, any baked shadow; bristle texture, impasto, thick paint build-up, scribbles, scratchy lines, dense scratches, dirt, wear, rust, ageing, mottling, noise, grain; a highlight line on every edge; any colour cast or tint (pink, purple, violet, warm yellow highlights, blue or violet shadows, cyan reflections); ambient, sky or environment light; directional sunlight and cast shadows (the game engine adds lighting); coloured glows or halos on anything that is not one of the model's own lights; black lines; text, numbers, logos that are not already in image 1; changing any shape; anything outside the silhouettes."""

NO_AMBIENT = """- NO ENVIRONMENT LIGHT: do not paint ambient, sky, sunset or bounce light or any coloured atmosphere. The ONLY light you may paint comes from a light source that is part of this model (listed below); every surface that is not that light keeps its base colour.
"""
LIGHTS = """- OWN LIGHTS ONLY: {lights}. Each light itself is bright: an almost-white core fading to its saturated colour at the rim, painted ON THE LIGHT ITSELF ONLY. Its light tints NO other surface (iron rule 0, 11-10: every object keeps its own base colour; light spill is the game engine's job). A light that is its own separate object (a strip, a lamp) is painted on that object only: on the wall behind it paint nothing of it - no halo, no second copy.
"""
NO_LIGHTS = """- This sheet has NO light sources: paint NO glow, halo or light tint anywhere.
"""
CARD = ("- IMAGE {k} is the approved design of this same object. Use it ONLY to see WHERE the brush blocks sit and how sparse they are. "
        "Do NOT take its shapes, layout, proportions, colours, tint, lighting or shadows; image 1 decides every shape and every colour.\n")
STYLE = ("- {imgs} brushwork reference from another game. Use {pron} only for the shape, size and spacing of the flat brush blocks "
         "and the chunky form, not for {pron2} colours, tint or lighting; take no shadows, environment colour or objects from {pron}. "
         "Image 1 decides every shape and every colour.\n")
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
    card = pr.get("card")
    cfgdir = os.path.dirname(os.path.abspath(sys.argv[1]))

    def resolve(c, what):
        c = c if os.path.isabs(c) else os.path.join(cfgdir, c)
        if not os.path.exists(c):
            sys.exit("%s not found: %s" % (what, c))
        return os.path.abspath(c).replace(os.sep, "/")

    def card_for(n):
        c = card.get(n) if isinstance(card, dict) else card
        return resolve(c, "prompt.card for " + n) if c else None
    refs = pr.get("style_refs") or []
    if isinstance(refs, str):
        refs = [refs]
    refs = [resolve(r, "prompt.style_refs") for r in refs]
    if pr.get("lights") or "glow" in (cfg.get("palette") or {}):
        lights = NO_AMBIENT + LIGHTS.format(lights=pr.get("lights") or LIGHTS_DEFAULT)
    else:
        lights = NO_AMBIENT + NO_LIGHTS
    extra = pr.get("extra", {})
    meta = json.load(open(os.path.join(W, "canvas", cfg["set"] + "_meta.json"), encoding="utf-8"))
    names, nref = [], set()
    for sh in meta["sheets"]:
        n = sh["name"]
        multi = MULTI if len(sh["tiles"]) > 1 else ""
        ex = extra.get(n, "")
        ex = ("- " + ex.strip().lstrip("- ") + "\n") if ex else ""
        c = card_for(n)
        refl = [W + "/canvas/" + n + ".png"] + ([c] if c else []) + refs
        nref.add(len(refl))
        pre = ""
        if c:
            pre += CARD.format(k=2)
        if refs:
            k0 = 3 if c else 2
            idx = list(range(k0, k0 + len(refs)))
            imgs = ("IMAGE %d is a" % idx[0]) if len(idx) == 1 else ("IMAGES " + ", ".join(map(str, idx)) + " are")
            pre += STYLE.format(imgs=imgs, pron="it" if len(idx) == 1 else "them",
                                pron2="its" if len(idx) == 1 else "their")
        ex = pre + ex
        txt = head(refl, n) + BODY.format(
            what=pr["what"], multi=multi, colors=pr["colors"], extra=ex, lights=lights)
        open(os.path.join(W, "p_%s.txt" % n), "w", encoding="utf-8", newline="\n").write(txt)
        names.append(n)
    os.makedirs(os.path.join(W, "img"), exist_ok=True)
    # LF only: xargs on Git Bash keeps the trailing \r of CRLF lines -> every job name breaks
    open(os.path.join(W, "joblist_%s.txt" % cfg["set"]), "w", newline="\n").write("\n".join(names) + "\n")
    if len(nref) > 1:
        sys.exit("prompt.card covers only some sheets: one ref count per set - give every sheet a card or none")
    N = nref.pop() if nref else 1
    open(os.path.join(W, "refcount_%s.txt" % cfg["set"]), "w", newline="\n").write("%d\n" % N)
    print("\n".join(names))
    print("refs per job (run_codex.sh last arg): %d" % N)


if __name__ == "__main__":
    main()
