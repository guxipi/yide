# 阶段 8:Unity 入库(F:\GitManagedUnityProjects\Extraction,Unity 6000.3.5f2,URP)

## 8.0 操作 Unity 的规矩(每次进这一阶段前读一遍)
- 首选 Unity CLI(`scripts/unity/ucli.sh` 包了一层),Coplay 只做备用。**从 Git Bash 调**,PowerShell 会吞掉 eval 代码里的双引号。
- eval 代码是语句形式,以 `return <表达式>;` 结尾;不能写 using,类型写全名;**不能同步等异步**(`.Result/.Wait()/GetAwaiter().GetResult()`)——会把编辑器主线程锁死,只能杀进程。
- **写任何 .cs 之前 `ucli.sh guard`**:编辑器设的是"Play 结束后再编译",Play 中写 .cs 会让所有会话的通道一起卡死,只有人手点 Stop 能解;"日志里没有 error CS"不等于编译过,以 editor_status 的 compiling=false 为准。别信"Unity 空了"这类旧消息,当场查。
- 不切场景;非切不可时先查有没有 dirty 场景(Coplay open_scene 会静默丢掉未保存的改动)。
- 不改无关文件(工作区里本来就有别人的改动,比如 Expedition.unity、CloudCode 产物,别碰)。不 commit。
- 截图别用 capture_scene_view(场景窗不刷新时是空白,而且存进 Assets/Temp);用 `render_views.cs`(临时相机 → RenderTexture → 直接写到工程外)。capture_game_view 只在 Play 里用,它把文件存进 `Assets/Temp/`,`ucli.sh capture` 会搬走并删掉 .meta。
- 验收完一定 `ucli.sh stop`,并确认 playMode=stopped 再说"测完"(stop 会假成功)。

## 8.1 放文件
目标目录 `Assets/Art/3DModelsfromGu/0_Characters/<Name>/`:
```
<Name>.fbx                      (rig 目录里 face_swap 之后的那个)
Textures/<Name>_basecolor.png   (rig_build 输出,2048)
Textures/<Name>_face_atlas.png  (2048x1152)
Textures/<Name>_emission.png    (有发光件才有)
```
用 bash `cp` 放进去,然后 eval `UnityEditor.AssetDatabase.Refresh(); return "ok";`。

## 8.2 一条条跑(先生成命令)
```
py -3 scripts/unity/spring_spec.py --config <cfg> --face-type "Gameplay.Actors.WrenFaceController, Assembly-CSharp"
```
它按 config 打印下面每一步的完整命令(占位符都填好)。**一步一步跑,读完返回值再跑下一步**。

