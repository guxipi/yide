---
name: ui-visual-rework
description: Rework an Extraction UI screen to production quality ("成品级") using the SuperCasual kit — recipe-extraction method, asset selection, state visuals, and DOTween motion language. Trigger on "重做XX界面视效" / "refine XX 界面" / "visual 太 cheap" / "成品级 visual" / "把材质底纹动效用起来" / "按 SuperCasual preview 做" / "界面太丑" / "美化一下界面" or any request to re-skin/polish a meta screen (panel, popup, calendar, leaderboard, reward reveal...). Battle-tested on Battle Pass, Leaderboard, Daily Login + universal Reward popup. Companion to the ui-placement skill (that one = placement discipline + verification channels; this one = how to reach finished-game visual quality).
---

# UI Visual Rework (Extraction · SuperCasual kit)

把一个"代码生成的平面色块界面"重做成成品级,流程与判断全部实跑验证过(Battle Pass / Leaderboard / Daily Login / Reward Reveal 四单)。**先读 `ui-placement` skill**(执行纪律、截图通道、RectTransform 坑)——本 skill 不重复它,只讲它之上的"做到好看"。

## 第〇步:侦察永远先行,别急着写代码

1. 读目标界面的 **runtime 脚本**(serialized 字段 = 你必须保留的 wiring 接口;public API = 调用方依赖)。
2. 找它的**建造方式**:grep `Tools/Setup` 菜单 → 多数界面由 `Assets/Scripts/Editor/Setup/*Setup.cs` 代码生成(scene 对象或 prefab 资产)。Builder 就是你要改的"源头"——改 builder + Rebuild 菜单,不要手摆场景。
3. 若界面在场景里被人手改过,先 dump 场景实例(hierarchy+sprite+color+rect)拿真相,再决定重建。
4. **顺手抓功能 bug 是本打法的一部分**:视效单里实际修出过「弹窗永远弹在全屏面板后面(sibling z 序)」「全服一人却排 #200(服务端占位估算)」「JSON 反序列化把可选对象变非 null 空壳导致所有卡显示同一图标」。界面难看常常和数据/流程坏掉混在一起,一起修,修完明说。

## 第一步:配方提取法(本打法的核心,严禁跳过)

**Preview 图只用来"选方向",数值必须来自 demo prefab dump。** 肉眼从截图猜比例/颜色是过去失败的根源。

1. **选参考**:`Assets/AssetPacks/UI/Layer Lab/GUI Pro-SuperCasual/Preview/` 里找同功能截图(命名即功能:`0_Daily_Bonus_7Day`、`10_Leaderboard_*`、`8_Shop_Pass_*`、`9_PopupFullScreen_Reward*`...)。Read 看图定方向。
2. **Dump 配方**:同名 demo prefab 在 `Prefabs/Prefabs_DemoScene_Panels/`(整屏)与 `Prefabs/Prefabs_Component_Popups/` 等(组件)。写临时 editor 脚本递归打印每个节点:`name / anchoredPosition / sizeDelta / anchors / rotation / Image(sprite名, type, #RRGGBBAA) / TMP(text, fontSize, color) / activeSelf`。这份 dump 就是像素级施工图——kit 作者自己的组装参数(tint 色值、sliced/tiled/simple、inset、字号)直接抄。
3. **素材清单**:`grep -o "m_Sprite: {fileID: [0-9]*, guid: [a-f0-9]*" <prefab>` 取 GUID → `grep -rl "guid: $g" --include="*.png.meta" ResourcesData/` 反查文件名 → 得到该界面用到的全部 sprite,一张不漏。
4. **素材性质求证**(像素采样,PowerShell System.Drawing 读 PNG):
   - 中心 A=255 且 RGB 白 → **可染色实心基底**(一切状态色都靠 tint 它);
   - 中心 A=0、边缘 A>0 → **描边框**(敢放心叠在内容上);
   - `.meta` 里 `spriteBorder` 非零 → 可 Sliced;为零(光效类)→ 只能 Simple,别 sliced 拉伸。
   - 拿不准 sprite 长相就 Read 那张 PNG 看图。
5. **尺寸换算**:kit demo 基准 1080 宽,本项目 canvas 1440×2560 → 几何与字号一律 **×1.33**(kit 40pt→53、卡 287×420→382×560)。

## 第二步:视觉语言(从 kit 提炼的规则,直接套)

