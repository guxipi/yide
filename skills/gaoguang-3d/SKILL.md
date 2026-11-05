---
name: gaoguang-3d
description: 高光3D — intake/fix pipeline for AI-generated 3D models (Tripo, Meshy, text-to-3D) into Extraction to match its mo.co-style painted toon look (Lab/LabLit material remap + pivot centering + rig/animation + real-lighting verify). Trigger — "高光3D" / "模型太灰暗" / "模型发灰" / "新模型不好看" / "像 mo.co 那样干净鲜亮" / "把XX替换成这个模型" / 新导入的 FBX 看起来灰、暗、塑料感 / pivot 轴心不在模型中间、转身会甩 / 模型有骨架没动画需要配动画. NOT particle/aura/trail/burst/光环拖尾爆开 VFX (→ vfx-production); model intake + look-fix only.
---

# 高光3D — AI 模型进项目的入库与修观感流水线 (Extraction)

**目标水准和验收以 ER 美术规范为准**:vault `01 - 星际拓荒重构/013 美术/ER美术规范.md`(对标 mo.co 游戏内画面的质量和质感;旧的 Archero / Brawl Stars 低模 / KayKit 平色加黑描边口径全部作废)。和本 skill 最相关的结果要求是:3D 世界里看不到黑描边(角色、怪也一样),阴影和暗面不灰黑,看不出硬刻面,饱和度按"地面低、主体高"的预算走。角色长相和头身以 vault `013 美术/角色手册/` 为准。下面写的是一种验证过的做法,不是唯一做法;换别的路线也行,结果过总纲门槛即可。

AI 生成的模型(Tripo 等)直接进项目必灰。原因是固定的三连:**embedded material 是 URP/Lit(PBR)** + **_BaseColor 常为 (0.8,0.8,0.8) 把贴图乘暗 20%**(也有白的,但 PBR 本身就压灰) + **_Smoothness 0.5 塑料高光**。工程里 3D 模型统一用 `Assets/Shaders/Lab/LabLit.shader`(`Lab/LabLit`:NdotL 两阶明暗 + 暗部 tint + rim,没有描边);原 ToonLit 已于 2026-10-30 换成 LabLit。这里的修法 = 换材质 + 对轴心 + 配动画 + 真光照验证,全程 Unity 内,不回 DCC。

## 0. 诊断(动手前必做,别猜)
dump 真值(一次性探针 .cs 放 **Assets 外**,如项目根 `Temp/`,用 `unity command script eval_file` / `script run` 跑,用完删;Coplay `execute_script` 只兜底,兜底时的临时驱动放 `Assets/Editor/CoplayTemp/`、不进 git;要留作工具的代码放正式目录 `Assets/Scripts/Editor/Setup/`):
- 加载 FBX,遍历 `GetComponentsInChildren<Renderer>` 打印每个 sharedMaterial 的 shader 名、`_BaseColor`、`_BaseMap`、`_Smoothness`、`AssetDatabase.GetAssetPath(mat)`。assetPath 指向 .fbx 本身 = embedded 自动材质,就是本 skill 的目标场景。
- **同时 dump rig 与动画**:hierarchy(有无 Armature)、SkinnedMeshRenderer.bones.Length、`LoadAllAssetsAtPath` 里的 AnimationClip 列表。Tripo 模型分两种:带 NLA 动画(科学家:Idle/Walk/Work)和**有骨架但零 clip**(球形机器人:41 bones,无动画)——后者要走第 3 节。
- 同时 dump 当前主角(Hero.prefab 上现在挂的英雄材质)做对照。engineer.mat 是旧 KayKit 角色的材质,不当标杆。
- grep FBX 的 guid 找到所有引用它的 prefab/scene(决定 pivot 修在哪)。
- 素材在云盘时注意:用户给的 `G:\My Drive\...` 路径本机 G: 直接可读(本机挂两个云盘账号,G: 和 H: 都在),别想当然换盘符。

