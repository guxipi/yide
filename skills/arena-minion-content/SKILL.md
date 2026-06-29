---
name: arena-minion-content
description: How to ADD a campaign's small enemies (小怪/minions — NOT bosses) in Extraction via the model-injection decoupling system — the repeatable content pipeline on the already-built BaseEnemy/EnemyConfig foundation. Trigger on "加小怪" / "做XX关的小怪" / "换皮敌人" / "把这几个模型做成小怪" / "接小怪到波次" / "new arena enemy" / "add minion" / "reskin enemy" or any task adding/skinning small enemies into a campaign's waves. Covers model→archetype mapping by silhouette, the 3 animation paths, the injection-surgery converting archetype prefabs, wave intro-cadence wiring, and the pitfalls (Tripo Z-up, inherited DefaultWeapon, pool skin-bleed). Orchestrates gaoguang-3d + playmode-verify-iterate. NOT for bosses (→ arena-boss-content) nor the difficulty foundation; content-addition only.
---

# 关卡小怪接入（模型注入解耦）· Extraction

把"给一个 campaign 做一套小怪/换皮"做成可复读流水线。**地基已建好**：BaseEnemy + EnemyConfig **模型注入解耦**（换皮 = 换 config，行为代码零改）+ 段难度金字塔。**本 skill 只管加内容，不动地基、不碰 boss。**

> 编排：模型 intake 走 `gaoguang-3d`；收尾验证走 `playmode-verify-iterate`；动画 3 路径细节见记忆 `enemy-model-animation-pipeline`。

## 系统怎么运作（先懂这个）
- **BaseEnemy.prefab** = 纯逻辑壳（Health/AI/Attack/EnemyUnit/NavMeshAgent…）+ 一个空 **ModelRoot**；UnitAnimator/HitFeedback 常驻 ModelRoot。
- **EnemyConfig** 持模型数据：`_modelPrefab` / `_animatorController` / `_weaponMountBonePath` / `_modelScaleOverride` / `_modelLocalOffset`(轴心补偿) / `_modelLocalEuler`(朝向修正)。
- 运行时 `EnemyUnit.InjectModel()` 把 `_modelPrefab` 实例化到 ModelRoot，自动重连 animator/renderer/武器挂点；`_modelPrefab==null` 走旧版(模型焊 prefab)路径，向后兼容。
- **换皮 = 复制一份 EnemyConfig，改名字 + `_modelPrefab` + 朝向/缩放/挂点；行为一字不改。**
- **行为原型** = 现有 prefab：Assault(基础近战)/Brute(重甲超甲)/Charger(冲锋,带 ChargeBehavior)/Bomber(自爆,带 ExplodeOnDeath)/Lobber(迫击远程)/Bee(飞行远程)。复用的就是它们的 EnemyUnit + 行为组件。

## 一关准备几个 + 节奏
- **4-5 个小怪/关**（业界推荐；含一个飞行远程如蜜蜂补维度）。
- 介绍节奏：前 5 波**每波首发一个新脸** → 6-9 波混搭升级 → 第 10 波 boss(不归你)。后段靠混搭 + tint 变体撑新鲜，**别真做 50 个模型**。

## 流程（每只怪）
1. **剪影配原型**：按 appeal 选——胖/硬壳→Brute、瘦快/人形→Assault、有翼/悬浮→Bee/Lobber、圆滚→Charger、能炸/菌伞→Bomber、生根植物→Lobber(固定)。覆盖近战/重甲/远程/冲锋/自爆几槽，威胁不重样。
2. **intake**（→ gaoguang-3d）：ToonLit remap + 轴心 + 绑定。动画按 3 路径(见记忆)：人形 retarget(套 HeroAnimationController) / Generic 自带 clip 循环 / 程序化(EnemyProceduralMotion)。
3. **建注入式 prefab**：
   - 原型 = Assault → BaseEnemy 已是注入式，直接做变体 + 换 config。
   - 原型 = Brute/Charger/Bomber/Lobber（老式焊死模型）→ **注入手术**：InstantiatePrefab → UnpackCompletely → 删模型子物体(humanoid=`Robot_One` / Lobber=`Bee`) → 建 ModelRoot → CopyComponent UnitAnimator+HitFeedback 到 ModelRoot → 清 HitFeedback._renderers → 清硬值(Health/AI/Melee/NavAgent.speed) → 接 `_modelRoot` + `_config` → SaveAsPrefabAsset 到**新路径**（**绝不动原型 prefab**）。模板：Extraction `Assets/Editor/CoplayTemp/BuildRainforestBatch.cs`。
