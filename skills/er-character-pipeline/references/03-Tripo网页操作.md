# 阶段 3/4/6a:Tripo 网页端(生成白模、上贴图、绑骨、预设动作、导出)

Tripo Studio:`https://studio.tripo3d.ai/workspace/generate`(还有 /texture、/rigging、/animate)。勾哥已登录。**点 Generate / Generate Texture / Auto Rig 都花点数,不能撤销**——勾哥在对话里说过"上 Tripo 生成、不满意可以 retry"就算授权;子 agent 不认转述的授权,这一步本会话自己做。不输入任何凭据。

## 3.0 浏览器验身(每次会话第一件事,不过不动手)
2026-10-07 整个下午操作的 Chrome 其实是另一台机器 DUCKCENTER(同 Tripo 账号、同 Google 同步),症状:勾哥看不到点击、导出提示成功但本机 Downloads 没文件、截图常超时。`list_connected_browsers` 的 `isLocal:true` 只说明系统相同,不可信。

1. 一次性加载工具:ToolSearch `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__file_upload,mcp__claude-in-chrome__list_connected_browsers,mcp__claude-in-chrome__select_browser`。
2. 在受控标签跑:
   ```js
   (async()=>{const u=await navigator.userAgentData.getHighEntropyValues(['uaFullVersion']);
   const g=document.createElement('canvas').getContext('webgl');const e=g.getExtension('WEBGL_debug_renderer_info');
   return JSON.stringify({ver:u.uaFullVersion,gpu:g.getParameter(e.UNMASKED_RENDERER_WEBGL),dpr:devicePixelRatio});})()
   ```
3. 和本机对:PowerShell `(Get-Item "C:\Program Files\Google\Chrome\Application\chrome.exe").VersionInfo.ProductVersion`。本机特征:GPU 含 NVIDIA/Intel、devicePixelRatio=1(DUCKCENTER 是 AMD)。版本号会随更新变,以当场查到的为准。
4. 对不上就停:请勾哥在本机 Chrome 的 militarypineapple 档案(Profile 2)里登录 Claude 扩展,然后 `select_browser`。不要在错的机器上"修下载/修权限"打转。
5. **开一个新的前台标签干活**(`tabs_create_mcp`)。后台标签会被节流:页面加载不完、截图失败。别用别的会话正在用的标签(10-07 共用标签里出现过别人的"石头遗迹门"项目)。

## 3.1 生成白模(结构参考 → 只要形状)
1. (不记余额、不对账——10-24 勾哥定。)
2. HD Model 页签 → 输入模式选第 2 个图标 **Multi-view Images to 3D**。槽位是 **Front / Left / Right / Back,按槽名放,不按顺序放**。上传 vault 里的结构参考四张(`file_upload`)。
3. 打开 General Settings → Geometry & Texture,**每次都逐项核对**(设置会自动保存,别的会话改过:10-07 发现面数被改成 200 万、PBR 被打开):
   | 项 | 值 |
   |---|---|
   | AI Model | H3.1 – Best Quality |
   | Ultra Mesh Quality | 开 |
   | Texture | **关** |
   | Topology | Triangle |
   | Polycount | head_ratio ≥ 0.20(Wren)填 60000;≤ 0.17(6.5 头身)填 **200000**,之后保脸减面到 58,000(SKILL 总纪律) |
   | Generate in Parts | 关 |
   按钮价格应显示 **30**(10-26 Coda 填 200000 也是 30)。不是 30 说明还有别的开关开着,先找出来。
4. Generate,约 4 分钟(Coda 200k 实测约 1 分钟出白模)。
   - 上贴图时,贴图页会自动带入生成时用的结构参考,要按垃圾桶清掉四张,再按槽名传平光定稿四视图;分辨率选 4K,Remove Lighting 关(10-26 Coda 照此做)。
5. 导出 GLB(带不带贴图都行),下载落在本机 `C:\Users\kryst\Downloads`。按时间找最新文件(`ls -t ~/Downloads | head`),拷到 `out/<slug>-tripo/tripo-web/gen-N/`,文件名写进 config `files.geo_glb`。
6. **每个下载文件先过 `inspect_model.py`**:10-07 拿到过一个"迟到落盘"的旧导出(时间戳 16:09,没有骨骼),差点当成新文件用。
7. 进阶段 5 的形状门(clay)。不过就重试:**改选项不改图**,最多 3 次,每次记选项。