## 1. 修观感:LabLit 材质 + ModelImporter Remap(不要在 prefab 里 override 材质)
1. 在模型同目录建 `<Model>.mat`:shader `Lab/LabLit`,`_BaseMap` = 模型 basecolor 贴图(LabLit 只吃这一张,法线 / ORM 不进)。
2. 参数 10-30 起以 `Assets/Art/3DModelsfromGu/J01Creatures_20261030/battery_goblin_revised/battery_goblin_revised.mat` 为准(同批 `doe_natural.mat` 同一组,只有 `_BaseColor` 是 0.8):

   | 属性 | 值 | 说明(shader Properties 原注) |
   |---|---|---|
   | `_BaseColor` | (0.82, 0.82, 0.82, 1) | 乘在 `_BaseMap` 上 |
   | `_ShadowThreshold` | -0.03 | NdotL 分界 |
   | `_ShadowSoftness` | 0.82 | NdotL 过渡带宽 |
   | `_ShadowTint` | (0.74, 0.76, 0.9, 1) | 暗部色,再乘全局 `_LabShadowTint` |
   | `_AmbientStrength` | 0.32 | |
   | `_RimColor` | (0.55, 0.65, 0.85, 0) | alpha = rim 强度,0 = 关 |
   | `_RimPower` | 5.37 | |
   | `_ReceiveContact` | 0 | Lab 接触压暗,0/1 |

   - 发光:`_UseEmissionMap` 1(Toggle,对应 keyword `_EMISSION`,脚本里要 `EnableKeyword("_EMISSION")`)+ `_EmissionMap` + `_EmissionColor`(HDR,始终叠加,黑 = 无)。
   - 环境 / 建筑 / 道具:同一 shader;rim 关(`_RimColor` alpha 0)。其余参数是否和角色 / 怪同一组:待核,先对照同类已入库件的 .mat。
   - LabLit 没有描边属性,不用写也写不了;别从旧材质拷 outline / shadow-color 一类的键。
   - 拿不准先做 Unlit 对照:换 URP/Unlit 纯贴图看一眼,判断问题出在几何还是着色。
3. **Remap 在 importer 上做**,所有使用处自动生效、prefab 零改动:
   ```csharp
   var importer = (ModelImporter)AssetImporter.GetAtPath(fbxPath);
   importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "<embedded材质名>"), mat);
   importer.SaveAndReimport();
   ```
   embedded 材质名从第 0 步的 dump 里拿(如 `tripo_mat_b2495fc7`)。成功标志:fbx.meta 的 `externalObjects` 出现该条目,样板是 `J01Creatures_20261030/doe_natural/doe_natural.fbx.meta`(`materialImportMode: 1`,`doe_natural_Painted` → `doe_natural.mat`)。
4. 材质用 `new Material(Shader.Find("Lab/LabLit"))` + `AssetDatabase.CreateAsset` 脚本建,别手写 YAML(shader guid 容易错)。现成脚本:er-character-pipeline 的 `scripts/unity/eval/materials_setup.cs`。

## 2. 修轴心:量 bounds、在使用方 prefab 上反向补偿(FBX pivot Unity 内改不了)
AI 模型 pivot 常不在模型中心,旋转时会"甩"。修法:
1. **量化**:实例化到 identity,合并所有 Renderer.bounds(跳过 ParticleSystemRenderer),对比 bounds.center 与 root position。再实例化使用方 prefab(如 LootCarrier)同样量一次——子节点常带旋转/缩放,偏移会被放大换轴(Scientist:FBX 本地 Z +0.088,经 Y90°+1.64 缩放后变成 X +0.145)。
2. **补偿**:`PrefabUtility.LoadPrefabContents(prefabPath)` → 找到 FBX 实例子节点(通常叫 Model)→ `model.localPosition -= new Vector3(offset.x, 0, offset.z)` —— **只补 XZ,Y 不动(脚要贴地)** → `SaveAsPrefabAsset` → `UnloadPrefabContents`(放 finally)。
3. **复测**:修完重新量,bounds.center 的 XZ 必须 ≈ (0,0)。再 grep prefab 确认只多了 m_LocalPosition.x/z 两个 override,没有别的脏改动。
4. 注意:Generic rig 的动画通常动 Armature 子节点、不动 FBX root,offset 安全;但若 Animator 开了 root motion 要重验。

## 3. 配动画:有骨架没 clip 的模型(Tripo rig 常态)
- **Coplay/Meshy 动画库走不通**:`apply_animation_to_rigged_model` 只认 `auto_rig_3d_model` rig 过的模型(要 `.meshy.info` 的 rig_task_id),Tripo rig 没有;云端重 rig 会替换整个模型 + 耗时 + 异形身材成功率未知——最后手段。
- **首选:手做循环 clip 动 Root 骨骼**(装饰性 NPC 足够,实测球形机器人"工作律动"效果成立):
  1. **先读 rest pose**:`fbx.transform.Find("Armature/Root")` 的 localPosition / localEulerAngles。**曲线必须围绕 rest pose 做相对偏移**——写绝对值会把骨骼拍到原点。Tripo 骨骼 rest 朝向很怪(如 Z=270),不动的轴也要用 `AnimationCurve.Constant` 锁在 rest 值,否则被归零。
  2. 律动配方(2s 循环):Y 浮沉 ±0.06(`m_LocalPosition.y` 正弦形 keyframe)+ 前倾 12° 点头(`localEulerAnglesRaw.x`)。`AnimationUtility.GetAnimationClipSettings` → `loopTime=true` → Set 回去。
  3. controller 与项目同构:单 state 循环(对照 `MineWorkerWork.controller`),`AnimatorController.CreateAnimatorControllerAtPath` + `AddState` + `state.motion = clip`。
