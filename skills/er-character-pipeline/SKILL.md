---
name: er-character-pipeline
description: ER(Extraction Raider)角色从定稿设计图到游戏里能跑能打能看的完整管线——建模四视图 → 结构参考 → Tripo 网页生成白模/上贴图/绑骨/预设动作 → 灰模与贴图验收 → Blender 修骨加马尾裙摆背包链 → 换脸表情图集 → Unity Humanoid 入库(T-pose、ToonLit 厚涂参数、SpringBone、换主角、枪挂点)→ 装备页+远征实机验收 → 归档。每步有脚本和可判定的门。只要用户说"做角色模型 / 出建模四视图 / 上 Tripo / 角色进 Unity / 给某角色建模绑骨 / 换主角模型 / 给 Harrow(Vesper/Tuba/Coda…)做 3D / 角色表情换脸 / 马尾裙子物理"或任何 ER 人物从图到 3D 到游戏的活,都用这个 skill;只修一个已入库模型的着色也先看这里的阶段 8。
---

# ER 角色模型管线(设计图 → Tripo → 绑骨 → 表情 → Unity → 实机)

Wren(2026-10-07)第一次把整条路走通,这个 skill 是那一天所有成功做法和踩过的坑的固化。照着走,每个阶段有入口条件、要跑的命令、能判定成败的门、常见失败和修法。细节在 `references/`,脚本在 `scripts/`,prompt 模板在 `templates/`。

## 先做这三件事
1. 读 `references/00-首次接手与输入.md`,把 checklist 过一遍(真源、环境、权限、落点、Unity 有没有人在 Play)。
2. 复制 `templates/char_config.example.json`(Wren 的真实参数)到 `{workspace}/configs/<slug>.json`。所有脚本只读这个文件;每个阶段产出的真实文件名填回 `files` 段。
3. 读 `references/pitfalls.md` 的 40 条坑,知道哪些地方会出事。

