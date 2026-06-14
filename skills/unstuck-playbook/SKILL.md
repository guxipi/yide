---
name: unstuck-playbook
description: A cross-domain methodology + anti-stuck playbook distilled from sessions that went WELL — read it for inspiration and a way forward when you feel stuck, are spinning on repeated failures, don't know how to approach a big/vague task, can't tell if your change actually worked, the tools keep fighting you, or you've lost the thread. Trigger on "卡住了" / "不知道怎么办" / "原地打转" / "试了几次都不行" / "无从下手" / "这个怎么搞" / "给点思路" / "方法论" / "怎么做才好" or any moment of being stuck / needing a method. Not domain-specific — it's the how-to-work layer that points to the concrete skills (feature-development, cloud-code-deploy, playmode-verify-iterate, ui-placement, ui-visual-rework) and project memories.
---

# Unstuck Playbook (Extraction · 工作心法 + 卡住急救)

不是某个领域的操作手册——是**做事的方式**。当你卡住、打转、无从下手、或不确定自己做对没有时,读这个找回路。蒸馏自一批"做成了"的 session(Base tab 大功能一次过、服务端实现+部署、UI 成品级重做、bug 根修)。它们的共性不是某项技术,是几条**贯穿始终的工作习惯**。

> 一句话:**先看清,再动手;真相驱动,不靠猜;改源头,不打补丁;小步闭环,验到落地;卡住先停下来命名问题,别蛮干。**

---

## A. 卡住急救:STOP → NAME → 对症(打转时第一件事)

意识到自己在打转(同一个动作试第 3 次、改一处冒一处、说不清现在在干嘛)——**先停**,别再蛮干。

1. **STOP**:停止重复失败的动作。工具被 deny 的调用别原样重试(那是反馈,不是噪音);同一个改法失败两次就换思路,别第三次。
2. **NAME**:用一句话说清你卡在**哪一类**(下面五类对号入座)。说不清卡在哪 = 还没真正理解问题,这本身就是诊断结果 → 回到"看清"。
3. **对症**:按下面分诊表下方子。

---

## B. 五类卡住 × 破法分诊表

| 你卡在… | 信号 | 破法 |
|---|---|---|
| **无从下手**(大/模糊任务) | 面太宽、不知从哪读起、想直接写但没底 | **侦察先行 + 并行 fan-out**:开多个 `Explore` subagent 同时摸不同子系统(代码/文档/数据/UI/服务端),建全局认知再动手。先 `TaskCreate` 拆块、规划,让全局可见。范围模糊先 research 同类做法,仍不确定 → 问勾哥(宁问勿错),别用假设硬填。 |
| **做了没用**(改了不生效/反复无效) | 改完现象没变、或变了别的 | 多半改错了地方或改在补丁层。**改源头**(UI 改 builder 不手摆;根修法已存在就传播+删旧补丁)。先**定位根因、引用代码佐证**再动手,别凭猜继续改。 |
| **验证不了**(不知道对没对) | "应该好了吧"、只看了返回值/截图就想交 | **真相驱动**:写临时探针脚本 dump 真实状态(数值/字段/落盘),`state dump 是权威,截图/返回值会骗人`。验到**副作用真正落地**那一层(数据真变了),不是只看"成功"消息。 |
| **工具不配合**(报错/假结果/打架) | 工具吐 ghost text、check 说谎、"成功"但没效果 | **独立核实**:异常即判失败 → 重调 + 换通道交叉验证(`check_compile_errors` 配 grep logs `error CS`;写操作回读确认落盘)。工具的"成功"可能假。 |
| **迷失方向**(忘了在干嘛/上下文乱) | 不记得目标、task 列表过时、东一榔头西一棒 | 回 `TaskList` 对齐;重述当前目标和"完成判据"一句话;砍掉跑偏的支线,收口到当前这一块(做完 > 做大)。 |

---

