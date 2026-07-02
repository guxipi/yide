---
name: tripo-blender-stylize
description: Take a Tripo-generated 3D model from "AI 肉感/高模平滑/low quality" to Extraction's Brawl-Stars chunky low-poly toon standard — the Tripo prompt recipe, the Blender (via blender-mcp) hard-surface stylize pipeline (decimate → flat shade → bevel silhouette → palette), and the Unity intake handoff. Trigger on "tripo 模型精修" / "blender 处理模型" / "模型肉感" / "模型太高模/太圆滑" / "tripo 怎么生成才好看" / "stylize this model" / "把模型改成低多边形" or any task cleaning up an AI-generated model to match the game's faceted toon look. Downstream of model generation, upstream of gaoguang-3d (Unity intake: ToonLit remap/pivot/verify). NOT for in-Unity material fixes alone — normals-only "肉感" often needs NO Blender at all (importer Calculate+30° 就够), check that first.
---

# Tripo → Brawl Stars 风格化流水线（Tripo prompt / Blender 精修 / Unity 交接）

目标观感 = Brawl Stars / Synty:**低面数硬面 + 圆润大剪影 + 高饱和平色 + 零高光**。
AI 模型(Tripo)默认输出 = 高模平滑 + PBR 贴图 → "肉感/塑料感"。修复分三层,**从便宜的做起**:

## 0. 先试零成本层:Unity importer(多数"肉感"到这就好了)
Tripo 的软塌感 80% 来自 **smooth normals**,不是网格本身。先在 Unity 里:
- ModelImporter → `importNormals = Calculate` + `normalSmoothingAngle 30°`(20°更碎/45°更圆)
- 材质走 `gaoguang-3d`(ToonLit remap,矿塔案例:材质早就对了,纯法线问题)
- 底部融合差 → `planet-dressing` 的 FoundationRing(土色底盘+低岩环)
**只有剪影/面数/比例本身不行,才进 Blender。**

## 1. Tripo 生成侧:prompt 就把风格钉住(每次生成都用)
- **必带关键词**:`low poly, flat shaded, faceted, hard edges, stylized cartoon prop, chunky proportions, vibrant flat colors, mobile game asset`
- **反向排除**:`realistic, high detail, PBR, weathered, greebles`(细碎凹凸=肉感之源)
- 比例口径:矮胖 > 瘦高(顶视角识别),大形体 2-3 个就够,别让它堆小细节
- 出图先看**剪影缩略图**:顶视角认不出的直接重 roll,别指望后期救
- 贴图选项有 "texture/no texture" 时:**风格化道具选纯色/简单贴图**,复杂 PBR 贴图后面全要扔

## 2. Blender 精修(blender-mcp 驱动,Claude 直接执行)
> 前置:Blender 装 blender-mcp addon 并连上(https://github.com/ahujasid/blender-mcp,`uvx blender-mcp` + addon 里 Connect)。会话里没有 mcp__blender__* 工具就先让勾哥开 Blender+Connect。

对每个 Tripo 模型(GLB/FBX)标准五步,全部可用 execute code 驱动:
1. **Decimate 减面**:Modifier `DECIMATE` ratio 起手 0.1(道具目标 800-3000 面);剪影垮了就升到 0.2。大平面多的用 Planar 模式(angle 8-12°)更干净
2. **Shade Flat + Auto Smooth**:`shade_flat` 全模型 → 需要局部圆润(球/管)加 auto smooth angle 30°。这步直接决定"硬面感"
3. **Bevel 大边**:Modifier `BEVEL` width 0.02-0.05、segments 1-2、angle limit 40°——低面数下边缘不刀刻,剪影变"chunky 圆润"(Brawl Stars 的关键:大形体圆、面片平)
4. **色彩归并**:扔掉 PBR 贴图。要么 vertex color 分块填色,要么烘一张 **16-64px 调色板贴图**(每个色块一格,UV 全部挪进对应格子)——高饱和平色,Unity 侧 ToonLit 直接吃
5. **导出**:Apply 所有 modifier → 原点放**底部中心**(省 Unity 侧 pivot 补偿) → FBX(`apply transform`, Z-up→Y-up 自动) → 落 `Assets/Art/3DModelsfromGu/<Name>/`

## 3. Unity 交接(→ gaoguang-3d / planet-dressing)
- 进项目走 `gaoguang-3d`:ToonLit remap(matte:rim alpha=0)+ LightSet 真光验证
- importer 仍设 Calculate+30°(Blender 已 flat 的话此步无害,双保险)
- 是地图 hero 件 → `planet-dressing` 的 FoundationRing 种进地里
- 描边:ToonLit `_OutlineWidth` 按体量调(大件 2-4,角色 20 口径是 KayKit 体量)

## 判断表:走哪条路
| 症状 | 路径 |
|---|---|
| 肉感/软塌但剪影 OK | §0 importer 法线,不进 Blender |
| 灰暗/塑料高光 | gaoguang-3d 材质 remap |
| 面数过高/剪影糊/比例差 | §2 Blender 五步 |
| 跟地面像"摆上去的" | planet-dressing FoundationRing |
| 生成侧就丑 | §1 重写 prompt 重 roll,别硬修 |
