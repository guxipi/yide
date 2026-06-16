---
name: vfx-production
description: Build production-quality ("成品级") 3D / world-space VFX in Extraction — drops, pickups, auras, bursts, on-character effects, projectile/impact FX — to shippable premium-mobile quality. The VFX counterpart to ui-visual-rework (that one = screen-space uGUI; THIS one = world particles/meshes/shaders/motion). Trigger on "做XX视效/特效" / "vfx 太cheap" / "重做掉落/拾取/光效" / "成品级 vfx" / "加个爆开/光环/拖尾/命中特效" / "把 EpicToon 用起来" / "3D 视觉重做" or any request to author or polish in-world visual effects. NOT for fixing an imported model's OWN look (grey/material/pivot/rig) — that's gaoguang-3d; this skill is world particles/meshes/shaders/motion only. Covers the asset-reuse-vs-custom choice, the runtime color-tint pipeline + alpha trap, pooling, the hover/pop/breath/burst motion language, and on-player feedback (body glow + world→screen rising icons).
---

# VFX Production (Extraction · EpicToon + URP)

把"一坨色块/软光团"的世界特效做到上线级精品。这是 `ui-visual-rework` 的 3D/VFX 对偶面 —— UI 那套是 screen-space uGUI(材质底纹+DOTween 飘窗),**本 skill 是世界空间的粒子/网格/材质/动效**,方法论与坑都不同。

> 信条:**先盘资产再动手;能改色复用就别自建;泡泡/壳子用 mesh 求清晰,光晕/爆开用粒子求生动;动效叠在静态视觉之上;静态先在 edit mode 看,运动+反馈再进 play 看。**

---

## 第〇步:方法论差异(为什么不能照搬 UI 那套)

| 维度 | UI 视效(ui-visual-rework) | **世界 VFX(本 skill)** |
|---|---|---|
| 媒介 | Image/TMP + sliced sprite + 底纹 | ParticleSystem + mesh + 透明/叠加材质 + emission |
| 上色 | sprite 自带色 / Image.color | **运行时 tint**:`ParticleSystem.main.startColor`(Color 模式)+ `MaterialPropertyBlock`(多候选属性) |
| 动效 | DOTween 改 anchoredPosition/scale/alpha | 粒子自演 + DOTween/脚本叠 transform(悬浮/呼吸/pop)+ 一次性 burst |
| 性能 | draw call / 图集 | **粒子数 / overdraw / 叠加混合**;高频生成必须池化 |
| 看效果 | F8 截屏(overlay canvas 截图盲) | edit-mode `capture_scene_object`(静态)+ play `ScreenCapture`(运动) |

核心:**VFX 是会动的、会被实例化很多份的、要按类型变色的**。这三点决定了 tint 管线、池化、动效分层是必修。

---

## 第一步:盘资产 + 复用 vs 自建的判断(默认复用)

1. 盘点项目 VFX 包:`Assets/AssetPacks/VFX/Epic Toon FX/`(1300+ prefab:Magic/Sphere・Shield・Aura・Field・Buff・Nova、Explosions/Bubble・Liquid・Sparkle・Glitter、Missiles/拖尾、Environment/Stars・Sparks)+ Hovl Studio 等。
2. **先用 `get_game_object_info(prefabPath=...)` 验单个 ETFX prefab 的结构**:几个 ParticleSystem、`looping`/`playOnAwake`、renderMode(Mesh vs Billboard)、有没有 AudioSource/脚本(ETFX 爆开自带音效+`ETFXPitchRandomizer`,很好用)。单 PS = 轻;多 PS = 注意池化与播放控制。
3. **复用 vs 自建的判断线**:
   - **持续的"形状壳"(泡泡/护盾/水晶外形)→ 自建 mesh**。教训:ETFX 的 MagicShield/AuraSoft 直接当泡泡壳用,渲出来是**一坨软光团**,糊掉模型、读不出"模型在泡泡里"。要清晰轮廓就用球 mesh + 透明材质。
   - **光晕/爆开/拖尾/星火 → 复用 ETFX 粒子**(BubbleExplosion 当泡泡爆开、LiquidExplosionWaterClear 当液体溅水、AuraSoft 当内发光、Glitter/Sparkle 当拾取闪)。这些粒子自带成品级运动,自建不划算。
   - 复用范式抄 `MeteorStrikeAttack._impactVfxPrefab`(serialized prefab → Instantiate → Destroy(lifetime))或池化版 `Gameplay.Effects.PoolableVFX`。

---

## 第二步:tint 管线(成品级"按类型变色"的核心,有个 alpha 陷阱)

每个 type 一个主色。复用 `Gameplay.Drops.PickupAuraVFX` 的范式(或照抄它):

