# 04 Unity 光照系统选型和手机成本

来源标记:〔读〕〔测〕〔推〕同 01。主要来源:Unity 6.0 手册的 URP 光照各页、电子书《Introduction to URP for advanced creators (Unity 6 edition)》第 33–104 页、《Optimize your game performance for mobile, XR and the web (Unity 6 edition)》第 50–57 页、Android 开发者站的 Unity 手机光照指南、Riot VALORANT 文章、Unity 的 Survival Kids 文章和 Galactic Colonies 案例。数字是 Unity 6.0 的,换版本要核。

工程当前的渲染设置先读真值再谈方案:`Assets/Settings/` 下的 RP Asset(阴影分辨率、距离、级联、软阴影档、每物体灯数上限、探针系统)和 Renderer(渲染路径、挂了哪些 renderer feature 及其参数),以及 `ProjectSettings/QualitySettings.asset` 里各档用的是哪个 RP Asset。

## 一、每种光用什么实现

| 要的光 | 可选机制 | 手机代价 | 限制 | shader 要接什么 |
|---|---|---|---|---|
| 暖色太阳主光和它的投影 | 实时或混合方向光加阴影图;混合 + Shadowmask(静态影烘、动态影实时);混合 + Subtractive(静态的直接光和影都烘进光照图);全烘加 blob 影 | 主光逐像素是最便宜的实时光。投影代价跟投影物数量(由 Max Distance 决定)、级联数、分辨率、软阴影采样数走 | 只有一盏方向光能投影。Subtractive 下烘焙影和实时影混不对,只有一个 Realtime Shadow Color 可调。Shadowmask 每个像素最多 4 盏混合光重叠,多一张贴图 | 主光阴影关键字、软阴影关键字、`GetMainLight(shadowCoord)`、ShadowCaster pass;烘焙影再加 `LIGHTMAP_SHADOW_MIXING`、`SHADOWS_SHADOWMASK` |
| 冷色天光补光 | 环境光设成 Gradient(天 / 赤道 / 地)或 Color,按 SH 求值;或烘进光照图、探针、APV | SH 求值几乎免费;RP Asset 的 SH Evaluation Mode 可选逐顶点 | 只有 Gradient 和 Color 模式能实时改;Skybox 模式要重烘。环境光本身不认几何遮挡 | `SampleSH` 或 `SAMPLE_GI`;`EVALUATE_SH_*` 关键字 |
| 地面反弹 | 渐变环境光的地面色(按法线 y 的半球项,免费);烘焙 GI;一盏不投影、从下往上的方向光 | 前两种没有运行时灯的代价 | 烘焙反弹是静态的;第三种占一个附加光名额,而且不认遮挡 | 烘焙的要光照图关键字和 Meta pass |
| 招牌、路灯的局部有色光 | 烘焙点光 / 聚光 / 面光(面光只能烘);烘焙自发光(材质 Emission GI 设 Baked);不投影的实时附加光;带 cookie 的聚光代替实时影;加色面片、贴花、光晕面片 | 烘的没有运行时代价。点光投影等于六张聚光阴影,文档建议手机上少用或不用 | Forward 路径每个物体最多 8 盏附加光,手机每个相机 32 盏。烘焙光只有漫反射没有高光。烘焙自发光只照亮静态物体,动的要靠探针 | 附加光关键字和循环;烘的要 `LIGHTMAP_ON`、Meta pass 输出自发光 |
| 接触和遮挡的压暗 | 光照图里的烘焙遮蔽;SSAO renderer feature;blob 或投射面片影;画的或顶点色遮蔽 | SSAO 要深度法线预通道,各参数代价见 03 | SSAO 只对不透明物体;After Opaque 会和烘焙遮蔽压两遍 | `_SCREEN_SPACE_OCCLUSION`、DepthNormals pass |
| 玻璃反射 | 烘焙反射探针;天空盒回退;在自己的 shader 里采一张手做的 cubemap 或 matcap | 文档建议低端手机关掉探针混合和 box projection;探针对合批代价高 | 每个物体最多 2 个探针;URP 没有屏幕空间反射 | 探针关键字,或直接采 cubemap |

## 二、数字和上限(Unity 6.0)

灯:

- Forward:每物体 9 盏(1 主 + 8 附加);每相机附加光桌面 256、手机 32、OpenGL ES 3.0 及更早 16。
- Forward+ 和 Deferred:每物体不限。Forward+ 没有逐顶点光、主光关不掉、每物体上限设置无效。Deferred 在手机上「性能影响大」且没有 MSAA。文档推荐手机用 Forward。
- 逐顶点的附加光只在 Forward 下有。

阴影:

- 级联 1 到 4,只给主光。没有面光阴影。
- 软阴影档:Low 是 4 次采样(「手机平衡」),Medium 是 5×5 tent(默认),High 是 7×7 tent。Unity 6 起可以逐灯覆盖。
- 文档例子:把 Max Distance 从 40 砍到 10,1024 的阴影图在近处比 2048 还清楚(级联 1)。电子书:风格化小场景里阴影图超过 1024 反而「太锐」;小场景级联数 1 最好。
- 文档明确认可「低分辨率 + 软阴影」当成一种美术手法,1024 软影和 4096 硬影观感相当。
- 附加光阴影图集最多装 16 张,点光一盏占 6 张。
- Screen Space Shadows feature 观感不变,但强制一次深度预通道,对手机的分块渲染 GPU 不利。

