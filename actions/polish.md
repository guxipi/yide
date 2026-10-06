# 翼德 · 打磨一屏(polish / 打磨 / refine)

> 把一个已经"能用但像开发版"的游戏界面(2D UI + 3D 场景 + 动效 + 声音)推到**成品级**的完整工作法。
> 蒸馏自 2026-10-02~05 ER「简报页 Briefing Room」三批打磨:14 个 topic、~30 张竞品对照图/批、13 次提交,勾哥评价"效果非常好"。
> 它不是"改一改好看点",而是**讨论 → 调研 → 拍板 → 方案 → 分片施工 → 亲眼验收 → 回填**的闭环,且**主脑只做判断,重活全派 Opus**。

## 0. 触发后第一件事:问清四样,别猜
用 AskUserQuestion(或一句话)问:
1. **写在哪个表格**:Google Sheet URL + 分页(没有就让他建一个空表给链接;表是讨论的真源,不是报告)。
2. **哪一屏 + 现状截图**(他发的截图路径;没有就自己进 Play 截)。
3. **他已经看出的问题**(原话逐条记下,后面每个 topic 的「勾哥原话」列要原样放)。
4. **美术出图通道**:Coplay `generate_or_edit_images` 能不能用(401 就走 §7 的 ChatGPT 通道),以及是否授权我用 ChatGPT。

然后登记 scope(`scope.js set`),每个 topic 一条「调研」+ 一条「实施+Play 验证」。

## 1. 总流程(一批 = 一轮,勾哥看完会再提一批,循环)
```
建档(目录/基线截图/Play 驱动手册)
 → 代码侦察(现状怎么实现,决定 action 落点)         ← Explore·opus
 → 既有设计继承侦察(近月提交+设计文档:继承骨架/可提升表现层) ← general-purpose·opus
 → 竞品调研(每个 topic 一路,多方向+多图+冗余 action)  ← general-purpose·opus ×N 并行
 → 写表(色带/现状图/对照图/他们怎么做/action/成本/建议/拍板列)
 → 弹窗拍板(只问真岔路,推荐项放第一)
 → 方案(精确到文件/方法/公式/数据流/性能/风险/验证)   ← general-purpose·opus(只读+只写一个方案文件)
 → 分片施工(一片一棒,串行占编辑器,一回合到底)        ← executor·opus
 → 主脑亲眼验收截图 → 显式路径 commit → attest
 → 不满意 → SendMessage 让同一执行者追加修(它有上下文,最省)
 → 批末:对抗式代码评审(只挑正确性/生命周期/关域重载/GC) ← general-purpose·opus
 → 回填:知识库 md+manifest+README+vault 镜像 / 记忆工地文件 / 表格状态列 / Planyway / 战绩
```
**勾哥的节奏**:他说「先这样做看看效果」「现在全做,我需要全通」= 拍板即开工,不要再确认一遍;他看完实物会再提下一批。

