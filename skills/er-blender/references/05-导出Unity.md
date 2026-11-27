# 05 导出到 Unity

导出这一步出的错,往往进了 Unity 才看得出来:武器头朝 -Z、挂点算错、霰弹枪被非等比缩放、Blender 里调好的法线被 Unity 重算冲掉。这一页把导出参数和导出后的回读核对固定下来。

## 导出前

1. 应用所有修改器;数据级合并成一个 mesh(静态件);原点放底部中心(武器例外,见挂点)。
2. 变换应用干净:scale = 1、无旋转;**不要非等比缩放**。尺寸要改就在 Blender 里按米制等比改,写进交接说明。
3. 名字没有 `.001` 后缀;材质数和贴图数符合交付格式。

## FBX 参数

`add_leaf_bones=False`;静态件不带动画;有自定义法线时勾上导出法线。隐藏物体会被静默丢掉,导出前确认要导的都可见。多材质 mesh 会被拆成多个,静态道具尽量单材质。Blender 默认 Z-up 导出,Unity 导入后轴向以回读核对为准。

## 法线:Blender 里调了法线,Unity 就要 Import

在 Blender 里做了法线处理(加权法线、Data Transfer 投法线)的件,Unity ModelImporter 的 normals 必须是 **Import**;用 Calculate 会把 Blender 的结果冲掉。反过来,没进 Blender、只想在 Unity 里修"肉感"的件,才用 Calculate + smoothing angle(gaoguang-3d 的零成本层)。两条路别混。

## 武器挂点:用命名 Empty,不猜

武器在 Blender 里放命名 Empty(`Grip_R`、`Grip_L`、`Muzzle`、`Head`),随 FBX 导出,到 Unity 就是子 Transform,挂载按名字对齐手骨。按"最长轴 + grip_frac"猜握点、看图定头端朝向的做法,武器进 Unity 后会头朝 -Z,只能靠探针兜底。Empty 的朝向约定(哪个轴指向头端)和 Unity 侧按名挂载的代码要和工程侧对齐,先查工程里现在怎么挂。

## 导出后回读

导出后在空场景(`--factory-startup`)把 FBX 导回来,用 `_er_bl.inspect` 核对三角数、尺寸、轴向、Empty 是否都在、材质数,和导出前记下的数一致才算过。

## 交给 Unity

落 `Assets/Art/3DModelsfromGu/<Name>/`,贴图现在只给 BaseColor(现行 LabLit 只吃 BaseMap,法线 / ORM 不进);要试法线图、ORM、新 shader 这类路线,和 LabLit 版同机位实拍对比后给勾哥看。材质、真光照验证走 gaoguang-3d;武器 shader 同样是 LabLit。描边一律关。
