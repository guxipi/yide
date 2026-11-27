# 06 Blender 建模和表面:倒角、加权法线、套件、trim、贴图密度、顶点色、导出

来源标记:〔读〕〔测〕〔推〕同 01。主要来源:本机 Blender 5.1 离线手册和 API 文档(`C:\blender_mcp\mcp\blmcp\data\`)、Blender 5.1 自带 FBX 导出器源码(`F:\Apps\5.1\scripts\addons_core\io_scene_fbx\export_fbx_bin.py`)、Blender 4.1 发布说明、Joel Burgess 的 GDC 2013 讲稿全文(Skyrim 模块化关卡)、Beyond Extent 的 trim sheet 和 texel density 两篇、Alex Nevarez 的模块化寺庙拆解、Android 开发者站转载的 Arm 几何和贴图两篇、Polycount wiki、Unity 6000.3 手册的模型导入页。80.lv、Matt Cane、Unity 手册这几处是抓取工具转出的摘要加短引,可信度比本机文件低一档。造型语言(敦实、宽倒角、粗附件)在 er-blender `references/00-造型与笔触标准.md`,这页只讲技术。

## 一、倒角

- Bevel 修改器的 Width Type 决定 Width 怎么解释:Offset 是新边到原边的距离,Width 是两条新边之间的距离,Depth 是倒角面到原边的垂直距离,Percent 按相邻边长度的百分比,Absolute 沿相邻边量。脚本里统一用一种,别混。〔读手册〕
- Limit Method:Angle 只倒锐边;Weight 按 `bevel_weight_edge` 属性,0 不倒;Vertex Group 要一条边两个顶点都在组里。脚本建模想精确控制哪条边倒、倒多宽,用 Weight。〔读〕
- Clamp Overlap 防倒角越过相邻面;Loop Slide 关掉宽度更均匀。Miter 管两条倒角边成角相遇处(Sharp / Patch / Arc)。〔读〕
- Harden Normals:不加几何,把倒角面的法线调成和两侧大面一致,大面保持平、过渡全压在倒角面上;没有自定义法线属性时会自动建 `custom_normal`。〔读〕
- 一段倒角加 Harden Normals,轮廓上是一个 45 度切角,靠法线渐变看起来圆;多段倒角轮廓真的圆,面数按段数涨。俯视镜头里读得到的是那条明暗过渡,轮廓圆不圆只有大弧(车顶、楼的大圆角)才看得出,所以默认一段,大弧才多段。〔推〕
- 倒角宽度相对物体尺寸取多少,没找到任何一手数字。有依据的判法是按屏幕像素:Arm 的说法是某一维小于 10 像素又拉得很长的三角形比别的三角形贵,举的例子正是「柱子上的倒角从远处看」;手机屏小,形状可以夸大。所以倒角宽度按「游戏镜头下这条面在屏幕上有几像素」定,窄于几像素的倒角既看不见又变成细长三角形。我们的宽倒角语言落在安全一侧。〔读 Arm;判法推〕

## 二、加权法线和 4.1 之后的平滑

- Weighted Normal 修改器改的是自定义法线。Weighting Mode:Face Area 按面积,Corner Angle 按顶点处的角(Blender 默认合成顶点法线的方法),Face Area and Angle 两者相乘。Weight 50 是均匀,大于 50 偏向大面。Keep Sharp 保留锐边。Face Influence 用面强度(weak / medium / strong),一个顶点上只听强度最高的面。〔读〕
- 手册写明的搭配:Bevel 在前、Weighted Normal 在后,Bevel 的 Face Strength 设 Affected 或 All,Weighted Normal 勾 Face Influence。结果是原来的大面记为 Strong、倒角面 Medium、角面 Weak,大面的顶点法线等于它自己的面法线。〔读;效果链推〕
- Harden Normals 和 Weighted Normal 做的是同一类事,二选一:只有倒角用 Harden Normals;倒角之外还有别的小面要压平用 Weighted Normal。两者同时开会怎样手册没写。〔推〕
- Blender 4.1 起没有 Auto Smooth:`Mesh.use_auto_smooth`、`auto_smooth_angle`、`calc_normals_split` 都被移除,旧脚本会报错或被 try/except 吞掉导致后面的法线步骤没跑。现在网格的基础状态等同旧版「开、180 度」;按角度平滑用 Smooth by Angle 修改器(`bpy.ops.object.shade_auto_smooth(angle=…)`)或 `Mesh.set_sharp_from_angle(angle=…)` 直接写 `sharp_edge` 属性。自定义法线用 `normals_split_custom_set` 写,存在 Face Corner 域的 `custom_normal` 属性里,`Mesh.has_custom_normals` 可查。〔读 4.1 发布说明、API 5.1〕
- 哪些操作会丢自定义法线,手册没列。稳妥顺序:所有改拓扑的操作做完,再写法线,导出前断言 `has_custom_normals`。〔推〕
- Bevel 着色节点只在 Cycles 有,只改着色不改几何,贵(手册说能慢 20%),用途是烘一张带圆角的法线图。我们大部分件不带法线贴图,用真实倒角加上面的法线处理更直接。〔读;取舍推〕

## 三、模块化套件(Burgess 讲稿)

- 先定全局尺寸再做件:统一门框、最窄通行宽度、能走的坡度、掩体高度。件占的格子范围叫 footprint,子套件的 footprint 必须互为整数倍(512 和 256 永远对得上,384 迟早出缝)。吸附步长取 footprint 的一半,步长大,没对齐的缝一眼看得出。〔读〕
- 件永远在 footprint 以内,只有和别的件相接处才贴到边;不要把东西做到边上或做出去(两条相邻走廊的墙会共面)。竖向同理,预先定好楼板厚度。〔读〕
- pivot 放在地面平面上居中,灰盒阶段就定;后面改 pivot 要手工更新几百个实例。〔读〕
- 不用补丁件救对不上的缝:对不上通常是某个件超出了 footprint,改那个件。拿到新件先做压力测试:绕一圈回到自身、上下叠放、拿走廊件拼房间。〔读〕
- 重复感:玩家对重复的小物件比对重复的大结构敏感得多;同功能同 footprint 的外观变体用 01 / 02 / 03 后缀;鼓励不同套件混搭;模块件上不放太大、太独特的细节(会被重复很多次)。〔读 Burgess、Nevarez〕
- 用到城市线:米制,先定开间、人行道宽、车道宽,墙段、转角、店面、屋顶沿的 footprint 互为整数倍(比如 4 m 和 2 m,不要出现 3 m)。〔推〕

## 四、trim sheet

- 定义:沿 U 或 V 一个方向平铺的贴图,切成若干条,模型的 UV 壳拉直后对到条上,UV 可以重叠、可以伸出 0–1。代价是条上不能有显眼的独特细节。好处是多个件共用一套贴图。〔读 Beyond Extent〕
- 布局:条高用 2 的幂步长(1024 的图取 512 / 256 / 128 / 64 …),同高的条可以互换;两张 trim 用同一布局就能不改 UV 直接换材质。先看场景里要贴的最大元素有多宽,再分条。〔读〕
- 「倒角法线条」(Sunset Overdrive 的 Ultimate Trim,硬边两侧 UV 对到一条预烘的 45 度法线条上):演讲正文没读到,只读到 GDC 简介。它依赖法线贴图,我们走顶点色、无法线贴图时用不上。〔简介读;其余没读到〕
- 风格化项目的两条路:Nevarez 用 4 张 trim sheet 装下一座寺庙的全部材质;80.lv 的卡通村庄不用 trim,5 张灰度平铺贴图加顶点色上色、顶点 alpha 混贴图,覆盖 95% 的画面。城市楼体要上图形细节(窗框条、檐口线、招牌边)时,一张小 trim 配顶点色调色比每栋楼一张独立贴图省。〔读;后一句推〕

## 五、贴图密度

- 定义:每米(或每厘米)多少像素,全游戏统一。算法:贴图边长像素 × UV 壳在 UV 空间的边长占比 ÷ 表面真实长度。4 m 的面铺满 4096 的图是 1024 px/m。〔定义读;公式推,和 Nevarez 的例子对得上〕
- 取值:Matt Cane 文里的参考是俯视游戏 512 px/m、第三人称 1024、第一人称 2048。手机游戏的取值没找到任何一手数字。实际做法是量游戏镜头下 1 m 在屏幕上占多少像素(我们的镜头在 40 m 距离约 130 px/m,见 04 第六节的机位),贴图密度略高于它就够。〔读;后一句推加测〕
- 一致性比绝对值重要:玩家看得出「这个糊、旁边那个锐」;trim 上允许上下浮动 25% 左右;只有玩家会贴近看的东西才有意偏高。〔读〕

## 六、顶点色

- Color Attribute 的域:Vertex 每顶点一个值;Face Corner 每个面拐角一个值,能做颜色硬边,代价是硬边处顶点在引擎里被拆开。类型:Color 是 32 位浮点、线性空间;Byte Color 是 8 位、按 sRGB 存。Python 里每个元素同时有 `color`(线性)和 `color_srgb` 两个读法。〔读手册、API〕
- FBX 导出:5.1 的导出器把每一层颜色属性都写出,四种域和类型的组合都行,一律展开成逐面拐角。`colors_type` 选 'SRGB'(默认)写 `color_srgb`,选 'LINEAR' 写 `color`。`prioritize_active_color` 保证激活层排第一(有些软件只认第一层)。〔读源码〕
- Unity 读进来是什么格式、做不做色彩空间转换,手册没写。推断是 8 位存、数值原样不转换;那么默认 'SRGB' 导出时 shader 拿到的是 sRGB 编码值,在 Linear 工程里当颜色用要自己转线性。存遮罩、遮蔽这类非颜色数据的通道要保证全程不被转换。动之前做一次实测:Blender 里涂 sRGB 0.5 灰,两种 `colors_type` 各导一次,Unity 里打印 `mesh.colors32`。〔推,待测〕
- 分通道的常见用法:RGB 乘在固有色上做色彩变化,或三个通道各当一张单色遮罩(贴图混合权重、风摆权重、遮蔽),A 是第四个通道。遮蔽存顶点色的限制见 03。〔读 Polycount;用法推〕

## 七、导出 Unity

- Blender 侧(`bpy.ops.export_scene.fbx`,参数都显式传,手册和 API 对 Scale 默认值的说法互相矛盾):`use_mesh_modifiers=True`(Bevel、Weighted Normal、Smooth by Angle 都是修改器,不勾就不进 FBX);`mesh_smooth_type='OFF'`(只导法线,目标认自定义法线时用这个);`axis_forward='-Z'`、`axis_up='Y'`;`colors_type` 按上一节定;`use_tspace` 只在要法线贴图时开,而且网格里有一个超过 4 边的面就整个网格跳过切线。自定义法线通过 `corner_normals` 自动带出,不需要额外开关。〔读 API、源码〕
- 缩放:`apply_scale_options` 默认 All Local 会把 100 倍的单位缩放写到物体变换上;选 FBX Units Scale 配合 Unity 的 Convert Units,物体 scale 才是干净的 1。这段因果是按选项说明推的,换配置后导一个 1 m 立方体量一次。〔推〕
- Unity 侧:Normals 保持 Import(设成 Calculate 会按角度重算,文件里的法线作废);Tangents 在 Normals 为 Import 时默认从文件读,文件没有切线就配不了法线贴图;超过四边的面无论 Keep Quads 怎么设都会被 Unity 三角化,切法由 Unity 决定;Mesh Compression 会量化法线和顶点色,做过加权法线的件先用 Off 验;Index Format 保持 16 位,单网格不超过 65,535 顶点。〔读 Unity 手册;压缩那句推〕
- 大平面开窗洞会产生大 n-gon。在 Blender 里自己三角化(Triangulate 修改器放在 Weighted Normal 之前),Blender 里看到的着色才和 Unity 一致,同时查有没有细长三角形。导出器的 `use_triangles` 会不会保住自定义法线,源码看不出来,没验证。〔推〕
- 自定义法线进了 Unity 没了,按这个顺序查:Unity 的 Normals 是不是 Import;导出勾没勾 Apply Modifiers;写法线之后有没有又改拓扑;脚本里有没有残留的 `use_auto_smooth`;Mesh Compression。〔推〕

## 没读到、待补

低模倒角宽度的业界取值;手机游戏的贴图密度取值;Unity 导入 FBX 顶点色的存储格式和色彩空间处理(要实测);Ultimate Trim 演讲正文和 45 度法线条的布局;Tim Simpson 的 trim sheet 视频教程(视频,没有文字版);`use_triangles` 是否保住自定义法线;静态合批对第二套 UV 的处理。
