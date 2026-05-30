---
description: 翼德(yide)生成可移植简报。当用户要把自己的偏好/规则带到 Claude Desktop、ChatGPT、Gemini 等其他 AI,或说"翼德简报/yide 简报/给我简报/brief/导出上下文/复制给别的AI"时使用。生成一段可直接复制粘贴的 Markdown。
argument-hint: [可选:场景,如 coding / unity / writing / 某项目名]
---

# 翼德 · 生成简报

目标:把大脑浓缩成一段**可复制粘贴**的简报,贴进任何 AI 的对话或自定义指令里。

## 步骤

1. **读大脑**:读取 `~/.yide/INDEX.md`、`core/identity.md`、`core/hard-rules.md`。

2. **按场景取材**(看 `$ARGUMENTS`):
   - 无参数 → 通用简报:身份 + 全部 hard-rules + 沟通偏好。
   - `coding` / `unity` → 额外并入 `style/coding.md`、`style/unity.md` 及 scope 命中代码的 lessons。
   - `writing` → 额外并入 `style/writing.md`。
   - 某项目名 → 额外并入 `projects/<名>.md`。

3. **合成简报**,用下面这个结构(简洁、命令式、把红线放最前):

   ```markdown
   # 关于我(请在本次对话全程遵守)

   ## 绝对规则(最高优先级)
   - <hard-rules 逐条,正向命令式>

   ## 我是谁
   - <身份/技术栈/语言偏好 精简版>

   ## 沟通偏好
   - <怎么回我 / 讨厌什么>

   ## 本场景相关(若有)
   - <coding / writing / 项目 的关键点>
   ```

4. **输出**:把这段 Markdown 直接打印在回复里,用代码块包起来,方便用户一键复制。提示他:贴进对方 AI 的"自定义指令/Project 说明"里效果最好(一次设置长期生效)。

## 原则
- 简报要短而高信息密度:别把整个大脑倒出来,只放当前场景用得上的。
- 红线放最前(LLM 对开头/结尾的指令最敏感)。
- 只输出确实存在于大脑里的内容,不补充、不编造。
