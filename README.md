# 翼德 🗡️

> 咕鸡为勾哥量身打造的专属 AI 秘书 —— 一个 Claude Code 插件。

## 这是什么 / 为谁做

翼德是给**一个人**(勾哥,Unity 手游程序员)做的私人助手,不是通用工具。它要解决勾哥每天的真实困扰:

- 每开一个新 AI 对话,都要把自己的技术栈、项目背景、喜好重讲一遍;
- 同一个错(编造 API、加屎山、未经同意大改…)被 AI 一犯再犯;
- AI 不懂 Unity 手游的坑,写出掉帧/过时 API/破封装的代码。

**翼德的承诺(Promise):**
1. **记住你** —— 你的身份、风格、规则记一次就牢,以后每个新对话自动 brief,换电脑也认得你。
2. **绝不让你重复踩坑** —— 你纠正过一次的错,记成教训,之后任何对话都不再犯(Claude Code 里还能硬拦)。
3. **帮你把关 Unity** —— 写 C# 时按手游 best practice 盯着,发现隐患就提醒,绝不擅自大改。
4. **轻** —— 按需加载,不常驻、不啰嗦,不拖累 Claude 本身的聪明。

## 安装

```text
# 在 Claude Code 对话框里(不是系统终端)输入:
/plugin marketplace add guxipi/yide
/plugin install yide@guji-tools
```
重启 Claude Code → 翼德自动打招呼 → 说一句 **"翼德,磨合一下"** 走几道选择题即可。
(不便用 GitHub 时,也可解压发行包后 `claude --plugin-dir ./yide`,但仅当次会话。)

> **开启自动更新(强烈建议,一次性)**:`/plugin` → Marketplaces → 选 `guji-tools` → 打开 **Auto-update**。第三方插件源**默认关闭**,不开就永远不会自动更新。开了之后开机自动拉最新、提示 `/reload-plugins` 热加载。手动更新则:`/plugin marketplace update guji-tools` + `/reload-plugins`。
> ⚠️ 注:翼德"静默更新"指的是**大脑默认(红线/charter 等)**在插件更新后自动生效;**插件代码本身的更新**走 Claude Code 的市场机制(上面那条),**模型/翼德无法代跑** `/plugin`。

## 用法:直接喊"翼德 + 动作"(自然语言)

> 翼德是插件,**做不到裸 `/yide`**(插件命令一律带命名空间)。所以:**最省事是用中文喊**——"翼德 磨合""翼德 记一下…""翼德 整理";要打命令则是 **`/yide:yide <动作>`**。下表 `<动作>` 是这些动作词。

> 两个 `yide` 是**插件名 : 技能名**(你把插件和技能都叫了 yide)。`/yide:yide` 只在**装了该插件的机器**上有效;裸开发源码(没 `/plugin install`)打它会报 `Unknown command`。

**全部 16 个动作**(`<X>` 就是 `/yide:yide X` 里的那个词):

| 动作词 `<X>` | 也可这样喊(自然语言) | 干什么 |
|---|---|---|
| `onboard` | 磨合 / 初始化 / 建大脑 | 首次访谈(选择题)建你的个人大脑;新设备自动认同步盘大脑 |
| `record` | 记一下 … / 记 / 这错别再犯 / redflag | 把一次纠错记成教训,下次绝不再犯;攒够升红线、可升级硬拦截 |
| `brief` | 简报 / 导出 / 给别的AI | 生成可复制简报,贴进别的 AI(ChatGPT / Gemini…) |
| `consolidate` | 整理 / 清理 | 整理记忆:合并重复、修正过时、升级反复犯的错 |
| `update` | 更新 / 迁移 | 插件更新后安全迁移:补新默认,**冲突先问、绝不覆盖你的数据** |
| `qa` | 测 / 测试 / test | 聚焦测试计划 / 强制 bug SOP / 跑测+三查 / 安卓真机取证 |
| `review` | 评审 / 挑刺 / 审代码 | 对抗式评审:新上下文 subagent 只看 diff、只挑正确性/耦合(不挑风格) |
| `note` | 笔记 / 随手记 / 想法 | 随手记:录入 / 整理手机扔来的笔记 / 查询 |
| `gaotapi` | 搞他皮 / 蒸馏 / distill | 把某人/某块蒸馏成能召唤的**命名专家**(如 maxim),含 IP/诚实护栏 |
| `experts` | 专家 / 用 <名> / 会诊 | 列出/召唤专家(`use maxim`)/ 推荐 / 多专家会诊 |
| `prompt` | 提示词 / 存这条 | prompt 库:自动静默存 / 看 / 自动召回 / 升级成命令 |
| `plan` | 计划 / 闭环造鸭 / 造鸭 / 回滚 | 闭环造鸭:几句话 → 对齐(镜头+线稿)→ 造 → 引擎验到全绿 → 交付可玩切片;失败一键回滚 |
| `mockup` | 线稿 / wireframe / 画界面 | 出可批注 HTML 线稿确认布局(点区域→弹框→一键「复制反馈给翼德」) |
| `ui` | 摆UI / 调界面 / 对齐 | 在 Unity 里摆 / 对齐 / 搭 uGUI(已接 Coplay/Unity MCP,引擎里直接摆):截图自检循环 + 锚点纪律 + 事件接线(通用,自动读项目约定) |
| `storyboard` | 分镜 / 运镜 / 分镜头 | 从描述出俯视分镜 HTML(取景框+运镜箭头+空间元素)确认运镜/空间/时序,可手绘批注导出 PNG |
| `figma` | 变体 / Figma落地 / 照Figma摆 | 从 Figma 逐变体落地 uGUI(共享仓只挂 Figma MCP):逐 variant 单独取数据避三 bug → 只产对照表+状态切换 C# → 一个 prefab+状态枚举(人摆走 PR)→ 逐状态视觉核对 |
| `docs` | 项目文档 / 吸收文档 / 文档管理 | Confluence 导出/增量 → 蒸成精简 `CLAUDE.md`(每次会话自动读)→ 7 天懒同步 |
| `playtest` | 冻帧标注 / 标注 / 试玩反馈 | Unity 按 F8 冻帧 + 抓命中元素/上下文 + 录音/打字 → 本地转写 → 带定位问题清单 → 联合优化回流 |
| `voice` | 语音 / 语音输入 / 听写 / 口述 | Rider 终端全局热键(默认 Ctrl+F9)说中文 → 复用 Google STT 流式转写 → 自动键入当前光标(Claude Code 输入框),审一眼再回车(Windows) |
| `zhanji` | 战绩 / stats | 看连斩 / 打卡链 / 三国称号(extraction 个人项目彩蛋) |