- **状态即 tint**:同一张白 sprite,状态只换颜色。日历卡:已领 `#A8BBD1` 灰蓝+绿勾+内容降透明、当前 `#24E715` 绿、未来 `#0787FF` 蓝。Pass 双列:免费蓝/付费金 `#FFD233`。
- **层叠配方(z 序=创建顺序)**:`Bg(tint, sliced, inset≈2-4)` → 内容层(`Light`高光 / `Gradient` / `Pattern` tiled α≈0.05-0.25 底纹) → `Border`(黑描边, sliced, 全尺寸) → `Glow`(图标后光斑) → 图标 → 文字。逐层都来自 kit 同名 sprite 家族。
- **复用既有家族保持全游戏一致**:ticket 弹窗家族(`Popup_Ticket_Bg/Gradient/Border/BottomPattern`+撕票线)、卡片 `CardFrame04_*`、奖励格 `ItemFrame00~03_*`、气泡格 `BubbleFrame05_*`、ribbon `Title_Ribbon01/02_*`。新界面先问"哪个家族最近",别每次发明新皮。
- **文字**:全部 CookieRun SDF **白色**(自带深描边,任何底色可读;勾哥明确不要黑字)。一律 `enableAutoSizing(min≈26, max=设计值)` + `textWrappingMode = NoWrap` 防溢出换行。深色字只许出现在明确浅底(如 BP 行内 navy)。
- **"当前/可点"必须活**:focus 双层(`FocusGlow` 青色外扩 + `FocusBorder` 白描边)+ 特效组(`Image_Effect_Rotate` 旋转光线 + `Image_Effect_Star01/Square` 星星方块)+ 呼吸 scale。kit 的 TODAY 卡就是这么做的,照抄。
- **炫目领奖配方**(`9_PopupFullScreen_RewardItems` 提炼):深黑 dim(≥0.9,越黑光越炸)→ 放射光芒 `Image_Effect_Light01_Yellow` → **旋转光圈 `Image_Effect_Rotate` 必须建在光芒之后**(否则被亮区吃掉看不见)→ `Glow_Circle01` 光晕 → 彩带 `Image_Papers` → ribbon → 奖励卡行。
- 装饰图 `raycastTarget=false` 一律关;通用图标在 `IconMisc/`、物品图标 `Icon_ItemIcons/256/`、demo 大图标 `Demo/Demo_ItemIcon/`。

## 第三步:动效语言(DOTween,数值实跑校准)

**揭示三段式**(任何"出现"类界面):
1. 光效 ramp:alpha `0.2→1` + scale `0.55→1.1`,`0.6s OutQuad` ——"渐变到高亮";
2. 主体 punch:ribbon/标题 `localScale 0→1, 0.4s OutBack`(delay 0.1);
3. 内容 stagger:每项 `0→1 OutBack 0.38s`,间隔 `0.12-0.14s`;每项落位时自己的 glow `0→1→0.55` 闪一下再进 yoyo 脉冲。

**持续层**(进场后一直跑):
- 旋转光圈:`DORotate((0,0,-360), 8-10s, FastBeyond360).SetEase(Linear).SetLoops(-1, Incremental)`;
- glow 脉冲:alpha 或 scale `yoyo 0.6-0.9s InOutSine`;呼吸(可点卡/CTA):scale `1↔1.04-1.08`;
- 星星:慢旋 ±18° + scale yoyo,每颗周期错开(`0.7+i*0.18s`);提示文字:落位后 alpha `1↔0.45` 闪。

**纪律**:全部 `.SetUpdate(true)`(防 timeScale);每条 tween 记进 List/字段,`OnBeforeHide`+`OnCleanup`/`OnDestroy` 统一 `Kill()` 并复位(rotation 归零、scale 归一);列表入场动画只做**前 10 个**(perf 指南);`async void` claim handler 在 await 后加 `if (this == null) return;` 守卫。

## 第四步:工程化(必须可一键重建)

- Builder 全写进对应 `*Setup.cs`,加 `Tools/Setup/<系统> - Rebuild ... (SuperCasual)` 菜单:删旧实例 → 重建 prefab 资产(`SaveAsPrefabAsset` **同路径覆盖保 GUID**,场景引用不断)→ 重建场景对象 → 重新注册 `UIPopupsManager._registeredPanels`(先清 null 残留)→ `MarkSceneDirty`;运行后用 `EditorSceneManager.SaveScene` 存场景(Coplay save_scene 有路径坑)。
- Wiring 一律 `SerializedObject.FindProperty(带 null 检查)`;sprite 加载失败要 `LogWarning` 路径——重建后 **grep 日志确认零 Sprite not found / Property not found**。
- **z 序**:同 Layer 内弹窗按 sibling 渲染。建造顺序=底→面(全屏面板先建,其上弹窗后建);运行时 `UIPopupsManager.ShowPanel` 已做 `SetAsLastSibling`,**自定义弹出路径必须走 manager**,直调 `panel.Show()` 不置顶。
- 别用 `SetActive(false)` 硬关 UIPanel(状态卡 Visible,下次 Show 早退)——正路是 `Hide()`。

