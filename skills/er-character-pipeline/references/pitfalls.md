# 踩过的坑总表(症状 → 根因 → 预防 → 在哪一步)

| # | 症状 | 根因 | 预防 / 修法 | 阶段 |
|---|---|---|---|---|
| 1 | 模型脸"蛇精脸":正脸平、眼窝深、V 下巴 | 只喂平光四视图,Tripo 读不出脸深度 | 两套参考图:结构参考(体积光)只建白模,平光厚涂只上贴图;clay 灰模从正/侧/3/4/俯 70° 看脸 | 2、3、5 |
| 2 | 建模图被打回"细节偏了" | 为重建把识别件简化成别的形状(Rook 绳袋/头盔、Wren 方罐) | 只删悬空件,识别件形状照定稿图;逐件对照表 | 1 |
| 3 | 头身比卡在 6.3 或一下跳到 4.7 | sol 按文字给立绘比例;"放大 25%"过冲 | edit 喂上一张,每次 10~12% | 1 |
| 4 | 改脸改不动 | 喂了旧版本当参考,脸被锁回去 | 改脸结构时去掉旧版,只用文字 + 定稿图特写 | 1、7 |
| 5 | 以为颜色偏色相,改了没用 | 实际差在饱和度/明度 | 先 `crop_compare.py --hsv` 量 | 1 |
| 6 | 对着 prompt 打勾交付,实际没改到 | 没看像素 | 每版和上一版裁同一区域并排看 | 全程 |
| 7 | 点了没反应、导出没文件、截图超时 | 控制的是另一台机器的 Chrome | 先 JS 验身(版本/GPU/DPR) | 3 |
| 8 | 页面加载不完、截不了图 | 后台标签被节流 | 开新的前台标签 | 3 |
| 9 | 设置和上次不一样(面数 200 万、PBR 开) | 设置跨会话保存,别的会话改过 | 每次 Generate 前逐项核对,看价格标签对不对 | 3 |
| 10 | 预设动作少了一半 | 点太快被吞 | 每个隔约 6 秒,关开导出面板核对数量 | 3.4 |
| 11 | 拿到的文件没骨骼 | 迟到落盘的旧导出 | 每个下载先 `inspect_model.py` | 3 |
| 12 | 上传被拦 | 浏览器上传工具读不到 character-art-lab | 从 vault 路径上传 | 2、3 |
| 13 | 手臂底面灰褐脏块 | 四视图拍不到的地方 Tripo 乱糊 | `tex_clean.py`(皮肤判定 + 手臂区生长 + push-pull) | 5 |
| 14 | 换了网格后脑出肤色斑和黑洞 | 拿旧网格清好的贴图套新网格,UV 不一样 | 在最终 rig GLB 上清理;网格一换就重做 | 5 |
| 15 | 举手时背包炸出黑刺 | 罐体/背带吃了上臂权重 | rigid 100%;straps 不收手臂驱动的顶点 | 6 |
| 16 | 下蹲/跑步裙子碎成黑白条纹 | 裙子顶点跟着大腿 | 裙子按布料颜色(含阴影内侧低饱和)+ 邻居投票识别,身体部分只给 Hips | 6 |
| 17 | 袖子后侧扯出白色尖片 | 袖子被背带规则收进去 | straps `max_arm` | 6 |
| 18 | 转头时后脑不动 | 远距修剪删了后脑的 Head 权重(1941 顶点落到 Neck) | 修剪跳过 Head 骨;审计 far_body | 6 |
| 19 | 链最后一节 SpringBone 方向怪 | 最后一节没有子骨 | 每条链加 `*_Tip`,导出保留非变形骨 | 6、8 |
| 20 | 装备页里一大块灰黑挡住镜头/枪 35 米长 | FBX 导出没烘缩放,armature 根 100 倍,挂手上的枪跟着放大 | 只用 `FBX_SCALE_ALL` 导出;`export_fbx.py` 复核 | 6、7 |
| 21 | 所有动画一起歪(手插身体、腿外撇) | Avatar 没做 Enforce T-Pose,.meta 骨骼表空 | enforce_tpose + avatar_check,看 .meta diff | 8 |
| 22 | 换模型后身体素色、脸上整张图集 | 新 FBX 材质名(tripo_mat_<uuid>)变了,旧 remap 失效 | 每次换 FBX 重跑 materials_setup | 8 |
| 23 | 闭眼表情眼角白三角 | 选面没包住眼角;或"后脑保护"的深度规则把眼角删了 | 特征带内邻接生长;后脑保护只按法线 | 7 |
| 24 | 脸上贴着整张图集/表情错位 | UV 没换成格子空间,或底图渲染投影和 UV 投影不一致 | face_swap 直接写格子空间;投影只存一份 face_projection.json | 7 |
| 25 | 表情画在旧脸上 | 网格变了没重画 | 网格一变,face_render + 全部表情重来 | 7 |
| 26 | Unity 里"像两个人、崩坏了" | 照抄 engineer.mat 的 ToonLit 参数,明暗算两遍、头发描黑线 | 厚涂参数;先 Unlit 对照判断是几何还是着色 | 8 |
| 27 | 马尾横飞成翅膀 | 马尾链挂了头/颈/胸碰撞球,根部陷在球里 | 马尾不挂碰撞球,裙摆只挂腿 | 8 |
| 28 | 装备页里人又小又背对 | 缩放/转身写在 Animator 外面一层 | 放在 Animator 节点上 | 8 |
| 29 | 枪握不对 | 握持参数按旧主角手骨调的 | WeaponMount 从旧主角同一帧换算 | 8 |
| 30 | 编辑器卡死、所有会话超时 | Play 中写 .cs / eval 里同步等异步 | `ucli.sh guard`;eval 不等异步 | 8、9 |
| 31 | eval 报 "; expected" | PowerShell 吞双引号 | 从 Git Bash 调 | 8 |
| 32 | 截图空白、Assets 里多出文件 | capture_scene_view 不刷新且存进 Assets/Temp | 用 render_views.cs;capture 后搬走删 .meta | 8、9 |
| 33 | 把游戏挂在 Play 交付 | 忘了停 / stop 假成功 | ingame_check 的 trap;stop 后查 playMode | 9 |
| 34 | SpringBone 代码编译不过 | 命名空间写成 UnityChan.* | `Unity.Animations.SpringBones` | 8 |
| 35 | 测弹簧参数结果乱跳 | 运行时开关骨头搞乱模拟状态 | 改 prefab → 重进 Play → 新实例 | 8 |
| 36 | 子 agent 不点 Generate | 不认转述的授权 | 花点数的步骤本会话做 | 3 |
| 37 | sol 活被直接拒 | 自动模式下没有 `Bash(codex exec:*)` 规则 | 开工前查权限 | 0 |
| 38 | `$(cat prompt)` 传给 codex 是空的 | 参数传长文本会丢 | `- < prompt.txt` 走 stdin | 1 |
| 39 | 并行出图全被杀 | `( … & )` 双层后台 | 同一 shell `&` + `wait` | 1 |
| 40 | 图床放错账号,表里图不显示 | 表在 militarypineapple,图放进了 krystalxch | 表在哪个账号,图就放哪个账号 | 10 |
| 41 | 持枪手指摊开、手枪横夹胸口、肘部对折、四种枪一个架势 | 枪挂右手骨的"手带枪"架构;rig 不修手旋转不管手指;AimDirection 读枪口,帧初跟着动画手乱指 | 持枪统一走 HeroGunHoldPose(枪带手+分枪型架势+上身扭转+两骨 IK+手指);验收看手部特写并量肘角(右肘 手枪约130/冲锋散弹约85/狙击约75,左肘120~150),再看 Kick 后坐不脱手 | 9 |
| 42 | 走跑跳蹲时裙摆下沿、大腿根出白缝黑三角,idle 正常 | 分区规则逐顶点硬赋值 + glTF 在 UV 缝拆顶点,权重台阶被大关节角扯开 | rig_build 接缝平滑 + 重合顶点共权重;规则渐隐不硬删;审计 seam 门 | 6 |
| 43 | 大笑弯腰裙子整片翻起、头发炸成碎片(只在开物理时) | SpringBone 角度限制全关;限制要 pivotNode 才生效 | spring_limits.cs:每骨参考节点 + 限制;裙摆不对称 | 8 |
| 44 | 蹲、抬腿时大腿从裙子中段穿出 | 碰撞球只在髋和膝 | spring_limits.cs 加大腿胶囊,挂到所有裙摆骨 | 8 |
| 45 | 改了限制后跑步/深蹲大腿从裙子前片穿出 | SpringBone 先碰撞后角度限制,前片限制比大腿抬升窄 | 前片外张 80、后片 25(按脚尖朝向渐变),dynamicRatio 1 | 8 |
| 46 | 冲刺起步后片裙子掀成钟形 | 惯性 + 后片外张余量太大 | 后片单独收到 25;验收必须在远征里真的跑起来拍 | 8 |
| 47 | 预览里不换表情、头发不动 | 预览生成删光脚本,表情/弹簧挂在 Animator 外层 | 挂到 Animator 同节点 + KeepOnPreview 白名单 | 8 |
| 48 | 小动作开始那帧人往上弹 | mixer 新输入当帧权重 1,与 idle 叠加 | Connect 后立刻 SetInputWeight(1,0) | 8 |
| 49 | 长动作中途塌回 idle | 截断时用了 0.35 s 淡出 | MaxSeconds 截断 + 0.8 s 淡出;优先挑 ≤6 s 的动作 | 8 |
| 50 | 贴脸开火枪口压向地面 | 只限制了左右;瞄准点只放枪口前 1 m,绕挂点转时角度放大 | 俯仰 ±12°、点放 ≥8 m | 9 |
| 51 | 死亡后角色还举着枪 | 死亡同帧 timeScale=0,按游戏时间淡出永不结束 | 死亡立即让出;淡出用 unscaledDeltaTime | 9 |
| 52 | 白人角色肤色偏黄 | Tripo 贴图皮肤橘黄 | skin_recolor.py 身体+图集同参;遮罩挡虹膜和靴子 | 8 |
| 53 | 预览动作手臂扁平、比心变平伸 | 动画 FBX 的 Avatar 没做 enforce T-pose | 动画 FBX 也跑 enforce_tpose | 8 |
| 54 | 弹簧裙子:窄了穿腿、宽了翻领、后片钟形,怎么调都不对 | 短裙贴着腿,插件先碰撞后限制 + 惯性 | 短裙改 HeroSkirtFollow 跟大腿走,删裙摆 SpringBone;弹簧只给头发 | 8 |
| 55 | 外八字、膝盖外翻 | Tripo 模型脚尖外撇 + 预设动作两腿外分 | HeroLegTidy 每帧收膝收脚尖;别改 Avatar 基准 | 8 |
| 56 | 白人肤色改成纸白,"像鬼" | 饱和砍太多、亮度提太多,亮灯下无血色 | sat 0.70 lift 0.16;三档在装备页灯光下挑 | 8 |
| 57 | QA 在 Play 时我写了 .cs 和 prefab,那轮结果作废 | 多 agent 共用编辑器 | 写 .cs/prefab 前先 editor_status,QA 在测就等它收尾 | 9 |
| 58 | 建模图头身比 5.5 的角色(Rook/Vesper)prompt 里写着"4.7-5 heads" | body.txt 写死了 Wren 的头身 | 已改成按 sheet.head_ratio 算 {HEADS};模板图用同头身的角色(Rook 用 Vesper front) | 1 |
| 59 | 左右视图朝向门 FAIL,目视朝向是对的 | 背包+头盔把 bbox 往后撑,"皮肤质心偏 bbox 中心"失效 | 大背负件角色朝向门只作参考,以不对称件逐件目视为准 | 1 |
| 60 | 侧面视图头比正面小 0.015 | sol 侧面按自己的比例画 | finalize 后用放大刻度量下巴(skin 检测会把脖子算进去),侧面 edit 喂 front final 作比例参考放大 10% | 1 |
| 61 | 头盔(琥珀面罩)被当成头发/挂着脖子权重,远距权重报几百 | 颜色规则看色相,琥珀=棕 | 背上悬空硬件单独一根 rigid + capsule_radius,max_head 放开 | 6 |
| 62 | 长脸角色嘴落在 face_calib 蓝带下面 | 默认投影按圆脸 Head 骨推 | 看 calib 调 center_z/ortho_scale(Rook 0.884/0.185);棕发角色 hair_hue_ranges 留空 | 7 |
| 63 | sol 出图 1254x1254,face_atlas 判 FAIL size | sol 偶尔不按要求尺寸 | 缩回 1024,原图留 *-1254 | 7 |
| 64 | hero_swap 后 HeroGunHoldPose/HeroPreviewShow/HeroLegTidy 全没了;或删旧模型报错 | 标准版只搬 UnitAnimator;Hero 里模型是嵌套预制体实例,子物体删不掉 | 用 hero_swap_keepall.cs;spring_spec 打印的命令清单行号别数错(Rook 误跑标准版,靠工程外备份还原) | 8 |
| 65 | ingame_check 后坐截图人弯着腰 | anim_state 只切指定层,base 层还停在上一个 death | 默认顺序改成 Sprint → Recoil → death | 9 |
| 66 | 实机脚本从 Expedition 直接起,装备页按钮全 none | playModeStartScene 是"当前场景" | 跑前设 Boot;**跑完还原成原来的值(正常就是 Boot),不要设 null**——从当前场景进会有一批服务不初始化 | 9 |
| 67 | 整身生成的头糊成碎块(发刺、鼻子平、骨棱碎、耳机熔在头发里),贴图怎么修都不像 | 整身一次生成,头只分到几千面 | 头单独出四视图(只有头颈+耳机,平光+结构两套)单独生成,在 Blender 拼到身体上(Rook 参考实现 character-art-lab/tools/rook_assemble.py) | 3 |
| 68 | Blender 里头盔/小件好好的,Unity 里边条和高光全黑 | 面朝里,Blender 默认双面看不出,Unity 剔除背面 | 生成件逐面检查法线朝外;进 Unity 前开背面剔除渲一遍 | 8 |
| 69 | rig_build 拉伸门"全过",减面后又不过 | p99 是全身顶点百分位,高面数的头不受拉伸,把百分位稀释了 | 比较拉伸门时面数要一致;看 deform_crops 原图 | 6 |
| 70 | 换了头的大小/位置后表情鼻梁双线鬼影 | 表情底图是在旧头上画的,和新几何错位 | 新旧 face_front 原始渲染做 ECC 仿射(ROI 偏移换回整图坐标),warpAffine(WARP_INVERSE_MAP) 把所有表情对到新头,残差 <0.5px | 7 |
| 71 | 贴图归色后游戏里布料满身碎斑 | Tripo 几何高频皱,ToonLit 硬阈值把每道皱都切成色块 | 平滑法线:代理网格先焊 UV 缝再加权拉普拉斯,按顶点对应写 custom normals,只选布料/头发区(rook_normals.py);别用按贴图逐点选+DataTransfer 最近面,会出斑 | 6 |
| 72 | 拼装参数说头 0.19H,审核量出来 0.16 | rig_build 会重新归一化身高,拼装值≠成品值 | 比例只在成品 rig 上量 | 5 |
| 73 | 宽袖弯肘下半截撕开、远距权重几百个都在袖子上 | Tripo 把约一半上臂权重刷满整根袖子到袖口 | sleeve_flood.reweight 按沿手臂位置重刷,袖口加 sleeve_chain | 6 |
| 74 | 平滑后深蹲/跑步大腿拉伸翻倍、举手袖子拉伸翻倍 | 外套和裤子、袖子和外套焊成一张网,双向扩散串层 | weight_smooth.rank 单侧扩散 + extra_passes 只在布料区宽平滑 | 6 |
| 75 | 待机时腋下袖子和外套前襟之间一块纯黑楔,无光照下是靛蓝里子 | 两片布挨着不共用顶点,权重不同,手一收缝张开,描边壳背面透出 | weight_smooth.near_weld;same_tag 只给布料区;Unity ToonLit 拍两侧腋下特写验 | 6、8 |
| 76 | 手从袖子里剔掉后手指权重变成脊柱 | 剔出来的手落进"外套躯干剥手臂权重"的规则 | 剔出的手单独记集合,所有剥离规则跳过 | 6 |
| 77 | 胶片条每帧一样 / 永远是绑定姿势 / 拍的是上一次的姿势 | SampleAnimation 对 Humanoid 在编辑器里只生效一次;Animator 在子节点上时采根节点无效;编辑器下蒙皮不随骨骼即时重算 | film_strip.cs 改用 AnimationMode 采 Animator 所在节点 + 预热一次 + forceMatrixRecalculationPerRender | 8 |
| 78 | 借来的 fold_arms 抱臂时手摊平、指尖外翘像劈掌 | 动作按 Wren 身材做,宽袖撑粗前臂,手不收进胳膊 | 借别人的手部接触类动作先拍特写;Vesper 撤掉 fold_arms 只留 look_around | 8 |
| 79 | 身高比例按"旧主角"换,结果矮 1% | hero_swap 以当前 Hero 里的模型为基准,现在是 Rook(0.99 倍宇航员)不是宇航员 | 换前从 git 历史取宇航员版 Hero.prefab 量高(3.649),按它算目标高度 | 8 |
| 73 | 带尾巴/长吻的角色竖图放不下 | 侧面宽度接近身高 | 四视图改 1024×1024 方图(sheet.size/top 跟着改),人形 body.txt 换成角色专用 prompt | 1 |
| 74 | 宽体角色跑步肚子和围裙下摆被腿撕开 | Tripo 把大腿权重刷到肚子中间 | `rig.upleg_cut` 渐隐给 Hips,且必须在接缝平滑之后再复核一次(平滑会扩散回去) | 6 |
| 75 | 左右不对称的义肢肩轴歪 | 左右平均把机械臂肩点挪了 5% | `rig.mirror_skip` 跳过手臂;机械件用 `hard_skin` 按段硬绑 | 6 |
| 76 | 躯干剥了手臂权重后手掌开黑洞 | 手掌贴肚那面没被连通识别收进手臂 | `sleeve_flood.keep_hand_dominant`;黑色 = Outline pass 画出的背面,说明网格破了 | 6、9 |
| 77 | 人形动画手臂插进大肚子 | 动画手臂垂到贴身,短臂宽体角色进肚子 | 改该角色 Avatar 肌肉范围(HumanLimit z=Down-Up,上臂 -25、锁骨 -5),不改动画不改网格 | 8 |
| 78 | 深眼窝外悬眼睑的角色闭眼格残留眼白 | 眼睑内侧面被法线/射线/后脑门全排除 | `face_swap.py --force-ellipses ... --force-ymax` 强制纳入眼眶椭圆内的面 | 7 |
| 79 | Chrome 下载卡住,Downloads 只有 .tmp | 浏览器等下载确认 | .tmp 读 glTF 头 12 字节,长度字段等于文件大小就是完整 GLB,直接拷走 | 3 |
| 80 | 改 HeroPreviewShow 的 Playable 对装备页没效果 | 装备页预览走 HeroPreviewAnimatorController | 先在 Play 里读 Animator.runtimeAnimatorController 确认走哪条 | 9 |
| 81 | 机械臂/硬件在错的位置弯、看着像拧碎 | Tripo 自动摆骨的肘腕离硬件关节轴 10cm 级 | 按深色关节环测中心,`rig.bone_overrides` 放骨;硬件按段整块绑 | 6 |
| 82 | 改了骨点/重建 FBX 后 Unity 里手臂拧成麻花 | .meta 里的 Avatar skeleton 还是旧骨向 | 每次换 FBX 都重跑 enforce_tpose(不只 avatar_check);硬件手臂 armTwist=0 | 8 |
| 83 | 握枪是反手或手背压在枪上 | 指骨前后摆反 / 非人手的指节排布 | `rig.finger_mirror` 镜像另一只手;仍偏就 HeroGunStyle.GripRoll 校准,实机看手 | 6、9 |
| 84 | 顶肩的枪型把大手臂的肘折到头顶 | Butt 锚点离肩太近 | 单手模式所有枪型走握把锚点 | 9 |
| 85 | 装备页看不到长吻角色的脸 | 预览相机在头下方 ~14°;待机动作仰头 | 选平视待机;另做头颈下压的预览专用待机,只给 HeroShowcase | 8 |
| 86 | 动画 FBX 换 Avatar 报 hierarchy 不匹配 | 只有骨架的 FBX 被 Unity 吞掉根节点 | 导出时加一个空物体兄弟节点,保住 `<Name>_Armature` 层 | 8 |
| 87 | rig_build 区域参数总是差一点 | 权重阶段网格还没最终归一(Tuba 1.11 倍) | 新参数用 final_space;旧参数是按当时空间试出来的,别混用 | 6 |
| 81 | sol 按"6.5 heads"出四视图实际约 8 头身 | sol 默认画立绘比例 | 写"头占身高 X%"并 PIL 量；+12% 只给 4%，直接写"现在 0.13 要变 0.15" | 1 |
| 82 | 无袖上衣抬手时袖窿布被拽成袖子 | Tripo 给袖窿附近上衣刷了手臂权重 | `rig.garment_arm_strip` 按位置剥（肩关节内侧），absx_fade 软过渡；别按颜色挑（夹克炭灰≈上衣黑） | 6 |
| 83 | 覆盖旧角色 FBX 后 Avatar isHuman=False | .meta 里旧 humanDescription 引用了新模型没有的骨 | 先清空 humanDescription 设 Generic 再设 Human 重新自动映射，再 enforce_tpose | 8 |
| 84 | 改了外部 basecolor.png 渲染没变 | rig blend 里贴图是打包的 | 改贴图走 rig_build --texture | 6、7 |
| 85 | 表情丢痣 / happy 画成睁眼 | sol 重画整脸 | 闭眼 prompt 写死无虹膜无眼白；痣从 neutral 移植 | 7 |
| 88 | 硬件手/机械手"用指尖夹着枪" | 持枪按人手算掌心+弯手指,硬件拳不会弯 | 拳心挂点 GripSocket(+Z 枪管、+Y 枪顶),持枪走挂点分支、不弯手指;手腕伸直反推枪位置;实机从手背/拳心/正面三个方向看 | 9 |
| 89 | 拳头下伸出一根黑杆 | 拇指权重被 Tripo 刷在前臂,手一转被拉长 | 拇指球锁到手 + hard_skin_vote 去孤岛;用"弯腕 45° 找拉伸边"脚本定位 | 6 |
| 90 | 实机脚本卡在简报室进不去远征 | 测试账号体力耗尽(弹 UINotEnoughStaminaPopup) | 用 StaminaService.GrantFromAdAsync 补(等同看广告),别改存档 | 9 |
| 91 | 5.5 头身做到绑骨被勾哥否("没法接受,正常头身比"),整轮作废 | 套了 Rook 的 5.5;老人/高大角色 Q 化 | 阶段 0 问头身比时给出对照(Rook 5.5 / Vesper 6.5 实物图),不默认沿用上一个角色 | 0、1 |
| 92 | sol 改头身比"放大 1.4x"只动了 15% | 百分比描述 sol 不认 | 写全身地标坐标(下巴/肩/腰带/裆/膝占身高比例),量格式模板得出,一轮到位;侧/背同一组地标 | 1 |
| 93 | 分体拼头后领口一圈锯齿碎片、旧胡子残留、橙色色带 | 按贴图颜色删旧头:颜色判断在领口必漏必多 | 先按旧帽子对齐新头,再用新头"皮肤+帽子"的切片半径删旧头;领口乱涂交给贴图层按 3D 位置重染,不在网格上按色删 | 3、5 |
| 94 | Unity 里新脖子和领子之间一圈黑块(双面时是白块) | Tripo 领子是单面壳,背面露出;ToonLit 剔除背面后看到描边色 | 新脖子侧向加宽+伸长塞进领口;立领加一层反向内壁(内缩 0.8mm,2mm 会在边沿露黑线) | 5、8 |
| 95 | 拉长脖子把山羊胡也拉长 | 拉伸按高度一刀切 | 胡子(前方顶点)单独 goatee_stretch | 5 |
| 96 | 斜挎背带举手/跑步时被拽成大片 | Tripo 给背带刷了手臂/大腿权重 | rig.colour_lock 按皮革色锁脊柱,vote 补阴影边;跳过手套(hand_max)和前臂(forearm_dist) | 6 |
| 97 | 无袖马甲举手时侧片被拽成翅膀;收紧后肘内侧又冒黑刺 | 马甲按色剥手臂权重后,远距修剪把脊柱权重也删了、兜底退回手臂;A-pose 肘内侧和马甲侧边网格焊在一起 | garment_arm_strip + far_dist_torso 0.14 + split_welds 删焊接三角;worst_verts.py 列最差顶点定位 | 6 |
| 98 | 背枪挂 Spine2,预制体里在背上,一播动画就转到左侧竖直 | 按 FBX 绑定姿势算的局部变换;Humanoid 播放时 Spine2 自转和绑定姿势不同 | 在动画姿势(Breathing Idle)下算挂点再写回 prefab(tools/harrow/unity_rifle_mount2.cs);用胶片条验收,不看 prefab 静态渲染 | 8 |
| 99 | 换主角后 Harrow 变成单手持枪、装备页做 Tuba 的验货动作 | hero_swap_keepall 把上一个主角的 HeroGunStyle/HeroShowcase 复制过来 | 换完删 HeroGunStyle(除非该角色要单手),HeroShowcase 改成本角色的 idle+性格动作 | 8 |
| 100 | 背挂长枪挂在一根脊柱骨上,驼背/跑动时下半截悬空、侧面看是隔着身体的竖杆 | 单骨挂点只跟胸转,下端不跟髋 | 上贴点挂 Spine2、下贴点挂 Hips,AimConstraint 让枪身每帧从上贴点指向下贴点;贴点在本角色待机姿势下按背部表面量(tools/harrow/unity_rifle_sling.cs) | 8 |
| 101 | 改了脊柱前弯的动画,人看着站在脚跟上、往后仰 | 人形动画的身体朝向(RootQ)取骨盆和胸口的平均,脊柱前弯 → 骨盆后仰、腿往前伸;改 RootT 没用 | 同时把 RootQ 往前俯仰补偿(Harrow 脊柱 -0.17 配 14°),用"髋部在脚踝前后多少/身高"量到接近原动画 | 8 |
| 102 | 重建 .anim 后装备页轮播变成别人的动作 | 脚本先 DeleteAsset 再 CreateAsset,GUID 变了,HeroShowcase/AOC 引用断 | 覆盖已有资产用 EditorUtility.CopySerialized 保留 GUID | 8 |
| 103 | 动作 FBX 导进来人躺着/腿全坏,数值审计却说膝盖正常 | 动作 FBX 的 avatarSetup 改成 CopyFromOther 借了模型 avatar,骨架静止姿势和模型不一致;之后在坏结果上叠 leg_fix / Blender 重烘焙补丁越修越坏;knee_probe 只量腿不量整体朝向 | 动作 FBX 一律 CreateFromThisModel 自建 avatar,靠 Unity 肌肉空间重定向(Wren 就是这样);审计必看正侧全身渲染,人不在画面里就是朝向坏了(Rook2 10-23) | 8 |
| 104 | eval 里 `EditorApplication.delayCall += SaveAndReimport` 永远不执行 | 无焦点编辑器不跑 delayCall | 同步 `imp.SaveAndReimport()`,`EVAL_TIMEOUT=300 bash ucli.sh eval …` | 8 |
| 105 | 预设 idle/walk 到角色身上两腿交叉/内八,Blender 里源动作脚距正常;Enforce T-Pose 跑过也没用 | Unity MakePoseValid 只把腿摆进合法范围,动画 FBX avatar 腿外展 12°、模型 avatar 6°,肌肉重定向把差值当成内收 | 模型和动画 FBX 的 skeleton T-pose 腿部都强制拉直到正下方、脚尖朝前(character-art-lab/tools/rook2/leg_tpose.cs),零肌肉姿势 ankleSpread/hip=1.00 才算过;改完重生成所有派生 .anim(Rook2 10-23) | 8 |
| 106 | 待机时手臂僵硬外撑、肘外弯、手垂在大腿前;与 Wren 并排一看就假 | 同 105 的手臂版:两份 avatar 手臂/手 T-pose 差异变成每个动作的恒定偏移;Enforce T-Pose 不管这个 | `eval/canon_tpose.cs` 对模型 FBX 和每个动画 FBX 都跑;验收=`fullbody.cs` 正侧背 3/4 四视图和 Wren 同机位并排(Rook2 10-24) | 8 |
| 107 | 规范 T-pose 后空投舱里角色背对镜头,渲染板却正常 | Unity 人形约定面朝 +Z 时左侧在 -X;脚本把左髋→右髋定成 +X,人形参考系转 180°;audit 相机跟着 transform.forward 所以看不出 | canon_tpose 左髋方向=-X;改完必跑 `eval/facing_probe.cs`(零肌肉 LHand.x<0、toes.z>0 = FACING OK);改 avatar 后舱内/挂点类 clip 全部重解(Rook2 10-24) | 8 |
| 108 | 脚尖点地/脚跟离地,离线板子只看出一点,实机明显 | 模型 avatar T-pose 脚掌俯仰 37.5°、动作 avatar 15.9°,差 22° 转嫁到每个动作;两副骨架问题的脚部版 | 不再做两份 avatar:动作烘到模型骨架(05 §6.8)+ CopyFromOther;`eval/foot_probe.cs` 待机脚掌俯仰应≈模型绑定姿势(Rook2 40°)(10-24) | 8 |
| 109 | 动作 FBX CopyFromOther 模型 avatar 后人躺倒/下沉 9 m | 动作 FBX 只有骨架一个顶层对象,Unity 把唯一顶层节点折叠成文件根,`Armature`(270° X)这一层没了,借来的 avatar 骨架层级对不上 | 导出动作 FBX 时多放一个空顶层对象(anim_bake_to_rig.py 已加 `Rook2` Empty),Unity 里 `eval/hier_probe.cs` 看到 文件根(0°)→Armature(270°)→Hips 和模型一致才算过(10-24) | 8 |
| 110 | 换脸后下颌/脸缘一圈锯齿深色带,正面不明显、3/4 和侧面明显;改图集改不掉 | face_swap 选面时留下"被脸材质包住的头材质小岛"(Rook2 侧视 5k px),它们用原头 UV 采头贴图下巴底面的暗色,与平光投影图集硬接 | 换脸后用材质 ID 渲染(脸/头两色)找岛;`tools/rook2/texfix/islands.py`:皮肤色小岛并入脸材质并重算图集 UV,被头/发包住的脸碎片退回头材质。不要去改图集或头贴图 | 7 |
| 111 | 耳后露底:侧面从耳廓后能看穿到背带/背景 | Tripo 头模耳后头壳缺口(Rook2 3×6 cm) | `holes.py` 六向剪影 fill_holes 检洞;`earcap_ray.py`+`earcap_build.py` 在洞内侧贴顺表面的深发色卡,权重抄最近顶点;复验洞数为零再导 FBX | 5、6 |
| 112 | 衣服上的细条纹/饰线(piping)糊成断线、双线、拖影;贴图上再怎么投影/重画,受光后仍像污渍 | Tripo 把四视图里 2 px 宽的线糊了;2K 贴图上一条线只有 3 纹素,贴图路线无解(Rook2 试了 15 版) | **饰线走几何**:`tools/rook2/texfix/piping.py` 沿设计图投到模型的 3D 折线生成贴布色带(UV 指纯色纹素);贴图上旧花纹**全部删掉重铺**(`suit_white3.py`,保护区按纹素 3D 位置划,不按颜色/尺寸猜)。勾哥口径:永远用最干净的做法 | 5 |
| 113 | 头贴图"脏"其实是设计 | Wren 的 `tex_clean.py` 在 Rook2 头上标出 2.1%,全是胡茬和耳廓阴影 | 头部不跑 tex_clean;先看 dirt_flags 渲到模型上再决定 | 5 |
| 114 | Blender 里几何饰线/补片都在,导进 Unity 一半不见 | 面朝向错:Unity ToonLit 背面剔除,Blender EEVEE 默认不剔除,所以 Blender 看不出 | 生成贴布几何时按布面法线定每个面的朝向(`dot(face.normal, surface_normal) < 0` 就翻),不要按坐标符号猜;导入后在 Unity 渲染一遍再算过 | 5、7 |
| 115 | 待机看着"上臂夹躯干、肩压低",调上臂 Down-Up/Front-Back 两轮都没改善 | 根因在锁骨:Shoulder Down-Up 均值被重定向压到 -1.2 以下(超范围)、Shoulder Front-Back 前卷;上臂值其实和 Wren 一样 | 先用 `tools/rook2/pose_tune.cs`/`muscle_means.cs` 把肩+上臂六个肌肉均值和 Wren 同类 clip 并排对数,再用 Wren 的 clip 套到本角色上做判别(clip 问题还是身体问题),定位到哪块再调;全套动作都塌肩就回 avatar 肩骨 T-pose 根修 | 7、8 |
| 116 | 6.5 头身角色整身生成,头只有 3~4 千面,眼睛成两道缝、唇软(Vesper gen-1,同坑 67) | 头占身高 15%,60k 面按面积分配 | ~~分头~~(10-26 改):整身 200,000 面生成 + `protect_decimate.py` 保脸减面到 58,000。Coda 实测头 22,944→11,213、脸前部 2,460→2,470,脸特写 SSIM 0.9745,上身衣服白模 SSIM 0.938(身体用 meshoptimizer、头用 collapse),无拼缝。10-24 那次"20 万面整身试"只看了头面数、没做保脸减面,所以判错了 | 0、3 |
| 117 | sol 改头身比每轮只给目标差 1/3,三轮到不了 | sol 对比例描述不敏感,数字和百分比都一样 | PIL 以领口为轴缩身体做 mock + sol 只融缝(01 §1.4) | 1 |
| 118 | 侧/背视图头比 front 小 30% | 图 3 喂了 9 头身转面图,比例被它带走 | 侧背只喂 front+设计稿;头高不一致同样走 mock 对齐 front 的领口/肩线 | 1 |
| 119 | 分头角色换头后,Tripo 身体的长发与上背/臀部融合成一体,删掉旧发就是洞,压平/成膜/切平五轮都不收敛(Vesper 10-25) | 整身生成时长发贴着背,Tripo 把发和背做成同一张壳,背面没有独立表面 | 分头角色的**身体**用去长发的四视图生成(sol edit 把长发剪成下颌长度短 bob、背面补衬衫/背心),头照旧单独生成;换头只做:领口 bisect 切平 + 脖子收进 + 材质合一 | 1、3、6 |
| 120 | 换头后脖子穿出领口/撕裂、领口顶一排白齿 | 脖子中心与领口中心偏 6 mm 还整体放大;脸材质顶点没跟着平移;按面中心删领口留锯齿;头自带领子上的肤色面被当脖子留下 | 领口用 bisect_plane 在 cut_z 切平;头部 z<cut+0.03 的**全部**顶点(含脸材质,UV 不动)平移到领口中心再绕中心径向缩 k(逐 15° 分箱 脖半径 ≤ 领口半径−0.002),smoothstep 到 0.85 衰减;neck_keep=0 | 6 |
| 121 | 侧裙片用 skirt ring 按颜色分类:手套/靴筒/低饱和大腿皮肤进裙子,橙边/黑片进不去,抬手裙片飞条、深蹲跑步碎片 | 三色裙片 vs 黑手套/黑靴/低饱和皮肤,颜色规则分不开;arm_keep_radius 0.045 又把手旁裙片排除 | `skirt.thin_max`(沿 −法线射线量厚度,薄片=裙片,Vesper 裙片 p90 0.011、大腿 0.08、靴 0.06)+ `arm_keep_radius 0.022`(只保手套壳和指尖);band_z 下限可放到 0.09(靴筒靠厚度排除);看 labels_board 分类图 + 抬手飞条诊断(位移>0.15 且 rest z<0.6 的顶点应为 0) | 6 |
| 122 | rig_build 跑完没有 <Name>_basecolor.png | 源贴图是 GLB 打包进来的,`img.save()` 写回包不落盘 | 跑完用 `img.save(filepath=...)`(或 save_render)显式落盘,核对尺寸 | 6 |
| 123 | anim_verify 每条动作 worst 恒 9° | rig_build 拉直脊柱/toe_ball/镜像改了骨的静止方向,烘焙搬的是世界增量旋转(网格运动一致),"比骨向"口径对重对正的骨失效(静止差=动画差) | 用增量模式比 D=pose·rest⁻¹(tools/vesper-cur/anim_verify.py 已加,VERIFY_DELTA);骨向差只作 informational | 6.8 |
| 124 | 增量 verify 剩 1.5°(集中在一条腿链) | Blender FBX 导出默认 bake_anim_simplify_factor=1.0 抽稀曲线 | 导出加 `bake_anim_simplify_factor=0.0, bake_anim_step=1.0`(文件变大 2.4 倍);动作 FBX 的骨架对象名要和模型 FBX 的骨架对象名一致(rig_build 出的是 `<Name>_Armature`),并且**一定保留顶层 Empty**:Blender 回读模型 FBX 会把网格挂回骨架下显示 1 个顶层,但 Unity 里模型是网格+骨架两个顶层,动作 FBX 单顶层会被折叠成文件根,CopyFromOther 导入 0 clip(Vesper 10-25 踩过一次) | 6.8 |
| 125 | Tripo Animate 连点 26 预设只到位 5 个 | 一个预设 Retargeting 没结束就点下一个会丢 | 每个预设:搜索框 form_input → JS 点卡片 → JS 轮询页面无 "Retargeting" 再点下一个(30~60 s,fold_arms/cheer 60 s+);导出前 Choose Animations 计数要等于点的数;Downloads 里 .tmp 用 glTF 头长度校验后直接拷 | 3 |
| 126 | Stop-Process 杀自己的 Blender 探针,结果杀了勾哥开着的 Blender GUI(PID 46508,10-23 起) | 只按进程名/猜 PID 杀 | 杀前 Get-Process 看 StartTime,只杀本会话起的;后台探针一律 `timeout` 包着跑,不手杀 | 全程 |
| 127 | 换头角色侧脸"鸟嘴":下巴比上唇缩进 3% 身高(Vesper 10-25 勾哥点名"畸形儿") | assemble 把头 z<0.85 的全部顶点径向缩 k0.80/ky0.84 塞进高领,下巴跟着缩回去;Tripo 独立头下巴本就偏弱,叠加后明显 | 换头后立刻量中线剖面(每 0.005 z 一档的最前 y):下巴尖应在下唇后 ≤0.005;要修就对 z 0.83~0.87、|x|<0.06 做钟形 Δy 前移(皮肤判据用贴图色相,别用"亮度>0.5",会把白高领一起推前),再对底面做边界钉住的 Laplacian 去掉 S 形回折;量 0.835 档时注意最前点可能是高领上沿不是皮肤 | 5 |
| 128 | 背视图里裙片内衬是黑色,Tripo 在小腿后方各生成一块独立的黑色尖顶薄板(游戏里像多出两块黑) | 多视图生成把"内衬可见面"当成了实体 | clay 背视/3/4 视必看小腿后方;按"y>0.06、薄板厚度<0.02、深色"圈面删掉(它和外套侧片连通,按转角线只删折回段);删后小腿皮肤会露出烘进贴图的阴影,贴图层按 3D 位置用同腿同 z 段肤色填 | 4、5 |
| 129 | 肩下头发在游戏里散成一条条缎带、飘 | 不是权重(实测肩下发 99% 已在 HairB),是 prefab_build 给 HairB 的弹簧 stiffness 20 + spring_limits ±45° 太软 | 长直发单链:肩以上两节 stiffness 80 / drag 0.75 / 限 ±8,肩以下两节 50 / 0.65 / ±16;验收用 Gear 页 idle 连拍 8 张 + 性格动作 6 张看整束是否同步 | 8 |
| 130 | 耳朵内一大片黑色碎斑、脖后 "LU" 形黑印(Vesper 10-22 独立头) | 这些面在 VesperFace 材质上,face_swap 从正面投影把耳前头发画进了耳朵 UV;贴图层任何"邻域肤色"判据都抓不到(耳区 75% 像素本来就是暗色),改也会误伤共用像素的头发 | 换脸前把耳朵/脖后的面留在身体材质(别划进脸材质),或换脸时侧向补投影;已入库的只能回 Blender 改材质槽重投 | 6 |
| 131 | Tripo 贴图白袖子满是灰褐脏块、黑色几何带糊成一团 | 多视图投影在袖子内侧/腋下没有参考 | 别修补,整段重绘:tex_posmap + 骨骼权重圈出袖子像素(Arm/ForeArm 主导、t∈[0.10,0.90]),铜甲按"到臂轴半径 + 三角铜色多数票 + 相邻褶皱环"排除(纯 HSV 会漏铜甲阴影面、纯半径会误伤低位甲片),白 #ECECEA 平涂乘弱法线明暗,黑带按 t 与绕臂角 φ 画斜带,gutter 外扩 8 px,posmap 用整三角平移进 tile 别按顶点 u%1 | 5 |
| 132 | 侧裙下摆尖在大动作里被拉成一根黑刺(Vesper 10-25) | 不是 HeroSkirtFollow(lift 只 ±21°、骨长不变),是 rig_build 后下摆仍有顶点带小腿/前臂权重,外加下摆尖角是两片独立薄片岛、完全没有裙骨权重挂在 Hips/小腿上 | 绑骨后加一道审计:Skirt 顶点里 Leg/ForeArm>0.05 的数,和"Skirt<0.02 但 Leg>0.3、离小腿轴>0.055、厚度<0.0164"的岛;前者清非裙权重归一,后者**整岛**改成最近 Skirt_xx_02_Tip 0.55+Hips 0.45(逐点改会撕裂,删岛会缺角) | 5 |
| 133 | 侧裙贴图按"一片平板"写花纹规则,正面糊成黑铜条纹 | Tripo 的侧裙片是前襟+侧后襟的 V 形折壳(约 6 mm 厚),PCA 平面投影把前襟压成一条 | 每个 v 带取截面弧长参数,apex=离身体中线最远点,前后襟各自 u'∈[0,1] 分别定义花纹;apex 两侧铜带随 v 加宽(0.03→0.12)盖住折角处内外面分类抖动;内外面按三角法线与"背离身体的截面法线"点乘投票再 3×3 众数滤波 | 5 |
| 134 | 表情在装备页(脸高 60~90 px)看不出变化 | 表情描述按"收着"写,眉眼嘴改动都小 | 描述每格至少两项大幅变化(眉高/角、眼开合/形、嘴形/开合),身份锁句里"眉形位置不变"要放开、闭眼格去掉虹膜;验收用 64 px 脸高的 contact_small 读情绪;focus 要和 jealous 分开:睁大直视+眉平压不聚拢+嘴水平抿;sol 并行 10 张会 429,串行;1254 的缩回 1024 留原图 | 7 |
| 135 | Gear 展示动作候选别只看名字 | Tripo 预设 WaveGoodbye01 retarget 成坐姿、Complain01 是蹲冲甩臂 | 先用 Blender -b 对 rig blend + Anims.fbx 每条 8 帧出 contact sheet 再选;Vesper 这类冷角色选 LookAround/Clap/StandingRelax | 8 |
| 136 | 表情图集 2048×1152 进 Unity 实际是 2048×1024 | TextureImporter nPOTScale=ToNearest 把非 2 次幂边缩了 | 4×3 格 UV 是比例取样所以不错位,只损失竖向精度;要全精度得把 .meta 的 npotScale 改 None(10-25 未改,与旧图集口径一致) | 8 |
| 137 | 表情按"幅度大"写出来全是凶相(Vesper 10-26 勾哥:"太 mean 了") | 把人设的"冷"理解成"凶",angry 龇牙、jealous 撇嘴、focus 盯死 | 先从手册性格句定情绪底色(Vesper=从容+一点玩味),勾哥只要 neutral/blink/wink/happy/smug 五格;其余槽填 neutral 别留凶脸;出图前先把十一格文字方案给勾哥批再花点数 | 7 |