## 2. 分工与模型(谁干什么、用什么模型)——这是省 token 的核心
| 角色 | subagent_type / model | 干什么 | 不干什么 |
|---|---|---|---|
| **主脑**(当前会话,Fable/最强模型) | — | 取舍、写工单、定岔路、**亲眼看截图验收**、commit、回填、和勾哥对话 | 不读大文件、不写大段代码、不自己调研(每一步都派) |
| 代码侦察 | `Explore` + `model: opus` | 读现状实现:怎么上屏、数据从哪来、哪些是占位、可下手的杠杆+成本 S/M/L | 不改文件、不动 scope |
| 竞品调研 | `general-purpose` + `model: opus`,**每个 topic 一路并行** | 7–11 个参考覆盖多方向,下图到知识库,**Read 每张图亲眼确认**,盘点项目 kit 里现成资源,输出 `block_<id>.json`(见 §4) | 不改项目、不 commit、不动 Unity |
| 施工方案 | `general-purpose` + `model: opus`(**不要用 `Plan` 类型——它只读,连方案文件都写不了,主脑得自己重打一遍**) | 读代码+数据后出可照做的方案,写到**唯一允许写的方案文件** | 不动编辑器 |
| 施工 | `executor` + `model: opus`,**一片一棒,串行** | 照工单实现 + 真流程 Play 验证 + 三档截图 + state-dump + 诚实汇报 | 不 commit/push、不 save 场景、不碰 ProjectSettings、不动别的棒的文件 |
| 追加修 | `SendMessage` 回同一执行者 | 验收后的小修(比重新派省很多) | — |
| 评审 | `general-purpose` + `model: opus`,只读 | 批末看合并 diff:泄漏/关域重载静态残留/空引用/每帧 GC/Cheat 隔离/字色铁规/行为回归;只报站得住的 | 不改文件 |
| 记忆整理 | `general-purpose` + `model: opus` | consolidate(到期时) | — |
| 基线截图+驱动手册 | `executor` + `model: opus`(批 1 开头) | 走真实路径到目标屏,三档截图,写 `PLAY_ROUTE.md` + 驱动脚本供后续所有棒复用 | — |
| **2D 出图**(图标/原画/贴图/decal) | **codex `gpt-6-astra`**(`codex exec -i <参考图> - < order.md`,产物落 `~/.codex/generated_images/`);Chrome MCP 的 ChatGPT 网页版是备选 | 概念图、图标集、原画、3D 贴图(地面/墙面/烧灼痕迹等 decal)、UI 贴图;主脑逐张审,不满意换 prompt 重出 | 不自己合成"差不多"的图顶上;astra 额度烧得快,别无脑全用 |
| **3D 建模**(建筑/道具/地标/飞船…) | **`executor` + `model: opus`(Opus 5.5)在 Blender 里跑 bpy 脚本;质量到顶不达标 → `tripo` CLI 出底模(先备多视角图)→ Opus 5.5 + Blender 精修**(2026-10-06 勾哥改口:「建模不要用 sol 和 astra 了,优先用 opus 5.5 在 blender 中建模」) | 写 bpy 脚本建模→渲染转台/三视图自审图→主脑对照竞品截图审→`SendMessage` 回同一执行者打回续做,直到对齐成品手游 | 不接受"有个形就行";一件模型通常要 2–4 轮打回;**不派 sol / astra 建模** |
| **音效** | `executor`·opus(Coplay `generate_sfx` 可用就用;401 → 已购音效包挑选 + 程序化合成脚本) | 按事件表配 SoundEvent、接项目 AudioService、裁剪/响度统一;循环音做成点缀 | 不能替勾哥"听"——听感验收留给他,汇报里明写 UNVERIFIED |

**编辑器只有一台 → 施工必须串行**;调研/方案/评审不占编辑器,可与施工并行。派活顺序按「勾哥最想先看到的」和「文件冲突最小」排。

## 3. 建档(批 1 开头做一次)
- 交付目录:`D:\screenshots\ER_<屏名>_<日期>\`(勾哥要求,scratchpad 会被清):`baseline\`(三档现状)、每片 `S1\`/`B2\`… 截图、`final\BEFORE_AFTER_*.png`、`PLAN_*.md`、`WORKORDER_*.md`、`PLAY_ROUTE.md` + `scripts\`。
- **先派一棒截基线并写驱动手册**:真实玩家路径(从哪点到哪)、每步的 Coplay 调用、怎么切 Game 视图三档分辨率(1080×1920 / 2340 / 2640)、怎么截图(Coplay capture 看不到 screen-space UI,用项目的 `ScreenCapture` 机制)、怎么干净退出。后面每棒都照抄,省掉重复摸路。
- 现状裁图:按 topic 从基线裁出局部放大(`now_<id>.png`),写表时放「现状图」列。

## 4. 调研工单(每 topic 一路)
工单要素:背景一段(品类/美术风格/这一屏是什么)、**勾哥原话**、方向种子(列 6–8 个不同 approach,允许增删)、每参考一张真实游戏内图(长边≥700,curl 带 UA,webp 转 jpg,存 `Competitive Research/images/<game>/<game>_<source>_<屏><id>_<nn>.<ext>`,**必须 Read 亲眼确认**)、先 Grep `_manifest_*.md` 复用库里已有图、盘点项目内可用资源(kit sprite/widget/字体/材质)、额外 action ≥6–12 条允许冗余。
**输出严格 JSON**(主脑不再手打):
```json
{"id":"B1","title":"…","goal":"≤40字","cause":"≤80字(基于代码现状)","now_img":"now_B1.png",
 "rows":[{"dir":"方向≤10字","game":"游戏·场景","img":"<game_dir>/<file>","how":"≤35字","action":"≤45字可执行","cost":"S|M|L","rec":"★ 首选:理由|可选:理由|备胎:理由","src":"URL","srcname":"Steam/Fandom/…"},
         {"dir":"额外·xxx","game":"灵感来源","action":"…","cost":"S","rec":"可选"}]}
