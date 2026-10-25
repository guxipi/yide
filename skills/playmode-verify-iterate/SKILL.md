---
name: playmode-verify-iterate
description: Drive the Unity game in Play Mode via Unity CLI (Coplay MCP as fallback), observe REAL behavior, fix, re-test, and iterate until the player experience is flawless — or the verification step of any gameplay/UI/data/server change. Trigger on "测一下" / "进 play 测" / "验证这个改动" / "确保好用" / "跑起来看看" / "自己测到满意" / "测到满分".
---

# Play Mode Verify & Iterate (Extraction · Unity CLI 主路)

CC 自己进 Play Mode 真测 → 发现问题 → 回来修 → 重测 → **一轮轮迭代到玩家体验满分**的闭环能力。这是头号铁律("改完先自己测到通过再交")的执行手册。蒸馏自一单实战:Base tab 改动跑了 6+ 轮 Play(按钮挤成方块→资源条被挡→raid 执行验证→loc 缺补 21 条→字体 tofu→驱动找不到按钮),每轮真测发现真问题、回来修、再测,直到全绿。

> 信条:**截图会骗人,state dump 是权威;不是截一张图就算测了,是真点击走完整链路;每发现一个问题就回来修一个,迭代到满分。**

---

## 第〇步:进 Play 前

> **通道(2026-10-23 定稿,替代 09-29 口径)**:**Unity 官方 CLI 是主路,Coplay MCP 只兜底**(Coplay 公司 2026-03 被收购并入 Aura,dev MCP 自 2026-02 停更)。Pipeline 包 **0.9.0-exp.1 起命令全部分组命名,旧扁平名直接报错**(`editor_play`→`editor.playmode start`、`eval`→`script eval`、`console`→`console get`…;全表 `unity command --obsolete-command-names`)。多编辑器并存时**每条命令都带 `--project-path <工程路径>`**;Pipeline 自有参数放 `--` 之后(`script eval` 的 `timeout` 是毫秒,会被 CLI 自己的 `--timeout` 秒吞掉);`--format json` 的输出末尾可能多一行 `<claude-code-hint …/>`,解析前 `grep -v claude-code-hint`。eval 走 Bash 不走 PowerShell,代码写成 `return <expr>;`,eval 里绝不同步等异步(会把编辑器锁死)。

**下面这些事 CLI 有明确优势,一律用 CLI,不许退回 Coplay**(验证口径 2026-10-23,Pipeline 0.9 / CLI 1.0.0-beta.14):

| 要做的事 | Unity CLI 写法 | 为什么必须用它(Coplay 做不到或做不好) |
|---|---|---|
| 找到并钉住编辑器 | `unity status --project-path <path>`;Play 后 `unity status --until-ready --project-path <path>` | 原生多编辑器钉选;`--until-ready` 代替手写轮询等域重载 |
| 进/出 Play | `unity command editor.playmode start` / `editor.playmode stop` / `editor.playmode pause` | Coplay `stop_game` 会说 "not playing",CLI 直接可靠 |
| 失焦不冻结 | 进 Play 前 `unity command editor set_auto_tick` + `unity command editor.playmode set_run_in_background`(退出后 `-- --enable false` 还原) | 项目级 Run In Background 覆盖且不进构建,比探针首行 `runInBackground=true` 干净 |
| 证明游戏真在跑 | `unity command job wait -- --condition '{"member":"UnityEngine.Time.frameCount","op":"changed"}' --timeout 10` | 服务端等帧数变化,截图冻帧骗不了它;同一命令可 `--on_met` 命中那一帧截图 |
| 截游戏画面(含 UI) | `unity command capture game_view -- --source screen --save_path Screenshots/x.png`(需内联加 `--include_inline_image true --max_resolution 512`) | **含 Screen Space-Overlay UI**,Coplay capture 看不见屏幕空间 UI;`capture scene_view` 拍 Scene 视图 |
| 读 Console | `unity command console get -- --tail 50 --level error`;只要编译红/计数用 `console status`;流式看 `unity logs --console --follow --project-path <path>` | 带 cursor/level 过滤,不用 tail Editor.log;`console status` 给编译失败标志 |
| 跑 C# | 一行 `unity command script eval 'return …;'`;多行走文件 `script eval_file --file <path>`;批量建对象用 `script run --file <Assets 外的 .cs> --entry Type.Method`(内存编译,无域重载,`--dry_run true` 只编不跑) | Roslyn 内存编译,不触发域重载;`script run` 就是 builder 模式 |
| 重编译 | `unity recompile`(失焦也能编;`--strict` 把 warning 当错) / `unity command recompile_status` 轮询 | 不用切窗口让编辑器拿焦点 |
| 跑 NUnit | 编辑器内 `unity command test run -- --mode playmode --filter <Fixture>`(长跑 `--async_tests true` + `test status`);无头 `unity test <project> --mode PlayMode --output r.xml`(退出码 8=有用例失败,其它非 0=没跑完) | Coplay 根本没有测试运行器 |
| 找对象/读写字段 | `gameobject find -- --name X --include_inactive true` → `component get_fields -- --target <handle> --component <Type>` / `component set_field` | 返回可复用 handle,不用每次反射 Find |
| 场景 | `scene open -- --path Assets/Scenes/Meta/HomeScreen.unity` / `scene save` / `scene list_open` / `scene get_hierarchy` | `scene save` 写回原路径,没有 Coplay `save_scene(scene_name)` 存错地方的坑 |
| 输入模拟 | `unity command simulate_pointer -- --x --y --action` / `simulate_key`(runtime 组) | 真 Input System 事件 |
| 等条件 | `job wait`(短同步)/ `job wait -- --async true` + `job wait_status`;CLI 侧长命令 `unity command --detach …` + `unity job wait <id>` | 服务端等待不占 MCP 往返 |

