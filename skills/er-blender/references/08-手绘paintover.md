# 08 手绘质感 paint-over:给模型加 mo.co 的笔触,任何场景复用

勾哥 10-30:模型太 basic,要用 paint-over 加 mo.co 的质感和笔触;10-31 看完 J01 全套后:"painter over 的把控尤其好,我需要未来根据不同的场景不断复用"。这一章就是复用手册:换场景只换一个配置 JSON,脚本不动。

**分工**:笔触由 sol 画(局内 2D 美术归 sol,代码不许画笔触或占位);Claude 出底稿、配准、投影、验收。看图验收必须亲眼看。

## 原理
在 Blender 里把模型按固定视角正交渲成"画布"(固有色乘柔和 AO,纯绿底,不打方向光)→ sol 在画布上原位手绘 → 配准回画布 → 每个面挑最正对、看得见它的视角,把画投影回 UV → 每类物件出一张图集。

**ER 的游戏镜头不转**(V5:从南 46° 俯视)。所以主视角就是"游戏镜头方向的正交视图 G",再补 E/W 侧视(0.6 倍密度,只在屏幕边缘斜着看到);朝北的面永远不上屏幕,不画。这样画的正好是玩家看到的那一面,张数也只有六面全画的一半左右。

## 五步(脚本在 `scripts/paintover/`)
```bash
B="<blender.exe>"; S=<yide>/skills/er-blender/scripts/paintover; W=<工作目录>; CFG=<配置>.json
"$B" -b <场景>.blend --factory-startup -P $S/po_canvas.py --python-exit-code 1 -- --cfg $CFG --out $W     # 1 底稿
py -3 $S/po_prompts.py $CFG $W                                                                             # 2 提示词
cat $W/joblist_<set>.txt | xargs -P 4 -I{} bash <yide>/skills/er-shop-mkt/scripts/run_codex.sh $W {} 4  # 2 sol 手绘(放进一个 run_in_background)
py -3 $S/po_register.py $W --set <set>                                                                     # 3 配准 + 门
"$B" -b <场景>.blend --factory-startup -P $S/po_project.py --python-exit-code 1 -- --cfg $CFG --work $W   # 4 投影 + 图集
"$B" -b <场景>_painted.blend --factory-startup -P $S/po_review.py --python-exit-code 1 -- --out $W --groups "标签=前缀"  # 5 评审图
py -3 $S/po_board.py <板>.png 2 760 "之前" a.png "之后" b.png ...                                          # 对照板
```

## 配置(`examples/` 有 J01 三份可抄)
| 字段 | 说明 |
|---|---|
| `set` | 名字;画布叫 `<set>_00.png`… |
| `groups` 或 `group_prefixes` | 一起画、互相遮挡的物件。母舱 = 壳 + 支脚一组;遗址每块残件一组;小件每件一组 |
| `views` | 默认 `["G","E","W"]`;也可以 `S N E W T` 六面正交 |
| `ppm` | 主视角像素密度。V5 实机约 71~77 px/m;J01 用过:母舱 62、遗址 70、小件 110、有顶屋 89 |
| `side_ratio` | 侧视密度系数,默认 0.6 |
| `underlay` | `col` = 顶点色 `Col`(我们 kit 生成的件);`material` = 物件原有的底色或贴图(Tripo 件、外来件) |
| `prompt.what / card / card_desc / colors / style_refs` | sheet 上画的是什么;过审概念卡(这件东西的成品画法);要保留的固有色;两张 mo.co 近景(先实看,红线⑥) |
| `fallback`、`atlas_scale`、`cut_m` | 第三轮兜底(默认开)、图集缩放(默认 0.75)、长面切段(默认 1 m) |

mo.co 近景参考存在 vault `013 美术/mo.co截图/裁切/expedition_mocoref_*_paintover参考_*.png`(石墙块、衣柜)。它们登记在参考登记表(Sheet「jungle lab」组件清单)「通用 / 人造物质感上限」行。新对象先查登记表里它自己那一行;要另挑和材质更接近的近景,按 `mo.co截图/INDEX.md` 挑好写回那一行再用,同一对象之后一直用这两张,不每次重挑。