说"翼德 记一下…/简报/整理/测试/蒸馏/用 maxim/起个计划"等自然语言也能触发。单入口 + 按需加载 = 不占上下文。

> 翼德小报告(发作者,可关):翼德会把勾哥使用中的**汇总信号**(主题+计数,**不含代码/原文/密钥**)整理成"✅ 已自动处理 / 🔧 需手动优化(附最佳做法)"发给作者咕鸡;首次明确告知勾哥,"翼德别看了"即关。

## 数据安全:代码 / 数据分离

- **代码**(hooks、lint、actions)在本仓库 → `git push` 后 `update` 即生效。
- **你的数据**(教训、身份、笔记、自定义红线)在 `~/.yide` → **更新永不覆盖**。
- 跨设备:把 `~/.yide`(或指针指向的同步盘文件夹,Google Drive / git)同步过去即可,免重新磨合。

## 它是怎么运作的(原理,尽量说人话)

| 机制 | 说人话 |
|---|---|
| **两层"绝不再犯"** | 软的一层:把规则塞进每次对话里提醒 Claude(到处都管用)。硬的一层:Claude Code 里有个"门卫",在动手前**真的拦下**危险操作。同一个门卫还会**自动放行只读的安全操作**,省得你一直点同意——危险的永远先拦。 |
| **工作准则 charter** | 开场常驻 4 条最高优先级准则(能求证就别猜 / 宁问勿错 / 做功能先调研 / 用架构总监的眼光),专管"该怎么做";红线专管"不许做"。 |
| **Unity 把关** | 你写/改 C# 后,翼德自动扫一遍(热路径性能、过时 API、序列化生命周期、资源卫生),只提建议、不擅自改;跟这个文件相关的旧教训也一并冒出来。 |
| **项目信息探测** | 进 Unity 项目自动读出版本 / 渲染管线 / 输入系统 / Addressables / 脚本后端,不用你告诉它。 |
| **记忆沉淀** | 隔一阵自动整理记忆(开会话时若距上次超过一天就理一次),电脑关机也不丢。 |
| **保持轻** | 教训用"源文件 + 索引"管理,开场只带身份 + 红线 + 条数,不会越用越臃肿;还有个"称重器"盯着开场注入别超标。 |

## 翼德 vs Claude(它俩的分工)

> 一句话:**翼德 = 记忆 + 触发 + 纪律(它本身不思考);Claude = 当场的脑子(负责思考、推理、写代码)。**

翼德是一堆纯文本 + 固定规则的小脚本,自己不动脑,只机械地做三件事:

| 翼德的三件事 | 具体是 |
|---|---|
| **喂** | 在对的时候,把对的记忆塞给 Claude:开场带上你的身份 + 红线 + 工作准则;改某个文件时,把跟它相关的旧教训顶出来;你打字时,召回你存过的好用 prompt。 |
| **拦 / 放** | 危险操作直接拦下来;只读的安全操作自动放行,省得你一直点"同意"。 |
| **提醒去学** | 到点了,提醒 Claude 去记教训、整理记忆。 |

所以会话里那份"聪明"始终是 **Claude** 的;翼德的价值,是**让这份聪明每次都带着"你是谁、踩过哪些坑"上场,并且把结果记下来**——没翼德的 Claude 是每次从零开始的聪明陌生人,有翼德的 Claude 越用越懂你。

## 结构

```
yide/
├── .claude-plugin/{plugin.json, marketplace.json}
├── SKILL.md                 # 单一 /yide 入口(派发)
├── skills/                  # 翼德托管的项目层 skill(自动发现,/yide:<名> 命名空间;v0.30.0 起)
├── actions/                 # 按需加载:onboard/record/brief/consolidate/update/qa/review/note/distill/experts/prompts/plan/mockup/docs/playtest/zhanji
├── hooks/hooks.json         # exec 形式(Windows-safe)
├── scripts/*.js             # 全 Node,无第三方依赖
├── templates/brain/         # onboard 时复制到 ~/.yide
├── templates/qa/            # bug SOP / 报告模板 / EvidenceCapture.cs
└── integrations/            # 可选:telegram(随手记)/ unity-mcp(看 Editor)/ android(真机取证)/ confluence(项目文档)/ playtest-capture(冻帧标注+本地转写)/ voice-prompt(语音喂 prompt)
```

## 跨平台 / Windows
为了在勾哥的 Windows 上不出岔子:hook 用更稳的调用方式(绕开一个已知的路径反斜杠 bug)、文件操作全走 Node、用 `.gitattributes` 锁住换行符。只依赖 `node`(Claude Code 自带),没有任何第三方包。

> 开发者自检(维护翼德时用):`npm test`(逻辑回归)· `npm run audit`(开场注入称重)。

---

## ✅ 验证状态(诚实)
**已验证**(`npm test` 29 用例 / 实跑 / 渲染截图 / 查官方文档):PreToolUse 放行·拦截·adb 门控、resolve 分层去重、索引自愈、charter 注入、注入体量、migrate 加文件、session-health 阈值、线稿/QA 报告 HTML 渲染与交互、`CLAUDE.md` 自动加载机制。

**⚠️ 尚未在真实环境端到端验证**(需勾哥在真机/真项目各跑一遍,验一项划一项):
- 闭环造鸭:几句话 → 引擎里可玩切片(需真 Unity + Coplay)
- 安卓真机 QA:EvidenceCapture + `adb pull` + SOP 报告(需真安卓设备)
- 项目文档管理:Confluence 导出 → 解压 → 蒸成 `CLAUDE.md` → 自动读(需真 Confluence)
- 角色镜头 `use architect` 在真会话能否召唤(需真 Claude Code 会话)
- 一键回滚"整段撤"(需真闭环跑一次)
- Playtest 冻帧标注:Unity 按 F8 冻帧+抓命中元素/上下文 → Google Cloud STT(Chirp 3)实时流式转写(已真机验证)→ 带定位 QA 清单(扫 marker→修复回流待真实 session 验)
- 语音喂 prompt(`voice`):Rider 终端全局热键说中文 → 复用 Google STT 流式转写 → SendInput 自动键入 Claude Code 输入框。**整链需勾哥真 Windows 端到端验**(全局热键捕获 / 麦克风 / 出中文 / Unicode 注入打进终端这四环);代码逻辑就绪,翼德未在真机跑过

