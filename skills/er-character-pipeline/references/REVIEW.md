# 复查记录

## 2026-10-07 首版复查:按"下一个角色 Harrow"逐步走一遍

方法:把 skill 当成第一次用,按 SKILL.md 的阶段顺序逐步执行。不花 Tripo 点数、不进 Unity Play、不写工程文件,所以:能离线跑的脚本全部用 Wren 的真实中间产物实跑(Tripo 的 rig/gen GLB、四视图、表情图);Harrow 用一份按手册写的草稿配置跑所有"读配置→生成东西"的步骤;Unity 的 eval 脚本在编辑器里做"只编译不执行"检查(包在一个从不调用的 lambda 里,零副作用);要拷进工程的两个 C# 模板用 Unity 自带的 Roslyn 离线编译。测试产物都在会话 scratchpad 的 `skilltest/`,没有写进 character-art-lab 或工程。

### 检查了什么、结果

| 检查 | 结果 |
|---|---|
| 所有 Python 脚本 `py_compile`、`-h` | 全过 |
| 所有 Blender 脚本无参数运行 | 都打印用法,无 traceback |
| 所有 bash 脚本 `bash -n` | 全过 |
| `rig_build.py` 用 Wren 配置跑 Tripo 原始 rig-2 GLB | 各部件计数和 10-07 交付版逐个相同(马尾+刘海 4942、裙 4369、罐 339、背带 1045);9 个形变姿势 body p99 全 ≤ 1.75(最差 arms_overhead 1.64);9 秒跑完 |
| `rig_audit.py` | 新 rig `RIG_AUDIT PASS`;**10-07 交付版 FAIL(far_body 1941)**,见下"发现的真 bug 1" |
| `deform_sheet.py` | 出图正常,9 个裁图 Opus 看过 |
| `face_render.py` | 从 Head 骨自动算出投影 0.8822/0.1629,和 10-07 手调的 0.8826/0.1633 一致 |
| `face_atlas.py` 用 10-07 的 10 张表情 | 相位相关量出全部约 7px 的竖直偏移(那批表情是在略不同的底图上画的),自动配准,PASS |
| `face_swap.py` + `face_qa_sheet.py` | 选面 556,后脑去掉 3;闭眼格眼角干净,后脑无图集颜色;Opus 看过 |
| `export_fbx.py` 回读 | armature 缩放 1、高 1.0、材质名打印,FBX_CHECK PASS;链末端 `*_Tip`、Prop_R 都在 |
| `render_views.py` + `compare_board.py` | 四视图和模型渲染逐格同向(left 视图脸朝画面左),对照板正确 |
| `clay_face.py` | 无骨 GLB 用头身比推头部中心,出 7 个角度 + 全身 |
| `tex_extract.py` + `tex_clean.py` | Wren gen-1(8K、已知手臂脏):手肘大脏块清掉,只剩手肘下一点淡灰(和 10-07 人工结果一致),22 秒;gen-2(2K)只标出 0.37%,基本干净 |
| `sheet_check.py` / `sheet_finalize.py` | Wren 候选图门全过;finalize 后 `--final` 四张 ALL PASS |
| `silhouette_iou.py` | Wren 平光定稿 vs 结构参考 0.944/0.983/0.969/0.964 → 门定 0.93 |
| `crop_compare.py --hsv` | 正常 |
| `build_prompts.py` 用 Harrow 草稿配置跑全部 5 种模式(四视图 ×4、修图、圆脸 ×2、结构参考 ×4、表情 ×7) | 无未替换占位符,无 Wren 残留词;第一次跑因控制台编码崩(见下) |
| `sol_image.sh --dry` | 命令形态和 10-07 实际用的一致(stdin、`--skip-git-repo-check`、多个 `-i`) |
| `spring_spec.py`(Wren、Harrow 两份配置)+ `UCLI_DRY=1` | 10 条 eval 命令占位符全部填满;Harrow 没有弹簧链时 SPRING 为空也能走 |
| Unity eval 只编译(`UCLI_COMPILE_ONLY=1`) | import_setup、avatar_check、materials_setup、prefab_build、render_views、hero_swap、weapon_mount、fix_animator_node、anim_state 全部 COMPILED;enforce_tpose 编译失败是预期的(依赖的 CharacterEnforceTPose 还没拷进工程) |
| `templates/unity/*.cs` 用 Unity 6000.3.5f2 的 csc 离线编译 | CharacterEnforceTPose + CharacterFaceController 编译通过(对照:工程里的 WrenEnforceTPose 同条件 0 错误) |
| `ucli.sh status/guard/eval` | 对真编辑器只读调用正常;占位符没填会拒绝执行 |
| 脚本里有没有写死 Wren 的路径/数值 | 只剩注释里的历史说明和可被环境变量覆盖的默认路径(Unity CLI、工程目录) |