## 总纪律
- **先回看 Wren 再动手(10-24 勾哥定,强制)**:Wren 是目前做得最好的角色。每个阶段、每个子步骤动手之前,必须先翻 Wren 当时这一步是怎么做的——`references/0X` 对应章节、`templates/char_config.example.json`(Wren 真值)、`scripts/` 里对应脚本的 docstring、`references/REVIEW.md` 和 pitfalls 里标 Wren 的条目,以及 Wren 的真实产物——然后严格照 Wren 的做法、Wren 的脚本、Wren 的门来做。不许先按自己的想法发明一条新路再回头对;只有 Wren 的做法在当前角色上**实测**走不通(跑过、有证据),才允许偏离,偏离时在交接文件里写"Wren 做法 / 为什么不通 / 改成什么",并补进 pitfalls。Rook2 两天里 avatar、脸图集、贴图清理各发明过一轮新路,都走了弯路,这条就是为此立的。
- **头小的角色:整身高面数生成 + 保脸减面,不分头(10-26 Coda 验证,取代 10-24 的"直接分头")**:`sheet.head_ratio` ≤ 0.17(约 6 头身及以上)的角色,整身 6 万面生成头只分到 3~6 千面,脸前部几百面,这是 Wren 之后人物精度掉下来的根因;以前的解法是分头换头,而 Rook2/Vesper2/Harrow/Coda 的领口碎片、脸岛、耳洞、颈断口、长发融壳、鸟嘴下巴大多出在换头这一步。现在的做法:阶段 3 **整身一次生成 200,000 面**(H3.1、Ultra、贴图关、Triangle,其余照 03 章),上贴图后用 `scripts/blender/protect_decimate.py` 焊 UV 缝 → 圈脸前部+双手锁定 → 身体 meshoptimizer、头 collapse,合计减到 58,000 → 投原模法线。Coda 实测(导出文件回读):194,895 → 58,000,头 11,213 面(6 万直出版 6,205)、脸前部 2,470(直出版 782,Wren 1,710),脸特写对 20 万原模 SSIM 0.9745,没有拼缝。**减面算法(10-26 第三轮定案)**:身体用 meshoptimizer `simplifyWithAttributes`(只保留原顶点、按法线和 UV 误差挑,硬边和衣服结构线不被揉软),头用 Blender collapse(会重新摆顶点,卷发、下颌、耳朵这类圆形不出锯齿),脸前部和手(半径 0.45 头高)锁定不减。对比 Coda 20 万原模:上身白模 SSIM 0.884→0.938、下身 0.912→0.943、脸 0.9745,马甲包边、扣环、袋盖边和原模一样利落,不比 6 万直出软;旧做法(纯 collapse)留下的衬衫斑驳和背面扣环拖影消失。试过不行的:按折痕加保护权重(collapse 把预算从平面抽走,出星状长条三角,全部变差);纯 meshoptimizer(头发轮廓和下颌变锯齿,脸 0.928)。65k 面能再好一点(上身 0.949),不是必需。meshoptimizer 1.3.0 简化器已放在 `scripts/blender/vendor/`,要 node,不用 npm 安装;`--method collapse` 保留旧做法。头部预算占比 `--head-share 0.193` 只在 Coda 上标定过,双马尾、长发角色用前先看头部三角数是否合理。**只验证到模型阶段**:绑骨、换脸、Unity 入库还没在这条路线上跑过,跑到哪步出问题照"先回看 Wren"的规矩补。剩下和 Wren 的差距在贴图(Tripo 把明暗斑烘进了脸部皮肤),靠阶段 4 的 tex_clean 和阶段 7 的脸图集解决,不是几何问题。head_ratio ≥ 0.20 的角色(Wren)照旧 6 万面单体直出。分头换头降为备选,只在整身路线实测走不通时用,用前读 05 的 assemble 段和坑 93/94/110/111/119/127。
- **长发角色万一要分头,身体必须用去长发的四视图生成(10-25 Vesper 定)**:整身生成的长发会和上背/臀部做成一体壳,背面没有独立表面,换头后删发=洞,压平/成膜/切平五轮都救不回;正确做法是 sol edit 把定稿四视图的长发剪成下颌长度短 bob(背面补衬衫/背心)再出结构参考重生成身体(Tripo 约 1 小时),头单独生成后换头只做领口切平+脖子收进+材质合一(坑 119/120)。
- **四视图头身比用 mock 法,不靠 sol 多轮(10-24 Vesper 定)**:sol 文生图默认立绘 8 头身,edit 改头身比每轮只给目标差的 1/3(0.108→0.124→0.131),写百分比或写目标数字都一样;正确做法=选一张 → PIL 以领口顶为轴把身体缩小到目标头身比做 mock(头不动)→ sol edit 只融合领口处接缝,一轮到位。侧/背视图同样:以领口顶(背面以肩甲/肩线)对齐 front 做 mock 再融缝;**侧背视图禁喂立绘比例的转面图**当图 3(会把头做小 30%)。量头高用 `character-art-lab/tools/vesper_cur_headmeasure.py`,不用肤色宽度门槛。
- **皮肤按部件换,底模冻结(10-26 Coda 验证)**:Tripo 每次整身重生成脸都会变,而且按总高归一化身体会缩放,所以皮肤不能整身重生成。每个英雄冻结一个底模(定稿脸 + 打底衣 + 寸头,头皮完整),新皮肤的发型/帽子/上衣/下装/鞋各自从新的整身生成里拆出来、相似变换对齐、适配到底模上。新英雄一开始就把寸头底模当定稿做;老英雄用 `head_shave.py` 剃头,脸一个顶点不动。全套做法、Coda 实测数字和没实测的部分见 `references/10-部件换装.md`。
- **一副骨架铁律(10-24 Rook2 定)**:模型 FBX 和所有动作 FBX 必须来自**同一副最终骨架**。绑骨阶段任何改静止姿势的操作(rig_build 的镜像/roll 归零/脊柱拉直、换头、归一化)之后,Tripo 预设/文生动作都要用 `scripts/blender/anim_bake_to_rig.py` 按世界空间重新烘到最终骨架上,再用 `anim_verify.py` 过门(逐骨世界方向误差 <1°,注意 FBX 读回从第 1 帧起要 +1 帧对齐),Unity 里动作 FBX 一律 `CopyFromOther` 模型 avatar(`eval/anim_import_shared.cs`)。**禁止**动作 FBX 自建第二份 avatar 再靠 enforce/canon T-pose 去凑;禁止看到交叉腿/点脚尖/后仰就去改 avatar、加 leg_fix 常量——先量 Blender 源和 Unity 同一时刻的数字(`eval/knee_t.cs`、`eval/foot_probe.cs`),差在哪修哪。
- **验收看全身四视图不看数字**:每个在用动作 `eval/fullbody.cs` 出正/侧/背/3/4,与 Wren 同机位并排,逐条列出不自然的点(脚掌俯仰、膝距、手臂贴身、手腕、头倾、朝向),派子 agent 修,再出同一组图复验;膝盖数值只能当辅助。改过 avatar 或骨架后,所有派生 .anim(裁剪待机、求解敬礼、舱内握把)全部作废重生成。
- **门只认证据**:脚本打印的 PASS/FAIL 和主会话亲眼看过的对照板/裁图。sol 或任何报告里写的"pass"不算。每次修改都和上一版裁同一区域并排看,不对着 prompt 打勾。
- **几何看灰模,贴图看不打光的纯贴图**,都从游戏会用的角度看(正、侧、3/4、70° 俯视)。
- **识别件照定稿图的形状**,只许删悬空件、加粗细件。同一件东西有两种可行画法,做对照板让勾哥点。
- **花点数的 Tripo 操作本会话做**(子 agent 不认转述授权);每次点 Generate 前核对设置。**不记点数、不记余额、不对账**(10-24 勾哥定:"不要 care Tripo 点数的事情"),单次明显异常(>150)才提一句。
- **Unity**:先 `scripts/unity/ucli.sh guard`;Play 中不写 .cs;eval 不同步等异步;从 Git Bash 调;收尾一定 stop 并确认。不切场景、不碰无关改动、不 commit/push,除非勾哥说。
- **分工**:sol(codex CLI)出图改图、可以照模板跑脚本;主会话写 spec、做所有验收、操作 Tripo 和 Unity(用哪个模型勾哥当次说,这里不写死)。
- Blender 在 `F:/Apps/blender.exe`(5.1,后台 `-b --python x.py -- 参数`,输出一律绝对路径)。Python 用 `py -3`。

