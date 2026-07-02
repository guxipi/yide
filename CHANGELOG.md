# 翼德 更新记录 Changelog

> 精选高亮日志(非逐版本穷举)。最新在上。

### v0.46.0–v0.49.0 — 2026-07-02 全系统 audit 修复(5 Phase)
- **v0.46.0 安全**:PreToolUse 自动放行层堵 4 处绕过 —— 命令切分补 `\r?\n`(多行命令第二行不再漏检)、`find -delete`/`-exec`+`sort -o` 等写形态回落审批、`git config/branch/tag/remote/reflog` 仅纯查询放行(`git branch <名>` 撞红线⑧,回落)、hooks.json 加 `PowerShell`(走 deny 层)、MCP allow 改按 `_` 分词整词匹配(`get` 不再误命中 `forget`/`budget`)。先写回归用例证明当前绕得过再修。
- **v0.47.0 多机健壮性**:会话级易变状态(session-health/greet/lint-seen/prompt-suggest-log)迁本机 `~/.yide-local`,不进同步盘(治 Drive lost update / conflicted copy);store 全改原子写;SessionStart **大脑完整性哨兵**(缺 INDEX.md/identity → 报警"指针多写一层",绝不当正常大脑/不 onboarding)+ 离线兜底 + 顶层 catch 降级简报 + timeout 15s;新增 `conflict-scan.js` + consolidate 冲突副本巡检。
- **v0.48.0 更新闭环 + 注入瘦身**:版本变化时 SessionStart 跑 `migrate --apply`(不再只打版本戳→快照冻结),安全部分立即落地、有冲突/缺红线则不打戳并引导"翼德 update"裁决;migrate 加 removed 清理清单(废弃 `core/charter.md`、digest 残留、已迁的共享 .meta);`audit-injection --real` 真实称重 + 修模板基线被完整性哨兵误判的回归;resolve charter-extra 软上限。live 大脑 charter-extra 拆分 ER 专属→ `charter-extra-er.md`(只在 ER 会话注入)。
- **v0.49.0 skills/文档 + 新功能**:15 个 skill description 瘦身 ≤500(触发词全保);修 ui-visual-rework 基准矛盾 + 临时脚本落点口径统一;文档漂移全修(动作数、结构图、changelog 拆出本文件、验证状态);新增 `翼德 体检`(doctor)、Unity SmartMerge 集成、`guid-find.js`、qa perf triage 节、lint-skill-refs。

### v0.38.0 — mockup action 术语解耦:art bible → 真源实名
- **背景**:「art bible」一词被重载——既指已删的云盘通用 zip(`supercasual_artbible.zip`),又被 `mockup` action / ER 线稿 prompt 拿来指**项目真源** `UI_Visual_Design_Guidelines.md`,含混。
- **改**:`actions/mockup.md` 5 处「art bible」全部改成「UI 设计规范文档」并点名真源;语义不变(仍是 kit 二手提炼、冲突以 kit 实物为准)。本地 ER 线稿 prompt 与项目记忆同步解耦(记忆库改动不在本仓)。kit 实物仍是数值绝对标准,文档仅作快速索引。

### v0.37.0 — ui-visual-rework 删 art bible 章节
- **删**:`ui-visual-rework` 的「Art bible(supercasual_artbible.zip)使用裁定」整段。那份云盘 zip 是通用 SuperCasual 规范、非项目真源(skill 自承净贡献 ~15%),真值早已由项目内 `UI_Visual_Design_Guidelines.md`(14 节,全部基于 RarityConfig.cs / UICurrencyItemWidget 等真实代码)+ kit prefab dump 接管;且原弃用项里那条 Canvas「改用 1440×2560」与 ui-placement 2026-06-14 RATIFIED 的 1080×2340 互相矛盾、已过时误导。
- **留**:把与 art bible 无关的真规则脱框架保留为新章节「交付前硬规则与自查」——6 条交付自查、`juice = art, not code`、`Core.UI.PressScale`、字体拍板 CookieRun;Canvas 参考顺手修正为正确的 1080×2340 / Match 0.487 并 cross-ref `UI_Placement_Rules.md`。

