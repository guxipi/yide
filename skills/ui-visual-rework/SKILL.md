---
name: ui-visual-rework
description: Rework an Extraction UI screen to production quality ("成品级" = clear hierarchy, calm and crisp per ER美术规范, NOT busier or rounder), SuperCasual kit as one toolset. Trigger — "逐屏优化" / "优化这个 screen / pop up" / "更有商业化成品感" / "重做XX界面视效" / "refine XX 界面" / "visual 太 cheap" / "成品级 visual" / "按 SuperCasual preview 做" / "界面太丑" / "美化一下界面" or any re-skin/polish of a meta screen (panel, popup, calendar, leaderboard, reward reveal). Companion to ui-placement (placement + verification); this = finished-game visual quality.
---

# UI Visual Rework (Extraction · SuperCasual kit)

> 分工提醒:勾哥手摆过的屏,几何归他,AI 只接线和改可读性(见 ui-placement 开头);本 skill 的整屏重做只用于他点名要 AI 重做的屏。

把一个"代码生成的平面色块界面"重做成成品级,流程与判断全部实跑验证过(Battle Pass / Leaderboard / Daily Login / Reward Reveal 四单)。**先读 `ui-placement` skill**(执行纪律、截图通道、RectTransform 坑)——本 skill 不重复它,只讲它之上的"做到好看"。

## 目标水准:先读参考资料第 9 节
**目标水准和验收以 ER 美术规范为准**(目标和红线;UI 的详细观察和判断方法在 `ER美术规范_参考资料.md` 第 9 节,只是参考):vault `01 - 星际拓荒重构/013 美术/ER美术规范.md`。这里的"成品级"指玩家打开一屏三秒内知道这屏干什么、该点哪,不是"做得更花"。ER 现在 UI 的毛病是太满、太圆、太吵,所以总纲要的结果是:一屏一件事(行动型页面一个主按钮,选择型页面突出当前选中或唯一推荐位);入口分级,低频入口不在首屏抢位置;红点和角标只给现在不处理就会损失的东西;分组靠间距看出来,不靠加框;形状利落不圆润,看不到双层边、内倒角高光、粗黑描边;颜色收敛,一个底色一个强调色加一两个语义色,蓝色不满屏,深底读起来是深色而不是黑;内容(物品、角色、奖励)是主角,框和底板是配角。红线第 6 条(蓝不满屏)、第 7 条(不 busy、不圆润)不可越过;交付前过参考资料 9.5 的自检和 9.3 的四项数字。

下面的 kit 配方、层叠和动效都是工程里验证过的做法,用来服务层级,不是越丰富越好;叠上去让层级更糊、更吵的就删掉。不用 kit 也行,结果过总纲门槛即可。

## 逐屏优化实战套路(2026-10-13 礼包弹窗 UIOfferPopup + 选弹药 UIShopChooseAmmoPopup 两屏跑通)

勾哥开始"逐屏优化 screen / pop up"时的缺省做法。两屏的真源可直接当样板抄:`Assets/Scripts/Editor/Setup/OfferUISetup.cs`(BuildVisual)、`Assets/Scripts/Meta/UI/Offers/UIOfferPopup.cs` / `UIOfferContentSlot.cs`、`Assets/Scripts/Meta/UI/ShopDesign/UIShopChooseAmmoPopup.cs`;实机截图在 vault `013 美术/UI弹窗优化_2026-10-13/`。

