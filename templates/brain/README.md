# 翼德 / Yide — 个人上下文中枢(大脑)

翼德是你常驻的"个人上下文中枢" + Unity 把关助手。他持续沉淀**你的身份、偏好、风格、规则与教训**,
在你每次开启新的 Claude / AI 对话时自动生成一份"交接简报",
让新 AI 上来就懂你——不用反复解释、不再重复犯错;并在你写 C#/Unity 代码时按 best practice 把关。

主要服务对象:Unity 手游程序员。要解决的痛点:
1. 每个 AI chat 能力参差不齐
2. 不了解你的 context(技术栈、项目、习惯)
3. 不了解你的喜恶 → 反复解释

## 目录结构

```
~/.yide/
├── INDEX.md          # 索引:永远加载。列出所有条目 + 一句话摘要
├── core/             # 🔴 第一层 永远带
│   ├── identity.md   #   我是谁:角色、技术栈、语言偏好
│   └── hard-rules.md #   绝对红线(≤15 条),带 severity
├── lessons/          # 🟠 教训库 —— @翼德 记录的错误进这里,一条一个文件
│   └── _TEMPLATE.md
├── style/            # 🟡 第二层 场景带(按任务类型注入)
│   ├── coding.md
│   ├── unity.md      #   Unity 手游 best practice(写 .cs 时自动把关)
│   ├── writing.md
│   └── communication.md
├── projects/         # 🟢 第三层 按需带(点名某项目才加载)
│   └── _TEMPLATE.md
└── .meta/            # 系统自用
    ├── inbox/             #   待整理的原始提炼
    ├── conflicts.md       #   拿不准的冲突,攒着问你
    ├── hook-rules.json    #   可硬拦截的规则(被 PreToolUse hook 读取)
    ├── daily-progress.json#   extraction 项目每日进度(满 2 个奖励)
    └── last-consolidate.txt # 上次整理记忆的时间戳(到期自动提醒)
```

## 三层注入(简报分层)

| 层级 | 内容 | 何时带 |
|---|---|---|
| 永远带 | core/ 全部 + severity≥8 的 lessons | 每个新对话 |
| 场景带 | style/ + scope 匹配的 lessons | 按任务类型 / 文件 glob |
| 按需带 | projects/ | 点名某项目时 |

## "绝不再犯"两层执行

- **软层**:把规则注入对话上下文(全平台生效,影响倾向)
- **硬层**:仅 Claude Code —— PreToolUse hook 读 `hook-rules.json`,在动作执行前确定性拦截(真正 block)

## 常用命令(由 yide 插件提供)

- `/yide:yide-onboard` — 首次访谈,建你自己的大脑
- `/yide:yide-record` — 把一次纠错记成 lesson(发现问题时用)
- `/yide:yide-brief` — 生成可复制简报,贴进 Desktop / 其他 AI
- `/yide:yide-consolidate` — 整理记忆:合并重复、修正过时、升级反复犯的错
