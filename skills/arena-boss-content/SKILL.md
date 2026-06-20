---
name: arena-boss-content
description: How to ADD a new arena boss in Extraction and wire it into the difficulty pyramid — the repeatable content pipeline on top of the already-built boss/difficulty foundation. Trigger on "加个新 boss" / "新关卡 boss" / "第 N 关 boss" / "做丛林星球的 boss" / "接 boss 到难度系统" / "boss 接难度" / "new arena boss" / "add a boss" / "wire boss to difficulty" or any task adding/placing a boss into a wave + difficulty. Covers the 7-step flow (model → EnemyConfig → prefab → archetype → wave → difficulty wire → verify), how campaignIndex hooks the Difficulty Hub, the three-layer rule (Hub=multiplier / EnemyConfig=base / archetype=which skills), and the pitfalls. Orchestrates gaoguang-3d (model) + playmode-verify-iterate (verify). NOT for changing the difficulty/pyramid foundation itself — that's already built; this is content-addition only.
---

# 新 arena boss 接入 + 难度 Hub wire（Extraction）

把"加一只新关卡 boss"做成可复读的标准流水线。**地基已建好**（boss 技能池/随机 moveset + 难度金字塔 + 数值 Hub，见代码库 `HANDOVER_Boss_Difficulty.md`、Obsidian 人话版 `Boss 系统背后 moveset抽卡设计` / 技术版 `Boss系统_开发交接(技术版)`）。**本 skill 只管"加内容"，不动地基。**

> 子步骤编排：模型走 `gaoguang-3d`，收尾验证走 `playmode-verify-iterate`。

---

## 第〇步：先记死三层别混（最重要）
| 层 | 改它 = 改什么 | 在哪 |
|---|---|---|
| **难度层** | "这关/段/波多难"（倍率 ×） | Difficulty Hub / DifficultyModel |
| **base 层** | "这只 boss / 这招本身多强"（绝对值） | EnemyConfig / 技能 prefab |
| **内容层** | "这局抽哪些招" | archetype（BossSkillPoolConfig） |

spawn 那一刻合体：`最终 = base × 倍率`。**别在两层调爆同一个值**（boss 太肉先看是 EnemyConfig 底子还是 Hub 倍率，别两边都拉）。

---

## 接入 7 步 flow

### ① 模型
boss FBX 进项目 → **走 `gaoguang-3d` skill** 修材质/轴心/动画（ToonLit 去灰、pivot 居中、配 Animator controller，真光照下验）。

### ② EnemyConfig（底子）
建该 boss 的 `EnemyConfig.asset`（`Assets/ScriptableObjects/Actors/Enemies/`）：`_maxHealth`、`_moveSpeed`、`_enemyName`、`_detectionRange`、`_attackInterruptible`(boss 建议 false=超甲)、`_experienceReward` 等。**这是 base 绝对值，Hub 倍率会乘在上面。**

### ③ boss prefab
**复制 `Boss_HeavyCommander.prefab` 当模板最快**，然后：
- 换模型子物体（①的）+ 改 Animator controller
- `EnemyUnit._config` 指向 ②的 EnemyConfig
- 确认挂着：`BossController` + `BossMovesetRandomizer` + Health/Unit/NavMeshAgent/AIController/TargetDetector/UnitAnimator/HitFeedback
- **不焊技能**（技能从 archetype 池运行时实例化）；`BossController._phases` 留空（运行时 SetMoveset 注入）

### ④ 指派 / 建 archetype（打法）
- **复用**现有 archetype：`Archetype_{Bruiser,Artillery,Trickster,Berserker}.asset`，或
- **新建**：右键 Create ▸ Gameplay ▸ Boss Skill Pool Config，列它的技能 prefab（`Assets/Prefabs/Enemies/Boss/Skills/`，现 10 招）+ 设 `RequireMeleeAndRanged`（纯近/纯远的套关掉）
- `BossMovesetRandomizer._skillPools`：**放 1 套 = 固定打法（叙事 boss 推荐）**；放多套 = 局局随机换打法

