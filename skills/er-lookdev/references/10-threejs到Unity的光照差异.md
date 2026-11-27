# 10 three.js 和 Unity URP 的光照模型差异

来源标记:〔读〕〔测〕〔推〕同 01。主要来源是两边的源码:three.js 仓库 r187(对照了 r150 到 r188dev 的若干版本)的 shader chunk、`WebGLLights.js`、`ColorManagement.js`、`GLTFExporter.js`,three.js 手册的 color-management 页、迁移指南、论坛的三个帖子;Unity Graphics 仓库 `6000.3/staging` 的 URP 17.3 `Lighting.hlsl`、`RealtimeLights.hlsl`、`Shadows.hlsl`、`Bloom.shader`、`Color.hlsl`;glTF 规范和 KHR_lights_punctual;glTFast 和 UnityGLTF 的灯光导入代码。换算系数都是把两边公式放在一起推的,没有在两边各渲一张图对过,搬之前拿一个白盒场景并排验一次。

城市线先在 three.js 造景再搬 Unity。同一份颜色和灯,两边出来不一样,差在下面这几处。

## 最要紧的三条

1. three.js 所有灯的漫反射都多除一个 π,URP 不除。同一盏强度 1 的方向光照白色 Lambert 面,three.js 输出线性 0.318(屏幕上约 153),URP 输出 1。灯强度从 three.js 搬到 URP 要除以 π。环境贴图(`scene.environment`)不用除。
2. three.js 的「线性雾」`Fog` 实际是 smoothstep 曲线;而且直接画到画布时,雾是在转成 sRGB 之后才混的。两点都和 Unity 不同。
3. three.js 的 Neutral 色调映射(Khronos PBR Neutral)和 Unity 的 Neutral 不是同一条曲线。

## 一、颜色

- three.js 从 r152 起默认开颜色管理,工作空间是线性 sRGB,`outputColorSpace` 默认 sRGB。`Color.setHex`、CSS 字符串按 sRGB 解释并转成线性;`setRGB(r,g,b)` 默认是线性,不转。〔读〕
- Unity 材质的 Color 属性也是 sRGB 输入、shader 里线性。所以十六进制颜色两边数值照抄;但 three.js 里 `setRGB(0.5,0.5,0.5)` 是线性 0.5,Unity 面板上的 0.5 是 sRGB 0.5(线性 0.214),这两个不是一回事。〔前半读;后半推〕
- 顶点色:three.js 手册写明顶点色按线性工作空间存,着色器里原样相乘,不做转换;glTF 规范对 COLOR_0 也是这个规定。把 sRGB 的数直接写进顶点色属性,three.js 会当线性用,颜色偏亮偏灰。Unity 这边顶点色不转换没读到官方原文,是推断(06 第六节有实测办法)。〔读;Unity 侧推〕
- 贴图:颜色贴图标 `SRGBColorSpace` 对应 Unity 勾 sRGB;法线、遮蔽、色带图保持 `NoColorSpace` 对应不勾。〔读〕

## 二、灯的强度

- 历史:r155 起默认不再是旧的灯光模式(旧模式把所有灯色乘 π),r165 彻底移除。旧教程里的强度数值在新版本里要乘 π 才一样亮。〔读源码和迁移指南〕
- 源码:three.js 的 `BRDF_Lambert` 返回 `固有色 / π`,Lambert、Phong、Toon、Standard 的漫反射项都乘它,灯的颜色就是颜色乘强度,没有补 π。URP 的 `LightingLambert` 是 `lightColor * NdotL`,不除。〔读〕
- 换算:Unity 灯强度 = three.js 灯强度 ÷ π,方向光、点光、聚光都一样。〔推〕
- 点光衰减两边同式:主项 1/d²,窗函数都是 (1 − (d/范围)⁴)²。three.js 的 `decay = 2`、`distance = R` 对应 URP 的 `range = R`。three.js 的 `distance = 0`(不截断)在 URP 里没有对应,`decay` 不是 2 也没有对应。聚光的锥角曲线两边不同,精确换算没查到。〔公式读;对应推〕
- 单位:three.js 的点光和聚光是坎德拉,方向光、环境光、半球光官方说不用国际单位。〔读〕

## 三、环境光