> 诚实底线:`node test` 只覆盖"可控的逻辑/文件层";**"模型在真实会话照做 + 勾哥真实环境"这层必须真机验,翼德不冒充已验证。**

## 更新记录 Changelog

### v0.30.0 — 翼德开始 ship 项目 skill(插件托管 + 自动分发)
- **背景**:此前 ER 的项目 skill(playmode-verify-iterate / ui-placement / ui-visual-rework / gaoguang-3d / cloud-code-deploy / feature-development / todo-to-planyway / unstuck-playbook + `server-service-pattern.md`)只活在 **Extraction 仓的 `.claude/skills/`**,跟着那个游戏仓走、别的项目用不到、也不随翼德同步。**它们其实是翼德的"项目层"能力**,该由翼德托管。
- **做法**:用 Claude Code 插件原生机制——`skills/<名>/SKILL.md` 自动发现、命名空间 `/yide:<名>`、user scope 安装 = **在勾哥所有项目自动可用**。无需任何复制/同步脚本,装了插件即得;`/plugin marketplace update guji-tools` + `/reload-plugins` 拉新。
- **迁移**:9 个 skill 全数迁入本仓 `skills/`,布局原样保留(`cloud-code-deploy` 的 `../server-service-pattern.md` 相对引用不破);playmode-verify-iterate 带上最新坑表(NUnit 走 CLI / save_scene 路径坑 / 编辑器活地盘——蒸自旧教训 L-0001/07/09)。
- **隔离**:skill 内容含 ER 专属(SuperCasual / UGS / Extraction 场景),但其 description 仅在对应语境触发,不会在别的项目误触;Extraction 本地副本待插件验证加载后再移除,避免空窗。

### v0.29.0 — `ui` 动作新增 §9「视效重做到成品级」通用方法论
- **来源**:ER 四单实战蒸馏(Battle Pass / Leaderboard / 签到日历 / 通用领奖弹窗,2026-06-12)。ER 本地有完整项目版 skill(`.claude/skills/ui-visual-rework/`,含 SuperCasual 专属配方),**原样保留、优先生效**;本节只收跨项目通用内核。
- **配方提取法**:kit preview 截图只选方向,数值来自 **dump 同名 demo prefab**(节点级 sprite/type/tint/rect/字号照抄);GUID 反查素材清单;像素采样定性 sprite(可染基底/描边框/能否 Sliced);kit 基准→项目参考分辨率等比换算。
- **视觉语言**:状态即 tint、层叠固定序(Bg→高光纹理→描边→Glow→图标→文字)、复用 kit 组件家族、"当前/可点"必须活。
- **动效骨架**:揭示三段式(光效 ramp→主体 punch→内容 stagger)+ 持续层(旋转光圈 Incremental loop / glow 脉冲 / 呼吸);SetUpdate(true) + tween 记账必 kill + 入场动画限量;光效层序与 dim 深度两条踩坑结论。
- **验证特技**:双帧对比证动画在动、同帧 Refresh+截图的 deferred-Destroy 残影鉴别、二分法锁幽灵元素、全分辨率裁块终检、端到端真点击。
- **项目隔离**:零项目写死值;开头声明"项目本地若有视效 skill 以它为准"(ER 即如此)。

### v0.28.0 — playtest 跨项目隔离护栏(与 ER 文件存储区分清楚)
- **背景**:`playtest` 本就按当前项目工作(处理脚本读当前项目 `QA/playtest`、Unity 默认写工程内 `QA/playtest`),非 ER 项目**代码上直接能跑、零改动**。唯一会串的点:Unity EditorPrefs `Yide.Playtest.SessionRoot` 是**全机全局键**,某项目(如 ER)指到共享目录(Google Drive)后,所有项目按 F8 都会写进同一处、混在一起。
- **加护栏(不碰 ER 现有路径)**:① `PlaytestMarker.cs` 每条 marker 落盘时多记一个「来源项目」(工程文件夹名,`ProjectId()`);② `playtest.js` 处理时若发现一场**混入多个来源项目**→ 醒目告警 + 给修复路径(非 ER 项目把 SessionRoot 留空走工程内隔离),单项目则显示来源。纯增量字段 + 一条校验,**ER 旧流程零变化**。
- **文档**:`playtest.md` 加「跨项目隔离(与 ER 区分清楚)」段;`SETUP.md` 在转写设置处标明 SessionRoot 全局键行为 + 多项目标准动作(留空或各指独立目录,别共用)。
- **测试**:回归 + 新增护栏用例(Unity 写来源项目字段 / 混项目告警 / 单项目显示来源)。

### v0.27.0 — `figma` 动作(从 Figma 逐变体落地 uGUI,专供非 ER 共享仓)
- **加**:`figma` 动作(变体 / Figma落地 / 照Figma摆)。面向**商业共享仓、UI 在 Figma 交付、只挂官方 Figma remote MCP** 的项目。核心是绕开官方 MCP 对 Component Set 的**三个静默 bug**(丢嵌套子节点/Code Connect、静默返回默认变体、嵌套变体不冒泡):**逐 variant 节点单独 `get_design_context`+`get_screenshot`,绝不对 Component Set 取一次就用**。
- **只产两类东西**:① 变体→数值对照表(颜色/字号/间距/sprite/文本/显隐,落 `<项目>/QA/`,数字照抄不估);② 状态切换 C#(枚举 + 每状态切 sprite/颜色/文本/SetActive)。**prefab/anchor 由人摆、走 PR**——一个 prefab+状态枚举,不堆 N 个难 merge 的 prefab。
- **逐状态视觉核对为强制项**:每状态 Unity 截图对 Figma 变体截图比,Claude 不许声称「都对了」(防那个静默默认变体 bug)。
- **项目隔离(关键)**:与 `ui` 触发词**零重叠**且 action 开头有「项目适配门」——`ui`=接 Coplay/Unity 写 MCP、引擎里直接摆(如 **ER**,本次零改动);`figma`=只挂 Figma 读 MCP、不碰引擎只产代码。ER 喊「摆UI/对齐」永远走 `ui.md`。
- **边界**:硬约束「不写 `.unity`/`.prefab`、不挂写 Unity 的 MCP、不引社区 MCP(凭证泄露面)」;Code Connect 对 Unity/C# 非一等公民,此条属**官方文档推断、未在 Unity C# 项目实测**,先拿一个组件试通再铺开。
- **顺带**:README 顶部动作表补上 `ui`/`storyboard`/`figma` 三行(此前漏列)。