### 复查中发现的真 bug(10-07 交付的 Wren 也受影响)
1. **后脑不跟头转**。远距权重修剪(离骨段 > 12% 身高就删)没有跳过 Head 骨;Head 是头骨前面一根细线,后脑和大头发天然离它远。交付版 1941 个后脑/头发顶点的 Head 权重被删,全落到 Neck。修:rig_build 修剪跳过 Head/HeadTop_End、归一化后重复修剪、全被剪光时退回最近的原骨;rig_audit 去掉 Wren 专用的"配件盒子豁免"(正是它把这个 bug 藏住了),改成按权重判次级顶点。修后 far_body 1941 → 13,head_turn p99 1.047 → 1.022。
2. **闭眼表情眼角白三角**。10-07 的"后脑保护"(法线点积 < 0.2 或在脸中心后面 1cm 就删)实际删掉的是 121 个脸侧/眼角多边形,不是后脑。用交付的 `fix-head2/wren_rig_face_fixed.blend` 渲 blink 格,两只眼外角都是白色眼白三角。修:只删法线真正背向脸的面(dot < 0),QA 加后脑一张。
3. **SpringBone 挂在没有子骨的链末端**。交付 FBX 里 12 根次级骨是叶子(马尾第 3 节、罐子、裙摆第 2 节),SpringBone 找不到子骨时用兜底方向。修:每条链加不变形的 `*_Tip`,导出保留非变形骨。

建议:按本 skill 对 Wren 重跑阶段 6~8(rig_build → face_swap → Unity 重导),把这三个问题从游戏里去掉。本次没做(不写工程)。

### 复查中修掉的 skill 自身问题
- 控制台是 cp1252,vault 路径有中文,所有 print 崩 → `_cfg.py` 和独立脚本统一把 stdout 设成 utf-8。
- FBX 导出目录不存在时报错 → 导出前建目录。
- 形变测试的扭腰/转头绕骨骼局部轴转,实际是仰头 → 改成绕世界 Z。
- 表情对齐门用像素差,分不出"重画噪声"和"脸挪位":平移 16px 的差值还比一张合格的露齿笑小 → 改成相位相关测平移 + 自动配准。
- tex_clean 第一版漏掉手肘最大的脏块(脏块本身过不了皮肤颜色判定)→ 加"手臂区向相邻深灰褐三角形生长"(10-07 的 grow.py 那一步)。
- out_dir 不在 workspace 里时,sol 的保存路径变成 `./../…` → build_prompts 直接拒绝。
- 四视图主体里写着 "cute",对 68 岁的 Harrow 不对 → 删掉;FACE 段加"角色自己的脸部说明优先于家族默认"。
- 斜背的长件(Harrow 的枪)用轴对齐盒子会把背上的衣服一起收成硬件 → rigid 加 `capsule_radius`。
- 驼背角色:加 `straighten_spine` 开关,并在 01 写明体态不画进建模图。
- 表情控制器的枚举是固定 11 个槽位,配置里换名字/顺序游戏里会显示错格子 → face_atlas 警告,文档改成"所有角色同一套槽位,只改描述"。
- materials_setup 的 ToonLit 参数写死在代码里、配置里的 toon 段没人读 → 改成由 spring_spec 从配置填。
- prefab_build 里对 UnityEngine.Object 用了 `??`(编辑器假 null 会让它失效)→ 改成显式判空。
- 实机文档说"出击后再截状态图",但脚本结束就 stop 了 → 状态截图并进 ingame_check.sh。
- UI 按钮名会变 → ucli.sh 加 `buttons` 列出当前屏可点按钮,文档写明点不到时怎么查。