Coplay 工具只在 CLI 没对应命令时用,且要先 `unity command --query <关键词>` 确认真没有。Coplay 独有且还在用的:`capture_scene_object` / `capture_ui_canvas`(可用 `script eval_file` 自己写 `RenderTexture` 截法替代)、`get_worst_cpu_frames` / `get_worst_gc_frames`、`generate_*` 生成类(项目不靠它,走 Tripo 网页 / sol / astra)。

**进 Play 前后固定序列**(Play 前先读 `unity command editor status`,`playMode` 已是 playing/paused = 这局是勾哥的,只读不动、不 stop):
```bash
P="--project-path C:/DuckGames/Extraction"
unity status $P --format json | grep -v claude-code-hint
unity command $P editor status
unity command $P editor set_auto_tick
unity command $P editor.playmode set_run_in_background
unity command $P editor.playmode start
unity status $P --until-ready --format json | grep -v claude-code-hint
unity command $P job wait -- --condition '{"member":"UnityEngine.Time.frameCount","op":"changed"}' --timeout 10
# …驱动(script eval_file / script run)、capture game_view、console get…
unity command $P editor.playmode stop
unity command $P editor.playmode set_run_in_background -- --enable false
```

- 确认编译干净:`unity command console status`(compile-failure 标志)+ `unity recompile`,再 grep logs `error CS` 交叉验证(单一工具偶发说谎)。
- 若改了 editor builder:**先把 builder 的产物落进场景**(跑 builder → SaveScene),否则 Play 里看到的是旧场景。
- `unity command editor.playmode start` 启动,随后 `unity status --until-ready`。游戏有 boot/sign-in,**等 ~20s** 再操作(用 `sleep 20 && echo ok` 这种带条件的等待,纯 `sleep N` 会被拦)。

> **想跑 NUnit 单测?** 走 CLI:编辑器内 `unity command test run -- --mode playmode --filter <Fixture.Test>`(`test list` 先看有哪些;长跑 `--async_tests true` 再 `test status` 轮询);无头跑 `unity test <project> --mode PlayMode --output results.xml`(退出码 **8=有用例失败**,其它非 0=没跑完可重试;别只看 0/非 0)。`editor.playmode start` 只验运行时行为,**不等于跑测试套件**。Coplay `execute_script` 调 `TestRunnerApi` 那条路作废。

---

## 第一步:驱动的四条铁律

1. **失焦不冻结**:进 Play 前 `unity command editor set_auto_tick` + `editor.playmode set_run_in_background`(见上面固定序列);仍走 Coplay `execute_script` 的旧驱动脚本保留首行 `Application.runInBackground = true`。编辑器失焦后游戏冻结、`Time.time` 不走、截图拍到坏帧——用 `job wait` 等 `Time.frameCount` 变化证明真在跑。

