# 翼德 · Onboarding 访谈

目标:为用户建立 `~/.yide/` 大脑,并通过简短访谈填充核心身份、风格与红线。

## 步骤

0. **自我介绍**:先把翼德介绍给用户(谁做的、能在哪三方面帮他、大脑结构、接下来要几分钟选择题磨合)。语气友好、简短。用户说"好/开始"再继续。

1. **先探测:是不是"新设备 / 已有大脑"**:Bash 运行 `node "${CLAUDE_SKILL_DIR}/scripts/detect-sync.js"`。
   - 若输出里有 `BRAIN\t<路径>` 行 → 说明同步盘里**已有大脑**(换了新设备)→ 跑 `node "${CLAUDE_SKILL_DIR}/scripts/install-brain.js"`(无参数,会 **ADOPTED** 自动认领、重建本机指针)→ **跳过访谈**,告诉用户"已认出你、无需重新磨合(教训/风格/红线都在)",问是否要补充/改某项即可。**结束。**
   - 若**没有** `BRAIN` 行 → 是首次,进第 2 步。

2. **首次:选大脑放哪(选择题,别让用户敲命令行)**:
   - 把第 1 步探测到的 Google Drive / Dropbox / iCloud 路径用 **AskUserQuestion** 列出 + "本地(不同步,~/.yide)";想用 git 仓库目录就让他**粘贴一个路径**。**不要列 OneDrive。** 推荐同步盘(换电脑免重磨)。
   - 建大脑(跨平台):选同步盘/自定义 → `node "${CLAUDE_SKILL_DIR}/scripts/install-brain.js" "<选的文件夹>/yide-brain"`;选本地 → 无参数。
   - 输出 `CREATED\t...` → 已建好(指针已记住),继续访谈;`ADOPTED/EXISTS\t...` → 已认出你,跳过访谈;`ERROR\t...` → 念给用户。
   (脚本用 Node `fs.cpSync` 不依赖 `cp`/`ls`;位置写进指针 `~/.yide-location`,无需环境变量。)

2. **访谈 —— 用选择题(务必用 AskUserQuestion 工具,不要开放式提问)**。
   分 2-3 批,每批 3-4 题,每题给 2-4 个选项(用户也可选 Other 自填)。能自动探测的先探测、别问:
   - 当前若在 Unity 项目里,先读 `ProjectSettings`/`Packages/manifest.json` 拿到 **Unity 版本、渲染管线、Input System、Addressables**(SessionStart 的探测逻辑已具备),这些就不要再问。
   - 操作系统用 `process.platform` 推断。

   参考选项(按需增减):
   - **目标帧率**:30 / 60 / 不锁帧
   - **渲染管线**(探测不到时才问):Built-in / URP / HDRP
   - **IDE**:Rider / Visual Studio / VS Code
   - **回复语言**:中文 / 英文 / 中英混(术语英文)
   - **回答结构**:先结论再过程 / 先过程再结论
   - **指错方式**:直接点出 / 先肯定再建议
   - **要不要 file:line 引用**:要 / 不用
   - **日志**:封装 Logger / Debug.Log / 看情况
   - **注释密度**:关键处即可 / 多 / 少
   - **测试习惯**:手测为主 / PlayMode / EditMode 单测
   - **额外红线**(多选):别碰指定目录 / 别改第三方插件 / 别动构建配置 / 无额外(可 Other 自填)

   规则:能从默认模板或已答推断的就别重复问;Unity best practice 已内置 unity.md,不必逐条问。

3. **写入**:把答案分别填进
   - `~/.yide/core/identity.md`
   - `~/.yide/style/communication.md`、`style/coding.md`、`style/writing.md`
   - 新增红线追加到 `~/.yide/core/hard-rules.md`(正向、具体、带 `**[sev:N]** IMPORTANT`)。
   - Unity best practice 已内置在 `style/unity.md`,无需重填。

4. **核对**:把填好的 `identity.md` 和 `hard-rules.md` 念给用户确认,有错当场改。

4.5 **免权限弹窗(选择题,征得同意再做)**:问用户"要不要让我免去以后每次跑脚本的权限弹窗?"
   - 同意 → 用 Edit 在用户设置 `~/.claude/settings.json` 的 `permissions.allow` 数组里加一条**窄规则**(只允许翼德脚本,不是所有 node):
     `"Bash(node:*yide*scripts*)"`
   - 文件不存在就创建 `{"permissions":{"allow":["Bash(node:*yide*scripts*)"]}}`;已存在就只往 allow 追加这一条、别动其他。
   - 解释:这只放行"翼德 scripts 目录下的 node 脚本",比放行全部 node 安全。

5. **收尾**:告诉用户——以后每开一个 Claude Code 会话,翼德会自动注入这份简报、读你的 Unity 项目档案、写 .cs 时自动把关;发现问题时说"翼德 记一下…";要贴给 Desktop/其他 AI 时说"翼德 简报"(也可打 `/yide:yide record` / `/yide:yide brief`)。
   **跨设备**:大脑位置已记在指针文件 `~/.yide-location`。在另一台电脑上,只要把同一个同步盘文件夹(Google Drive / git 仓库)同步过来,装好翼德跑 onboard 时会"认出"已有大脑、免重新磨合。**不要用 OneDrive。**

## 原则
- 遵守用户已有的 hard-rules(尤其:不编造、不过度工程、只做被要求的事)。
- 访谈要轻,别让用户一次回答太多。能从默认模板带过的就别重复问。