### v0.26.0 — `ui` 动作(跨项目摆 uGUI)+ 语音多轮打磨
- **加**:`ui` 动作(摆UI / 调界面 / 对齐)。在 Unity 里把 uGUI 摆对/对齐/重建的**通用执行纪律**——「截图自检循环 + 锚点纪律 + 事件接线」三件套。项目专属(参考分辨率 / UI 套件 / 安全区组件 / 画布层 / 具名 widget)**一律探测、绝不写死**,从 `~/.yide/projects/<项目>.md` 预设 + 引擎真值读。**不信 Coplay capture**(对 Screen-Space canvas 是瞎的)→ 改用 `ScreenCapture.CaptureScreenshot` 出 PNG 自读,或 LIVE Play 里 `execute_script` 读 worldPos 做「在屏判据」。沉淀 RectTransform 高发坑(stretch rect 不设 localPosition / 面板隐藏出厂 / 一帧布局抖动 / active≠可见)。前提:项目已接 Coplay / Unity MCP;没接就明说只能凭文本猜、没在引擎验过。
- **加**:`storyboard` 动作扩写 + `templates/storyboard/draw-layer.html` 手绘批注层(俯视分镜上圈画 → 导出 PNG 贴回当反馈);`plan` 接一行,涉及运镜/空间编排时自动走分镜。
- **改 voice(4 轮)**:① 中英混说——`YIDE_STT_LANG` 支持逗号分隔多语言码;② 开机静默自启(`yide-voice-silent.vbs`)+ 按热键时输入框占位提示;③ 浮窗实时 interim 字幕 + 加速出 final;④ 浮窗独立线程 + 焦点恢复 + modifier 释放 + 翼德纠错 + `--selftest`(中途试过 endpointing 提速,因副作用撤回)。
- **范围/边界**:`ui`/`storyboard` 的引擎侧验证以 Coplay / Unity MCP 事实为准;voice 整链仍**需勾哥真 Windows 端到端验一次**,翼德不冒充已验证。

### v0.25.1 — voice 默认热键改 Ctrl+F9
- **改**:语音喂 prompt 默认热键 `Ctrl+Alt+V` → **`Ctrl+F9`**(单手好按、不劫持打字;F8 已被 playtest 占用故避开)。代码默认值 + `.bat` + SETUP/README/SKILL/action 文档同步。撞键则用 `YIDE_VOICE_HOTKEY` 改(如 `<f10>`)。

### v0.25.0 — 语音喂 prompt(Rider 终端全局热键说话 → 自动键入 Claude Code 输入框)
- **加**:`voice` 动作 + `integrations/voice-prompt/`(`yide_voice.py` 常驻守护进程 + `yide-voice.bat` 启动器 + `SETUP.md`)。在 Rider 终端跑 Claude Code 时,光标停在输入框,按全局热键(默认 **Ctrl+F9**)说中文 → **复用 playtest 那套 `stt_google.py`(Chirp 3 流式)**实时转写 → 停录后把最终中文用 **Windows SendInput(KEYEVENTF_UNICODE)** 自动键入当前光标,**默认不自动回车,留你审稿**。停顿 ~6s 也会自动停。
- **复用不重写**:STT 直接拉起 `stt_google.py` 的常驻流式服务(`START\t<wav>`/`STOP` → emit `done`),只把出口从喂 Unity 改成喂终端光标。
- **配置**:`YIDE_VOICE_HOTKEY`(热键)· `YIDE_VOICE_SUBMIT=1`(键入后自动回车)· `YIDE_STT_SILENCE_SEC`(静音自动停,默认 6s)· `YIDE_VOICE_KEEP_WAV`。依赖 `pynput`(全局热键,免管理员)+ 复用 `google-cloud-speech sounddevice` + gcloud ADC 认证。
- **范围/边界**:面向 **Windows**(自动键入用 SendInput)。整链(全局热键捕获 / 麦克风 / Google 出中文 / Unicode 注入打进 Claude Code 输入框)**需勾哥真 Windows 端到端验一次**,翼德不冒充已验证。降级:STT 起不来报原因、照常打字。

### v0.24.0 — Playtest 冻帧标注反馈(Unity 内按 F8 → 翼德直通代码的问题清单)
- **加**:`playtest` 动作 + `integrations/playtest-capture/` + `templates/qa/PlaytestMarker.cs`(运行时)+ `templates/qa/Editor/PlaytestMarkerWindow.cs`(编辑器停靠窗口)。勾哥试玩时按 **F8** → **冻帧**(`Time.timeScale=0`)+ 自动截图 + **抓游戏内状态**(命中的 UI/物体**层级路径 + 来源 Prefab** + 场景 + 分辨率/FPS/版本)+ 录一小段语音;**语音为主、可打字补充**;再按 F8 存成一个 marker。说"**翼德 playtest**" → `scripts/playtest.js` **本地 SenseVoice 批量转写** + 合并打字 + 读截图/上下文 → 翼德出**带定位问题清单**(`现象 → BattleHUD/TopBar/PauseBtn ← PauseButton.prefab`)→ 接 v0.22 **联合优化回流**。
- **为什么比录屏强**:翼德拿到的是**游戏内部状态**(直通脚本/Prefab,不靠看图猜)+ 一条标注 = 一个干净问题包(低噪音)。**标注面板是独立编辑器停靠窗口,绝不遮挡游戏**;打字时**完全不需转写**。
- **中文转写本地化(适配在海外)**:不用 Whisper(中文口语弱);走**本地 SenseVoice / funasr**(`asr_sensevoice.py`,离线、免费、CPU 可跑、自带标点),**不上云、不跨境**。没装 → **降级成只用打字+上下文,不阻断**。
- **铁律**:勾哥只做"按 F8 / 测 / 说或打字 / 再按 F8",其余翼德全自动。
- **隐私**:录麦**全程本地处理、不外传**;不想说话只打字;产物进项目 `QA/playtest/`(`.gitignore`)。
- **反臃肿**:lazy action(零常驻,`npm run audit` 仍 816 tokens)+ opt-in + 无新 hook。`#if UNITY_EDITOR||DEVELOPMENT_BUILD` 包住,不进正式包。测试 31 用例。
- **可选保留**:整段屏幕录屏老方案(`playtest-rec.bat`)默认不启用,专看手感/动效时才用。
- ⚠️ **整条链路(Unity 工具 / 录音 / 本地 SenseVoice 转写)尚未在真 Unity 端到端验证**(见上「验证状态」)。

