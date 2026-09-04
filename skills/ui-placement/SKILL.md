---
name: ui-placement
description: Placing, aligning, restyling, or building Unity uGUI UI in Extraction — RectTransform layout, anchors, panels, HUD, popups, tabs, item slots, multi-resolution / safe-area fitting. Trigger — "摆一下UI" / "摆UI" / "摆一下界面" / "摆界面" / "调一下界面" / "做个界面" / "改UI" / "弄个面板/弹窗/HUD" / 涉及 UI、界面、面板、暂停界面、掉落/奖励格子、item slot、安全区、对齐 的任何摆放任务. Coplay capture tools are BLIND to screen-space UI — verify via F8 ScreenCapture PNG + numeric geometry. Invoke BEFORE touching any .unity/.prefab UI or UI layout code.
---

# UI Placement (Extraction)

Extraction is **portrait-only** mobile (portrait 9:16; for the exact canvas ref see Source of truth below — kit screens are ratified to 1080×2340). The visual language, tokens, prefab mapping and per-screen specs already exist as docs — this skill is the **execution workflow + discipline**, not a re-spec.

## Source of truth — read, never duplicate
- `UI_Placement_Rules.md` (**bundled in this skill folder**) — hard placement law (band heights, button sizes, casing, banner/ribbon/badge/grid positions, HUD anchors) **measured from the SuperCasual kit prefabs** — the kit is the absolute standard. Read this for any "where/how-big/what-casing" question; match the kit prefab's own size/anchor, don't eyeball. Canvas ref RATIFIED to the kit's 1080×2340 for kit screens.
- `Claude Feature Docs/UI Visual Design/UI_Visual_Design_Guidelines.md` — 8px grid + tokens, colors, type scale, safe-area, portrait zones, animation timings (§7), feedback/juice (§8), layer manager, performance.
- `Claude Feature Docs/UI Visual Design/Component_Selection_Matrix.md` — which SuperCasual prefab for which job.
- `Claude Feature Docs/UI Visual Design/Screen_Layout_Specs.md` — per-screen layouts.
- Kit: `Assets/AssetPacks/UI/Layer Lab/GUI Pro-SuperCasual/`. Font(2026-07-07 修订为二分制): Title/大数字 = CookieRun Black Outline 54 SDF;其余一切 = `Cairo_Line_Black SDF`(kit ResourcesData/Fonts),均挂 CJK fallback。Canvas layers: `Core.UI.UICanvasLayerManager` (Background 0 → SystemPopup 600).
- **Universal 件唯一注册表** = repo `Claude Feature Docs/UI Visual Design/Universal_Widgets_Registry.md`(2026-07-07 起唯一权威,已自 Claude 记忆迁入 repo)。做任何 UI **先查它复用**;新建 universal 件必回填该表。别再指向 Claude memory 的 `universal-ui-widgets`(已废弃)。

## 真源模型 + 交互底线(2026-07-07 拍板)
总纲:`Claude Feature Docs/UI Architecture Refactor/HANDOVER_UI真源prefab化_总纲.md`;硬契约:`Claude Feature Docs/UI Visual Design/Visual_Refine_Contract.md`。
- **UI 真源 = prefab(目标态)**。过渡期双轨,动手前先判目标屏在哪条轨:
  - **已 prefab 化的屏**:直接改 prefab(Prefab Mode / `LoadPrefabContents`),对应 **builder 已退役——禁止重跑 Rebuild** 冲掉手工 refine。
  - **未迁移的旧屏(现状大多数)**:仍是"改 builder + 重跑菜单",不手摆场景(手摆的下次 Rebuild 被冲掉)。
- **判轨方法**:查总纲 M3 进度表该屏是否已迁 + 菜单项是否带 **"(retired)"** 前缀(退役 builder 加此前缀不删代码);拿不准就 grep builder 的 `Tools/Setup` 菜单名。
- **新面板一律 prefab**(进 `Prefabs/UI/Meta/` 或 `Prefabs/UI/Gameplay/`),**禁止新增场景内联 UI 子树**。
- **交互底线(立即生效)**:
  - 含文字/可交互元素的 UI 必须整体在安全区内(`Core.UI.SafeArea`);可点矩形出安全区 = 缺陷。
  - **每个 UI 必有可达的关闭/后退按钮**,并接系统返回键栈(Android:Escape→`UIPopupsManager` 栈顶 GoBack→`AppNavigator` 兜底;iOS 无系统返回键,等价保证 = 必有关闭钮)。
  - **新面板必须注册 `AppNavigator` deeplink 路由**;末端 UI 跳转复用 navigator,返回键/deeplink/popup 栈共享同一条栈逻辑。

