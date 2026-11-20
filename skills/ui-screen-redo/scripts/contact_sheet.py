# usage: py -3 contact_sheet.py <dir containing r2shots/n*.png>  -> <dir>/r2_sheet.png (5 columns, labelled) for a one-look review of every state.
import sys, glob, os
from PIL import Image, ImageDraw
SP=sys.argv[1]; fs=sorted(glob.glob(SP+'/r2shots/n*.png')); W,H=300,650; cols=5; rows=(len(fs)+cols-1)//cols
S=Image.new('RGB',(cols*W,rows*(H+20)),(230,230,238)); d=ImageDraw.Draw(S)
for i,f in enumerate(fs):
    im=Image.open(f).convert('RGB').resize((W,H)); x=(i%cols)*W; y=(i//cols)*(H+20); S.paste(im,(x,y+20)); d.text((x+4,y+4),os.path.basename(f),fill=(0,0,0))
S.save(SP+'/r2_sheet.png'); print(S.size)
