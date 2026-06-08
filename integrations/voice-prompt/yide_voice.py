#!/usr/bin/env python3
# 翼德 · 语音喂 prompt（Windows 常驻守护进程）
# 用途：在 Rider/任意终端跑 Claude Code 时，不打字——按全局热键说一句话，
#       中文实时转写完后**自动键入当前光标处**（Claude Code 输入框），你审一眼再回车。
#
# 复用现成 STT：不重写识别逻辑，直接拉起 playtest 那套 stt_google.py 的“常驻流式服务”模式
#   （它打印一行 __READY__ 后从 stdin 收 START\t<wav> / STOP；stdout 逐行 JSON：interim/final/done）。
#
# 三件事它包了：① 全局热键开关录音；② 复用 stt_google.py 流式转写；③ done 后把最终中文用
#   SendInput(KEYEVENTF_UNICODE) 打进当前焦点窗口。**不自动回车**（默认），留你审稿。
#
# 状态机：idle --热键--> recording --热键/静音自动停--> (done) --键入--> idle
#
# 依赖（都轻量、无 PyTorch）：
#   pip install pynput                         # 全局热键（不需管理员）
#   pip install google-cloud-speech sounddevice # STT（playtest 已装过就不用再装）
# 认证：复用 gcloud ADC（gcloud auth application-default login + set-quota-project），同 playtest。
#
# 配置（环境变量，都可不设）：
#   YIDE_STT_SCRIPT       stt_google.py 路径（默认：本文件 ../playtest-capture/stt_google.py）
#   YIDE_VOICE_PY         跑 stt_google.py 用的 python（默认：python）
#   YIDE_VOICE_HOTKEY     pynput 组合键（默认 <ctrl>+<alt>+v）；同一组合键按一下开、再按一下停
#   YIDE_VOICE_SUBMIT     设为 1 则键入后自动回车提交（默认 0：只键入不回车，留你审）
#   YIDE_VOICE_KEEP_WAV   设为 1 保留每段录音 wav（默认 0：键入后删掉，干净）
#   其余 STT 变量透传给 stt_google.py：YIDE_GCP_PROJECT / YIDE_GCP_LOCATION / YIDE_STT_LANG /
#                                     YIDE_STT_MODEL / YIDE_STT_SILENCE_SEC（语音喂 prompt 默认改短到 6s）
#
# 自检：python yide_voice.py --check   → 透传到 stt_google.py --check（验依赖/认证/麦克风/API）

import os
import sys
import json
import time
import tempfile
import threading
import subprocess

HOTKEY = os.environ.get("YIDE_VOICE_HOTKEY", "<ctrl>+<alt>+v")
SUBMIT = os.environ.get("YIDE_VOICE_SUBMIT", "0") == "1"
KEEP_WAV = os.environ.get("YIDE_VOICE_KEEP_WAV", "0") == "1"
PYTHON = os.environ.get("YIDE_VOICE_PY", "python")


def _default_stt_script():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "playtest-capture", "stt_google.py"))


STT_SCRIPT = os.environ.get("YIDE_STT_SCRIPT", _default_stt_script())


def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# ── 把字符串用 Windows SendInput 以 Unicode 打进当前焦点窗口（CJK 直出，不依赖键盘布局）──
def type_unicode(text):
    if not text:
        return
    if os.name != "nt":
        # 非 Windows 兜底：打印出来，让你手动复制（本工具按需求面向 Windows）
        log("（非 Windows，无法自动键入）转写结果：" + text)
        return
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    INPUT_KEYBOARD = 1
    KEYEVENTF_UNICODE = 0x0004
    KEYEVENTF_KEYUP = 0x0002
    VK_RETURN = 0x0D

    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD),
                    ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class _INPUTunion(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTunion)]

    def _send(events):
        n = len(events)
        arr = (INPUT * n)(*events)
        user32.SendInput(n, arr, ctypes.sizeof(INPUT))

    def _unicode_event(code_unit, keyup=False):
        flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if keyup else 0)
        ki = KEYBDINPUT(0, code_unit, flags, 0, 0)
        return INPUT(INPUT_KEYBOARD, _INPUTunion(ki=ki))

    def _vk_event(vk, keyup=False):
        flags = KEYEVENTF_KEYUP if keyup else 0
        ki = KEYBDINPUT(vk, 0, flags, 0, 0)
        return INPUT(INPUT_KEYBOARD, _INPUTunion(ki=ki))

    # 用 UTF-16 码元逐个发（含中文 BMP；emoji 等代理对也按码元发，down+up）
    units = []
    for ch in text:
        b = ch.encode("utf-16-le")
        for i in range(0, len(b), 2):
            units.append(b[i] | (b[i + 1] << 8))
    for cu in units:
        _send([_unicode_event(cu, keyup=False)])
        _send([_unicode_event(cu, keyup=True)])

    if SUBMIT:
        time.sleep(0.05)
        _send([_vk_event(VK_RETURN, keyup=False)])
        _send([_vk_event(VK_RETURN, keyup=True)])


