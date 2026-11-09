---
name: er-blender
description: ER 非角色 Blender 活总入口:POI 建筑 / 联邦小件部件化建模与按设计坐标拼装、小 POI 15 分钟一轮(拆解单 → 体块 → 叠概念图)、干净上色 paint-over、Tripo 件清理与风格化、评审对照图与验收门、导出 Unity、VFX mesh 等离线件、bpy 坑表与 Blender MCP。Trigger on "blender 建模" / "POI 建模" / "建筑建模" / "体块" / "blockout" / "叠概念图" / "建模不准" / "paint over" / "干净上色" / "tripo 模型精修" / "模型太 basic" / "看得出刻面" / "减面" / "导出 FBX 进 Unity" / "道具风格化" / "拆成墙再组合" / "blender 出图" / "blender mcp" / "bpy 报错"。角色走 er-character-pipeline;Unity 里修材质 / pivot 走 gaoguang-3d;树草崖地块走 Unity 生成器,不进 Blender。
---

# ER Blender 总入口

这份 skill 管 ER 里所有不是角色的 Blender 活。结果按 ER 美术规范验收(vault `01 - 星际拓荒重构/013 美术/ER美术规范.md`,对标 mo.co,建筑道具看第 7 节):平滑饱满的大形体、大块干净色面、两阶明暗、没有写实高光,3D 世界里不描黑边。**禁区**:看得出刻面或低多边形、flat shaded、写实材质纹理、细碎凹凸,任何一项都打回。

## 先判断走哪条路

| 要做的事 | 去哪 |
|---|---|
| POI 建筑(有顶屋、母舱、遗址残壳)和联邦硬表面小件:先做部件再按设计坐标拼,不做地板 | 本 skill `references/07-建筑部件拼装.md` + `scripts/kit/`(10-30 勾哥定 Claude 直接做) |
| 干净上色 paint-over:底稿 → sol 干净上色 → 配准 → 锁色 → 投影回 UV → 图集。**J01 建筑 / 拆件一律干净上色(11-04 勾哥);颜色一律从参考图受光面直取 + 进引擎闭环标定,不混灰(11-05 勾哥);小件 / 圆件 / 斜放件不投影贴图,走顶点色 + LabLit** | 本 skill `references/08-干净上色paintover.md` + `scripts/paintover/`;换场景只写一个配置 JSON |
| 角色(四视图 → Tripo → 绑骨 → 表情 → 入库) | er-character-pipeline(它的 Blender 坑同样以本 skill 的 02 为准) |
| 模型进了 Unity 发灰、塑料感、pivot 歪、只是法线软塌 | gaoguang-3d;先试 Unity importer 法线,多数"肉感"不用进 Blender |
| Tripo 道具/武器/家具/POI 件:减面、刻面、色块、尺寸、挂点 | 本 skill `references/03-道具风格化.md` |
| 出评审对照图、量数字、判过没过 | `references/04-验收门.md` |
| 导出 FBX、挂点 Empty、回读核对、交给 Unity | `references/05-导出Unity.md` |
| VFX mesh(斩击弧/环/冲击波/拖尾)、flipbook、圆润石头单元库 | `references/06-离线件.md`(做法已调研、未在 ER 实测,先做 pilot) |
| POI 里的植物:花坛 / 花箱的叶团、花、垂藤,树池树,压顶树团 | **Blender 建,和件一起交(11-09 勾哥「植物建模也由 blender 进行」)**;单元 `scripts/kit/plants.py`(v0 未验收) |
| 地形上的树、草、崖、台地、沙被、散布 | 现行走 Unity 自写生成器(记忆里松树/莲座树/崖体做法卡);11-09 植物改 Blender 的拍板是否也覆盖这里**未确认,先问勾哥** |

## 通道:live 用 MCP 迭代,出货用 blender -b

本机用官方 Blender Lab MCP(2026-10-26 换装,社区版已卸)。MCP 只用来边改边看;导入、修改器、烘焙、导出、验收门、批处理一律写成脚本后台跑:`F:/Apps/blender.exe -b --factory-startup -P <脚本> --python-exit-code 1 -- <参数>`。**证据只认后台渲到文件的对照板加数字**,MCP 截图只算迭代过程。工具清单、开工检查、Online Access、回退备份见 `references/01-通道与工具.md`。

写 bpy 之前先读 `references/02-bpy51坑.md`:枚举运行时读(5.1 的 EEVEE 是 `BLENDER_EEVEE`)、节点按 type 找、5.x 删掉的 API、后台没有视口上下文要 temp_override、operator 返回 FINISHED 不等于生效。这些坑在 2026-07~10 的 38 个 Blender 会话里反复踩过。

Tripo 只用浏览器里的 Tripo Studio 网页版(10-26 勾哥定),不用 tripo-cli、不直接调 API;操作和验身见 er-character-pipeline `references/03-Tripo网页操作.md`,点数不记。

## 脚本库

