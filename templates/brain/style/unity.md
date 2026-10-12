# Unity 手游 Best Practice(翼德把关清单)

> 场景带:写 C#/Unity 代码时参考。翼德的 PostToolUse 把关器会按这些点自动 lint 你改过的 .cs,
> 把隐患作为**建议**浮出来(不强制、不擅自大改)。以下也是翼德向你解释把关结果时的依据。

## 🔌 先在引擎里验证,别只凭文本猜
操作 Editor 首选 **Unity CLI**(`unity status` / `unity cmd editor_status|console|editor_play|editor_stop|capture_game_view|eval|find_gameobjects`;eval 走 Bash 不走 PowerShell,eval 里绝不同步等异步),Coplay MCP(`check_compile_errors` / `get_unity_logs` / `play_game` / `execute_script` / `get_worst_cpu_frames` / `get_worst_gc_frames`)只在 CLI 没对应命令时用。两者都**没有测试运行器**:跑 NUnit 只能 Unity CLI `-runTests -batchmode`(解析 XML,别看退出码)或勾哥在 Test Runner 手动跑。贴图导入设置 / 包体没现成工具,走 eval 读 `TextureImporter`。没接引擎时明说"这是静态建议、没在引擎里验证过"。

## 0. 让位项目约定 + 专家友好(把关原则)
- **项目约定 > 通用建议**:本仓库的 `CLAUDE.md`/`AGENTS.md`/`.editorconfig`/`.cursor/rules`、以及已探测的 Unity 事实(管线/版本/Input/Addressables)**优先**;通用 best practice 与它们冲突时**让位、闭嘴**(那是有意的取舍,不是错)。
- **资深友好(默认 expert 档)**:只在**非显而易见**的地方开口(async/Task 生命周期、特定版本弃用 API 等);"缓存 GetComponent""用对象池"这类资深本就会的,默认不报。档位在 `~/.yide/.meta/gatekeeper.json`(novice/balanced/expert)。
- **行内豁免**:某行结尾写 `// yide-ok: 原因`,翼德就不再对该行报任何把关项(像 eslint-disable)。要永久静音某规则,在 gatekeeper.json 的 `suppressed` 加一条。
- **只看本次改动的行**,不翻旧账。

## 1. 性能热路径(Update / FixedUpdate / LateUpdate 内)
帧预算很紧(60fps≈16.6ms,30fps≈33ms),热路径里任何浪费都会掉帧。
- **缓存引用**:`GetComponent` / `Find*` / `Camera.main` 不要每帧调,放 `Awake`/`Start` 缓存。`Camera.main` 内部是全场景 tag 搜索。
- **避免 GC 分配**:热路径里别 `new`、别用 LINQ(`Where/Select/...` 会分配+装箱)、别字符串拼接(用 `StringBuilder` 或缓存)。
- **对象池**:频繁 `Instantiate/Destroy`(子弹/敌人/特效)→ 用 `UnityEngine.Pool.ObjectPool<T>`(2021+ 内置)。需要动态对象时**走传入的池接口**取,别在热路径 `new`。
- **物理写 `FixedUpdate`,输入采样 `Update`**。
- **连续内存优先**:热路径遍历用 `Array` / `struct` 的 `List<T>`,提高 CPU cache 命中;别在每帧遍历里用会装箱的接口集合。

## 1b. 海量数据(背包/排行榜)与序列化/IO
帧预算之外的另一类卡顿源:大集合全量拷贝、字符串/正则、阻塞式 IO。
- **海量集合(背包数千件/全服排行)别全量拷贝**:就地操作(in-place)或返回**只读视图**(`ReadOnlySpan<T>`/`IEnumerable<T>`),别每次 `ToList()`/`new[]` 复制一份。
- **排序比较器 `Comparer` 内零分配**:别在比较函数里 `new`、拼字符串、`ToString()`;预算好排序键再排。排序选**稳定且高效**的算法。
- **此处别用昂贵字符串拼接/正则**:大循环里的 `+` 拼接、`Regex` 是 GC + CPU 重灾区。
- **大列表给分页/延迟加载接口**(Pagination / Lazy Loading),别一次性灌全量。
- **序列化下发给客户端:极致压缩 + 只发该发的**——剔除客户端不需要的服务端内部状态/隐秘属性(防作弊也防带宽);布尔与极小枚举用**位域/位掩码(Bitfield/Bitmask)**打包合并。
- **数据库/存档批处理**:多条写用 **Batching / Bulk** 一次提交,**绝不在 `for` 循环里一条条执行 SQL / 单条 CloudSave 写**。

