---
name: er-blender
description: ER 非角色 Blender 活总入口:POI 建筑 / 联邦小件部件化建模与按设计坐标拼装、小 POI 15 分钟一轮(拆解单 → 体块 → 叠概念图)、干净上色 paint-over、Tripo 件清理与风格化、评审对照图与验收门、导出 Unity、VFX mesh 等离线件、bpy 坑表与 Blender MCP。Trigger on "blender 建模" / "POI 建模" / "建筑建模" / "体块" / "blockout" / "叠概念图" / "建模不准" / "paint over" / "干净上色" / "tripo 模型精修" / "模型太 basic" / "看得出刻面" / "减面" / "导出 FBX 进 Unity" / "道具风格化" / "拆成墙再组合" / "blender 出图" / "blender mcp" / "bpy 报错" / "POI 检查表" / "POI 交付前"。角色走 er-character-pipeline;Unity 里修材质 / pivot 走 gaoguang-3d;树草崖地块默认走 Unity 生成器。
---

# ER Blender 总入口

这份 skill 管 ER 里所有不是角色的 Blender 活。**建筑和物品的建模、paint-over 一律按 `references/00-造型与笔触标准.md`**(mo.co 车辆语言:敦实硬表面、大平面宽倒角、粗附件、稀疏硬边块面笔触,底色只放固有色,环境色和光照交给 Unity),打回项和验收五项都在那份里。

## 先判断走哪条路

| 要做的事 | 去哪 |
|---|---|
| POI 建筑(有顶屋、母舱、遗址残壳、城市楼)和联邦硬表面小件:先做部件再按设计坐标拼,不做地板;Claude 直接做(勾哥定) | 本 skill `references/07-建筑部件拼装.md` + `scripts/kit/` |
| paint-over(楼体、小件、家具、道具):画法按 00 第二、三节;**手段按效果选**(00 第四节):顶点色 `scripts/paintover/po_vertex.py` 出固有色 + 棱边短条 / 局部面状提亮(按面硬边、稀疏),大面内的斜块楔形、玻璃、屏幕、招牌、标识走贴图,两者可混用 | 本 skill `references/08-干净上色paintover.md` |
| 贴图 paint-over 管线:底稿 → terra 上色 → 配准 → hardhue(纠意外色漂)→ 投影回 UV → 图集 | 本 skill `references/08-干净上色paintover.md` + `scripts/paintover/`;换场景只写一个配置 JSON |
| 角色(四视图 → Tripo → 绑骨 → 表情 → 入库) | er-character-pipeline(它的 Blender 坑同样以本 skill 的 02 为准) |
| 模型进了 Unity 发灰、塑料感、pivot 歪、只是法线软塌 | gaoguang-3d;先试 Unity importer 法线,多数"肉感"不用进 Blender |
| Tripo 道具/武器/家具/POI 件:减面、刻面、色块、尺寸、挂点 | 本 skill `references/03-道具风格化.md` |
| 出评审对照图、量数字、判过没过 | `references/04-验收门.md` |
| 导出 FBX、挂点 Empty、回读核对、交给 Unity | `references/05-导出Unity.md` |
| VFX mesh(斩击弧/环/冲击波/拖尾)、flipbook、石头单元库 | `references/06-离线件.md`(做法已调研、未在 ER 实测,先做 pilot) |
| POI 里的植物:花坛 / 花箱的叶团、花、垂藤,树池树,压顶树团 | 和件一起交。默认做法:灌木在 Blender 逐片叶建,按 `references/10-植物建模.md`(多团相挤、小叶贴面、法线取自圆壳;`scripts/kit/shrub_lab.py` 是实测过的生成器和对照实验);树冠走 Tripo,进 Blender 减面烘色后和硬表面件合成。别的路线(程序化、Unity 里做、新工具)可以试,按实拍和参考并排判 |
| 地形上的植物、崖(树、草、崖、台地、沙被、散布) | 默认 Unity 编辑器 + codex 合作;进 Blender、走 Tripo 或别的新路线也可以试,按引擎实拍判 |

## 通道:live 用 MCP 迭代,出货用 blender -b

用官方 Blender Lab MCP。MCP 只用来边改边看;导入、修改器、烘焙、导出、验收门、批处理一律写成脚本后台跑:`<blender.exe> -b --factory-startup -P <脚本> --python-exit-code 1 -- <参数>`。**证据只认后台渲到文件的对照板加数字**,MCP 截图只算迭代过程。工具清单、开工检查、Online Access 见 `references/01-通道与工具.md`。

