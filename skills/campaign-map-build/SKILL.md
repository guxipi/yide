---
name: campaign-map-build
description: How to BUILD a Campaign planet/room map for Extraction that LevelManager can load and ExplorationPhaseController can drive — a walled greybox (or art) dungeon prefab honoring the room-graph contract. Trigger on "建关卡地图" / "做星球地图" / "建房间地图" / "灰盒地图" / "新关卡场景" / "搭一张图" / "换张地图" / "每个星球不同地图" / "build campaign map" / "greybox dungeon" / "room map" / "new planet map" or any task authoring/replacing the map a Campaign run plays on. Covers the prefab CONTRACT (LevelRoot + PlayerSpawnPoint + RoomGraphAuthoring + RoomVolume/RoomBarrier + navmesh), the programmatic builder recipe (rooms + walls + door gaps + corridors + carving barriers), how it plugs into CampaignConfig/Phase1ExplorationConfig, and the three hard-won traps (magenta materials, prefab navmesh won't register, OpenScene fake-null). Each planet = its own map asset, ZERO code changes. Companion to playmode-verify-iterate (verify). NOT the Campaign gameplay code itself (that's already built) — this is map-asset authoring only.
---

# Campaign 关卡地图搭建 · Extraction

把"给一颗星球做/换一张地图"做成可复读流水线。**Campaign 玩法代码已建好且地图无关**：`CampaignRunController`/`ExplorationPhaseController` 从「当前加载的那张图」上读 `RoomGraphAuthoring`，所以**每颗星球 = 一张自己的地图 prefab，加新图零代码改动**。本 skill 只管「产出一张合规的地图 prefab 并接进 CampaignConfig」。

> 编排：地图几何若要真美术模型走 `gaoguang-3d`；收尾验证走 `playmode-verify-iterate`。Campaign 架构全貌见记忆 `campaign-refactor-progress`。

## 地图 prefab 的「契约」（必须挂齐，否则跑不起来）
LevelManager 加载 prefab、ExplorationPhaseController 驱动它，依赖这套组件：
1. **`LevelRoot`**（prefab 根）—— 提供 spawn；它按名自动解析名为 **`PlayerSpawnPoint`** 的子物体（摆在起始房 R1）。
2. **`RoomGraphAuthoring`**（根）—— `StartRoomId`（起始房，通常 R1，prep 无怪）。运行时自动收集子级所有 RoomVolume/RoomBarrier（含 inactive）。
3. 每个房间一个 **`RoomVolume`**（带 BoxCollider isTrigger）+ `RoomId`（**必须与 `Phase1ExplorationConfig` 的 `RoomDefinition.RoomId` 对上**）。房间检测靠它的 world bounds(XZ)。
4. 每道门一个 **`RoomBarrier`**（`FromRoomId`/`ToRoomId`）—— 实体 cube(物理挡玩家=no-backtrack) + `NavMeshObstacle`(shape=Box, carving=true, size=1 即满体积)。**初始 SetActive(false)=开**；控制器进房封后门/前门、清空开门。
5. **navmesh**（见坑②）。

## 它怎么接进 Campaign
- 一个 `LevelConfig`（`_handcraftedMode=true`，`_levelPrefab`=地图 prefab）→ `CampaignConfig.SharedMap`。
- `Phase1ExplorationConfig._rooms`：每个 RoomId 一条 `RoomDefinition`（Kind=Prep/Combat/Boss + 敌人组）。Boss-kind 房清空 → `OnBossDefeated` → 决断节点。
- Phase2 守矿复用 `ArenaConfig`（同一张图，不重载）。

## 三大坑（都踩过，照修）
1. **🔴 地板/墙渲染成品红**：`new Material()` 运行时建的材质赋给 prefab cube → 不是资产 → prefab 引用丢失 → "缺失材质粉"。**必须 `AssetDatabase.CreateAsset(mat, path.mat)` 存成资产**再赋值。
2. **🔴 "Failed to create agent because there is no valid NavMesh"**：prefab 里预烤的 NavMeshData **不能可靠存活 prefab 管线**，实例化时不注册（连玩家 agent 都建失败）。**程序化/灰盒地图**：挂运行时组件 `Gameplay.Campaign.RuntimeNavMeshBake`（Awake 调 `NavMeshSurface.BuildNavMesh`，surface `collectObjects=Children`+`useGeometry=PhysicsColliders`）→ 实例化即烤。**真美术地图**：正常预烤 NavMeshData（去掉该组件）。注意运行时烤比玩家 spawn 晚约 1s，有几条启动期警告，玩家随即恢复，可忽略。
3. **🔴 OpenScene fake-null**：editor 脚本里 `OpenScene(Single)` 会把刚 `CreateAsset` 的 SO 当「未使用资产」卸载 → 之前 load 的引用变 Unity fake-null（赋值进场景 = null）。**在 OpenScene 之后重新 `LoadAssetAtPath` 一次**再 wire 进场景组件。

## 流程
1. **搭几何**（程序化最快）：矩形房（floor cube + 4 面墙，门方向留 G≈6 宽门缝）+ 走廊连接 + 门口 barrier。线性北进或带分支（分支 = 一个房有 2+ 条出边 RoomBarrier）。脚本模板：Extraction `Assets/Editor/CoplayTemp/CampaignMapBuilder.cs`（3 房 R1prep/R2combat/R3boss，含墙/门缝/走廊/barrier/RoomVolume/RoomBarrier/LevelRoot/PlayerSpawnPoint/NavMeshSurface+RuntimeNavMeshBake，一键 SaveAsPrefabAsset 并回填 LevelConfig）。
2. **挂契约组件**（见上）；材质走资产（坑①）。
3. **存 prefab**：`PrefabUtility.SaveAsPrefabAsset`；OpenScene 前后注意 fake-null（坑③）。
4. **接配置**：LevelConfig→CampaignConfig.SharedMap；Phase1ExplorationConfig 的 RoomId 与 RoomVolume 对齐。
5. **品阶越高房间越多**（设计口径）：高阶星球多摆几间 + 加分支，graph 引擎照吃；别真做几十张独立图，复用几何 + tint/敌人组变体撑量。
6. **验证**（→ playmode-verify-iterate）：从 **Boot** 起跑（不经 Boot → 无 SceneTransitionService → 进不去），HomeScreen→Campaign→逐房清怪→boss→决断。日志看 `[RuntimeNavMeshBake] baked`、`[ExplorationPhaseController] Entered/cleared`、无 "no valid NavMesh"。

## 边界
- 不改 Campaign 玩法代码（已建好）；只产出地图资产 + config 接线。
- CoplayTemp 下的 builder 脚本是 editor 工具，保留复用；地图 prefab 落生产目录（如 `Assets/Prefabs/Campaign/`）。
