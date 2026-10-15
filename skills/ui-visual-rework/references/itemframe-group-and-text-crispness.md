# 物品格与面板宽度：项目约定和实测数据

2026-10-15 从 Codex 个人 skill `er-ui-refine` 合并过来，按"只留事实、不留操作细则"瘦身。字号、字体、字色以 Unity 工程根目录 `CLAUDE.md` 的「UI 字体铁规」为准。

**项目约定。** 物品格用背包同款 `UIUniversalItemWidget`。右下角数字只表示堆叠数量，格式为 `xN`,右对齐、贴右下角。同一组格子的几何在空、满、锁定、选中、各稀有度状态下都不变。

**宽度实测(2026-09-04,旧背包屏)。** 当时的渲染目标是 1080 × 2400,根 canvas scaleFactor 为 0.8385255。可见外壳宽 1192 画布单位，约合 1000 像素；左右各留 48 画布单位，约合 40 像素。之后 CARGO 改版换过画布，用之前先在当前实机上复测。

`ui-width-range.png` 和 `gameplay-backpack-baseline.png` 是勾哥画的宽度范围：内容不窄于绿线，外壳不宽于红线。图里的面板样式已经过时，只看线。`itemframe-group-alignment-example.png` 是物品格没对齐的反例截图。
