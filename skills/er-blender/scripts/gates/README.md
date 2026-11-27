# POI 共用闸门(gates/)

POI 打回里多数能用数字判定(门口净区、挡路高度、精英位、楼梯宽、暗室被剪、整层上不去),各 POI 各写一套量法会口径打架,而且要等进引擎才发现。这里的脚本所有 POI 共用,阈值只放在 `thresholds.json` 一处,口径改了只改那张表。

| 脚本 | 什么时候跑 | 判什么 |
|---|---|---|
| `poi_nav_gate.py` | 装机前,用导出的 `.blend` 离线跑(Blender 后台,一个中型 POI 约 10 秒) | 按工程 NavMesh 参数模拟 Recast:各楼层走不到的地面(孤岛、暗室被剪)、每扇门两侧是否可达、门洞净宽 / 净高 / 墙楣、门口两侧家具净区、精英位离寻路面边距离、探点;每层一张俯视图 |
| `navdump_reach.py` | 装机烘焙后,读工程导出的真实三角形(不占锁) | 从入口出发,每个探点 / 门两侧 / 精英位是否在同一块连通的 NavMesh 上 |

**过不了不申请工程锁**;引擎里烘完再跑一次 `navdump_reach.py`,和离线结果对一眼。

## 命令

```bash
"<blender.exe>" -b <POI>.blend --factory-startup -P <yide>/skills/er-blender/scripts/gates/poi_nav_gate.py --python-exit-code 1 -- <POI>_gate.json <out_dir>
python <yide>/skills/er-blender/scripts/gates/navdump_reach.py <navdump.json> <POI>_gate.json <out.json>
```

退出码 0 = 过,3 = 不过(报告 `fails` 写原因),1 = 脚本出错。报告:`<out_dir>/nav_gate_report.json` + `nav_z±H.png`(绿 = 可达,深绿 = 半径 0.5 腐蚀边,紫 = 孤岛,红 = 寻路盖不到的地面,橙 = 小于 2 m² 被剪;黄点 / 品红 = 门过 / 不过,青 / 红 = 精英位过 / 不过)。

## 每个 POI 写一份配置(写一次,之后不改代码)

坐标一律是导出 `.blend` 的世界坐标(Z 朝上)。`navdump_reach.py` 读同一份,所以 NavDump 也要导出成同一坐标(样例 POI 的 `NavDump()` 已是)。

| 字段 | 必填 | 说明 |
|---|---|---|
| `floors` | 是 | 每层地坪高度,如 `[0.1, 3.8]`;走不到的地面只在这些高度 ±0.6 内统计 |
| `ground_z` | 否,默认 0 | 楼外 / 1F 地坪模型里没有(重烘才生成)时补的虚拟地面;`null` = 不补 |
| `door_leaf_regex` | 是 | 房门门扇名字规则(如 `^LF_0[45]_Door`)。门扇高 < `door_min_leaf_height`(默认 1.7)的自动当家具;`X__glass` 归门扇 X |
| `ignore_regex` | 建议 | **照抄安装器的 nav ignore 名单**(屋顶、雨棚、植物、发光件、线缆),否则雨棚顶会被当成走不到的地面 |
| `structure_regex` | 建议 | 墙 / 窗 / 楼板的名字规则:门口净区只统计家具,不把墙算进去 |
| `not_walkable_boxes` | 否 | `[[x0,y0,x1,y1,zlo,zhi],…]` 本来就不让走的空间(关着的车厢、封闭井道) |
| `seeds` | 否 | 入口外的点 `[[x,y,z],…]`;不写就用网格外圈的地面 |
| `probes` | 建议 | `{"房间名": [x,y,z]}` 每个房间、每层、屋顶各放一个 |
| `elites` | 是(有精英时) | `[[x,y,z],…]`,和安装器里的精英位一致 |
| `waive_zone` | 否 | 总控批过的门口净区例外(门名,报告里的 `door` 字段原样) |

样例:`examples/TS_gate.json`(含照抄安装器的 ignore 名单)、`examples/LF_gate.json`。

## 已知限制

- 近似 Recast:网格 1/6 m、身高 2 m、台阶 0.75、坡 45°、半径 0.5、最小区域 2 m²(取自工程 `ProjectSettings/NavMeshAreas.asset`,数值以 `thresholds.json` 为准)。它比引擎里的逐门测法严(会查整体连通),对楼梯坡度 / 体素取整比引擎宽一点:外挂梯离线判能走、引擎只烘出上半段的情况出现过。离线过了,引擎烘完仍要跑 `navdump_reach.py`。
- 门从门扇包围盒推:单扇 / 双扇(并排两扇自动合并)都行;开着的门、推拉门、没有门扇的门洞不会被当成门,要量就加 `probes`。
- 门口净区按门洞两侧「门洞宽 × 1.5 m」查,门框本身不算;0.05–2.0 m 高的非结构件都算家具。
- **NavDump 导出框要包住所有入口外 10 m**:按三角形中心裁框时,框外的楼梯段会让上层被误判成孤岛;碰到导出框边(`dump_box`)的连通块报 `unknown_cropped`。
