---
name: figma-ugui-bridge
description: Turn a Figma design into a Unity UGUI prefab using the self-built figma-ugui-bridge tool (a Figma Plugin-API exporter + a Unity Editor importer) — NOT Figma MCP. Use when you HAVE a Figma design and want a UGUI prefab out of it, multi-resolution anchors inferred. ALSO trigger on the user's Chinese requests, e.g. "照figma摆" / "figma落地" / "从figma导UI" / "figma导ugui" / "figma到unity" / "figma2unity" / "配置figma2unity" / "我要配置 Figma2Unity" / 涉及 把 Figma 设计稿导成 Unity prefab 的任务. This is a THIN handbook: the tool's code lives in its own repo `guxipi/figma-ugui-bridge` (clone it); this skill only tells you how to drive it + its naming convention + caveats. NOT for engine-direct UI work — projects with Coplay/Unity write-MCP (e.g. Extraction) that say "摆UI/对齐" go to the ui-placement skill instead.
---

# figma-ugui-bridge (Figma → UGUI prefab)

A **self-built** pipeline: Figma selection → `layout.json` + sliced PNGs → a Unity **UGUI prefab** with inferred multi-resolution anchors. It reads Figma through the **Plugin API** (runs locally in the Figma desktop client) to dodge the free-tier REST/MCP cap (6 req/month since 2025-11-17). No token, no per-month limit.

> **This skill is a handbook, not the tool.** The code is its own repo — do NOT vendor it into yide.
> Repo: `https://github.com/guxipi/figma-ugui-bridge` (private; owner = guxipi).
> Two halves: `figma-plugin/` (TS Figma plugin, the exporter) + `unity-importer/` (Unity package `com.yide.figma-ugui-importer`, the importer).

## When this vs other UI skills (don't cross the wires)
- **This skill** = you have a **Figma design** and want a **prefab generated** from it.
- **ui-placement** = engine-direct uGUI placement/alignment via Coplay/Unity write-MCP (e.g. **Extraction**). ER saying "摆UI/对齐" goes there, **not** here.
- **gen-uibind** = the **downstream** step: a prefab already exists (whether made by this bridge or by hand) → generate the `XxxPanel.Generated.cs` reference-binding code so you stop hand-dragging refs / hand-writing `transform.Find`. Chain: `Figma → (this) → prefab → (gen-uibind) → Generated.cs`.

## Get the tool (per machine, one-time)
```bash
git clone https://github.com/guxipi/figma-ugui-bridge   # to a LOCAL disk
cd figma-ugui-bridge/figma-plugin
npm install
npm run build        # -> dist/code.js + dist/ui.html (JSZip inlined, offline)
npm test             # vitest: markers / coords / anchors (23 tests)
```
> ⚠️ **Do NOT put the clone on Google Drive / OneDrive** — `npm install` fails on the virtual
> filesystem (`EBADF`). The `H:\My Drive\中转\figma-ugui-bridge` copy is a transfer/staging copy
> only, NOT a build clone. Clone fresh to a local disk to build.