```
主脑拿到后:**contact sheet 抽验**(`templates/polish/contact.py` 拼版一张图,Read 一次看全部)→ 调 `rec`(翼德建议)→ 去重跨 topic 重复图 → 进表。
**选竞品不限品类**:meta/UI 看 Supercell(Brawl Stars/Clash Royale/Squad Busters)、主机成品(Helldivers 2/DRG/Hades/XCOM)、SLG(Whiteout/RoK);地图/沙盘看 Bad North/Islanders/Dorfromantik/Civ VI/Zelda;同品类撤离(Delta Force/Arena Breakout/头号禁区)看题材语义。

## 5. 表格规格(勾哥的讨论真源)
- 列:`# | 现状图 | 方向 | 参考游戏 | 对照图 | 他们怎么做 | Action 候选 | 成本 | 翼德建议 | 勾哥拍板 | 讨论备注 | 来源`;表头冻结;第 2 行一句用法。
- 每 topic 一条色带(标题+目标+现状根因),带图行在前(行高 190,对照图嵌格),额外 action 行在后;「现状图」列按 topic **纵向合并**并**顶对齐**,现状大图挨着参考图看;★首选行黄底;来源列用超链接。
- 表尾「**定案施工单**」(片/名称/做什么/依据行/状态):拍板后填,每棒完成把状态改 ✅+commit hash;下一批追加 Batch 块(topic/原话/做法/状态)再接对照块。
- **写表管线**(`templates/polish/gen_sheet.py` + `sheet_helpers.js`):block JSON → payload(HTML 表 + 图片放置表 + 行高)→ Chrome MCP 合成 paste 贴表 → `file_upload` 把图传进页内 `<input type=file>` → 合成 paste 落浮动图 → JS 点「Put image in selected cell」。**一份 JSON 同时生成表格与知识库 md + manifest**。
- **写表三坑(都踩过)**:① 页内长任务(贴 8 块/嵌 72 图)用 **window.__job 完成标记 + 轮询**,**超时后绝不再发任何会改 selection 的脚本**(会把块贴错位、图漂到别处);② 嵌图失败的要重试,失败残留的**浮动图**要逐张选中 Delete;③ 带 colspan 的 HTML 表会撑宽列,贴完复位列宽;`white-space:normal` 不一定生效,选区后用 `alt+/` 菜单搜索「Wrap text」「Text align: Middle/Top」真点。
- 写中文/格式/图都走合成事件,不碰系统剪贴板(和勾哥共用会互相污染)。

## 6. 拍板 → 方案 → 施工
### 6.1 弹窗只问真岔路
每批 ≤4 问,推荐项放第一并标 (Recommended),每项一句利弊+成本;互相牵连的 topic 先问「整体路线」(如:连续地图 vs 切块模型台)。勾哥答完**立刻落表**(拍板列+备注)并改相关记忆/GDD(以现状为准就回写 GDD,注明日期)。

### 6.2 方案工单要它回答
① 每片改动清单精确到文件/方法/新文件、关键公式与算法可照做;② 数据流只复用已有事件/属性,不新造总线;③ 性能预算(顶点/RT/DC/overdraw/初始化耗时/低端档降级);④ 风险与暗坑(共享资产耦合、关域重载 static、shader strip、烘焙回执、单 mesh 65k);⑤ 验证方法(真流程/三档/防回归);⑥ 切片顺序与工作量;⑦ 只列真岔路。方案文件主脑**落盘保存**(上下文会被压缩),施工工单只引用章节。

