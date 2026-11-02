# A1 · 联邦主干道人行道地砖 + 地缘砖(J01 v7,2026-11-02 勾哥过)

## 要模仿的外形(自然语言,建之前先写这段)
- **地砖(1.1 m 方板)**:近方形,边长 1.05–1.14 m、长宽差 ≤3%;四条边不是直线,每边微弓 0.5–1.5% 边长,沿边 2–3 处 ±0.5–1 cm 的小起伏;四角各不相同:直角、3–6 cm 切角、3–5 cm 圆角、6–9 cm 缺一口,每块至少两种;厚 0.15 m,顶面平,顶边 1.5 cm 软圆角(不直切、不鼓),侧壁直;顶面一个平色 + 极淡大块起伏(±4%),块间只差 ±2%;板与板缝 2 cm,缝底比板深一阶、不是沟。
- **地缘砖(0.55 × 0.37 m)**:长方小块,尺寸差 ±5%,同样的弓 / 起伏 / 角型;厚 0.15,顶面与地砖齐;**朝车道的长边是打磨出来的大圆肩(R 6 cm,约高度四成)**,其余三条棱硬;立面比顶面深一档;一列沿路缘,块与块缝 2 cm。
- **铺法**:正交不错缝、不转向;每块 ±1° / ±1 cm;缺角只在块上,不缺整块;缝板不露边(地缘砖侧缩 2.5 cm)。
- **质感在光里不在砖上**:平色 + 几何缝 + 阴影 + 极淡起伏;无笔触、无颗粒、无黑描边(mo.co 口径)。

## 唯一参考
`Claude Feature Docs/Jungle Planet/BIBLE/lineup/pipeline/refs/moco_street_crosswalk.png` 裁 480,0,641,300(勾哥 11-02「认定唯一参考图」)。屏幕目标色与本色见 `kit.json`。

## 重建(别的机器没有资产时)
项目仓(任一 worktree)打开 Unity 后:
```
unity cmd script eval --port <端口> -- "Lab.J01v7.Editor.A1KitGen.Build(); return \"ok\";"
```
或菜单 `Tools/Lab/J01v7/A1 人行道砖套件 重建`。产物 `Assets/Art/Lab/J01v7/A1/{Meshes,Textures,Materials,Prefabs}` + `A1_kit.json`;SHA 对照 `kit.json` 的 `assets`。

## 铺开(一小段街道 / 走廊两侧)
```
python -X utf8 "Claude Feature Docs/Jungle Planet/BUILD/J01_v7/gen/export_kerb_lines.py"
unity cmd script eval_file --port <端口> -- --file "Claude Feature Docs/Jungle Planet/BUILD/J01_v7/engine/A1/a1_pave_capture.cs"
```
第一步从 `j01_v7_base.py` 导走廊两侧地缘砖线(世界坐标 + 高程 + 朝车道法线);第二步沿线铺 prefab(地缘砖一列 + 地砖两列 + 缝板)并 V5 实拍。

## 维护
改套件 = 同回合更新本目录 `kit.json`(含资产 SHA)+ 本 README + 项目 `Assets/Scripts/Editor/Lab/J01v7/A1KitGen.cs`;翼德仓 commit + push,项目仓 commit 不 push。
