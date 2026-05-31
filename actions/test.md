# 翼德 · QA / 测试(test)

解决两个痛点:① 测试乱测边角、不测重点;② bug 散在对话里、纯自然语言、没 repro/日志/截图。
翼德能纯文件/CLI 做的:**定测试重点、强制 bug SOP、跑测+读结果、整理证据做三查**。

按用户意图选其一(看 `$ARGUMENTS`):

## A. 出一份"聚焦测试计划"(治"乱测边角")
1. 读 `git diff` / `git log`(最近改动)+ 当前 Unity 项目档案 + 用户一句"这次重点是什么"。
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
- 若机器有 Unity 编辑器 + license:`Unity -runTests -batchmode -projectPath . -testPlatform EditMode -testResults r.xml`(冒烟子集用 `-testCategory Smoke`)。**别看退出码**(Unity 无统一约定),**解析 NUnit XML** 判定通过/失败。
- 读 `Player.log` / `adb logcat` / NUnit XML,聚类失败,产出结构化报告(按 SOP)。
- 需 Editor/真机/UI 自动化(AltTester 等)的部分翼德做不了,如实说明,别假装跑过。

## 原则
- 聚焦重点,不堆边角(对应用户痛点);不编造测过、不编造日志;报告必须可复现+带证据。
