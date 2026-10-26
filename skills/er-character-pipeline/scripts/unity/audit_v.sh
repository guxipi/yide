#!/usr/bin/env bash
# usage: audit.sh <outname> [prefab]   renders all Rook clips + knee metrics, builds board
U=/c/Users/kryst/.claude/skills/er-character-pipeline/scripts/unity/ucli.sh; T=/c/Users/kryst/character-art-lab/tools/rook2
O=C:/Users/kryst/character-art-lab/out/rook2-tripo/unity/$1; rm -rf $O; mkdir -p $O
A=Assets/Art/3DModelsfromGu/0_Characters/Rook2/Animations; R=${CLIPDIR:-Assets/Art/3DModelsfromGu/0_Characters/Rook/Anims}
CL=${CLIPS:-"$A/Rook2_Anims.fbx#Rook_Guard;$A/Rook2_Anims.fbx#Rook_Boxer;$A/Rook2_Anims.fbx#Rook_HeadScratch;$A/Rook2_Anims.fbx#Rook_ArmsCross;$A/Rook_Salute3.anim;$R/Rook_Idle.fbx;$R/Rook_Walk.fbx;$R/Rook_Run.fbx;$R/Rook_Hit.fbx;$R/Rook_Death.fbx;$R/Rook_ExtractWin.fbx;$R/Rook_ExtractFail.fbx"}
bash $U eval $T/leg_audit_v.cs VIEW=${VIEW:-front} PREFAB=${2:-Assets/Art/3DModelsfromGu/0_Characters/Rook2/Rook2.prefab} CLIPS="$CL" OUT=$O N=${N:-6} | tee $O/metrics.txt
cd $O; PYTHONIOENCODING=utf-8 py -3 -c "
import glob,os
from PIL import Image,ImageDraw
names=sorted(set(os.path.basename(f).rsplit('_',1)[0] for f in glob.glob('*.png')))
n=int('${N:-6}'); W,H=180,270
b=Image.new('RGB',(n*W+150,len(names)*H),(30,30,30)); d=ImageDraw.Draw(b)
for r,nm in enumerate(names):
  d.text((4,r*H+120),nm,fill=(255,255,0))
  for k in range(n): b.paste(Image.open(f'{nm}_{k}.png').resize((W,H)),(150+k*W,r*H))
b.save('../$1_board.png')"