class VoiceDaemon:
    def __init__(self):
        self.proc = None
        self.recording = False
        self.lock = threading.Lock()
        self.cur_wav = None
        self._last_interim = ""

    # —— 启动 stt_google.py 常驻服务，等到 __READY__ ——
    def start_stt(self):
        if not os.path.exists(STT_SCRIPT):
            log("✗ 找不到 stt_google.py：%s\n  设 YIDE_STT_SCRIPT 指向它。" % STT_SCRIPT)
            return False

        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        # 语音喂 prompt：说完停顿就该收尾，静音自动停默认改短（playtest 默认 30s 太长）
        env.setdefault("YIDE_STT_SILENCE_SEC", "6")

        try:
            self.proc = subprocess.Popen(
                [PYTHON, STT_SCRIPT],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=env, text=True, encoding="utf-8", bufsize=1,
            )
        except Exception as e:
            log("✗ 起 stt_google.py 失败：%s" % e)
            return False

        # 等 __READY__（起不来时它会先往 stderr 打原因再退出）
        ready = False
        for _ in range(120):  # 最多等 ~60s（首次连 GCP 可能慢）
            line = self.proc.stdout.readline()
            if line == "" and self.proc.poll() is not None:
                break
            if line.strip() == "__READY__":
                ready = True
                break
        if not ready:
            err = ""
            try:
                err = self.proc.stderr.read() or ""
            except Exception:
                pass
            log("✗ STT 没就绪。先跑：python yide_voice.py --check\n" + err.strip())
            return False

        threading.Thread(target=self._read_stt, daemon=True).start()
        return True

    # —— 持续读 stt_google.py 的 stdout JSON ——
    def _read_stt(self):
        while True:
            line = self.proc.stdout.readline()
            if line == "" and self.proc.poll() is not None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except Exception:
                continue
            t = msg.get("type")
            if t == "interim":
                txt = msg.get("text", "")
                if txt and txt != self._last_interim:
                    self._last_interim = txt
                    # 同一行刷新预览（不抢焦点，仅本进程控制台）
                    sys.stdout.write("\r🎙  " + txt[-60:].ljust(62))
                    sys.stdout.flush()
            elif t == "final":
                pass  # 等 done 拿整段
            elif t == "done":
                self._on_done(msg.get("text", ""), msg.get("auto", False), msg.get("wav"))
            elif t == "error":
                log("\n⚠ STT 出错：%s（这次没转成，可直接打字）" % msg.get("error"))
                with self.lock:
                    self.recording = False

    def _on_done(self, text, auto, wav):
        with self.lock:
            self.recording = False
        self._last_interim = ""
        sys.stdout.write("\r" + " " * 64 + "\r")
        sys.stdout.flush()
        text = (text or "").strip()
        if not text:
            log("（没听到内容，未键入）" + ("[静音自动停]" if auto else ""))
        else:
            log("✓ 键入：" + text + ("  [静音自动停]" if auto else ""))
            time.sleep(0.18)  # 给焦点一点时间，确保打进 Claude Code 输入框
            type_unicode(text)
        if wav and not KEEP_WAV:
            try:
                os.remove(wav)
            except Exception:
                pass

    # —— 热键回调：toggle ——
    def toggle(self):
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                log("⚠ STT 服务已退出，重启中…")
                if not self.start_stt():
                    return
            if not self.recording:
                wav = os.path.join(tempfile.gettempdir(), "yide-voice",
                                   "voice-%d.wav" % int(time.time() * 1000))
                self.cur_wav = wav
                self.recording = True
                try:
                    self.proc.stdin.write("START\t%s\n" % wav)
                    self.proc.stdin.flush()
                except Exception as e:
                    self.recording = False
                    log("⚠ 启动录音失败：%s" % e)
                    return
                log("● 录音中…（说中文；再按一次热键停，或停顿自动停）")
            else:
                try:
                    self.proc.stdin.write("STOP\n")
                    self.proc.stdin.flush()
                except Exception:
                    pass
                # done 会从 _read_stt 回来；这里只置请求停
                log("… 收尾转写中")

    def quit(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
        except Exception:
            pass


def main():
    args = [a for a in sys.argv[1:] if a]

    # 自检直接透传给 stt_google.py
    if args and args[0] in ("--check", "-check", "check"):
        if not os.path.exists(STT_SCRIPT):
            log("✗ 找不到 stt_google.py：%s" % STT_SCRIPT)
            sys.exit(2)
        sys.exit(subprocess.call([PYTHON, STT_SCRIPT, "--check"]))

    if os.name != "nt":
        log("⚠ 自动键入只在 Windows 上支持（目标系统）。当前非 Windows，仅可 --check / 看转写。")

    try:
        from pynput import keyboard
    except Exception:
        log("✗ 缺 pynput：pip install pynput")
        sys.exit(2)

    daemon = VoiceDaemon()
    log("翼德语音 · 启动 STT 服务中…")
    if not daemon.start_stt():
        sys.exit(3)

    log("✓ 就绪。热键：%s（按一下开始说，再按停；停顿 %ss 也会自动停）"
        % (HOTKEY, os.environ.get("YIDE_STT_SILENCE_SEC", "6")))
    log("  键入后%s自动回车。Ctrl+C 退出。"
        % ("会" if SUBMIT else "不会（默认留你审稿，自己回车）"))

    def on_toggle():
        daemon.toggle()

    try:
        with keyboard.GlobalHotKeys({HOTKEY: on_toggle}) as h:
            h.join()
    except KeyboardInterrupt:
        pass
    finally:
        daemon.quit()
        log("\n再见。")


if __name__ == "__main__":
    main()
