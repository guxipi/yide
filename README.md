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
重启 Claude Code → 翼德自动打招呼 → 跟着 `/yide onboard` 走几道选择题即可。
(不便用 GitHub 时,也可解压发行包后 `claude --plugin-dir ./yide`,但仅当次会话。)

## 用法:一个命令 `/yide <动作>`(也认自然语言)

| 你说 | 干什么 |
|---|---|
| `/yide onboard` / `磨合` | 首次访谈(选择题),建你的个人大脑 |
| `/yide record` / `记一下 …` | 记一笔教训,下次绝不再犯 |
| `/yide brief` / `简报` | 生成可复制简报,贴进 Desktop / ChatGPT / Gemini |
| `/yide 整理` / `consolidate` | 整理记忆:合并重复、修正过时、升级反复犯的错 |
| `/yide update` / `更新` | 插件更新后安全迁移:补新默认,**冲突先问、绝不覆盖你的数据** |
| `/yide test` / `测 …` | QA:聚焦测试计划 / 强制 bug SOP / 跑测+三查 |
| `/yide 笔记 …` / `capture` | 随手记:录入 / 整理手机扔来的笔记 / 查询 |

说"翼德 记一下…/简报/整理/测试"等自然语言也能触发。单入口 + 按需加载 = 不占上下文。

## 数据安全:代码 / 数据分离

- **代码**(hooks、lint、actions)在本仓库 → `git push` 后 `/yide update` 即生效。
- **你的数据**(教训、身份、笔记、自定义红线)在 `~/.yide` → **更新永不覆盖**。
- 跨设备:把 `~/.yide`(或指针指向的同步盘文件夹,Google Drive / git)同步过去即可,免重新磨合。

## 核心机制

- **两层"绝不再犯"**:软层(规则注入上下文,全平台)+ 硬层(仅 Claude Code 的 `PreToolUse` hook 确定性拦截)。
- **Unity 把关**:写/改 `.cs` 后 `PostToolUse` 自动 lint(性能热路径 / 过时 API / 序列化生命周期 / 资源 git 卫生),非阻断只建议;命中文件 scope 的教训一并浮现。
- **项目档案探测**:Unity 项目里自动读出版本 / 渲染管线 / Input System / Addressables / 脚本后端。
- **记忆沉淀**:事件驱动(开会话若距上次 >24h 自动整理),电脑关机也不丢。
- **长期规模**:lessons 源文件 + 编译索引(mtime 自愈)+ 归档;开场只注入身份+红线+计数,不随年月膨胀。

## 结构

```
yide/
├── .claude-plugin/{plugin.json, marketplace.json}
├── SKILL.md                 # 单一 /yide 入口(派发)
├── actions/                 # 按需加载:onboard / record / brief / consolidate / update / test / capture
├── hooks/hooks.json         # exec 形式(Windows-safe)
├── scripts/*.js             # 全 Node,无第三方依赖
├── templates/brain/         # onboard 时复制到 ~/.yide
├── templates/qa/            # bug SOP / 报告模板 / EvidenceCapture.cs
└── integrations/            # 可选:telegram(随手记)/ unity-mcp(看 Editor)
```

## 跨平台 / Windows
hook 用 exec 形式(避开 `${CLAUDE_PLUGIN_ROOT}` 反斜杠 bug);文件操作走 Node;`.gitattributes` 锁 LF。依赖 `node`(Claude Code 自带)。

---

## 更新记录 Changelog

### v0.4.0 — 单命令 + QA + 随手记
- **改**:5 个 `/yide:yide-*` 合并为单一 `/yide <动作>`(progressive disclosure)。**解决**:命令啰嗦、插件占用上下文拖累 Claude。
- **加**:QA(`/yide 测`)聚焦测试计划 + 强制 bug SOP + 证据捕获脚本。**解决**:测试乱测边角、bug 报告散乱无证据。
- **加**:随手记(`/yide 笔记`)手机笔记按时间/主题/项目归类。**解决**:随时记想法没地方落。
- **改**:减少权限弹窗(`allowed-tools` + 可选窄 allow 规则)。**解决**:每开新窗口反复授权。

### v0.3.0 — 安全迁移 + 跨设备 + 减负
- **加**:`/yide update` 三方安全合并(只增不删、冲突先问)。**解决**:推更新会不会覆盖用户已攒的教训。
- **加**:指针文件选大脑位置(免命令行/环境变量),跨设备免重配。**解决**:换电脑要重新磨合。
- **改**:scope 教训按文件浮现 + 开场有界注入(教训只报数)。**解决**:context 随年月膨胀。

### v0.2.0 — Unity 把关 + Windows 化
- **加**:Unity 静态 lint(四类)+ 项目档案自动探测。**解决**:对 Unity 程序员没有实际价值。
- **改**:hook 改 exec 形式、Node 重写(去 jq 依赖)、事件驱动整理替代夜间 cron。**解决**:Windows 装不起来、无 jq 失灵、电脑关机沉淀丢失。
- **改**:更名"翼德"。

### v0.1.0 — 上下文中枢初版
- 大脑骨架(core/lessons/style/projects)+ SessionStart 注入 + PreToolUse 硬拦截 + 记录/简报/整理技能。**解决**:每次重复解释、记过的错重复犯。
