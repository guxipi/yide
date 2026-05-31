# Unity 手游 Best Practice(翼德把关清单)

> 场景带:写 C#/Unity 代码时参考。翼德的 PostToolUse 把关器会按这些点自动 lint 你改过的 .cs,
> 把隐患作为**建议**浮出来(不强制、不擅自大改)。以下也是翼德向你解释把关结果时的依据。

## 🔌 若已接 Unity MCP:优先在引擎里验证(别只凭文本猜)
检测到 Unity MCP 工具可用时,**把关与 QA 一律以引擎事实为准**,文本 lint 只是没 MCP 时的退路:
- 改完脚本 → `read_console`(看真实编译错/警告,胜过正则猜)→ 有错先修再说;
- 验证 → `run_tests`(EditMode/PlayMode)读真实通过/失败,别口头说"应该没问题";
- 手游性能/资源 → 用 `manage_texture`/`manage_profiler`/`manage_build` 看真实导入设置/内存/包体,而不是凭经验断言;
- 场景体检 → 查丢失引用(`MissingReferenceException` 文本审查抓不到)。
- **诚实**:没接 MCP 时,明说"这是静态启发式建议、没在引擎里验证过",不要假装跑过。

## 0. 让位项目约定 + 专家友好(把关原则)
- **项目约定 > 通用建议**:本仓库的 `CLAUDE.md`/`AGENTS.md`/`.editorconfig`/`.cursor/rules`、以及已探测的 Unity 事实(管线/版本/Input/Addressables)**优先**;通用 best practice 与它们冲突时**让位、闭嘴**(那是有意的取舍,不是错)。
- **资深友好(默认 expert 档)**:只在**非显而易见**的地方开口(async/Task 生命周期、特定版本弃用 API 等);"缓存 GetComponent""用对象池"这类资深本就会的,默认不报。档位在 `~/.yide/.meta/gatekeeper.json`(novice/balanced/expert)。
- **行内豁免**:某行结尾写 `// yide-ok: 原因`,翼德就不再对该行报任何把关项(像 eslint-disable)。要永久静音某规则,在 gatekeeper.json 的 `suppressed` 加一条。
- **只看本次改动的行**,不翻旧账。

## 1. 性能热路径(Update / FixedUpdate / LateUpdate 内)
帧预算很紧(60fps≈16.6ms,30fps≈33ms),热路径里任何浪费都会掉帧。
- **缓存引用**:`GetComponent` / `Find*` / `Camera.main` 不要每帧调,放 `Awake`/`Start` 缓存。`Camera.main` 内部是全场景 tag 搜索。
- **避免 GC 分配**:热路径里别 `new`、别用 LINQ(`Where/Select/...` 会分配+装箱)、别字符串拼接(用 `StringBuilder` 或缓存)。
- **对象池**:频繁 `Instantiate/Destroy`(子弹/敌人/特效)→ 用 `UnityEngine.Pool.ObjectPool<T>`(2021+ 内置)。
- **物理写 `FixedUpdate`,输入采样 `Update`**。

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
- `Awake` 自初始化、`Start` 解析跨对象引用;别在编辑器代码里调运行时场景 API。

## 4. 资源 / git 卫生
- 慎用 `Resources.Load`:`/Resources` 会被强制全量打包且同步加载 → 改 Addressables(`Addressables.LoadAssetAsync`,记得释放 handle)。
- 移动/重命名/删除资源**必须连同 `.meta`** 一起(GUID 在里面),别手改 GUID。
- 场景/prefab 是 YAML,用 Unity 的 `UnityYAMLMerge`(`.gitattributes` 配 `*.unity merge=unityyamlmerge`),别手动文本合并;`Asset Serialization = Force Text`。
- 移动端资源:贴图用 ASTC 压缩、关掉不需要的 Read/Write Enabled、限 Max Size(能显著降包体与内存)。

## 5. 工程结构
- 尊重已有 `.asmdef` 边界;编辑器代码放 `Editor/` 文件夹/asmdef;运行时程序集**绝不引用 `UnityEditor`**(会构建失败)。