### 6.3 施工工单模板(`templates/polish/workorder_template.md`)——必含
- **必读**:方案章节、现状截图、参考图(Read)、要改的源码、驱动手册、项目 CLAUDE.md、相关技能/记忆。
- **验收口径 = 勾哥原话 + 拍板**,并写明「你对好不好看负责,调到截图真的好看为止,不是能跑就交」。
- **范围围栏**:列出"不要动"的文件/系统(别的棒刚改完的)。
- **硬性约束**:不改共享资产与烘焙工具(`git diff <共享目录>` 为空 + 回执校验 PASS);2D 回退/旧路径不许坏;float 分支不用 shader_feature;关域重载 static 复位;运行时对象 OnDestroy 销毁;只用确认存在的 API;日志按周围风格;**每次改文件前先 `get_unity_editor_state` 确认 playMode=false**(五棒里四棒违反过这条,要写进去);改完 `check_compile_errors` 再进 Play;不 save 被自动标 dirty 的场景;不碰 ProjectSettings;收尾 stop Play + 还原 Game 视图;不 commit/push;不跑 scope.js;**一回合连续干到底,没有 watcher 会叫你**。
- **验证清单**:编译零错;真流程三档截图(+ 该片特有视角);**每张 Read 亲眼看并迭代**;真点击回归;state-dump 原值;防回归;`git status --short`。
- **汇报格式**:改动清单 / 证据(截图绝对路径+dump 原值)/ 画面自评逐项 / **偏离与欠账逐条**(不伪造验证)。

### 6.4 主脑验收纪律
- **不信汇报,看图**:每棒至少 Read 1 张整屏 + 1 张关键局部拼图(`contact.py` 拼多张省 token);对比基线与上一棒。
- 通过 → `git add -- <显式路径>` + `git commit -- <显式路径>`(共享工作树,只提交这一棒的文件)→ `scope.js attest` 写具体证据 → 表格状态列 ✅。
- 不通过 → `SendMessage` 同一执行者,写清「主脑看到的具体问题 + 要改成什么 + 怎么验」。
- 执行者汇报里的「偏离与欠账」原样转给勾哥,不洗白;发现别的工地的东西(DTO 缺字段、ProjectSettings 被编辑器改)只上报不代修。

## 7. 美术与建模通道(项目缺素材时自产到满意为止,不等美术)
### 7.1 2D 出图(图标 / 原画 / 贴图 / decal)
1. 先试 Coplay `generate_or_edit_images` 一次;401 = 未授权,别反复试。
2. **主通道 = codex 的 astra**:`~/.codex/config.toml` 里 `model = "gpt-6-astra"`,codex CLI ≥0.160 的 `image_generation` 可用:`codex exec --sandbox workspace-write -i <参考图1> -i <参考图2> - < order.md`(prompt 走 stdin),产物落 `~/.codex/generated_images/`;打回续做 `codex exec resume <session id> - < feedback.md`(session id 在 stdout 日志头)。参考图喂项目现有 KV/kit 预览保证画风一致。
3. **备选 = ChatGPT 网页版**(勾哥授权后):Chrome MCP 打开 chatgpt.com(已登录)切 Chat 模式,`type` 整段 prompt + Return;轮询 `main img` 的 naturalWidth 与 stop-button 消失;`fetch(img.src)→blob→a[download]` 存到 Downloads 再拷进交付目录(告诉勾哥这一步)。**同一会话续 prompt**,画风自动一致(「Same hero, same art style…」)。桌面版没有稳定操控通道(会和他抢键鼠),用网页版并说明。
4. **prompt 配方**:图标集 = 「N 个 … 排成 R×C 网格、均匀留白、**纯品红 #FF00FF 平底、无阴影无文字**、Supercell/Brawl Stars 风、厚白边+深描边圆徽+粗壮卡通物件+柔 cel shading+小高光、尺寸一致」;原画 = 「主角描述(保持一致)+ 场景 + 画风(高饱和厚涂卡通)+ **构图规则**(将被裁成 4:1,主体在左半中带,右 40% 留给 UI,上下只放叶子天空)+ 无文字无 UI」;**3D 贴图/地面** = 「无缝可平铺(seamless tileable)、正交俯视、均匀打光无投影、卡通手绘质感、指定 2–3 档色、1024/2048 方图」+ 用 PIL 验平铺接缝;**decal(烧灼/裂缝/苔藓/弹痕)** = 「透明底、单个元素居中、边缘羽化、无投影」+ 切图抠底。
5. 切图:`matte-icon-slicer` 技能(品红底自动键色+去边)→ **按连通域只留主体**(否则带进隔壁图标的边)→ 残留品红/粉色用阈值再抠 → 导出 256/128(地图用)或 512(UI 用);导入 Unity:Sprite(2D and UI),地图小图标**开 mipmap**,压缩对齐同类资源 .meta;贴图走 gaoguang-3d 的材质口径。
6. 主脑**逐张 Read 审**,不满意就在同一会话让它重画那一张;「refine 到满意」是硬要求,不是出一版就用。

