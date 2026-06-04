# Playtest 冻帧标注 · 实时语音转写配置(Google Cloud STT)

**目的**:试玩时按一个键(默认 **F8**)冻帧、说出/打出问题,翼德自动把这些变成"哪里要改 + 在哪个脚本/Prefab"的清单。
**铁律**:你只做 4 件——按 F8、测、说反馈(或打字)、再按 F8 存。其余翼德全自动。

> 语音走 **Google Cloud Speech-to-Text(Chirp 3 · v2 流式)**:Python 直接持麦,**边说边出字**(interim),停录出最终稿。比批量"停录再转"实时得多。

---

## 1. 放入标注工具(3 个文件)
1. `PlaytestMarker.cs` → 放进项目任意 `Scripts` 目录(运行时:冻帧/截图/抓上下文,不再自己录音)。
2. `PlaytestMarkerWindow.cs` → 放进任意 **`Editor/`** 文件夹(编辑器窗口 + 轮询驱动)。
3. `PlaytestAsrServer.cs` → 放进任意 **`Editor/`** 文件夹(拉起 `stt_google.py`、收发实时转写)。

进 Play 模式它会**自动生成**(不用手挂物体);三个文件都用 `#if UNITY_EDITOR || DEVELOPMENT_BUILD` / `#if UNITY_EDITOR` 包住,**不会进正式上线包**。
- 想换标注键:场景里 `~YidePlaytestMarker` 物体上改 `Mark Key`(默认 F8;别用空格,常被游戏占用)。

## 2. 装 Python 依赖(轻量,无 PyTorch)
```
pip install google-cloud-speech sounddevice
```
- `google-cloud-speech`:调 GCP 流式识别。
- `sounddevice`:Python 持麦(自带 PortAudio,Windows 直接装,无需编译)。

## 3. Google Cloud 认证(二选一)

### 方式 A:gcloud ADC(推荐 —— 无密钥文件、最安全)
1. 装 Google Cloud CLI(gcloud),装完重开终端验证 `gcloud --version`。
2. 登录并设配额项目(`<项目ID>` 换成你的 GCP 项目):
   ```
   gcloud auth application-default login
   gcloud auth application-default set-quota-project <项目ID>
   ```
3. 确保该项目已 **启用 Speech-to-Text API** 且开了 **billing**。
4. Unity「⚙ 转写设置」里 **服务账号 JSON 留空** 即可(脚本自动用 ADC)。

### 方式 B:service account JSON 密钥
1. 在 GCP 控制台建 service account、给 *Speech-to-Text User* 角色、下载 JSON 密钥。
2. Unity「⚙ 转写设置」里把 **服务账号 JSON** 指向该文件(或设环境变量 `GOOGLE_APPLICATION_CREDENTIALS`)。

> 自检:配好后先跑一遍,确认依赖/认证/麦克风都 OK 再进 Unity:
> ```
> python stt_google.py --check
> ```

## 4. Unity 一次性配置(EditorPrefs 永久记住)
窗口底部展开「⚙ 转写设置」:
- **Python**:`python`(或具体的 `python.exe` 路径 / venv)。
- **stt_google.py**:指向本文件同目录的 `stt_google.py`。
- **服务账号 JSON**:方式 A 留空;方式 B 填密钥路径。
- **区域 (us/eu)**:默认 `us`;海外可填 `eu` 延迟更低。chirp_3 中文流式在 us / eu 多区均 GA。

## 5. 怎么用(配好之后)
1. 进 Playmode 玩,遇到问题按 **F8** → 冻帧 + 自动截图/抓上下文 + 开始实时听写;「翼德 标注」窗口弹出(停在 Game 视图旁,不挡画面)。
2. 说出问题(中文)→ 文字**边说边滚进打字框**;说完按 **F8**(或点「停录」)出最终稿、解冻。`Esc` 取消当前条。需要时可直接改字。
3. 测完回 Claude Code 说"**翼德 playtest**" → 翼德读截图/上下文 + 已转写文字 → 出带定位的问题清单。

## 6. 隐私
- 录的是**你的麦克风**;音频流到 Google Cloud 转写(走 GCP,受你项目的数据条款约束)。不想说话就**只打字**。
- 产物都在项目 `QA/playtest/`,可直接删。建议把 `QA/playtest/` 加进 `.gitignore`(截图/录音是大文件,别进 git)。

## 7. 可选环境变量(一般不用动)
- `YIDE_GCP_PROJECT`:覆盖项目 ID(默认从凭证/ADC 读)。
- `YIDE_GCP_LOCATION`:区域(默认 `us`)。
- `YIDE_STT_LANG`:语言(默认 `cmn-Hans-CN` 普通话)。
- `YIDE_STT_MODEL`:模型(默认 `chirp_3`)。
- `YIDE_STT_SILENCE_SEC`:静音多少秒自动停转写省 API(默认 `30`)。说完不按 F8 也会在静音 30 秒后自动停、自动归到复核态。

## 8. 故障排查
- 窗口状态显示「转写不可用 / Failed」:看后面的原因。
  - `未配置 stt_google.py 路径` → 在「⚙ 转写设置」指向脚本。
  - `拿不到 GCP project_id` → 跑方式 A 的两条 gcloud 命令(尤其 `set-quota-project`)。
  - `sounddevice 未安装` → `pip install sounddevice`。
  - `CANCELLED / 区域不支持` → 确认区域是 `us` 或 `eu`(不要用 `us-central1` 这类单区域 + chirp_2,中文流式有已知 CANCELLED 问题)。
- 不出字但能打字:照常打字保存,事后 `python stt_google.py <voice.wav>` 批量补转。

## 验证边界(诚实)
冻帧/截图/抓上下文是确定性的 Unity 调用;**麦克风、Google 流式转写**这两环需你这边真环境验一次(尤其 gcloud 登录 + 第一次出中文字)。翼德跑时如实报结果,不冒充。