- 自带动画的 FBX(科学家)直接 clipAnimations 切片 + controller,不用这节。

## 4. 整体替换场景里的旧模型(如 KayKit 占位 → AI 模型)
在 `LoadPrefabContents` 里对每个旧实例:记下 localPos/localRot/siblingIndex/name → `DestroyImmediate` → `PrefabUtility.InstantiatePrefab(fbx, parent)` → 还原 transform、`SetSiblingIndex`、改名 → 挂 Animator + controller → **逐实例 pivot 补偿**(实例朝向各不同,补偿量不同,统一按"量 bounds → 视觉中心 XZ 拉回锚点、bounds.min.y 拉到锚点平面"算)→ 体量对齐:先量旧模型视觉高度(KayKit Engineer@0.7 ≈ 1.33),换算新模型 scale。最后打印每个实例的 centerXZ off / footY off,全部 ≈ 0 才算完。

## 5. 验证:必须在"真"光照下看(最大的坑)
- **编辑器当前开的场景可能一盏灯都没有**(UIDesign_Gameplay 就是:无 Light,ambient=Skybox)——在那里截图永远灰,会误判没修好。先 `FindFirstObjectByType<Light>()` 探一下。
- 真实战局光 = `Assets/Prefabs/Environment/LightSet.prefab`(方向光 暖白(1,0.96,0.84)×1.6 + spots)。验证流程:临时 `InstantiatePrefab` 一个 LightSet + 一个模型实例(改名加 `__` 前缀)→ `capture_scene_object` 截图 → 看受光面**和背光面两个角度**(背光面只能看出 shadow band,判断不了饱和度)→ `DestroyImmediate` 全部临时物,**场景不保存**。
- **场景会被用户中途切走**:用户在编辑器里干活,active scene 随时变(实测一次会话里 UIDesign_Gameplay → GameScene → Boot)。每次 `GameObject.Find` 临时物前先确认 active scene;预览物随"切场景不保存"自动消失——用 `git status <scene>` 确认场景没被连带保存,而不是假设。
- **capture 对小物件会钻进几何体**:`capture_scene_object` 自动取景在杂物多的场景里会把相机怼进模型/地面内部(出来一张噪点贴脸图)。解法:把模型单独 spawn 到远处空地(如 (60,0,60))单拍;方向光是无限远的,照样有效。
- **用户 WIP 编译错会卡死脚本执行**(CLI `script eval` 和 Coplay `execute_script` 都一样):报错若来自用户正在写的代码,别去修(那是他的活)。验证降级为**直接读资产 YAML**:.anim 的曲线值/`m_LoopTime`、.controller 的 `m_Motion` guid、fbx.meta 的 `externalObjects`——资产层证据同样硬。编译正常时也可用 `AnimationMode.SampleAnimationClip`(实例化→采样→销毁,一次脚本内完成)做数值验证。
- 修好的样子:贴图原有的厚涂色阶保住、LabLit 两阶阴影干净、**看不到黑描边**、暗面不灰黑、不发灰不塑料,和当前 Hero 站一起是一个画风。上面这套隔离摆拍只是自查;最终验收按总纲"怎么判断做到了",在真游戏相机、真灯光的竖屏截图上看,编辑器里孤立模型的截图不算数。

## 6. 收尾
- 删 `Temp/` 下所有临时 .cs。
- 改动面应当只有:新模型文件(fbx/贴图)、新 .mat、新 .anim/.controller(若配了动画)、fbx.meta 的 externalObjects、使用方 prefab 的 transform override / 实例替换。多一个文件都要解释。
- 不 commit、不 push(红线)。

## 已知局限 / 升级路线
- 贴图本身饱和度低(白大褂、灰发)时 LabLit 只能还原贴图,不能无中生有。要不要更艳先看参考资料第 3 节的饱和度预算:角色、怪、交互物该跳出来,环境件反而要收。确实要提,可以微调 `.mat` 的 `_BaseColor` 往暖色推,或 PS 里直接加贴图饱和度,二选一,别叠加过头。
- 手做律动 clip 只适合装饰性 NPC;要正经走路/战斗动画,走 Meshy 重 rig(auto_rig_3d_model → apply_animation_to_rigged_model → .glb)或回 DCC。
