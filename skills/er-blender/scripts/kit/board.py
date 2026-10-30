"""Side-by-side review board: reference | ours, one row per pair, label in each cell's top-left corner.

py -3 -I board.py <out.png> <cell_w> <label_a> <img_a> <label_b> <img_b> [<label_c> <img_c> <label_d> <img_d> ...]
Images are given in pairs per row (2 columns).
"""
import sys

from PIL import Image, ImageDraw, ImageFont


def font(sz):
    for f in ("C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(f, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def main(argv):
    out, cw = argv[0], int(argv[1])
    items = argv[2:]
    pairs = [(items[i], items[i + 1]) for i in range(0, len(items), 2)]
    rows = [pairs[i:i + 2] for i in range(0, len(pairs), 2)]
    cells = []
    for row in rows:
        r = []
        for label, path in row:
            im = Image.open(path).convert("RGB")
            h = round(im.height * cw / im.width)
            r.append((label, im.resize((cw, h), Image.LANCZOS)))
        cells.append(r)
    pad = 8
    row_h = [max(im.height for _, im in r) for r in cells]
    W = 2 * cw + 3 * pad
    H = sum(row_h) + pad * (len(cells) + 1)
    board = Image.new("RGB", (W, H), (40, 40, 48))
    d = ImageDraw.Draw(board)
    f = font(22)
    y = pad
    for r, rh in zip(cells, row_h):
        x = pad
        for label, im in r:
            board.paste(im, (x, y))
            tw = d.textlength(label, font=f)
            d.rectangle((x, y, x + tw + 16, y + 34), fill=(20, 20, 28))
            d.text((x + 8, y + 5), label, fill=(255, 255, 255), font=f)
            x += cw + pad
        y += rh + pad
    board.save(out)
    print(out, board.size)


if __name__ == "__main__":
    main(sys.argv[1:])