### 7.2 3D 建模(对齐成品手游,多轮迭代)
- 工具:本机 Blender(winget 官方源装,先 [[verify-install-source-authenticity]]),脚本化建模(bpy),管线脚本进仓库 `ArtWork/<工地>/gen/`,渲染自审图 `ArtWork/<工地>/renders/`(大文件目录不跟踪)。
- 流程:① 主脑先拿 2–3 张**同类成品手游的模型截图**当标尺(Brawl Stars / Clash of Clans / Squad Busters 的建筑、载具、地标),写建模单(尺寸、轮廓语言、面数预算、色块数、描边/倒角、贴图方式、必须有的细节如烧灼痕迹/舱门/天线);② 派 **`executor`·opus(Opus 5.5)**写 bpy 脚本建模(headless `blender -b -P`)并渲染转台 4 视 + 一张与竞品同角度的对比图;③ 主脑 Read 对比图,按「轮廓/比例/细节密度/色块/质感」逐项打回(`SendMessage` 回同一执行者,它有上下文),通常 2–4 轮;④ Opus 到顶了先换建模思路(拆件/换轮廓语言/加参考图),仍不行上报勾哥,**不擅自改派 sol / astra**;⑤ **材质必须生图再贴**(勾哥 10-06 原话:「材质要生图然后 apply 然后你要迭代到满意对齐其它成品游戏 level 才行」):贴图/decal 由 7.1 的 astra 出(不拿纯色/程序化噪声凑),展 UV 贴上模型后重新渲染,主脑对照成品手游逐项打回贴图本身(笔触/色阶/磨损/接缝)和贴法(UV 比例/朝向),材质与模型一起迭代到对齐;UV 与材质按 `gaoguang-3d`/`tripo-blender-stylize` 的 ToonLit 口径接入;⑥ 进 Unity 后在真光照下再截一次对比(模型在引擎里和在 Blender 里不是一回事),不达标回到 ③。
- **三段式口径(2026-10-06 晚勾哥原话:「你用 opus5.5+blender,如果感觉模型质量达不到要求就用 tripo cli,之后用 opus5.5+blender 精修,注意提供好多视角视图减少返工」)**:① 默认 Opus 5.5 + Blender(bpy)建;② 主脑看渲染图判定到顶仍不达标(角色/怪物/有机体/复杂造型)→ 用本机 `tripo` CLI 出底模,**先用出图通道备好同一设计的多视角视图(正/侧/背/俯 + 3/4,白底、无透视畸变)并自审一致性再喂**;③ 底模交回 Opus 5.5 + Blender 精修(减面/硬边/toon 化/拆件/UV/材质,走 `tripo-blender-stylize` → `gaoguang-3d`)。仍不派 sol / astra 建模。
- 判据:**和参照手游并排截图看不出"我们这件是占位"**才算过。勾哥原话:「建模的精细程度要像成品竞品一样,对照着其它手游多次迭代」。
- 模型口径(2026-10-06 起):**建模优先 Opus 5.5,不用 sol / astra**(勾哥 10-06 原话见 §2 表;背景:astra 一个下午能把额度烧穿,基地页 10-04 实测)。astra 只留给 7.1 的 2D 出图。汇报里写明几轮打回。

