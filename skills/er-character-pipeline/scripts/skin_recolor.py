"""Lighten / de-yellow skin in a painted albedo with a soft hue-sat-value mask.
usage: py -3 skin_recolor.py in.png out.png [--sat 0.45] [--lift 0.35] [--hue -4] [--mask mask.png]"""
import sys, argparse
import numpy as np
from PIL import Image
ap=argparse.ArgumentParser(); ap.add_argument('src'); ap.add_argument('dst'); ap.add_argument('--sat',type=float,default=.45)
ap.add_argument('--lift',type=float,default=.35); ap.add_argument('--hue',type=float,default=-4); ap.add_argument('--mask')
a=ap.parse_args()
img=Image.open(a.src); alpha=img.getchannel('A') if img.mode=='RGBA' else None
im=np.asarray(img.convert('RGB')).astype(np.float32)/255
r,g,b=im[...,0],im[...,1],im[...,2]; mx=im.max(-1); mn=im.min(-1); d=mx-mn+1e-6; s=d/(mx+1e-6)
h=np.where(mx==r,((g-b)/d)%6,np.where(mx==g,(b-r)/d+2,(r-g)/d+4))*60
def ramp(x,a0,a1): return np.clip((x-a0)/(a1-a0),0,1)
# skin: orange hue 8..38, mid saturation, not dark
m=ramp(h,4,10)*(1-ramp(h,34,42))*ramp(s,.32,.40)*(1-ramp(s,.66,.74))*ramp(mx,.50,.62)
if a.mask: Image.fromarray((m*255).astype(np.uint8)).save(a.mask)
h2=(h+a.hue*m)%360; s2=s*(1-(1-a.sat)*m); v2=mx+(1-mx)*a.lift*m
c=v2*s2; x=c*(1-np.abs((h2/60)%2-1)); z=v2-c; k=(h2//60).astype(int)%6
rgb=np.zeros_like(im)
for i,(R,G,B) in enumerate([(c,x,0*c),(x,c,0*c),(0*c,c,x),(0*c,x,c),(x,0*c,c),(c,0*c,x)]):
    sel=k==i; rgb[...,0][sel]=R[sel]; rgb[...,1][sel]=G[sel]; rgb[...,2][sel]=B[sel]
rgb+=z[...,None]
out=Image.fromarray((np.clip(rgb,0,1)*255+.5).astype(np.uint8))
if alpha is not None: out.putalpha(alpha)
out.save(a.dst)
print('skin px', int((m>.5).sum()), 'mean before', (im[m>.5].mean(0)*255).round(), 'after', (np.clip(rgb,0,1)[m>.5].mean(0)*255).round())
