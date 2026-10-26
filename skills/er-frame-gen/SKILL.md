---
name: er-frame-gen
description: ER(Extraction)出头像框(avatar frame)的管线——调本机 gemini 工具箱的无头 CLI(er_frame_cli.py),白底网格一次出 ≤12 个圆框、程序抠外圈和中间开口、按开口归一化算 RefFrameToFace、查方头像四角有没有被盖住、对照板(圆脸/方脸/手机档)在 Claude 窗口给勾哥点选,再入 Unity 的 AvatarFrameDefinition + Registry。Trigger on "出头像框" / "做头像框" / "头像框储备" / "新赛季头像框" / "frame 没图" / "avatar frame" / 任何 frame.* 装扮缺图或要重做。物品/资源 icon 走 er-icon-gen;聊天气泡、称号、名字色不归这里。
---

# ER 头像框生成(gemini 工具箱 CLI)

勾哥 2026-10-26 拍的口径,出任何头像框都守:

- **正圆开口**(CARGO 头像 = Porthole 正圆)。环带要宽到盖住方头像四角(角点离圆心 0.707 个边长),这样资料卡/排行/聊天那些方头像处也能直接套,不改遮罩代码。
- **金、红、橙是高阶色,只给 BP 付费线的框。** 其余框按品阶色定主色:Common 灰蓝 #C9D6E6、Uncommon 绿 #4CC26B、Rare 蓝 #3B8BEA、Epic 紫 #9A3CF5(CARGO tokens)。描述里对非 BP 框写明 `no gold, no yellow, no orange, no red`。
- **不描黑边**,轮廓用本色压暗(ER 美术规范 + CARGO 物件画法)。旧 `Frame_S1_01~03`、旧 `frame_s2_*` 就是因为黑描边被重做。
- 手机可读:每个框最多两三个装饰,不要细纹、小雕刻、文字。

工具在 `F:\AI\Claude\ER\er_frame_cli.py`(只在 kryst 这台机器,不在 git;复用同目录 er_icon_cli / er_enemy_engine 的 key、限流和模型调用)。开工先确认文件在;不在就告诉勾哥,不换别的生图通道。命令一律 `PYTHONUTF8=1 py -3 "F:/AI/Claude/ER/er_frame_cli.py" ...`,走 Bash。

## 1. 先定需求再出图

头像框的需求真源:Config Hub `Cosmetics.Catalog`(Slot=frame 的行,Source 列是渠道)、`BattlePass.Tiers`(哪一级、免费还是付费线)、Expedition 各表里的 `*CosmeticId`。盘点表在 Item 视觉登记表(`1I25waTLU9S-u8-cvQCAI-cWfJFhAutlIQn8gOGdp_O4`)的「头像框」tab,新框先在那里加行(id / 主题 / 渠道 / 获取条件 / 稀有度 / 主色),再出图。表里没有的 id 标「提议」,不当既成事实。

## 2. 出一批(1 次调用)

spec 例子见 `F:\AI\Claude\ER\spec_frames_1026.json`。每项 `[文件名, 显示名, 英文描述, 英文配色]`,描述只写形状和装饰(画风约束 CLI 自带),不写中文。一批 ≤12 个,默认 2K($0.101/批,勾哥已授权按批出,不逐批问)。

```bash
CLI="F:/AI/Claude/ER/er_frame_cli.py"
PYTHONUTF8=1 py -3 "$CLI" gen "F:/AI/Claude/ER/spec_<set>.json" --yes   # 打印批次目录
```

gen 完先把 grid.png 缩到 1200 看一眼:个数、顺序、开口是不是空白、有没有字、非 BP 框有没有混进金色。

画风参考:第一批(10-26)无参考、纯文字约束出的,勾哥已点过的框可以写进 spec 的 `style_ref` 当后续批次的参考(只用他批过的,未批的新图不许接力当参考)。

## 3. cut(0 次调用)

```bash
PYTHONUTF8=1 py -3 "$CLI" cut "<批次目录>" [--face <头像.png>]
```

做的事:白底分块(不连环的气泡、信号弧等小件并进最近的框)→ 外圈白和中间开口白抠透明,开口边 2px 按白底反混合留软边 → 开口轻微椭圆(±18%)按两轴拉正 → 以开口圆心居中、头像面直径取「开口最远点 ×2」(叶子压进开口的地方由框盖住脸,反过来不会露底)→ 输出 `frames/<名>_512.png` 和 `qa.json`(ref = RefFrameToFace、cover = 方头像四角覆盖率)→ `sheet.png`(上排圆脸纸底、中排方脸墨底、下排手机档 72/56)。

退出码:0 干净;2 框数/行数对不上(框粘连或少画,重 gen);3 有红旗(cover < 0.995,方头像四角露出来)。橙旗:ref > 1.9(框比头像大很多,窄行里会压到邻居)或开口不圆,不挡流程,写进汇报让勾哥看。

单格不对用 `fix "<批次>" --cell K [--desc ...] [--palette ...] --yes`,改完重新 cut。同一格两轮不对就停,换描述或拿给勾哥。

## 4. 给勾哥点选

`sheet.png` 用 SendUserFile(display render)发出,再用 AskUserQuestion 让他点:一物多候选(如默认框 A/B)单选,其余多选"可入库"。只搬他点过的。

## 5. 入 Unity

- 图:`Assets/Art/UI/Cosmetics/Frame/<frame_id 点换下划线>.png`。重做的框原位覆盖 PNG,保留 meta(GUID 不变,定义和 BP theme 的引用不用动)。新图的 meta 照 `frame_s2_goldrush.png.meta` 抄、换 GUID、spriteBorder 清零(Sprite single,fileID 21300000)。
- 定义:`Assets/ScriptableObjects/Avatar/Frames/<名>.asset`(AvatarFrameDefinition),`_refFrameToFace` 填 qa.json 的 ref,`_accentColor` 填主色(会染资料卡头部渐变条),加进 `Assets/Resources/Core/AvatarFrameRegistry.asset` 的 `_frames`。
- id 常量:`Core.Services.Cosmetics.CosmeticIds` 和 `Core.Content.CosmeticIds` 两份都补;要在聊天里显示就在 ShortCodes 末尾追加短码(只追加,不改旧码)。
- 不碰 BP 配置表和 BattlePass 服务端/客户端代码;BP 奖励预览图在 `BPTheme_<season>.asset` 的 RewardIcons,要改先问 BP 那条线。
- 10-26 入库脚本在当时会话 scratchpad 的 `intake_frames.py`,思路:拷图 → 写 meta → 写/改定义 → 追加 Registry。

## 6. 实机看一眼

写 .cs 前查 playMode、拿 `Tools/cargo_lock.sh` 的 compile 锁;进 Play 拿 play 锁。资料卡(`UIHomeScreenPanel.OpenSelfProfile()`)上的 `UIAvatarFrame` 可以 eval 调 `SetFrameById("<id>")` 临时换框看效果(只改显示不改存档);衣柜头像框页 `ShowPanel<UICosmeticWardrobePanel>().SelectTab(1)`。`capture_game_view --save_path` 会存进 `Assets/Temp/`,看完挪走并删 .meta。测完 stop、放锁。

## 已知现状(10-26)

- CARGO 主页左上头像钮(CrewTag Porthole)的 `_avatarFrameImage` 在 HomeScreen.unity 里是空引用,装备的框在主页看不到;Porthole 带 Mask,框要挂在 Mask 外。
- 衣柜头像框页只列 BP 来源的框,商店/周榜/深潜/图鉴框不在列表。
- 衣柜格子比框小,ref ≥1.56 的框会压到相邻格。