2. **分步驱动,每步独立调用**。动画/异步是时序的:`切到目标 tab` → `sleep 2-4s` → `关掉挡路弹窗` → `操作` → `sleep` → `截图`,拆成多次 `script eval_file`(或 Coplay `execute_script`),不要塞进一个脚本一口气跑完。服务端往返要 `sleep 3-4s`,或直接 `job wait` 等目标字段。

3. **驱动走真实链路,不静态摆拍**。用 `button.onClick.Invoke()` 触发真实点击 → 服务端 → 回调 → 刷新,验证整条链路。涉及一次性状态(签到/首次)用 Debug 重置后重启 Play 验自动路径。

4. **导航/弹窗用项目 API**:切 tab 用 `UITabNavigationManager.SwitchToTab(i)`;关弹窗用 `UIPopupsManager.HideAll()`;关自定义面板走面板自己的 `ReturnToIdle()`/`Hide()`,别 `SetActive(false)` 硬关 UIPanel(状态卡死)。

---

## 第二步:state dump 是权威,截图只看视觉

**截图会骗人**:编辑器失焦那一帧 UI canvas 可能整层不渲染 → 拍出"只有 3D 没有 UI"的坏帧,真玩家看不到。**功能对不对,靠 dump 真值,不靠截图。**

写临时 editor 脚本(`Temp/yide_*.cs`)dump 关键状态到 logs:
```csharp
Debug.Log($"YIDE: mode={panel.CurrentMode} alpha={cg.alpha:F2} " +
          $"resultActive={resultGroup.activeSelf} text=\"{tmp.text}\" " +
          $"gold={data.Resources.StoredGold}");
```
实战靠这个确认 raid 闭环:`mode=Raiding, alpha=1.00, ResultText="Stolen: 256 Gold, 80 Metal", gold 1000→1256`——精确入账,功能铁证。截图同时飘到了别的 tab(焦点漂移),但 dump 不骗人。

**截图只用来判视觉质量**:对齐、配色、字体、瑕疵。全分辨率截图缩略图会骗人(暗色误判、细节糊),关键区域 PowerShell 裁原尺寸 Read 检查。两帧间隔 1-2s 对比证明动画在动。

---

## 第三步:迭代闭环(每发现一个问题转一圈)

```
进 Play → 真测 → 发现问题 → 停 Play → 修 → 重编译 → (改了builder就)重跑builder → SaveScene → 再进 Play → 再测
```
**关键:停 Play 会切回 Boot 场景**(首场景)。重跑 builder/存场景前**必须先 `open_scene` 回目标场景**(如 HomeScreen),否则 builder 报 "X not found"、SaveScene 存错场景。

- 停 Play:`unity command editor.playmode stop`(Coplay `stop_game` 偶尔说 "not playing";兜底 eval `EditorApplication.isPlaying = false`),然后 `unity status --until-ready` 等域重载。
- `SaveScene` **Play 模式下会抛 "cannot be used during play mode"**,必须先停。
- 改了 builder C#:停 Play → `unity recompile` 等编译 → `unity command scene open -- --path <场景>` → 跑 builder(`script run` / `editor invoke_menu`)→ `scene save`。
- 写操作回读验证落盘:`grep` 场景文件确认新对象进去了。

一轮只修能定位根因的问题,别盲改。修完那个问题,下一轮 Play 专门复验它 + 扫有没有引入新问题。**直到玩家从进入到完成整个 loop 都顺、好看、无报错。**

> **收尾铁律:测完(无论通过还是这一回合先告一段落)立刻停 Play,别把 Editor 晾在 Play 状态。** 退出本身要 ~8s 重编译 + domain reload,留着它挂着 = 勾哥那头一直卡在 Play 里、下次操作还得先等它退。判定「这一轮自测做完」的最后一个动作**固定是停 Play**(`unity command editor.playmode stop`;Coplay `stop_game` 偶尔说 "not playing",兜底 eval `EditorApplication.isPlaying = false`),跟「MCP 改完必 SAVE」同级。只有「马上要进下一轮 fix→replay、停了又得重进」时才允许暂时留着——但回话给勾哥前必须已停。

---

## 第四步:实战反复踩的具体坑(直接照查)