4. **配 config**：拷原型 config → 改 `_enemyName` + `_modelPrefab` + scale/offset/euler + 挂点；**`DefaultWeapon` 置空**(除非真要带武器，见坑②)。
5. **接波次**：WaveConfig `_enemies` 加 entry（EnemyPrefab=新 prefab，清 `EnemyPrefabRef.m_AssetGUID` 走 legacy，MinCount/MaxCount，SpawnDelay，SpawnChance=1，SpawnSlots 各 RandomRadius≈2.5 防叠）。**只动 W1-W9，W10 boss 波不碰**。改前备份波次。
6. **验证**（→ playmode-verify-iterate）：进 arena 真跑——每波新脸、行为对、池复用不串皮、无报错。Play 里 execute_script 可驱动(`UIHomeScreenPanel.SelectGameMode(WaveSurvival)`→点 `PlayButton`)，但 **Play 期间绝不写 .cs**(重编译卡死 Coplay 桥)。

## 必记的坑（血泪）
1. **Tripo 常 Z-up → 模型躺平**：单看正面会被深度骗(像站着)，**必须侧面渲染**核对；bounds 宽>高 = 躺；修 `_modelLocalEuler=(-90,0,0)`，旋转后**重算** `_modelLocalOffset` 让它接地居中。
2. **拷来的 config 继承 `DefaultWeapon`**：reskin 近战怪会平白在 ModelRoot 挂出原型的武器模型(螃蟹挂了 Brute 的刀)。**reskin 一律置空**(去武器会丢武器伤害加成，知会数值 owner)。
3. **Generic FBX 实例化默认不带 Animator**：要 `avatarSetup=CreateFromThisModel` 才带；用它自带 clip 还要 `clipAnimations[].loopTime=true` + 单 state controller。
4. **池化串皮**：靠 OnDespawn `DestroyCurrentModel` + InjectModel 开头先清。**别在同一个 ModelRoot 上同时用 EnemyProceduralMotion.Bob 和 HitFeedback shake**（抢 localPosition）；Spin(rotation)安全。
5. **别碰 boss**：你是做小怪的——W10、Boss prefab、ArenaDifficultyConfig 一律不动(→ `arena-boss-content`)。误碰了要忠实还原。
6. **三层别混**(同 boss skill)：难度层(Hub 倍率×) / base 层(EnemyConfig 绝对值) / 内容层(哪些怪)。**数值是难度 session 的活**，你只管"接得上 + 行为对"。
7. **多 session 协同**：DifficultyModel/EnemyUnit 等是共享文件，另一个 session 可能 commit 把你的改动卷走；动前 pull，commit **只 stage 自己的文件**，**别 `git add -A`** 把别人的脏改动/包 meta 删除一起提交。
8. **要保留复用的 builder/工具脚本写 `Assets/Editor/CoplayTemp/`**（如本 skill 的批量注入/接线脚本，留作工具）。一次性探针/dump 脚本才写项目根 `Temp/yide_*.cs`（无 domain reload、跑完删）——按生命周期分，别混。

## 关键文件
- 系统：`EnemyUnit.cs`(InjectModel) / `EnemyConfig.cs`(模型字段) / `BaseEnemy.prefab` / `EnemyProceduralMotion.cs`
- 原型：`Assets/Prefabs/Enemies/Humanoid/HumanoidEnemy_*.prefab`、`RangedEnemy_Lobber.prefab`、`RangedBee.prefab`；configs `Assets/ScriptableObjects/Actors/Enemies/Enemy_*.asset`
- 波次：`Assets/ScriptableObjects/WaveSurvival/Waves/Arena01_W*.asset`、`Arena_TestArena.asset`
- 工具模板(CoplayTemp)：`BuildRainforestBatch.cs` / `WireRainforestWaves.cs` / `InjectTestBatch.cs` / `RenderBatch.cs` / `ClearDebtCrab.cs`(自带clip循环) / `PiranhaFix.cs`(朝向修正)