## 2. 过时 / 幻觉 API(按项目 Unity 版本)
AI 常因训练数据混版本而给出过时接口:
- `WWW` → `UnityWebRequest`(2018.3+ 弃用)。
- `UnityWebRequest.isNetworkError/isHttpError` → `result == UnityWebRequest.Result.ConnectionError` 等。
- `FindObjectOfType` → `FindFirstObjectByType`/`FindAnyObjectByType`(2023+/6)。
- Input:旧 `Input.GetKey/GetAxis` 与新 Input System 别混用,按项目选定的那套来。
- 版本差异集中到一个 compat 适配层,别到处撒 `#if UNITY_x_y`。

## 3. 序列化 / 生命周期
- Inspector 暴露字段用 `[SerializeField] private`,别为了露字段就改 `public`(破坏封装)。
- Unity 不序列化 `Dictionary`、多维/交错数组、嵌套容器;自定义数据类记得 `[Serializable]`;自动属性用 `[field: SerializeField]`。
- MonoBehaviour 里 `async void`/`Task` 不随 GameObject 销毁而停 → 绑 `OnDestroy` 的 `CancellationToken`(或用 `Awaitable`/UniTask)。`async void` 只用于事件处理。
- **关 domain reload 的项目**(Enter Play Mode Options 常见配置):SDK 包内 static 单次回调(IAP/analytics/native 桥)第二次 Play **永不再发** → boot/init 里凡 await 这类回调,必须自建 static 缓存跨 Play 补发**或**加超时上限,**绝不裸 await**(表象="间歇性挂死+重编译自愈";详见 `notes/2026/2026-07-10-unity-domain-reload-traps.md`)。
- `Awake` 自初始化、`Start` 解析跨对象引用;别在编辑器代码里调运行时场景 API。

## 4. 资源 / git 卫生
- 慎用 `Resources.Load`:`/Resources` 会被强制全量打包且同步加载 → 改 Addressables(`Addressables.LoadAssetAsync`,记得释放 handle)。
- 移动/重命名/删除资源**必须连同 `.meta`** 一起(GUID 在里面),别手改 GUID。
- 场景/prefab 是 YAML,用 Unity 的 `UnityYAMLMerge`(`.gitattributes` 配 `*.unity merge=unityyamlmerge`),别手动文本合并;`Asset Serialization = Force Text`。
- 移动端资源:贴图用 ASTC 压缩、关掉不需要的 Read/Write Enabled、限 Max Size(能显著降包体与内存)。

## 5. 工程结构
- 尊重已有 `.asmdef` 边界;编辑器代码放 `Editor/` 文件夹/asmdef;运行时程序集**绝不引用 `UnityEditor`**(会构建失败)。

## 7. 测试:EditMode vs PlayMode 分工(勾哥偏好 PlayMode,有道理)
- **EditMode**(不进游戏、快):只配**纯逻辑**——掉率/伤害公式/计时/状态机这类不依赖运行时的代码。
- **PlayMode**(真把游戏跑起来):**玩法/集成的唯一真值**——移动、物理、协程、动画、随时间发生的行为(Boss 走位/放技能/死亡/空投),`Update`/协程只在这里真的跑。
- **以 PlayMode 为准**:玩法相关别用 EditMode"假装测过";EditMode 测试还逼你解耦代码,屎山项目里常常得不偿失。慢就**批量跑**(一次进 Play 多验几条),别靠"少测玩法"省时间。

