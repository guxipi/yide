"""Chroma-key a flat #00FF00 object render into RGBA with edge despill (W4 10-27 version).

usage: py -3 key.py in.png out.png
Thresholds spill 90..170 are tight on purpose: looser keys turn mint #22C8A8 parts semi-transparent.
"""
import sys
import numpy as np
from PIL import Image, ImageFilter

src = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(np.float32)
r, g, b = src[..., 0], src[..., 1], src[..., 2]
spill = g - np.maximum(r, b)
a = 1.0 - np.clip((spill - 90.0) / (170.0 - 90.0), 0, 1)
alpha = Image.fromarray((a * 255).astype(np.uint8))
alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
edge = np.asarray(alpha, dtype=np.float32) < 250
g2 = np.where((spill > 0) & edge, np.maximum(r, b), g)
out = np.dstack([r, g2, b, np.asarray(alpha, dtype=np.float32)]).clip(0, 255).astype(np.uint8)
Image.fromarray(out, 'RGBA').save(sys.argv[2])
