---
name: feature-development
description: Build or investigate/complete a feature in Extraction at high completion + verified quality, plus the anti-stuck triage. Trigger — "做功能" / "补全功能" / "调查这个功能缺什么" / "把XX功能做完整" / "实现XX系统" / "这块没接通" / "refine XX 并补全 implementation" / "卡住了" / "原地打转" / "试了几次都不行" / "无从下手" / "给点思路". Pipeline — recon → breakdown → build → close half-wired V2 gaps → Play self-verify. Companions — ui-placement, ui-visual-rework, cloud-code-deploy, playmode-verify-iterate, qa-testing.
---

# Feature Development (Extraction · 分块 / 规划 / good practice / 卡住急救)

把"做一个大功能 / 调查并补全一个半成品功能"做到**完成度高、测过、可交付**的元流程。蒸馏自一单实战:Base tab 从平面色块 → 成品级 UI + raid 闭环全通 + 服务端端点实现并部署(dev),一次过。本 skill 是**编排层**,具体活儿交给 companion skill,但纪律和顺序在这里。卡住、打转时看文末附录。

> 核心信念:**做完 > 做大;先摸清全局再动手;改真源不打补丁;进 Play 真测;V2 断点专门找。**

---

## 第〇步:先判断这是"建新功能"还是"补全旧功能"

两种入口,流程同源但侦察重点不同:
- **建新功能**:先查同类手游怎么做(默认动作,带引用) → 设计意图落 `Claude Feature Docs/<feature>/` 一篇 doc(没有就建)。
- **补全/调查旧功能**(更常见):假设它是**"写了一半没接通"**。Extraction 里这种标本极多——典型形态见第三步。别假设"没做",先假设"做了一半,断在某处"。

范围/边界拿不准:先查真源(vault 设计文档、Config Hub、引擎实读)。真正影响方案的二选一一次弹窗问全;其余自己定,在交付里写明假设。琐碎可逆的小改直接做。

---

## 第一步:并行侦察建立全局认知(大功能严禁自己一行行读)

大功能的代码/文档面铺得开,**用 subagent 并行 fan-out** 比自己顺序读快一个数量级,且不污染主上下文。实战里一次开了 5 个 `Explore` agent:

| Agent | 任务 |
|---|---|
| A | 深读整个 feature 的实现代码(所有 .cs),产出系统地图 + 数据模型 + 现有数值清单 + 完成度 |
| B | 读所有设计文档(`Claude Feature Docs/` + `Design_Docs/`),产出设计意图 + 已决定/未决 |
| C | 摸经济/数值衔接面(这功能产/耗什么货币、与主线怎么挂) |
| D | 摸 UI 层:每个 panel 的 serialized 字段 + public API + 动态内容构建方式 |
| E | 摸服务端:CloudCode 已有/缺哪些端点、部署方式 |

**并行发射**:一条消息里多个 Agent 调用 → 同时跑。每个 agent prompt 要具体到"读哪些文件、报什么结构"。

**铁律:独立核实 agent 输出**。实战里 agent 把 .asset 的 hex 字节解错(把 14400 秒说成 40 秒)。凡是要拿来做决策的关键数值/事实,亲自 Read 原文核实。工具偶发吐 ghost text 假结果,异常即判失败重调。

---

## 第二步:分块列任务清单,先规划再动手

把活儿切成有依赖关系的块,放进任务清单(桌面 app 用 `update_plan`,CLI 用 `TaskCreate`)。实战的 7 块可作模板:
1. **侦察落地**:dump 目标在场景/prefab 里的真实状态(序列化字段哪些 NULL、哪些 panel 存在)——这是"补全"类的真相来源。
2. **备料**(若涉及 UI 视效:提取 SuperCasual 配方,见 `ui-visual-rework`)。
3. **实现主体**(改 prefab / builder / 新代码,按第四步判轨)。
4. **补客户端功能缺口**(接通 V2 断点)。
5. **服务端**:修 + 实现 + 编译(见 `cloud-code-deploy`)。
6. **部署服务端**(只部 `-e development`,见 `cloud-code-deploy`)。
7. **进 Play 端到端验证**(见 `playmode-verify-iterate`,测什么见 `qa-testing`)。

