# 翼德 · 从 Figma 摆 UI（figma / 变体 / Figma落地 / 照Figma摆 / Figma变体）

把 Figma 交付的 uGUI **逐变体**翻成 Unity:Claude 只产**两类东西**——「变体 → 数值对照表」+「状态切换 C# 代码」;**prefab/场景由人摆、走 PR**。面向**商业共享仓、UI 在 Figma 交付、只挂官方 Figma remote MCP** 的项目。

> **和 `ui.md` 的分工(别串）**:`ui`=项目已接 **Coplay/Unity 写权限 MCP**,Claude 在引擎里直接摆 UI + 自己截图验(如 ER）。`figma`=只挂 **Figma 读 MCP** 的共享仓,Claude **不碰引擎、不写 prefab**,只产代码+对照表,人摆人 review。**两者触发词不重叠;ER 那类喊「摆UI/对齐」永远走 `ui.md`,不走这里。**

## 0. 项目适配门（先确认这是哪类项目，别把 ER 那套套进来）
动手前先拿真值，确认当前项目确实属于本 action 适用范围：
1. **读项目档案** `~/.yide/projects/<当前项目>.md`：是否标了「UI 在 Figma 交付 / 只挂 Figma MCP / prefab 走 PR」?若标了「已接 Coplay/Unity 写 MCP、引擎里直接摆」→ **停，转 `ui.md`**。
2. **看当前会话挂了什么 MCP**:只有官方 Figma remote MCP（`https://mcp.figma.com/mcp`）、没有 Unity 写权限 MCP → 属于本 action。两者都没有 → 明说「没挂 Figma MCP，只能凭你贴的截图/数据猜、没在 Figma 取过」，别假装取过。
3. **档案里没记过项目类型** → 用 `AskUserQuestion` 问勾哥一次（「这个项目走 Figma 交付+人摆 prefab，还是引擎里直接摆?」），**把答案写回项目档案**，学一次以后就有。拿不准别瞎编（红线②）。

## 硬约束（先遵守这一节，再谈别的）
1. **不写 `.unity` / `.prefab`**。只产 C# 代码 + 数值清单；prefab/场景布局/anchor 由人摆。Unity 场景/prefab 是 YAML，AI 直接写 = 绕过 review 造 merge 地狱。
2. **只挂官方 Figma remote MCP**（`https://mcp.figma.com/mcp`，OAuth 登录，Dev/Full 席位），**不挂任何会写 Unity Editor 的 MCP**。
3. **不引第三方/社区 MCP**（如 GLips/Figma-Context-MCP）——会裁数据、个人维护、把 token 当工具参数传 = 凭证泄露面。仓库里不放 personal access token。
4. **能复用不新造**：优先用项目已有 prefab / 组件 / 状态基类，不另起一套。
5. **不碰无关代码**：不改与当前任务无关的代码、不改别人的代码风格。
6. **所有改动走 git / PR**。

## 1. 逐变体取数据（三个 Component Set bug 的直接对策——本 action 的核心）
官方 MCP 对 Component Set 有三个**已确认且静默**的 bug，所以**对每个 variant 节点单独 `get_design_context` + `get_screenshot`，绝不对整个 Component Set 取一次就用**：
- **5a** 组件变成变体集后，`get_design_context` 会丢掉嵌套子节点和 Code Connect 片段。
- **5b** 它返回**默认变体**而不是实例真正的覆盖值，**不报错**——对表格/列表/状态展示**最危险**。
- **5c** 嵌套组件的变体属性不会冒泡到父组件。
> 让人在 Figma 选中要做的 frame/组件，给**指向精确 node 的 link**（不要给附近的父 frame）。逐 variant 节点取，一个都不漏。

## 2. Claude 只产两类东西
- **(a) 变体 → 数值对照表**：每个状态对应的颜色 / 字号 / 间距 / 圆角 / sprite / 文本 / 显隐。落到 `<项目>/QA/figma-<组件>-variants.md`（草稿；交付附**完整绝对路径**，见 give-full-file-path 教训）。**数字由你从 Figma 取的单一数据源照抄，绝不估**（红线④）。
- **(b) 状态切换 C# 代码**：一个状态**枚举** + 每个状态切 sprite/颜色/文本/`SetActive` 的逻辑。
  > 状态机制**按类型选、跟团队既有约定走**，不自创：
  > - 交互态（按下/禁用/高亮）→ `Selectable` 的 Color Tint / Sprite Swap / Animation。
  > - 数据/状态展示（online/offline、锁定、段位）→ 枚举驱动脚本切 sprite/颜色/文本。
  > - 改布局（折叠/展开、空/有内容）→ `SetActive` 切子树 / 切 `LayoutGroup`。

## 3. 一个 prefab + 一个状态组件（不是 N 个 prefab）
把「不同形态」做成**同一个 prefab 上由状态枚举驱动的切换**：既对应 Figma「一个组件多个变体」，又避免在共享仓堆出 N 个难 merge 的 prefab。Claude 只给 (a)(b)，**这个 prefab 由人摆布局+anchor、挂状态组件**。

## 4. 逐状态视觉核对（强制项，不是可选）
**每个状态在 Unity 里截图，对着对应变体的 Figma 截图比，再标完成。** 鉴于 5b 那个「静默返回默认变体」的 bug，这一步在商业项目里**必须执行**：
- **Claude 不许声称「几个状态都对了」**——没逐状态比过就只报「代码就绪、待人核对」，不冒充已验证（红线①）。
- 对照表里每个状态留一行核对位（Figma 截图 vs Unity 截图 → ✅/✗），人点一下才算闭环。

## 资源是独立任务（别混进布局）
图标/图片导成 Sprite 并配好导入设置、字体转 TMP——当成**独立任务**处理，不要混在变体落地里。

## 执行流程（按序走）
1. **人**：在 Figma 选精确 node，拿指向该 node 的 link。
2. **Claude**：逐 variant 节点 `get_design_context` + `get_screenshot`。
3. **Claude**：产 (a) 变体→数值对照表 + (b) 状态切换 C#。
4. **人**：摆**一个 prefab** 的布局/anchor，挂状态组件。
5. **核对**：逐状态截图比 Figma 变体截图。
6. **PR**：代码 + prefab 改动走正常 review。

## 一次性配置（落地前先弄好）
- **官方 Figma remote MCP**：端点 `https://mcp.figma.com/mcp`，需 **Dev / Full 席位**，OAuth 登录。
- **Code Connect（可选，复用组件用）**：需 **Org/Enterprise 计划 + Dev/Full 席位**。⚠️ **Unity/C# 不是 Code Connect 一等公民**（原生 parser 只有 React/HTML/SwiftUI/Compose）→ 走 UI 手动映射或 CLI template files；**先拿一个组件试通再铺开**。此条基于官方文档能力的**推断，未在 Unity C# 项目实测**（红线①，不冒充已验）。
- **WSL 网络坑**：Claude Code 在 WSL、Unity 在 Windows 时 `localhost` 不互通，需开 Windows WSL Mirrored 网络模式；Rider 原生跑无此问题。

## 这个 action 不进大脑
属于插件能力。变体对照表等工作产物落 `<项目>/QA/`，**不进 `~/.yide` 大脑、不进项目证据库**（与 voice/playtest 同理）。