写 bpy 之前先读 `references/02-bpy51坑.md`:枚举运行时读(5.1 的 EEVEE 是 `BLENDER_EEVEE`)、节点按 type 找、5.x 删掉的 API、后台没有视口上下文要 temp_override、operator 返回 FINISHED 不等于生效。

Tripo 默认用浏览器里的 Tripo Studio 网页版;tripo-cli、API、Blender 桥插件或别的生成工具想试可以试,先在一件上对比效果;操作和验身见 er-character-pipeline `references/03-Tripo网页操作.md`,点数不记。

## 脚本库

`scripts/blender/` 下的脚本都是"一个 `main(argv)`、参数在 `--` 之后、打一行 JSON、失败退出码非 0",后台和 MCP(`importlib.reload` 后调)两用。先看库里有没有现成的;要试新做法就写新脚本,跑通、有复用价值的收进库,别留在 scratchpad 里一次性用完。

| 脚本 | 干什么 |
|---|---|
| `_er_bl.py` | 公共库:`ops_ctx`(统一 temp_override)、`import_any`(焊点、应用变换、原点底部中心,焊点时保住原法线)、`inspect`(三角/开放边/非流形/材质/UV/尺寸)、`make_lablit_preview`(纯 Emission 两阶明暗,只是评审用的近似 Unity LabLit 展示光,不进交付底色) |
| `stage.py` | 评审台:V5 46° 游戏镜头、正交俯视、正/侧/3/4、128px 游戏尺寸图,lablit / white(只看明暗)两种模式,另存掩码 |
| `overlay_render.py` | 只渲一个集合(Workbench,约 1 秒,透明底)并导出相机投影矩阵;视角 top / g46 / cam / concept,给 `kit/overlay.py` 用 |
| `bake_hi_to_lo.py` | 高模顶点色以 EMIT 烘进低模贴图(纯固有色),见 07 |
| `scripts/kit/blockout.py` | 拆解单 parts JSON → 体块 .blend(盒子 / 竖圆柱,每件一个物件),约 3 秒 |
| `scripts/kit/overlay.py` | 体块叠概念图:对应点配准(相似 / 仿射 / 单应)、IoU、检查点偏差、反推概念图相机算"概念图画了多高";出三联板 + 闪烁 gif。系统 Python 跑,自己调 Blender(找不到时设 `BLENDER=`) |
| `scripts/kit/plants.py` | 植物单元:尖头叶片、五瓣花、叶团(底团盖土 + 放射莲座)、垂藤 |
| `scripts/kit/shrub_lab.py` | 花坛灌木对照实验和生成函数 `leaf_clump()`:同一花坛七种做法同机位出图(叠圆盘 / 面法线 / 圆壳法线 / 规整 / 不规则 / 大团相挤),换植物种类或调参数前先跑它,见 10 |
| `scripts/kit/*` | 部件化建模生成器(kitlib 拼装器 + 有顶屋 / 母舱 / 遗址 / 小件 / 家具),见 07 |
| `scripts/paintover/po_vertex.py` | 顶点色 paint-over:固有色 + 稀疏棱边短条(按整条棱选、朝上的优先)+ 可选局部面状提亮 / 块间差,按面硬边,只改明度不改色相,不烘方向光;跑两次结果一样,见 08 |
| `scripts/paintover/po_*.py` | 贴图 paint-over:canvas → prompts(底稿 + 可选本件拆件格 + 可选 mo.co 笔触参考)→ register → hardhue(纠意外色漂)→ project → review(+ po_board 对照板),配置样例在 `paintover/examples/`,见 08 |
| `scripts/imagegen/prompt_lint.py` / `img_colorcheck.py` | 生图发单前查提示词、回图查偏色(铁规 0),见 09 |
| `scripts/gates/poi_nav_gate.py` + `navdump_reach.py` | POI 共用寻路闸:装机前用导出 .blend 按工程 NavMesh 参数离线判(门两侧通不通、门宽 / 高 / 墙楣、门口净区、精英位离边、各层走不到的地面),引擎烘完读 navdump 判入口连通;阈值只在 `gates/thresholds.json`,每个 POI 一份配置,见 `gates/README.md` |

## 工作纪律

