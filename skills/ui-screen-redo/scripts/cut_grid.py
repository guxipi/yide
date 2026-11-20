# usage: py -3 cut_grid.py <3x3 grid png on white> <out_dir> <name1,...,name9>
# Cuts a 3x3 icon board drawn on pure white with thick dark outlines: flood-fills white from every cell border (the outline protects inner whites), crops, pads, saves 160px transparent webp.
import sys
from PIL import Image, ImageDraw
src, out, names = sys.argv[1], sys.argv[2], sys.argv[3].split(',')
im = Image.open(src).convert('RGB'); W, H = im.size; cw, ch = W/3, H/3
for i, n in enumerate(names):
    r, c = divmod(i, 3)
    cell = im.crop((int(c*cw), int(r*ch), int((c+1)*cw), int((r+1)*ch))).convert('RGBA')
    w, h = cell.size
    # flood fill from every border pixel that is near-white
    px = cell.load(); seen = bytearray(w*h); stack = []
    for x in range(w):
        stack += [(x,0),(x,h-1)]
    for y in range(h):
        stack += [(0,y),(w-1,y)]
    while stack:
        x, y = stack.pop()
        if x<0 or y<0 or x>=w or y>=h: continue
        k = y*w+x
        if seen[k]: continue
        R,G,B,A = px[x,y]
        if min(R,G,B) < 225: continue
        seen[k] = 1; px[x,y] = (255,255,255,0)
        stack += [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]
    bb = cell.getbbox()
    ic = cell.crop(bb); s = max(ic.size); pad = int(s*0.04)
    sq = Image.new('RGBA', (s+2*pad, s+2*pad), (0,0,0,0)); sq.paste(ic, ((s-ic.size[0])//2+pad, (s-ic.size[1])//2+pad))
    sq.resize((160,160), Image.LANCZOS).save(f'{out}/{n}.webp', 'WEBP', quality=88, method=6)
print('ok', len(names))