### v0.36.0 — 移除「翼德小报告」(digest)
- **删**:观察勾哥使用 → 统计汇总信号 → 发 Telegram 给作者的 digest 功能整体下线(`scripts/digest.js`、SessionStart async hook、开场一次性披露、`maker-telegram.json` 配置)。`signals.js` 保留(`session-health` 仍用)。**原因**:勾哥要求彻底抹除该功能。

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
- **项目隔离(关键)**:与 `ui` 触发词**零重叠**且 action 开头有「项目适配门」——`ui`=接 Coplay/Unity 写 MCP、引擎里直接摆(如 **ER**,本次零改动);`figma`=只挂 Figma 读 MCP、不碰引擎只产代码。ER 喊「摆UI/对齐」永远走 `ui.md`。注:`figma` 已独立成 `skills/figma-ugui-bridge`,不再是 action。
- **边界**:硬约束「不写 `.unity`/`.prefab`、不挂写 Unity 的 MCP、不引社区 MCP(凭证泄露面)」;Code Connect 对 Unity/C# 非一等公民,此条属**官方文档推断、未在 Unity C# 项目实测**,先拿一个组件试通再铺开。

### v0.26.0 — `ui` 动作(跨项目摆 uGUI)+ 语音多轮打磨
- **加**:`ui` 动作(摆UI / 调界面 / 对齐)。在 Unity 里把 uGUI 摆对/对齐/重建的**通用执行纪律**——「截图自检循环 + 锚点纪律 + 事件接线」三件套。项目专属**一律探测、绝不写死**。**不信 Coplay capture**(对 Screen-Space canvas 是瞎的)→ 改用 `ScreenCapture.CaptureScreenshot` 出 PNG 自读。
- **加**:`storyboard` 动作扩写 + `templates/storyboard/draw-layer.html` 手绘批注层;`plan` 接一行,涉及运镜/空间编排时自动走分镜。
- **改 voice(4 轮)**:中英混说 / 开机静默自启 / 浮窗实时 interim 字幕 / 浮窗独立线程 + 焦点恢复 + `--selftest`。

### v0.25.0 — 语音喂 prompt(Rider 终端全局热键说话 → 自动键入 Claude Code 输入框)
- **加**:`voice` 动作 + `integrations/voice-prompt/`。光标停在输入框,按全局热键(默认 **Ctrl+F9**)说中文 → 复用 playtest 那套 `stt_google.py`(Chirp 3 流式)实时转写 → 停录后用 **Windows SendInput(KEYEVENTF_UNICODE)** 自动键入,默认不自动回车留审稿。面向 Windows;整链需真机端到端验。

### v0.24.0 — Playtest 冻帧标注反馈(Unity 内按 F8 → 翼德直通代码的问题清单)
- **加**:`playtest` 动作 + `integrations/playtest-capture/` + `PlaytestMarker.cs`(运行时)+ `PlaytestMarkerWindow.cs`(编辑器停靠窗口)。按 **F8** → 冻帧 + 截图 + 抓游戏内状态(命中 UI/物体层级路径 + 来源 Prefab + 场景/分辨率/FPS)+ 录音;"翼德 playtest" → 转写 + 合并打字 + 读截图 → 出带定位问题清单。**标注面板独立编辑器窗,绝不遮挡游戏**。`#if UNITY_EDITOR||DEVELOPMENT_BUILD` 包住不进正式包。

### v0.23.0 — 项目文档管理(Confluence → 项目根 CLAUDE.md,自动耦合开发)
- **加**:`docs` 动作——Confluence 文档:首次一键导出(免 token)→ 蒸成精简层写进项目根 `CLAUDE.md`(Claude Code 每次会话自动读)→ API token 增量保鲜 → 7 天懒同步。三层:源(Confluence)/ 镜像(`~/.yide/.cache/confluence/`,不进 git)/ 精简层(仓库 `CLAUDE.md`,进 git)。**注**:自动加载的是 `CLAUDE.md` 不是 `AGENTS.md`。

