# 工具和坑(2026-11-20 星图试跑踩出来的)

试跑一屏从选屏到交评审页约三小时。下面每条都是当天真踩到、改过才通的做法。

## 拍现状图(第 0 步)

- `unity command capture game_view` 按编辑器窗口尺寸出图,会把 1080×2340 压成 1280×720,还会强制落进 `Assets/`。改用 eval:`UnityEngine.ScreenCapture.CaptureScreenshot("<本地临时目录>/x.png")`,下一帧才写盘,循环等文件出现再读。
- 不要直接拍进 Google Drive 下的 vault:同步程序会锁住刚写的文件(EBUSY)。先拍到 scratchpad,最后统一拷进 `<屏>_redo/shots_now/`。
- `job wait` 的比较符是 `equals / notEquals / greaterThan / lessThan / contains / changed`。写成 `gt` 会立刻报错返回,看起来像等过了,其实没等。拿它当延时用:`{"member":"UnityEngine.Time.frameCount","op":"greaterThan","value":99999999}` 加 `--timeout 秒数`。
- 拍图前占 Play 锁:`OWNER=<会话名> bash Tools/cargo_lock.sh acquire play <phase> <分钟> "<说明>"`,拍完 `editor.playmode stop` 再 `release play`。别人拿着锁就后台 until 循环等文件消失,不抢。
- 底栏、按钮这类 UI 用 eval 找到 Button 后 `onClick.Invoke()`,和玩家点击走同一条路径。`simulate_pointer` 点不到星图这类自己读 `Mouse.current` 的 3D 点选,改用反射调用控制器的点选方法(星图是 `StarSystemViewController.HandleTap(Vector2 屏幕坐标)`),坐标用 `Camera.main.WorldToScreenPoint` 算。
- 新手引导会挡住点选,这本身是盲测素材,要拍下来;后面的状态再中止引导(星图是 `Meta.StarSystem.Guide.StarMapGuideDirector.Instance.Abort("…")`)。
- 要一张没有 HUD 的干净场景底:把所有 `Canvas.enabled` 关掉(只关根 Canvas 不够,子 Canvas 还会画),等一帧再拍。同一帧把场景标记的屏幕坐标和 DTO 字段导成 JSON,新稿就按真位置、真数据摆名牌。星图这次因此查出「21 人里只有 2 个能打,名牌却都一样」和「推荐的是 HARD」。

## 出图(第 2 步)

- 功能图标走 codex:`er-shop-mkt/scripts/run_codex.sh <工作目录> <名字> 5`,参考图给 5 张 tab 图标(codex 最多带 5 张)。prompt 要求 3×3 网格、纯白底、每个图标有闭合的粗墨紫描边,一行一个图标、每行 3 个方向。
- 切图:`scripts/cut_grid.py <网格图> <输出目录> 名1,…,名9`。从每格边缘往里漫填白色,描边能护住图标里的白;输出 160px 透明 webp。切完拼到墨紫底上看一遍有没有白边。

## 可点击稿和截新稿状态(第 2、3 步)

- 单文件体积有上限(现行口径「流程」一节)。图片压成 webp 用 `content:url(data:…)` 嵌一次,只嵌用到的类。星图这次:地图底 720 宽 q62 约 34KB,整份可点击稿 226KB;方向板里没选中的图标放进评审页,不放可点击稿。
- 给稿子加 hash 驱动:`#shot&st=<状态>&a=<data-act 或选择器>,…`,shot 模式下隐藏页面控件、去掉圆角和过渡动画,按顺序触发点击,间隔约 650ms。
- 用 Chrome 无头逐状态截图:`chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=3 --window-size=360,780 --virtual-time-budget=5000 --screenshot=<路径> "file:///…html#shot&…"`。无头 Chrome 的最小窗口比 360 宽,shot 模式里 body 要靠左对齐,不能居中。
- 无头的虚拟时间里 `requestAnimationFrame` 会晚到,把已经关掉的卡又打开。打开动画用可取消的 `setTimeout`,关闭时一并清掉。
- `scripts/contact_sheet.py` 把所有状态拼成一张总览,自测时一次看完;疑点再按原分辨率裁出来看(缩略图会骗人,星图引导态在总览里看着发暗,裁出来是对的)。
- 内置浏览器打不开 scratchpad 里的本地文件(只给静态快照、页面工具不能用);拷进 vault 再打开,JS 能跑。

## 三路评审和合成

- persona 用便宜模型,五个同时派,第二轮用 SendMessage 续同一个 agent,让它对比前后。派单写死「只读这些图,不看别的文件」。
- 合成时每加一条 persona 要的信息,先查这屏的设计文档红线。星图这次给玩家气泡加「预计战利品」,撞了 04 文档「不显示可抢预览」的红线,只能列进待拍板,不能当成已定。
- 演示数据从实机导出的 JSON 里挑,挑之前看清字段:这次被打演示挑了一个同盟玩家,五个 persona 全看出来了。