**流程**
1. 现状先实读:prefab dump(节点 / sprite / 色值 / 字体 / 字号)+ 实机截图;字号一律换算成屏上像素(字号 × 父级缩放 × canvas scaleFactor;Popup 层 1440 参考 → 1080 屏 ×0.75,kit 屏 1080 参考 1:1)。
2. 第一轮可以出 mock 定方向(竞品只借布局和层次);**方向一定就只改真 prefab,每轮给勾哥的是 Play 截图**(`ScreenCapture.CaptureScreenshot`,1080×2340)。mock 和 builder 两套组装代码必出偏差,这次因此多返工三轮。
3. 有 builder 的 prefab 改 builder 再跑(菜单覆盖前要确认,避免冲掉手摆);没有 builder 的直接 `PrefabUtility.LoadPrefabContents` 改结构 → `SaveAsPrefabAsset`。脚本改成序列化引用,不按节点名查。
4. 进 Play 走真入口打开,每个变体都开一遍(单格 / 多格 / 不同礼包),state dump(文本、`characterCount`、active、屏上 rect)+ 截图;关闭键走真 `onClick`。测完停 Play,只提交本单文件。
5. **遮挡检查是交付硬门(勾哥 10-13 点名)**:每屏两道都过才算完。① 脚本:关键元素(标题 / 副标题 / 内容行 / 按钮 / 倒计时 / 角标 / info)屏上矩形两两求交,TMP 按**可见字形轮廓**(`characterInfo` 的 bottomLeft/topRight)算,别用 `textBounds`(含整行行高,Saira ≈1.57em,会大量误报),重叠 >3% 或出卡/出窗即红;有意的叠放(贴纸角标压按钮沿)显式豁免。脚本在 vault `013 美术/工具/ui_occlusion_check.cs`。② 肉眼:人物的脸、手、主道具不许被任何 UI 压住,压插画的元素优先放插画空景一侧。

**勾哥定的硬口径**
- 组件用 SuperCasual kit 现成 prefab(少用大圆角),**不要自己画 / 渲按钮和底板**,不用粉色。已验证可直接嵌套的件:`Popup09_Topbar_Divided_Label_*` 壳(顶栏放大到 ~170)、`Button01_l_BtnText_Yellow`(价格直接写在按钮上)、`BorderFrame_Oval58_Dark`(倒计时套件 = 深底 + `Icon_Timer`,倒计时不在正中就用它)、`Label_Parallelogram_Yellow`(ONE-TIME / PICK ONE 角标)、`Title_LIne03_Divider`(YOU GET / PICK ONE 分隔)、`CardFrame04_FocusBorder`(选中框)。
- 物品格 = 背包同款 `UIUniversalItemWidget`(颜色按真实稀有度,数量右下);不要另造格子。多于一行的内容分行居中、整窗加高,不缩格子(缩了字会低于下限)。
- 每个功能 / 礼包一套主题色,进配置不进代码(范式:`OfferBannerLibrary` 条目的 Theme 四色);正文由浅到深(竖向 alpha 渐变条 `expedition_竖向渐变遮罩_8x256` 染深色压下半);底纹用勾哥的半调波点 `expedition_波点渐变底纹_1024x1024`,透明度 ~1.5%。
- 字体 Saira,字号下限见 Extraction 工程 CLAUDE.md UI 字体铁规第 4 条(1080 屏 32px / 标签 40 / 按钮 48 / 标题 64);每段字对比度量完再交。
- 头图要讲这个功能的故事并放英雄;避开 UI 压条的安全区(顶部倒计时 / 渐变、底部渐变);已定稿 KV 构图不合优先往外扩画,不重画;人物按角色手册修(出图口径见 KV 相关记忆)。头图下沿渐变融进正文底色。
- 提示语义:红点 = "有新东西 / 待处理",不能当"这格可选";自选类用文字标签,且和下一屏用同一个词。

**动效(只给主角,不铺满)**:CTA `UIShineSweep` + 呼吸;内容格依次弹出(0.38s OutBack,间隔 0.12s);头图闪星 / 格子背光用 `UIAmbientPulse`(alpha 闪烁要同节点有 `CanvasGroup`)。挂了 `Core.UI.PressScale` 的节点不要再做缩放动效,它每帧回拉 localScale。