| 步 | 命令 | 返回值里必须看到 |
|---|---|---|
| 1 | `ucli.sh guard` | GUARD OK |
| 2 | `import_setup.cs` | animationType=Human;embedded materials 列表(= remap 键,形如 `tripo_mat_<uuid>`、`<Name>Face`) |
| 3 | 一次性:把 `templates/unity/CharacterEnforceTPose.cs` 拷到 `Assets/Editor/CoplayTemp/`(写 .cs,先 guard),等编译完(compiling=false) | — |
| 4a | `canon_tpose.cs FBX=<模型 FBX>`(10-24 新增,**必跑**,在 enforce_tpose 之后) | 返回 `Left arm=(-1,0,0) hand=(-1,0,0) idxlit=(0,0,1) leg=(0,-1,0)`、右侧镜像、`avatar valid=True`;动作 FBX **不跑**(它共用模型 avatar,见 8.8);只对模型 FBX 跑。原因:Unity 的 Enforce T-Pose 只把骨头摆进"合法范围",模型和动画两份 avatar 的 T-pose 各自偏几度,肌肉重定向把差值当成恒定内收/外撑(Rook2 10-23:腿交叉内八、手臂僵硬外撑都是它)。两份都规范到同一标准(臂/前臂/手沿 ±X 掌心朝下、手指伸直、脊柱头竖直、腿正下脚尖朝前)后,世界角度原样搬运。只改 avatar 参考姿势,网格和权重不动。 |
| 4c | `facing_probe.cs ASSETS=<模型 prefab;动画 FBX>` | 每份 `FACING OK`(零肌肉姿势左手 x<0、脚尖 z>0);WRONG = T-pose 左右定反了,人会在挂点上背对镜头 |
| 4b | `tpose_probe.cs ASSETS=<模型 prefab;动画 FBX>` | 两份 `zeroMuscle: ankleSpread/hip=1.00` 且 `Lleg dir(lat,y)=(0.00,-0.98)`;不一致就回 4a |
| 4 | `enforce_tpose.cs` | `IsPoseValid before=False … after=True`、`patched skeleton bones=N/N` |
| 5 | `avatar_check.cs` | **`AVATAR PASS`**:human ≥ 22(Wren 55)、skeleton 非空(Wren 80)、isHuman、isValid。另外 `git diff` 看 `<Name>.fbx.meta` 的 humanDescription 确实写进去了。 |
| 6 | `materials_setup.cs` | remapped 每个 embedded 名都映射到 `<Name>.mat` / `<Name>Face.mat`;emission 贴图名 |
| 7 | `prefab_build.cs` | `PREFAB OK`、springBones 数 = 次级骨数(不含 _Tip)、没有 "WARN leaf spring bone" |
| 8 | `render_views.cs UNLIT=1` 和 `UNLIT=0` | 见 8.3 |
| 9 | `hero_swap.cs`(本地验收用) | HERO SWAP OK、oldH/newScale/newH、repointed、UNRESOLVED 只剩 WeaponHolder._mountPoint |
| 10 | `weapon_mount.cs` | WEAPON MOUNT OK、assigned、lscl 在 0.1~3(~100 倍 = FBX 根缩放的坑回来了) |
| 11 | `avatar_check.cs` | 再确认一次 |

## 8.3 着色门:Unity 里和 Tripo 里必须是同一个人
- 先看 `UNLIT=1`(URP/Unlit 纯贴图):应和 Blender 里的 tex 渲染几乎一样。不一样 = 贴图/UV/材质 remap 有问题(常见:新 FBX 的材质名变了,旧 remap 不生效,身体变素色、脸上贴了整张图集——重跑 materials_setup)。
- 再看 `UNLIT=0`(ToonLit + LightSet 真光):不能"崩坏"。10-07 勾哥说"跟 Tripo 里像两个人"——原因是照抄了 engineer.mat 的 ToonLit 参数(描边 20、阴影 0.6/0.5/0.6、阈值 0.746、平滑 0.06、rim 0.351),那是给 KayKit 低模平色角色调的;叠在自带厚涂明暗的 AI 角色上 = 明暗算两遍 + 每缕头发描黑线。厚涂角色用 materials_setup 里的参数:`_ShadowColor (0.85,0.8,0.85)`、`_ShadowThreshold 0.5`、`_ShadowSmoothing 0.25`、`_OutlineWidth 0`(2026-10-11 起 3D 世界看不到黑描边,角色也不描)、`_RimThreshold 0.9`、`_BaseColor 0.95`。gaoguang-3d skill 里的 engineer 口径**不适用于这类角色**。
- 看:脸干净、厚涂色阶保住、头发和膝盖后面没有黑描边、没有过曝;受光面和背光面各一张;top70 俯视能认出角色。

## 8.4 换主角时的三个结构要求(hero_swap.cs 已经做对,手改时别破坏)
**10-08 起优先用 `eval/hero_swap_keepall.cs`**:Hero.prefab 里模型现在是嵌套预制体实例(Hero > <旧角色>[prefab] > Model[Animator]),Animator 节点上挂着共用组件(UnitAnimator、HeroAnimationRig、HeroGunHoldPose、HeroPreviewShow、HeroLegTidy)。keepall 版替换整个实例、保留这些组件,只不搬旧角色的表情控制器 / SpringManager / HeroSkirtFollow,并删掉旧角色的空壳实例。标准版 hero_swap.cs 只搬 UnitAnimator,别再用在现在的 Hero.prefab 上。换前把 Hero.prefab 拷到工程外备份。