### v0.23.1 — 修正:自动加载的是 `CLAUDE.md` 不是 `AGENTS.md`
- **修 bug**:v0.23.0 误称"`AGENTS.md` 被 Claude Code 每次会话自动加载"——**错**。官方文档:**Claude Code 只自动读 `CLAUDE.md`,不读 `AGENTS.md`**。已全部改为写 `CLAUDE.md`(要兼容别的 AI 就 `AGENTS.md` + `CLAUDE.md` 用 `@AGENTS.md` 引入)。docs/plan/projects 模板同步修正。

### v0.23.0 — 项目文档管理(Confluence → 项目根 CLAUDE.md,自动耦合开发)
- **加**:`docs`(项目文档管理)动作——把勾哥写在 **Confluence** 的项目文档变成 AI 好用的形态:**首次一键导出空间(免 token)→ 翼德蒸成精简层写进项目根 `CLAUDE.md` → API token 增量保鲜 → 7 天懒同步**。三层:源(Confluence,不动他习惯)/ 镜像(`~/.yide/.cache/confluence/`,不进 git,可重拉)/ 精简层(仓库 `CLAUDE.md`,进 git)。
- **自动耦合开发(不用提醒)**:`CLAUDE.md` 在仓库根 → **Claude Code 每次会话自动加载** → 做功能天然带项目背景;`plan` 的"读 context"含它,要细节自动钻镜像。守则:精简层必须精简(常驻不撑爆),全量细节留镜像。
- **加**:`integrations/confluence/SETUP.md`(傻瓜版:一键导出 / 配 API token);`projects` 模板加「📚 项目文档」段。
- **不引重依赖**:首次走 Confluence 自带导出、增量走免费 REST API;Playwright 仅作以后兜底、不进核心。
- ⚠️ **端到端尚未在真实 Confluence + 真项目验证**(见 README「验证状态」)。测试 29 用例(覆盖文件/路由/逻辑,不含真实环境链路)。

### v0.22.0 — QA 报告可交互手感表 + 联合优化回流
- **加**:`templates/qa/feel-form.html`——QA 报告里"要勾哥定的手感项"做成**可交互**:每项点 👍还行 / 👎要改 / 🤔不确定 + 写一句 → 「📋 提交反馈给翼德」一键复制粘回。
- **加**:**反馈回流闭环**——翼德拿到手感反馈 → 拉 **art-director(数值)+ ui-ux(设计)联合建议、PM challenge** → **最佳优化方案供勾哥定夺** → 勾哥拍板 → 翼德执行(改 config 数值 / 走小闭环)。写进 `qa.md`(F)+ `plan.md`(试玩反馈回流)。
- 报告 HTML 也用了**自适应缩放填满**(和线稿一致,不再缩在角落留白)。测试 28 用例。

### v0.21.0 — 安卓真机 QA(EvidenceCapture + adb + SOP,无 AltTester)
- **加**:`qa` / `闭环造鸭` 的安卓真机实测流程——**先自动测到全绿才惊动勾哥;真机实测是可选项**(全绿后问一句,他要才 guide USB 调试)。他在手机上玩 → 游戏里 `EvidenceCapture.cs` 在任何异常自动存 截图+log+机型 → 翼德 `adb pull` 拉回 → 按 `BUG-SOP` 出真机 QA 报告(聚焦真机问题 + 手感项,不混基础 bug)。
- **加**:`integrations/android/SETUP.md` 傻瓜配置(装 adb、开 USB 调试、EvidenceCapture 只在 dev build 开)。
- **加**:只读 adb(`devices`/`logcat`/`pull`/`get-state` 等)进自动放行白名单,取证不弹审批;`adb shell`/`install` 仍走审批。
- **明确不做 AltTester**(会改 build/开端口/必须从 release 剥离/对实时战斗脚本脆),留作"以后要无人值守回归再说"。测试 27 用例。

### v0.20.0 — 分层架构 + 真·静默更新(发货层 / 用户层 / 读取时合并)
- **加**:`resolve.js`——唯一懂分层的地方。**发货默认(红线/工作准则)读自插件、用户层(`~/.yide`)只放勾哥的、在"读取时"按 manifest 合并**;消费方只调 `resolve(key)`,合并逻辑不再散落。
- **真·静默更新**:咕哥更新插件 → 新发货默认**现读现合自动生效,`~/.yide` 一个字都不用动 → 零冲突、零迁移、零审批**。开窗不再卡、不再问;"提醒去 update"换成一行"已自动更新到 vX"(无需操作)。
- **去重不拆**:旧大脑里"默认+自定义混在一起"的 `hard-rules.md` 直接当用户层叠加,**按 (防XXX) tag 去重**——默认只出一次、自定义保留,**不做危险的拆分迁移**。
- **可定制不退化**:用户同 tag = 改写(override);`.meta/redline-suppress.json` 按 id 禁用某条默认红线。
- 红线 / charter 已上 resolver;`unity.md` 与配置(hook-rules 等)同机制,后续加 manifest 一行即可。测试 25 用例。