| 现象 | 根因 / 修法 |
|---|---|
| 截图只有 3D 场景没 UI | 失焦坏帧伪影;`runInBackground=true` + 用 state dump 核实功能,别误判成 bug |
| 按钮全挤成 100×100 方块 | LayoutGroup 没开 `childControlWidth/Height` → force-expand 和 LayoutElement preferred 都不生效 |
| 元素被状态栏/刘海挡 | 顶部元素 y 往下让(资源条等),用 `Core.UI.SafeArea` |
| 文字出现 ☐ 豆腐块 | CookieRun 字体无该字形(如 em-dash `—`);换普通字符(`-`) |
| 界面显示原始 loc key 字符串 | StringTable 缺 key;builder 里 `SharedData.AddKey + enTable.AddEntry` 补,重跑 builder |
| 驱动脚本点不到按钮 | 重命名过的按钮(如 RaidButton→RaidExecuteButton);驱动按真实节点名找;`execute_script` 每次现编译会拾取改名 |
| 停 Play 后 builder 报 not found | 切回了 Boot 场景;先 `open_scene HomeScreen` |
| 面板按预设条件不弹 | 可能是设计门槛(如 Core 面板要先有 CoreVault);先确认是不是 by-design 再当 bug |
| 切 tab/MoveTo NRE | 场景对象在 Awake 前被外部调;lazy-resolve 缓存字段(别在 Awake 才初始化) |
| 上回合 spawn 的预览物/对象突然 `Find` 不到 | 编辑器是勾哥活地盘,active scene 被他中途切走(实测 UIDesign_Gameplay→GameScene→Boot);跨回合先 `list_game_objects_in_hierarchy`/确认 active scene,找不到就重 spawn;临时物 `__` 前缀、尽量"实例化→操作→销毁"一次脚本内闭环(原 L-0009)|
| `execute_script` 突然报编译错 | 多半是勾哥 IDE 里 WIP 代码编译不过——**先看报错文件,来自他的活就不碰、只汇报**;验证降级为直接读资产 YAML(.anim 曲线 / .controller 的 `m_Motion` / .meta `externalObjects`),资产层证据同样硬(原 L-0009)|
| Coplay 通道全超时:`get_unity_editor_state` 秒回,但 `execute_script`/`stop_game`/`get_unity_logs` 全 60s 超时,Unity 窗口仍 responding、CPU 三核满转 | **不是编译死锁,是每帧日志风暴**(实例:玩家旁金币 + PlayerData service 缺失,CoinPickup 每帧刷警告+提栈)。鉴别:绕开 MCP 直接 tail `%LOCALAPPDATA%\Unity\Editor\Editor.log`。**卡住时 `stop_game` 只发一次然后等**——超时期间发的会排队迟到生效,连发几发会莫名掐断后续几次 Play。预防:playtest 驱动 warp 后顺手 Destroy 玩家周围 `PickupBase`(2026-08-23)|
| `save_scene("Name")` 存出 `Assets/Name.unity` 垃圾文件、真场景没动 | 它把 `scene_name` 当相对 Assets 路径;改用 `EditorSceneManager.SaveScene(scene)`(无 path,写回 `scene.path` 原路径),流程 `OpenScene(canonicalPath,Single)`→改→`MarkSceneDirty`→`SaveScene`;改完 `Grep` 真 YAML 核实落地,**别只信工具返回串**(原 L-0007)|

---

## 第五步:交付前终检清单(全过才喊"测好了")

- [ ] `unity command console status` 无编译失败 **且** grep logs `error CS` 为空(交叉验证)
- [ ] builder 重跑日志零 `Sprite not found` / `Property '...' not found`
- [ ] 端到端真点击走通完整 loop(进入→操作→服务端→结果→刷新),用 state dump 确认副作用数值正确
- [ ] 关键 UI 区域全分辨率裁块 Read,对齐/配色/字体/无瑕疵
- [ ] 场景已 SaveScene 且回读确认落盘
- [ ] 多轮迭代后无残留问题、无新引入问题
- [ ] **Play Mode 已停**(`unity command editor.playmode stop`),`set_run_in_background -- --enable false` 已还原,没把 Editor 晾在 Play 状态就回话

UI 专属的截图通道/几何数值核实细节见 `ui-placement`;视觉质量标准见 `ui-visual-rework`;服务端验证见 `cloud-code-deploy`。
