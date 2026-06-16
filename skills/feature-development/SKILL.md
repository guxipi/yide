---
name: feature-development
description: End-to-end method for BUILDING or INVESTIGATING/COMPLETING a feature in Extraction at high completion + verified quality. Trigger on "做功能" / "做个新功能" / "补全功能" / "调查这个功能缺什么" / "把XX功能做完整" / "实现XX系统" / "feature 不完整" / "这块没接通" / "refine XX 并补全 implementation" or any non-trivial feature/investigation work. Pipeline — parallel recon (subagents) → task breakdown → builder implementation → close the half-wired "V2" gaps → Play Mode self-verify → memory + 战绩. Companion skills do the specifics, invoke them too — ui-placement / ui-visual-rework (UI), cloud-code-deploy (server), playmode-verify-iterate (the test loop).
---

# Feature Development (Extraction · 分块 / 规划 / good practice)

把"做一个大功能 / 调查并补全一个半成品功能"做到**完成度高、测过、可交付**的元流程。蒸馏自一单实战:Base tab 从平面色块 → 成品级 UI + raid 闭环全通 + 服务端端点实现并部署 production,一次过。本 skill 是**编排层**,具体活儿交给 companion skill,但纪律和顺序在这里。

> 核心信念:**做完 > 做大;先摸清全局再动手;改 builder 不手摆;进 Play 真测;V2 断点专门找。**

---

## 第〇步:先判断这是"建新功能"还是"补全旧功能"

两种入口,流程同源但侦察重点不同:
- **建新功能**:先查同类手游怎么做(默认动作,带引用) → 设计意图落 `Claude Feature Docs/<feature>/` 一篇 doc(没有就建)。
- **补全/调查旧功能**(更常见):假设它是**"写了一半没接通"**。Extraction 里这种标本极多——典型形态见第三步。别假设"没做",先假设"做了一半,断在某处"。

不确定范围/边界 → 先 research 再问勾哥(宁问勿错);琐碎可逆的小改直接做。

---

## 第一步:并行侦察建立全局认知(大功能严禁自己一行行读)

大功能的代码/文档面铺得开,**用 subagent 并行 fan-out** 比自己顺序读快一个数量级,且不污染主上下文。实战里一次开了 5 个 `Explore` agent:

| Agent | 任务 |
|---|---|
| A | 深读整个 feature 的实现代码(所有 .cs),产出系统地图 + 数据模型 + 现有数值清单 + 完成度 |
| B | 读所有设计文档(`Claude Feature Docs/` + `Design_Docs/`),产出设计意图 + 已决定/未决 |
| C | 摸经济/数值衔接面(这功能产/耗什么货币、与主线怎么挂) |
| D | 摸 UI 层:每个 panel 的 serialized 字段 + public API + 动态内容构建方式(为重建 builder 备料) |
| E | 摸服务端:CloudCode 已有/缺哪些端点、部署方式 |

**并行发射**:一条消息里多个 Agent 调用 → 同时跑。每个 agent prompt 要具体到"读哪些文件、报什么结构"。

**铁律:独立核实 agent 输出**。实战里 agent 把 .asset 的 hex 字节解错(把 14400 秒说成 40 秒)。凡是要拿来做决策的关键数值/事实,亲自 Read 原文核实。工具偶发吐 ghost text 假结果,异常即判失败重调。

---

## 第二步:TaskCreate 分块,先规划再动手

把活儿切成有依赖关系的 task(实战的 7 块,可作模板):
1. **侦察落地**:dump 目标在场景里的真实状态(序列化字段哪些 NULL、哪些 panel 存在)——这是"补全"类的真相来源。
2. **备料**(若涉及 UI 视效:提取 SuperCasual 配方,见 `ui-visual-rework`)。
3. **实现主体**(builder 重建 / 新代码)。
4. **补客户端功能缺口**(接通 V2 断点)。
5. **服务端**:修 + 实现 + 编译(见 `cloud-code-deploy`)。
6. **部署服务端**(见 `cloud-code-deploy`)。
7. **进 Play 端到端验证**(见 `playmode-verify-iterate`)。

每块 in_progress→completed 实时更新。`TaskCreate` 的价值不是仪式,是让你和勾哥都看得见"全局还剩什么 + 不漏步"。

