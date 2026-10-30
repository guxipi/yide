"""Contact sheet: py -3 grid.py <out.png> <cols> <cell_w> <label> <img> [<label> <img> ...]"""
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
    out, cols, cw = argv[0], int(argv[1]), int(argv[2])
    items = [(argv[i], argv[i + 1]) for i in range(3, len(argv), 2)]
    ims = []
    for label, path in items:
        im = Image.open(path).convert("RGB")
        ims.append((label, im.resize((cw, round(im.height * cw / im.width)), Image.LANCZOS)))
    ch = max(im.height for _, im in ims)
    rows = (len(ims) + cols - 1) // cols
    pad = 6
    board = Image.new("RGB", (cols * cw + (cols + 1) * pad, rows * ch + (rows + 1) * pad), (40, 40, 48))
    d = ImageDraw.Draw(board)
    f = font(20)
    for i, (label, im) in enumerate(ims):
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + pad)
        board.paste(im, (x, y))
        tw = d.textlength(label, font=f)
        d.rectangle((x, y, x + tw + 14, y + 30), fill=(20, 20, 28))
        d.text((x + 7, y + 4), label, fill=(255, 255, 255), font=f)
    board.save(out)
    print(out, board.size)


if __name__ == "__main__":
    main(sys.argv[1:])
