# 翼德 · QA / 测试(test)

解决两个痛点:① 测试乱测边角、不测重点;② bug 散在对话里、纯自然语言、没 repro/日志/截图。
翼德能纯文件/CLI 做的:**定测试重点、强制 bug SOP、跑测+读结果、整理证据做三查**。

按用户意图选其一(看 `$ARGUMENTS`):

## A. 出一份"聚焦测试计划"(治"乱测边角")
1. 读 `git diff` / `git log`(最近改动)+ 当前 Unity 项目档案 + **"本次重点"**。重点来源让勾哥当场选:
   - **贴一句**给翼德(最简单);或
   - **从 Slack 读**:若已接 Slack MCP/连接器,翼德直接读他指定的频道/线程提取本次重点(不用复制);
   - 都没有 → 就从 git commit 信息推断,但提示可能不准。
2. 用**风险 = 失败可能性 × 业务影响**排序,产出 **P0→P3** 测试清单:P0=本次改动触及的关键路径/高风险;边角 edge case 降到最后。
3. 每条注明:测什么、为什么(关联哪个改动/文件/场景)、怎么测(手测步骤或对应的 PlayMode/EditMode 测试名)。
4. 写到项目里 `QA/test-plan-<日期>.md`,让他照着测。**别一股脑列全量,聚焦重点。**

## B. 强制 bug 报告 SOP(治"散、没证据")
1. 项目里若没有,创建结构化模板:把 `${CLAUDE_SKILL_DIR}/templates/qa/bug-report.md` 和 `BUG-SOP.md` 复制到项目 `QA/`(或 `.github/ISSUE_TEMPLATE/bug.yml`)。
2. 当用户/测试在对话里甩来一条自然语言 bug:**把它改写进模板**——标题、严重度 vs 优先级、复现步骤(编号、从已知状态起)、期望 vs 实际、环境(设备/系统/构建版本)、**证据(日志/截图/视频)**。
3. **缺字段就挡回去**:明确列出"缺:复现步骤 / 日志 / 构建版本",要求补齐再立项。不接受三无报告。

## C. 让游戏自动留证据(治"没日志/截图")
- 把 `${CLAUDE_SKILL_DIR}/templates/qa/EvidenceCapture.cs` 介绍给用户、按需放进项目:它订阅 `Application.logMessageReceived` 写日志文件 + `ScreenCapture.CaptureScreenshot` + 抓 `Application.version`/`SystemInfo`/场景名到 JSON,一键打包。
- 提醒:翼德不能替他按 Play/出包/上真机;但证据落盘后,翼德能读回来做三查。

## D. 跑测 + 三查(triage)
- **若接了 Unity MCP**(见 `integrations/unity-mcp/`,且 Unity 开着):直接 `run_tests`(EditMode/PlayMode)读 pass/fail、`read_console` 读报错——真·在引擎里验证。
- **否则**(纯 CLI,需本机 Unity 编辑器 + license):`Unity -runTests -batchmode -projectPath . -testPlatform EditMode -testResults r.xml`(冒烟子集 `-testCategory Smoke`)。**别看退出码**(Unity 无统一约定),**解析 NUnit XML**。
- 读 `Player.log` / `adb logcat` / NUnit XML,聚类失败,产出结构化报告(按 SOP)。
- 没有以上条件就如实说"跑不了",别假装跑过。

## E. 改老代码前先系"安全绳":行为快照测试(治"修一个 bug 坏六个")
针对屎山/高耦合代码改动 —— 不是验证它"对不对",而是先**记录它现在的行为**,改完比对,**一动坏就当场报警**(业界叫 characterization test)。
1. **先拍快照**:动手前,围绕"将要改的那块 + 它现在还正常的相邻功能",让 **Claude 自己写**几个 EditMode/PlayMode 测试,断言**当前的实际行为**(哪怕这行为本身不完美——先锁住现状)。
2. **改完真跑**:有 Unity MCP 就 `run_tests` 真跑;**绿了才算修好**,红了说明碰坏了别处,立刻回头。
3. **怎么不烦人(重要)**:
   - **只对非琐碎 / 改到耦合处或关键路径的改动做**;琐碎、可逆、独立的小改**跳过**,别为它写测试拖慢手感。
   - **Claude 自动写、自动跑**,勾哥只看结果——别把写测试甩给他(他不爱写测试)。
   - 那块代码缠得太死、根本没法单独测出来 → **别硬写**:如实说"这块当前测不了",改用 `翼德 评审` + 列一份手测步骤兜底,并记一条"这里缺测试覆盖"的欠账。

## 文件去哪、怎么跟公司配合(归档口径)
- **测试计划** → 项目内 `QA/test-plan-<日期>.md`。
- **bug 报告** → 项目内 `QA/bugs/<日期>-<短标题>.md`;若公司用 Jira/GitHub Issues,改写进对应模板**贴过去**,翼德不擅自建外部工单。
- **证据**(日志/截图)→ `EvidenceCapture.cs` 默认存到 `Application.persistentDataPath/yide-evidence/`;附进 bug 报告时拷到 `QA/bugs/` 同名目录。
- **翼德的"教训"(可复用经验)进 ~/.yide**,**项目相关产物进项目仓库**——两者分开,不混。

## 原则
- 聚焦重点,不堆边角;不编造测过/日志;报告必须可复现+带证据。