**这两屏踩实的坑**
| 现象 | 根因 / 修法 |
|---|---|
| 内容区顶部被裁一截 | 纵向拉伸锚点的新节点 `sizeDelta` 默认 (100,100) → 比视口高 100,被 RectMask2D 裁;新建后清零 |
| 高光条错位 | 抄 kit 子节点位置前先实读 pivot(kit `LIght` 是 pivot 居中 y-24 = 贴顶) |
| 倒计时秒表压住首字母 | kit 套件 HLG 左 padding 58 按 Cairo 留,Saira 加到 ~86 |
| 物品名整行消失,`characterCount=0` | TMP Ellipsis + 框高 < 行高(Saira ≈1.57×字号)→ 整行被省略;框高跟字号走 |
| 多行内容互相压 | VerticalLayoutGroup `childControlHeight=false` 时子级 LayoutElement 不生效 |
| 通用格整格消失 | `ItemDesignData` icon 传 null 会被当空格隐藏;要替换图就传真 icon(或做合成 icon) |
| eval 报 Main thread 5000ms 超时 | 长操作(导图 / 生成字体 / 跑 builder)用 `unity cmd eval_file --detach` + `unity job wait` |
| 离屏渲染拍进场景物体 | 临时相机 `cullingMask = UI 层`,节点 layer 设 5 |
| 外部新建的 .cs 永远不进编译(`recompile` 报 up_to_date、MonoScript.GetClass()=null) | 编辑器不在前台时新文件没登记进脚本集合;删掉后用 `unity cmd create_script --name X --path ... --namespace ...` 让 Unity 建,再覆盖内容、recompile |
| 倒计时 / 角标压脸 | 放插画空景一侧(右上);跑遮挡检查 + 看脸 |
| 关掉弹窗又弹出来 | 不是 bug:`HomeAttentionDirector` 排队,手动先开的话关闭后它补弹;新手三礼包会依次弹 |

## Refine 工单六步(缺省流程,2026-07-07 契约 §8 原文)
任何 UI refine 任务的缺省框架;硬契约全文见 `Claude Feature Docs/UI Visual Design/Visual_Refine_Contract.md`,范式库见同目录 `Pattern_Catalog/`。下面的第〇~五步是这六步在本 skill 里的展开。
1. 读 `Pattern_Catalog/` 声明本次套哪条范式(套不上 = 先扩范式库问勾哥,**禁 freestyle**);
2. F8 `ScreenCapture.CaptureScreenshot` 截基线;
3. 只经 UITheme token / ApplyStyle 改(M1 后;当前:值必须引用金标准屏实测值并注明出处);
4. 跑风格体检红项清零(M1 后 UI Hub;当前:人工过契约 §1-§6 逐条);
5. 截图对比基线 + `QA/golden/` 金标准;
6. 真流程 Play(真切 tab 真点按钮),含 Android 返回键路径。

**范式库引用义务(硬规)**:开工必先在 `Pattern_Catalog/` 声明套哪条范式;套不上的区域 = 先扩范式库并问勾哥,禁 freestyle 自由发挥。refine 完在 `Pattern_Catalog/` 记一行出处留痕(套了哪条范式、用了哪些 token),供下个接手者先读意图不逆向猜。

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
5. **尺寸换算**:kit demo 与本项目 kit 屏同基准 **1080×2340 / Match 0.487**,measured px **1:1 照抄**(真源 `UI_Placement_Rules.md`,2026-06-14 RATIFIED)。旧的「canvas 1440×2560 → ×1.33」对 kit 屏**已废弃,别再用**。

## 第二步:视觉语言(从 kit 提炼的做法,结果以参考资料第 9 节为准)