### v0.22.0 — QA 报告可交互手感表 + 联合优化回流
- **加**:`feel-form.html`——手感项做成可交互(👍/👎/🤔 + 一句 → 一键复制粘回);翼德拿到反馈 → art-director(数值)+ ui-ux(设计)联合建议、PM challenge → 最佳方案供勾哥定夺。

### v0.21.0 — 安卓真机 QA(EvidenceCapture + adb + SOP,无 AltTester)
- **加**:先自动测到全绿才惊动勾哥、真机实测可选;`EvidenceCapture.cs` 异常自动存 截图+log+机型 → `adb pull` 拉回 → 按 BUG-SOP 出报告;只读 adb 进自动放行白名单。明确不做 AltTester。

### v0.20.0 — 分层架构 + 真·静默更新(发货层 / 用户层 / 读取时合并)
- **加**:`resolve.js`——发货默认读自插件、用户层只放勾哥的、"读取时"按 manifest 合并;更新插件 → 新默认现读现合自动生效,`~/.yide` 零改动。旧大脑混合 `hard-rules.md` 按 (防XXX) tag 去重不拆;`redline-suppress.json` 可禁用某默认。

### v0.19.x — 闭环造鸭(几句话 → 可玩切片)
- `plan`(闭环造鸭)从"起草计划"进化成端到端闭环:对齐 → 造 → 验 → 交付。producer 视角 8 条加固(验收分三层/接口盘点/垂直切片/隔离开发/智能默认/可调参数/prefab 借皮/循环护栏);开造前检查点 + 一键回滚;验证按层分工、玩法以 PlayMode 为真值。

### v0.18.x — UI 线稿确认 + 资深角色镜头
- 做界面功能先出 HTML 低保真线稿确认布局(点选组件→弹框→自动保存);4 个开箱角色镜头 `architect`/`ui-ux`/`art-director`/`pm`,`use architect` 召唤或 `翼德 会诊`;项目档案加「UI/UX 设计预设」+ 确认线稿文件夹。

### v0.17.0 — 架构整顿(测试/称重/收口/去重/版本提醒)
- `test/run.js` + `npm test` 首套提交进仓库的自检;`audit-injection.js` + `npm run audit` 开场注入称重器;`store.js` 统一 `.meta` 状态访问;`signals.js` 共享纠正信号正则;SessionStart 版本落后提醒。

### v0.16.0 — 治"爱 hack fix" + 长对话自救
- 改 bug 规矩进 charter + 默认红线「防 hackfix」;`session-health.js` 会话健康度自救(同问题纠正 ≥3 次/会话过长 → 一次性温和提醒重开,承诺不丢);`qa` 加行为快照测试;`unity.md` 加 DOTween + UGUI 常见坑。

### v0.15.0 — 去 approval + 工作准则 charter + 对抗式评审
- `PreToolUse` 自动放行只读/导航安全操作(deny 永远优先);`core/charter.md` 工作准则(能求证别猜/宁问勿错/先调研/架构总监视角);`翼德 评审` 派新上下文 subagent 只看 diff 挑正确性/耦合。

### v0.14.0 — 新设备自动认大脑 + 能力边界
- 新设备 onboard 自动从同步盘认领已有大脑并重建本机指针;README 加能力边界章节。

### v0.10.0–v0.13.x — prompt 库 / 触发中英 / 专家模式雏形
- 零策展 prompt 库(达标自动静默存 + UserPromptSubmit 自动召回);触发覆盖中英文;把关分档 expertLevel(默认只报非显而易见)、只看本次改动行、行内 `// yide-ok:` 豁免。

### v0.5.0–v0.9.0 — 蒸馏同事 / 命名专家 / 个人项目游戏化
- 蒸馏公司代码成个人可移植知识(IP 护栏);命名专家(`use maxim`);个人放松项目轻量游戏化(连斩/打卡/称号/张飞人格彩蛋,可调可关)。

### v0.1.0–v0.4.0 — 上下文中枢初版 → 单命令 + Unity 把关 + Windows 化
- 大脑骨架(core/lessons/style/projects)+ SessionStart 注入 + PreToolUse 硬拦截;5 个命令合并为单一 `<动作>`;Unity 静态 lint + 项目档案探测;hook 改 exec 形式、Node 重写去 jq 依赖、更名"翼德"。
