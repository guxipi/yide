# 工单 <批次>·<片号> <片名>(翼德 polish 施工工单模板——派 executor·opus 时整段作为 prompt,路径/口径按本次替换)

施工任务「<屏名> <批次> · <片名>」。项目 `<项目根>`(Unity <版本>,URP,竖屏手游)。中文汇报。当前 HEAD = <hash>,你在其上继续。

## 必读(先读再动手)
1. 方案:`<POLISH_DIR>\PLAN_<xx>.md` 的 §<n>(本次只做 <范围>;<其它片> 不做)。
2. 现状截图(Read):`<POLISH_DIR>\<上一棒目录>\<整屏>.png`、局部 `now_<id>.png`。参考图(Read):`<知识库>/images/<game>/<file>`(写明各张看什么)。
3. 代码(通读相关部分):<文件列表,标注只读/可改>。
4. Play 驱动:`<POLISH_DIR>\PLAY_ROUTE.md` + `scripts\`(**共享脚本不要改**,需要就复制到 `<片目录>\scripts\`);进页有约 <n>s 运镜,截终态要等它结束或点一下跳过。
5. `<项目根>\CLAUDE.md`;技能 `yide:playmode-verify-iterate`(+ `yide:ui-visual-rework` / `yide:vfx-production` 按片选);相关记忆(遇坑再读):<列出文件名与一句话>。

## 制作人原话与拍板(验收口径)
- 「<原话 1>」→ <拍板/解读>
- 「<原话 2>」→ …
- 你对「好不好看」负责:对照参考图反复调参,截图里真的好看为止,不是能跑就交。

## 实现要点
- <做法要点 1(精确到文件/方法/公式)>
- <要点 2>
- 数据真实:界面上的数字接真源,查不到就不显示并写欠账,不编。

## 硬性约束
- **不要动**:<别的棒刚改完/正要改的文件与系统>。
- **不许改**共享资产与烘焙工具:<列出>;`git diff <共享目录>` 必须为空;<回执/校验菜单> PASS。旧路径/2D 回退不许坏。
- shader 放 `<目录>`,材质走 Resources 防 strip;float 分支不用 shader_feature;关域重载:static 加 SubsystemRegistration 复位;运行时 Texture/Mesh/Material/RT 在 OnDestroy 销毁;日志按周围风格 `Debug.Log*("[<Tag>] …")`;只用确认存在的 API;新代码贴合周围风格,不加没被要求的抽象。
- UI 铁规:UI 真源=prefab(用 MCP 改后显式保存);字体二分;字面白+描边(UIInk),禁彩色字面;token 走 UITheme/TextStyle;新引 kit sprite 后重跑 KitSprite Rebuild Manifest;新 universal 件回填注册表;静态文案英文。
- 编辑器(Coplay MCP,root `<项目根>`)归你独占,当前不在 Play、无编译错误。**每次改文件前先 `get_unity_editor_state` 确认 playMode=false**(前几棒违反过);改完 `check_compile_errors` 再进 Play。被编辑态组件自动标 dirty 的场景**不要 save**;不碰 ProjectSettings。收尾 stop Play 并还原 Game 视图(`scripts\BrRestore.cs`)。
- 不许运行 scope.js;不许 git commit/push;不动无关文件。
- 一回合连续干到底;没有 watcher/计时器/触发器会叫你;停回合=停工作;除非真 blocked 于需要人拍板的不可逆决定,否则不许中途停。

## 验证(必须做,不许伪造)
1. 编译零错(shader 无报错);<Ink Sweep / UI Audit 等体检菜单>零命中。
2. 真流程进 <屏>,截图存 `<POLISH_DIR>\<片目录>\`:三档 1080×1920 / 1080×2340 / 1080×2640 的 <主视角>;1080×2340 下 <该片特有视角列表>;动效证明(同一视角相隔 ~0.5s 两张)。**每张 Read 亲眼看**,与基线/参考图对比,迭代到满意。
3. 真点击回归:<列出必须仍能用的交互>。
4. state-dump 原值:<尺寸/顶点/耗时/频率/数据来源/delta>。
5. 防回归:<校验菜单> PASS;共享资产 diff 为空;`git status --short` 列全部改动。

## 汇报格式(≤500 字)
改动清单(文件+一句话)/ 证据(截图绝对路径 + dump 原值)/ 画面自评(验收口径逐项:做到/没做到)/ 「偏离与欠账」逐条(与方案不同之处及原因、没验证到的;不伪造验证)。
