---
name: ui-truth-reclaim
description: 把一个 Extraction UI 屏从"四个作者抢着写同一批 RectTransform"收成单一真源——prefab 是唯一真源、运行时零坐标写入、场景零 override,收完就能所见即所得手摆。Trigger — "收屏" / "把这个屏收成真源" / "UI 真源" / "所见即所得" / "手摆 UI 被回写" / "改了又弹回来" / "这个屏改了又弹回来" / "override 太多" / "prefab 拍平" / "reclaim screen truth" / "single source of truth for a screen". 机械活走 `Tools/UI Truth/Reclaim Window`;本 skill 只管判断题和流程。
---

# UI Truth Reclaim (Extraction)

一个屏"改了又弹回来",根因永远是同一批 RectTransform 有多个作者:外层 prefab 的序列化值、嵌套 prefab 的自己一套、场景实例上的 override、以及运行时脚本每次 `OnRefresh` 跑一遍的 normalize 链。四个作者互相盖,谁最后跑谁赢,于是手摆没有意义。**收屏 = 把作者砍到一个**:prefab 是唯一真源、运行时一行都不写这棵树的 RectTransform、场景实例零 override。收完之后 Prefab Mode 里拖出来的就是实机的样子。

机械活已经有 Editor 工具,菜单 `Tools/UI Truth/Reclaim Window`,按钮依次 Dump / Bake / Revert Scene Instances / Disable Layout Groups,另有 Diff 和 Open Prefab Env;只读审计走 `Tools/UI Truth/Audit All Screens`,输出 `Temp/ui-truth/audit.md`,五列 = 代码写坐标数 / 场景 override 净数 / 嵌套 prefab 及其 override / 启用中 LayoutGroup 数 / 活 builder 菜单数。**本 skill 不重复工具内部实现**,只写工具替你决定不了的那部分:哪些代码该删、哪些必须留、什么算收干净。

## 什么时候用、什么时候不用

用它的信号是**回写**,不是丑:手摆的位置下次进 Play 弹回去、prefab 里看着对进场景全歪、场景 diff 里几百条 `m_AnchoredPosition`、同一个数字在运行时代码和 editor builder 里各写了一遍。

单个属性微调(挪一个按钮、改一档间距)不要收屏,走 `ui-placement` 直接改;收屏是一整天的活,只有当你确认"改不动"是结构性的才开。新屏更不用收——一开始就按真源规矩建(prefab 里摆死、运行时不写坐标、不在场景实例上拖),收屏是给历史债还账的。

## 开工前必读的三个真值

**先跑 Audit,看这个屏的五个数。** 没有这五个数就动手 = 盲改。代码写坐标数决定要删多少方法,场景 override 净数决定 Revert 的规模,嵌套 prefab 那列决定要不要 unpack,LayoutGroup 数决定有几个打架点,活 builder 菜单数决定收完之后谁还会来冲掉你(退役的 builder 带 `(retired)` 前缀,不算)。

**画布口径:HomeScreen 主 canvas(`UICanvasLayerManager`)是 ScaleWithScreenSize / 1440×2560 / MatchWidthOrHeight / match = 0**,不是 0.5。match 0 是纯跟宽,所以 1080×2400 实机上 scaleFactor 0.75、画布逻辑尺寸是 1440×3200 而不是 1440×2560。任何写死的绝对 y 坐标在不同屏比例下都不等价——这是"同一批数在不同机器上对不齐"的结构性原因。开 UI prefab 单独编辑前确认 `ProjectSettings/EditorSettings.asset` 的 `m_PrefabUIEnvironment` 指着同口径的环境场景(`Assets/Scenes/Editor/PrefabUIEnvironment.unity`),否则 prefab 里量的坐标是假的。

**看不见就别猜:Coplay 的 `capture_ui_canvas` / `capture_scene_object` 对 screen space canvas 出黑图。** 截图两条路:Screen Space - Camera 的 canvas 在 Play 里用 `execute_script` 把 `canvas.worldCamera` 渲到 RenderTexture 再 `ReadPixels` 落盘;Overlay 的只能让人按 F8。

## 流程

**1. Audit(工具)。** 跑 `Tools/UI Truth/Audit All Screens`,读 `Temp/ui-truth/audit.md`,确认目标屏值得收、并记下五个数作为收工时的对照基线。

**2. 派 executor 做静态审计(模型判断 + 子 agent)。** 这一步纯只读,不启 Unity,适合派出去。要问四件事:哪些方法在写这棵树的坐标(逐方法逐行号,并标出每一行是布局还是业务);LayoutGroup 清单(挂在谁身上、参数、当前 enabled、和哪段代码抢同一批子件);谁引用这个 prefab(包括 editor builder 的反向引用和意料之外的中间工作件);以及那些 `public` 几何常量的消费者是谁。审计报告不给结论就白派——要的是"可切开性"判断,不是行号堆。

