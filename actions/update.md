# 翼德 · 安全迁移(yide-update)

原则:**用户数据神圣**。身份、教训(lessons)、项目、用户填写的风格——**一律不动**。只做"补充新默认"和"在用户没改过的发货文件上刷新"。

## 步骤

1. **跑迁移引擎(安全部分自动应用)**:Bash 运行
   `node "${CLAUDE_SKILL_DIR}/scripts/migrate.js" --apply`
   它返回一段 JSON 报告:`{ added[], refreshed[], conflicts[], rulesToAdd[] }`,并已自动:
   - **added**:用户缺的新文件 → 已新增;
   - **refreshed**:发货知识文件(如 `style/unity.md`)且用户没改过 → 已刷新到新版。

2. **报告自动部分**:把 added / refreshed 简短念给用户(让他知道补了什么)。

3. **冲突(conflicts):逐个问用户**。这些是"发货文件,但用户改过、上游也更新了"。对每个:
   - 用 Read 把"用户版"和插件模板版(`${CLAUDE_SKILL_DIR}/templates/brain/<file>`)对比给用户看关键差异;
   - 问他:**保留我的 / 换成新版 / 手动合并**(默认保留用户的)。
   - 按选择用 Edit/Write 处理;**不要替他擅自决定**。

4. **新增默认红线(rulesToAdd):问用户要不要加**。这些是新版带来的默认 hard-rules,用户大脑里还没有(按"(防XXX)"标识判断)。
   - 列给用户看;他同意的,用 Edit 追加到 `~/.yide/core/hard-rules.md`(接着现有编号往下排,保持 ≤15 条预算;超了提示用户精简)。
   - 不删用户已有的任何红线。

5. **收尾**:一句话总结(新增 N 文件 / 刷新 M / 解决冲突 K / 加红线 J),提醒用户他原有的教训和设置都原封未动。

## 原则
- 只增不删;冲突先问;用户私有数据(identity/lessons/projects/用户填的 style)绝不自动改。
- 迁移引擎已更新"基线快照"(`.meta/shipped-base`),供下次比较;无需手动维护。
- 拿不准就保留用户版本(对应红线:不擅自大改、不编造)。