## C. 七条心法(成功 session 的共同底色,可迁移到任何任务)

1. **侦察永远先行**。动手前先看清全貌——读 runtime 脚本拿接口、找 builder 拿源头、dump 场景拿真相。大任务用 subagent 并行 fan-out,别自己一行行顺序读(慢且爆上下文)。

2. **真相驱动,绝不靠猜**。Unity 行为、报错、测试结果——有 MCP 就读真值。关键数值亲自 Read 原文(agent 解错过 hex)。bug 先定位根因+引用代码再动手。

3. **deployed / 编译过 / "成功" ≠ 真的工作**。验证要穿到**行为和副作用**那一层。反面教材:整个 CloudCode module 的 `_gameApiClient` 注入是 null,所有 CloudSave 端点其实不工作,却被 try-catch 全掩盖、部署照样"成功"。光看返回会被骗——要验数据真的变了(raid 后 dump 玩家资源确认精确入账)。

4. **改源头,不打补丁**。补丁习惯的标本="根修法已存在却没传播/没删旧补丁"。优先复用 repo 已有干净修法 + 顺手迁同类;UI 改 builder + Rebuild 菜单不手摆;真要止血必明说"临时方案 + 欠技术债"。

5. **小步闭环,迭代到满分**。每轮只修一个能定位根因的问题 → 立刻验证 → 再下一个。原地打转时**缩小每步 + 强制每步验证**。一个改动从进入到完成整条 loop 都顺、好看、无报错才算完。

6. **复用 > 发明**。抄最近同类实现的 helper / 模式 / 套路,贴合周围代码风格与抽象层级。不引入没被要求的抽象、配置、扩展点(最简能解决就行)。

7. **带着"常见 bug 形态"去找**,比瞎找快:① "写了一半没接通"(prefab 没 wire / loc key 缺 / 端点没实现 / 两边配置不符)② init-order(异步 spawn 后才有,别在 Start/Awake 缓存,lazy-resolve)③ 场景重载死掉的一次性初始化服务。

---

## D. 具体动作工具箱(卡住时可直接抄的招)

- **并行侦察**:一条消息发多个 `Agent`(Explore)调用,每个 prompt 具体到"读哪些文件、报什么结构"。
- **临时探针脚本**:`Temp/yide_*.cs` 经 Coplay `execute_script` 跑,`Debug.Log` 真实状态到 logs 再读;或 dump 到 `Temp/*.txt` 再 Read。用完即删。
- **闭环迭代节奏**(改了 editor 代码):停 Play → 等重编译 → `open_scene` 回目标场景 → 跑 builder → SaveScene → 再进 Play 测。
- **交叉验证**:任何"成功"用第二通道确认(编译/落盘/行为/数值)。
- **拆块可见**:`TaskCreate` 分块 + 实时 in_progress/completed,你和勾哥都看得见进度、不漏步。
- **收尾即学习**:非显然的教训写进项目记忆(`memory/` + MEMORY.md 一行索引),让下次不重蹈。

---

## E. 卡太久的出口

工具连续 2-3 次失败、或同一思路反复不通、或探索越走越偏——**停下来摊给勾哥**:说清你试了什么、哪里不通、想怎么走,让他定夺。卡住时多问一句,远胜猜错方向闷头干半天。这不是认输,是把关。

---

## 指路(具体活儿交给对应 skill / 记忆)

- 做/补全功能的完整流程 → `feature-development`
- 服务端改 + 部署 → `cloud-code-deploy`(注意 [[cloudcode-gameapiclient-null]] 的 SDK 坑)
- 进 Play 自测迭代 → `playmode-verify-iterate`
- 摆 UI / 成品级视效 → `ui-placement` / `ui-visual-rework`
- 反补丁工作法 → 记忆 `extraction-anti-hackfix-method`
- 工具假结果 → 记忆 `tool-output-ghost-text`
- 头号铁律(测过再交) → 记忆 `verify-before-handoff`