1. **缩放和 180° 转身放在 Animator 那一层**。CharacterPreviewController(装备页预览)只取带 Animator 的 GameObject,包在外面一层的缩放/转身会丢:Wren 一开始在装备页里又小又背对镜头。180° 是玩家"负 forward"约定(PlayerController 故意反着转,模型根补 180°),不要去"修"这个负号。
2. **WeaponMount 挂在右手骨下,位姿从旧主角换算**。两个主角播同一条 clip 的同一帧,把旧挂点相对旧手骨的位姿搬到新手骨上,所有枪原来的握持参数(GunClassVisualLibrary 的 GripRotation 等)就能直接用。
3. **SpringBone**:马尾/刘海链**不挂任何碰撞球**——根部天然陷在 Head/Neck/Spine2 的球里,挂了就被推成水平"翅膀",缩半径也没用;裙摆只和腿上的球碰撞。测弹簧参数要改 prefab → 重进 Play → 生成新实例,运行时反复开关骨头会把模拟状态搞乱。包是 `com.unity.springbone`(git `https://github.com/unity3d-jp/UnityChanSpringBone.git#release/1.2`),命名空间 `Unity.Animations.SpringBones`(10-07 写成 `UnityChan.*` 编译不过)。Wren 参数:马尾 18/0.34/0.018、刘海 22/0.38/0.014、裙摆 55/0.58/0.022、罐子 180/0.82/0.018;Manager 60Hz、dynamicRatio 0.75、gravity (0,-0.08,0)、碰撞开、长度限制关、地面碰撞关;腿球 UpLeg 0.09、Leg 0.075。

## 8.5 表情控制器
现在工程里只有 `Gameplay.Actors.WrenFaceController`(按材质名前缀 "WrenFace" 找脸)。新角色要用通用版 `templates/unity/CharacterFaceController.cs`(按材质名后缀 "Face" 找,枚举顺序 = 图集顺序)。这是共享代码改动:先问勾哥,guard 后再写,不要为了复用把新角色的脸材质也叫 "WrenFace..."。Expression 枚举顺序必须和 config `face.expressions` 一致。

## 8.6 出口门
AVATAR PASS(+ .meta diff);材质 remap 覆盖全部 embedded 名;UNLIT 和 ToonLit 两组渲染看图门过;prefab OK;(本地)Hero 换好、WeaponMount 赋上;编辑器 stopped、compiling=false、Console 无新错误;Assets/Temp 里只剩 HeroOld.prefab(阶段 9 后删)。