### 7.3 音效与音乐(**唯一硬规则:零版权问题**;做法不僵化,勾哥在持续探索怎么把音效/BGM 生成得好,每次都可以试新路)
- **硬规则**:只用①已购且许可覆盖本项目的音效包/音乐包,②自己生成或合成的素材(AI 生成、程序化合成、自录),③许可明确可商用的来源(CC0 等,记来源)。来源不明、网上随手扒的、带他人作品片段的,一律不用。每条素材在汇报/映射表里写来源与许可。
- **可用的路(按当时能用的选,不按固定顺序;新工具出现就试)**:Coplay `generate_sfx` / `generate_music`(可用时最省事);codex astra/sol 这类模型若有音频能力也试;已购包(项目里已有 Cyberleaf UI / Cute UI / Epic Toon FX 等,先 Glob 盘点);程序化合成(仓库 `Assets/Audio/SFX/<域>/_gen/gen_*_sfx.py` 的 numpy 范式,适合 UI 点击/确认/tick 类短音);BGM 目前全项目尚无——做之前先问勾哥想要的风格与参考曲,用能生成完整曲子的工具,分段 loop 做成可切换的 intro/loop/outro。勾哥的话:「只要不出现任何版权问题就行」,其余自由发挥、多试、把好的路记回这里。
- **落地**:按「事件表」配(按钮按下/确认、tab 切换、卡片入场、合约切换、出发确认、建造开始/完工/揭幕、收取、奖励弹窗…),做成项目的 `SoundEvent`/`XxxSfxLibrary` 资产并接 `GameAudioConfig` 的槽位与 AudioService 调用点(主页那次查到 5 个 UI 音效槽与 `DefaultMusicEvent` 全空、代码早在调——先查配置是不是空的);响度统一(峰值/LUFS 对齐同类);**循环音做成点缀**(基地施工循环音太吵,改成近看时的 tick);BGM 与 SFX 分总线、有音量设置项。
- **验收**:执行者只能验「事件触发→播放调用→clip 非空→音量合理→许可记录齐」+ 导出波形/频谱截图;**听感必须勾哥本人验**,汇报里明写 UNVERIFIED,并给「哪个按钮听哪条」的清单;他听完的反馈回填到本节。

## 8. 成品级 checklist(交付前逐项过;哪项没做要明写欠账)
- **2D UI**:字体二分 + 字面白进描边(UIInk)无彩色字面;kit 同族底板不混用;图层完整(底板/高光/厚边/投影/图标/副行);空态有语义(ADD/锁/剪影)不是灰块;主 CTA 与主页同形同级;入场(卡滑入/逐个 pop)、按压(缩放+下沉)、常驻(呼吸/扫光)动效克制只给重点;三档长宽比不出框不互压;交互在 SafeArea 内;返回键栈;Ink Sweep 零命中;新件回填 widget 注册表。
- **3D 沙盘/场景**:抗锯齿(MSAA 关着就超采样)+ 网格密度足够;toon ramp + AO + rim;轮廓白边/高亮边框;周边不留纯色虚空(云/水/桌面);有厚度(裙边)不悬空;地标夸大+三级 marker 层级+目标光柱脉冲;路线有方向有分段色有 pulse;进页运镜+显形;按需渲染不白跑;性能预算与低端档;**改动只在自己的 shader/网格里,共享烘焙资产零改动**。
- **动效**:选中态要「大一档 + 外环脉冲/箭头」而不是只缩放 wobble;切换(模式/合约)有过渡(路线生长、镜头跟随);云/水/光柱常驻慢动;所有动效 unscaled 时间,触摸可跳过。
- **声音**:按 §7.3(零版权问题是唯一硬规则,做法可变)配齐事件表(按钮/确认/tab/卡片入场/合约切换/出发/建造三段/收取/奖励),接 AudioService,循环音做点缀;**简报页那次没做,基地页做了但听感未验——每批施工单必须排一棒音效,收尾请勾哥听**。
- **数据真实**:界面上出现的数字(消耗/负重/奖励)必须接真源,查不到就不显示并写欠账,不编。

