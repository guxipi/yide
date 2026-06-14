---
name: gaoguang-3d
description: "高光3D" — intake/fix pipeline for AI-generated 3D models (Tripo, Meshy, text-to-3D…) dropped into the Extraction project so they match the game's Archero-style high-saturation toon look. Trigger on "高光3D" / "模型太灰暗" / "模型发灰" / "新模型不好看" / "像 archero 一样饱和" / "把XX替换成这个模型" / 新导入的 FBX 看起来灰、暗、塑料感 / pivot 轴心不在模型中间、转身会甩 / 模型有骨架没动画需要配动画. Fixes = ToonLit material remap on the ModelImporter + pivot centering + rig/animation wiring + verification under REAL game lighting (LightSet.prefab — preview scenes often have NO light at all). Battle-tested on the mine-point Scientist (tripo FBX in LootCarrier.prefab) and the spherical robot mine workers (rigged-but-no-clips tripo FBX replacing KayKit Engineers in LootGeyserInstallation.prefab).
---

# 高光3D — AI 模型进项目的"去灰提饱和"流水线 (Extraction)

AI 生成的模型(Tripo 等)直接进项目必灰。原因是固定的三连:**embedded material 是 URP/Lit(PBR)** + **_BaseColor 常为 (0.8,0.8,0.8) 把贴图乘暗 20%**(也有白的,但 PBR 本身就压灰) + **_Smoothness 0.5 塑料高光**。项目的 Archero 风格来自 `Assets/Shaders/ToonLit.shader`(`Custom/ToonLit`:双阶 toon 光 + rim + 描边)——所有角色(Hero/engineer.mat)都用它。修复 = 换材质 + 对轴心 + 配动画 + 真光照验证,全程 Unity 内,不回 DCC。

## 0. 诊断(动手前必做,别猜)
用 `execute_script` dump 真值(临时 .cs 放 **项目根 `Temp/`,不进 Assets**,用完删):
- 加载 FBX,遍历 `GetComponentsInChildren<Renderer>` 打印每个 sharedMaterial 的 shader 名、`_BaseColor`、`_BaseMap`、`_Smoothness`、`AssetDatabase.GetAssetPath(mat)`。assetPath 指向 .fbx 本身 = embedded 自动材质,就是本 skill 的目标场景。
- **同时 dump rig 与动画**:hierarchy(有无 Armature)、SkinnedMeshRenderer.bones.Length、`LoadAllAssetsAtPath` 里的 AnimationClip 列表。Tripo 模型分两种:带 NLA 动画(科学家:Idle/Walk/Work)和**有骨架但零 clip**(球形机器人:41 bones,无动画)——后者要走第 3 节。
- 同时 dump 一个项目标杆(Hero.prefab → engineer.mat)做对照。
- grep FBX 的 guid 找到所有引用它的 prefab/scene(决定 pivot 修在哪)。
- 素材在云盘时注意:用户给的 `G:\My Drive\...` 路径本机 G: 直接可读(本机挂两个云盘账号,G: 和 H: 都在),别想当然换盘符。

## 1. 修观感:ToonLit 材质 + ModelImporter Remap(不要在 prefab 里 override 材质)
1. 在模型同目录建 `<Model>.mat`:shader `Custom/ToonLit`,`_BaseMap` = 模型 basecolor 贴图,`_BaseColor` = **纯白**(别留灰)。
2. Toon 参数**完全对齐 engineer.mat**,保证全场一个画风:`_ShadowColor (0.6,0.5,0.6)`、`_ShadowThreshold 0.746`、`_ShadowSmoothing 0.0619`、`_RimColor 白`、`_RimPower 5.37`、`_RimThreshold 0.351`、`_OutlineWidth 20`、`_OutlineColor 黑`。
3. **Remap 在 importer 上做**,所有使用处自动生效、prefab 零改动:
   ```csharp
   var importer = (ModelImporter)AssetImporter.GetAtPath(fbxPath);
   importer.AddRemap(new AssetImporter.SourceAssetIdentifier(typeof(Material), "<embedded材质名>"), mat);
   importer.SaveAndReimport();
   ```
   embedded 材质名从第 0 步的 dump 里拿(如 `tripo_mat_b2495fc7`)。成功标志:fbx.meta 的 `externalObjects` 出现该条目。
4. 材质用 `new Material(Shader.Find("Custom/ToonLit"))` + `AssetDatabase.CreateAsset` 脚本建,别手写 YAML(shader guid 容易错)。

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
- **用户 WIP 编译错会卡死 execute_script**:报错若来自用户正在写的代码,别去修(那是他的活)。验证降级为**直接读资产 YAML**:.anim 的曲线值/`m_LoopTime`、.controller 的 `m_Motion` guid、fbx.meta 的 `externalObjects`——资产层证据同样硬。编译正常时也可用 `AnimationMode.SampleAnimationClip`(实例化→采样→销毁,一次脚本内完成)做数值验证。
- 修好的样子:亮白/饱和的固有色 + 双阶 toon 阴影 + 黑描边,和 Hero 站一起是一个画风。

## 6. 收尾
- 删 `Temp/` 下所有临时 .cs。
- 改动面应当只有:新模型文件(fbx/贴图)、新 .mat、新 .anim/.controller(若配了动画)、fbx.meta 的 externalObjects、使用方 prefab 的 transform override / 实例替换。多一个文件都要解释。
- 不 commit、不 push(红线)。

## 已知局限 / 升级路线
- 贴图本身饱和度低(白大褂、灰发)时 ToonLit 只能还原贴图,不能无中生有——还想更艳:微调 `.mat` 的 `_BaseColor` 往暖色推,或 PS 里直接加贴图饱和度,二选一,别叠加过头。
- `_OutlineWidth 20` 是按 KayKit 角色体量调的;模型特别大/小时描边可能过粗/过细,按截图微调。
- 手做律动 clip 只适合装饰性 NPC;要正经走路/战斗动画,走 Meshy 重 rig(auto_rig_3d_model → apply_animation_to_rigged_model → .glb)或回 DCC。
