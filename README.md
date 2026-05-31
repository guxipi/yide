# 翼德 🗡️ — Unity 程序员的上下文中枢与把关助手(Claude Code 插件)

翼德做两件事:
1. **个人上下文中枢**:沉淀你的身份、风格、规则与教训,每次开新对话自动 brief 给 Claude,**记过的错绝不再犯**。
2. **Unity 把关助手**:写 C#/Unity 代码时,按手游 best practice 自动 lint 你改过的 `.cs`,把隐患作为建议浮出来。

为 Unity 手游程序员而做,解决三个老问题:AI 能力参差、不懂你的 context、不懂你的喜恶 → 反复解释。

## 安装(本地开发 / 分发)

```bash
# 加载本插件(当前会话)
claude --plugin-dir /path/to/yide

# 首次设置:跑一次访谈,建立你的大脑(~/.yide)
/yide:yide-onboard
```

装好后**每次开 Claude Code 会话,翼德会自动**:注入你的核心上下文 + 红线、读当前 Unity 项目档案(版本/管线/帧率)、并在你写 .cs 时把关。

## 一个命令 `/yide <动作>`(也认自然语言)

只有一个轻量入口 `/yide`,后面跟动作词或中文,翼德按需加载对应能力(progressive disclosure,不占上下文):

| 你说 | 干什么 |
|---|---|
| `/yide onboard` / `/yide 磨合` | 首次访谈(选择题),建你的个人大脑 |
| `/yide record` / `/yide 记一下 …` | 记一笔教训,下次绝不再犯 |
| `/yide brief` / `/yide 简报` | 生成可复制简报,贴进 Desktop / ChatGPT / Gemini |
| `/yide 整理` / `/yide consolidate` | 整理记忆:合并重复、修正过时、升级反复犯的错 |
| `/yide update` / `/yide 更新` | 插件更新后安全迁移:补新默认,**冲突先问、绝不覆盖你的数据** |
| `/yide test` / `/yide 测 …` | QA:聚焦测试计划 / 强制 bug SOP / 跑测+三查 |
| `/yide 笔记 …` / `/yide capture` | 随手记:录入 / 整理手机扔来的笔记 / 查询 |

说"翼德 记一下…/简报/整理/测试"等自然语言也能触发。

## 更新与数据安全(代码/数据分离)

- **代码**(hooks、lint、actions)在仓库里 → 更新即生效。
- **你的数据**(lessons、identity、笔记、自定义红线)在 `~/.yide` → **更新永不覆盖**。
- 把新版默认安全并入老大脑:`/yide update`(基于 `.meta/shipped-base` 三方比较,只增不删、冲突先问)。

## 核心能力

**① 两层"绝不再犯"**
- 软层(全平台):规则注入上下文,影响 AI 倾向。
- 硬层(仅 Claude Code):`PreToolUse` hook 读 `~/.yide/.meta/hook-rules.json`,在 Bash/Write/Edit 真正执行前确定性拦截 —— 唯一能 100% block 的一层。
- (Desktop / 其他 AI 没有 hook,只能软层。)

**② Unity 把关(PostToolUse 把关器)+ scope 教训**
写/改 `.cs` 后自动 lint,覆盖四类:性能热路径(Update 里的 GC/查找/Instantiate)、过时/幻觉 API、序列化/生命周期、资源/git 卫生。**非阻断**,只给建议。规则依据见 `~/.yide/style/unity.md`。
同时:命中该文件路径的 lessons(带 `scope:["**/*.cs"]` 之类的 glob)会一并浮现,"写 X 时才生效"的教训按文件触发。

**③ 自动项目档案探测**
在 Unity 项目里开会话时,自动读出 **Unity 版本 / 渲染管线(URP·HDRP·Built-in)/ Input System / Addressables / 脚本后端**注入上下文,省得每次重新解释。

**④ 记忆沉淀(自动,电脑关机也不丢)**
不靠夜间 cron。每次开会话若距上次整理 >24h,翼德**自动**先静默跑一次 `/yide:yide-consolidate` 再干活(`YIDE_NO_AUTO_CONSOLIDATE=1` 可退回仅提醒)。需要无人值守可叠加 Windows 任务计划程序(勾 "StartWhenAvailable" 补跑)。

**⑤ extraction 项目专属**(项目路径含 `extraction` 时启用)
- 督促"做完 > 做大",劝阻盲目扩 scale。
- 变比率奖励:完成小功能调 `scripts/progress.js bump "功能名"`,随机 2–6 个(满 10 必触发)→ 浏览器放[雷霆小鸡](https://www.bilibili.com/video/BV1kpwszhEDh/)并夸奖勾哥(`YIDE_NO_OPEN=1` 静音)。

## 大脑结构(运行时在 `~/.yide/`)

```
INDEX.md          索引(永远加载)
core/             🔴 永远带:identity.md / hard-rules.md
lessons/          🟠 教训库:一条一个 L-XXXX.md
style/            🟡 场景带:coding / unity / writing / communication
projects/         🟢 按需带:每个项目一个文件
.meta/            系统自用:hook-rules.json / daily-progress.json / last-consolidate.txt / conflicts.md / inbox
```

## 插件结构

```
yide/
├── .claude-plugin/plugin.json
├── .gitattributes              # 锁 LF,Windows 检出不被改 CRLF
├── skills/yide-{onboard,record,brief,consolidate}/SKILL.md
├── hooks/hooks.json            # exec 形式(Windows-safe)
├── scripts/                    # 全 Node,无第三方依赖
│   ├── lib.js                  #   大脑路径 / 跨平台开浏览器 / 日期
│   ├── session-start.js        #   注入上下文 + Unity 项目档案 + 奖励/督促
│   ├── pre-tool-use.js         #   硬层拦截
│   ├── post-tool-use.js        #   Unity 把关(advisory)
│   ├── lint-unity.js           #   Unity 静态 lint 规则
│   ├── progress.js             #   每日进度 + 雷霆小鸡奖励
│   ├── stamp-consolidate.js    #   整理时间戳
│   └── install-brain.js        #   跨平台建大脑(替代 cp -R)
└── templates/brain/            # onboard 时复制到 ~/.yide
```

## 跨平台 / Windows

- hook 用 **exec 形式**(`command:"node"` + `args`),规避 Windows 上 `${CLAUDE_PLUGIN_ROOT}` 反斜杠被 Git Bash 吞掉的已知问题(claude-code#18527)。
- 文件操作走 Node(`fs.cpSync` 等),不用 `cp`/`ls`,Win/mac/Linux 一致。
- 放歌跨平台:Windows `cmd /c start "" url`、mac `open`、Linux `xdg-open`。

依赖:`node`(Claude Code 本身即跑在 Node 上,通常已具备),无第三方包。