## 8.7 裙子和头发:裙子跟大腿走,头发才用弹簧(10-08 定,三轮调物理失败后换方案)
**短裙不要用 SpringBone。** 三轮实测:前片限制窄 → 跑步深蹲大腿穿出前片(插件先算碰撞后算角度限制,限制把推开的裙子拽回腿里);放宽到 80° → 被大腿胶囊顶成翻领;后片 → 冲刺起步被惯性甩成钟形。怎么调都按下葫芦起瓢。
**现做法:`Gameplay.Animation.HeroSkirtFollow`**(挂 Animator 节点,执行序 -90,在 HeroLegTidy 之后、SpringManager 之前)。每片裙摆根骨按"最近那条大腿朝这片抬了多少度"直接转出去,没有惯性:不可能穿腿、不会钟形、不会卡在掀起状态。参数 Wren:gain 2(裙子顶点保留约 45% Hips 权重,骨头要多转一倍才够)、maxLift 90、deadZone 6、falloff 1.6、hemFlare 0.25。prefab 上必须**删掉裙摆骨的 SpringBone、它们在 SpringManager 列表里的条目和大腿胶囊**,否则两套系统打架。
**头发**仍用 `spring_limits.cs`,SKIRT 填 `NONE`:LIMITS `Hair_F|25|0.45;Hair|45|0.45`,DYN 1。角度限制要 `pivotNode` 才生效(脚本会建),头发不挂碰撞体。
**验收**:① 离线:编辑器里 SampleAnimation 后用反射调组件的 Awake/LateUpdate(把 _response 设很大)拍开/关对照,run/jump_down/laugh_01/cheer;注意 SampleAnimation 不会复位裙摆骨,关组件那组要把 gain 设 0 再调一次 LateUpdate 复位。② 远征:`PlayerController.OnControlStarted(true)` + `OnControlInput(new Vector3(1,0,0.3f), true)` 冲刺,起步和稳定各拍一组。③ Gear 页强制大动作。看:大腿不穿出前片、后片不钟形、前片不翻领。
**已知遗留**:大腿根和裙摆下沿偶见小白碎片,贴图里没有白面(全贴图近白三角形 1 个),疑似边缘光打在裙子内侧薄面上,未修。

**腿型:`Gameplay.Animation.HeroLegTidy`**(勾哥:"外八字和膝盖外翻")。Tripo 模型本身脚尖外撇约 9°,Tripo 的预设动作(尤其 cheer)两腿外分、膝盖外翻。每帧动画后:大腿绕"髋→脚腕"轴转,让膝盖回到正前方(脚腕不动,IK 结果保留);脚尖外撇超过 8° 的绕脚腕竖轴转回;膝角小于 110°(跪坐、深蹲)不动。不要在 Avatar 基准姿势上修:试过,工程里的 Mixamo 动作反而外撇到 18~48°,已还原。

## 8.8 装备页/背包预览:不持枪 + 1~2 个性格动作 + 表情循环(10-08 勾哥定)
背包和装备页里角色手上不拿枪,只循环 idle,隔几秒插一个能认出这个人性格的动作,同时换表情。**每个角色的动作和表情配在自己 prefab 的 Animator 节点上:组件 `Gameplay.Animation.HeroShowcase`(Idle、Fidgets[Clip/Expression/MaxSeconds]、IdleGap)。** 播放器 `HeroPreviewShow` 是通用的:优先读角色的 HeroShowcase,没有才用自己身上的兜底字段;表情走接口 `Gameplay.Actors.IExpressionFace`(WrenFaceController、CharacterFaceController 都实现,新表情控制器也要实现它,否则预览里表情不动)。换主角时不用动 Hero.prefab 上的 HeroPreviewShow。组件 `Gameplay.Animation.HeroPreviewShow`(PlayableGraph,idle 循环 + 交叉淡入小动作),挂在 Hero.prefab 的 Animator 节点上并**默认关闭**,局内永远不跑;`CharacterPreviewController` / `ProfileCharacterPreviewController` 生成预览时启用它,有它就不挂枪、不开持枪层。