### v0.19.3 — 验证按层分工:玩法以 PlayMode 为真值
- **改**:闭环造鸭把"EditMode 优先"改成**按层分工**——纯逻辑(掉率/伤害/计时)用 EditMode(快),**真玩法/集成(Boss 关核心)用 PlayMode 且以它为真值**,别用 EditMode 假装测了玩法;PlayMode 慢就批量跑 + 护栏控时间。(勾哥是玩法程序员,偏好 PlayMode,有道理)
- **加**:`unity.md` 增 EditMode vs PlayMode 测试分工知识。

### v0.19.2 — 闭环造鸭加"后悔药"(检查点 + 一键回滚)
- **加**:闭环造鸭**开造前问勾哥要不要建检查点**(`git stash` 存住未提交的活 + 在专用分支 `yide/闭环-<功能>` 上造、主分支不碰、每里程碑原子提交)——是闭环造鸭的一个步骤,不是新动作。
- **加**:**失败一键回滚**(说"翼德 回滚")——读检查点、给勾哥看再确认、**整段当一个单位一次撤**(切回原分支+弃闭环分支+恢复 stash;别逐条 revert),回滚前再 stash 一份防反悔;没建检查点就老实说只能手动。

### v0.19.1 — 闭环造鸭按 producer 视角加固(治"假交付")
- **改**:`plan`(闭环造鸭)折进 8 条手游 producer/勾哥视角的改进——① **验收分三层**(`[逻辑·自动测]`/`[集成·冒烟]`/`[手感·试玩]`,只自动验前两层,手感留试玩,绝不声称验了手感);② **接口盘点**(读真实现有系统契约再动,治集成进屎山);③ **垂直切片优先**(先给最小能玩竖切让勾哥早 gut-check);④ **隔离开发**(独立/additive 场景先做,最后接线);⑤ **智能默认 `[假设]` + 只问 3–5 关键**(治"几句话太模糊但别问 20 题");⑥ **可调参数集中**(数值进 config,勾哥自己调不重编译,试玩反馈只重跑那条);⑦ **prefab 只借皮**(剥非视觉脚本);⑧ **循环护栏**(EditMode 优先、迭代/时间上限、卡住停下报、Coplay 掉线降级为"交付+你自己跑")。
- 交付附**试玩清单 + 测试明细 + 占位清单**,信任靠勾哥点不靠嘴。

### v0.19.0 — plan 进化成「闭环造鸭」(几句话 → 可玩切片)
- **改**:`plan`(中文名**闭环造鸭**)从"起草计划"进化成**端到端闭环**(规范驱动开发):**对齐 → 造 → 验 → 交付**。对齐沿用角色镜头 + 线稿确认 + EARS 验收;**造**阶段占位**先复用项目里已有 prefab/资源、实在没有才用灰盒**(勾哥不喜欢全灰盒);**验**阶段用**测试 + 已接的 Coplay(Unity MCP)** 当 oracle,`run_tests`/`read_console`/PlayMode **循环到全绿** + `翼德 评审`;**交付**可玩占位切片 + "请勾哥试玩什么手感"清单。
- 诚实:闭环闭到"编译过+测试绿+引擎能跑的占位可玩切片",**"好玩/平衡/手感"机器验不了,靠勾哥试玩**;美术用占位。

### v0.18.1 — 线稿打磨 + 项目 UI/UX 预设
- **改**:线稿批注改成**点选组件 → 当场弹框 → 边打边自动保存**(去掉拖拽圈选/overlay/保存按钮);手机框**居中 + 自适应缩放填满**。
- **加**:项目档案新增结构化「🎨 UI/UX 设计预设」(屏幕方向/分辨率/UI框架/美术基调/控件约定);mockup 与 `ui-ux` 镜头设计前先读它,缺啥问勾哥一次并记下。
- **加**:勾哥确认过的线稿存进**确认线稿文件夹**(默认 `Docs/UX/mockups/`,首次问勾哥确认、路径记进项目档案 + 放 README),方便 yide / 其他 AI 提取既有布局。

### v0.18.0 — 出 UI 线稿确认需求 + 资深角色镜头
- **加**:做带界面的功能时,`plan` 会自动**先出一张 HTML 低保真线稿**确认布局/流程,改对了再写代码。线稿上勾哥能**拖拽圈出某块区域写意见**,点「📋 复制反馈给翼德」一键把批注复制粘回(批注层 = `templates/mockup/annotate.html`,标准做法是给区域编号 + 集中批注)。也可单独喊"翼德 线稿 …"。
- **加**:4 个**开箱即用的资深角色镜头**——`architect`(架构总监)/ `ui-ux`(界面布局,也是出线稿那个脑子)/ `art-director`(美术方向/手游性能,**不产美术**)/ `pm`(需求/最小可玩/优先级)。任意项目 `use architect` 召唤,或 `翼德 会诊`。plan 做界面功能时会**快速内联**走一轮"资深小结"(UI/UX+美术+PM 出方案 → 架构 challenge),只给结论不展示拉锯。
- **修**:`extraction` 项目的"战绩"只奖励**推进游戏产品**(玩家可见的功能/内容/影响玩家的修复);**更新翼德、改工具/配置/杂活不再算战绩**(PM 判据)。
- 诚实底线:线稿是确认布局用、不是最终 UI/美术;镜头是 Claude 戴角色帽子的"资深第二意见",变不出美术资源。

### v0.17.0 — 架构整顿(测试/称重/收口/去重/版本提醒)
- **加**:`test/run.js` + `npm test` —— **首套提交进仓库的自检**(glob/索引自愈/PreToolUse allow·deny·defer/会话健康度/charter 注入/版本提醒),改完先跑,防回归溜到勾哥那。
- **加**:`scripts/audit-injection.js` + `npm run audit` —— 开场常驻注入"**称重器**",分节计字 + 估 token + 对比软预算(守"轻";当前稳态 ~885 tokens)。
- **加**:`scripts/store.js` —— `.meta` 状态访问**统一前台**(metaPath/readJson/writeJson/...),收掉散在 14 个脚本里的路径拼接与 ad-hoc JSON。
- **加**:`scripts/signals.js` —— 共享"纠正信号"正则(digest + session-health 不再各写一份)。
- **加**:SessionStart **版本落后提醒** —— 大脑 `plugin-version.txt` 落后于插件版本时,提醒跑一次 `翼德 update`(缺文件不烦新用户)。
- **改**:charter 第 5 条不再复述红线⑥,改为指向(去重 + 省 token)。

