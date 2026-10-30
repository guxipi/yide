> 2026-10-30 由项目 skill `ui-design-match` 并入 `ui-visual-rework`。有预摆的无代码设计参考(`UIDesign_Gameplay.unity` 里的 `PopupDim_*` / `Popup_*`)或 mockup 截图、要求 runtime 和它一致时,走这份流程。机制和截图通道见 `ui-placement`,Play 驱动见 `playmode-verify-iterate`。

# UI Design-Reference Parity(照设计参考对齐 runtime UI)

> 信条:**参考是可测量的数据,不是"看着像"。目测像素永远对不齐;1279.63 这种数字只能从场景里读出来。最贵的时间花在"测量"和"追异常"上,中间的实现环节就几乎不用返工。**

适用场景:勾哥在 `Assets/UI_Design/UIDesign_Gameplay.unity` 预摆了无代码视觉参考(如 `PopupDim_Base_HQ` / `Popup_Base_HQ_Info`),或给了 mockup 截图(`D:\screenshots\` 最新),要求 runtime UI 与之一致。

---

## 第〇步 · Mockup spec sidecar + 实施解读门(2026-07-07 拍板,以 mockup 为参考时的前置)

> 总纲:`Claude Feature Docs/UI Architecture Refactor/HANDOVER_UI真源prefab化_总纲.md` §3;契约:`Claude Feature Docs/UI Visual Design/Visual_Refine_Contract.md` §9。

- **无 sidecar 的 mockup 不得作实施依据**。每张 mockup 必须有**同名 spec sidecar**(机器可读边车,`.md`),逐区域记:区域 → 功能 / 交互路由 / 状态清单 / 复用件 / 套哪条范式(`Pattern_Catalog/`)。存量 mockup 缺 sidecar 先补(agent 初稿 + 勾哥勾错),新 mockup 生成时由 HTML 埋的 `data-*` 自动产出(见 `mockup` action)。
- **实施解读门**:开工前先交「**实施解读**」(区域清单 / 范式引用 / 复用件 / 交互路由表 / 疑问),**勾哥批准后才动手**;套不上范式的区域 = 先扩范式库问勾哥,禁 freestyle。
- **parity 流水线消费 sidecar**:第一步的数值化对比、第五步的同框比对都以 sidecar 为对齐清单(区域逐条核销),不是只对着 PNG 目测。
- **交互契约纳入验收**:每个可点元素的**目标 / 反馈 / 失败态 / 返回路径**都要落实并在第五步真流程 Play 中逐个验到(含关闭/返回按钮 + Android 返回键路径)。

---

## 第一步 · 真源采集 —— 一行码都不写,先把所有未知消掉

1. **Mockup 截图**:读图,把每个视觉元素翻译成"规格语言"(行=图标框+`当前/需求`文本+右侧对号/按钮;按钮内=时钟图标+时长…)。
2. **通用件登记表**:先查 repo `Claude Feature Docs/UI Visual Design/Universal_Widgets_Registry.md`(2026-07-07 起唯一权威,已自 Claude memory 迁入 repo)——要动的件是否已有 universal 版(改造 vs 新建),避免重复造。
3. **设计场景数值化(核心动作)**:写一次性 dump 脚本(放 Assets 外,`unity command script eval_file` / `script run` 跑;Coplay `execute_script` 只兜底)把参考对象的完整 spec 导出成文本再 `Read`:
   - 每节点:name/activeSelf、`anchorMin/Max`、`pivot`、`anchoredPosition`、`sizeDelta`、(stretch 时)`offsetMin/Max`;
   - Image:sprite 名 + `AssetDatabase.GetAssetPath`(拿到 kit 资产精确路径)+ `ColorUtility.ToHtmlStringRGBA` 色值 + type(Sliced/Simple);
   - TMP:text/font 名/fontSize/autoSize 区间/color/alignment/fontStyle/outline;
   - LayoutGroup padding+spacing+ctrl/expand 四开关、ContentSizeFitter、LayoutElement。
   - 勾哥经常正开着设计场景(他刚给你看参考)——`unity command scene list_open` 确认后直接从 active scene dump,不用切场景。
4. **现状同样数值化**:用同一 dump 逻辑导 runtime prefab(`PrefabUtility.LoadPrefabContents`)——参考和现状必须是**同一种语言**才能对比。
5. **数据源踩点**:参考里显示的数据(时长/成本/每级效果)在 config/registry 里对应什么 API——显示永远接真数据,不造数。

## 第二步 · 数值诊断 —— 把每条抱怨翻译成测得出的差异

动手前,逐条把用户反馈定位到具体数字/结构:
- "padding 不一样" → 现状 section 宽 831 vs 参考 1279.63(1440 画布左右各 80);
- "元素样式不对" → 结构差异:现状把 widget 做成小 chip 塞进一条行,参考是每条需求=一整行(行底+图标框+文本+右侧动作);
- "按钮里要 timer" → 现状是旧成本样式(马蹄铁+数字)。

**说不出"为什么错、错多少"就不许动手。** 不带诊断的修复都是碰运气。

## 第三步 · 施工 —— 贴着项目已有纹理

- **先判轨**(见 `ui-placement`「真源模型」):已 prefab 化的屏直接改 prefab,禁重跑退役 builder;还没迁的旧屏走幂等 builder decorate-in-place(保 wiring)。都不在场景实例上手摆;prefab-only 改动优先(不动 scene = 不撞勾哥未提交的场景改动)。勾哥手摆过的几何不动,只接线。
- **state 驱动同一 prefab**:多建筑/多状态的差异做成内容切换(标题文本、内容区 SetActive、LayoutElement.preferredHeight 由代码按 state 设),不做 variant。
- **通用件**:新造的 timer/列表行等按 universal 标准放 `Core.UI.Widgets` + prefab 进 `Prefabs/UI/Core/`,做完**必回填 repo `Claude Feature Docs/UI Visual Design/Universal_Widgets_Registry.md`**(唯一权威)。
- **展示文案单一解析点**:每级效果/成本这类"从数据到文案"写成静态 helper(如 `BuildingLevelEffects`),UI 只调它;发现公式在别的面板里是私有的 → 提升为共享真源、两处共用(anti-hackfix 顺手迁同类)。

## 第四步 · 老 prefab 四大陷阱(本 skill 含金量最高的一节,逐条踩过)

| 症状 | 根因 → 修法 |
|---|---|
| screen rect 比 rect.size 均匀小 ~3%,localScale/lossyScale 全是 1 | **`localPosition.z≠0`(遗留 z=90)+ 透视 UI 相机** 把子树"推远显小"。追查阶梯:localScale → lossyScale → `rect.size`(对!)→ 只剩投影环节 → 打印 z。修:builder 里 z 清零(**只改 z 分量**,保 xy 不碰 anchoredPosition) |
| 整块 UI 比 spec 小一圈(如 0.729 倍) | 老 prefab 子树带遗留 **localScale**(WYSIWYG 手调残留)。builder 重新授权几何时统一 `localScale=Vector3.one` |
| 序列化引用运行时是 NULL,"按钮点了没反应",但代码/事件订阅都对 | ① prefab 本体字段就是空(旧 builder 漏接)→ builder 补 wire **所有**核心引用,别假设旧值还在;② 场景实例 **stale override** 盖住 prefab 值 → 附加加载场景(`OpenScene(path, Additive)`,不动当前打开的场景/未保存改动)+ `PrefabUtility.RevertPropertyOverride` + 只存该场景。先兜底让流程能验,**回头必须根修 prefab 并把兜底 override revert 掉** |
| VLG/HLG 里子物体塌成 0 宽,或高度是垃圾负数 | `childControlWidth=true`+`expandWidth=false` 但子物体无 Graphic/无 preferredWidth → 首选项=0;`childControlHeight=false` 时子物体沿用旧的(可能为负的)sizeDelta。规则:**section 类子物体给 LayoutElement.preferredHeight + ctrlH=true;子物体无宽度首选项时 expW=true** |

## 第五步 · Play 验证 —— 数值为主、截图为辅、走真流程

固定节奏:`改 → 停 Play → 重跑 builder → Play → 驱动 → dump/截图`。要点(细节手册在 `playmode-verify-iterate`):
- **数值 dump 第一通道**:关键节点 `GetWorldCorners`→`WorldToScreenPoint(canvas.worldCamera, …)` 得 screen rect,和参考 spec×canvas 缩放比(如 1080/1440=0.75)硬对;text 内容/active 状态一并 dump。截图(camera-RT,见 `ui-placement` A2)只判视觉质感。
- **走真实交互链路**:真 `button.onClick.Invoke()` → confirm 弹窗 → 结果。**正是走真按钮才暴露 `_upgradeButton` 空引用这种"点了没反应"的真 bug——probe 反射直调 handler 会完全绕过它。**
- **无不可测**:资源不够 cheat 造(数据 API 反射调,如 `BaseResourceData.Add`);建筑没建就直插数据 + `SpawnBuilding` 造一个,**测完清理**;两种状态(红字不足/绿勾足够)都要亲眼见到。
- **探针竞态**:面板 Show 后同帧读 `CanvasGroup.alpha=0` ≠ 没显示——`PlayReveal` 类渐入 tween 起点就是 0。隔 1-2s 重读再下结论,别对着假象修不存在的 bug。
- **异常必追根**:每个偏差数字要么解释清楚(如半透明 sprite 忠实于设计资产),要么修掉。"差不多"= 差很多。

## 第六步 · 收尾

- 新 universal 件回填 repo `Claude Feature Docs/UI Visual Design/Universal_Widgets_Registry.md`(唯一权威);新踩的坑回填本 skill / `ui-placement`;
- 临时 dump/驱动脚本全删(Assets 外的探针、`Assets/Editor/CoplayTemp/` 里的驱动);
- 汇报忠实:顺手修的 bug、故意保留的偏差、被 Play 弄脏的无关资产(如 TMP fallback 字体)都要说。

---

**一句话总纲:先测量、再诊断、贴纹理、真流程验证、异常必追根、收尾留资产。参考 spec 是抄答案,老 prefab 的 scale/z/override 是暗雷,真点击是照妖镜。**

标本:BuildingInfoPanel 对齐 PopupDim_Base_HQ/StoragVault/MedicalStation + UIBuildingInfoPopup 对齐 Popup_Base_HQ_Info(2026-07-02)——builder `Tools/Setup/Building Info Panel - Rebuild`,通用件 `UITimerWidget`/`CountdownTimer`/`UILabelValueRowWidget`,坑记录见 memory `base-tab-ui-and-deploy`。
