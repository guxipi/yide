# Playtest 冻帧标注 · 给勾哥的傻瓜配置(一次搞定)

**目的**:试玩时按一个键(默认 **F8**)冻帧、说出/打出问题,翼德自动把这些变成"哪里要改 + 在哪个脚本/Prefab"的清单。
**铁律**:你只做几件——按 F8 开始、测、说反馈(或打字)、F8 停录(屏上会自动出字、看一眼对不对)、F8 存。其余翼德全自动。

> 比录屏强在:翼德拿到的是**游戏内部状态**(命中的 GameObject/Prefab/场景),能直通代码;语音走 **Google Cloud STT(Chirp 3)**,海外可用、普通话准、带标点,停录即出字当场确认。

---

## 1. 放入标注工具(3 个文件)
1. `templates/qa/PlaytestMarker.cs` → 放进项目任意 `Scripts` 目录。
2. `templates/qa/Editor/PlaytestMarkerWindow.cs` → 放进任意 **`Editor/`** 文件夹(必须在 Editor 目录,否则出包报错)。
3. `templates/qa/Editor/PlaytestAsrServer.cs` → 同样放进 **`Editor/`** 文件夹(它在录音时把转写服务拉起来,让你"停录即看字")。

进 Play 模式它会**自动生成**(不用手挂物体);文件都用 `#if UNITY_EDITOR`(或 `|| DEVELOPMENT_BUILD`)包住,**不会进正式上线包**。
- 想换标注键:在场景里那个 `~YidePlaytestMarker` 物体上改 `Mark Key`(默认 F8;**别用空格**,通常被跳跃/确认占用)。

## 2. 配 Google Cloud 转写(Chirp 3)
不配也能用——降级成"只用打字 + 上下文"。配了才有语音自动转写。**为什么选它**:海外可用(不像腾讯/阿里要跨境)、普通话是它最准的语言之一、带标点、每月**前 60 分钟免费**(试玩这点量基本免费),超了 $0.016/min。Chirp 3 只在 **Speech-to-Text v2**,认证用 **service account**(不是简单 API key)。

### 2.0 先确认有没有 Google Cloud 账号(一看就知道)
浏览器打开 **https://console.cloud.google.com/** 用你的 Google 账号登:
- 顶部能选到一个**项目(Project)**、且左侧能进「Billing 结算」看到已绑卡 → **已有**,跳到 2.1。
- 提示要「创建项目 / 启用结算 / 同意条款」→ **从零**,按 2.1 全做一遍(新账号通常还有 $300 试用额度)。

### 2.1 GCP 一次性配置(从零也就 5 步)
1. **建项目**:Console 顶部「选择项目 → 新建项目」,起个名(如 `er-playtest`)。
2. **开结算**:左侧「Billing」给项目绑一张卡(开通才可用;Chirp 在免费额度内基本不花钱)。
3. **启用 API**:搜索栏搜「Cloud Speech-to-Text API」→ **Enable**。
4. **建 service account**:「IAM & Admin → Service Accounts → 创建」→ 给它角色 **Cloud Speech Client**(没在建账号时选成,可回 IAM 页「Grant access」补:Principal=该账号邮箱,Role=Cloud Speech Client)。
5. **拿凭证 —— 两条路,任选一条:**
   - **(A) 下密钥 JSON**:点该账号「Keys → Add Key → JSON」→ 下载那个 .json(=钥匙,别外传、别进 git)。
     ⚠️ **若报「Service account key creation is disabled / `iam.disableServiceAccountKeyCreation`」**(组织开了 secure-by-default,挡密钥下载)→ 别去关那条策略,直接走下面 (B)。
   - **(B) gcloud ADC 登录(推荐,无密钥文件)**:在**勾哥那台**装 Google Cloud CLI(`cloud.google.com/sdk` 一路 next),然后跑:
     ```
     gcloud auth application-default login          # 浏览器登有项目权限的 Google 账号
     gcloud auth application-default set-quota-project <你的项目ID>
     ```
     库会自动用这份登录,不用任何密钥文件、也绕开组织策略。(登录的账号需有 Cloud Speech Client 权限;用项目 Owner 账号最省事。)
