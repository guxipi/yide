"""Step 2 · sol colour-pass prompt files.   py -3 po_prompts.py <cfg.json> <work_dir>

Finish = the CLEAN, NEW-LOOKING colour pass (勾哥 2026-11-04: J01 buildings and building parts use only this look;
standard images in vault `013 美术/丛林Lab/贴图风格基准/`). There is no weathered / brush-stroke mode any more.

Writes <work>/p_<sheet>.txt for every sheet in canvas/<set>_meta.json. References, in order:
  1   the canvas sheet itself (EDITED, layout kept)
  2-3 cfg.prompt.style_refs = the finish benchmark: 06 scene painting (full) + its guard-booth close crop
      (default: the two files in 贴图风格基准/; pass absolute paths if the vault sits on another drive)
  4   cfg.prompt.card (optional): this object's own approved scene painting / crop - read for colour layout only
Run each with:  bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh <work_dir> <sheet> <N>
N = number of references printed at the end (written to refcount_<set>.txt). 4 in parallel via xargs -P 4 inside ONE
run_in_background command; REJECT -> rerun once unchanged. After registration run color_lock (see 08).

cfg.prompt fields: what (what the sheet shows), colors (base colours to keep, e.g. "warm cream-beige shell #DCC8B3,
NEUTRAL grey frames #535556"), card + card_desc (optional), style_refs (optional, [full, crop]),
extra (optional dict sheet_name -> extra instruction lines, e.g. "the dark square is a closed metal hatch, NOT a window").
"""
import json
import os
import sys

VAULT_STD = "I:/My Drive/Obsidian/ExtractionRaider/01 - 星际拓荒重构/013 美术/丛林Lab/贴图风格基准"
DEFAULT_STYLE_REFS = [VAULT_STD + "/ref06_full.png", VAULT_STD + "/ref06_booth.png"]

BODY = """WHAT THIS IS: image 1 is a sheet of orthographic flat renders of 3D game models ({what}) laid out on a pure green #00FF00 background. It will be projected back onto the 3D models as their colour texture, so every pixel must stay where it is.{multi}

TASK: EDIT image 1 into a CLEAN, NEW-LOOKING stylized game texture. This is a colour pass on top of the existing render, not a redraw.
- Keep EVERY shape, edge, opening, gap, seam and the outer silhouette at EXACTLY the same pixel position and size. Same framing, same scale, no perspective change, no camera move, do not crop, do not add or remove any part, paint nothing outside the existing silhouette.
- Keep the background flat pure #00FF00 everywhere outside the models.
- Keep each part's base colour: {colors}. Greys are NEUTRAL grey, not blue, not violet.
{extra}
FINISH, exactly like the guard booth on the right side of image 2 (image 3 is a close crop of that booth):
- every panel and block is an almost flat, even colour with only ONE very large, very soft gradient: a touch lighter at its top, a touch darker toward its bottom;
- a thin, crisp, light highlight line along the top edges and convex corners of each block (the bevel catching light);
- neighbouring blocks / panels may differ very slightly in value, but each single block stays one clean tone;
- window glass: flat colour with one or two clean, straight, lighter diagonal reflection bands, like the booth window in image 2;
- safety stripes, light strips and screens are flat, clean colour bands with crisp edges;
- soft occlusion only in the tightest inner corners and right under overhangs, warm grey, very narrow.
{card}
AVOID (this matters most): brush strokes, painterly texture, visible strokes, mottling, blotches, noise, grain, chipped paint, scratches, scuffs, dents, dust, dirt, stains, streaks, drips, grunge, wear, rust, ageing of any kind; cool blue or violet shading; black lines or outlines; directional lighting, cast shadows, sun or sky light (the game engine adds lighting); text, numbers, logos; changing any shape; anything outside the silhouettes; any colour other than the base colours plus their slightly lighter and darker tones."""

MULTI = (" The sheet holds SEVERAL SEPARATE views laid out side by side; each view is one part seen straight on "
         "(some from the game camera angle, some from the side). Paint each view as its own object and keep the green gaps between them.")
CARD = ("\nImage 4 is {card_desc}: use it only to check which part gets which colour. Do NOT copy its brushwork, "
        "texture or any wear; the finish comes from images 2-3.\n")


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
    refs = list(pr.get("style_refs") or DEFAULT_STYLE_REFS)[:2]
    card = ""
    if pr.get("card"):
        refs.append(pr["card"])
        card = CARD.format(card_desc=pr.get("card_desc", "the approved scene painting of this same object"))
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
            what=pr["what"], multi=multi, colors=pr["colors"], extra=ex, card=card)
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