- **状态即 tint**:同一张白 sprite,状态只换颜色。日历卡:已领 `#A8BBD1` 灰蓝+绿勾+内容降透明、当前 `#24E715` 绿、未来 `#0787FF` 蓝。Pass 双列:免费蓝/付费金 `#FFD233`。
- **层叠配方(z 序=创建顺序)**:`Bg(tint, sliced, inset≈2-4)` → 内容层(`Light`高光 / `Gradient` / `Pattern` tiled α≈0.05-0.25 底纹) → `Border`(黑描边, sliced, 全尺寸) → `Glow`(图标后光斑) → 图标 → 文字。逐层都来自 kit 同名 sprite 家族。这是 kit demo 的满配;按参考资料 9.1,结果上不能读出双层边、内倒角高光和粗黑描边,层数够把内容托起来就停,用不上的层不加。
- **复用既有家族保持全游戏一致**:ticket 弹窗家族(`Popup_Ticket_Bg/Gradient/Border/BottomPattern`+撕票线)、卡片 `CardFrame04_*`、奖励格 `ItemFrame00~03_*`、气泡格 `BubbleFrame05_*`、ribbon `Title_Ribbon01/02_*`。新界面先问"哪个家族最近",别每次发明新皮。
- **字体与字色(2026-10-12 勾哥定稿,优先于下面的旧口径)**:除主页 START 外所有 UI 文字用 Saira(`Assets/Fonts/Saira/`;标题 SairaCondensed-Black、按钮/导航/数字/标签 SairaCondensed-ExtraBold、正文 Saira-Bold、小字 Saira-SemiBold,字号放大到字高不小于原字体);字色按底色定——纯色底只换字色(浅底同色系深色字、深底白字)→ 按钮白字或同色系深字二选一不描边 → 压插画先投影 → 仍读不清才细的同色系深描边 → 3D 画面上的字可描边;对比度小字 ≥4.5、大字 ≥3,交付前自己量。规则全文见工程 CLAUDE.md UI 字体铁规第 2、5 条和 vault ER美术规范 "文字要读得清" 一条;还没迁 Saira 的旧屏沿用下面的旧口径。
- **文字(旧屏口径)**(2026-07-07 修订,对齐字体二分制):**Title / 大数字 = CookieRun Black Outline SDF**,**其余一切非 title 文字(正文/按钮/标签/描述)= `Cairo_Line_Black SDF`**;两者都白色 + 自带深描边(任何底色可读;勾哥明确不要黑字;参考资料 9.9:描边只是一圈轮廓,看起来是深彩色而不是纯黑),都必挂 CJK fallback 链(NotoSansCJKsc→ZCOOLKuaiLe)。一律 `enableAutoSizing(min≈26, max=设计值)` + `textWrappingMode = NoWrap` 防溢出换行。深色字只许出现在明确浅底(如 BP 行内 navy)。
- **"当前/可点"要一眼看得出来**:kit 的 TODAY 卡用的是 focus 双层(`FocusGlow` 青色外扩 + `FocusBorder` 白描边)+ 特效组(`Image_Effect_Rotate` 旋转光线 + `Image_Effect_Star01/Square` 星星方块)+ 呼吸 scale,这些手段可以挑着用。但一屏只有一个东西在用强调色和动效喊"点我"(参考资料 9.11),别把这整套满配铺到每个可点元素上。
- **炫目领奖配方**(`9_PopupFullScreen_RewardItems` 提炼,奖励物品是画面主角):dim 压暗背景(kit 原配是 ≥0.9 的黑;参考资料 9.3 要深底读起来是"深"而不是"黑",颜色和深度以过门槛为准)→ 放射光芒 `Image_Effect_Light01_Yellow` → **旋转光圈 `Image_Effect_Rotate` 必须建在光芒之后**(否则被亮区吃掉看不见)→ `Glow_Circle01` 光晕 → 彩带 `Image_Papers` → ribbon → 奖励卡行。
- 装饰图 `raycastTarget=false` 一律关;通用图标在 `IconMisc/`、物品图标 `Icon_ItemIcons/256/`、demo 大图标 `Demo/Demo_ItemIcon/`。

## 第三步:动效语言(DOTween,数值实跑校准)

