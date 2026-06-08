# 翼德语音喂 prompt · 配置（Windows · 全局热键 + 自动键入）

**目的**：在 Rider 终端跑 Claude Code/翼德时，不打字——按一个全局热键说中文，转写完**自动键入当前光标处**（Claude Code 输入框），你审一眼再回车。
**铁律**：常驻一个后台进程；你只做两件——按热键说话、再按热键停（或停顿自动停）。其余翼德全自动。

> 语音复用 playtest 那套 **Google Cloud Speech-to-Text（Chirp 3 · v2 流式）**：`integrations/playtest-capture/stt_google.py`。这里不重写识别，只是把它从“喂 Unity”改成“喂终端光标”。

---

## 1. 装依赖（轻量，无 PyTorch）
```
pip install pynput google-cloud-speech sounddevice
```
- `pynput`：全局热键 + 监听（**不需要管理员**）。
- `google-cloud-speech` + `sounddevice`：STT（playtest 已装过就跳过）。
- 自动键入用的是 Windows 自带 `SendInput`，**无需额外库**。

## 2. Google Cloud 认证（和 playtest 同一套，配过就不用再配）
推荐 gcloud ADC（无密钥文件）：
```
gcloud auth application-default login
gcloud auth application-default set-quota-project <你的GCP项目ID>
```
确保该项目已**开 billing** 且**启用 Speech-to-Text API**（`gcloud services enable speech.googleapis.com`）。
或用 service account JSON：设环境变量 `GOOGLE_APPLICATION_CREDENTIALS` 指向密钥文件。

## 3. 先自检（验依赖/认证/麦克风/API，别留到用时才炸）
```
python integrations\voice-prompt\yide_voice.py --check
```
打印一串 ✓ 且最后 `API 可达` 即就绪；有 ✗ 按提示修。

## 4. 启动常驻热键
双击 `integrations\voice-prompt\yide-voice.bat`，或终端跑：
```
python integrations\voice-prompt\yide_voice.py
```
看到 `✓ 就绪。热键：<ctrl>+<f9> …` 即可。**让这个窗口一直开着**（最小化即可）。

## 5. 怎么用
1. 光标停在 **Claude Code 的输入框**（Rider 终端里）。
2. 按 **Ctrl+F9** → 控制台显示「● 录音中…」→ 说中文（窗口里边说边滚预览）。
3. 再按 **Ctrl+F9** 停（或停顿 ~6 秒自动停）→ 转写的中文**自动打进输入框**。
4. **自己审一眼、按回车**提交（默认不自动回车）。

## 6. 配置（环境变量，都可不设）
| 变量 | 默认 | 作用 |
|---|---|---|
| `YIDE_VOICE_HOTKEY` | `<ctrl>+<f9>` | 全局热键（pynput 写法，如 `<ctrl>+<alt>+v` / `<f10>`）。同键开/停。在 .bat 里改要把 `<` `>` 转义成 `^<` `^>`；设系统环境变量则原样写。 |
| `YIDE_VOICE_SUBMIT` | `0` | 设 `1` 则键入后自动回车提交；默认 0 留你审稿。 |
| `YIDE_VOICE_PY` | `python` | 跑 STT 用的 python（venv 填 venv 里的 python.exe）。 |
| `YIDE_STT_SILENCE_SEC` | `6` | 停顿几秒自动停（语音喂 prompt 默认比 playtest 短）。 |
| `YIDE_VOICE_KEEP_WAV` | `0` | 设 `1` 保留每段录音 wav；默认键入后删掉。 |
| `YIDE_STT_SCRIPT` | `../playtest-capture/stt_google.py` | stt_google.py 路径（移动了再设）。 |
| `YIDE_GCP_LOCATION` / `YIDE_STT_LANG` / `YIDE_STT_MODEL` | `us` / `cmn-Hans-CN` / `chirp_3` | 透传给 stt_google.py。 |

## 7. 开机自启（可选）
按 `Win+R` 输 `shell:startup` 回车 → 把 `yide-voice.bat` 的**快捷方式**拖进去。下次开机自动常驻。
（想静默后台、不弹黑窗，可改用 `pythonw` + 计划任务；先用 .bat 跑顺了再说。）

## 8. 隐私
录的是你的麦克风，音频流到 Google Cloud 转写（走你 GCP 项目的数据条款）；不想说话就照常打字。录音 wav 默认键入后即删。

## 9. 降级（诚实，别硬编）
- **STT 起不来 / 认证缺失**：启动时直接报原因并退出，先跑 `--check` 修；这期间照常打字。
- **没听到内容 / 转写失败**：不键入，控制台提示，你直接打字。
- **热键被别的软件占了**：换 `YIDE_VOICE_HOTKEY`。
- **键入的是别处不是 Claude Code**：键入打的是**当前焦点窗口**——停顿那一下别切走焦点。

## 10. 验证边界（诚实，未替你跑过）
确定性部分（拉起子进程、解析 JSON、SendInput 调用）是代码逻辑；但 **① 全局热键在你机器上能捕获、② 麦克风、③ Google 流式出中文、④ SendInput 把中文打进 Rider 终端的 Claude Code 输入框** 这四环必须在你真 Windows + 真环境端到端验一次。尤其第 ④ 环：个别终端/输入法对 Unicode 注入处理不同，第一次务必亲测一句。翼德没在你机器上跑过，不冒充已验证。
