"""Contact sheet of the face-swap QA renders + 2x crops of the eye band for every closed-eye expression.

usage: py -3 face_qa_sheet.py --config char.json --qa RIG_DIR/face_qa [--proj FACE_DIR/face_projection.json]
Writes <qa>/../face_swap_qa.png. Look at it at full size:
  neutral: no seam ring where the face material meets the head; eyes/mouth on the right geometry;
  closed-eye cells (blink/half/happy/ko...): ZERO white sclera / lash / old-mouth pixels left at eye corners;
  3/4 view: no hair paint smeared on forehead/cheeks; full_front/top70: still reads from the game camera.
"""
import argparse
import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _cfg import load_cfg, out_path  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--qa", required=True)
    ap.add_argument("--proj")
    a = ap.parse_args()
    cfg = load_cfg(a.config)
    proj = json.load(open(a.proj or out_path(cfg, cfg["files"].get("face_dir", "face"), "face_projection.json"), encoding="utf-8"))
    ex = cfg["face"]["expressions"]
    names = [(f"{e['id']}_{v}", f"{e['id']} / {v}") for e in ex for v in ("front", "threequarter")] + [("full_front", "full"), ("top70", "top70")]
    th, lh, cols = 320, 28, 6
    rows = (len(names) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * th, rows * (th + lh)), (20, 20, 24))
    d = ImageDraw.Draw(sheet)
    for i, (fn, lab) in enumerate(names):
        p = os.path.join(a.qa, fn + ".png")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("RGB")
        im.thumbnail((th, th))
        x, y = (i % cols) * th, (i // cols) * (th + lh)
        sheet.paste(im, (x, y))
        d.text((x + 6, y + th + 6), lab, fill=(240, 240, 240))
    b = proj["feature_bands"]["eyes_brows"]
    crops = []
    for e in ex:
        if e.get("eyes_closed"):
            p = os.path.join(a.qa, f"{e['id']}_front.png")
            if os.path.exists(p):
                c = Image.open(p).convert("RGB").crop(tuple(b))
                crops.append((e["id"], c.resize((c.width * 2, c.height * 2), Image.NEAREST)))
    ch = sum(c.height + lh for _, c in crops)
    out = Image.new("RGB", (max(sheet.width, max((c.width for _, c in crops), default=0)), sheet.height + ch), (20, 20, 24))
    out.paste(sheet, (0, 0))
    d = ImageDraw.Draw(out)
    y = sheet.height
    for e, c in crops:
        out.paste(c, (0, y))
        d.text((6, y + c.height + 4), f"{e} eyes 2x", fill=(240, 240, 240))
        y += c.height + lh
    op = os.path.join(os.path.dirname(os.path.abspath(a.qa)), "face_swap_qa.png")
    out.save(op)
    print("sheet", op)


if __name__ == "__main__":
    main()
