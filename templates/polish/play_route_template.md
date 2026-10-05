# <屏名> — Play 驱动手册(翼德 polish:批 1 开头派一棒执行者实跑并填好,后续每棒照抄)

> 目的:所有施工棒都能不摸路、直接走到目标屏截三档图。脚本**不进 Assets**(`execute_script` 用绝对路径直接编译运行,避免 Play 中触发域重载),放 `<POLISH_DIR>\scripts\`。

## 0. 文件
| 文件 | 作用 |
|---|---|
| `scripts\<Drive>.cs` | 主驱动:每个 public static 方法 = 一步(State / Res1920 / Res2340 / Res2640 / ClickXxx / Dump / ShotA / Close…),`execute_script` 的 `methodName` 调 |
| `scripts\<Preflight>.cs` | 编辑态自检:场景 dirty、playModeStartScene(必须是 Boot 类启动场景,否则服务全 null)、相关 PlayerPrefs |
| `scripts\<Restore>.cs` | 收尾:Game 视图还原为会话前尺寸 |
| `scripts\shotname.txt` | 下一张截图文件名(不带 .png) |

## 1. 真实玩家路径(读代码确认,不走反射直开面板)
<Boot → 主页 → 点哪个按钮 → … → 目标屏>;其它入口(deeplink/路由)只作兜底并注明。

## 2. 步骤(每步单独一次调用,execute_script 必须纯同步)
1. 进 Play 前:`get_unity_editor_state`(playMode=false, 无编译错)→ `check_compile_errors` → Preflight。
2. 设分辨率:Game 视图尺寸表加/选 `1080x1920 / 1080x2340 / 1080x2640`(用户级设置不进 git);返回值里的尺寸下一帧才生效。
3. `play_game` → 轮询 State 直到目标按钮 active+interactable 且射线顶层命中它(top 不是它=有东西挡着,先处理弹窗)。
4. 真点击:EventSystem.RaycastAll 命中检查 → pointerDown/Up/Click(命中不对就 FAIL,不强点)。
5. Dump 状态(面板路径/关键 Rect 像素矩形/RT 尺寸/当前数据)。
6. 截图:把文件名写进 shotname.txt → ShotA(项目的 ScreenCapture 单次组件,下一次 MCP 调用返回时 PNG 已落盘)→ Read 看一眼。
7. 换档重开:关面板 → 换分辨率 → 重新点进(保证每档是新开的布局与 RT)。
8. 退出:关面板 → `stop_game` → 确认 playMode=false → Restore → Preflight 看 dirty(**不要 save**)→ `git status --short` 与开工前对比。

## 3. state dump(实测值填这里)
<面板根路径 / Canvas 缩放 / 关键 Rect 三档像素矩形 / RT 尺寸 / 数据条目 / 渲染管线与 MSAA/renderScale>

## 4. 坑
- Coplay capture 看不到 screen-space UI → 用 ScreenCapture。
- Input System 真鼠标注入通常不通 → 用 EventSystem raycast 级点击(命中检查是真的)。
- 场景会被 [ExecuteAlways] 布局件自动标 dirty → 不 save。
- <本屏特有的坑>
