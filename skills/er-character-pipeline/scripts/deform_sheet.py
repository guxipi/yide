"""Contact sheet + 2x stressed-region crops of the rig deformation renders (rig_build.py deform/ folder).

usage: py -3 deform_sheet.py --dir RIG_OUT/deform --out RIG_OUT/deform_sheet.png --crops RIG_OUT/deform_crops.png
The crops are what you actually judge: open deform_crops.png at full size. Look for
  arms_overhead: no black spikes from backpack/straps, shoulder volume kept
  arms_forward_90 / elbows_bent_120: no sleeve shards, elbow bends at the elbow
  deep_squat / running_stride: boot shaft and thigh stay joined, skirt hem closed, no black/white stripes
  torso_twist_35 / head_turn_40: no torn seams at neck/waist
  chains_outward_40: the WHOLE hair mass swings, scalp stays put
  skirt_lift_30: smooth hem, not saw-toothed
A "pass" written in any report is not evidence; these two images are.
"""
import argparse
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import os

from PIL import Image, ImageDraw, ImageFont

CROPS = {
    "arms_overhead": ("threequarter", (256, 120, 768, 632), "backpack + shoulder"),
    "arms_forward_90": ("threequarter", (190, 230, 702, 742), "armpit + shoulder"),
    "elbows_bent_120": ("front", (256, 220, 768, 732), "elbows + shoulders"),
    "deep_squat": ("threequarter", (240, 380, 752, 892), "hips + knees + boots"),
    "running_stride": ("threequarter", (220, 350, 732, 862), "thigh + knees + boots"),
    "torso_twist_35": ("threequarter", (256, 250, 768, 762), "torso seams"),
    "head_turn_40": ("threequarter", (256, 40, 768, 552), "neck + head"),
    "chains_outward_40": ("front", (180, 40, 692, 552), "hair chains"),
    "skirt_lift_30": ("threequarter", (256, 260, 768, 772), "skirt hem"),
}


def font(sz):
    try:
        return ImageFont.truetype("arial.ttf", sz)
    except OSError:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crops", required=True)
    a = ap.parse_args()
    poses = [p for p in CROPS if os.path.exists(os.path.join(a.dir, f"{p}_front.png"))]
    if not poses:
        raise SystemExit("no deform renders found in " + a.dir)
    f = font(24)
    sheet = Image.new("RGB", (1024, len(poses) * 512), (18, 18, 18))
    d = ImageDraw.Draw(sheet)
    for r, p in enumerate(poses):
        for c, v in enumerate(("front", "threequarter")):
            im = Image.open(os.path.join(a.dir, f"{p}_{v}.png")).convert("RGB").resize((512, 512), Image.LANCZOS)
            sheet.paste(im, (c * 512, r * 512))
            d.text((c * 512 + 10, r * 512 + 10), f"{p} / {v}", font=f, fill="white")
    sheet.save(a.out)
    rows = (len(poses) + 1) // 2
    qa = Image.new("RGB", (2048, rows * 1080), (14, 14, 14))
    d = ImageDraw.Draw(qa)
    for i, p in enumerate(poses):
        v, box, lab = CROPS[p]
        im = Image.open(os.path.join(a.dir, f"{p}_{v}.png")).convert("RGB").crop(box).resize((1024, 1024), Image.NEAREST)
        x, y = (i % 2) * 1024, (i // 2) * 1080
        qa.paste(im, (x, y))
        d.text((x + 12, y + 1030), f"{p} - {lab} - 2x", font=f, fill="white")
    qa.save(a.crops)
    print("sheet", a.out)
    print("crops", a.crops)


if __name__ == "__main__":
    main()
