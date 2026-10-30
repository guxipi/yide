"""Step 2 · sol paint-over prompt files.   py -3 po_prompts.py <cfg.json> <work_dir>

Writes <work>/p_<sheet>.txt for every sheet in canvas/<set>_meta.json. Each job has 4 references, in order:
  1 the canvas sheet itself (EDITED, layout kept)   2 cfg.prompt.card (approved concept painting of this thing)
  3-4 cfg.prompt.style_refs (in-game mo.co close-ups, opened and looked at before this run - red line 6)
Run each with:  bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh <work_dir> <sheet> 4
(4 in parallel via xargs -P 4 inside ONE run_in_background command; REJECT -> rerun once unchanged).

cfg.prompt fields: what (what the sheet shows), card (abs png), card_desc, style_refs [2 abs png],
colors (base colours to keep, e.g. "white shell #C6CFDD, slate frames #606F84"), marks (story marks, optional).
"""
import json
import os
import sys

BODY = """WHAT THIS IS: image 1 is a sheet of orthographic flat renders of 3D game models ({what}) laid out on a pure green #00FF00 background. It will be projected back onto the 3D models as their colour texture, so every pixel must stay where it is.{multi}

TASK: EDIT image 1 into a hand-painted texture. This is a paint-over, not a redraw.
- Keep EVERY shape, edge, opening, gap, seam and the outer silhouette at EXACTLY the same pixel position and size. Same framing, same scale, no perspective change, no camera move, do not crop, do not add or remove any part, paint nothing outside the existing silhouette.
- Keep the background flat pure #00FF00 everywhere outside the models.
- Keep each part's base colour: {colors}.

PAINT, in the hand-painted mobile-game finish of images 2-4:
- a soft tonal gradient inside every panel and block, a little lighter toward its top, a little cooler toward its bottom;
- a thin, soft, light painted highlight along convex edges, corners and panel tops;
- soft cool blue-violet painted occlusion in seams, inner corners, under ledges and along the ground line (the lowest half metre a little darker);
- gentle low-frequency brush mottling: a few large soft strokes per panel, small value change only;
- {marks}

REFERENCES: image 2 is {card_desc}: match its painted finish and edge treatment. Images 3 and 4 are in-game surfaces from the game mo.co: match their stroke size, softness and how edges catch light. Do NOT copy their content, colours or layout.

AVOID: directional lighting, cast shadows, sun or sky light (the game engine adds lighting); black lines or outlines; text, numbers, letters, logos; realistic or photographic texture; grain or noise; high-frequency detail; rust; changing any shape; anything outside the silhouettes; any colour other than the base colours plus their lighter and darker painted tones."""

MULTI = (" The sheet holds SEVERAL SEPARATE views laid out side by side; each view is one part seen straight on "
         "(some from the game camera angle, some from the side). Paint each view as its own object and keep the green gaps between them.")
MARKS = ("a few small story marks, sparse: chipped paint on some corners and edges, faint scuffs and vertical dust streaks, "
         "a little dirt at the base.")


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
    refs = [pr["card"]] + list(pr["style_refs"])[:2]
    for r in refs:
        if not os.path.exists(r):
            sys.exit("missing reference: " + r)
    meta = json.load(open(os.path.join(W, "canvas", cfg["set"] + "_meta.json"), encoding="utf-8"))
    names = []
    for sh in meta["sheets"]:
        n = sh["name"]
        multi = MULTI if len(sh["tiles"]) > 1 else ""
        txt = head([W + "/canvas/" + n + ".png"] + refs, n) + BODY.format(
            what=pr["what"], multi=multi, colors=pr["colors"], marks=pr.get("marks", MARKS), card_desc=pr["card_desc"])
        open(os.path.join(W, "p_%s.txt" % n), "w", encoding="utf-8").write(txt)
        names.append(n)
    os.makedirs(os.path.join(W, "img"), exist_ok=True)
    # LF only: xargs on Git Bash keeps the trailing \r of CRLF lines -> every job name breaks
    open(os.path.join(W, "joblist_%s.txt" % cfg["set"]), "w", newline="\n").write("\n".join(names) + "\n")
    print("\n".join(names))


if __name__ == "__main__":
    main()