### v0.16.0 — 治"爱 hack fix" + 长对话自救(为屎山项目)
- **加**:**改 bug 规矩**进 charter(第 5 条)+ 新增默认红线第 6 条「防 hackfix」——先定位根因引用代码不猜、从根上修不打补丁、根太深只能止血时明说"临时方案+欠技术债"不假装修好、只动该动的、收尾跑 `翼德 评审`;勾哥说"赶时间就 hack"则尊重但仍记一句欠账。
- **加**:**会话健康度自救**(`session-health.js`,接进 UserPromptSubmit)——同一问题来回纠正 ≥3 次、或会话过长时,**一次性温和提醒重开会话**,并承诺"重开前把要点记进教训库、新会话自动带上,不丢"。治"一个 bug 修 6 遍 / 长对话上下文污染"。
- **加**:`qa` 增「**行为快照测试**(characterization test)」——改老代码前 Claude 自动给相关功能写快照测试、改完用 MCP 真跑(绿了才算修好),治"修一个坏六个";带"不烦人"约束(只对非琐碎/耦合处做、自动写自动跑、测不了就如实说)。
- **加**:`style/unity.md` 增 **DOTween + UGUI 常见坑**(tween 没 Kill 崩、UGUI Canvas 重建/Raycast/Layout)作为建议知识(不进正则 lint)。

### v0.15.0 — 去 approval + 工作准则 charter + 对抗式评审
- **加**:`PreToolUse` 不只硬拦,还**自动放行只读/导航类安全操作**(`cd`/`ls`/`cat`/`grep`/`git status·diff·log`/只读 MCP 等),治"每天开 Claude 一堆 approval"。安全模型:只放确定安全的,`Write`/`Edit` 仍走审批,deny 永远优先,拿不准回落正常审批。默认白名单烤在脚本里随更新走;想调松/调紧自建 `~/.yide/.meta/allow-rules.json` 覆盖。
- **加**:`core/charter.md`**工作准则**(最高级别,开场常驻):①能求证就别猜(MCP-first)②宁问勿错③非琐碎功能先调研同类最佳实践④架构总监视角(边界/耦合/暗坑)。红线说"不许做",charter 说"该怎么做",冲突时红线优先。
- **加**:`翼德 评审`(`review`)——派**新上下文** subagent 只看 diff、只挑正确性/耦合(不挑风格),破"自评循环";有 MCP 可调 `read_console`/`run_tests` 验真值。是 charter #4 的牙齿。
- **改**:`plan` 把"调研同类最佳实践 + 架构耦合考量"从可选升为非琐碎功能的默认步骤。
- **内务**:`session-start` 拆出 `extraction-context.js`;`lessons` 与 `prompts` 两套索引合并进 `index-util.js`(去重,行为不变)。

### v0.14.0 — 新设备自动认大脑 + 能力边界
- **加**:新设备装好插件跑 onboard 时,自动从同步盘(Google Drive/Dropbox/iCloud)**认领已有大脑**并重建本机指针——免重新磨合、连选文件夹都省(指针文件本地不同步,这步补齐)。
- **加**:README 新增**能力边界**章节(能做/需条件/不能做),诚实划清没接 MCP 时是"看不见屏幕的顾问"。

### v0.13.2 — 触发覆盖中英文
- **改**:SKILL 触发描述补全**英文自然语言**示例(yide brief / yide record this / yide plan this / use maxim…),中英文都能唤起;routing 本就认英文 keyword。

### v0.13.1 — 修正命令文案(插件做不到裸 /yide)
- **修**:全仓库把误导性的 `/yide <动作>` 改为**自然语言**("翼德 X")为主、`/yide:yide <动作>` 为辅。插件命令带命名空间,裸 `/yide X` 不存在(就是 onboard 报 unknown skill 的根因)。开场介绍/安装说明/README/各动作收尾全部统一。

### v0.13.0 — 专家模式 + 让位项目约定(资深友好)
- **加**:把关分档 `expertLevel`(默认 **expert**)——给每条规则标"是否显而易见",expert 档**只报非显而易见**的(async/Task 生命周期、版本特定弃用),"缓存 GetComponent/用对象池"等资深本就会的默认闭嘴。**解决**资深用户"说的我都会了"。
- **加**:**只看本次改动的行**(clean-as-you-code,不翻旧账);**行内 `// yide-ok: 原因`** 一次性豁免;`gatekeeper.json` 的 `suppressed` 永久静音某规则×路径。**解决**"它不懂我们是故意的"。
- **加**:unity.md 写明"项目约定(CLAUDE.md/AGENTS.md/.editorconfig/已探测管线版本)优先于通用建议,冲突让位"。
- 守反臃肿:**没加新 regex、没建新索引**,只是给既有规则加标签+分档过滤。#4(MCP 真验证环+对抗评审)待接 MCP。

### v0.12.2 — 把关器降误报 + 按版本 gating + MCP-first
- **改**:lint 去注释/字符串字面量(字符串里的 Camera.main 等不再误报);过时 API 按项目 Unity 版本 gating(FindObjectOfType 仅 2023+/U6 报、版本未知不给过时建议)。**解决**资深用户最烦的"误报/给过时建议"。
- **加**:unity.md 写明"若接 Unity MCP 则优先在引擎里验证(read_console/run_tests/profiler),文本 lint 只是退路;没接就老实说没在引擎验证过"。为接 MCP 后"看得见屏幕"铺路。

### v0.12.1 — 架构审计 + SessionStart 瘦身
- **改**:压掉 SessionStart 几条常驻 prose 指令(prompt 提示/教训计数/整理),稳态注入 ~542 tokens(其中 ⅔ 是用户自己的红线=应当常驻)。审计结论:actions 懒加载零常驻成本、hook 仅毫秒级延迟,**不拖累 Claude**;无数据口径残留。

### v0.12.0 — 翼德小报告(改名 + 自动/手动分栏)
- **改**:"维护者日报"→**翼德小报告**;内容重构为"✅ 翼德已自动处理(本期记的教训/存的 prompt/整理记忆/守的红线,只报可度量的真实动作)"+"🔧 需手动优化(每条附最佳做法)"。**解决**:作者要分清哪些翼德已自动搞定、哪些需自己动手、以及怎么动手最好。

