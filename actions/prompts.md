# 翼德 · prompt 库(prompts)

把勾哥跑得好的 prompt 固化下来,日后可查、可在合适时机被翼德建议、够热可升级成命令。
存在 `~/.yide/prompts/`:一条一个 `.md`(frontmatter + 正文),`index.md` 一行一条。

按 `$ARGUMENTS` 分四种用法:

## A. 存(capture)—— 翼德提议 + 用户确认(绝不自动存)
- 触发时机:某条 prompt 明显好用(几轮就搞定、用户说"对了/就是这个/完美"、产出可直接用)。**在任务边界问一句**:"刚那条 prompt 不错,存进库吗?(存/改名/跳过)"。一个任务最多问一次,被拒就本会话闭嘴。
- 用户同意 → 翼德自动拟好 name/description/tags/paths,**把具体处改成 `$参数` 占位**(可复用),写文件(status: draft),并在 `index.md` 加一行。
- 写前先在 index 查重,有近似的就**问要不要更新已有**,别建重复。

## B. 看(browse)—— `/yide prompt`(无参数)
- 读 `~/.yide/prompts/index.md`,列出:名字 | 何时用 | tags | 用过几次。可按关键词筛。

## C. 建议(suggest)—— 上下文里温和提醒
- 当前任务/文件匹配到库里的 prompt(优先按 `paths` glob,再按 tag/关键词;偏好 status: tested、uses 高的)。
- **只在任务边界、高置信时**,说一句:"你库里有个 `<name>` 适合这个,用吗?(用/看看/不用)"。**一个任务一次,别打断、别刷屏、低置信就别提。**
- 用户说"用" → 这时才读那条 prompt 全文(按需加载,不预载,省上下文)。

## D. 升级(promote)—— 够热做成命令
- 某条 `uses >= 3` → 提议:"`<name>` 你用了 N 次,要不要做成 `/<name>` 命令直接调?"。
- 同意 → 因为 frontmatter 与 Skill 兼容,把文件挪到 `~/.claude/skills/<name>/SKILL.md` 即成一等命令。

## 文件格式
```yaml
---
name: gen-unity-test
description: 为 MonoBehaviour 生成按生命周期分组 + 边界值表的 NUnit 测试
tags: [unity, testing]
paths: "**/*.cs"        # 决定何时建议
status: draft           # draft | tested(用过≥2次或用户认可)
uses: 0
created: ""
why: "为什么这条好用(一句话)"
arguments: [target_class]
---
<prompt 正文,用 $target_class 之类占位>
```

## 原则
- 永远"提议+确认",绝不自动存;不刷屏、不打断、低置信不建议(这是这类功能被关掉的头号原因)。
- 只在用户说"用"后才载全文;平时翼德只需 index.md(轻)。