### ⑤ 排进 wave
把 boss prefab 放进该关对应 boss 轮的 `WaveConfig`（如 `ArenaXX_W10/20/30/40/50` 的 enemy 条目，count 1）。每段末（第 10 波）是 boss 轮。

### ⑥ wire 难度 Hub
- `ArenaConfig._difficultyModel` 指向难度模型（现 `DifficultyModel_Arena01`）、`_campaignIndex` = **这关在 campaign 曲线上第几号**（现只 1 关 = 0；加新关递增）。
- 在 **Tools ▸ Difficulty Hub** 调这关/这段的难度——boss 的 HP/伤害/技能数/出招间隔**自动按金字塔派生**（`关 × 段 × 波 × 角色权重`）；要某只 boss 特调 → Hub 那段加 override。
- **加了新关（CampaignCount 变大）**：把 `CampaignDifficultyCurve` 的 X 范围（末 anchor）拖到新关号——X 轴是实际格数，与数量耦合。

### ⑦ 验证
**走 `playmode-verify-iterate` skill**：进 arena 看 boss spawn + HP/伤害缩放 + moveset 随机。避雷见下。

---

## 必避的坑
- **三层别混**：见第〇步，别两层调爆同一值。
- **campaignIndex 别忘设**（默认 0，多关时各 arena 设各自号）。
- **同机制、不同数值的招 = 换 prefab/archetype，不写代码**；只有**全新机制**的招才写新 `BossAttackBase` 子类（参考现有 10 招：近 GroundSlamShockwave/WhirlwindSpin/LeapSlam/DashLunge/MeleeSweep、远 RadialBurst/HomingOrbs/MortarVolley/ProjectileBarrage/MeteorStrike）。
- **活体测 boss 别反射跳波次**——会 race `EnemySpawnService` 的协程波状态机（destroy 敌人触发"波完成"撞车）。要么自然玩到 boss 轮，要么用"不碰波状态机"的 harness（如临时 bump GlobalDifficultyScale 让早波小怪当场缩放给看）。
- **Play 中别 Write 新 .cs**——触发重编译会踢出 Play。进 play 前把驱动脚本写好，play 中只 execute 现有文件。
- **新 AoE 近战招 `_hitLayerMask` 默认 Everything**：production 收紧到 Player+Enemy 层（性能/精度）；当前靠 `IsHostileTo` 过滤友伤，功能正确。
- **boot 有 cloud 403 时**：进 play 等 ~20s 再操作；`SceneTransitionService.Instance` 要 boot 完才有。进 arena = `GameModeContext.CurrentMode=WaveSurvival` + `SceneTransitionService.Instance.LoadGameSceneAsync(ArenaProvider.DefaultArena)`。

---

## 关键文件速查
- boss 模板：`Assets/Prefabs/Enemies/Boss/Boss_HeavyCommander.prefab`
- 技能 prefab：`Assets/Prefabs/Enemies/Boss/Skills/Skill_*.prefab`
- archetype：`Assets/ScriptableObjects/WaveSurvival/Archetype_*.asset`
- 难度模型：`Assets/ScriptableObjects/WaveSurvival/DifficultyModel_Arena01.asset`（Hub 编辑它）
- 接线代码：`BossMovesetRandomizer.cs`、`DifficultyModel.cs`(含 Resolver/ArenaDifficultyContext)、`WaveSurvivalController.cs`(每波 SetWave)、`EnemyUnit.ApplyConfig`、`ArenaConfig.cs`(_difficultyModel/_campaignIndex)
- 工具：Tools ▸ Difficulty Hub（`DifficultyHubWindow.cs`）

## 收尾
- 按铁律：玩家可见改动 → `playmode-verify-iterate` 真测到位再交。
- 内容资产改完即存盘；boss prefab / SO 改完确认落盘。
- 算"推进 ER 产品"（新 boss 内容是玩家可见），可记一笔战绩。