- AmbientLight:颜色乘强度,再乘固有色除以 π。搬到 Unity 的 Color 模式:线性值除以 π。〔读;换算推〕
- HemisphereLight:`权重 = 0.5 * dot(法线, 灯方向) + 0.5`,在地色和天色之间线性插值,再乘固有色除以 π。法线水平时天地各半。〔读〕
- Unity 的 Gradient 三色模式不是这个公式。它被投影成球谐,过渡被抹平:实测地面色在法线水平的墙上只占约 11%,法线朝正下方也只占约 54%(04 第六节)。所以把 HemisphereLight 的两色填进 Unity 的三色面板对不上。要对上就在自己的 shader 里不采球谐,直接写 `lerp(地色, 天色, 0.5 * normalWS.y + 0.5)`,两个颜色填 three.js 的值除以 π(URP 会把 `unity_AmbientSky`、`unity_AmbientGround` 两个全局量传给 shader)。〔测 Unity 侧;做法推〕
- `scene.environment`:取环境贴图时乘了 π,后面再除 π,抵消,亮度 1 的环境照白面输出 1。r187 里 Standard、Lambert、Phong 取这一项,Toon 不取。〔读〕
- LightProbe 在 r188 弃用。〔读〕

## 四、aoMap 和 lightMap

- aoMap 只乘间接漫反射(环境光、半球光、探针、lightMap、环境贴图的漫反射)和间接高光,不碰直接光;只读 R 通道;强度是在 1 和采样值之间插值。场景只有直接光时 aoMap 没有任何效果。这和 URP Lit 的遮蔽图规则一样(03 第一节),所以两边都有「遮蔽只压环境光、主光强时看不见」的问题,要让它影响主光都得自己写。〔读〕
- lightMap 加进间接漫反射,之后乘固有色除以 π。同一张图要两边一样亮,three.js 的 `lightMapIntensity` 设成 π。〔读;换算推〕
- UV 通道:r151 起不再强制第二套 UV,用 `texture.channel` 指定(0 是 `uv`,1 是 `uv1`)。〔读〕
- glTF 带不了 lightMap(导出器里没有这个字段)。绕法:借 emissive 槽带出去、加载后挪到 `.lightMap`(Don McCurdy 的建议);或者模型带第二套 UV,贴图单独加载后赋值并设 `channel = 1`。〔前一种读;后一种推〕
- r188 起 Standard 的 aoMap 改成多次反弹公式,亮色表面的遮蔽变弱(和 03 实测的副作用是同一件事)。three.js 那边要锁版本。〔读〕

## 五、材质

- MeshToonMaterial 最接近我们自写的 half-lambert 分带:色带坐标是 `N·L * 0.5 + 0.5`,去采 gradientMap 的 R 通道(要设 NearestFilter、NoColorSpace)。不给 gradientMap 时默认两段,0.7 和 1.0,分界在 N·L = 0.4,背光面仍有 0.7 倍的灯光。没有高光项,不取环境贴图。〔读〕
- 和我们的差别:多一个 1/π;色带是灰度的,做不了带色阴影,暗部颜色只能靠环境光和半球光染。真要带色色带得用 ShaderMaterial 或 `onBeforeCompile`。〔推〕
- MeshBasicMaterial 不受灯影响但支持 lightMap 和 aoMap;MeshLambertMaterial 从 r144 起逐像素;MeshMatcapMaterial 不受灯影响、不接收阴影。〔读〕

## 六、阴影

- 语义两边一致:影子里直接光(漫反射加高光)整项归零,只剩间接光。阴影强度也是同一个公式(three.js 的 `shadow.intensity`,r166 起;URP 的 Shadow Strength)。〔读〕
- three.js 的方向光阴影相机是一个手动设范围的正交相机(默认 ±5、512×512),核心没有级联,范围之外算受光、没有距离淡出。URP 有级联、Max Distance 和淡出。〔读〕
- 过滤:r182 起 PCF 改成 5 点圆盘加屏幕噪点,PCFSoft 弃用并回退到 PCF;URP 是 4 次采样或 5×5、7×7 的 tent。软硬只能并排目测调,等价参数没查到。bias 的单位两边不同,数值不能照抄。〔读;后一句推〕

## 七、色调映射和后处理