### Harrow 逐阶段走查结论
| 阶段 | 能不能不靠人走完 | 需要勾哥拍的 |
|---|---|---|
| 0 | 能 | 落点;身高相对主角(他高大,配置里先写 1.05) |
| 1 | 能(数值门 + Opus 看图门) | **背后长枪**:识别件,画进模型做 rigid,还是做成单独挂件(手里还会有一把通用枪);**驼背**:建模图按规则画直,体态交给动画——要不要做驼背动画层 |
| 2 | 能 | — |
| 3/4 | 能(验身、核对设置、价格标签都是可判定的) | 点数超 150 时 |
| 5 | 能 | 胡子/皱纹在灰模上的取舍 |
| 6 | 能。没有马尾和裙子:chains 留空、skirt 删掉;枪用 rigid + capsule。注意:有长头发/布料却不建链,审计 far_body 会报(会提示你该建链) | 马甲下摆要不要链 |
| 7 | 能;投影要看 face_calib(帽子、胡子可能让默认框不合适);hair_hue_ranges 留空(灰发低饱和,靠遮挡和法线排除) | 11 个槽位的"收着"版描述 |
| 8 | 能(先拷两个通用 C# 模板进工程,这是代码改动) | 提交与否 |
| 9 | 能 | 血条等共享系统问题 |

### 剩下的风险(没验证到的、可能出事的)
1. **Unity 端只做了编译检查,没在编辑器里真跑**(工程正被另一个会话使用,本次不写工程):materials_setup、prefab_build、hero_swap、render_views、anim_state、ingame_check.sh 全流程、CharacterEnforceTPose、CharacterFaceController。weapon_mount、render_views、fix_animator_node、按钮点击流程的代码是从 10-07 实际跑通的 eval 整理的,其余是按 10-07 报告的做法重写的。第一次用时一步一步跑,每步读返回值。
2. FBX 现在保留非变形骨(`*_Tip`、Prop_R、手指末端等)。Blender 回读没问题,但 Unity Humanoid 自动映射和 SpringBone 在这种 FBX 上还没实测;出问题就把配置 `export_deform_only` 改回 true(代价是链末端又没有子骨)。
3. 门的阈值都只用 Wren 一个样本标定:形变 p99 1.75、表情配准 12px、结构参考 IOU 0.93、脏贴图覆盖率 15%、远距权重 0.1%。换体型差别大的角色(Tuba 2m+ 宽体)可能要调;调了记在本文件。
4. 脸部投影的特征带(眼带、嘴带)是按 Wren 的脸在框里的位置定的。默认框由 Head 骨推算,一般会跟着走,但帽檐、胡子、老人眼皮可能需要手调,所以 face_calib 那一眼不能省。
5. tex_clean 的规则只在 Wren 的暖肤色上验证过。深肤色(Tuba)的 LAB 色相/亮度窗口要先用 `--dry` 看 dirt_flags 再定。
6. Tripo 网页的界面、价格、按钮会变;sol(gpt-5.6-sol)的出图习惯也会变。03 里的价格表和步骤是 10-07 的实测。
7. Unity CLI、工程路径、Blender 路径是这台机器(AW-SuperPineapple)的默认值,换机器要设 `UNITY_CLI`、`UNITY_PROJECT`,改配置里的 `blender`。
8. 已知没解决的游戏侧问题照旧(血条压头顶、按枪型重做握枪开火、远征原点多一个实例、Tripo 动作没接、受击动作失效、鼓腮只是画的),skill 只要求把它们写进报告,不负责解决。
9. 工程里 `Packages/manifest.json` 加 SpringBone 包、`Hero.prefab` 换成 Wren 都还是本地未提交改动;新机器上可能没有 SpringBone 包。

## Vesper 真人(2026-10-07,第二个实跑角色)
长外套到小腿 + 羽织宽袖 + 齐肩短发,和 Wren(短裙双马尾背罐)差别很大,暴露了这些问题,已改:
- **config 示例是 Wren 的比例**:头 0.20~0.22、height_vs_old_hero 0.90 是 Wren 专属。Vesper 照抄差点做成小孩比例(勾哥:"每个角色身高体型不一样,不要硬套 Wren")。阶段 1 前必须问头身比和身高;Vesper 定 5.5 头身(头 0.18~0.19,同 Rook),身高 = 原宇航员 ×0.97。
- **Tripo 绑骨导出选 4K 的 GLB 是坏的**:骨头 NaN、顶点 1e30,rig_build 报 ZeroDivision。2K 导出正常。下载后 inspect 必看骨头坐标。
- **免费重试**:白模页工具栏有 Free Retry(不扣点,旧版留在历史)。第一版嘴往前撅 + 睫毛棱,重试那版脸明显好,值得默认试一次。
- **长外套 = skirt 环,但 Tripo 把外套下摆大面积刷给手臂**(手垂在旁边)。新增 `skirt.arm_keep_radius`(按离手臂骨距离排除手,不按 Tripo 手臂权重判)。
- **宽袖和外套身体分不开**:位置规则 / 软过渡都会在装备页 idle 抬手时把袖子内片留在腰边拉成黑刀片。新增 `rig.sleeve_flood`:从前臂周围按网格连通往上灌(z_cap = 腋下),袖子只留手臂/肩权重,外套身体在 torso_z 内剥光手臂权重。arms_overhead 3.3 → 1.35。
- 外套后开衩离腿近:`radial_min` 0.085 + 颜色 `v_min` 0.20(外套和裤子按亮度分开)。
- face_render 默认投影对短发齐刘海的脸太大(嘴出框),手调 center_z 0.892 / scale 0.20。
- sol 出表情偶尔给 1254 见方,face_atlas 报 size FAIL;缩回 1024 再配准即可(位移 < 3px)。
- **Hero.prefab 会和别的角色会话撞车**:本地 Hero.prefab 是 Wren 会话的未提交版本(含新通用持枪 HeroGunHoldPose)。我恢复成 git HEAD 再换,冲掉了它,用工程外备份还原。以后阶段 8/9 前先问有没有别的会话在改 Hero.prefab;要临时换就先约好、备份对方最新版、测完逐字节还原。HeroDefinition.ModelPrefab 目前运行时没人读,不能拿来切角色。
- ingame_check.sh 在主页点不到 PlayButton(UI 已变),远征这段没跑到,要先 `ucli.sh buttons` 找新名字。

## 2026-10-08 Rook(第三个走完全程的角色,5.5 头身男主,大背包+头盔,无马尾裙摆)
改了什么:`build_prompts.py` + `body.txt` 头身数按 head_ratio 算(原来写死 4.7);`ingame_check.sh` 默认状态顺序把 death 放最后;新增 `eval/hero_swap_keepall.cs`(嵌套预制体实例 + 保留 Animator 节点上全部共用组件)和 `eval/film_strip.cs`(编辑器里拍真实动画胶片条看腰胯腋下)。pitfalls 58~66。
实测阈值:结构参考 IOU 0.970~0.986(门 0.93 宽松够用);脏贴图 1.3%;表情配准 ≤ 0.5px;绑骨举手 p99 1.85、接缝 336/279、远距 197/35 没过,但真实动画胶片条干净——宇航服袖子 A 字下贴着躯干,举手 125° 的拉伸门对这类宽松上衣偏严,两三个角色后再定要不要放宽或改看图门为准。
没验证到的:Tripo 预设动作没导出;装备页预览的 Rook 表情和性格动作没接(要改 HeroPreviewShow,等勾哥)。

## 2026-10-08 晚 Vesper 重绑 + 入库收尾(第一次照 10-08 新方法跑完宽袖长外套)
改了什么:rig_build.py 加 7 个可选开关(sleeve_flood.reweight/exclude_hand/torso_fade、sleeve_chain、skirt.top_ramp、weight_smooth.rank/extra_passes/near_weld、--dump-labels),不配置时 Wren/Rook 重跑 COUNTS+METRICS 逐字节一致;spring_spec.py 认 sleeve_chain 并改打 hero_swap_keepall;film_strip.cs 改 AnimationMode 采样(原版对 Humanoid 不可靠,pitfalls 77)且支持 "fbx#clip"。详见 05 §6.7、pitfalls 73~79。
实测:审计 14/14;拉伸 8/9(举手 1.96);装备页 60 s 轮播、髋高 5.311~5.321、无枪渲染器;远征真实走/冲刺下摆不穿腿不钟形;Console 0 错。
没做到的:性格动作只剩 look_around 一个,手册里的"平掌示意停""两指按太阳穴"工程里没有对应动作,要做得另出;举手 125° 拉伸门对宽松上衣仍偏严(Vesper、Rook 两例),建议改成以看图门为准。

## 2026-10-09 Tuba(第四个角色,第一个非人形:鳄鱼宽体、长吻、尾巴、机械右臂)
改了什么:`rig_build.py` 加 `mirror_skip`、`hard_skin`、`rigid.hsv_any/grow_rings`、`upleg_cut`、`skirt.colour_rule.r_minus_g_min`、`sleeve_flood.sides/max_dist/hips_split_z/keep_hand_dominant/post`、`spine_to_hips`(全部默认关,Wren/Rook/Vesper 行为不变);`face_swap.py` 加 `--force-ellipses/--force-ymax`。角色专用脚本在 `character-art-lab/tools/tuba/`(四视图 prompt、背部串色修补、老花镜生成、一键重建)。pitfalls 73~80。
实测阈值:结构参考 IOU 0.994~0.996;表情配准 ≤ 0.82px;形变 p99 跑步 1.97、扭腰 2.53、转头 2.56、举手 3.29(宽体角色的身体边离骨远,p99 门偏严,以看图为准)。
没验证到的:持枪(左手托枪穿肚子,共享系统待拍板);装备页性格动作没配;Tripo 预设动作没导。
2026-10-09 Tuba 第二轮:rig_build 加 `bone_overrides`、`finger_mirror`、`hard_skin.sphere/final_space/to_bone/hsv_any/rigid_fingers/by_segment`、`arm_far_strip.restore_dist`、`post_smooth`、`sleeve_flood.exclude_white`;这些配置的坐标都是最终空间(probe 量出来的数),内部换算了 1.11 倍(网格在中途还没重新归一)。共享代码新增 HeroGunStyle(单手持枪、GripRoll)。pitfalls 81~87。

## 2026-10-09 Vesper v4（真人重设计：立领无袖上衣+挂肘短夹克+阔腿伞兵裤+姬发长发到腰）
改了什么：`rig_build.py` 加 3 个可选开关，不配置时行为不变：
- `region.any`：多个盒子的并集。长直发贴着后背，头发和后背的深度分界随高度变，一个盒子圈不准。
- `garment_arm_strip {region, absx_fade, skip_s_min, skip_hue, post}`：无袖上衣袖窿附近的布被 Tripo 刷了手臂权重，抬手时像袖子一样被拽起来（勾哥点名）。按位置（肩关节内侧）剥手臂权重给脊柱，absx_fade 做软过渡；skip_s_min/skip_hue 放过高饱和的夹克靛蓝里子。**按颜色挑上衣失败**：炭灰夹克和黑上衣颜色太近，夹克被剥后整片挂在躯干上。
- `post_smooth.seed_tags` + 收尾统一重合顶点权重：按颜色挑点的 post 规则会让 UV 缝两侧的重合顶点读到不同纹素，拆出 507 个 coloc split。
实测：结构参考 IOU 0.948~0.991；审计 14/14（接缝 248/273）；拉伸 6/8，举手 2.19、前平举 1.79——挂肘夹克把手臂和后背连在一起，抬手时里子必然拉长，看图接受；脏贴图覆盖 21%（皮肤纹素本来就少，看图只落在袖窿边，接受）；表情配准 ≤1.1px。
新坑：
- sol 按"6.5 heads"出图实际约 8 头身；四视图要写"头占身高 15%、比参考图头更大"并量像素。头身比一次只给 +12% sol 只给 4%，要写目标数字（"现在 0.13 要变 0.15"）。
- 同一 FBX 覆盖旧角色时，.meta 里旧的 humanDescription（v3 的袖链、下摆骨）留着，Avatar isHuman=False。先清空 humanDescription 再设 Human 让 Unity 重新自动映射，再 enforce_tpose。
- Tripo 贴图在左眼下画了两颗痣（设计是一颗）；改贴图要改 rig_build --texture 的那张，rig blend 里贴图是打包的，改外部 png 不生效。
- sol 画表情会丢痣、happy 会画成睁眼；闭眼表情 prompt 要写死"没有虹膜没有眼白"，丢的痣从 neutral 移植。
- 多会话共用 Unity：Tuba 会话中途反复进出 Play。ucli guard 要在每一步前查，不能只查一次；换 Hero.prefab 前用 SendMessage 约时间。

## 2026-10-09 Harrow(第五个角色,最后一个:68 岁驼背老兵,反戴帽+山羊胡,背后长枪挂件,红脖子白人肤色)
改了什么:`rig_build.py` 加可选开关(默认关):`colour_lock`(按皮革色把斜挎背带/皮带锁到对应高度的脊柱骨,`vote` 邻居投票补阴影边,`hand_max`/`forearm_dist` 跳过手套和前臂)、`garment_arm_strip.absx_fade_z_min/arm_dist_keep/arm_dist_z_min`(无袖马甲:腋下以下侧片零手臂权重,袖窿按离手臂骨距离软过渡)、`far_dist_torso`(宽体躯干远距修剪放宽;12% 会删掉马甲侧边的脊柱权重,兜底又退回手臂=走路时一排黑刺)、`post_smooth.unify_all`、`split_welds`(删掉 A-pose 肘内侧和马甲焊在一起的三角,权重怎么调都会被拉成刺)。角色专用工具在 `character-art-lab/tools/harrow/`(拼头、肤色、长枪、领口检查、Unity 挂枪)。pitfalls 91~99。
实测:结构参考 IOU 0.989~0.991,头部 0.991~0.997;形变 7/7 过门(最差跑步 1.73);表情配准 ≤2.6px;审计 spine_lean 8.3°(驼背拍板)、far_body ~3470(宽体)不过,看图接受。
新坑:头身比要先问清并且给参考比例的实物(5.5 被否作废一轮);"高大"老兵用正常 6.5;挂件按动画姿势挂;长挂件的大小要先给勾哥看再定。

## 2026-10-25 Vesper 当前造型(第六个角色:6.5 头身、黑长直发、两片侧裙片、分头换头)
改了什么:`rig_build.py` 裙子分类加可选键(默认不配=原行为):`skirt.thin_max`(沿 −法线射线量厚度,薄片=裙布,代替颜色规则)、`colour_rule.r_minus_b_max`、`colour_rule.also_sat_min`;`anim_bake_to_rig.py` 导出加 `bake_anim_simplify_factor=0, bake_anim_step=1`(默认 1.0 抽稀曲线给 1.5° 增量误差)并注明骨架对象名/顶层 Empty 规则;`anim_verify.py` 加增量模式 `VERIFY_DELTA`(比 pose·rest⁻¹,门 <1°;骨向差在 rig_build 重对正骨后恒差几度,改为 informational)。换头脚本 `tools/vesper-cur/assemble.py`(bisect 领口、脖子平移+径向缩进、材质合一 4096×2048、VesperFace 保留)和 `qa_render.py`/`probe*.py` 在 character-art-lab,未进 skill。
实测:四视图 0.152~0.156 头身比(mock 法);结构参考 IOU 0.966~0.988,去长发版 0.954~0.971;表情图集 11 格 gate 全 true、shift ≤4px;rig r5 审计 14/14、拉伸 9/9(最差 squat 1.65、run 1.51);anim 增量 0.000°。Tripo 两套身体各 30+20+20 点。
新坑(已进 pitfalls 119~126):整身生成的长发与背/臀融合无独立背面,分头角色身体要用去长发四视图重生成;换头脖子要含脸材质顶点一起平移+径向缩进、领口 bisect;侧裙片颜色分类分不开手套/靴/皮肤,用厚度判据;rig_build 打包图 img.save 不落盘;verify 改增量;FBX 简化;Tripo 预设逐个等;动作 FBX 顶层 Empty 必留。
