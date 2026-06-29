# 翼德 · 摆 UI(ui / 摆UI / 摆界面 / 调界面 / 改UI / 弄个面板·弹窗·HUD / 对齐)

在 Unity 里把 **uGUI** 摆对 / 对齐 / 重新搭建,靠三件套:**截图自检循环 + 锚点纪律 + 事件接线**。本文件是**通用执行纪律**,适用于任何 uGUI 项目;**项目专属的东西(参考分辨率 / UI 套件 / 字体 / 安全区组件 / 画布层 / 具名 widget)一律"探测"出来,绝不写死**。
> 前提:假设项目已接 **Coplay / Unity MCP**(把关与验证以引擎事实为准)。没接 MCP 时明说"只能凭文本猜、没在引擎里验过",别假装跑过。
> **优先级**:若当前项目已挂专属 `ui-placement` skill(如 Extraction)→ **以那个 skill 为准**,本 action 仅是没挂 skill 的项目的通用兜底,别两套并行。

## 0. 先读项目约定,再动手(别拿一个项目的习惯套另一个)
按顺序拿"这个项目怎么做 UI"的真值,**项目本地约定永远覆盖本文件的通用值**:
1. **yide 项目档案**:读 `~/.yide/projects/<当前项目>.md` 的「🎨 UI/UX 设计预设」(屏幕方向 / 参考分辨率·安全区 / UI 框架 / 美术基调 / 控件约定 / 确认线稿)+ `unity-context` 技术事实。
2. **项目本地 UI 规范**:若项目自带 UI 约定(`.claude/skills/` 下的 UI skill、UI 设计文档、`CLAUDE.md` 的 UI 段、组件选型表)→ **读它并以它为准**,本文件只当通用底座。
3. **引擎探测真值**(别猜):从场景里任一 Canvas 读 `CanvasScaler` 的 `referenceResolution` / `matchWidthOrHeight`;搜项目的 SafeArea 组件(驱动自 `Screen.safeArea` 的那个);搜截图 / 冻帧 marker 机制(见 §1)。
4. 预设里**缺关键项**(尤其屏幕方向、参考分辨率、确认稿文件夹)→ 用 `AskUserQuestion` 问勾哥一次,**写回项目档案**(学一次以后就有);拿不准别瞎编(红线②)。

## 1. 看结果:Coplay 的 capture 工具对 screen-space UI 是**瞎的**
`capture_ui_canvas` / `capture_scene_object` 走离屏相机 / RT,**渲不到 Screen Space(Overlay & Camera)的 canvas → 黑 / 灰图**。这类项目 UI **别信它**。用两条通道:

**A. 看像素 = `ScreenCapture.CaptureScreenshot` → `Read` 那张 PNG。**
- 抓最终合成帧(所有 UI 层)到磁盘文件;**与 MCP bridge 解耦**(进 Play 掉 bridge 也读得到)。
- **只在从游戏循环调时才写**(Play 中的某个 MonoBehaviour);从 `execute_script`(editor 上下文)调会**静默不写**,且要有真实渲染帧(Boot/loading 不写)。
- 项目若有**冻帧 / playtest marker**(如 ER 的 F8 PlaytestMarker)就直接用它;它本质就是这个 API。

**B. 数值校验几何 / 状态 = 在 LIVE Play 里 `execute_script`。**
- 读真值:`Time.timeScale`、目标 widget 的状态标志、`CanvasGroup.alpha/blocksRaycasts`、各关键元素 `RectTransform.position`(world)。
- **在屏判据**:显示中的元素必须 `0 < worldPos.x < 参考宽` 且 `0 < worldPos.y < 参考高`(宽高用项目参考分辨率)。x=1744 在 1440 宽下就是飞出右边——flow/timeScale 测试**抓不到**这类 bug。
- 不能截图时这是结论性手段。**说"修好了"之前必做**:flow 测试(timeScale 开关)通过 **≠** 面板渲对。

## 2. 改 UI 用 `execute_script`(最稳),别堆 20 个零散 MCP 调用
单属性微调可用 MCP(`set_rect_transform` / `set_property` / `create_ui_element` / `set_ui_text` / `parent_game_object` 等);**复杂改动写一个 C# 文件**(class + `public static string Method()`)用 `execute_script` 跑——原子、可复现:
- **稳健找对象**:`FindObjectOfType(type)`(只找 active)或走 `SceneManager.GetActiveScene().GetRootGameObjects()`(含 inactive 根)。`GameObject.Find(path)` 找不到 inactive / 路径错——隐藏面板别信它。
- **跨程序集解析类型**:遍历 `AppDomain.CurrentDomain.GetAssemblies()` + `asm.GetType("Namespace.Type")`,别假设 `Assembly-CSharp`。
- **写 `[SerializeField]` 私有**:`var so = new SerializedObject(comp); so.FindProperty("_field").objectReferenceValue = target; so.ApplyModifiedPropertiesWithoutUndo();`。
- 临时 `.cs` 放**项目根**(不在 Assets 下,免 domain reload),跑完删。