6. **装客户端库**(勾哥那台装了 Python 的机器):`pip install google-cloud-speech`(轻量,**不带 PyTorch**)。
   - 默认 `python` 不对(venv / `py` 启动器)→ 在 Unity ⚙ 里把 **Python** 填对,或设 `YIDE_PYTHON`。

### 2.2 让 Unity 里"停录即出字"(配一次)
标注窗口会调 `integrations/playtest-capture/stt_google.py`(常驻,省 Python 启动)。进 Play 按一次 F8 → 窗口底部展开 **「⚙ 转写设置」**:
- **stt_google.py**:点「选择…」指到 `yide` 仓库里的 `integrations/playtest-capture/stt_google.py`。
- **服务账号 JSON**:走 (A) 的填那个 .json(会作为 `GOOGLE_APPLICATION_CREDENTIALS` 传给转写进程);**走 (B) ADC 的留空**(库自动用 gcloud 登录)。
- **区域**:海外填 `eu` 延迟更低(或 `us`)。
- **Python**:填装了 google-cloud-speech 的那个。
- 设一次永久记住。也可改设系统环境变量(`GOOGLE_APPLICATION_CREDENTIALS` / `YIDE_ASR_SCRIPT` / `YIDE_GCP_LOCATION`),Unity 自动读作默认。
- 项目 ID:(A) 从 JSON 自动读;(B) 从 `set-quota-project` 自动读;都要覆盖可设 `YIDE_GCP_PROJECT`。
- **事后 `翼德 playtest` 批量补转**用同一套凭证:(A) 需系统环境变量 `GOOGLE_APPLICATION_CREDENTIALS` 已设;(B) gcloud 登录过即可(它是另一个进程,读不到 Unity 里的设置)。

> ⚠️ Google 转写这步**尚未在勾哥机器端到端验证**(开发机无 GCP 凭证);脚本的 import/请求结构已在本机验过,但真转一句中文要你这边第一次跑确认。出不来翼德会如实报、自动降级成打字,不假装。
> 旧的本地方案 `asr_sensevoice.py`(funasr/SenseVoice,离线)仍留在仓库作应急备选,但默认走 Google,不再依赖它。

## 3. 隐私 & 数据
- 录的是**你的麦克风**;语音会发到 **Google Cloud** 转写(海外服务、非中国云)。Google 默认按其条款处理;如需更严可在 Console 开「不记录数据 / data logging off」(可能小幅加价)。
- 不想说话就**只打字**(标注窗口里有输入框,全程不发云)。产物都在项目 `QA/playtest/`,你能直接删。
- **service account JSON 是密钥**:别外传、别提交进 git。
- 建议把 `QA/playtest/` 加进 `.gitignore`(截图/录音是大文件,别进 git)。

## 4. 怎么用(配好之后)· F8 三段
1. 进 Playmode 玩,遇到问题按 **F8**(第①下)→ 冻帧 + 自动截图/抓上下文 + **开始录音**;「翼德 标注」窗口弹出(停在 Game 视图旁,不挡画面)。
2. 说出问题(中文)→ 说完按 **F8**(第②下)**停录** → 几秒后转写的中文**自动填进打字框**,你**看一眼对不对**,不对就直接改/补。(嫌吵不想说也行,直接在框里打字。)
3. 确认无误 → 再按 **F8**(第③下,或点绿钮)**保存**这条,解冻继续。`Esc` 随时取消当前条。
4. 测完回 Claude Code 说"**翼德 playtest**" → 翼德读截图 + 已确认的文字 → 出带定位的问题清单。

---

## 可选:整段屏幕录屏(老方案,默认不用)
若某场就想要"连续画面看手感",仓库里还留着 `playtest-rec.bat`(ffmpeg 录屏录麦)+ 旧的处理路径。**默认不启用**——冻帧标注已覆盖绝大多数反馈,录屏只在专看动效/手感时偶尔用。

## 验证边界(诚实)
冻帧/截图/抓上下文是确定性的 Unity 调用;**Google STT 转写、真机录音**这两环需你这边真环境验一次(脚本 import/请求结构已在开发机验过,真凭证+真转写没验)。翼德跑时如实报结果,不冒充。
