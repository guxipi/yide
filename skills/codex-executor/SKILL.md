---
name: codex-executor
description: 主会话当大脑、OpenAI Codex CLI(gpt-5.6-sol)当执行手的协作工作法 — 派侦察/施工工单、串行调度、沙箱坑、工单模板、大脑侧验收纪律。Trigger — 用户说「让 sol 做」「codex 执行」「5.6 来干」「派给 codex」,或想把读大文档/扫码/批量改码/出图交给 OpenAI 侧跑时。
---

# Codex (gpt-5.6-sol) 执行手工作法

经 2026-07-10 FTUE 盘点+施工实战验证。核心分工:**主会话=大脑**(读设计 SSOT 做裁决、写工单、抽查报告、Unity Play 验收、commit/deploy);**sol=手**(读大文档、扫代码、按工单写码、出图)。什么活派给 sol 由勾哥当次说;美术工具分工见本机记忆 `art-model-tool-routing`。想让一个 Claude 子 agent 代为调度和核对 diff,派项目里的 `codex-executor` agent。

## 1. 调用配方(踩坑后的正确姿势)

```bash
# 侦察(只读):
codex exec --sandbox read-only --skip-git-repo-check --cd "<workdir>" \
  --output-last-message "<scratchpad>/report.md" "$(cat <scratchpad>/order.md)" < /dev/null

# 施工(可写 workdir):
codex exec --sandbox workspace-write --skip-git-repo-check --cd "<workdir>" \
  --output-last-message "<scratchpad>/report.md" "$(cat <scratchpad>/order.md)" < /dev/null
```

- **`< /dev/null` 必加**:非 TTY 下 codex exec 会挂起等 stdin EOF("Reading additional input from stdin...")。
- **`--output-last-message`**:最终报告落文件,别从 stdout 抠(进度混在一起)。
- 工单写成文件再 `"$(cat ...)"` 传入,避免引号地狱。
- 后台跑(Bash run_in_background),等完成通知,不写 sleep 轮询;一单常 10-40 分钟。
- **codex CLI 0.160 起已删掉 `--full-auto`**(本机 2026-10-30 为 0.163),施工用 `--sandbox workspace-write`(只读侦察仍 `--sandbox read-only`);带参考图用 `-i a.png -i b.png`(出图/对照任务必带)。
- 版本:`gpt-5.6-sol` 需 codex CLI ≥0.144(报"requires a newer version"就 `npm install -g @openai/codex@latest`)。模型/登录复用桌面 App 的 `~/.codex/config.toml`,Extraction 已是 trusted 项目。

## 2. 铁律:严格串行,绝不并行

**Windows 下并行跑多个 codex exec 会把沙箱层挤瘫**:每条 shell 命令起一个 `codex-windows-sandbox-setup` 进程,3 个实例并行 → 几十个沙箱进程空转 → 所有 agent 文件读超时 → sol 触发自己的"读不到就不盲改"红线,零改动退出(干净失败,报告说"请恢复终端访问")。

- 一次只跑 **1 个** codex exec(用户上限 5,实测 3 就炸,别赌)。
- 炸过之后先清理:`Get-Process codex-windows-sandbox-setup | Stop-Process -Force`(桌面 App 的 codex 主进程别杀,看 StartTime 区分)。
- sol 会自己 spawn 子 agent(session jsonl `thread_source:"subagent"`),进程数>agent 数是正常的。

## 3. 工单模板(自包含,sol 不共享你的上下文)

```
# 施工工单 WO-N:<一句话目标>
workdir = <路径>。共享工作树有别人 WIP——只改本工单列出的文件,绝不 git commit/push/stash。
## 背景(已核实的事实,给 file:line)
## 要做的事(分节,每节给范式源文件让它镜像,别让它自造)
## 红线
- 文件白名单;并行工地互斥文件列出来「读可以绝不能写」
- 不发明数值/API;只用读源码确认存在的东西
- 客户端序列化字段只加不删;DTO 全字段镜像 server
## 交付报告(最终回复)
1. 改动文件清单+每处一句话 2. 构建/测试结果 3. 指定调查项结论 4. 残留风险
## 作业环境注意
- 不要调用 Coplay MCP(headless 下 approval 自动取消,报 user cancelled)
- 读文件一律 shell(cat/rg/sed);命令超时原样重试一次再换分段小命令
```

侦察工单同理:列输入源(文档+代码)、报告格式(总览表/逐项 file:line 证据/差距分级 P0-P2)、「每个结论给证据、不轻信文档与 commit message」、限 500 行。

## 4. 大脑侧纪律(这些活不能转包)

1. **设计裁决亲自做**:派施工单前亲读设计 SSOT 关键段。实例:sol 盘点把「TutorialHpMul 无运行时消费者」报成差距,施工图其实明写"设计就是烘进资产,别找运行时钩子"——不亲读就会派错工单。
2. **载重结论逐条抽查**:sol 报告的 P0 每条用 Read/Grep 定点核实再动工(实测 4/4 属实,但行号/路径偶有小偏差)。
3. **归因快照**:共享工作树,派单前 `git status --porcelain > snapshot`,收工后 diff 归因——sol 的改动 vs 别人工地的改动要能分开。
4. **Unity 侧全归大脑**:编译检查、builder 运行、Play 验证由主会话走 Unity CLI(见 `playmode-verify-iterate`);sol 接不到 Editor,headless 下 Coplay 工具也全被自动拒。
5. **commit/deploy 全归大脑**:显式路径 commit;CloudCode 部署串行且只 `-e development`。
6. **额度监控**:Codex 5h 窗口限额,session jsonl 尾部 `rate_limits.primary.used_percent` 可查;侦察一单约 2 万 token,施工单更多。爆额度前收敛派单。

## 5. 失败模式速查

| 症状 | 根因 | 处置 |
|---|---|---|
| 挂起无输出 | stdin 等 EOF | 加 `< /dev/null` |
| 400 requires newer version | CLI 旧 | npm 升级 codex |
| 报告说"终端/文件访问失败请重派" | 并行沙箱拥堵 | 杀僵尸沙箱进程,串行重派(工单原文可直接重用,追加环境注意节) |
| user cancelled MCP tool call | headless 下 MCP approval 自动拒 | 工单里禁用该 MCP,让它用 shell |
| 树上多了非白名单改动 | 多半是别人工地 | 对 snapshot 归因,别误删 |

失败是干净的:sol 守"读不到就不盲改",零改动退出,重派即可,不用擦屁股。