## 第五步:验证闭环(交付前必过)

通道与纪律见 `ui-placement` skill;本打法特有的:

- **分步驱动截图**:动画是时序的——`Open`(走 manager)→ sleep 2-3s → `Capture` 拆成独立 execute_script 调用(`Application.runInBackground=true` 否则编辑器失焦游戏冻结、`Time.time` 不走)。
- **动画在动的证明**:间隔 1-2s 截两帧,对比旋转光圈角度/光线位置。
- **伪影鉴别**:同一帧里 `Refresh()`+截图 → 被 `Destroy()`(延迟到帧尾)的旧元素仍渲染,会拍出"压扁乱码双份卡"。**新帧重拍干净 = 伪影,真玩家看不到**;别误修。
- **找不到的元素用二分**:逐个 `SetActive(false)` 区域再截图,三轮内锁定;比反推坐标快得多。
- **全分辨率裁块终检**:1440×2560 截图缩略图会骗人(暗色误判、细节糊),交付前 PowerShell 裁 2-3 个关键区域(当前卡/按钮行/奖励格)原尺寸 Read 检查对齐与瑕疵。
- **端到端真点击**:`button.onClick.Invoke()` 走真实链路(领取→服务端→弹窗→刷新),别只截静态摆拍。涉及签到等一次性状态,用 Debug tab 的 Reset(删 CloudSave key)重置后重启 Play 验自动弹出路径。

## 已验证的坑速查

| 坑 | 真相 |
|---|---|
| RemoteConfig/JSON 配置里的可选对象 | 反序列化后**非 null 空壳**,判断必须用内容字段(`!string.IsNullOrEmpty(x.Rarity)`) |
| 弹窗弹了看不见 | 在全屏面板 sibling 之下;走 manager(SetAsLastSibling)或后建 |
| kit "按钮" prefab | 多数是纯 Image,**没有 Button 组件**,要自己 Add |
| 光效叠不出来 | 旋转光圈/星星必须建在亮光层**之后**;dim 不够黑光效不炸(≥0.9) |
| 撕票线 | `Popup_Ticket_BottomPattern` 用 **Tiled** 挂在底条顶边 y+14 |
| 编辑器失焦 Play 不走 | 第一件事 `Application.runInBackground = true` |
| check_compile_errors 偶发说谎 | 再 grep Unity logs `error CS` 交叉验证 |

## 交付前硬规则与自查(本项目)

**数值真源** = `UI_Visual_Design_Guidelines.md`(项目内 `Claude Feature Docs/UI Visual Design/`,基于真实代码:RarityConfig.cs / UICurrencyItemWidget 等)+ kit prefab dump(配方提取法)。hex / 尺寸 / 时长以这两者为准,散文描述让位。

**交付前 6 条自查**:① 无裸 hex(色值可溯源到 Guidelines / kit dump)② 框体策略统一(本项目 = 烘焙 9-slice,永远不用程序化圆角)③ 锚点用预设、无绝对坐标硬编码 ④ 同轴只有一个尺寸权威(LayoutGroup / ContentSizeFitter / 显式,三选一)⑤ 字体规范见下 ⑥ 可点元素挂 `Core.UI.PressScale`。

- **juice = art, not code**:渐变 / 圆角 / 描边一律来自 kit 9-slice 美术资产,不用 `ThemePalette` / `UIGradient` / `com.nobi.roundedcorners` 这类代码方案(它们也不在项目里)。
- **`Core.UI.PressScale`**(已入库 `Assets/Scripts/Core/UI/PressScale.cs`):kit 按钮是纯 Image 无按压反馈,新按钮一律挂上;unscaled time,timeScale=0 下照常工作。
- **Canvas 参考**:kit 屏用 kit 自身 CanvasScaler **1080×2340 / Match 0.487**,measured px 1:1(详见 ui-placement 真源 `UI_Placement_Rules.md`,2026-06-14 RATIFIED;旧的 1440×2560 对 kit 屏已废弃)。

**字体拍板(勾哥 2026-06-12):全场回归 CookieRun Black Outline 54 SDF**(Guidelines §3)。已知欠账:死亡三屏(UIRevivePopup / UIDeathSummaryPanel / UIMineDefeatPanel)与 battle_endreward 设计稿当前用 kit 的 Sen/Cairo,后续换成 CookieRun;新屏一律直接 CookieRun,不要再扩大 Sen/Cairo 面积。
