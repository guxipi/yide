# 草顶崖壁(GrassTopCliff)· 2026-11-14 勾哥过

勾哥原话:「非常好，除了零碎的叶片，其它的进无伤复用，叫草顶崖壁」。

一句话:给几级台地的平面轮廓,出「一整块阶梯岩体 + 每级压一块带圆肩垂边的草盖」。山是一个整体,草是一个整体,草压在山上。

## 已批 / 没批

| 部分 | 状态 |
|---|---|
| 岩体(每面墙一个素平面)+ 草盖(顶面、圆肩、垂边、宽弧下沿、悬出墙面)+ 两个材质的设法 | **已批,套件默认就是这些** |
| 垂边下沿的叶片(成组边缘叶 + 少量探出的亮叶) | **没批**。11-14「这些叶片有点过大了」,已缩到约 0.55 倍,缩小后勾哥还没单独表态。`Params.leaves` 默认 false,要用自己开,并且单独给勾哥看 |
| 岩壁上的横向岩层线 | **否决,不在套件里**。11-14 试了三版(贴墙方块 / 探出薄层靠投影 / 斜切带靠朝向),勾哥:「把这些横向的纹路删掉，太丑了，横纹不要入复用库」。代码已整段删掉,别再加回来 |

## 要模仿的外形(自然语言)

- **岩体**:平面是几条长直边加 45° 切角,长边上可以有一处 0.6–0.7 m 的 45° 折向;一级一级往后退,每级露出的平台进深和墙高差不多。每面墙就是一个平面,下沿一刀切到下一级平台或地面,墙上什么都不加。
- **草盖**:一块有厚度的垫子。顶面是平的,和地面是同一种草;到崖沿圆着肩翻下去(肩是 0.28 × 0.45 m 的四分之一椭圆),往下垂 0.85 m 左右,再收回墙面。整块草盖悬出墙面 0.3 m。转角处草盖是圆着拐的,岩体的角是硬的。
- **垂边下沿**:大部分是平静的,偶尔鼓出一两个 1.6–2.8 m 宽、深 0.15–0.3 m 的宽弧。不是锯齿,不是等间距。
- **明暗**:顶面亮,垂边背着太阳变暗,垂边底下在墙上压一条软的暗带。这三样都是灯光给的,没有一样是画的。
- **不该出现的**:粉灰色的露边、贴在墙上的平面色带、流到半墙的草舌、墙上孤立的绿块、等间距锯齿、被穿插切碎的墙面。这些是 11-14 上午被勾哥骂「稀碎」的旧崖的毛病。
- **红线**:草盖不许比 mo.co 更厚更软。第一版肩 0.42 × 0.75 m、垂边 1.26 m 被判「充气软垫」,收到现在的值才过。往大调之前先想清楚。

## 参考

- 形和结构:mo.co,登记表「台地崖壁(层序、草皮垂盖、砂顶包沿)」行 —— `013 美术/丛林Lab/观察/崖壁/frames/cl_1-28.png` 裁 1250,410,2050,1000,`moco_11-01_orig.png` 裁 560,600,1500,900。
- 颜色:不取 mo.co。基地那座崖取 Boom Beach(奶油色砂岩);别处用就传那个场景自己的草色和岩色。

## 怎么用

生成器是单文件 `GrassTopCliffKit.cs`(本目录有一份,SHA 见 `kit.json`),放进任意 Unity 工程的 Editor 程序集就能用。只依赖工程里有 `Lab/LabLit` shader。

```csharp
using Lab.Kits.Editor;

var tiers = new List<GrassTopCliffKit.Tier>
{
    new GrassTopCliffKit.Tier { outline = lowerXZ, baseY = 0f,   topY = 4.3f, seed = 11 },
    new GrassTopCliffKit.Tier { outline = upperXZ, baseY = 4.3f, topY = 7.6f, seed = 29 },   // 上层轮廓要完全落在下层里面
};
var p = new GrassTopCliffKit.Params
{
    grass = groundGrassVertexColourLinear,   // 和地面草网格同一个顶点色(线性)
    rock  = rockVertexColourLinear,
    wallSeen = n => n.y < 0.35f,             // 游戏相机看得见哪些墙(n = 墙的外法线 XZ);默认是相机沿 +z 看
};
var m = GrassTopCliffKit.Make(tiers, p, "MyCliff");
m.rock = GrassTopCliffKit.KeepMesh(m.rock, dir + "/MyCliff_Rock.asset");
m.turf = GrassTopCliffKit.KeepMesh(m.turf, dir + "/MyCliff_Turf.asset");
var turfMat = GrassTopCliffKit.TurfMaterialAsset(groundGrassMaterial, dir + "/MyCliff_Turf.mat");
var rockMat = GrassTopCliffKit.RockMaterialAsset(dir + "/MyCliff_Rock.mat");
GrassTopCliffKit.Attach(parent, m, rockMat, turfMat, "Cliff");
```