**3. Play 里 Dump before + Bake(工具)。** 进 Play,让这个屏完整跑完一遍它的 normalize 链(即所有作者都写完、画面已经是最终态),此时 Dump 一份全子树基线,然后 Bake——把运行时树整棵烤回 prefab 资产。烤出来的 prefab 里的坐标就是实机最终坐标,从此不用心算"运行时会把它挪到哪"。嵌套 prefab 在这一步被 `UnpackPrefabInstance(Completely)` 拍平成普通子树。**注意 Play 内对场景实例的 unpack 退出 Play 就丢,只有写到 prefab 资产上的是真落盘**——所以验收 Bake 是否成功要退出 Play 后去读 `.prefab` 文件本身。

**4. Revert 场景实例(工具)。** 把场景里那个实例的 override 清干净。收干净的标志是 `m_Modifications` 只剩 Unity 强制给每个实例根 transform 保留的那组(m_Name / pivot / anchorMin/Max / sizeDelta / LocalPosition / LocalRotation / anchoredPosition / EulerAnglesHint),而 `objectOverrides` / `addedGameObjects` / `removedComponents` / `addedComponents` 全为 0。

**5. 删运行时布局代码(模型判断,本 skill 的核心,见下一节)。** 工具帮不了你,这一步靠读代码分类。

**6. 关掉打架的 LayoutGroup(工具 + 判断)。** 判断哪些该关见坑清单;工具负责关之前先抄子件实测坐标。

**7. Play 验收:Diff 0 + 截图对照。** 重进 Play,Dump after,跑 Diff 比对 before/after(按路径匹配,比 anchorMin/anchorMax/pivot/anchoredPosition/sizeDelta 和 activeSelf)。目标是 diffCount 0;有差异必须逐条解释清楚才算过(隐藏节点下 TMP 不生成 SubMeshUI fallback 这类节点数差异无害,但要写明白)。截图前后肉眼对照一遍——Diff 只看几何,看不见颜色、图标、文字。

**8. commit(不 push)+ 交接文档。**

## 删代码的判断规则

把每一行分成三类,不是两类。**"是不是写 RectTransform"只是第一刀,第二刀是"这件事每次刷新会不会被别人重写"**——这一刀漏了,删完实机就出鬼。

**能烤进 prefab、跟着一起删的**:静态摆位(anchor / pivot / sizeDelta / anchoredPosition / offsetMin/Max / localScale 的一次性钉死)、空槽染色、藏 Icon、运行时新建标签节点、sibling 顺序(`SetAsFirstSibling` / `SetAsLastSibling` 严格说是渲染顺序不是 rect,但它在烤出来的树里已经定型了,可以跟着删)、Transition / raycastTarget / 文字样式(font / alignment / autosize / fontStyle / 墨色)。这些的共同点是**只在建树时发生一次**,烤进 prefab 之后没人再改它。

**必须留的**:喂动态内容的 `SetParent`——`BuildStashGrid` 把 widget 挂进 grid、`RefreshPocketSlots` 把新建 widget 拉伸铺满格子,这些管的是运行时才存在的节点,prefab 里根本没有它们;DragGhost 那套拖拽临时物件同理。这两类和页面骨架无关,别顺手删。

**烤不住、必须留一个零 rect 写入的 chrome 方法的**:被别的 widget 自己每次刷新重写的东西。真实案例——`UIUniversalItemSlotWidget.ShowEmptyState()` 每次 `RefreshSlot` 都会把自己的分类占位图标(`Icon` 子节点)重新点亮、把 `_slotLabelText` 按装备状态 SetActive 并把文字写回内部名("Clan" 被写成 "ClanGear")。这是**每帧刷新级的动态行为**,你烤进 prefab 的状态会被 widget 自己盖掉。所以补一个 `ApplySlotChrome()`,在 `RefreshEquipmentSlots()` 末尾调一次,**只做 SetActive 和 tmp.text,零 RectTransform 写入**——这样既修了鬼,又不破坏"prefab 是布局真源"。判断方法:删之前先想清楚"这个属性除了我还有谁写";想不清楚就删完进 Play 走一遍,鬼会自己冒出来。

**editor builder 反向引用的 public 几何常量:保留,加一行注释说明"仅供 editor builder 引用,运行时不再使用"。** 运行时侧和 editor 侧读同一批数字各写一遍,你只砍运行时那一遍;直接删常量会连带编译不过。同理,别去动同一批常量的其他消费者(别的页面可能还在用)。

