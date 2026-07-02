---
name: planet-dressing
description: Turn an Extraction Campaign greybox room map into a production-grade ("成品级") planet-themed environment — walls become cliffs/terrain, floors get planet palettes, rooms get props, all with the Whiteout-Survival / Stealth-Master "通透感" (open diorama readability) and a Brawl-Stars saturated toon look. Trigger on "把灰盒换成星球地貌" / "地图穿衣服" / "关卡环境美化" / "星球主题环境" / "dress the map" / "换成品环境" / "把墙换成悬崖/建筑" or any task theming a Campaign greybox map to shippable visual quality. Battle-tested on Map_CampaignDungeon → Verdance (翠垣星) with Synty ScifiWorlds + ToonLit. Gameplay layer is READ-ONLY (walls/RoomVolume/Barrier/navmesh untouched); visuals are one idempotent re-runnable "Dressing" node. Companion to campaign-map-build (builds the greybox this skill dresses) and gaoguang-3d (single-model look-fix; THIS skill is whole-map dressing).
---

# 星球地貌 Dressing · Extraction（灰盒 → 成品级星球环境）

把「勾哥给房间路线灰盒 → 一键换成该星球主题的成品级环境」做成可复读流水线。
**核心原则：gameplay 层与视觉层彻底分离** —— 灰盒（墙碰撞 / RoomVolume / RoomBarrier / navmesh / spawn 标记）只读不改；视觉全部挂 `Dressing` 单节点 + 墙关 renderer + 地板换材质。重跑 = 删 Dressing 重摆，改路线后一分钟出新环境，永不出现"美术摆完不敢动路线"死锁。

> 工具落点：Extraction `Assets/Editor/CoplayTemp/PlanetDresser.cs`（dresser 本体，幂等）+ `DressPreview.cs`（scene-view 取景截图）。上游灰盒契约见 `campaign-map-build`；单模型去灰见 `gaoguang-3d`；Play 验证见 `playmode-verify-iterate`。

## 1. Theme Kit（每星球一份，人策划一次，算法消费）
成品感 80% 来自 curation 不来自算法。每星球定义:
- **边界件 Cliffs**：悬崖/大岩（SM_Env_Cliff_Flat/Rough、Rock_Large）— 视觉表达碰撞墙
- **低矮件 LowRocks**：小岩石（Rock_01..08）— 专给相机侧(南向)墙,不挡视线
- **中型件 MediumProps**：植物群/水晶/大花 — 房间边带
- **小件 SmallDecor**：草/小花 — 房内散布,无碰撞可穿行
- **远景件 FarScatter**：大螺旋树/尖塔/高气球树 — 地图外环带
- **材质 4-6 个**：ground(房间)/path(走廊)/outer(外圈)/cliff/foliage/crystal,全部 `Custom/ToonLit`
- Tripo 只补 kit 缺的 **hero 地标件**(星球专属大物件),不用它铺量——风格不稳,铺多必脏

## 2. 通透感硬规则（Whiteout Survival / Stealth Master 拆解,写死进算法)
1. **边界视觉连续**：隐形碰撞墙在哪,悬崖脊就在哪(step≈3.4m,贴墙外推 1.6-2.6m)——玩家不能撞看不见的空气墙;但**宁疏勿密**,别糊死
2. **相机侧(南向外)墙一律低矮件**(≤2.4m 高)——俯视相机从南往北看,南墙高崖会遮玩家
3. **尺寸归一化**：按目标世界尺寸反算 scale(量 prefab bounds 缓存)。边界件按 **Footprint**(4.2-6m),props 按 **MaxDim**(不是 Height!扁宽件如大花按高度归一宽度会爆炸 3 倍)
4. **一星球一主色调+一 accent**：Verdance=草绿底+薰衣草紫岩+青蓝 emission 植物;走廊路面换暖 tan 色,路线引导免费拿到
5. **全部 dressing 件剥 Collider** → RuntimeNavMeshBake(PhysicsColliders) 结果与灰盒完全一致,玩法零影响
6. gameplay 净空:spawn/extraction/scientist/门口 barrier 坐标列 KeepClear,半径 2.2-3.5m 不摆件
7. Barrier 门禁别留裸灰块,换主题能量墙材质(亮青 toon)