## Diagnose from the YAML first (read-only)
Hand-EDITING `.prefab`/`.unity` stays banned — but **READING them with Grep/Read is the fastest root-cause channel**: a layout bug is often fully pinned before Unity is even touched (battle-tested: the UIBaseTabTopBar resource-row squish — left-anchored container, non-uniform 0.6 scale, HLG spacing 24 — was diagnosed entirely from the prefab text).
- Walk the tree by fileID: `m_Children`/`m_Father` on RectTransforms; read anchors/pivot/`m_LocalScale`/`m_SizeDelta` plus the LayoutGroup block (`m_Spacing`, `m_ChildAlignment`, `m_ChildControl*`).
- Nested prefabs appear as `PrefabInstance` blocks — their `m_Modifications` list is where per-instance size/active overrides hide (e.g. a hidden "+" button = `m_IsActive 0` on a child fileID).
- **Before editing a prefab, grep the scene for `target: {fileID: <that RT's fileID>, guid: <prefab guid>`** — a scene override on the same property masks your prefab edit ([[ui-prefab-not-scene-copy]]). No hits = the prefab edit will take effect.

## Seeing the result — Coplay capture is BROKEN; use these two channels (battle-tested)
`capture_ui_canvas` / `capture_scene_object` render through an offscreen camera/RT and **miss Screen Space (Overlay & Camera) canvases → black/grey images**. Do NOT rely on them for this project's UI. Instead:

**A. See pixels = `ScreenCapture.CaptureScreenshot` → `Read` the PNG.**
- Captures the final composited frame (all UI layers) to a disk file; bridge-independent (readable even if the MCP bridge drops on Play).
- **Only writes when called from the GAME LOOP** (a MonoBehaviour during Play) — calling it from `execute_script` (editor context) silently writes nothing. Also needs a real rendered frame (won't write in Boot/loading).
- The project's **F8 PlaytestMarker IS exactly this** → writes `playtest-sessions/session-*/marker-*/shot.png` (+ note.txt/context.json). Flow: get the UI on screen in Play → user presses **F8** → `Read` the newest `shot.png`. This is THE visual channel (see [[playtest-realtime-stt]]).

**A2. Screen Space - Camera canvases (MetaUIRoot/UICanvasLayerManager is one) can be screenshotted WITHOUT F8**: from `execute_script` during Play, render the canvas's real camera to a RenderTexture — `cam = rootCanvas.worldCamera; cam.targetTexture = rt; cam.Render(); ReadPixels → File.WriteAllBytes("x.png")`. Works in editor context (battle-tested on the Achievement popup); only Overlay canvases need the F8 path. Note: dynamically-compiled MonoBehaviours added via execute_script never get Update() called — do checks/captures synchronously, not via spawned helper components.

**B. Verify geometry/state numerically = `execute_script` in a LIVE Play session.**
- Read ground truth: `Time.timeScale`, widget flags (`IsPaused`), `CanvasGroup.alpha/blocksRaycasts`, and each key element's `RectTransform.position` (world).
- **On-screen test**: a shown element must satisfy `0 < worldPos.x < 1440` and `0 < worldPos.y < 2560`. An element at x=1744 is off the right edge — the exact class of bug a flow/timeScale test will NOT catch. **Camera-mode canvases use world units ≠ pixels** — convert corners with `RectTransformUtility.WorldToScreenPoint(canvas.worldCamera, corner)` first, then bounds-test against `Screen.width/height`.
- This is conclusive when you can't screenshot. **Do it before claiming "fixed"** ([[verify-before-handoff]]); a flow test (timeScale toggles) passing does NOT mean the panel renders correctly.
- For rows/grids: dump each child's `GetWorldCorners` → `WorldToScreenPoint` and assert **equal gaps + the intended edge margin** — a numeric pass/fail beats squinting at a PNG.

## Make changes via `execute_script` (most reliable), not 20 granular MCP calls
For anything beyond a one-property tweak, write a C# file and run it with `execute_script` — atomic, reproducible, and it handles what granular calls fumble. **Entry-point contract: a class with a `public static Execute()` method** — Coplay looks for exactly that method name (any other name → "no entry point was found"); pass the file via the `filePath` argument.
- **Find objects robustly**: `FindObjectOfType(type)` (ACTIVE only) or walk `SceneManager.GetActiveScene().GetRootGameObjects()` (includes INACTIVE roots). `GameObject.Find(path)` fails on inactive objects / wrong path — never trust it for hidden panels.
- **Resolve a game type**: loop `AppDomain.CurrentDomain.GetAssemblies()` + `asm.GetType("Namespace.Type")` — don't assume `Assembly-CSharp`.
- **Wire serialized `[SerializeField]` privates**: `var so = new SerializedObject(comp); so.FindProperty("_field").objectReferenceValue = target; so.ApplyModifiedPropertiesWithoutUndo();`.
- **Prefab edits**: MCP `set_property` + `prefab_path` works for simple props (float/bool). `PrefabUtility.ApplyObjectOverride(comp, prefabPath, InteractionMode.AutomatedAction)` pushes an instance's component values down to the prefab. For structural/multi-property edits the battle-tested pattern is `LoadPrefabContents(path)` → edit → `SaveAsPrefabAsset(root, path)` → `UnloadPrefabContents` in `finally` — safe even when the prefab CONTAINS nested prefab instances (the "Can't save a Prefab instance" throw comes from passing a scene instance, not loaded contents). After saving, re-`Read` the `.prefab` on disk to confirm the write landed ([[tool-output-ghost-text]]).
- One-off probe `.cs` go at **project root** `Temp/` (NOT under Assets — avoids a domain reload), run, then delete; keep-as-tool builders → `Assets/Editor/CoplayTemp/`.

## RectTransform — the traps that bit us
- **Never set `localPosition` on a stretch RectTransform.** It corrupts `anchoredPosition` and shoves the whole subtree off-screen (this pushed a pause panel to the top-right corner, CONTINUE button off-screen). To fill a parent: `anchorMin=(0,0); anchorMax=(1,1); pivot=(0.5,0.5); offsetMin=offsetMax=Vector2.zero;` — and leave localPosition alone.
- **Panels ship hidden by default**: serialize `CanvasGroup` alpha=0, interactable=false, blocksRaycasts=false. Don't rely *only* on a runtime `HideImmediate` — any frame before it runs (or any session where it doesn't) leaks the panel on screen.
- **Re-parenting keeps world layout only if the new parent's rect matches.** After moving a root into a layer, reset it to fill (above) and confirm children's worldPos are on-screen.
- "active" ≠ "visible/correct" — confirm worldPos is within screen bounds, not just that the GameObject is active.

