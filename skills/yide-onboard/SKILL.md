---
description: 翼德(yide)首次访谈 onboarding。当用户第一次设置翼德/yide、想建立或重建个人上下文大脑(~/.yide)、或说"初始化翼德/初始化 yide/建大脑/onboard"时使用。会访谈用户并填充 core/ 与 style/。
---

# 翼德 · Onboarding 访谈

目标:为用户建立 `~/.yide/` 大脑,并通过简短访谈填充核心身份、风格与红线。

## 步骤

0. **自我介绍**:先把翼德介绍给用户(谁做的、能在哪三方面帮他、大脑结构、接下来要几分钟选择题磨合)。语气友好、简短。用户说"好/开始"再继续。

1. **选大脑放哪(用选择题,别让用户敲命令行)**:
   - 先探测候选同步盘:Bash 运行 `node "${CLAUDE_PLUGIN_ROOT}/scripts/detect-sync.js"`(每行 `标签\t路径`)。
   - 用 **AskUserQuestion** 让用户挑(他只需点选):把探测到的 Google Drive / Dropbox / iCloud 路径各列一个选项 + "本地(不同步,~/.yide)"。**不要列 OneDrive。**
   - 推荐顺序:Google Drive 或 git 仓库文件夹 > 其他同步盘 > 本地。告诉他选同步盘的好处=换电脑免重新磨合。
   - 若他想用自定义文件夹(如某个 git 仓库目录),让他**粘贴一个路径**(一次粘贴,不是命令)。

2. **建大脑(跨平台,Windows 也能跑)**:用 Bash 运行
   - 选了同步盘/自定义:`node "${CLAUDE_PLUGIN_ROOT}/scripts/install-brain.js" "<用户选的文件夹>/yide-brain"`
   - 选了本地:`node "${CLAUDE_PLUGIN_ROOT}/scripts/install-brain.js"`
   - 输出 `CREATED\t...` → 已建好(指针文件已记住位置),继续访谈。
   - 输出 `EXISTS\t...` → **大脑已存在**(很可能换了设备、同步盘里已有)→ **跳过访谈**,告诉用户"已认出你、无需重新磨合",问他是否补充/修改某项即可。
   - 输出 `ERROR\t...` → 把错误念给用户。
   (脚本用 Node `fs.cpSync`,不依赖 `cp`/`ls`;并把所选位置写进指针文件 `~/.yide-location`,以后所有 hook 都用这个位置——用户无需设环境变量。)

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

5. **收尾**:告诉用户——以后每开一个 Claude Code 会话,翼德会自动注入这份简报、读你的 Unity 项目档案、写 .cs 时自动把关;发现问题时用 `/yide:yide-record` 记一笔;要贴给 Desktop/其他 AI 时用 `/yide:yide-brief`。
   **跨设备**:大脑位置已记在指针文件 `~/.yide-location`。在另一台电脑上,只要把同一个同步盘文件夹(Google Drive / git 仓库)同步过来,装好翼德跑 onboard 时会"认出"已有大脑、免重新磨合。**不要用 OneDrive。**

## 原则
- 遵守用户已有的 hard-rules(尤其:不编造、不过度工程、只做被要求的事)。
- 访谈要轻,别让用户一次回答太多。能从默认模板带过的就别重复问。