## 3. Synty → Brawl Stars 观感(材质层,三个必踩的坑)
1. **🔴 EnvTriplanar 死于 URP 17**:Synty 大地形件(Cliff/Ground/Rock_Large)用 `SyntyStudios/EnvTriplanar`,本项目下渲染成纯白/纯黑。**全部换 ToonLit 纯色块**——正好更贴 Brawl Stars(干净色块+描边)
2. **🔴 植物的鲜艳色来自 _EMISSION**:Synty 科幻植物 albedo 本体是深褐,青蓝发光全靠 emission 贴图(Textures/Emissive)。ToonLit 原本不支持 → **已加 `_EmissionMap`/`_EmissionColor`**(黑图默认=无副作用)。remap 时把原材质的 emission 贴图+颜色一起搬过来,否则植物全是黑巧克力
3. **环境 toon 参数别抄角色**:角色那套重阴影(threshold 0.746)会把环境压灰。环境配方:`_ShadowThreshold ≈0.32`、`_ShadowColor (0.66,0.62,0.74)`、`_AmbientStrength 0.5`、地面 outline=0、小件 outline≤2
4. **🔴 matte 铁律(勾哥 2026-07-02 拍板)**:Brawl Stars/Whiteout Survival 质感 = 高饱和固有色 + **零高光零 rim** + 柔阴影。环境材质 **`_RimColor` alpha 必须 = 0**(rim 项乘零关死)——白 rim 在石头上读作"高光/荧光感",是环境显塑料的头号元凶;emission 也别开满,植物 ≈0.55×、水晶 ≈0.65× 原厂色,够点缀不荧光。地面绿往深里压一档(如 (0.28,0.62,0.30))比荧光绿(0.30,0.66,0.33)更"厚"
- 材质做成资产存 `Assets/Art/Materials/PlanetKits/<Planet>/`,dressing 层实例上 sharedMaterials 替换;**不改 Synty 包本体**(红线)

## 4. 流程
1. 读灰盒尺寸(墙 transform dump):房间 bounds/墙高/走廊宽/标记坐标 → KeepClear 表
2. 建/复用 kit 材质(§3 配方) → 风格小样先过一眼(几件 + LightSet + Hero 对照,场景 additive 建在远处,拍完整场景关掉不保存)
3. 跑 dresser:墙关 renderer→悬崖脊;地板换 ground/path;房间边带 props+内部小件;外圈大地台(-0.65)+远景环带;barrier 换能量墙材质
4. `SaveAsPrefabAsset` 回原 prefab —— config 零改动(LevelConfig 还指同一张图)
5. scene-view 全图+逐房截图自检(通透?边界连续?体量对?) → 迭代参数重跑(幂等)
6. Play 验证(Boot 起跑→DriveLoad):看真游戏相机,`[RuntimeNavMeshBake] baked`、玩家能跑、房间触发正常

## 5. Play 验证的坑(这次全踩过)
- **Play 中绝不写/改 Assets 下的 .cs**(domain reload→重启回 Boot→主线程卡死 MCP 全超时)。Play 中要临时脚本 → 写**项目根 `Temp/`**(不进资产管线,安全),用完删
- DriveLoad 必须等 HomeScreen transition complete 之后发,发早了会被 Boot 启动导航覆盖(现象:LevelRoot 都 resolve 了又弹回 HomeScreen)
- HomeScreen 的 meta 弹窗(UILoginRewardPanel 等)是 DontDestroyOnLoad,会盖在 GameScene 截图上,先 SetActive(false)
- 巡场拍图别裸传送:战斗房传进去几秒就被打死。**warp+清怪+回血+`Time.timeScale=0` 一次调用做完**,拍完 timeScale=1;分两次调用必有竞态
- editor 卡死时 stop_game 会排队,连发后用 get_unity_editor_state 轻探,等它消化;测完必 stop(铁律)

## 6. 收尾
- 改动面只应有:地图 prefab、PlanetKits 材质、(首次)ToonLit shader 的 emission 三处、CoplayTemp 工具;字体 SDF .asset 是 Play 动态图集自动 dirty,不算
- 不 commit 不 push(红线);向勾哥交付截图(scene-view 全图 + 游戏相机逐房)

## 边界
- 只管"给灰盒穿衣服";灰盒本身/路线设计 → `campaign-map-build`;Campaign 玩法代码不碰
- 品阶越高房间越多 = 重跑 dresser 即可;新星球 = 新 kit(材质+件表) + 同一个 dresser
