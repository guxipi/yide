---
name: er-blender
description: ER(Extraction)所有非角色的 Blender 活的总入口——POI 建筑与联邦小件的部件化建模和按设计坐标拼装、给模型加 mo.co 手绘质感的 paint-over 管线(sol 手绘 + 配准投影回 UV,换场景只换配置)、Tripo 道具/武器/HOME 家具/POI 件的清理与风格化、评审台出对照图、数字验收门、导出进 Unity、VFX mesh 和圆润石头这类离线件;附 Blender 5.1/5.2 bpy 坑表和官方 Blender Lab MCP 的用法。Trigger on "blender 建模" / "建筑建模" / "拆成墙再组合" / "POI 建模" / "做部件库" / "paint over" / "painter over" / "手绘质感" / "加 mo.co 笔触" / "模型太 basic" / "blender 处理模型" / "tripo 模型精修" / "模型肉感" / "模型太高模/太碎" / "看得出刻面" / "减面" / "道具风格化" / "blender 出图/渲染对照" / "导出 FBX 进 Unity" / "blender mcp" / "bpy 报错" / "stylize this model"。角色从设计图到入库走 er-character-pipeline;只在 Unity 里修材质/法线/pivot 走 gaoguang-3d;树、草、崖、地块这类程序化地编走 Unity 生成器,不进 Blender。
---

# ER Blender 总入口

这份 skill 管 ER 里所有不是角色的 Blender 活。结果按 ER 美术规范验收(vault `01 - 星际拓荒重构/013 美术/ER美术规范.md`,对标 mo.co,建筑道具看第 7 节):平滑饱满的大形体、大块干净色面、两阶明暗、没有写实高光,3D 世界里不描黑边。**禁区**:看得出刻面或低多边形、flat shaded、写实材质纹理、细碎凹凸,任何一项都打回。

## 先判断走哪条路

| 要做的事 | 去哪 |
|---|---|
| POI 建筑(有顶屋、母舱、遗址残壳)和联邦硬表面小件:先做部件再按设计坐标拼,不做地板 | 本 skill `references/07-建筑部件拼装.md` + `scripts/kit/`(10-30 勾哥定 Claude 直接做) |
| 给任何模型加 mo.co 手绘质感和笔触(paint-over):底稿 → sol 手绘 → 配准 → 投影回 UV → 图集 | 本 skill `references/08-手绘paintover.md` + `scripts/paintover/`;换场景只写一个配置 JSON |
| 角色(四视图 → Tripo → 绑骨 → 表情 → 入库) | er-character-pipeline(它的 Blender 坑同样以本 skill 的 02 为准) |
| 模型进了 Unity 发灰、塑料感、pivot 歪、只是法线软塌 | gaoguang-3d;先试 Unity importer 法线,多数"肉感"不用进 Blender |
| Tripo 道具/武器/家具/POI 件:减面、刻面、色块、尺寸、挂点 | 本 skill `references/03-道具风格化.md` |
| 出评审对照图、量数字、判过没过 | `references/04-验收门.md` |
| 导出 FBX、挂点 Empty、回读核对、交给 Unity | `references/05-导出Unity.md` |
| VFX mesh(斩击弧/环/冲击波/拖尾)、flipbook、圆润石头单元库 | `references/06-离线件.md`(做法已调研、未在 ER 实测,先做 pilot) |
| 树、草、崖、台地、沙被、散布 | 不进 Blender。走 Unity 自写生成器(记忆里松树/莲座树/崖体做法卡);Blender 做树叶在 10 月被放弃过 |

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
| `scripts/kit/*` | 部件化建模生成器(kitlib 拼装器 + 有顶屋 / 母舱 / 遗址 / 小件 / 家具),见 07 |
| `scripts/paintover/po_*.py` | paint-over 五步:canvas → prompts → register → project → review(+ po_board 对照板),配置样例在 `paintover/examples/`,见 08 |

## 工作纪律

- **第 0 步:用 Skill 工具加载 `yide:reference-replicate`**,按它锁参考、整张找实例、逐层填观察表、用 `refkit.py` 量比例,再动 Blender。没加载就跑 Blender,PreToolUse 的 skill 闸会拦下(10-31 起;此前 14 个跑过 Blender 的会话 0 个加载过它,J01 三脚架、工具匣因此各打回多轮)。只读一遍这句不算,闸只认真实的 Skill 调用。
- **第 0.5 步:登记参考。** 从全项目参考登记表(Sheet「jungle lab」组件清单 I 列)取本物件那一行的图,打开原图实看,跑 `node <插件>/scripts/ref-check.js lock …`;只导出 / 改 pivot / 减面不改形这类不改外观的活跑 `exempt --why "不改外观:…"`。参考闸会拦没登记的 Blender 调用。规则全文 vault `013 美术/mo.co截图/README_参考怎么选.md`;人造物外形只挂我们认可的概念图,mo.co 只当质感上限。
- 评审先用现成的 `stage.py`(46° 游戏镜头、white 只看明暗、128px 游戏尺寸图),别另写一套;两轮不中换方法,不在一条路上盲调。
- 一件东西的固有色两三个,体积靠顶亮底暗和边缘提亮,不靠纹理;面数只为预算服务,减完要把面藏住。
- 改了别人开着的 .blend 前先确认;不关别人的 Blender GUI;重要 .blend 不只放 scratchpad。
- 做完交给 Unity 后,在真光照下再截一次和 Blender 评审图并排;模型在引擎里和在 Blender 里不是一回事。

## 前沿雷达

2026-10-26 做过一轮八个方向的调研(人物、Rig、动作、物品、环境、材质、光效、agent 驱动 Blender),142 条带出处和 ER 采用判断,结论表在 Google Sheet「ER Blender 建模前沿调研」。新工具先查那张表有没有判过,再决定要不要试。
