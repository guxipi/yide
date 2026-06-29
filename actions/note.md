# 翼德 · 随手记(capture)

让勾哥随时记想法/笔记/随想,翼德按**时间 / 主题 / 项目**归类,日后可查。
数据在大脑里 `~/.yide/notes/`:`inbox/`(待整理)、`<YYYY>/`(按年归档)、`index.md`(主题/项目索引)。

三种用法(看 `$ARGUMENTS`):

## A. 直接录入(他在对话里说"记笔记 …/想法 …")
- 把内容写成一条带 frontmatter 的笔记:`~/.yide/notes/<YYYY>/<YYYY-MM-DD>-<短标题>.md`
  ```
  ---
  created: 2026-05-31T14:20
  topic: <你判断的主题>
  project: <相关项目或 none>
  tags: [..]
  source: chat
  ---
  <原文 + 必要的一句澄清>
  ```
- 在 `notes/index.md` 加一行索引。简短确认。

## B. 整理 inbox(他从手机扔进来的)
> 手机端怎么进来(Phase 1,零服务器):大脑放在 Google Drive 同步盘时,他用手机的 Google Drive / Obsidian / 记事本往 `~/.yide/notes/inbox/` 丢 `.md`/`.txt`;电脑联网后翼德处理。
> (若配了 Telegram bot 集成 → 手机直接发消息也会落进这个 inbox,配置见 `integrations/telegram/SETUP.md`。)
1. 读 `~/.yide/notes/inbox/` 下所有文件。
2. 每条:判断主题、关联项目、抽 tags、定时间(文件时间或内容里的日期)。
3. 归档到 `~/.yide/notes/<YYYY>/`,写好 frontmatter;更新 `notes/index.md`(按主题/项目分组)。
4. 处理完把原始件移到 `notes/inbox/_done/`(软删,保留),报告"整理了 N 条,涉及主题/项目 …"。

## C. 查询("问翼德:关于 X 我记过什么")
- 在 `~/.yide/notes/` 里按关键词/主题/项目/时间检索(grep/读 index),把相关笔记汇总回答,附文件路径方便他翻原文。

## 原则
- 不丢原文、不擅自改写他的想法(可补澄清,但保留原话);分类拿不准就标 `topic: 待定` 而不是瞎归。
- 归档结构是纯 markdown,任何工具(Obsidian/编辑器)都能直接看。
