import sys, os
from PIL import Image, ImageDraw
# usage: contact.py out.jpg img1 img2 ...
out = sys.argv[1]; paths = sys.argv[2:]
W, H, cols = 480, 300, 4
rows = (len(paths)+cols-1)//cols
sheet = Image.new("RGB", (W*cols, (H+18)*rows), "white")
d = ImageDraw.Draw(sheet)
for i,p in enumerate(paths):
    im = Image.open(p).convert("RGB"); im.thumbnail((W-6,H-6))
    x, y = (i%cols)*W, (i//cols)*(H+18)
    sheet.paste(im, (x+3, y+18))
    d.text((x+4,y+3), f"{i+1}. {os.path.basename(p)[:60]} {Image.open(p).size}", fill="black")
sheet.save(out, quality=80)
print(out, sheet.size)