- **第 0 步:用 Skill 工具加载 `yide:reference-replicate`**,按它锁参考、整张找实例、逐层填观察表、用 `refkit.py` 量比例,再动 Blender。没加载就跑 Blender,PreToolUse 的 skill 闸会拦下;闸只认真实的 Skill 调用。不加载时最常见的后果是看个大概就按常识搭,丢细节、加细节。
- **第 0.5 步:锁参考。** 按 vault `013 美术/AI记忆/现行口径_参考与工具分工.md` 第二节取本物件锁定的 mo.co 图,打开原图实看;只导出 / 改 pivot / 减面不改形这类不改外观的活不用拉。人造物外形只挂我们认可的概念图;mo.co 只学造型语言和笔触(建筑和物品的总基准是 `车辆语言基准_20261127/`,见 00),不学它的环境色和光照。
- **POI 每一轮交付前过 `references/09-POI交付前检查表.md`**:开工读对应环节,交付前逐条打勾,交付说明写「09 已过」和没过的条目。头号四类:paint-over 只加明暗不改色相、按游戏镜头(V5 46° 俯视)做屋顶和外墙、先拆解再建单件做像、看得见的瑕疵不自己放过。
- **铁规 0:生图时每样东西都是它自己的本色,概念图、拆件图不画光影和 hue**(勾哥强制执行):楼、屋顶、地面、草、树、岩、水、道具、家具全部本色,灯光 / 时段 / 氛围 / 阴影不改任何东西的颜色,发光件不往别处染色;风格参考只学形和质感;少用粉 / 紫(男性向)。HUE 是 Unity 里游戏光影的事。发单前 `scripts/imagegen/prompt_lint.py`、回图 `scripts/imagegen/img_colorcheck.py`,退出码非 0 不发 / 不交。全文见 09 铁规 0 和 07「概念图 / 拆件图一律物品本色」。
- **工具和 skill 的目的是单件精准、细节还原**:每个件对着拆件图那一格单独做、单独渲、左右并排验收;复用件库里没有就照格新做,不放占位块。摆位和概念图的小偏差不纠结,不把坐标同步回设计数据。见 07「单件精度」。
- **小 POI 一轮 15 分钟内发截图**:拆解单 3 分钟(每件写干什么用、参考格号,再写参考里没有什么)→ `blockout.py` 体块 → `overlay.py` 俯视 + 46° 叠图自检 → 细节 → 出图(发勾哥的只有单件并排板,评审图和叠图板留给自己和总控)。细节、命令、叠图怎么读、AI 概念图透视不自洽怎么办,见 07「小 POI 一轮 15 分钟」。说不出用途的件不建;叠图没过不做细节。
- **上色后直接进实地测**:paint-over 做完,模型直接放进游戏地图里这个 POI 的实际位置,在那里的真光照、游戏镜头下截图验收;不先放进样板间。发光件在 paint-over 里只画它自己,不往别的面画光(铁规 0)。
- **有盖子 / 有门的件一律做成可打开的容器**:箱、柜、罐、冰柜、储物格、带门小屋、桌子抽屉等,建模时盖 / 门单独成物件、轴心放在铰链处,并出关着 / 开着两态(开态露出内部,内部也要上色);进 Unity 挂 `LootableContainer` + `LootContainerLidVisual`(`_closedVisual` / `_openVisual` 两态切换,Extraction `Assets/Scripts/Gameplay/Containers/`)。拆解单里每个有盖 / 有门的件标「容器」,漏标就打回。
- Blender 路径因机器而异(`F:/Apps/blender.exe` 或 `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`),先 `ls` 确认;`overlay.py` 两处都会找,也认 `BLENDER` 环境变量。
- 评审默认用 `stage.py`(46° 游戏镜头、white 只看明暗、128px 游戏尺寸图),需要别的评审方式就加进库;两轮不中换方法,不在一条路上盲调。
- 一件东西的固有色按设计来(多色分件、标识照留),体积靠形和引擎光影,paint-over 只加 00 第二节那种稀疏硬边块面;不烘 AO、投影、环境色;面数只为预算服务,看得出的刻面要藏住,但不靠把平面抹圆来藏。
- 改了别人开着的 .blend 前先确认;不关别人的 Blender GUI;重要 .blend 不只放 scratchpad。
- 做完交给 Unity 后,在真光照下再截一次和 Blender 评审图并排;模型在引擎里和在 Blender 里不是一回事。

## 前沿雷达

人物、Rig、动作、物品、环境、材质、光效、agent 驱动 Blender 八个方向的调研结论(带出处和 ER 采用判断)在 Google Sheet「ER Blender 建模前沿调研」。新工具先查那张表有没有判过,再决定要不要试。