In **Figma desktop** (plugins don't run in the browser):
`Plugins ▸ Development ▸ Import plugin from manifest…` → pick `figma-plugin/manifest.json`.

## Figma layer naming convention (the contract — author layers like this)
| Marker in layer name | Meaning | Unity result |
|---|---|---|
| `Btn_…` prefix | button | `Button` + `targetGraphic` |
| `Txt_…` prefix | text | `TextMeshProUGUI` |
| `@9s(l,r,t,b)` | nine-slice | TextureImporter border + `Image.type = Sliced` |
| `@stretch` / `@stretch-h` / `@stretch-v` | force stretch anchors | overrides inferred anchor |
| `@anchor(tl/t/tr/l/c/r/bl/b/br)` | force anchor side | overrides inferred anchor |
| `@img` | bake vector/group to one PNG | exported as a single image |
| `@ignore` | skip node + subtree | not exported / not built |
| `@safe` | safe-area fitter | `FigmaSafeArea` component attached |

Anchor inference priority: **markers → non-default Figma constraints → geometric heuristic**.
> The `Btn_` / `Txt_` **prefix** convention is carried onto the generated GameObject names — keep this
> in mind when configuring **gen-uibind** downstream (its marker matcher should recognize the `Btn_` prefix
> so bridge-made prefabs feed straight in).

## End-to-end flow
1. **Figma**: name layers per the table; select top-level **Frame(s)**; run the plugin → choose **1x/2x** → **Export → zip**. Unzip anywhere (`layout.json` + `images/`).
2. **Unity (per project, one-time)**: `Window ▸ Package Manager ▸ + ▸ Add package from disk…` → pick `unity-importer/package.json`. Pulls `com.unity.nuget.newtonsoft-json`; TMP+UGUI are built into Unity 6.
3. **Import**: `Tools ▸ Figma Importer ▸ Import From Folder…` → pick the unzipped folder → prefab written to `Assets/UI/Prefabs/<Frame>.prefab` (images under `Assets/UI/Imported/<Frame>/`). Console prints `added / updated / removed`.
4. **Re-import = stable update**: each GameObject carries `FigmaBinding(nodeId)`; re-importing the same frame **reuses objects by id**, so user-added scripts/refs survive. Nodes deleted in Figma (that still carry a binding) are removed; user-added objects without a binding are left alone.
5. **Verify across resolutions**: drag prefab under a `Canvas` (Scale With Screen Size); `Tools ▸ Figma Importer ▸ Multi-Res Preview…` → Capture (best in Play mode). Top-pinned hug top, bottom hug bottom, centered stay centered, full-bleed stretch.

### Reference resolution (auto-match)
Importer reads `referenceResolution` + `matchWidthOrHeight` from a scene `CanvasScaler` (or `TargetCanvasName`), so the same zip adapts to whatever project it lands in. No CanvasScaler → falls back to the frame's own size (1:1); non-matching aspect ratio logs a warning. **Match the Figma frame to the Canvas reference resolution to avoid non-uniform scaling.**

### Batch / MCP entry point
```csharp
var settings = new Yide.FigmaUGUI.Editor.ImportSettings();
var prefab = Yide.FigmaUGUI.Editor.FigmaImporter.ImportFolder(@"C:\path\to\unzipped", settings);
```

## The one trap that bites
The shared algorithm (coordinate y-flip + anchor inference) is implemented **twice** —
`figma-plugin/src/{coords,anchors}.ts` and `unity-importer/Editor/{CoordConvert,AnchorSolver}.cs`.
**Change one side → change the other.** Both sides have unit tests; run both.

## Known limitations (carry honestly, don't oversell)
- Rounded solid rects render as plain quads (cornerRadius kept in data only) — use `@9s` 9-slice for rounded UI.
- Gradients / stacked fills → only the top SOLID or IMAGE is recorded.
- `SPACE_BETWEEN` auto-layout approximated (warned). Rich text / `<sprite>` mixed content is out of scope (plain TMP placeholder).
- `lineHeightPx` not applied; `letterSpacing` ≈ TMP `characterSpacing` (unit mismatch).
- Multi-Res Preview uses **undocumented internal GameView APIs** (reflection) — best-effort, may need tweaks per Unity version, renders best in Play mode.

## Verification status (as of the bridge's 2026-06-11 handoff — verify before claiming)
- **Plugin**: `npm run build` + `tsc` zero errors; **vitest 23/23 green**. ❗ **Not loaded in Figma desktop** in the build environment (no Figma there) — the live `exportAsync`/postMessage/zip round-trip needs **one manual run on a machine with Figma**. Don't claim the export path is verified until you've run it.
- **Importer**: verified in **Extraction (Unity 6000.3.5f2)** — install → zero compile errors → sample `layout.json` imported; top/bottom/center/stretch anchors + auto-match scaling + `Button.targetGraphic` + SafeArea + LayoutGroup + CanvasGroup all checked. (Package was then removed from ER and the test prefab deleted — ER restored.)

## What this skill does NOT do
- It does not modify the prefab after import beyond the importer's own behavior, and it does not generate your panel's **reference-binding C#** — that's **gen-uibind**'s job (run it on the produced prefab).
- It does not live inside ER. The bridge is a generic tool, not bound to any one game.