写完 `EditorSceneManager.SaveScene`。崖顶种树、给林带的避让轮廓这些属于各场景自己的布局,不在套件里;`Ccw` / `Inside` / `EdgeDist` 三个小工具是公开的,可以拿来算。

## 几条用的时候必须满足的

1. **草盖材质必须是地面草材质的副本**(`TurfMaterialAsset(地面草材质, 路径)`),只改三个值:`_NormalUp` 0.12、`_ShadowThreshold` 0.10、`_ShadowSoftness` 0.7。这样顶面和地面一模一样,垂边靠真实法线受光变暗。地面草材质原样拿来用的话(`_NormalUp` 0.9),侧面会被照成和顶面一样亮,草盖读不出厚度。
2. **岩体和草盖都要投影、收影**(`Attach` 已经设好)。垂边压在墙上的那条暗带是真投影,关了就没了。
3. **顶点色是线性空间**。这个工程是 Linear,直接填 sRGB 值会发白。
4. **不许往顶点色里画明暗**。唯一的渐变是垂边梢到根 ×(0.92, 0.94, 0.97),那是草自己的颜色。
5. **叶片不投影**(开了叶片时 `Attach` 已设)。基地白天的主光几乎贴着墙面照下来,墙前任何小凸起都会拖出一米多的斜影。
6. `Lab/LabLit` 是两段式:墙面 N·L 只要大于 0 就算全亮。所以朝镜头的墙和顶面一样亮,只有背光的切角面落进暗调。想让墙整体暗一档要改岩色,不要去动阈值(阈值一动,已批的画面就变了)。

## 参数(默认值就是已批的那一版)

| 参数 | 默认 | 是什么 |
|---|---|---|
| `lift` | 0.10 | 草顶高出岩顶 |
| `overhang` | 0.30 | 垂边立面悬出墙面 |
| `shoulderX` / `shoulderY` | 0.28 / 0.45 | 圆肩:向外 / 向下 |
| `drop` | 0.85 | 垂边平均深度(从草顶量) |
| `scallopDrop` | 0.24 | 宽弧额外下垂 |
| `cornerBlend` | 0.45 | 草盖拐角有多圆(法线在转角前后这么长的弧上混合) |
| `stepSeen` / `stepUnseen` | 0.14 / 0.6 | 看得见 / 看不见的边的采样步长 |
| `skirtRoot` | (0.92, 0.94, 0.97) | 垂边梢到根的本色渐变 |
| `leaves` | false | 叶片(没批) |

岩墙从 `baseY − 0.3` 起,到 `topY − 0.45` 止:墙顶必须低于草顶 0.45 m,否则悬出变窄的地方岩壁上沿会从圆肩里戳出来(做的时候真出过,顶面上一个个奶油色梭形洞)。

## 尺度是怎么定的

mo.co 里一级墙约 1.1 个角色身高、垂边约 0.42 个身高。基地没有主角当尺子,取局部单位 Hc = 3 m(约一棵半树高):一级墙 3.3 m。垂边按 0.42 Hc = 1.26 m 做出来太厚,最后定 0.85 m。换场景时先定那个场景的 Hc,墙高按 1.1 Hc 起,垂边从 0.85 m 起试,不要直接按比例放大。

## 面数(基地那座,两级,轮廓各 12 个顶点)

岩体 68 三角,草盖 9,778 三角(绝大部分花在看得见的边的圆肩和垂边上;看不见的边按 0.6 m 采样)。开叶片另加约 3,200。

## 现有实例

- **Extraction 基地背后的山崖**(W1,`Assets/Scripts/Editor/Setup/BaseV3Env/BaseCliffD6.cs`):两级,台顶 4.3 m / 7.6 m。重建:HomeScreen 打开、非 Play,`Editor.Setup.BaseV3Env.BaseV3EnvStep4Builder.Build()` 后存场景。产物 `Assets/Art/Meta/BaseV3Env/Step4/BV3S4_CliffD6_*`。这座崖开着叶片(缩小后的),等勾哥定。

## 维护

改套件 = 同回合更新项目里的 `Assets/Scripts/Editor/Lab/Kits/GrassTopCliffKit.cs`、本目录的那份拷贝、`kit.json`(含 SHA)和本 README;翼德仓 commit + push,项目仓 commit 不 push。改了默认参数就等于改了已批的画面,要重新给勾哥看。