## 门(全部要过)
1. **sol 门**:`run_codex.sh` 自动核 rollout,参考图张数必须等于 4。REJECT 原样重跑一次;连续两次 REJECT 停下查原因。J01 两批 33 张里有 2 张第一次被拦,重跑后通过。
2. **配准门**:`po_register` 判 PASS = 仿射配准后轮廓吻合度 ≥ 0.965,且 Lab 色漂 < 12。J01 33 张实测 0.970~0.999。
3. **内部漂移,必须人看**:轮廓门看不出"轮廓里的东西被挪了"(例如屋顶俯视是个矩形,肋画歪了也照样 PASS)。每张 sheet 和画布上下叠着看一遍。
4. **评审门**:46° 全景、3/4、游戏距离各一张,前后对比;再缩到 512 px 近景,和 mo.co 近景并排,逐项写差在哪(笔触、渐变、亮边、暗缝、斑驳频率)。有绿色、有品红(没投上的面)、有错位的竖纹 = 回去查,不交。
5. **引擎门**:进 Unity 后在真光照、V5 镜头下再截一次(两阶 toon 只是近似 LabLit)。LabLit 只吃这一张底色图。

## 坑(全是 J01 实际踩过的,每条都改进了脚本)
| 坑 | 症状 | 根因与做法(脚本里已处理) |
|---|---|---|
| 一个面横跨多格 | 屋顶出绿块、不存在的肋 | 面的中心落在半格里,两端却伸到别的格。投影前沿世界 X、Y 每 1 m 切开,并要求整个面落在格内 |
| 被挂件盖住角的面 | 货匣端面没上色 | 只要多数采样点可见就算可见,护角盖住采样点后被判成看不见。改成三轮:严格(中心 + 多数角点)→ 宽松(只看中心)→ 兜底 |
| 被前景挡了一半的面 | 门楼发光环被抹到旁边的小面上 | 宽松规则太松。先过严格轮,严格轮挑不出视角才降到宽松 |
| 侧面正好与主视角平行 | 肋旁一条条浅色竖纹 | E/W 视角被相邻肋挡住,主视角又看不到这个面。兜底轮:取最正对视图里投影位置的颜色 |
| 画布边缘抗锯齿混进绿色 | 倒角上一圈绿线 | 只信任内缩 3 px 的内部,向外延 40 px 留边;去绿只在边缘 8 px 带里做,否则苔藓绿、绿灰扣带会被洗成灰 |
| `mesh.materials.clear()` | 没投上的面渲成图集颜色(满屏绿) | 清材质会把所有面的 material_index 重置成 0。换材质一律按槽位原地替换 |
| 多个物件在 blend 里重叠 | 遗址互相"挡住" | 遮挡只在同一组内判 |
| 前台 shell 里 `cmd &` 起 codex | 任务被杀,没出图 | 并行一律放进一个 `run_in_background` 命令里,用 `xargs -P 4` |
| 打包只填当前行 | 45 张 sheet | first-fit 打包后 24 张 |
| 深色件被画成藏蓝 | 单件好看,和其它联邦件放一起对不齐色 | 勾哥 10-31 要统一:`prompt.colors` 写死「深色件是中性石板灰 #465C6D / #606F84,NOT navy, NOT blue」 |
| joblist 写成 CRLF 换行 | xargs 拿到"名字\r",找不到提示词,全部 REJECT | po_prompts 改成只写 LF(10-31 第一次复用时踩到) |
| 底稿画了方向光 | 进游戏明暗算两遍 | 底稿只有固有色乘柔和 AO;提示词禁方向光和投影 |

## 已知不足
- 大块白板的明暗对比比 mo.co 弱(10-30 勾哥选这版先铺开)。要加强时,在提示词里明确写"明暗对比和亮边加倍"。
- 室内面(进屋时屋顶隐藏后才看得到的面)要另出一套拿掉屋顶的底稿。
- 图集现在每类一张 3456 宽;手机上要不要拆成每栋一张或降到 2048,进 Unity 时定。