## 3.2 上贴图(平光厚涂四视图 → 只要颜色)
1. 左栏 Texture → 选中刚生成的白模。
2. 输入选 multi-views。槽位会被自动填上结构参考图:**逐个删掉**(先删才露出上传框),换成阶段 1 定稿的平光厚涂四张,同样按槽名放。
3. Style:None(不选预设风格);Remove Lighting:**关**(参考图本来就是平光,开了可能把手绘色阶当光照抹掉);分辨率 **4K**(当母版,20 点)。8K 只有一次试用,不需要。
4. Generate Texture。导出 GLB(2K 贴图够进游戏),存 `tripo-web/gen-N/`,填 `files.tex_glb`。
5. 进阶段 5 的贴图门(unlit 对照、笔触、手臂底面)。

> 备选:如果白模这一步直接开着贴图出(Wren gen-1 就是,带 Ultra 约 45~60 点),脸也过了形状门,可以省掉 3.2。但只要脸有问题,就回到"两套参考图"的标准路径。

## 3.3 绑骨(Tripo 自动人形骨)
1. 左栏 Rig → 选中**带贴图的**模型。Rigging Type: Humanoid;Skeleton Preset: **Mixamo**(出 `mixamorig:` 命名,Unity 直接认 Humanoid);Auto Rig = 20 点。
2. 导出 GLB(带骨骼),存 `tripo-web/rig-N/`,填 `files.rig_glb`。`inspect_model.py` 应看到 ~65 根 mixamorig 骨 + 一个 42/80 顶点的 Icosphere(杂物,rig_build 会删)。
3. 注意:绑骨后的网格 UV 可能和生成时不同(Wren gen-1:顶点位置差 0.03mm,UV 差到 1.37)。**之后所有贴图处理(脏手臂清理、emission 遮罩)都在 rig GLB 上做**,不要拿生成版的贴图套。

## 3.4 预设动作(免费重定向,备用素材)
1. 左栏 Animate → Preset library。**每点一个预设,它就排进重定向队列,不扣点**。
2. 点慢一点:10-07 连点 26 个只成了 14 个,漏的 12 个**每个隔约 6 秒**补点才全到。
2b. 10-25 实测可靠做法:`find` 拿搜索框 ref → `form_input` 填预设名 → JS `[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===name).click()` → JS 轮询 `/Retargeting/.test(document.body.innerText)` 为 false 再点下一个(30~60 s,fold_arms/cheer 60 s+);两个一批放 browser_batch(三个会超时)。导出用 Choose Animations 的 Select All,计数要等于点的数;Export 后 Downloads 里是 .tmp,glTF 头 12 字节长度=文件大小即完整,直接拷走(坑 79/125)。
3. 导出面板里的动作列表不会自动刷新:关掉再打开看真实数量,对上了再导。
4. Export:格式 FBX,骨架预设 **Mixamo**,"Number of Animations" 选全部。下载是 zip,解开得到 `tripo_convert_<uuid>.fbx`,填 `files.anim_fbx`;`inspect_model.py` 列出 actions 和帧范围,数量要和点的一致。
5. 这些动作目前只是素材:游戏里先用工程现有 Humanoid 动画跑通。逐条 QA(手脚配合、滑步、穿模)和接进控制器是后续单独任务(`character-art-lab/prompts/wren-anim-qa.txt` 是写好的 QA 任务书)。

## 3.5 其他事实
- 价格(10-07 页面标价):HD 默认 30;关贴图 15;4K +10;Ultra +15;Quad +5;PBR +5;贴图页 2K/4K/8K = 10/20/30;Auto Rig 20;文生动作 20;预设重定向 0。
- DCC Bridge(推到本机 Blender/Unity)要装插件,没装,不用它。
- Tripo CLI(`tripo.cmd`,PowerShell 里直接 `tripo` 会撞脚本策略)能生成和绑骨,但:人形绑骨要显式 `model=v1.0-20240301`(默认 v2.5 是给非人形的);动作重定向 API 在勾哥账号上全是 1004,别再试;CLI 出的模型朝 +X。网页端选项更全,首选网页。
- 页面偶尔显示余额 0 + "Unknown server error",刷新即恢复。
