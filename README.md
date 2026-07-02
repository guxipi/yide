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

**全部 19 个动作**(`<X>` 就是 `/yide:yide X` 里的那个词):

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
| `docs` | 项目文档 / 吸收文档 / 文档管理 | Confluence 导出/增量 → 蒸成精简 `CLAUDE.md`(每次会话自动读)→ 7 天懒同步 |
| `playtest` | 冻帧标注 / 标注 / 试玩反馈 | Unity 按 F8 冻帧 + 抓命中元素/上下文 + 录音/打字 → 本地转写 → 带定位问题清单 → 联合优化回流 |
| `voice` | 语音 / 语音输入 / 听写 / 口述 | Rider 终端全局热键(默认 Ctrl+F9)说中文 → 复用 Google STT 流式转写 → 自动键入当前光标(Claude Code 输入框),审一眼再回车(Windows) |
| `zhanji` | 战绩 / stats | 看连斩 / 打卡链 / 三国称号(extraction 个人项目彩蛋) |

说"翼德 记一下…/简报/整理/测试/蒸馏/用 maxim/起个计划"等自然语言也能触发。单入口 + 按需加载 = 不占上下文。

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
├── actions/                 # 按需加载:onboard/record/brief/consolidate/update/qa/review/note/distill/experts/prompts/plan/mockup/ui/storyboard/docs/playtest/voice/zhanji
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
**已验证**(`npm test` 全套回归 / 实跑 / 渲染截图 / 查官方文档):PreToolUse 放行·拦截·adb 门控·换行切分·危险 flag·PowerShell·MCP 整词匹配、resolve 分层去重·软上限、索引自愈、charter 注入、注入体量(`npm run audit` / `audit:real`)、migrate 加文件·清理·打戳、大脑完整性哨兵·冲突副本巡检、本机私有状态·原子写、session-health 阈值、线稿/QA 报告 HTML 渲染与交互、`CLAUDE.md` 自动加载机制、skill 描述触发安全、文档一致性。

**⚠️ 尚未在真实环境端到端验证**(需勾哥在真机/真项目各跑一遍,验一项划一项):
- 闭环造鸭:几句话 → 引擎里可玩切片(需真 Unity + Coplay)
- 安卓真机 QA:EvidenceCapture + `adb pull` + SOP 报告(需真安卓设备)
- 项目文档管理:Confluence 导出 → 解压 → 蒸成 `CLAUDE.md` → 自动读(需真 Confluence)
- 角色镜头 `use architect` 在真会话能否召唤(需真 Claude Code 会话)
- 一键回滚"整段撤"(需真闭环跑一次)
- Playtest 冻帧标注:F8 冻帧+抓命中元素/上下文+marker 落盘、非 Play 截窗、Google Cloud STT(Chirp 3)流式转写**均已真机验证通过**;仅"扫 marker → 联合优化修复回流"整链待一次真实 session 端到端验
- 语音喂 prompt(`voice`):Rider 终端全局热键说中文 → 复用 Google STT 流式转写 → SendInput 自动键入 Claude Code 输入框。**整链需勾哥真 Windows 端到端验**(全局热键捕获 / 麦克风 / 出中文 / Unicode 注入打进终端这四环);代码逻辑就绪,翼德未在真机跑过

> 诚实底线:`node test` 只覆盖"可控的逻辑/文件层";**"模型在真实会话照做 + 勾哥真实环境"这层必须真机验,翼德不冒充已验证。**

## 更新记录 Changelog

完整更新记录见 **[CHANGELOG.md](./CHANGELOG.md)**(精选高亮日志,最新在上)。
