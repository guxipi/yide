# 翼德 · 语音喂 prompt（voice）

解决:在 Rider 终端跑 Claude Code/翼德时懒得打字。**按全局热键说中文 → 实时转写 → 自动键入当前光标处(Claude Code 输入框)**,你审一眼再回车。

> 复用 playtest 那套 Google Cloud STT(Chirp 3 流式,`integrations/playtest-capture/stt_google.py`),只是把出口从"喂 Unity"改成"喂终端光标"。**面向 Windows**(自动键入用 SendInput)。

## 这个动作干什么
用户说"翼德 语音 / voice / 听写 / 口述"时:不是翼德自己录音,而是**引导/启动那个常驻热键守护进程**,并按需自检。翼德要做的:

1. **首次没配**:照 `integrations/voice-prompt/SETUP.md` 引导(装 `pynput google-cloud-speech sounddevice` + gcloud ADC 认证),别假装能用。先让用户跑自检:
   ```
   python integrations\voice-prompt\yide_voice.py --check
   ```
2. **启动常驻**(让用户自己在终端跑或双击 .bat,翼德不替他常驻):
   ```
   python integrations\voice-prompt\yide_voice.py
   ```
   或双击 `integrations\voice-prompt\yide-voice.bat`。
3. **用法**一句话讲清:光标停在 Claude Code 输入框 → 按 **Ctrl+Alt+V** 说中文 → 再按一次停(或停顿 ~6s 自动停)→ 中文自动键入 → 自己回车。

## 规则
- **不冒充已验证**:全局热键捕获 / 麦克风 / Google 出中文 / SendInput 打进 Claude Code 这四环要用户真 Windows 端到端验一次(见 SETUP「验证边界」)。翼德报的是"代码就绪",不是"已在你机器上跑通"。
- **降级诚实**:STT 起不来就报原因、照常打字,别硬编。
- 热键被占 → 改 `YIDE_VOICE_HOTKEY`;想键入后自动回车 → `YIDE_VOICE_SUBMIT=1`。
- 这是终端工具,**不进项目证据,不进 ~/.yide 大脑**;算插件能力的一部分。