## 阶段一览
| 阶段 | 做什么 | 关键命令 | 出口门(全过才往下) | 细节 |
|---|---|---|---|---|
| 0 输入与核对 | 读真源、建配置、环境/权限/落点、查枪型和控制器现状 | — | 配置已填;环境自检过;落点已问;无人 Play | 00 |
| 1 建模四视图 | A-pose 平光厚涂四视图,头身比按各角色手册定(Rook 模型 5.5,Vesper、Harrow 6.5 等),识别件照原样 | `build_prompts.py fourview/edit/faceround` → `sol_image.sh` → `sheet_check.py` → `sheet_finalize.py` | `sheet_check --final` ALL PASS;头身比刻度图落在配置的 `head_ratio`;识别件逐视图表全对;脸型门(front+侧脸) | 01 |
| 2 结构参考 | 把定稿四视图重画成柔和体积光的结构图(只给 Tripo 建形状) | `build_prompts.py struct` → sol → `silhouette_iou.py` | 四张 IOU ≥ 0.93;脸部结构看图门;存进 vault | 02 |
| 3 Tripo 白模 | 浏览器验身;Multi-view,H3.1,Ultra 开,贴图关,6 万面,30 点 | 网页(见 03);`inspect_model.py` | 下载文件验过;进 5.1 | 03 |
| 4 Tripo 贴图 | 贴图页换上平光厚涂四张,Remove Lighting 关,4K,20 点 | 网页;`inspect_model.py` | 进 5.2 | 03 |
| 5 模型验收 | 灰模看脸和剪影;纯贴图看笔触、镜像、手臂底面 | `clay_face.py`、`render_views.py --mode clay/unlit`、`compare_board.py` | 形状门 + 贴图门(04 列的每条) | 04 |
| 6 绑骨 | Tripo Humanoid/Mixamo 绑骨(20 点)+ 预设动作(免费);rig GLB 上清脏贴图;修骨、加次级链、形变测试 | `tex_extract.py` → `tex_clean.py` → `rig_build.py` → `rig_audit.py` → `deform_sheet.py` | `RIG_AUDIT PASS`(含接缝门 seam_jump_edges ≤ 0.3%、seam_coloc_split = 0);`gate_body_p99_all_pass`;主会话看 deform_crops 九个姿势 | 03、04、05 |
| 7 表情换脸 | 渲脸底图+投影;sol 画表情;拼 4×3 图集;脸面分材质写格子空间 UV;发光遮罩 | `face_render.py` → `build_prompts.py expr` → `face_atlas.py` → `face_swap.py` → `face_qa_sheet.py`;`emission_mask.py` | calib 门;`ATLAS_GATES PASS`;闭眼格眼角零残留、后脑干净;`export_fbx.py` FBX_CHECK PASS | 06 |
| 8 Unity 入库 | Humanoid + Enforce T-Pose;ToonLit 厚涂参数 + remap;prefab + SpringBone + 短裙 `HeroSkirtFollow` 跟大腿走 + 腿型 `HeroLegTidy` + 头发 `spring_limits.cs`(见 07 §8.7)+ 预览秀 `HeroPreviewShow`(1~2 个性格动作 + 表情,§8.8)+ 肤色核对(§8.9);本地换主角 + 枪挂点 | `spring_spec.py` 打印全部命令 → `ucli.sh eval …cs` | `AVATAR PASS`(+ .meta diff);Unlit/ToonLit 渲染门;PREFAB OK;SPRING_LIMITS;Gear 页强制大动作不炸;WEAPON MOUNT OK | 07 |
| 9 实机验收 | Boot → 主页 → 装备页 → START → 出击 → 远征;状态截图;收尾 stop | `ingame_check.sh <Name> <out>`、`anim_state.cs` | 08 列的每条看图门;Console 无新错;stopped;Assets/Temp 清干净;欠账写清 | 08 |
| 10 归档 | 文件进 vault、写回手册、写报告、更新 skill/记忆 | — | 09 的清单 | 09 |