`scripts/blender/` 下的脚本都是"一个 `main(argv)`、参数在 `--` 之后、打一行 JSON、失败退出码非 0",后台和 MCP(`importlib.reload` 后调)两用。先用库里的,别在会话里再写一份:2026-07~10 的会话写了 389 个脚本名,375 个不在 skill 里,出图脚本另写了 49 个、体检脚本 87 个,大半只用过一次。

| 脚本 | 干什么 |
|---|---|
| `_er_bl.py` | 公共库:`ops_ctx`(统一 temp_override)、`import_any`(焊点、应用变换、原点底部中心,焊点时保住原法线)、`inspect`(三角/开放边/非流形/材质/UV/尺寸)、`make_lablit_preview`(纯 Emission 两阶明暗,近似 Unity LabLit) |
| `stage.py` | 评审台:V5 46° 游戏镜头、正交俯视、正/侧/3/4、128px 游戏尺寸图,lablit / white(只看明暗)两种模式,另存掩码 |
| `overlay_render.py` | 只渲一个集合(Workbench,约 1 秒,透明底)并导出相机投影矩阵;视角 top / g46 / cam / concept,给 `kit/overlay.py` 用 |
| `scripts/kit/blockout.py` | 拆解单 parts JSON → 体块 .blend(盒子 / 竖圆柱,每件一个物件),约 3 秒 |
| `scripts/kit/overlay.py` | 体块叠概念图:对应点配准(相似 / 仿射 / 单应)、IoU、检查点偏差、反推概念图相机算"概念图画了多高";出三联板 + 闪烁 gif。系统 Python 跑,自己调 Blender(找不到时设 `BLENDER=`) |
| `scripts/kit/plants.py` | 植物单元:尖头叶片、五瓣花、叶团(底团盖土 + 放射莲座)、垂藤;PARK 花坛 v0 |
| `scripts/kit/*` | 部件化建模生成器(kitlib 拼装器 + 有顶屋 / 母舱 / 遗址 / 小件 / 家具),见 07 |
| `scripts/paintover/po_*.py` | 干净上色 paint-over:canvas → prompts → register → colorlock → project → review(+ po_board 对照板),配置样例在 `paintover/examples/`(哨亭 + M1 矿点),见 08 |

## 工作纪律

- **第 0 步:用 Skill 工具加载 `yide:reference-replicate`**,按它锁参考、整张找实例、逐层填观察表、用 `refkit.py` 量比例,再动 Blender。没加载就跑 Blender,PreToolUse 的 skill 闸会拦下(10-31 起;此前 14 个跑过 Blender 的会话 0 个加载过它,J01 三脚架、工具匣因此各打回多轮)。只读一遍这句不算,闸只认真实的 Skill 调用。
- **第 0.5 步:登记参考。** 从全项目参考登记表(Sheet「jungle lab」组件清单 I 列)取本物件那一行的图,打开原图实看,跑 `node <插件>/scripts/ref-check.js lock …`;只导出 / 改 pivot / 减面不改形这类不改外观的活跑 `exempt --why "不改外观:…"`。参考闸会拦没登记的 Blender 调用。规则全文 vault `013 美术/mo.co截图/README_参考怎么选.md`;人造物外形只挂我们认可的概念图,mo.co 只当质感上限。
- **工具和 skill 的目的是单件精准、细节还原(11-09 勾哥)**:每个件对着拆件图那一格单独做、单独渲、左右并排验收;复用件库里没有就照格新做,不放占位块。摆位和概念图的小偏差不纠结,不把坐标同步回设计数据。见 07「单件精度」。
- **小 POI 一轮 15 分钟内发截图(11-09 勾哥)**:拆解单 3 分钟(每件写干什么用、参考格号,再写参考里没有什么)→ `blockout.py` 体块 → `overlay.py` 俯视 + 46° 叠图自检 → 细节 → 出图,叠图板和评审图一起发。细节、命令、叠图怎么读、AI 概念图透视不自洽怎么办,见 07「小 POI 一轮 15 分钟」。说不出用途的件不建;叠图没过不做细节。
- Blender 路径因机器而异(`F:/Apps/blender.exe` 或 `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`),先 `ls` 确认;`overlay.py` 两处都会找,也认 `BLENDER` 环境变量。
- 评审先用现成的 `stage.py`(46° 游戏镜头、white 只看明暗、128px 游戏尺寸图),别另写一套;两轮不中换方法,不在一条路上盲调。
- 一件东西的固有色两三个,体积靠顶亮底暗和边缘提亮,不靠纹理;面数只为预算服务,减完要把面藏住。
- 改了别人开着的 .blend 前先确认;不关别人的 Blender GUI;重要 .blend 不只放 scratchpad。
- 做完交给 Unity 后,在真光照下再截一次和 Blender 评审图并排;模型在引擎里和在 Blender 里不是一回事。

## 前沿雷达

2026-10-26 做过一轮八个方向的调研(人物、Rig、动作、物品、环境、材质、光效、agent 驱动 Blender),142 条带出处和 ER 采用判断,结论表在 Google Sheet「ER Blender 建模前沿调研」。新工具先查那张表有没有判过,再决定要不要试。
