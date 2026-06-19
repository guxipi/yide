---
name: playmode-verify-iterate
description: Drive the Unity game in Play Mode via Coplay MCP, observe REAL behavior, fix, re-test, and iterate until the player experience is flawless. Trigger after ANY gameplay/UI/data/server change to verify it actually works for the player — "测一下" / "进 play 测" / "验证这个改动" / "确保好用" / "跑起来看看" / "自己测到满意" / "测到满分" — or as the verification step of any feature. Covers runInBackground-first, step-driven capture, real-click driving through the full chain, state-dump-beats-screenshot, the stop→fix→rebuild→save→replay loop, and the recurring Play Mode gotchas (Boot scene on stop, font tofu, button-rename breaks the driver, save_scene path trap, execute_script blocked by a WIP compile error → read asset YAML instead, no run_tests in Coplay MCP).
---

# Play Mode Verify & Iterate (Extraction · Coplay MCP)

CC 自己进 Play Mode 真测 → 发现问题 → 回来修 → 重测 → **一轮轮迭代到玩家体验满分**的闭环能力。这是头号铁律("改完先自己测到通过再交")的执行手册。蒸馏自一单实战:Base tab 改动跑了 6+ 轮 Play(按钮挤成方块→资源条被挡→raid 执行验证→loc 缺补 21 条→字体 tofu→驱动找不到按钮),每轮真测发现真问题、回来修、再测,直到全绿。

> 信条:**截图会骗人,state dump 是权威;不是截一张图就算测了,是真点击走完整链路;每发现一个问题就回来修一个,迭代到满分。**

---

## 第〇步:进 Play 前

- 确认编译干净:`check_compile_errors` + grep logs `error CS`(工具偶发说谎,交叉验证)。
- 若改了 editor builder:**先把 builder 的产物落进场景**(跑 builder → SaveScene),否则 Play 里看到的是旧场景。
- `play_game` 启动。游戏有 boot/sign-in,**等 ~20s** 再操作(用 `sleep 20 && echo ok` 这种带条件的等待,纯 `sleep N` 会被拦)。

> **想跑 NUnit 单测?**(原 L-0001)Coplay MCP **没有 run_tests**——`play_game` 只验运行时行为,**不等于跑测试套件**。真要跑单测只能:① Unity CLI `-runTests -batchmode`(解析 NUnit XML,**别看退出码**);② 勾哥在 Editor Test Runner 手动跑、我读结果/日志。`execute_script` 调 `TestRunnerApi` 异步 + 跨域重载,拿结果不稳,不当主路径。

---

## 第一步:驱动的四条铁律

1. **`Application.runInBackground = true` 是每个驱动脚本的第一行**。编辑器失焦后游戏冻结、`Time.time` 不走、截图拍到坏帧。每个 `execute_script` 入口先设它。

2. **分步驱动,每步独立调用**。动画/异步是时序的:`切到目标 tab` → `sleep 2-4s` → `关掉挡路弹窗` → `操作` → `sleep` → `截图`,拆成多次 `execute_script`,不要塞进一个脚本一口气跑完。服务端往返要 `sleep 3-4s`。

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

- 停 Play:`EditorApplication.isPlaying = false`(`stop_game` 偶尔说 "not playing"),等 ~8s 重编译 + domain reload。
- `SaveScene` **Play 模式下会抛 "cannot be used during play mode"**,必须先停。
- 改了 builder C#:停 Play → 等编译 → open 目标场景 → 跑 builder → SaveScene。
- 写操作回读验证落盘:`grep` 场景文件确认新对象进去了。

一轮只修能定位根因的问题,别盲改。修完那个问题,下一轮 Play 专门复验它 + 扫有没有引入新问题。**直到玩家从进入到完成整个 loop 都顺、好看、无报错。**

> **收尾铁律:测完(无论通过还是这一回合先告一段落)立刻停 Play,别把 Editor 晾在 Play 状态。** 退出本身要 ~8s 重编译 + domain reload,留着它挂着 = 勾哥那头一直卡在 Play 里、下次操作还得先等它退。判定「这一轮 MCP 自测做完」的最后一个动作**固定是停 Play**(`EditorApplication.isPlaying = false`,`stop_game` 偶尔说 "not playing" 就用前者),跟「MCP 改完必 SAVE」同级。只有「马上要进下一轮 fix→replay、停了又得重进」时才允许暂时留着——但回话给勾哥前必须已停。

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
| `save_scene("Name")` 存出 `Assets/Name.unity` 垃圾文件、真场景没动 | 它把 `scene_name` 当相对 Assets 路径;改用 `EditorSceneManager.SaveScene(scene)`(无 path,写回 `scene.path` 原路径),流程 `OpenScene(canonicalPath,Single)`→改→`MarkSceneDirty`→`SaveScene`;改完 `Grep` 真 YAML 核实落地,**别只信工具返回串**(原 L-0007)|

---

## 第五步:交付前终检清单(全过才喊"测好了")

- [ ] `check_compile_errors` 干净 **且** grep logs `error CS` 为空(交叉验证)
- [ ] builder 重跑日志零 `Sprite not found` / `Property '...' not found`
- [ ] 端到端真点击走通完整 loop(进入→操作→服务端→结果→刷新),用 state dump 确认副作用数值正确
- [ ] 关键 UI 区域全分辨率裁块 Read,对齐/配色/字体/无瑕疵
- [ ] 场景已 SaveScene 且回读确认落盘
- [ ] 多轮迭代后无残留问题、无新引入问题
- [ ] **Play Mode 已停**(`EditorApplication.isPlaying=false`),没把 Editor 晾在 Play 状态就回话

UI 专属的截图通道/几何数值核实细节见 `ui-placement`;视觉质量标准见 `ui-visual-rework`;服务端验证见 `cloud-code-deploy`。