## 坑清单

`LoadPrefabContents` 一加载就会在预览场景里重跑一遍布局,把 HLG/VLG 驱动的子件打回 (0,0)——因为这些子件的序列化坐标本来就全是 (0,0),位置是组算出来的。所以**关掉一个还在生效的 LayoutGroup 之前,必须先把它子件的实际渲染坐标抄下来再写死**,否则保存出来的 prefab 里子件全叠在一起。工具已经内置这一步,但你要知道为什么,免得看到工具在关组前先 Dump 一遍以为是多余的。

打开 HomeScreen 场景,某个受 ContentSizeFitter 驱动的节点会自己冒出一条 `m_SizeDelta.y` override。那是 Unity 自己的布局系统写的,不是回归,别当成收屏失败;不想让它进 diff 就别在开完场景后随手 Ctrl+S。

TMP 的 `m_TextStyleHashCode` 不是 churn 根因。prefab YAML 里那几百行 `TextStyle` 是 `TMP_Text` 的内置序列化字段,有多少个 TextMeshProUGUI 就有多少条,不是某个组件在编辑态回写。真正会在编辑态跑代码的是 `[ExecuteAlways]` 的组件——`SafeArea` 的 `Update()` 无护栏地写 `anchorMin/anchorMax`,那才是场景级 churn 的可信来源。追 diff 先查 `[ExecuteAlways]` 清单,别追 TMP。

LayoutGroup 分两类,处理方式相反。**管动态内容的保持开**:Grid + ContentSizeFitter(格子数随物品变)、tab 条、资源条、按钮行、preset chip 行——关掉反而会坏。**静态容器上的关**:页面骨架的 Vertical/Horizontal 容器,它们只是在跟你的手摆抢同一批子件,烤完之后没有任何存在意义。判断标准是"这个组的子件数量会不会在运行时变",不是"它看起来重不重要"。另外静态审计报告里写的 LayoutGroup 状态可能是老嵌套件里的,烤平之后有些组件压根不存在了——以烤后的 prefab 为准。

**验收要覆盖不止一种数据态。** 空仓库和满仓库是两棵不同的树:满仓库才会暴露 grid 溢出和 ContentSizeFitter 的行为,空仓库才会暴露空槽占位图标和标签那类 chrome bug。只测一种态的 Diff 0 不算数。

`Assets/Prefabs/UI_MiddleWork/BlankParent.prefab` 这类中间工作件会是意料之外的第五层引用——它里面可能有一个指向目标 prefab 的 PrefabInstance,带着一堆布局 override。它不在生产路径上,收屏时不用管,但收完之后它多半已经悬空/失配;要么单独确认它是废弃件删掉,要么在交接文档里写明,免得后人打开看到一堆红以为是你搞坏的。

## 重绑引用

Dump 出来的 JSON 里有 `panelRefs.fields` 数组,把面板脚本上每个序列化对象引用字段名对应到它当时指向的完整层级路径,格式是 `{"field":"_weaponSlot","type":"UIUniversalItemSlotWidget","target":"MetaUIRoot/.../Upper/EquipmentSlotsContainer/UIUniversalItemSlotWidget"}`。以后重做布局把节点搬了家、Inspector 里冒出 None,照这份表按路径找回节点重新拖上去。**别信字段名去猜 GameObject 名**——槽位的 GameObject 名往往就是原始类名带序号(`UIUniversalItemSlotWidget` / `UIUniversalItemSlotWidget (1)` / `UIUniversalItemSlotWidget (2)`),不叫 WeaponSlot / HelmetSlot / ArmorSlot 这种一眼能对上的名字。收屏前先把 Dump 存好,这份表是唯一的还原凭据。

## 收尾

commit,不 push。交接文档落到 vault `05 - 开发任务/`,要写清楚:真源 prefab 的绝对路径、怎么编辑(Prefab Mode / in-context,别在场景实例上拖)、每个 LayoutGroup 现在是开是关以及为什么、删了哪些方法、留了哪些以及理由、重绑引用怎么查、以及所有已知的悬空引用和没处理的欠账。

**收干净的判据 = audit 五项全零。** 代码写坐标数 0、场景 override 净数 0、嵌套 prefab 0、跟手摆打架的 LayoutGroup 0、会冲掉手工 refine 的活 builder 菜单 0。任何一项非零都要在交接文档里写明为什么留。

**新屏门禁**:代码写坐标数、场景 override 净数、嵌套 prefab 三个数从第一天就必须是零。守住这三个数,以后就没有屏需要收。

摆位规矩看 `ui-placement`,Play Mode 验收看 `playmode-verify-iterate`。
