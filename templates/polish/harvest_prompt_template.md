# 实机帧收割工单(ER 主玩法打磨 · 给对照表换干净的竞品实机图)

只下视频片段 + 抽帧 + 写一个 catalog JSON。**不许改项目代码/资产、不许运行 scope.js、不许 git commit、不许动 Unity 编辑器、不许再派子代理**。预算约 100k token:图片一律拼版后再看。一回合干到底,没有 watcher 会叫你。

## 为什么
制作人要把自家游戏(ER:俯视角搜打撤射击手游,toon 风,对标 mo.co)的现状截图和竞品**实机画面并排比**。第一轮调研里很多图是商店宣传合成图(叠大标题/立绘)或带主播框的缩略图,不合格。你负责给指定游戏收一批**干净的 1080p 实机帧**,建成带标签的图库,后面按标签替换进对照表。

## 怎么做
1. 找该游戏的实机视频(YouTube;优先 "no commentary" / 官方 gameplay / 4K-1080p 录屏;避开带主播摄像头框、大字幕、片头的段落)。`python -m yt_dlp --flat-playlist "ytsearch8:<query>" --print "%(id)s %(duration)s %(title)s"` 可搜。
2. 只下小段再抽帧(本机有 `python -m yt_dlp` 与 `ffmpeg`):
   `python -m yt_dlp -f "bv*[height<=1080][ext=mp4]/bv*[height<=1080]" --download-sections "*MM:SS-MM:SS" --force-keyframes-at-cuts -o "D:\screenshots\ER_主玩法打磨_20261006\research\harvest\tmp_<game>\clip_%(id)s_%(section_start)s.%(ext)s" <url>`(每段 ≤10 秒;多段可重复 `--download-sections`)
   → `ffmpeg -y -i clip.mp4 -vf fps=1 f_%03d.jpg` → PIL 拼版(每格 ~480px,标文件名)→ Read 拼版 → 挑帧。
   不知道哪一段有什么:先用 storyboard/低清整段(`-f "bv*[height<=360]"`,整段下完用 `ffmpeg -vf fps=1/8` 抽稀拼版)定位时间点,再回头下 1080p 小段。
3. 每个覆盖点挑 1–3 张**最能说明做法、没有运动模糊、UI 完整**的帧,拷进图库:
   `C:\DuckGames\Extraction\Claude Feature Docs\Competitive Research\images\<game_snake_case>\<game>_ytframe_mainH_<nn>.jpg`(沿用已有子目录;nn 从 01 递增;长边超 1920 缩到 1920,jpg 质量 90)。
4. 写 catalog:`D:\screenshots\ER_主玩法打磨_20261006\research\harvest\<game_snake_case>.json`:
   ```json
   [{"file":"mo_co/mo_co_ytframe_mainH_01.jpg","shows":"≤40字:画面里是什么、能看清哪种做法","tags":["G01","G07"],"src":"https://youtu.be/<id>?t=<秒>"}]
   ```
   `tags` 用 topic id(见 `D:\screenshots\ER_主玩法打磨_20261006\TOPICS.md`,先读)。写完用 python 校验 JSON 能解析、每个文件存在。
5. 最后把你入库的全部帧拼成 1–2 张 contact sheet 存 `research\harvest\contact_<game>.jpg`(每格标 nn)。

## 覆盖点(每个游戏尽量都要有;该游戏没有的就跳过并在回复里说明)
战斗命中瞬间(伤害数字/命中闪光/击杀) · 群战割草 · 敌人攻击预警(地面红区/弹道线)与玩家瞄准/射程提示 · boss 登场与 boss 战(血条) · 完整 HUD 静止画面 · 小地图/大地图 · 目标追踪与屏外指示 · 掉落物/光柱/拾取吸附/开箱 · 背包/装备/搜刮界面 · 不同主题地图的**地面与场景**(每张地图至少 1 帧,地面看得清)· POI/巢穴/事件点 · 事件横幅(开始/完成/倒计时)· 结算/胜利/撤离/死亡 · 玩家角色近景(动作姿态)· 敌人近景 · 环境动效元素(水/草/传送门/光)· 新手引导/交互提示(有就收)

## 最终回复(≤200 字)
catalog 路径、入库帧数、每个覆盖点各几张、哪些覆盖点没收到及原因、用了哪些视频。
