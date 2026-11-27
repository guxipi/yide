# 物品格与面板宽度：项目约定和实测数据

字号、字体、字色以 Unity 工程根目录 `CLAUDE.md` 的「UI 字体铁规」为准。

**项目约定。** 物品格用背包同款 `UIUniversalItemWidget`。右下角数字只表示堆叠数量，格式为 `xN`,右对齐、贴右下角。同一组格子的几何在空、满、锁定、选中、各稀有度状态下都不变。

**宽度量法。** 面板宽度一律换算成屏上像素再比(画布单位 × 根 canvas scaleFactor);旧背包屏在 1080 宽实机上是外壳约 1000 像素、左右各约 40 像素边距,只当量级参考,用之前在当前实机上复测。

`ui-width-range.png` 和 `gameplay-backpack-baseline.png` 是勾哥画的宽度范围：内容不窄于绿线，外壳不宽于红线。图里的面板样式已经过时，只看线。`itemframe-group-alignment-example.png` 是物品格没对齐的反例截图。