## 3. RectTransform —— 高发坑
- **stretch rect 上绝不设 `localPosition`**:会污染 `anchoredPosition`、把整棵子树顶出屏幕。填满父级:`anchorMin=(0,0); anchorMax=(1,1); pivot=(0.5,0.5); offsetMin=offsetMax=Vector2.zero;`——`localPosition` 别碰。
- **面板默认隐藏出厂**:序列化 `CanvasGroup` alpha=0 / interactable=false / blocksRaycasts=false;别**只**靠运行时 `HideImmediate`(它跑之前那几帧会漏面板)。
- **重父级只有新父 rect 匹配时才保持世界布局**:移进某层后按上面重置为填满,再确认子元素 worldPos 在屏内。
- **"active" ≠ "可见 / 正确"**:确认 worldPos 在屏界内,不止是 GameObject active。

## 4. 锚点与布局:结构化操作,别手算
- center / edge-pin 用 **anchor preset**,别算绝对 `anchoredPosition`。
- 行 / 网格 / 列表用 `Horizontal/Vertical/GridLayoutGroup` + `ContentSizeFitter`;**静态布局优先固定 RectTransform**(Layout Group 子项一变就 rebuild),动态内容才用 Group。
- **每个元素锚到自己那条屏边 / 角**,跨比例才不漂。
- **一帧布局抖动**(嵌套 Group/ContentSizeFitter 在你读取 / 截图那帧没结算,尤其填完列表或 `SetActive(true)` 后):别赌"下一帧自己会好",内容变更后立刻 `LayoutRebuilder.ForceRebuildLayoutImmediate(rect)`。**"截图里错、回放却对" = 未结算的 rebuild,不是 flake。**

## 5. 多分辨率
- `CanvasScaler` = Scale With Screen Size;`referenceResolution` 与 `matchWidthOrHeight` **从项目预设 / Canvas 真值读,别写死**(每个 canvas 的 match 可能不同,逐个确认)。
- 选一个基准比例,沿单轴扩展;几个目标比例都用 §1 的 PNG 复查(一个比例完美、换个就漂是手游 UI 头号失败)。

## 6. 安全区(刘海 / 挖孔 / 手势条)
- **别硬编码像素 offset**。用项目的 SafeArea 组件(驱动自 `Screen.safeArea`)——没有就提示项目缺、别自己造一个临时的。
- close / back 按钮 + tab bar 必须在安全区内;Background 满屏不 inset。

## 7. 行为接线:照项目**既有**的事件 / 中介约定(别造 MVVM)
**UI 反映状态;不轮询逻辑去推 UI,逻辑也不反向戳 UI。** 先摸项目现有打法照着来,别另起一套绑定层:
- **订阅而非轮询**:widget 监听事件、在回调里刷新自己。优先订**所属 service 自己的事件**,再到**项目的全局事件总线**。
- **订阅 / 退订成对**:`Start`/`OnEnable` 订,**`OnDestroy` 必 `-=`**(连 `DOTween` 的 `.Kill()` / `transform.DOKill()`)。漏退订的死 widget = "改 A 崩 B"那类隐性耦合。
- **async 依赖 late-bind**:service / 单例在你 `Start` 时可能还没生成(玩家 / 角色常异步 spawn)→ 每帧 try-subscribe 直到拿到,别在 `Start` 缓存就假设它在。
- **子面板经面板根中介转发**,不互相直连、不直接戳 service:子面板向上抛意图事件,根面板路由到 service 并编排显隐。
- 唯一被许可的"轮询" = 基于单一真值的自愈门(如按 `Time.timeScale` 决定按钮是否可点)——刻意为之,别拿去做通用状态同步。

## 8. Juice = 美术,不是生成代码
gradient / metallic / glow 来自套件的 9-slice 精灵(uGUI 没原生 box-shadow / gradient)。你管:layout、层级、state swap(normal/pressed/disabled)、`DOTween` 动效。效果精灵从项目套件里拿,别想"用代码画出光泽"。