## 9. 坑清单(每条都付过学费)
- Play 中改 .cs/shader = 可能卡死「Reloading Domain」/假故障——写进每张工单并要求先查 playMode。
- 执行者会把「等待」当回合终点——工单结尾必须写「一回合到底、没有 watcher」。
- `Plan` 类子代理只读、写不了文件;方案要主脑落盘或改用 general-purpose 限写一个文件。
- 子代理共用 scratchpad 会互相覆盖临时脚本——让它们用自己的子目录。
- 共享工作树:只 `commit -- <显式路径>`;别的工地的 WIP/编辑器自动改的 ProjectSettings 不碰不提交。
- Sheet:超时后的并发脚本会贴错位(见 §5);colspan 撑宽列;`Plan` 的图片 `img` 跨盘路径 relpath 会炸。
- 图标切图:自动框会带进隔壁徽章的边——按连通域取主体;品红底在半透明光芒处会残留——阈值再抠。
- 执行者报告的 dump 要有原值(像素/顶点/耗时/delta),没有原值的"验证过了"不算。
- 子代理会被看门狗判停(600s 无进展)——需要长跑的棒工单里写「不要再派子代理、不要起后台任务然后等它」。
- 截图/测试棒在 dev 号上会真花付费货币、真往世界频道发消息——工单写明「不花 GEM/体力、不发真消息」。
- astra 额度一个下午能烧穿;建模一律优先 Opus 5.5 + Blender(2026-10-06 勾哥改口,不再派 sol / astra 建模),astra 只出 2D 图。
- 翼德 stop hook 会在 scope 未收敛时拦截收工——等后台棒时用一句话状态回应即可,不要为了过审计把没做完的说成做完。
- Chrome MCP `navigate` 到**同一 URL**(只换 hash)不会重载页面:上一轮没跑完的嵌图循环会继续跑,和新循环抢选区 → 重复图/贴错格。要重置就 `location.reload()` 或先导去别的 URL;嵌图任务统一用 `__job` done 标志,等它结束前不要再发任何改选区的脚本。
- 勾哥可能正在同一台编辑器里试玩:执行者开工前 `get_unity_editor_state` 若 playMode=true,**等,不要 stop 他的 Play**(曾有执行者把勾哥的试玩停了)。工单里写明。
- 后台 `git push` 到 yide 仓被看门狗判 killed 不等于没推上——先 `git ls-remote origin main` 比对 hash 再决定重推。

- **对照图必须是干净实机画面**(2026-10-06 主玩法 25 题踩到):让调研代理自由找图,一半会是商店宣传合成图(叠大标题/立绘)或带主播框的封面,勾哥要的是「和我们实机并排比」。做法:调研工单里直接给 `python -m yt_dlp --download-sections "*MM:SS-MM:SS" --force-keyframes-at-cuts` + `ffmpeg -vf fps=1` 抽帧配方;标杆游戏另派「实机帧收割」(`templates/polish/harvest_prompt_template.md`,每游戏一路,产出带 topic 标签的 catalog + 拼版),调研回来后再派「换图质检」(`swap_prompt_template.md`,每 3 个 block 一路,只许改 img/src/how/game + 补标杆帧)。
- 并发子代理上限 20:题数多时侦察+基线+前 16 题先发,其余等通知补派;调研代理 3–6 分钟就回,**比侦察快**,别让它等 RECON——`cause` 由主脑用脚本从 RECON 的 `cause:` 行回填(RECON 每题固定一行 `cause:`)。
- 多路代理共用 scratchpad 会互相覆盖同名脚本(clips.py/sheet.py 被踩过)——工单给每路指定独立临时目录。
- 基线截图拆两棒(UI flow 一棒、战斗/场景/POI 一棒),每棒实耗 ~150k token;真 DEPLOY 扣体力、撤离是真结算会入库——工单写明允许几次。
- 多分页大表:先把模板页(表头/列宽/冻结)做好再 Duplicate 出各分页(tab 右键菜单用合成 contextmenu 事件可点,Rename 后真键入名字);**paste 会把垂直对齐重置成 bottom,预先设格式无效**——贴完再 `Wrap text` + `Text align: middle`,现状图合并格逐个 `Text align: top`。现成生成器 `templates/polish/gen_sheet_multitab.py`(多分页 + 现状图竖拼 + 总览页 + 知识库 md)。
- 传图用 base64 JSON 包(每包原图合计 ≤6.3MB,一次 `file_upload`,页内 `atob`→`new File`),比逐张列路径省一个数量级的 token;300 张图嵌格约 20 分钟(~3.7s/张),期间只轮询 `__job`。
- 表格标签是别的窗口里的后台标签时 `visibilityState=hidden` 嵌不了图;开工先查,hidden 就请勾哥把标签拖成独立窗口。
- Stop hook 在 scope 未收敛时会拦收工:等后台棒用前台 `until [ 条件 ]; do sleep 5; done`(timeout ≤590s)挂着等,通知会随工具结果一起到。

