# 翼德 · 记录教训(record)

目标:把一次"AI 做错了 + 用户的纠正"变成**下次真能生效**的规则。

> **2026-07-25 起最重要的一步是分流,不是写卡片。**
> 旧做法把所有教训写进 `~/.yide/lessons/`,靠 PostToolUse 按 scope glob 自动浮现——实测几乎从不命中(改 .cs/.unity 时命中 0 条,MCP 改场景根本不走 PostToolUse),写进去等于沉底。
> `lessons/` 现在**没有任何自动加载机制**,只是历史档案。要让规则生效,必须放进下面四层里的一层。

## 第一步:确定内容

从 `$ARGUMENTS` 或最近对话里识别:AI 当时**做错了什么**、**正确做法是什么**、用户的**原话**。

## 第二步:分流(决定放哪层)

| 这条规则的性质 | 放哪 | 什么时候生效 |
|---|---|---|
| 通用行为约束,跨项目都成立,严重(sev≥8) | `~/.yide/core/hard-rules.md` | 每次会话常驻 |
| 通用工作方法 / 权限约定 / 本机环境事实 | `~/.yide/core/charter-extra.md` | 每次会话常驻 |
| 只在某个项目成立(路径、约定、铁规) | 该项目的 `CLAUDE.md` | 在该项目的会话里常驻 |
| 某类活的技术知识(摆 UI / 写服务端 / 做 VFX / 模型 intake…) | 对应 skill 的 `SKILL.md`(`skills/<name>/`) | 干这类活时自动加载 |
| 能用一个精确正则在工具输入里抓到的硬约束 | `~/.yide/.meta/hook-rules.json` | PreToolUse **真 block** |
| 以上都不是(一次性的、纯历史) | `~/.yide/lessons/L-XXXX.md` | 不自动生效,只作档案 |

判据是一句话:**"下次这条该在什么时刻出现在上下文里?"** 答案决定层级;答不上来就说明它不该被记成规则,问勾哥。

写进常驻层(前两行)前先掂量:那两层每一条都吃每次会话的注入预算,现代模型原生已覆盖的通用规范(诚实、不越界、别过度工程、结论先行)**不要再写进去**,重复只是占位。

## 第三步:落地

- **常驻层 / 项目 CLAUDE.md / skill**:直接改对应文件,措辞先给勾哥确认再落盘。规则**正向化**("该怎么做"而非"不要怎样"),具体、可验证,常驻层配 `**IMPORTANT**`。
  - ❌ 不要用 Debug.Log → ✅ **IMPORTANT** 调试输出一律走项目封装的 Logger
- **hook 规则**:向 `.meta/hook-rules.json` 的 `rules` 追加 `{pattern, reason, tools}`。pattern 是 **JS 正则**(`new RegExp(pattern)` 加载),reason 写清为什么拦。保守:只在正则能精确命中、误伤风险低时才做(`Debug.Log` 这类高频词慎做,易误伤注释/字符串)。
- **档案**:基于 `~/.yide/lessons/_TEMPLATE.md` 写 `~/.yide/lessons/L-XXXX.md`(编号取现有最大 +1),frontmatter 填 id/date/severity/status。**不必再写 scope glob**(没有消费者了),也不必重建索引。

## 第四步:确认

把落地位置 + 措辞念给勾哥:"记在了 X 层,下次 <什么时刻> 会自动带上"。说不出生效时刻 = 没记对地方。

## 收尾(写了大脑就同步)
- 落盘后跑 `node "${CLAUDE_SKILL_DIR}/scripts/brain-git.js" sync "记教训:<简述>"`:大脑是 git 仓则自动 commit+push(工具自身数据持久化,受红线定向豁免,别回头问权限);非 git 大脑自动 no-op。
- 若规则写进了 **skill 或项目 CLAUDE.md**(那是代码仓,不是大脑),按各自仓的 commit 规矩走,别混进大脑同步。