## 9. 视效重做到"成品级"(通用方法论;项目本地若有视效 skill 以它为准)
> 从 ER 四单实战(Battle Pass / Leaderboard / 签到 / 领奖弹窗)蒸馏的**通用内核**;项目专属数值(kit 路径 / 组件家族 / 字体 / 配色)一律探测或读本地 overlay。

**配方提取法(核心,严禁肉眼猜数值)**:
1. kit 的 **preview 截图只用来"选方向"**(找同功能参考);
2. 真正的施工图 = **dump kit 自带的同名 demo prefab**:临时 editor 脚本递归打印每节点 `name / anchoredPosition / sizeDelta / anchors / rotation / Image(sprite, type, #RRGGBBAA) / TMP(text, size, color) / activeSelf` —— kit 作者自己的 tint / sliced·tiled / inset / 字号,照抄;
3. **素材清单靠 GUID 反查**:grep prefab 里的 `m_Sprite guid` → 反查 `*.png.meta` → 该界面全部 sprite 一张不漏;
4. **素材定性靠像素采样**(读 PNG 中心 / 边缘像素):中心 A=255 且白 = **可染色实心基底**(状态色全靠 tint 它);中心 A=0 = **描边框**;`.meta` 的 `spriteBorder` 非零才可 Sliced,光效类只能 Simple;
5. **尺寸换算**:kit demo 基准分辨率 → 项目参考分辨率,几何与字号**等比缩放**(比例 = 两者宽度之比)。

**视觉语言**:状态即 tint(同一张白 sprite 换色表达 已完成/当前/锁定);层叠固定序 `Bg(tint) → 高光/渐变/底纹 → 描边 Border → Glow → 图标 → 文字`(z 序=创建顺序);**复用 kit 既有组件家族**保全游戏一致,新界面先问"哪个家族最近"而不是发明新皮;"当前/可点"项必须**活**(focus 描边 + 特效组 + 呼吸 scale)。

**动效骨架(DOTween)**——揭示三段式:① 光效 ramp `alpha 0.2→1 + scale 0.55→1.1, 0.6s OutQuad`;② 主体 punch `scale 0→1, 0.4s OutBack`;③ 内容 stagger `每项 OutBack 0.38s,间隔 0.12-0.14s`,落位时各自 glow 闪一下转 yoyo 脉冲。持续层:旋转光圈 `DORotate(-360, 8-10s, FastBeyond360, Linear, Loops(-1, Incremental))`、glow/呼吸 `yoyo InOutSine`、星星错频缓旋。纪律:全 `.SetUpdate(true)`;tween 全记账,Hide/OnDestroy 统一 `Kill()` 并复位;列表入场动画只做首屏前 ~10 个。**亮光层之上才建旋转光圈/星星**(否则被亮区吃掉);dim 不够黑光效不炸(≥0.9)。

**工程化**:builder 写进 editor setup 脚本 + `Rebuild` 菜单(可一键重建);prefab 资产**同路径覆盖**保 GUID 引用不断;重建后 grep 日志确认零 "sprite/property not found"。

**验证特技**(在 §1 通道之上):动画"在动"的证明 = 间隔 1-2s 截两帧对比角度;**同帧 `Refresh()`+截图会拍到 deferred-`Destroy` 残影**(压扁双份内容)——新帧重拍干净即伪影,别误修;幽灵元素用**二分法**(逐区 `SetActive(false)` 再截)三轮锁定;交付前**全分辨率裁块终检**(整屏缩略图会骗人);**端到端真点击**(`onClick.Invoke()` 走完真实链路)而非静态摆拍。

## 循环 & 硬规矩(每次都走)
1. **Edit Mode 摆放**(Play 里的摆放改动会被丢弃;进 Play 会触发 domain reload 掉 MCP bridge,回 Edit Mode 后重连 / 确认)。
2. 改 → **截图(§1A)或数值验(§1B)** → 对着项目约定自评(对齐 / 间距 / token 色 / 拇指区 / 单一主 CTA / 安全区 / 文字可读 / 层级)→ 修 → 重拍。
3. **多比例复查**:几个目标比例各拍一张。
4. 改完**立刻存场景**(未存的改动会在 Play 载入别的场景 / domain reload 时丢)。
5. 收尾:`check_compile_errors` + 取日志,干净。
- 不文本编辑 `.unity` / `.prefab`(GUID 序列化,易损、费 token)——走 `execute_script` / MCP。
- **说"修好了"之前**:数值 worldPos 在屏 **或** 一张 PNG——**绝不只信 Coplay 的 capture 工具,也不只信 flow-only 测试。**(对应红线:验证后再交付。)