**揭示三段式**(任何"出现"类界面):
1. 光效 ramp:alpha `0.2→1` + scale `0.55→1.1`,`0.6s OutQuad` ——"渐变到高亮";
2. 主体 punch:ribbon/标题 `localScale 0→1, 0.4s OutBack`(delay 0.1);
3. 内容 stagger:每项 `0→1 OutBack 0.38s`,间隔 `0.12-0.14s`;每项落位时自己的 glow `0→1→0.55` 闪一下再进 yoyo 脉冲。

**持续层**(进场后一直跑;只给这屏的主角,也就是奖励或主按钮,其余元素静下来。一屏同时在转、在闪、在呼吸的东西多了就是 busy,碰红线第 7 条):
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

通道与纪律见 `ui-placement` skill;物品格的项目约定和面板宽度实测数据见 `references/itemframe-group-and-text-crispness.md`。本打法特有的:

- **分步驱动截图**:动画是时序的——`Open`(走 manager)→ sleep 2-3s → `Capture` 拆成独立 execute_script 调用(`Application.runInBackground=true` 否则编辑器失焦游戏冻结、`Time.time` 不走)。
- **动画在动的证明**:间隔 1-2s 截两帧,对比旋转光圈角度/光线位置。
- **伪影鉴别**:同一帧里 `Refresh()`+截图 → 被 `Destroy()`(延迟到帧尾)的旧元素仍渲染,会拍出"压扁乱码双份卡"。**新帧重拍干净 = 伪影,真玩家看不到**;别误修。
- **找不到的元素用二分**:逐个 `SetActive(false)` 区域再截图,三轮内锁定;比反推坐标快得多。
- **全分辨率裁块终检**:全分辨率截图缩略图会骗人(暗色误判、细节糊),交付前 PowerShell 裁 2-3 个关键区域(当前卡/按钮行/奖励格)原尺寸 Read 检查对齐与瑕疵。
- **端到端真点击**:`button.onClick.Invoke()` 走真实链路(领取→服务端→弹窗→刷新),别只截静态摆拍。涉及签到等一次性状态,用 Debug tab 的 Reset(删 CloudSave key)重置后重启 Play 验自动弹出路径。

## 已验证的坑速查

| 坑 | 真相 |
|---|---|
| RemoteConfig/JSON 配置里的可选对象 | 反序列化后**非 null 空壳**,判断必须用内容字段(`!string.IsNullOrEmpty(x.Rarity)`) |
| 弹窗弹了看不见 | 在全屏面板 sibling 之下;走 manager(SetAsLastSibling)或后建 |
| kit "按钮" prefab | 多数是纯 Image,**没有 Button 组件**,要自己 Add |
| 光效叠不出来 | 旋转光圈/星星必须建在亮光层**之后**;dim 太浅光效不炸(kit 原配 ≥0.9,颜色按参考资料 9.3 用深色别用纯黑) |
| 撕票线 | `Popup_Ticket_BottomPattern` 用 **Tiled** 挂在底条顶边 y+14 |
| 编辑器失焦 Play 不走 | 第一件事 `Application.runInBackground = true` |
| check_compile_errors 偶发说谎 | 再 grep Unity logs `error CS` 交叉验证 |

