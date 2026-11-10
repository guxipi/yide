# -*- coding: utf-8 -*-
"""ER 生图铁规 0 · 发单前工单检查(11-10 勾哥:「生图的时候主体什么颜色就是什么颜色,绝对不要做出,例如灯光使得 F 类楼体是淡紫灰这种事情,强制执行」
「仅仅是 F 类楼体吗?」「减少粉色,紫色的使用,这个主要是男生玩的游戏」)。

查每张出图工单(codex / sol / terra 的 prompt 文本):
  1. 必须有「全部物体本色」段:含 BASE COLOUR ONLY 且写到 every object / each part(不是只写楼体)。
  2. 不许出现让光给物体上色的说法:lavender / purple-grey / glow halo / light tints / tinted shadows / colour grading / sunset …
     (同一句里有 no / never / not / without 的否定句放行)。
  3. 有风格参考(范本 / 方向图 / mo.co 帧)时,必须写明「只学形 / 材质 / 质感,不学它们的光和颜色」。
  4. 楼体 / 屋顶 / 大面积不许用粉 / 紫 / 品红 / 丁香。
退出码 0 = 全过;1 = 有违规(逐条打印,不发单)。
python prompt_lint.py p_*.txt
"""
import re
import sys
from pathlib import Path

BAD = [r"lavender", r"purple[- ]grey", r"pale purple", r"violet tint", r"glow halo", r"\bhalos?\b", r"glow on the surfaces", r"soft coloured glow",
       r"light tints", r"tinted shadows?", r"shadow tint", r"colou?r grading", r"sunset", r"golden hour", r"warm light wash", r"colou?r cast toward",
       r"ambient carr(y|ies) a", r"colou?r comes from the (glowing|light)", r"pastel pink", r"coral[- ]pink"]
NEG = re.compile(r"\b(no|not|never|without|nor|don't|do not|must not|forbidden|avoid)\b", re.I)
PINK_BODY = re.compile(r"\b(pink|purple|violet|lilac|lavender|magenta|mauve)\b[^.\n]{0,40}\b(wall|walls|body|bodies|roof|roofs|facade|building|block|slab)\b"
                       r"|\b(wall|walls|body|bodies|roof|roofs|facade|building|block)\b[^.\n]{0,30}\b(pink|purple|violet|lilac|lavender|magenta|mauve)\b", re.I)
STYLE_REF = re.compile(r"(heroes|dir[DF]_|moco_|style referen)", re.I)
REF_ONLY_SHAPE = re.compile(r"(only|solely)[^.\n]{0,60}(shape|form|material|finish)[^.\n]{0,80}(not|never)[^.\n]{0,40}(light|colou?r|tint)", re.I)
BASE = re.compile(r"BASE COLOU?R ONLY", re.I)
EVERY = re.compile(r"\b(every|each) (object|part|piece|thing)", re.I)


def sentences(t):
    return re.split(r"(?<=[.!?;:])\s+|\n", t)


def lint(path):
    t = Path(path).read_text(encoding="utf-8")
    errs = []
    if not BASE.search(t) or not EVERY.search(t):
        errs.append("缺「全部物体本色」段(要有 BASE COLOUR ONLY 且写 every object / each part,不能只写楼体)")
    for s in sentences(t):
        low = s.lower()
        if NEG.search(low):
            continue
        for b in BAD:
            if re.search(b, low):
                errs.append(f"让光 / 色调给物体上色:「{s.strip()[:120]}」")
                break
        if PINK_BODY.search(s):
            errs.append(f"楼体 / 屋顶 / 大面积用粉紫:「{s.strip()[:120]}」")
    if STYLE_REF.search(t) and not REF_ONLY_SHAPE.search(t):
        errs.append("用了风格参考但没写明「只学形 / 材质 / 质感,不学它们的光和颜色」")
    return errs


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    files = [f for a in sys.argv[1:] for f in (sorted(Path().glob(a)) if any(c in a for c in "*?[") else [Path(a)])]
    if not files:
        print(__doc__); sys.exit(2)
    bad = 0
    for f in files:
        e = lint(f)
        if e:
            bad += 1
            print(f"✗ {f}")
            for x in dict.fromkeys(e):
                print("   -", x)
        else:
            print(f"✓ {f}")
    print(f"{len(files) - bad}/{len(files)} 过铁规 0")
    sys.exit(1 if bad else 0)
