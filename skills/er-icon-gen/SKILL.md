---
name: er-icon-gen
description: ER(Extraction)出 icon 的唯一管线——攒批调本机 gemini 生图工具箱的无头 CLI(er_icon_cli.py),一张网格出 9~12 件、程序抠框切图、自动 QA、对照板在 Claude 窗口给勾哥点选,再入 Unity。Trigger on "出 icon" / "做图标" / "生成图标" / "画个图标" / "缺图标" / "这个物品没图" / "icon 攒一批" / "出图" / 物品、资源、货币、道具、弹药、奖励的 2D icon 需求。不管 3D 模型(gaoguang-3d)、KV/宣传图、UI 黑白 glyph。
---

# ER icon 生成(gemini 工具箱 CLI)

勾哥 2026-10-26 拍板:以后所有 icon 都走他自己调的 gemini 工具箱,不走 codex image_gen(他原话:"它的画风一致性调教比 codex 好")。画风以仓库物品图标为准,母版是 vault `01 - 星际拓荒重构/011_基地星/art/基地星icon_v4_style_reference.png`,默认参考就用它(勾哥 10-26 定 v4 样张)。可读性标准也是勾哥原话:"过于复杂了,放在手机屏幕上会花"——单一粗轮廓主体、少零件、不要细纹/网格/电路线。

工具在 `F:\AI\Claude\ER\`(只在 kryst 这台机器上,不在 git)。CLI 是 `er_icon_cli.py`,同目录 `HANDOFF_生图工具箱.md` §0.0 记着每条设计的实测依据。开工先确认这个文件存在;不存在就告诉勾哥这台机器没装工具箱,不要改用别的生图通道。所有命令用 `PYTHONUTF8=1 py -3 "F:/AI/Claude/ER/er_icon_cli.py" ...`(Bash,不走 PowerShell 管道喂中文)。

## 1. 先攒,不当场出

收到 icon 需求先入队,不花钱:

```bash
PYTHONUTF8=1 py -3 "F:/AI/Claude/ER/er_icon_cli.py" queue add Ammo_T2 "three rifle cartridges bundled together, silver casings with blue bands" --play item --note "勾哥 10-26 要"
```

队列只收勾哥原话说要生成的东西。AI 自己觉得"该补图"的放进汇报让他点,不进队列;"未选""一物多图"也不等于要生成。名字用 ASCII(会成为文件名 `玩法_名称_WxH.png`),play 是命名第一段(item / ui / weapon …,同类沿用已有前缀)。

什么时候出:同 play 的件攒到 9 件以上;或者勾哥说"出图 / 现在就要";或者这件挡住了手上的活。凑批时优先把同一类(同系列、同品阶)放一张网格,同网格出的兄弟件画风天然一致。

描述怎么写(这一步决定成败,写不好再贵的模型也救不回来):

- 英文,一件一个主物体,说清形状和两三种颜色;系列件用同一句式只换颜色和符号(Ammo_T1/T2/T3)。
- 允许一个简单符号(雪花、闪电、骷髅、爪印);禁任何要写字的东西,书/屏幕/牌子写明 blank surface。
- 不写画风形容词(画风由参考图给,写了会和参考打架);不写 glow/sparkle/shiny。
- 描述里不能有中文,CLI 会拦。

## 2. 出一批(一条命令一步,每步最多一次调用)

```bash
CLI="F:/AI/Claude/ER/er_icon_cli.py"
PYTHONUTF8=1 py -3 "$CLI" queue take --play item --n 12          # 写出 spec_<set>.json,默认 style_ref=v4、sizes=[256]
PYTHONUTF8=1 py -3 "$CLI" gen "F:/AI/Claude/ER/spec_<set>.json" --yes   # 1 次调用,打印批次目录
```

勾哥已授权这条管线按批出图,每批 1K 网格工具内置估价 $0.067(2K $0.101),不必逐批问;汇报里写这批花了几次调用。要 512 导出就在 spec 的 sizes 里写,CLI 会自己判断要不要上 2K。一批最多 12 件。

gen 完先看网格再 cut。看缩到 640 的版本省 token(`Image.thumbnail((640,640))` 存 scratchpad 再 Read),只核四件事:格数和顺序对不对、有没有字、每格是不是清单里那样东西、有没有复杂到手机上会花。

```bash
PYTHONUTF8=1 py -3 "$CLI" cut "<批次目录>" --ref <同类仓库图标.png ...>   # 0 次调用
```

cut 做的事:按蓝色面板程序抠框(不再调 AI 去框)、切图、按 `玩法_名称_WxH` 命名到 `<批次>/icons/`、写 `qa.json`、出 `sheet.png`(纸/牛皮/墨三底 128 + 48/32 手机档,`--ref` 的仓库图标并排在右边)。退出码:0 全干净;2 面板数或行数对不上,模型少画/多画了格,不往下切;3 有格子标红。名字标橙 = detail_loss > 24,细节偏多。

## 3. 出问题怎么补(按便宜程度)

1. 某一两格画错或太复杂:`fix "<批次>" --cell K [--desc "新描述"] --yes`,只重画那格,其余像素不动,然后重新 cut。
2. 面板数对不上(退出码 2):整张 gen 重来;重来前先看是不是清单太长或描述含糊。
3. 程序抠框整批不干净:`deframe "<批次>" --yes` 走 AI 去框,再 `cut`(自动用 deframed.png)。
4. 同一件两轮还不对就停,换描述思路或拿给勾哥看,别第三次硬烧。

别拿刚生成的图当下一批的参考,画风会接力漂;参考永远是 v4 母版(CLI 自动从里面挑最简单的格拼成同行列样张,`style_ref_used.png` 留在批次目录)。

## 4. 给勾哥看,他点了才算

把 `sheet.png` 用 SendUserFile(display render)发给勾哥,一句话说清每格的红旗/橙旗。他点"用"的才进下一步;"重出"的改描述放回队列(`queue add`,note 写上他的意见),下一批一起出。一个物品出现两张候选图时永远由他选,不替他挑。

## 5. 入 Unity

只搬他点过的图,放到同类现有图标所在的文件夹(资源/货币在 `Assets/Art/UI/CurrencyIcons/`,装备在 `Assets/Art/Equipment/Icons/Designed/`;别的类先 Glob 同类图标在哪,找不到就问)。导入设置照现有图标:textureType 8(Sprite)、spriteMode 1、enableMipMap 0、alphaIsTransparency 1、filterMode 1、maxTextureSize 2048、textureCompression 1。换物品图要不要改 `ItemDefinition._icon` 和 `GameContentCatalog` 快照,按 Item 视觉登记表的流程走(见项目记忆 er-item-visual-registry),勾哥没说换就只放文件不接线。

## 6. 现在不覆盖的

CLI 只包了物品 icon 工具的 prompt。装备整套(编辑真实截图那套)、枪械、UI 黑白 glyph、buff 九宫格仍在 GUI(`er_launch.pyw` 双击开 hub),要用这些先告诉勾哥 CLI 还没接,别拿物品 prompt 硬套。