## 视觉/交互契约要点(2026-07-07,全文见 Visual_Refine_Contract.md)
碰 UI 全员硬约束,以下要点立即生效:
- **文字**:迁到 Saira 的屏按上面 2026-10-12 的规则(浅底用同色系深色字是对的,不是缺陷);旧屏口径:默认白色 + 描边(项目字体自带描边保可读);**旧屏里黑色正文 = 缺陷,见到就修**;彩色仅用于确有功能语义处(增益绿/危险红/稀有度/货币色)。
- **颜色 = 功能 + 重要度层次**:先判元素在本屏的功能重要度层级,再取对应视觉权重,不是"选个好看的色";禁顺色(前景背景趋同不可读)、禁无视觉重点。
- **Title 禁用"banner 一条"asset**(黑名单,具体 sprite 名见 `Pattern_Catalog/` 采收确认)。
- **popup 壳统一**:dim 层 + panel 底 + 底纹阴影按标准 popup shell 规格(`Pattern_Catalog/`),不各弹窗自配。
- **主动修破损,不等勾哥提**:遮挡 / 出框 / 出父容器裁剪 / 字太小 / 九宫格拉变形 / 四边不合拢——碰 UI 时见到就修;修不了必须上报,沉默路过 = 违规。
- **动效基准 = 排行榜 / Friends**:各层级 UI 都要有动效但**有重点**;**开 / 关必有 subtle 过渡**(质感关键);层级越深越轻;StagedReveal/Shine 只给重点元素。
- **state vs variant**:运行时会切换 = 同 prefab + state(脚本驱动,默认选择:稀有度/空满/锁定/可用禁用/分段);作者期定型风味 = variant(公司主题皮、场景装饰,深度 ≤1);**运行时要变的绝不用 variant**;variant 里一半节点要删改时 → 改为两 prefab 共享脚本 + token。

## 交付前硬规则与自查(本项目)

**数值真源** = `UI_Visual_Design_Guidelines.md`(项目内 `Claude Feature Docs/UI Visual Design/`,基于真实代码:RarityConfig.cs / UICurrencyItemWidget 等)+ kit prefab dump(配方提取法)。hex / 尺寸 / 时长以这两者为准,散文描述让位。

**交付前 6 条自查**:① 无裸 hex(色值可溯源到 Guidelines / kit dump)② 框体策略统一(同一屏用同一种底图;读起来不圆润、没有双层边,见总纲红线第 7 条)③ 锚点用预设、无绝对坐标硬编码 ④ 同轴只有一个尺寸权威(LayoutGroup / ContentSizeFitter / 显式,三选一)⑤ 字体规范见下 ⑥ 可点元素挂 `Core.UI.PressScale`。

- **底图优先用美术资产**:渐变、圆角、投影通常来自九宫格美术图(kit 或 2026-10-12 批准的新底图,实验版在 `Assets/_Experiments/UIKitV2/`);代码方案不禁止,结果过总纲即可。注意 kit 的面板和按钮底图把大圆角、双层边画死在九宫格贴图里,改尺寸收不小(总纲附录);用 kit 底图做出来读成"圆滚滚、双层边"就没过红线第 7 条,这时换底图还是另找办法,先和勾哥对一下。
- **`Core.UI.PressScale`**(已入库 `Assets/Scripts/Core/UI/PressScale.cs`):kit 按钮是纯 Image 无按压反馈,新按钮一律挂上;unscaled time,timeScale=0 下照常工作。
- **Canvas 参考**:kit 屏用 kit 自身 CanvasScaler **1080×2340 / Match 0.487**,measured px 1:1(详见 ui-placement 真源 `UI_Placement_Rules.md`,2026-06-14 RATIFIED;旧的 1440×2560 对 kit 屏已废弃)。

**字体拍板(2026-10-12 已被 Saira 定稿取代,见第二步"字体与字色";以下仅适用于未迁移的旧屏)(2026-07-06 修订二分制,取代旧的"全场 CookieRun")**:**Title/大数字 = CookieRun Black Outline 54 SDF**;**其余一切非 title 文字 = `Cairo_Line_Black SDF`**(`GUI Pro-SuperCasual/ResourcesData/Fonts/`);两者都必挂 CJK fallback 链,UI 文案一律英文,字号下限对齐 HomeScreen 基线(见 CLAUDE.md「UI 字体铁规」)。已知欠账:死亡三屏(UIRevivePopup / UIDeathSummaryPanel / UIMineDefeatPanel)与 battle_endreward 设计稿字体口径待按二分制核一遍;新屏一律照二分制,别再手搓 Sen。