- **打磨要继承既有设计**(2026-10-06 主玩法被勾哥纠偏:「poi、采矿、contract 这些都有挺多 fix up,你要继承它们……不应该改掉,而是按照这些的精神提升到打磨成品 level;但也不要因此减少更改或者动作变形」):代码侦察之外必须加一路**「既有设计继承侦察」**(近 1–2 个月相关提交 + vault 设计文档/分区设计卡/术语表 → 「必须继承的骨架 / 可放手提升的表现层」对照表),调研、方案、出图工单都引用它;给勾哥看美术方向用**「现有 X 的成品化 paint-over」**(拿实机截图当参考图喂出图模型:同布局同功能同叙事,只提完成度),不出「新主题三选一」;继承不等于缩手,action 力度不打折。
- 续派(SendMessage)同一执行者共用它原来的 token 预算:上一棒已烧到 ~150k 的,续做单会直接 BLOCKED——收尾活另派新棒并把上一棒汇报里的关键参数写进新工单。

## 10. 收尾(每批)
1. 知识库:`Competitive Research/<屏>打磨对照_<日期>[_B2].md`(含「实现现状」附录)+ `_manifest_*.md` + README 两行 + `cp` 镜像到 vault `08 - 竞品研究/`(含新图目录)→ 只提交 md。
2. 记忆:工地文件(状态/提交/拍板/欠账/下一步/出图通道),MEMORY.md 一行索引;被取代的旧记忆加「⚠ 更正」。
3. 表格:施工单与 Batch 块状态列全部更新(✅+hash / ⚠欠账 / 施工中)。
4. Planyway:默认建 KAN issue 标完成(assignee 按当次 userEmail);战绩 `progress.js bump` 一次。
5. 向勾哥汇报:前后对比图路径、每 topic 一两句、**欠账与需要他拍板的**单列,不夸大。

## 先例(记忆里有全套过程资料与教训)
- 简报页 [[briefing-room-polish-worksite]](本法原型:对照表/弹窗拍板/分片施工/ChatGPT 网页出图/v2 地图 Cheat 对照)
- 基地页 [[base-page-polish-worksite]](3D 场景主题/Blender 建模迭代/实体施工演出/音效库/加速经济,两波)
- 主玩法 [[main-gameplay-polish-worksite]](25 题 288 图 659 action 的多分页大表;实机帧收割+换图质检两段式;三路代码侦察)
- 主页 [[home-tab-polish-worksite]](13 题 199 条 action 大表、音频配置为空的侦察)
- 美术自产路线 [[art-asset-production-routes]]

## 模板与脚本
`${CLAUDE_SKILL_DIR}/templates/polish/`:`gen_sheet.py`(block JSON → 表格 payload + 知识库 md/manifest;多分页大表用 `gen_sheet_multitab.py`)、`harvest_prompt_template.md` / `swap_prompt_template.md`(实机帧收割 / 换图质检工单)、`contact.py`(拼版验图)、`sheet_helpers.js`(Chrome MCP 页内助手:合成 paste / 嵌图 / 调行高列宽 / 任务标记)、`workorder_template.md`(施工工单)、`research_prompt_template.md`(调研工单)、`play_route_template.md`(驱动手册骨架)。用前先读一遍,路径和表头按本次替换。