光照图:

- 默认:Progressive CPU、最大反弹 2、边距 2 像素、最大 1024、Directional 模式、带遮蔽。
- Directional 光照图占约两倍显存。Lightmap Resolution 翻倍,像素数变四倍。室外间接采样 128 左右常常够。
- Arm 的建议:Lightmap Resolution 从每单位 5 到 10 像素起步。
- UV:光照图 UV 在第二套(uv2),必须在 0..1 内、面不重叠、岛之间至少隔 2 个完整像素。用 UV Overlap 绘制模式查(红色像素)。

APV:

- 每块 64 个探针,默认间距 1 / 3 / 9 / 27 m,每像素采最近的 8 个探针。
- 没找到任何手机上的性能或内存数字。要用先在目标机上量。

其它:

- Rendering Layers 用于让某盏灯只照某些物体,Forward 下对灯的代价「可忽略」。
- 文档的手机配置建议:关 Depth Priming;附加光关掉或逐顶点;软阴影关掉或降档。

## 三、同类游戏怎么选的

- VALORANT:场景只用离线烘的光照图(存入射光和主方向,只有漫反射);角色吃一盏风格化的方向光加最近的间接光样本并按区域钳制;可玩空间里没有动态投影。
- Survival Kids(Unity 6 URP,Forward):一个太阳;为了能改光的颜色和强度没用光照图,用探针加更重的遮蔽补;从自写探针系统换到了 APV;影子是四分之一分辨率的屏幕空间通道,三种阴影色之间混;后处理只留色调映射、bloom、调色。
- Galactic Colonies(俯视手机游戏,较老的 Unity):每个模块化建筑 prefab 在专门的烘焙场景里烘,光照图、第二套 UV、缩放偏移存进 prefab;每个生态一张共用光照图;假高光用写死的太阳方向;假影子网格。

## 四、烘焙流程和坑

流程:

1. 静态物体勾 Contribute GI;大面选 Receive GI = Lightmaps,小物件和自发光网格选 Light Probes(省图集)。
2. 灯设成 Baked 或 Mixed,选场景的 Lighting Mode。
3. 先用低分辨率和 GPU 烘焙器迭代,定了再提高。
4. 用每个 renderer 的 Scale In Lightmap 给看不到的、平光的、很小的物体少分像素。俯视游戏里朝下和背对镜头的面也算。
5. Generate Lighting。

坑:

- 自写 shader 烘不出东西:先查 `LIGHTMAP_ON` 关键字和 Meta pass。
- 烘焙光没有高光。
- 过滤可能让物体相接处的接触影断开,电子书建议换 A-Trous 滤波。
- prefab 化或运行时生成的静态物体:光照图索引和缩放偏移存在场景的光照数据里,不在 prefab 里。老做法是烘的时候记下 `lightmapIndex` / `lightmapScaleOffset`,实例化后重新赋值,并且这类 prefab 不开 Batching Static(静态合批会改 UV)。这条只有论坛级别的旧资料,Unity 6 上没验证,用之前上真机试。
- 探针组按物体包围盒中心采一次,大物体和多部件物体会出现不连续,用共用的 Anchor Override 修。稀疏的探针会让亮度穿过暗处的缝。
- 叠加加载场景后探针不会自动重新四面体化,加载完调一次 `LightProbes.Tetrahedralize()`。
- APV 是烘好的固定网格。运行时生成的建筑能逐像素吃到 APV 的光,但它自己不挡光、不反弹;生成在烘焙时是空地的位置,采到的是「露天」的探针。〔推〕
- APV 漏光按这个顺序修:加厚墙 → Probe Volumes Options 的各个 bias 和 Leak Reduction Mode → 用 rendering layer 把室内外网格分开 → Dilation 和 Virtual Offset → Probe Adjustment Volume 把探针标为无效。

## 五、手机上的软阴影配方

有出处的设置:

- 只让太阳一盏灯投影,附加光的 Cast Shadows 关掉。
- Max Distance 设成刚好盖住镜头能看到的范围;这个距离小的时候级联数用 1。
- 主光阴影图 1024(高档 2048),开软阴影;低中档用 Low(4 次采样),高档用 Medium。过滤在分块渲染 GPU 上贵,要在真机上量。
- 减少投影物:小物件关 Cast Shadows,复杂的楼和车用简化的「只投影」代理网格。
- 逐灯调 Depth Bias 和 Normal Bias;太大影子会和物体脱开。
- 手机上不用 Screen Space Shadows feature。

补充(推断):

- 俯视固定镜头时,Max Distance 几乎可以贴着可见地面范围设,这正是 1024 单级联够用的原因。
- 静态楼的影子可以烘(Shadowmask 或 Subtractive,软硬由 Baked Shadow Angle 定,运行时免费,但不会动),也可以留实时(和动态物体的影子完全一致)。
- 低档机上角色和车用 blob 面片影。
- 低分辨率加软阴影会藏住锯齿,代价是细东西(杆、线、招牌)的影子会丢,宽滤波在镜头移动时会闪。

## 没读到、待补

Arm「Real-time 3D Art Best Practices: Lighting」原文(页面空壳);URP light cookie 专页(404);环境光 Gradient / Color 模式的专页;blob 影、加色面片霓虹光晕、三色环境光在 URP 里的具体实现没找到专门资料。
