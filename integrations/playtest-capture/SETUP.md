# Playtest 冻帧标注 · 给勾哥的傻瓜配置(一次搞定)

**目的**:试玩时按一个键(默认 **F8**)冻帧、说出/打出问题,翼德自动把这些变成"哪里要改 + 在哪个脚本/Prefab"的清单。
**铁律**:你只做几件——按 F8 开始、测、说反馈(或打字)、F8 停录(屏上会自动出字、看一眼对不对)、F8 存。其余翼德全自动。

> 比录屏强在:翼德拿到的是**游戏内部状态**(命中的 GameObject/Prefab/场景),能直通代码;语音走**本地 SenseVoice 离线转写**,不上云、不跨境(适配在海外)。

---

## 1. 放入标注工具(3 个文件)
1. `templates/qa/PlaytestMarker.cs` → 放进项目任意 `Scripts` 目录。
2. `templates/qa/Editor/PlaytestMarkerWindow.cs` → 放进任意 **`Editor/`** 文件夹(必须在 Editor 目录,否则出包报错)。
3. `templates/qa/Editor/PlaytestAsrServer.cs` → 同样放进 **`Editor/`** 文件夹(它在录音时把本地转写服务拉起来,让你"停录即看字")。

进 Play 模式它会**自动生成**(不用手挂物体);文件都用 `#if UNITY_EDITOR`(或 `|| DEVELOPMENT_BUILD`)包住,**不会进正式上线包**。
- 想换标注键:在场景里那个 `~YidePlaytestMarker` 物体上改 `Mark Key`(默认 F8;**别用空格**,通常被跳跃/确认占用)。

## 2. 装本地中文转写(SenseVoice)
不装也能用——降级成"只用打字 + 上下文"。装了才有语音自动转写。**为什么不用 Whisper**:它中文口语弱;SenseVoice 中文强、快、纯 CPU 可跑、自带标点。

**默认:funasr(本地 SenseVoice)** —— 顺序要对(经 funasr/SenseVoice 官方文档核实):
1. 装 **Python 3.10 或 3.11**(python.org;勾上 **Add Python to PATH**)。验证 `python --version`。(官方对上限口径不一,3.10/3.11 是 wheel 覆盖最稳的区间。)
2. **先**装 PyTorch(CPU 版,官方 CPU 源、不拉 CUDA)—— funasr **不**自动带它:
   `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu`
3. 装 funasr(会自动带 modelscope/huggingface_hub/soundfile,**不用单独装 modelscope**):
   `pip install -U funasr`
4. **再显式补一遍 `soundfile`** —— Windows 上 torchaudio 默认没 wav 解码后端,不补会报"找不到 backend":
   `pip install soundfile`
5. 自检装好没:`python -c "import torch,torchaudio,soundfile; from funasr import AutoModel; print('OK')"` 打印 `OK` 即成。
6. **首次转写**自动拉 SenseVoice 模型(~900MB,一次性,需联网)。默认走 ModelScope;**海外连慢 → 设环境变量 `YIDE_ASR_HUB=hf` 切 HuggingFace 源**(脚本已支持)。之后翼德跑 `scripts/playtest.js` 自动调它批量转写。
   - 若默认 `python` 不是装了 funasr 的那个(venv / `py` 启动器),设 **`YIDE_PYTHON`** 指到对应 python.exe。
   - ⚠️ 别把测试脚本命名成 `funasr.py`/`torch.py`(会触发循环导入报错)。

### 2.1 让 Unity 里"停录即出字"(配一次转写脚本路径)
为了试玩时**当场看到转写、确认对不对**,标注窗口会调常驻服务 `integrations/playtest-capture/asr_server.py`(和上面同一个模型,只是常驻、不每次重载)。Unity 在你的 ER 工程里,得告诉它这个脚本在哪:
- 进 Play 按一次 F8,「翼德 标注」窗口底部展开 **「⚙ 转写设置」** → 把 **asr_server.py** 指到 `yide` 仓库里的 `integrations/playtest-capture/asr_server.py`(点「选择…」选文件即可),**Python** 填装了 funasr 的那个(默认 `python`),海外把 **模型源** 填 `hf`。设一次永久记住。
- 也可改设环境变量 `YIDE_ASR_SCRIPT`(指向 asr_server.py)+ `YIDE_PYTHON` + `YIDE_ASR_HUB`,Unity 会自动读作默认值。
- **没配也能用**:停录后不自动出字,照常打字即可;事后 `翼德 playtest` 仍会用 `asr_sensevoice.py` 批量补转。
- 首条转写慢(载模型约 10 秒,窗口会显示「转写中…」);之后每条 1-3 秒。录音一开始服务就预热,通常你说完停录时已就绪。

> **更轻的跑法(可选)**:嫌 PyTorch 重,可用 **sherpa-onnx** 跑 SenseVoice 的 ONNX 版(免 PyTorch、有预编译包)。要走这条跟翼德说,它把 `asr_sensevoice.py` 换成 sherpa-onnx 版。
> ⚠️ 本地转写这步**尚未在勾哥机器端到端验证**;装好后第一次跑请确认能出中文稿(出不来翼德会如实报、自动降级,不假装)。

## 3. 隐私
- 录的是**你的麦克风**:**全程本地处理、录音不外传**(本地 SenseVoice,不上任何云)。
- 不想说话就**只打字**(标注窗口里有输入框)。产物都在项目 `QA/playtest/`,你能直接删。
- 建议把 `QA/playtest/` 加进 `.gitignore`(截图/录音是大文件,别进 git)。

## 4. 怎么用(配好之后)· F8 三段
1. 进 Playmode 玩,遇到问题按 **F8**(第①下)→ 冻帧 + 自动截图/抓上下文 + **开始录音**;「翼德 标注」窗口弹出(停在 Game 视图旁,不挡画面)。
2. 说出问题(中文)→ 说完按 **F8**(第②下)**停录** → 几秒后转写的中文**自动填进打字框**,你**看一眼对不对**,不对就直接改/补。(嫌吵不想说也行,直接在框里打字。)
3. 确认无误 → 再按 **F8**(第③下,或点绿钮)**保存**这条,解冻继续。`Esc` 随时取消当前条。
4. 测完回 Claude Code 说"**翼德 playtest**" → 翼德读截图 + 已确认的文字 → 出带定位的问题清单。

---

## 可选:整段屏幕录屏(老方案,默认不用)
若某场就想要"连续画面看手感",仓库里还留着 `playtest-rec.bat`(ffmpeg 录屏录麦)+ 旧的处理路径。**默认不启用**——冻帧标注已覆盖绝大多数反馈,录屏只在专看动效/手感时偶尔用,且转写同样建议走本地。

## 验证边界(诚实)
冻帧/截图/抓上下文是确定性的 Unity 调用;**本地 SenseVoice 转写、真机录音**这两环需你这边真环境验一次。翼德跑时如实报结果,不冒充。
