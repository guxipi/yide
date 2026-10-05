# 调研工单模板(翼德 polish——派 general-purpose·opus,每个 topic 一路并行;整段作 prompt,占位按本次替换)

竞品视觉/UI 调研任务(只调研+下图+写一个 JSON;**不许改项目代码/资产、不许运行 scope.js、不许 git commit、不许动 Unity 编辑器**)。中文输出,游戏名/术语保留英文,语言**极简**。

## 背景
<游戏一句话:品类/视角/美术风格/UI kit 与对标成品>。<这一屏是什么、结构>。现状截图(先 Read):`<POLISH_DIR>\now_<id>.png`、整屏 `<...>.png`。

## 本次问题 <id>
制作人原话:「<原话>」。<补充:现在是怎么做的、问题在哪>。

## 你要做的
1. 找 **<N>–<M> 个参考**,覆盖尽量多的不同方向/approach(每方向 1–2 个最佳实践),不限品类不限平台,手游优先。方向种子(自己验证、可增删,找到更好的就换):
   - <方向 1(游戏举例)> / <方向 2> / … (6–8 条)
2. 每个参考:一张清晰的真实游戏内截图(长边 ≥700px,确实展示该做法),curl 下载(带浏览器 UA;来源可用官方站/Steam/商店页/wiki(fandom)/媒体/Reddit/interfaceingame.com/gameuidatabase.com);webp/avif/gif 用 PIL 转 jpg/png;长边超 1600 缩到 1600。存 `<知识库>\images\<game_snake_case>\<game>_<source>_<屏><id>_<nn>.<ext>`(沿用已有子目录)。**必须 Read 每张图亲眼确认**展示的就是你声称的做法,不对就丢弃重找。先 Grep 上级目录 `_manifest_*.md`,库里已有的直接复用并给现有路径。
3. (按需)**盘点项目内可用资源**(只读):<kit 目录/字体/widget 注册表> 下能用的 sprite/件/材质,列「用途 → 路径」,Read 关键几张确认长相;说清缺什么。
4. 产出 action:每个参考一条「ER 可抄的 action」(≤45 字,具体到做什么),再给额外 action(≥<n> 条,允许冗余供取舍),**具体到图层/数值/用项目哪个现成资产**。成本按 Unity 手游实现难度:S≈半天内 / M≈1–2 天 / L≈3 天+。

## 交付(JSON,UTF-8,严格按 schema,键名不要改)
写到 `<scratchpad>\block_<id>.json`:
```json
{"id":"<id>","title":"<题>","goal":"≤40字","cause":"≤80字(基于你读到的现状)","now_img":"now_<id>.png",
 "rows":[{"dir":"方向≤10字","game":"游戏·场景","img":"<game_dir>/<文件名>","how":"他们怎么做≤35字","action":"ER 可抄的 action≤45字","cost":"S|M|L","rec":"★ 首选:理由 | 可选:理由 | 备胎:理由","src":"来源URL","srcname":"Steam/Fandom/…"},
         {"dir":"额外·xxx","game":"灵感来源","action":"…","cost":"S","rec":"可选"}]}
```
(`img` 相对 `<知识库>\images\`;无图的额外 action 行不写 `img`/`how`/`src`。)写完用 `python -c "import json;json.load(open(r'<路径>',encoding='utf-8'))"` 验证能解析。

## 最终回复(≤300 字)
文件路径;你最推荐的 2 个方向及一句理由;(若有)项目内资源盘点结论;图里要注意的(官方渲染/带标注/非实机)。
