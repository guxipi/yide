# 对照图质检与换图工单(ER 主玩法打磨 · 每个分页一路)

只改你负责的 `research\block_<ID>.json`(允许改的字段见下),外加按需入库新图。**不许改项目代码/资产、不许运行 scope.js、不许 git commit、不许动 Unity 编辑器、不许再派子代理**。预算约 100k token:图片一律看拼版,不逐张 Read。临时文件只放 `D:\screenshots\ER_主玩法打磨_20261006\research\swap_<你的分页号>\`(别用共享 scratchpad,会和别的代理互相覆盖)。一回合干到底。

## 为什么
制作人(勾哥)要把自家游戏现状截图和竞品**实机画面并排比**,对照表每个带图行的图必须是「一眼看得清该做法的干净实机画面」。第一轮调研里混进了不少商店宣传合成图(叠大标题/立绘)、带大字的 YouTube 封面、过小的图。另有三路代理刚收了一批干净的 1080p 实机帧(带标签 catalog)。你负责把你那几个 block 的图质检一遍,不合格的换掉,并把最好的 mo.co 实机帧补进去。

## 输入
- 你的 block:`D:\screenshots\ER_主玩法打磨_20261006\research\block_<ID>.json`(schema:rows 里带 `img` 的是带图行;`img` 相对 `C:\DuckGames\Extraction\Claude Feature Docs\Competitive Research\images\`)。
- 干净帧图库 catalog:`D:\screenshots\ER_主玩法打磨_20261006\research\harvest\*.json`(每条 `{file, shows, tags, src}`;`tags` 是 topic id)与拼版 `research\harvest\contact_<game>.jpg`(先 Read 这些拼版,心里有数)。
- topic 原话:`D:\screenshots\ER_主玩法打磨_20261006\TOPICS.md`。

## 要做的
1. 把每个 block 当前的带图行拼成一张 contact sheet(每格 ~480px,标 行号+文件名)Read 一遍。逐行判定:
   - **换**:商店宣传合成图(叠营销大标题/立绘/斜切框)、带大字或主播大头的封面图、长边 <700px、画面其实看不出 `how` 声称的做法。
   - **留**:干净实机截图/实机帧/官方实机截图(Steam 商店实机图算合格)、确实展示了做法的界面截图。
2. 换图来源优先级:① harvest catalog 里同游戏、`tags`/`shows` 对得上的帧;② catalog 里别的游戏但更能说明同一做法的帧(同时把该行 `game` 改成新游戏·场景);③ 自己抽帧:`python -m yt_dlp -f "bv*[height<=1080][ext=mp4]/bv*[height<=1080]" --download-sections "*MM:SS-MM:SS" --force-keyframes-at-cuts -o "<你的临时目录>\clip_%(id)s.%(ext)s" <url>` → `ffmpeg -y -i clip.mp4 -vf fps=1 f_%02d.jpg` → 挑帧入库 `images\<game>\<game>_ytframe_main<ID>_<nn>.jpg`;④ 实在找不到更好的就保留原图,并在 `how` 末尾标「(宣传图)」。
3. **补 mo.co**:每个 block 至少要有 2 张干净的 mo.co 实机帧(mo.co 是勾哥点名的头号标杆;G13/G14 至少 5 张)。不够就从 `harvest\mo_co.json` 里挑最贴题的帧新增带图行(完整写 `dir/game/img/how/action/cost/rec/src/srcname`;`rec` 用「可选:…」,除非它明显比现有 ★ 行更该首选)。每个 block 带图行总数上限 13。
4. 换图后 `how` 要和新图对得上(≤35 字);`src` 填新图来源(catalog 的 `src`),`srcname` 填 `YouTube 实机帧`。
5. **允许改的字段只有**:带图行的 `img` / `src` / `srcname` / `how` / `game`,以及新增带图行。**不许**删行、改无图行、改 `action`/`rec`/`cost`/`cause`/`goal`/`title`/`now_img`。
6. 改完:python 校验每个 block 能解析、每个 `img` 文件存在;把每个 block 的**最终**带图行再拼一张 contact sheet 存 `research\swap_<分页号>\final_<ID>.jpg` 并 Read 确认。

## 最终回复(≤250 字)
每个 block:换了几张、新增几行、保留的不合格图(及原因);还有哪类做法始终找不到干净实机图。