- **粒子**:只在 `main.startColor.mode == Color` 时改 `startColor`,Gradient/TwoColor 是美术作者意图、不要动。
- **Renderer**:用 `MaterialPropertyBlock` 写**多候选颜色属性**——`_BaseColor`(URP Lit/Unlit)、`_TintColor`(粒子/ETFX)、`_Color`(legacy)、`_EmissionColor`。写一个 shader 没有的属性是无害 no-op,所以全写一遍 = 跨 shader 稳。
- **tint-root 模式**:给一个 `_tintRoot` Transform,`GetComponentsInChildren` 一次性 tint 整个 VFX 子组(壳+光晕)。

⚠️ **三个硬坑:**
1. **tint 无法变色相,只能乘(变暗/滤色)**。蓝球 tint 紫 ≠ 紫。所以**按主色 hue 选最近的颜色变体**(MagicShield 有 Blue/Green/Yellow/**Purple**;AuraSoft 只有 Blue/Green/Yellow),tint 只做微调。
2. **运行时 tint 会把透明材质的 alpha 写成 1 → 泡泡变实心**。解法:**固定类型的透明壳在 build 时烘焙好颜色+低 alpha,放在 `_tintRoot` 之外**(别让运行时 tint 碰它);只有运行时才知道颜色的(装备稀有度)才走 tint。
3. **模型 emission 别太猛**(*1.2 会糊成白球,读不出色);*0.4~0.5 让模型显出饱和本色,当泡泡里的"核"。

---

## 第三步:成品级配方(掉落物实战,可作模板)

一个世界拾取物的视觉 rig(全部由 editor builder 幂等装配,**改 builder 不手摆**):
```
root
├── Model (modelContainer)   // mesh,轻 emission(*0.5)显本色;PickupBase 驱动旋转/bob
├── BubbleShell              // 球 mesh + 烘焙染色透明材质(alpha~0.28, smoothness~0.95,
│                            //   轻 emission rim);放 _tintRoot 之外避免 alpha 被改实
└── VFX (= _tintRoot)
    └── InnerGlow            // ETFX AuraSoft(按 hue 选变体),小 scale(~0.22)做核心光晕
```
透明材质 URP 设法(脚本):`_Surface=1, _Blend=0, _SrcBlend=SrcAlpha, _DstBlend=OneMinusSrcAlpha, _ZWrite=0, EnableKeyword("_SURFACE_TYPE_TRANSPARENT"), renderQueue=Transparent`。

---

## 第四步:动效语言(静态视觉 + 这些动效才叫成品级)

叠在静态 rig 之上,缺一个就显廉价:
- **原地悬浮**:旋转 + 正弦 bob(`PickupBase` 已有)。
- **呼吸**:模型 scale 叠 `1 + sin(t)*0.06`,有生命感。
- **spawn pop-in**:出生时 scale 0→1 走 `EaseOutBack`(过冲),"有重量地出现"。
- **散射**:从死亡点 ease-out 爆开一小段再停(loot 的手感)。
- **飞向玩家 / 原地等**:磁吸(`_alwaysMagnet` 无限距离 + `_magnetStartDelay` 落地停顿)vs 关磁吸走过拾取——**按掉落物语义分**(钱/经验/loot 飞、补给/buff 原地)。
- **拾取爆开**:在拾取点放一次性 burst(BubbleExplosion 泡泡爆 + LiquidExplosionWaterClear 水花,池化,自带音),tint 成该色。

---

## 第五步:玩家侧反馈(订阅事件,集中一处,池化)

一个 `*FeedbackController` 订阅领域事件(掉落系统用 `DropEvents.OnPickupCollected(type,amount,worldPos)`),按 type 表驱动:
- **身上光效**:把 tint 后的特效**挂到玩家**(范式抄 `HitFeedback` 的池化 splash)。高频类型(金币/经验)别每次 new 一个光环→**单实例 re-pulse**(`ps.Clear()+Play()` + 重 tint),防刷屏+省。脚环用 `MagicFieldWhite`(白色→可 tint 任意色),build 时把 `main.loop=false` 让它一次性。
- **上升 icon**:world→screen 飘窗,复用 `UIDamagePopupWidget` 范式(池化 + DOTween 上浮 + CanvasGroup fade)。挂 `UICanvasLayerManager.GetLayerContainer(UILayer.HUD)`;`Camera.WorldToScreenPoint` →(behind-camera 判 z<0 跳过)→ `RectTransformUtility.ScreenPointToLocalPointInRectangle`(overlay canvas 传 null camera)。
- 颜色心智:**玩家身上闪红 = 受伤**,所以"回血"光效用**绿**不用红。

池化提示:`PoolService.Get(prefab)` 不存在会自动建池(size 5),burst/popup 低频可懒建;高频(金币)预热。`PoolableVFX` 只 Clear+Play **自身**那个 PS——多 PS 的 ETFX,子粒子要 `playOnAwake=true` 才会在 pool 激活时播,根上设 `_overrideLifetime`。

---

## 第六步:MCP 看效果迭代(VFX 专属流程,和 UI 不同)

**先 edit mode 定静态,再 play mode 验运动+反馈。** 别一上来全在 play 里调——play 有怪/暂停/升级面板/失焦坏帧干扰。

1. **静态(edit mode,最可靠)**:`execute_script` 把各 type prefab `PrefabUtility.InstantiatePrefab` 排一行到一个 parent → `capture_scene_object(parent)` 一张图看**颜色对不对、模型读不读得出、壳子在不在**。粒子在 edit 里不自动播没关系,这步只判静态。用完删 parent、别存场景。
2. **运动 + 反馈(play mode)**:走 `playmode-verify-iterate` 的纪律(`runInBackground=true` 第一行、分步驱动、state dump 是权威)。
   - 进局内主玩法用记忆里的 playbook(`GameModeContext.CurrentMode` 先设再 `LoadGameSceneAsync(arena)`)。
   - 直接 `PoolService.Get(prefab)+Initialize(pos)` 在玩家周围生成各 type,看悬浮/飞-停/壳子光晕。
   - 验拾取反馈:生成在玩家身上触发 collect,**state dump 数 popup 数 / body-glow 实例 / 玩家 StatusEffectHandler.ActiveEffects**(overlay canvas 的 popup 截图是盲的,只能 dump);`ScreenCapture.CaptureScreenshot` + PowerShell 裁中心区 Read 判 3D 视觉。
3. **对比上线级再迭代**:每轮问"差在哪"——糊(光团太大/emission 太猛)、读不出泡泡(壳用了粒子不是 mesh)、色不对(tint 想变色相了→选变体)、没生命(缺呼吸/pop/burst)。一次只改能定位的一项,重跑 builder→重测。

---

## 已验证会翻车的坑速查

| 现象 | 根因 / 修法 |
|---|---|
| 泡泡/护盾是一坨软光团、糊掉模型 | ETFX shield/aura 是软粒子;形状壳改用 **球 mesh + 透明材质** |
| 泡泡 tint 后变实心球 | 运行时 tint 把 `_BaseColor.a` 写成 1;固定类型烘焙颜色 + **壳放 `_tintRoot` 外** |
| tint 想把蓝变紫但变暗了 | tint 是乘法、不能加色相;**按 hue 选最近颜色变体** |
| 模型糊成白球 | emission 太强;降到 *0.4~0.5 |
| 高频拾取光环刷屏/掉帧 | 身上光效**单实例 re-pulse**,别每次实例化 |
| 多 PS 的 ETFX 池化后只播一个 | `PoolableVFX` 只控根 PS;子粒子设 `playOnAwake`,根设 `_overrideLifetime` |
| 上升 icon 截图看不到 | GameScene 是 ScreenSpaceOverlay canvas,截图盲;用 **state dump** 数实例 |
| play 里调视效老被打断 | 怪/auto-combat/升级面板/失焦坏帧;静态评估挪 **edit mode** |
| 别人同开编辑器,execute_script 偶发 timeout / play 态被清 | 并发 domain reload;重试 + 关键值 dump 核实,只在别 session 占 Play 时才等 |
| dump 实例 `GameObject.Find("X")` 得 null 假阴性 | `Instantiate` 出的实例名是 `X(Clone)`;用子串匹配或 reflect 控制器持有的实例字段,别用精确 Find |
| dump 池化对象数=0 假阴性 | 池化对象秒级归池,`FindObjects(Exclude inactive)` 漏掉曾生成的;用 `Include` inactive(池对象不销毁=曾用过)或生成后即时 dump |
| 找模型/资产 Glob/Grep/Read 全找不到 + subagent 编造路径 | asset 包常被 `.gitignore` 忽略 → ripgrep 系工具(Glob/Grep/Read)+ Explore agent **全盲**;改用 Unity `AssetDatabase.FindAssets("name t:GameObject")` 经 `execute_script` 查真库,渲染 contact sheet 肉眼挑 |

---

## 收尾(同 feature 流程)

编译干净(`check_compile_errors` + grep logs `error CS` 交叉验证)→ edit-mode 静态过 + play-mode 运动/反馈 dump 过 → 写一条 project 记忆(builder 入口、配方、踩坑)→ 推进了产品就 `progress.js bump` → 问勾哥上传 Planyway。配套:`ui-visual-rework`(UI 面)、`playmode-verify-iterate`(测试闭环)、`gaoguang-3d`(AI 模型进项目去灰提饱和)。
