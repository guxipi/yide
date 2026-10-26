"""Pull painted skin and hair back to the approved design's tone (10-08 Rook: Tripo/sol drifted skin brighter and
more orange, hair lighter). Multiplies value/saturation inside soft hue-sat-value masks. Use the SAME parameters on the
body basecolor and the face atlas, otherwise the neck shows a seam.
usage: py -3 tone_grade.py in.png out.png [--skin-v 0.92 --skin-s 0.88] [--hair-v 0.82 --hair-s 0.95] [--mask m.png]
Measure first (crop_compare.py --hsv): target / current median V and S give the factors."""
import argparse
import numpy as np
from PIL import Image
ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst')
ap.add_argument('--skin-v',type=float,default=.92); ap.add_argument('--skin-s',type=float,default=.88)
ap.add_argument('--hair-v',type=float,default=.82); ap.add_argument('--hair-s',type=float,default=.95); ap.add_argument('--mask')
a=ap.parse_args()
img=Image.open(a.src); alpha=img.getchannel('A') if img.mode=='RGBA' else None
im=np.asarray(img.convert('RGB')).astype(np.float32)/255
r,g,b=im[...,0],im[...,1],im[...,2]; mx=im.max(-1); mn=im.min(-1); d=mx-mn+1e-6; s=d/(mx+1e-6)
h=np.where(mx==r,((g-b)/d)%6,np.where(mx==g,(b-r)/d+2,(r-g)/d+4))*60
def ramp(x,a0,a1): return np.clip((x-a0)/(a1-a0),0,1)
warm=ramp(h,4,9)*(1-ramp(h,34,40))
skin=warm*ramp(s,.30,.38)*(1-ramp(s,.78,.86))*ramp(mx,.50,.60)          # lit and mid skin
hair=warm*ramp(s,.30,.38)*(1-ramp(mx,.50,.58))*ramp(mx,.12,.18)          # dark warm browns (hair, skin core shadow)
vf=1+(a.skin_v-1)*skin+(a.hair_v-1)*hair; sf=1+(a.skin_s-1)*skin+(a.hair_s-1)*hair
v2=np.clip(mx*vf,0,1); s2=np.clip(s*sf,0,1)
c=v2*s2; x=c*(1-np.abs((h/60)%2-1)); z=v2-c; k=(h//60).astype(int)%6
rgb=np.zeros_like(im)
for i,(R,G,B) in enumerate([(c,x,0*c),(x,c,0*c),(0*c,c,x),(0*c,x,c),(x,0*c,c),(c,0*c,x)]):
    sel=k==i; rgb[...,0][sel]=R[sel]; rgb[...,1][sel]=G[sel]; rgb[...,2][sel]=B[sel]
rgb+=z[...,None]
if a.mask: Image.fromarray((np.stack([skin,hair,0*skin],-1)*255).astype(np.uint8)).save(a.mask)
out=Image.fromarray((np.clip(rgb,0,1)*255+.5).astype(np.uint8))
if alpha is not None: out.putalpha(alpha)
out.save(a.dst); print('skin px',int((skin>.5).sum()),'hair px',int((hair>.5).sum()))