## 脚本索引
`scripts/`(Python 用 `py -3`;`blender/` 下的用 `F:/Apps/blender.exe -b --python <脚本> -- <参数>`;每个脚本 `-h`/无参数会打印用法)
| 脚本 | 用途 |
|---|---|
| `_cfg.py` | 读角色配置(其他脚本共用) |
| `build_prompts.py` | 从模板 + 配置生成 sol prompt(四视图/修图/圆脸/结构参考/表情),打印运行命令 |
| `sol_image.sh` | 跑一个 sol 出图任务(stdin 喂 prompt、`--skip-git-repo-check`、日志) |
| `sheet_check.py` | 四视图数值门 + 头部刻度裁图 + 对照板 |
| `sheet_finalize.py` | 背景填 138、对齐 0.88 画高、可选色相修正 |
| `crop_compare.py` | 同区域并排对比、量 HSV、裁头部给 sol 改 |
| `sheet_paste.py` | 改好的头部裁图羽化贴回 |
| `silhouette_iou.py` | 结构参考和平光图的轮廓一致性 |
| `compare_board.py` | 四视图 vs 模型渲染两行对照板;任意图一行并排 |
| `tex_clean.py` | 皮肤脏块检测 + push-pull 修补 |
| `deform_sheet.py` | 形变测试总图 + 2× 关节裁图 |
| `face_atlas.py` | 拼表情图集 + 相位相关对齐门 |
| `face_qa_sheet.py` | 换脸 QA 总图 + 闭眼格眼部 2× 裁图 |
| `emission_mask.py` | 按色相出发光遮罩 |
| `blender/_bl.py` | Blender 公共函数(加载、正交相机、不打光/灰模材质、唯一正确的 FBX 导出) |
| `blender/inspect_model.py` | 看下载文件里到底有什么(网格/骨骼/贴图/动作/朝向) |
| `blender/render_views.py` | 和四视图同构图的正交渲染;灰模/纯贴图;特写;换贴图对比 |
| `blender/clay_face.py` | 头部灰模多角度(脸型门) |
| `blender/tex_extract.py` | 导出三角形/UV/法线 + 原贴图给 tex_clean |
| `blender/rig_build.py` | 配置驱动的修骨 + 次级链 + 权重 + 形变测试 + FBX |
| `blender/rig_audit.py` | 绑骨数值审计(13 条门) |
| `blender/deform_gates.py` | 形变数字门:手臂钻躯干 + 小幅度姿势拉伸(10-26,见 05 章 6.4 第 3 条) |
| `blender/protect_decimate.py` | 整身高面数模型保脸保手减面到预算(焊 UV 缝 → 几何圈脸前部+手锁定 → 身体 meshoptimizer、头 collapse → 投原模法线);只吃未绑骨的生成件,要 node(10-26,见总纪律"头小的角色") |
| `blender/meshopt_simplify.mjs` + `blender/vendor/meshoptimizer-1.3.0/` | protect_decimate 调用的 meshoptimizer 简化器(MIT,vendored) |
| `blender/part_align.py` | 皮肤部件来源整身 → 底模 ICP(默认相似变换)(10-26,见 10 章) |
| `blender/part_pick.py` | 从 Tripo Detailed 拆件挑部件、清罗纹、抠头发带,出掩码和部件 glb |
| `blender/part_graft.py` | 上衣/下装类部件贴回底模(删被盖面、留裙边、边界吸附、推穿模) |
| `blender/part_fit.py` | 发型/帽子类部件适配底模(只推不拉、焊接平滑、补推) |
| `blender/head_shave.py` | 老英雄剃头:定稿模型只把头发区换成寸头头皮,脸不动 |
| `blender/face_render.py` | 脸底图 + 投影 json + 标定图 |
| `blender/face_swap.py` | 脸面选面、格子空间 UV、表情材质、QA 渲染、FBX |
| `blender/export_fbx.py` | 从 blend 重新导出 FBX 并回读校验 |
| `unity/ucli.sh` | Unity CLI 包装:status/guard/eval 模板/play/stop/capture/click/scenes |
| `unity/spring_spec.py` | 按配置打印阶段 8 全部 eval 命令 |
| `unity/ingame_check.sh` | 实机流程跑一遍并截图,trap 保证 stop |
| `unity/eval/*.cs` | import_setup、enforce_tpose、avatar_check、materials_setup、prefab_build、hero_swap、weapon_mount、fix_animator_node、render_views、anim_state、hero_swap_keepall(换主角用这个)、film_strip(真实动画胶片条) |

`templates/`:`char_config.example.json`(Wren 真值)、`fourview/`(spec 骨架、英文主体、视图块、Wren 角色块示例、修图、圆脸、结构参考)、`face/expression_common.txt`、`sol/`(派给 sol 的绑骨/换脸任务书)、`unity/`(CharacterEnforceTPose.cs、CharacterFaceController.cs,要拷进工程的通用版)。

## 什么时候停下来问勾哥
识别件形状有两种读法;同一件东西出了两种可行画法;头身比、体态(驼背、宽体)在建模图里保留多少;角色落点(换主角/可选角色/NPC);要不要提交 Hero.prefab、manifest、新的 .cs;点数明显超预算(单角色 > 150 点);任何要改共享系统(枪、动画控制器、血条)的事。

## 复查记录
`references/REVIEW.md`:本 skill 写完后按"下一个角色 Harrow"逐步走查的结果、修掉的问题和剩下的风险。每做完一个新角色在末尾追加一段。
