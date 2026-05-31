# 翼德 · prompt 库(prompts)

为"不会主动记、也不记得何时该用"的勾哥而设计:**翼德自动注意好 prompt→达标静默存→下次在对的时机自动端上来→够熟升级成命令**。全程他可零操作。
存在 `~/.yide/prompts/`(全项目通用、随大脑同步)。

## A. 捕获 —— 自动 + 静默 + 带质量门(不再每条问他)
在一个任务收尾时,评估**刚才用户那条 prompt** 是否值得长期复用:
- **质量门(≥2 个信号才存)**:① 几轮内就搞定 ② 用户明确满意("对了/完美/就这样")③ 产出没返工 ④ 这类措辞反复出现过。
- **去重**:先看 `prompts/index.json`,已有近似的就**别新建**,改跑 `node "${CLAUDE_SKILL_DIR}/scripts/prompts.js" use <slug>`(uses+1)。
- 达标且新颖 → **静默存**:写 `~/.yide/prompts/<slug>.md`(schema 见下),然后 `node "${CLAUDE_SKILL_DIR}/scripts/prompts.js" index` 重建索引。**只回一行**:"已把这条收进库:〈名字〉,不要就说删掉。"——不打断、不要他确认。
- 拿不准质量 → 宁可不存(避免垃圾污染库,否则他会不信任)。

## B. 召回 —— 自动(由 UserPromptSubmit hook 负责,你无需做事)
hook 会在勾哥每次发话时匹配库并温和推荐一条(同会话不重复、低置信不推)。
当用户说"用 / 套用 / 用那条"时:读对应条目,把 `{{占位符}}` 按当前任务填好执行,并 `prompts.js use <slug>`(uses+1)。

## C. 通用化(存的时候就做)
- **核心逐字保留**(那是它好用的原因);只把 **1–3 个任务专属名词**(类名/路径/报错串/平台)抽成 `{{占位符}}`。别过度抽象。
- 配好元数据(下面)以便召回命中。

## D. 升级成命令
- 某条 `uses >= 3` → 提议:"〈名字〉你用了 N 次,做成 `/<slug>` 命令?" 同意就把文件挪到 `~/.claude/skills/<slug>/SKILL.md`(懒加载、不占上下文)。

## 文件 schema
```yaml
---
name: 生成Unity测试
slug: gen-unity-test
description: 何时用(一句话,召回靠它)
tags: [unity, testing]
keywords: [单元测试, MonoBehaviour, NUnit]   # 召回匹配用,写 2-4 个高区分度的
globs: ["**/*.cs"]                            # 可选
uses: 0
created: 2026-01-01
---
为 {{target_class}} 生成 NUnit 测试:按生命周期分组、列 edge cases……(核心逐字)
```

## /yide prompt(用户主动)
无参数/`list` → 列库;`<关键词>` → 搜。

## 原则
- 捕获静默不打断、有质量门、去重;召回不刷屏、低置信不推、可忽略;只在用户说"用"时才载全文。
- 不编造他没说过的 prompt;库脏了他就不信——宁缺毋滥。