---

## 第三步:"V2 写了一半没接通" —— 调查补全的主战场

Extraction 里功能常以"骨架齐、神经没接"的形态存在。**专门搜这几种断点**:
- **Prefab 造好但没 wire**:`*ContentSetup.cs` 造了 prefab/SO,但没有 builder 把它们 wire 进主 panel 的 serialized 字段。实战:6 个 V2 base 面板 prefab 全造好了,但旧 `BaseSceneSetup` 只接了 5 个 v1 面板,新面板 serialized 字段全 NULL。
- **本地化 key 缺**:UI 调 `Loc.Get/Format(TABLE_X, "key")` 但 key 没进 StringTable → 界面显示原始 key 字符串。批量补:照 `LocalizationTableSetup` 的 `collection.SharedData.AddKey + enTable.AddEntry` 模式,做进 builder 顺手加。
- **服务端端点客户端调了但没实现**:客户端 `CloudCodeManager` 有调用、服务端没对应 `[CloudCodeFunction]`(或反过来客户端缺 wrapper 方法 → 卡死整个 Unity 编译)。见 `cloud-code-deploy`。
- **buff/产出没接进消费端**:产出资源/buff 算出来了但没人读。先验证管线接没接(grep 消费方),没接就接上或明说欠债。
- **客户端/服务端配置不符**:同一个值两边硬编码且不一致(实战:服务端说 HQ 满级 10,客户端配置是 5)。对齐。

dump 真相的方法:写临时 editor 脚本(`Temp/yide_*.cs`)经 `execute_script` 跑,递归打印 serialized 字段值(NULL 与否)、hierarchy、tab 顺序,写到 `Temp/*.txt` 再 Read。

---

## 第四步:实现纪律(贴合 repo,别堆屎山)

- **改 builder,不手摆场景**:UI/场景对象由 `Assets/Scripts/Editor/Setup/*Setup.cs` 代码生成。新建/重写 builder + 一个 `Tools/Setup/... Rebuild` 菜单。`SaveAsPrefabAsset` 同路径覆盖保 GUID;`SerializedObject.FindProperty` 带 null 检查 wire 字段;sprite 加载失败 `LogWarning` 路径。
- **复用既有套路保持一致**:抄最近的同类 builder 的 helper(`ApplySprite`/`CreateUIChild`/`SetRef`/`PlaceText`),别每次发明。视效走 `ui-visual-rework` 的配方提取法。
- **生产级视效从第一版就上**(项目默认):材质底纹 + 动效,没素材就从别的 feature 借。
- **最简方案**:不引入没被要求的抽象/配置项/扩展点。只动该动的文件。
- **新代码贴合周围风格与抽象层级**。Unity 用项目 Logger,不裸 `Debug.Log`(无则回退)。

---

## 第五步:验证 → 收尾(不测不算完)

1. **编译干净**:`check_compile_errors` + grep Unity logs `error CS` **交叉验证**(工具偶发说谎)。
2. **进 Play 端到端真测 + 迭代到满分**:这是头号铁律,完整流程见 `playmode-verify-iterate`——不是截一张图就完,是真点击走全链路、发现问题回来一轮轮修到玩家体验满分。
3. **收尾**:写一条 project 记忆(可复用的非显然事实:builder 入口、部署方式、踩的坑);推进了 ER 产品就 `progress.js bump`;完成后问勾哥"上传 Planyway 吗"。
4. 非琐碎改动可跑一次"翼德 评审"让独立上下文挑正确性/耦合。

---

## 已验证的"会拖慢/翻车"的坑速查

| 坑 | 真相 |
|---|---|
| 自己顺序读大功能全部代码 | 慢且爆上下文;改用并行 Explore agent fan-out |
| 信 agent/工具的二手数值 | 关键值亲自 Read 原文核实(hex 解错过) |
| 假设旧功能"没做" | 多半"做了一半没接通";先 dump 真相找断点 |
| 手摆场景 | 永远改 builder + Rebuild 菜单,否则下次重建被冲掉 |
| 改完只 check_compile_errors | 它会说谎;grep logs `error CS` 交叉验证 |
| 改完不进 Play 就交 | 头号红线;走 `playmode-verify-iterate` |