- three.js 默认不做色调映射。用 EffectComposer 时(r155 起)色调映射和 sRGB 转换要挪到 OutputPass。〔读〕
- 两边的 Neutral 按公式算灰阶(输入 → three.js / Unity):0.18 → 0.140 / 0.182;0.5 → 0.460 / 0.416;1.0 → 0.869 / 0.631。three.js 的在 0.76 以下基本直通,Unity 的整段都在压。要对齐只能两边都不开,或者在 Unity 里自己实现同一条曲线。〔公式读;数是算的〕
- bloom:three.js 的 UnrealBloomPass 按线性亮度硬切阈值、过阈值的像素保留原色,强度有固定的 3 倍系数;URP 的阈值是 gamma 空间的值、取最大通道、有软膝、减掉阈值(05、07)。三个参数的数值换算没查到,并排调。〔读〕

## 八、雾

- three.js 的 `Fog(near, far)`:`smoothstep(near, far, 深度)`。设 t 是归一化距离,雾量是 t²(3 − 2t),Unity 的线性雾是 t;t = 0.25 时是 0.156 对 0.25。要对上就在自己的 shader 里用 smoothstep。〔读;对比推〕
- `FogExp2(density)` 和 Unity 的 Exponential Squared 同式,density 照抄。three.js 没有一次指数雾。〔推,由两边公式〕
- 混合的位置:three.js 直接画到画布时,雾排在色调映射和 sRGB 编码之后,等于在 sRGB 编码值上混;走 EffectComposer 时在线性里混。Unity 在线性里混、后处理之前。所以 three.js 这边走 EffectComposer 加 OutputPass 才和 Unity 同序。〔读;后一句推〕

## 九、导出和搬运

- GLTFExporter 能带:四套 UV、顶点色、遮蔽图和它的强度、方向光点光聚光(强度写原值)。带不了:lightMap、ShaderMaterial、Toon / Lambert / Phong 的专有属性(色带图)、环境光和半球光、阴影设置、雾、色调映射。〔读〕
- 进 Unity:glTFast 在 URP 下灯强度原样用(乘 `LightIntensityFactor`,默认 1),所以 three.js 导出的灯进 URP 会比 three.js 里亮 π 倍,把这个系数设成 1/π。坐标系由导入器处理,glTFast 现在翻的是 X 轴,不是 Z。〔代码读;结论推〕

## 十、对照表

| three.js(r187) | Unity 6000.3 / URP 17.3 | 换算 |
|---|---|---|
| 十六进制、CSS 颜色 | 材质 Color 属性 | 数值照抄 |
| `Color.setRGB`(线性) | Color 属性 | 先转 sRGB 再填 |
| 顶点色(线性,原样乘) | 顶点色 | shader 里不再转换(Unity 侧待测) |
| DirectionalLight 强度 | 方向光 intensity | ÷ π |
| PointLight 强度、`decay 2`、`distance R` | 点光 intensity、range | ÷ π;range = R |
| AmbientLight | 环境光 Color 模式 | 线性值 ÷ π |
| HemisphereLight 天、地 | 自写 `lerp(地, 天, 0.5*N.y+0.5)` | 各 ÷ π;Unity 的三色面板对不上 |
| `scene.environment` | Skybox 环境光 | 不除 π |
| aoMap | 遮蔽图 | 语义一致,都只压间接光 |
| lightMap × `lightMapIntensity` | 光照图 | 强度设 π 时一致 |
| MeshToon 加 gradientMap | half-lambert 色带 | 坐标一致;灯强 ÷ π;带色阴影自写 |
| 阴影、`shadow.intensity` | 阴影、Shadow Strength | 语义和公式一致 |
| PCF 的 radius、bias | 软阴影档、bias | 没查到 |
| `NoToneMapping` | Tonemapping None | 一致 |
| `NeutralToneMapping` | Neutral | 不是同一条曲线 |
| `Fog` | 线性雾 | 不等价,自写 smoothstep |
| `FogExp2` | Exponential Squared | density 照抄 |
| UnrealBloomPass | Bloom | 没查到 |
| glTF 灯强度 | glTFast 的 `LightIntensityFactor` | 设 1/π |

## 没读到、待补

Unity Gradient 三色投影成球谐的公式(引擎不公开,只有 04 的实测权重);Unity 顶点色不做颜色空间转换的官方原文;聚光锥角、阴影过滤和 bias、bloom 三个参数的换算;ACES 两边是否一致;UnityGLTF 的坐标转换和方向光强度;three.js 的 CSM 示例内容。全页的换算系数没有做过两边并排渲染的验证。