每块实时更新状态,让你和勾哥都看得见"全局还剩什么 + 不漏步"。

---

## 第三步:"V2 写了一半没接通" —— 调查补全的主战场

Extraction 里功能常以"骨架齐、神经没接"的形态存在。**专门搜这几种断点**:
- **Prefab 造好但没 wire**:`*ContentSetup.cs` 造了 prefab/SO,但没人把它们 wire 进主 panel 的 serialized 字段。实战:6 个 V2 base 面板 prefab 全造好了,但旧 `BaseSceneSetup` 只接了 5 个 v1 面板,新面板 serialized 字段全 NULL。
- **本地化 key 缺**:UI 调 `Loc.Get/Format(TABLE_X, "key")` 但 key 没进 StringTable → 界面显示原始 key 字符串。批量补:照 `LocalizationTableSetup` 的 `collection.SharedData.AddKey + enTable.AddEntry` 模式。
- **服务端端点客户端调了但没实现**:客户端 `CloudCodeManager` 有调用、服务端没对应 `[CloudCodeFunction]`(或反过来客户端缺 wrapper 方法 → 卡死整个 Unity 编译)。见 `cloud-code-deploy`。
- **buff/产出没接进消费端**:产出资源/buff 算出来了但没人读。先验证管线接没接(grep 消费方),没接就接上或明说欠债。
- **客户端/服务端配置不符**:同一个值两边硬编码且不一致(实战:服务端说 HQ 满级 10,客户端配置是 5)。按 Config Hub 铁规对齐到 Sheet 源头。

dump 真相的方法:写一次性探针 .cs 放 **Assets 外**(项目根 `Temp/` 或 scratchpad),用 `unity command script eval_file --file <path>` / `script run --file <path> --entry Type.Method` 跑(内存编译,无域重载),递归打印 serialized 字段值(NULL 与否)、hierarchy、tab 顺序,写到 `Temp/*.txt` 再 Read,用完删。不得不走 Coplay `execute_script` 时,临时驱动脚本放 `Assets/Editor/CoplayTemp/`,不进 git、用完删;要留作工具的代码一律放正式目录(`Assets/Scripts/Editor/Setup/` 等),见工程 CLAUDE.md 锁协议第 2 条。

---

## 第四步:实现纪律(贴合 repo,别堆屎山)

- **改真源,不改副本**。UI 先判轨(细则见 `ui-placement`「真源模型」):
  - **已 prefab 化的屏**:直接改 prefab(Prefab Mode / `LoadPrefabContents`),对应 builder 已退役(菜单带 `(retired)`),**禁止重跑**冲掉手工 refine。勾哥手摆过的几何不动,只接线。
  - **还没迁的旧屏**:改 `Assets/Scripts/Editor/Setup/*Setup.cs` builder + `Tools/Setup/... Rebuild` 菜单,不手摆场景;顺手 prefab 化。新面板一律 prefab,禁止新增场景内联 UI 子树。
  - builder 写法:`SaveAsPrefabAsset` 同路径覆盖保 GUID;`SerializedObject.FindProperty` 带 null 检查 wire 字段;sprite 加载失败 `LogWarning` 路径。
- **复用既有套路保持一致**:抄最近的同类实现的 helper(`ApplySprite`/`CreateUIChild`/`SetRef`/`PlaceText`),别每次发明。视效走 `ui-visual-rework` 的配方提取法。
- **生产级视效从第一版就上**(项目默认):材质底纹 + 动效,没素材就从别的 feature 借;局内美术不许用代码画占位。
- **最简方案**:不引入没被要求的抽象/配置项/扩展点。只动该动的文件。
- **新代码贴合周围风格与抽象层级**。Extraction 没有日志封装,直接 `Debug.Log`,别造一个。
- 写 Assets 下 .cs、进 Play、跑 builder、存场景/prefab 前按工程 CLAUDE.md 锁协议 v2 拿锁。

---

## 第五步:验证 → 收尾(不测不算完)

