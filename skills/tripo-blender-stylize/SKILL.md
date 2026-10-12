---
name: tripo-blender-stylize
description: Take a Tripo-generated 3D model from "AI 肉感/塑料感/细碎噪点/low quality" to Extraction’s mo.co painted toon standard (smooth chunky forms, clean painted colour areas, NO faceting, NO outline) — Tripo prompt recipe + Blender clean-up pipeline + Unity intake handoff. Upstream of gaoguang-3d. Trigger on "tripo 模型精修" / "blender 处理模型" / "模型肉感" / "模型太高模/太碎" / "tripo 怎么生成才好看" / "stylize this model". NOT for in-Unity fixes alone — normals-only "肉感" often needs NO Blender (importer normals 就够), check first.
---

# Tripo → mo.co 风格化流水线（Tripo prompt / Blender 精修 / Unity 交接）

**目标水准和验收以 ER 美术规范为准**:vault `01 - 星际拓荒重构/013 美术/ER美术规范.md`(对标 mo.co 游戏内画面的质量和质感,2026-10-11 起取代旧的 Brawl Stars / Synty 低模口径),建筑道具植被看它第 7 节。读起来要是**平滑饱满的大形体 + 大块干净色面 + 两阶明暗 + 没有写实高光**,3D 世界里看不到黑描边。

**结果禁区**(总纲红线和参考资料第 7 节):画面上读出硬刻面、低多边形感(玩家能数出面就是失败)、flat shaded、写实材质纹理、细碎凹凸,任何一项都打回。旧版本这份 skill 让 prompt 写 `low poly, flat shaded, faceted` 并在 Blender 里 Shade Flat,那套已作废,别照旧笔记做。

下面三层是验证过的一种做法,不是唯一做法;别的路线也行,结果过总纲门槛即可。AI 模型(Tripo)默认输出 = 高模平滑 + PBR 贴图 → "肉感/塑料感"。修复分三层,**从便宜的做起**:

## 0. 先试零成本层:Unity importer(多数"肉感"到这就好了)
Tripo 的软塌感多半来自法线,不是网格本身。先在 Unity 里:
- ModelImporter → `importNormals = Calculate`,smoothing angle 从大往小试,**以截图看不出多边形面为准**(减过面的模型角度太小会出刻面,这是禁区)
- 材质走 `gaoguang-3d`(ToonLit remap,矿塔案例:材质早就对了,纯法线问题)
- 底部融合差 → 给件加土色底盘 + 低岩环(原 planet-dressing 的 FoundationRing 思路;该 skill 已随战役退役)
**只有剪影/面数/比例本身不行,才进 Blender。**

## 1. Tripo 生成侧:prompt 就把风格钉住
- **常用正向关键词**:`stylized cartoon game asset, smooth rounded chunky forms, large clean colour areas, simple two-tone painted shading, minimal surface texture, mobile game asset`
- **反向排除**:`low poly, faceted, flat shaded, hard facets, black outline, realistic, high detail, PBR, weathered, greebles, noisy texture`(细碎凹凸 = 肉感之源,刻面 = 画风禁区)
- 比例口径:矮胖 > 瘦高(顶视角识别),大形体 2-3 个就够,别让它堆小细节
- 出图先看**剪影缩略图**:顶视角认不出的直接重 roll,别指望后期救
- 角色不走这份 skill:角色从定稿设计图到游戏走 `er-character-pipeline`(四视图 → Tripo → 绑骨 → 入库),长相和头身以角色手册为准

## 2. Blender 精修(blender-mcp 驱动,Claude 直接执行)
> 前置:Blender 装 blender-mcp addon 并连上(https://github.com/ahujasid/blender-mcp,`uvx blender-mcp` + addon 里 Connect)。会话里没有 mcp__blender__* 工具就先让勾哥开 Blender+Connect。

对每个 Tripo 模型(GLB/FBX)常用这五步,全部可用 execute code 驱动(顺序和参数按模型调,不是死流程):
1. **Decimate 减面**:Modifier `DECIMATE` ratio 起手 0.1(道具目标 800-3000 面);剪影垮了就升到 0.2。**面数只为预算服务,不是画风**——减完必须靠第 2 步把面藏住
2. **Shade Smooth**:全模型 `shade_smooth`(配 auto smooth / weighted normal),只在真正的结构转折处留硬边。这步决定"看不看得出多边形",看得出就回头调
3. **Bevel 大边**:Modifier `BEVEL` width 8-15%(视觉元素做法库 mo.co 岩石条)、segments 1-2——边缘圆润不刀刻,剪影变 chunky 圆润(mo.co 岩石/道具 = 大倒角块状体)
4. **色彩归并**:扔掉 AI 自带的 PBR 贴图和纹理噪点。每块东西的固有色控制在两三个以内(总纲红线和参考资料第 7 节),体积靠"顶部亮、底部暗"的渐变(顶点色写 world-Y AO)和边缘提亮出,不靠纹理。可以烘一张小调色板贴图(每个色块一格,UV 挪进对应格子),Unity 侧 ToonLit 直接吃
5. **导出**:Apply 所有 modifier → 原点放**底部中心**(省 Unity 侧 pivot 补偿) → FBX(`apply transform`, Z-up→Y-up 自动) → 落 `Assets/Art/3DModelsfromGu/<Name>/`

## 3. Unity 交接(→ gaoguang-3d)
- 进项目走 `gaoguang-3d`:ToonLit remap(matte:rim alpha=0)+ LightSet 真光验证
- importer 法线按 §0 设,以看不出刻面为准
- 是地图 hero 件 → 加底盘 / 岩环种进地里(远征地编走 vault 016 的施工手册)
- 描边:结果要求是 3D 世界里看不到黑描边(角色也一样,总纲红线第 1 条);用 ToonLit 的话 `_OutlineWidth` 显式设 0(新建材质默认 1.5 纯黑)

## 判断表:走哪条路
| 症状 | 路径 |
|---|---|
| 肉感/软塌但剪影 OK | §0 importer 法线,不进 Blender |
| 灰暗/塑料高光 | gaoguang-3d 材质 remap |
| 看得出刻面/多边形 | §0 加大 smoothing angle,不行再 §2 第 2 步 |
| 面数过高/剪影糊/比例差 | §2 Blender 五步 |
| 表面细碎噪点、像写实贴图 | §2 第 4 步色彩归并 |
| 跟地面像"摆上去的" | 加土色底盘 / 低岩环,或埋低一点 |
| 生成侧就丑 | §1 重写 prompt 重 roll,别硬修 |