**挑动作 = 从角色手册"性格""体态与动作方向""表情"三段推,不是挑好看的。** Wren:"可爱、聪明、嫉妒心极重","招牌动作是把发光的标本罐举起来给人看" → 两个:`cheer`(单臂高举 = 炫耀"你看我找到了什么",表情 Grin)+ `frustrated_01`(叉腰跺脚 = 小孩式嫉妒撒气,表情 Jealous)。只要 1~2 个:多了像随机舞蹈,认不出人。
**动作来源(10-24 重写,Rook2 根因后)**:Tripo Animate 页预设(Mixamo 骨架直接套,该角色第一次重定向扣约 70 点,之后其余预设不再扣),Export 选 GLB + 勾选全部动作 + Animation stay in Place,一个 GLB 里每个动作是独立 animation(FBX 会被合成一条)。**不要**把 GLB 骨架直接转 FBX 自建 avatar(那是第二副骨架,见 05 §6.8):用 `scripts/blender/anim_bake_to_rig.py` 把动作烘到模型最终骨架(`<slug>_rig_final.blend`)上导出 `<Name>_Anims.fbx`,`anim_verify.py` worst <1° 过门后进 Unity,导入用 `eval/anim_import_shared.cs`(Humanoid + **CopyFromOther = 模型 avatar**,骨架逐骨相同时这才合法;clip 循环标志在脚本里改)。进来后三道门,缺一不可:① `eval/foot_probe.cs`/`eval/knee_t.cs` 取同一时刻和 Blender 源对数(脚掌俯仰、膝距、踝距差 ≤0.05 胯宽/≤3°);② `scripts/unity/audit_v.sh`(`CLIPS="path#clip;..." VIEW=front|side N=6`)正侧全身板,人不在画面里=朝向坏;③ `eval/fullbody.cs` 正/侧/背/3/4 与 Wren 同机位并排,逐条列不自然点。enforce_tpose/canon_tpose 只对**模型** FBX 跑一次(让外来的共享 Humanoid clip 如 Death、Pod_SeatBrace 落得正),不再对动作 FBX 跑。
**筛选门**(Unity 里 SampleAnimation 拍胶片条,和 Blender 里同一帧量手骨位置对数字,别对着小图判断):
- 淘汰会转身背对镜头的(scratch、warm_up)、会飞出画面的(flip)、两腿交叉/坐姿穿插的(wave_goodbye_01)、辨识度低的(standing_relax、fold_arms)、手臂穿进头发的(heart_pose 穿马尾)、名不副实的(greet_01 手不动)。
- 时长:长于 6 s 的设 `MaxSeconds` 截断(cheer 12 s → 4.5 s),截断时用 0.8 s 淡出(`_truncatedFadeOut`),0.35 s 会让举着的手臂突然塌下。
**接入三坑**(都踩过):① 预览生成时会删光模型上的 MonoBehaviour——表情控制器、SpringManager 必须挂在 **Animator 同一节点**上并在 `HeroPreviewShow.KeepOnPreview` 白名单里,挂在外层就跟着 Hero 根一起被删,预览里不换表情、头发不动;② 新动作接进 mixer 后当帧权重是 1,idle 1 + 动作 1 叠加,人往上弹一帧 → Connect 后立刻把第 1 路权重置 0;③ 第一个动作在打开后约 2 s 出,让人马上看到性格。
**验收**:Play → 装备页 → 等 60 s,记录轮播顺序、表情、髋部高度(不许跳)、手上武器渲染器数 = 0;切别的 tab 再回来仍在播。

## 8.9 肤色(10-08,勾哥:"肤色太黄了,她是白人")
Tripo 贴图的皮肤普遍偏橘黄(Wren 量出来 RGB 约 239/149/109,色相 18°、饱和 0.54)。白人角色用 `scripts/skin_recolor.py` 对身体底色和表情图集**用同一组参数**改(否则脖子接缝两色)。**定稿参数 `--sat 0.70 --lift 0.16 --hue -3`**(浅桃色,脸约 246/174/151)。第一版 `--sat 0.45 --lift 0.35` 被勾哥打回"太白了像鬼":装备页灯光很亮,纸白皮肤没有血色、发灰。白人肤色要保留暖调和血色,做三档(sat 0.8/0.7/0.62、lift 0.10/0.16/0.22)在装备页真实光照下挑。软遮罩阈值是试出来的:色相 4~42°、饱和 0.32~0.74(上限挡住琥珀色虹膜,第一版没挡眼睛变灰)、亮度 ≥ 0.5(挡住深棕靴子和皮件,第一版靴子变粉)。先出 `--mask` 遮罩图和前后对照看,再进 Unity 拍正/侧/背/3/4 四向,放大看背光面没有残留橘块。角色设定写明肤色的,出贴图前先核对一次,别等进游戏才发现。