1. **编译干净**:`unity command console status`(编译失败标志)+ grep Editor 日志 `error CS` **交叉验证**(单一工具偶发说谎)。
2. **进 Play 端到端真测 + 迭代到满分**:这是头号铁律,驱动方法见 `playmode-verify-iterate`,测哪些 flow、过哪些门禁见 `qa-testing`——不是截一张图就完,是真点击走全链路、发现问题回来一轮轮修到玩家体验满分。
3. **收尾**:写一条 project 记忆(可复用的非显然事实:builder 入口、部署方式、踩的坑);推进了 ER 产品就 `progress.js bump`;玩家可见的推进按 `todo-to-planyway` 模式 B 直接上传 Planyway,不用问(工具/文档/纯重构不发)。
4. 非琐碎改动跑一次内置 `/code-review`(或"翼德 评审")让独立上下文挑正确性/耦合。

---

## 已验证的"会拖慢/翻车"的坑速查

| 坑 | 真相 |
|---|---|
| 自己顺序读大功能全部代码 | 慢且爆上下文;改用并行 Explore agent fan-out |
| 信 agent/工具的二手数值 | 关键值亲自 Read 原文核实(hex 解错过) |
| 假设旧功能"没做" | 多半"做了一半没接通";先 dump 真相找断点 |
| 改错层 | 已 prefab 化的屏改 prefab、禁重跑 builder;旧屏改 builder;两者都不在场景实例上手摆 |
| 只看一个编译通道 | `console status` + grep `error CS` 交叉验证 |
| 改完不进 Play 就交 | 头号红线;走 `playmode-verify-iterate` |

---

## 附录:卡住急救(原 unstuck-playbook,2026-10-30 并入)

意识到自己在打转(同一个动作试第 3 次、改一处冒一处、说不清现在在干嘛)——先停,别蛮干。

1. **STOP**:停止重复失败的动作。工具被 deny 的调用别原样重试(那是反馈,不是噪音);同一个改法失败两次就换思路,带着报错和已试过的上网查,有依据再动。
2. **NAME**:用一句话说清卡在哪一类(下表)。说不清 = 还没真正理解问题,回到侦察。
3. **对症**:

| 卡在… | 信号 | 破法 |
|---|---|---|
| **无从下手**(大/模糊任务) | 面太宽、不知从哪读起 | 侦察先行 + 并行 fan-out(第一步);先分块列清单(第二步);范围模糊先查真源和同类做法 |
| **做了没用**(改了不生效) | 改完现象没变、或变了别的 | 多半改错了层或改在补丁层。先定位根因、引用代码佐证;根修法已存在就传播并删旧补丁;UI 判轨见第四步 |
| **验证不了** | "应该好了吧"、只看了返回值/截图 | state dump 是权威,截图/返回值会骗人;验到副作用真正落地(数据真变了)。反面教材:CloudCode module 的 `_gameApiClient` 注入为 null,所有 CloudSave 端点其实不工作,却被 try-catch 掩盖、部署照样"成功" |
| **工具不配合** | ghost text、"成功"但没效果 | 异常即判失败 → 换通道交叉验证(编译看 `console status` + grep 日志;写操作回读确认落盘) |
| **迷失方向** | 忘了目标、清单过时 | 回任务清单对齐;一句话重述目标和完成判据;砍掉跑偏的支线 |

常见 bug 形态,带着找比瞎找快:① 写了一半没接通(第三步)② init-order(异步 spawn 后才有,别在 Start/Awake 缓存,lazy-resolve)③ 场景重载后死掉的一次性初始化服务。换/删资产前先查引用面:`node scripts/guid-find.js <asset路径|GUID> <项目根>`(翼德工具仓)。

**卡太久的出口**:先按成本 × 可逆性把剩下的路排一排,免费可逆的直接试;真需要勾哥拍板的不可逆分岔,一次弹窗问全(说清试了什么、哪里不通、推荐哪条),超 2 分钟没答按制作人判断代拍板继续、事后注明。只有勾哥能测的环(真机/外部服务/人机交互)前置说清。