### v0.11.0 — 闭环计划起草 + 翼德小报告
- **加**:`plan` —— 多文件/架构级任务先按项目 context 起草**闭环计划**(EARS 验收标准 + 测试计划 + `[需澄清]` + 红线门),批准再写;变化快的主题(URP/Addressables/性能)才问一句要不要查最新实践(带引用+缓存)。真跑 QA 待 Unity MCP。**解决**:不会写好 prompt、想要从架构到 QA 闭环。
- **加**:翼德小报告 —— 本地把使用中的**汇总信号**整理成"✅ 翼德已自动处理 / 🔧 需手动优化(附最佳做法)"(**只主题+计数,不含代码/原文/密钥**)发给作者;首次明确告知用户、"翼德别看了"即关、本地处理。**解决**:沉默用户不反馈,作者盲目迭代。

### v0.10.0 — 零策展 prompt 库(自动存 + 自动召回)
- **改**:prompt 库捕获从"提议+确认"改为**达标自动静默存**(≥2 质量信号 + 去重)——为"不会主动记"的人而设计。
- **加**:`UserPromptSubmit` hook **自动召回** —— 你每发一句,翼德自动匹配库里合适的 prompt 并温和推荐(同会话不重复、低置信不推、绝不阻断),让你"根本不用记何时该用"。
- 通用化:存时只把 1–3 个具体名词抽成 `{{占位符}}`,核心逐字保留;`uses≥3` 可升级成 `/命令`。全项目生效。**解决**:好 prompt 留不住、也想不起来何时复用。

### v0.9.0 — 个人项目轻量游戏化(可调可关)
- **加**:连斩 combo、今日首胜、打卡链、三国称号成就、`战绩` 面板、按时辰开场问候 + 深夜守护。全部只在个人放松项目生效、出错不出现、`enabled:false` 一键全关,奖励"质量事件"而非刷提交。(细节为个人配置,不公开。)

### v0.8.0 — 个人项目彩蛋可配置化
- **改**:个人放松项目的氛围彩蛋(鼓励语 + 音乐 + 口吻台词)抽到一张可调爆率表里,用户改数字即可调频率。(细节为个人配置,不在此公开。)

### v0.7.0 — 改名 + 张飞人格彩蛋 + 蒸馏定为"只蒸知识"
- **改**:命令更短 —— `qa`(原 测)、`note`(原 笔记)、`gaotapi`(搞他皮,原 蒸馏)。
- **定**:蒸馏**只蒸知识与去耦模式(尺度 1)**,移除原始代码片段路径 —— 对齐承诺与 IP 安全(带走文件是最重违法因子)。清掉 vestigial `distilled/`。
- **加**:🐯 张飞人格彩蛋 —— 仅在个人放松项目(extraction)里,翼德偶尔用张翼德豪爽口吻插科打诨("战又不战退又不退却是何故!"等),幽默为辅、把事办对为主,严肃场景自动收起。

### v0.6.0 — 命名专家 + prompt 库 + QA 重点来源
- **改**:蒸馏重设计为**命名专家**——把某人/某块蒸馏成用户级 subagent(`~/.claude/agents/maxim.md`),在你自己项目里 `use maxim` 即可召唤;原则优先(可迁移)、带来源声明/置信度、行为化框架(研究证实浮夸人设反伤正确性)、默认代号匿名。新增 `专家`(列出/召唤/会诊)。**解决**:想把好同事/好模块的本事带到自己项目复用。
- **加**:`prompt` 库——翼德提议+你确认地固化好 prompt,任务边界温和建议,够热升级成命令。**解决**:好用的 prompt 留不住、想复用。
- **加**:QA"本次重点"支持**贴一句或从 Slack 读**(勾哥当场选)。**解决**:重点在 Slack 里要不要手动复制。
- 跨设备:`sync-experts` 在 SessionStart 把大脑里的专家副本补进 `~/.claude/agents/`。

### v0.5.0 — 蒸馏同事(初版)
- **加**:`蒸馏` 把公司多人代码蒸馏成个人可移植知识库(架构图 + 去耦模式 + 设计取舍),内置 IP 护栏(默认只蒸馏可迁移知识、扫密钥、标 ipScope、提醒查雇佣协议、本地优先)。**解决**:想带走/复用工作中积累的架构与模式,又不踩 IP 雷。

### v0.4.0 — 单命令 + QA + 随手记
- **改**:5 个 `/yide:yide-*` 合并为单一 `<动作>`(progressive disclosure)。**解决**:命令啰嗦、插件占用上下文拖累 Claude。
- **加**:QA(`测`)聚焦测试计划 + 强制 bug SOP + 证据捕获脚本。**解决**:测试乱测边角、bug 报告散乱无证据。
- **加**:随手记(`笔记`)手机笔记按时间/主题/项目归类。**解决**:随时记想法没地方落。
- **改**:减少权限弹窗(`allowed-tools` + 可选窄 allow 规则)。**解决**:每开新窗口反复授权。

### v0.3.0 — 安全迁移 + 跨设备 + 减负
- **加**:`update` 三方安全合并(只增不删、冲突先问)。**解决**:推更新会不会覆盖用户已攒的教训。
- **加**:指针文件选大脑位置(免命令行/环境变量),跨设备免重配。**解决**:换电脑要重新磨合。
- **改**:scope 教训按文件浮现 + 开场有界注入(教训只报数)。**解决**:context 随年月膨胀。

### v0.2.0 — Unity 把关 + Windows 化
- **加**:Unity 静态 lint(四类)+ 项目档案自动探测。**解决**:对 Unity 程序员没有实际价值。
- **改**:hook 改 exec 形式、Node 重写(去 jq 依赖)、事件驱动整理替代夜间 cron。**解决**:Windows 装不起来、无 jq 失灵、电脑关机沉淀丢失。
- **改**:更名"翼德"。

### v0.1.0 — 上下文中枢初版
- 大脑骨架(core/lessons/style/projects)+ SessionStart 注入 + PreToolUse 硬拦截 + 记录/简报/整理技能。**解决**:每次重复解释、记过的错重复犯。