## Anchors & layout — structured ops, never hand-math
- **Center / edge-pin**: anchor preset, not a computed anchoredPosition.
- **Rows / grids / lists**: `Horizontal/Vertical/GridLayoutGroup` + `ContentSizeFitter`. (Perf §13: Layout Groups rebuild on child change — static layouts prefer fixed RectTransforms; groups for dynamic content.)
- **One-frame layout jitter** (nested Group/ContentSizeFitter not settled the frame you read/screenshot it, esp. after populating a list or `SetActive(true)`): don't trust "it'll fix itself next frame" — force it deterministically with `LayoutRebuilder.ForceRebuildLayoutImmediate(rectTransform)` right after the content change. This is the escape hatch for "looked wrong in the shot but fine on replay" — that's an unsettled rebuild, not a flake.
- **`ForceRebuildLayoutImmediate(rect)` only rebuilds if `rect` ITSELF carries an ILayoutController** (LayoutGroup / ContentSizeFitter / ScrollRect). Called on a panel root with no group, Unity's `PerformLayoutControl` stops right there and it is a **silent no-op on every descendant** — you think you forced a rebuild, nothing happened. Call it on the group/content that actually drives the layout.
- **A single-row LayoutGroup will crush localizable text into "stacked glyphs".** With `childControlWidth=true`, when `Σ child.preferredWidth + spacing > row width` the group compresses children *below their content size*; a `NoWrap` centered TMP then overflows its own rect and bleeds into its neighbours (that is what "all the text piled up" actually is — overflow collision, not centering). Design-time placeholders ("87 KILLS") fit; runtime localized strings ("Lost loot value: 2,500") don't — ER ships 9 locales, DE/FR run longest. Measure the sum before you commit to a row; when it can't be guaranteed, use **one wrapping TMP** instead: NBSP (` `) inside each segment, a plain space between segments as the only legal break point. Never overlaps, wraps in any locale, reuses already-translated strings.
- **Item grids with dynamic counts need a real scroll rig**, not a fixed-height rect: `ScrollRect → Viewport(RectMask2D + transparent raycast Image) → Content(GridLayoutGroup + ContentSizeFitter vertical=PreferredSize, top anchor, pivot(0.5,1))`. A bare GridLayoutGroup in a fixed rect overflows downward and covers whatever sits below it (buttons).
- **Anchor each element to its own screen corner/edge** so it sticks across aspect ratios.
- **"Fine in Edit Mode, re-squishes every runtime"** = someone hand-dragged children INSIDE a LayoutGroup; the dragged positions are serialized lies — the next rebuild (Play always rebuilds) snaps back to the group's config. Fix the GROUP (spacing/alignment/container anchors); never re-drag its children.
- **Overhanging child visuals break LayoutGroup spacing math.** A widget's icon/button anchored AT its rect edge often pokes OUTSIDE the rect (icon anchored x=0 centered on the edge → ~half its width overhangs left; "+" button anchored x=1 → half overhangs right). Layout Groups only see rect widths, so the real collision line is `spacing ≥ prevRightOverhang + nextLeftOverhang + visible gap` — measure the overhangs from the widget prefab's YAML, don't eyeball. (UICurrencyItemWidget: icon −40 left, "+" +35 right ⇒ spacing 24 meant ~51px of guaranteed overlap; 100 reads clean.)
- **Edge-hugging row recipe** (e.g. currency row on the screen's right): container `anchorMin=anchorMax=(1, y)`, `pivot.x=1`, `anchoredPosition.x = −margin`, HLG `childAlignment=MiddleRight` — hugs the edge on every aspect ratio, no computed x.
- **Non-uniform `localScale` on a UI container (e.g. 0.6 / 0.6225) = hand-tweak smell** — subtle distortion; normalize to uniform while you're there.
- Coplay tools (for simple ops): `set_rect_transform`, `set_ui_layout`, `set_property`, `create_ui_element`, `set_ui_text`, `set_sibling_index`, `add_component`, `parent_game_object`.
- In-editor hands-on tool: **`DuckGames/UI Designer`** menu (palette / property / preview / templates / undo).

## SuperCasual kit specifics (learned)
- Kit "buttons" (e.g. `Button_124_Green/Blue`) are styled **Images with NO `Button` component** — add `Button` before wiring onClick (filter-by-Button returns empty = they're not buttons yet).
- `LayerLab.CasualGame.PanelView` is a trivial OnEnable/OnDisable SetActive-cascade, not an animation system — don't fight it.
- To re-skin existing behaviour, reuse the proven widget (e.g. `UIPauseMenuWidget`: timeScale pause, DOTween `.SetUpdate(true)`, audio snapshots, `ExtractionService.AbandonSessionAsync` → `SceneTransitionService.ReturnToHomeScreenAsync`); for run-reward grids reuse `UIDeathSummaryPanel`'s loot-cell pattern fed by `ExtractionService.SessionLoot/SessionCoins`.

## Wiring behaviour — follow ER's existing event/mediator convention (don't invent MVVM)
ER already has a consistent decoupling pattern — **UI reflects state via events; it never polls game logic to push updates, and game logic never reaches into UI.** Match it; don't hand-roll a new binding layer.
- **Subscribe, don't poll.** A widget listens to an event and refreshes itself in the handler. Sources, in order of preference: the owning **service's own `UnityEvent`** (`ExtractionService.OnSessionCoinsChanged`, `BasePlacementService.OnPlacementConfirmed`), then the global bus **`Core.Events.GameEvents`** (`OnPlayerStatsChanged`, `OnItemAdded`, …). Pattern: `UICoinHudWidget` → `OnLootRegistered` → `RefreshCoinText()`.
- **Subscribe/unsubscribe in matched pairs.** Subscribe in `Start`/`OnEnable`, **always `-=` in `OnDestroy`** (and `transform.DOKill()` / tween `.Kill()` there too). Leaked listeners on destroyed widgets = the "changed A, B broke" class of bug.
- **Async-spawned dependencies**: services/singletons may not exist when your `Start` runs (Hero spawns async — see [[init-order-singleton-caching]]). Late-bind: try-subscribe each frame until resolved (`UICoinHudWidget.TrySubscribeToExtraction`), don't cache in `Start` and assume it's there.
- **Sub-panels talk through the panel-root mediator, not to each other.** A sub-panel raises an intent event upward (`OnDemolishRequested`); the root (`UIBasePanel` — "central mediator between sub-panels and services") routes it to the service and orchestrates show/hide. Don't let a sub-panel reach into a sibling or a service directly.
- **The one sanctioned "poll":** a self-healing gate off a single source of truth (e.g. `UICoinHudWidget` enabling its button from `Time.timeScale`). That's deliberate, not naive coupling — don't copy it for general state sync.

## Play Mode reality (this project)
- Pressing Play boots **Boot → menus**, NOT directly into a wave — you can't script your way into gameplay; a scene's widgets are absent/inactive until you're actually in that scene/state.
- **Save the scene immediately after editing** — unsaved edits get wiped when a Play session loads a different scene.
- Editing `.cs` triggers a domain reload — do it in Edit Mode. The user may enter Play Mode at any time: check `get_unity_editor_state.playMode` before `open_scene` (it errors in Play).
- Play Mode is for **look/verify (read-only)**; placement edits made in Play are discarded. (Prefab ASSET edits do persist — but do them in Edit Mode anyway, then re-enter Play to verify.)
- **Split act/measure across separate `execute_script` calls** (e.g. switch tab in call 1, capture+measure in call 2): frames pass between MCP calls so layout settles naturally, and each script stays pure-sync ([[mcp-execute-script-async-hang]]).
- **Drive the real flow, not SetActive**: reach a home tab via `UITabNavigationManager.SwitchToTab<T>()`; a popup photobombing your capture (Daily Login etc.) → find its real `CloseButton` and `onClick.Invoke()` it.

## Multi-resolution
- Project convention (verified): `CanvasScaler` = Scale With Screen Size, **reference 1440×2560** (portrait 9:16), **Match ≈ 0.5** (some canvases use 0 — confirm per-canvas).
- Pick one base aspect; expand along a single axis; check a few portrait ratios (tall 9:19.5, 9:16, tablet 3:4) via F8 shots.
- **Canvas unit width SHRINKS on taller phones** (ref 1440×2560, match 0.5): 9:16 → 1440, 19.5:9 → ~1304, 20:9 → ~1288, 21:9 → ~1257 units. Before committing an edge-anchored row, do the arithmetic: row visual span (content + overhangs, × scale) must fit the NARROWEST width without hitting left-side content — a layout that fits 9:16 can collide on 21:9.

## Safe area (notch / punch-hole / gesture bar)
- Don't hardcode pixel offsets. Use `Core.UI.SafeArea` (`Assets/Scripts/Core/UI/SafeArea.cs`, `[ExecuteAlways]`, driven by `Screen.safeArea`). Add a full-screen SafeArea child under the canvas, parent screen UI to it; close/back buttons + tab bar inside it. `_conformY` = top notch + bottom gesture bar; `_conformX` = curved/landscape only. Insets to the device's *actual* safe area (guidelines' "44/34" are design paddings, separate). Per-layer wiring: wrap each content layer (HUD/Overlay/Main) in its own SafeArea container; leave Background full-bleed (don't inset it).

## Juice = art, not generated code
Gradients/metallic/glow come from kit 9-slice sprites, not code (uGUI has no native box-shadow/gradient). Your job: layout, hierarchy, state swaps (normal/pressed/disabled §2.4), DOTween motion (§7). Pull effect sprites from the kit.

## Spacing & tokens
8px scale (xs4 / sm8 / md16 / lg24 / xl32 / 2xl48) + documented colors/type scale. No freehand gaps. Equal spacing via Layout Groups.

## Hard rules (always)
- Portrait only · place in Edit Mode · **save scene right after editing** · no text-editing of `.unity`/`.prefab` (use execute_script / MCP) · **verify before "fixed": numeric worldPos on-screen OR an F8 PNG — never trust Coplay's capture tools or a flow-only test.**

**一个屏"改了又弹回来"、override 几百条、prefab 里对进场景全歪 → 那是结构性的多作者问题,别在这里硬摆,走 `ui-truth-reclaim` 先收成单一真源(`Tools/UI Truth/Reclaim Window` + `Audit All Screens`)。**
