# 翼德 · 记录教训

目标:把一次"AI 做错了 + 用户的纠正"变成一条**可复用、绝不再犯**的教训。

## 步骤

1. **确定内容**:从 `$ARGUMENTS` 或最近对话里,识别出:AI 当时**做错了什么**、**正确做法是什么**、用户的**原话**。

2. **找下一个编号**:用 Glob/Read 列出 `~/.yide/lessons/` 下的 `L-*.md`,取最大编号 +1(没有则 `L-0001`)。

3. **起草 lesson 卡**(给用户确认,别直接写盘)。遵循最佳实践:
   - **规则正向化**:写"该怎么做"而非"不要怎样",并配对正确替代。配 `**IMPORTANT**`。
     - ❌ 不要用 Debug.Log → ✅ **IMPORTANT** 调试输出一律走项目封装的 Logger(之前因为用了 Debug.Log 出过错)
   - **第一人称教训**(Reflexion 风格):简述"我当时假设了 X,正确规则是 Y"。
   - **具体、可验证**,不泛泛。

4. **问用户**:
   - **severity(1-10)**:≥8 视为红线。
   - **scope**:适用范围(glob 如 `**/*.cs`,或场景如"写 Unity 代码时")。
   - **能不能做成硬拦截?**(见第 7 步)

5. **写入**:基于 `~/.yide/lessons/_TEMPLATE.md` 写 `~/.yide/lessons/L-XXXX.md`,填好 frontmatter(id / date 用今天 / severity / scope / enforce / status: active)与三段正文。

6. **更新索引**:在 `~/.yide/INDEX.md` 的 lessons 段加一行:`- [L-XXXX](lessons/L-XXXX.md) [sev:N] — 一句话`;然后用 Bash 运行 `node "${CLAUDE_SKILL_DIR}/scripts/build-index.js"` 重建编译索引(供把关器快速按文件匹配)。

7. **按 severity 升级**:
   - **severity ≥ 8**:把该规则同时追加到 `~/.yide/core/hard-rules.md`(永远带,全平台软层生效)。
   - **可硬拦截的**(能用一个明确正则在 Bash/Write/Edit 的输入里抓到,例如禁用某 API/某命令):问用户确认后,把 `enforce` 设为 `hook`,并向 `~/.yide/.meta/hook-rules.json` 的 `rules` 数组追加一条 `{pattern, reason, tools}`。**pattern 为 JS 正则**(会被 `new RegExp(pattern)` 加载),tools 是适用工具数组(如 `["Write","Edit","MultiEdit"]`),reason 注明教训编号。这样下次任何会话里该动作会被 PreToolUse hook 直接 block。
   - 拿不准能否硬拦截就别硬塞——保持软层即可(对应红线:不过度工程)。

8. **确认**:把写好的 lesson + (若有)hook 规则念给用户,告诉他"已记录,下次起生效"。

## 原则
- 措辞先给用户确认再落盘。
- 一条教训一个文件,单一关注点。
- 升级硬拦截要保守:只有正则能精确命中、误伤风险低时才做(`Debug.Log` 这类高频词慎做硬拦截,易误伤注释/字符串)。
