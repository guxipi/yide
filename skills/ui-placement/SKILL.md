---
name: ui-placement
description: Use when placing, aligning, restyling, or building Unity uGUI UI in the Extraction project — RectTransform layout, anchors, panels, HUD, popups, tabs, item slots, multi-resolution / safe-area fitting. ALSO trigger on the user's Chinese requests, e.g. "摆一下UI" / "摆UI" / "摆一下界面" / "摆界面" / "调一下界面" / "做个界面" / "改UI" / "弄个面板/弹窗/HUD" / 涉及 UI、界面、面板、暂停界面、掉落/奖励格子、item slot、安全区、对齐 的任何摆放任务. Coplay's capture tools are BLIND to screen-space UI — see results via F8 ScreenCapture PNG + verify geometry numerically. Invoke BEFORE touching any .unity/.prefab UI or writing UI layout code.
---

# UI Placement (Extraction)

Extraction is **portrait-only** mobile (portrait 9:16; for the exact canvas ref see Source of truth below — kit screens are ratified to 1080×2340). The visual language, tokens, prefab mapping and per-screen specs already exist as docs — this skill is the **execution workflow + discipline**, not a re-spec.

## Source of truth — read, never duplicate
- `UI_Placement_Rules.md` (**bundled in this skill folder**) — hard placement law (band heights, button sizes, casing, banner/ribbon/badge/grid positions, HUD anchors) **measured from the SuperCasual kit prefabs** — the kit is the absolute standard. Read this for any "where/how-big/what-casing" question; match the kit prefab's own size/anchor, don't eyeball. Canvas ref RATIFIED to the kit's 1080×2340 for kit screens.
- `Claude Feature Docs/UI Visual Design/UI_Visual_Design_Guidelines.md` — 8px grid + tokens, colors, type scale, safe-area, portrait zones, animation timings (§7), feedback/juice (§8), layer manager, performance.
- `Claude Feature Docs/UI Visual Design/Component_Selection_Matrix.md` — which SuperCasual prefab for which job.
- `Claude Feature Docs/UI Visual Design/Screen_Layout_Specs.md` — per-screen layouts.
- Kit: `Assets/AssetPacks/UI/Layer Lab/GUI Pro-SuperCasual/`. Font: CookieRun Black Outline 54 SDF. Canvas layers: `Core.UI.UICanvasLayerManager` (Background 0 → SystemPopup 600).

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

## Make changes via `execute_script` (most reliable), not 20 granular MCP calls
For anything beyond a one-property tweak, write a C# file (class + `public static string Method()`) and run it with `execute_script` — atomic, reproducible, and it handles what granular calls fumble:
- **Find objects robustly**: `FindObjectOfType(type)` (ACTIVE only) or walk `SceneManager.GetActiveScene().GetRootGameObjects()` (includes INACTIVE roots). `GameObject.Find(path)` fails on inactive objects / wrong path — never trust it for hidden panels.
- **Resolve a game type**: loop `AppDomain.CurrentDomain.GetAssemblies()` + `asm.GetType("Namespace.Type")` — don't assume `Assembly-CSharp`.
- **Wire serialized `[SerializeField]` privates**: `var so = new SerializedObject(comp); so.FindProperty("_field").objectReferenceValue = target; so.ApplyModifiedPropertiesWithoutUndo();`.
- **Prefab edits**: MCP `set_property` + `prefab_path` works for simple props (float/bool). `PrefabUtility.ApplyObjectOverride(comp, prefabPath, InteractionMode.AutomatedAction)` pushes an instance's component values down to the prefab. `LoadPrefabContents`/`SavePrefabAsset` can throw "Can't save a Prefab instance" with nested prefabs — prefer the first two.
- Temp `.cs` go at **project root** (NOT under Assets — avoids a domain reload), run, then delete.

## RectTransform — the traps that bit us
- **Never set `localPosition` on a stretch RectTransform.** It corrupts `anchoredPosition` and shoves the whole subtree off-screen (this pushed a pause panel to the top-right corner, CONTINUE button off-screen). To fill a parent: `anchorMin=(0,0); anchorMax=(1,1); pivot=(0.5,0.5); offsetMin=offsetMax=Vector2.zero;` — and leave localPosition alone.
- **Panels ship hidden by default**: serialize `CanvasGroup` alpha=0, interactable=false, blocksRaycasts=false. Don't rely *only* on a runtime `HideImmediate` — any frame before it runs (or any session where it doesn't) leaks the panel on screen.
- **Re-parenting keeps world layout only if the new parent's rect matches.** After moving a root into a layer, reset it to fill (above) and confirm children's worldPos are on-screen.
- "active" ≠ "visible/correct" — confirm worldPos is within screen bounds, not just that the GameObject is active.

## Anchors & layout — structured ops, never hand-math
- **Center / edge-pin**: anchor preset, not a computed anchoredPosition.
- **Rows / grids / lists**: `Horizontal/Vertical/GridLayoutGroup` + `ContentSizeFitter`. (Perf §13: Layout Groups rebuild on child change — static layouts prefer fixed RectTransforms; groups for dynamic content.)
- **One-frame layout jitter** (nested Group/ContentSizeFitter not settled the frame you read/screenshot it, esp. after populating a list or `SetActive(true)`): don't trust "it'll fix itself next frame" — force it deterministically with `LayoutRebuilder.ForceRebuildLayoutImmediate(rectTransform)` right after the content change. This is the escape hatch for "looked wrong in the shot but fine on replay" — that's an unsettled rebuild, not a flake.
- **Anchor each element to its own screen corner/edge** so it sticks across aspect ratios.
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
- Play Mode is for **look/verify (read-only)**; placement edits made in Play are discarded.

## Multi-resolution
- Project convention (verified): `CanvasScaler` = Scale With Screen Size, **reference 1440×2560** (portrait 9:16), **Match ≈ 0.5** (some canvases use 0 — confirm per-canvas).
- Pick one base aspect; expand along a single axis; check a few portrait ratios (tall 9:19.5, 9:16, tablet 3:4) via F8 shots.

## Safe area (notch / punch-hole / gesture bar)
- Don't hardcode pixel offsets. Use `Core.UI.SafeArea` (`Assets/Scripts/Core/UI/SafeArea.cs`, `[ExecuteAlways]`, driven by `Screen.safeArea`). Add a full-screen SafeArea child under the canvas, parent screen UI to it; close/back buttons + tab bar inside it. `_conformY` = top notch + bottom gesture bar; `_conformX` = curved/landscape only. Insets to the device's *actual* safe area (guidelines' "44/34" are design paddings, separate). Per-layer wiring: wrap each content layer (HUD/Overlay/Main) in its own SafeArea container; leave Background full-bleed (don't inset it).

## Juice = art, not generated code
Gradients/metallic/glow come from kit 9-slice sprites, not code (uGUI has no native box-shadow/gradient). Your job: layout, hierarchy, state swaps (normal/pressed/disabled §2.4), DOTween motion (§7). Pull effect sprites from the kit.

## Spacing & tokens
8px scale (xs4 / sm8 / md16 / lg24 / xl32 / 2xl48) + documented colors/type scale. No freehand gaps. Equal spacing via Layout Groups.

## Hard rules (always)
- Portrait only · place in Edit Mode · **save scene right after editing** · no text-editing of `.unity`/`.prefab` (use execute_script / MCP) · **verify before "fixed": numeric worldPos on-screen OR an F8 PNG — never trust Coplay's capture tools or a flow-only test.**