## 6. DOTween + Unity UI(UGUI)常见坑(本项目主力栈,作为"建议知识"参考,不做正则 lint)
**DOTween:**
- **对象销毁前先 Kill tween**:tween 还在跑、对象已 `Destroy` → 回调访问已销毁对象 → 崩/`MissingReferenceException`。`OnDestroy` 里 `transform.DOKill()`,或建 tween 时 `.SetLink(gameObject)` 绑生命周期(这是"一个动画修坏别处"的高发区)。
- **无限循环 / 复用的 tween 必须手动管**:`SetLoops(-1)` 或关掉 `SetAutoKill(false)` 的 tween,不 Kill 会泄漏、堆积。
- **别每帧 `new` tween**(`DOMove` 等):热路径里会 GC + 堆积;复用或用回调。
- **暂停**:`Time.timeScale=0` 时若要 UI 动画仍动,`SetUpdate(true)`(独立于 timeScale)。
**Unity UI(UGUI):**
- **拆 Canvas 降重建**:同一 Canvas 上任一元素变化会触发整块 rebuild。把**频繁变的(分数/血条/计时)和静态的分到不同 Canvas**,缩小重建范围。
- **关掉用不到的 Raycast Target**:不接收点击的 Text/Image 取消勾选,省 raycast 开销(满屏 UI 时明显)。
- **慎用嵌套 Layout Group + ContentSizeFitter**:层层嵌套会多次 rebuild,列表多了就卡;长列表用对象池/虚拟列表。
- **频繁显隐别狂 `SetActive`**:用对象池或 `CanvasGroup.alpha`/移出屏幕替代。

## 8. 直白命名(可定位 > 简短)
> 详规则见 `style/coding.md`「直白命名铁律」;这里是把关器对**新写**的成员/变量的 lint 点(贴合周围已有命名风格**优先**,别为直白破坏一致性)。
- 新函数/变量含**机械缩写**(`Pwr`/`Def`/`Mgr`/`Calc`/`Cfg`/`Tmp`/`reqId`…且非 `HP`/`UI`/`HQ`/`Id` 这类领域共识)→ 建议展开成完整词。
- 跨系统概念的裸名(`power`/`result`/`data`/`DoTrade`)→ 建议补**系统前缀 + 完整动宾**(`CalculateAsyncPvPDefendPower`),让人一眼知道归属与动作。
- 循环计数器/lambda 短参豁免。

## 9. scene/prefab 合并冲突处置(Git 管 Unity 的头号日常痛)
- **先上 SmartMerge**:配好 UnityYAMLMerge 后(见 `integrations/unity-smartmerge/SETUP.md`),撞 `.unity`/`.prefab` 冲突先 `git mergetool` —— 它按 YAML 语义自动合大部分,只把真冲突留给你。
- **剩余冲突按 YAML 块裁决,别按文本行**:Unity YAML 每个对象是一个 `--- !u!<classID> &<fileID>` 块。看冲突落在哪个 fileID / 组件块,按"这个对象两边各改了什么"整块取舍,而不是逐行拼。
- **绝不手瞎删 `--- !u!` 块**:删一个块 = 删一个 GameObject/Component,还会留下别处对它 `{fileID: ...}` 的悬空引用(打开就丢组件/报错)。宁可保留两份再在 Editor 里删多的。
- **`.meta` 冲突**:冲突多在 `guid`(两边各自 import 生成)——**保留任一方的 guid 即可,但全项目要一致**;别两个资产撞同一 guid。`.meta` 内其它字段(importer 设置)按需取。
- **合完必开 Editor 验**:Unity 里打开该场景/prefab,确认无 "missing script"/丢引用/重复对象,再提交;文本合过 ≠ 语义正确。
- **预防 > 治疗**:大场景拆子场景 / 用 prefab 变体 / 约定"同一 prefab 一次只一人改",从源头少撞。
