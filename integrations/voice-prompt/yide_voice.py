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
# 实时反馈（P0）：录音中用一个**置顶无边框小浮窗**边说边滚 interim 预览（生成式模型 interim 会
#   反复改写前文，放浮窗里抖动无所谓，绝不抖进输入框）；说完 final 才一次性键入输入框，输入框全程干净。
#   无 tkinter 时自动降级为控制台预览 + 原阻塞模式。
#
# 状态机：idle --热键--> recording（浮窗显示）--热键/静音自动停--> (done) --键入+关浮窗--> idle
#
# 依赖（都轻量、无 PyTorch）：
#   pip install pynput                         # 全局热键（不需管理员）
#   pip install google-cloud-speech sounddevice # STT（playtest 已装过就不用再装）
# 认证：复用 gcloud ADC（gcloud auth application-default login + set-quota-project），同 playtest。
#
# 配置（环境变量，都可不设）：
#   YIDE_STT_SCRIPT       stt_google.py 路径（默认：本文件 ../playtest-capture/stt_google.py）
#   YIDE_VOICE_PY         跑 stt_google.py 用的 python（默认：python）
#   YIDE_VOICE_HOTKEY     pynput 组合键（默认 <ctrl>+<f9>）；同一组合键按一下开、再按一下停
#   YIDE_VOICE_SUBMIT     设为 1 则键入后自动回车提交（默认 0：只键入不回车，留你审）
#   YIDE_VOICE_KEEP_WAV   设为 1 保留每段录音 wav（默认 0：键入后删掉，干净）
#   其余 STT 变量透传给 stt_google.py：YIDE_GCP_PROJECT / YIDE_GCP_LOCATION / YIDE_STT_LANG /
#                                     YIDE_STT_MODEL / YIDE_STT_SILENCE_SEC（语音喂 prompt 默认改短到 6s）
#
# 自检：python yide_voice.py --check      → 透传到 stt_google.py --check（验依赖/认证/麦克风/API）
#       python yide_voice.py --selftest   → 前台跑：逐环验证 STT + 浮窗 + 焦点 + 键入链路，打印红绿报告

import os
import sys
import json
import time
import queue
import tempfile
import threading
import subprocess

try:
    import tkinter as tk
except Exception:
    tk = None

HOTKEY = os.environ.get("YIDE_VOICE_HOTKEY", "<ctrl>+<f9>")
SUBMIT = os.environ.get("YIDE_VOICE_SUBMIT", "0") == "1"
KEEP_WAV = os.environ.get("YIDE_VOICE_KEEP_WAV", "0") == "1"
PYTHON = os.environ.get("YIDE_VOICE_PY", "python")
PROMPT = "🎙 请说话…"   # 录音中浮窗的初始提示


def _default_stt_script():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "playtest-capture", "stt_google.py"))


STT_SCRIPT = os.environ.get("YIDE_STT_SCRIPT", _default_stt_script())


def log(msg):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# 转写后处理：把常见同音误识别纠正成专名（Google 默认 recognizer 不支持 adaptation，
# 只能本地纠错；“翼德”常被 STT 听成同音字。需要更多词时往这里加，或反馈给上游）。
_TERM_FIXES = {
    "一得": "翼德", "一德": "翼德", "亦得": "翼德", "义德": "翼德",
    "易德": "翼德", "翼徳": "翼德", "壹得": "翼德", "益得": "翼德",
}


def fix_terms(text):
    for wrong, right in _TERM_FIXES.items():
        if wrong in text:
            text = text.replace(wrong, right)
    return text


# ── 把字符串用 Windows SendInput 以 Unicode 打进当前焦点窗口（CJK 直出，不依赖键盘布局）──
def type_unicode(text, backspaces=0):
    if not text and backspaces <= 0:
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

    # 键入前强制松开可能仍按着的修饰键：热键 Ctrl+Alt+V 收尾快时残留，会让 Unicode 被当快捷键吞掉
    for _mod in (0x11, 0x12, 0x10, 0x5B, 0x5C):  # Ctrl, Alt, Shift, LWin, RWin
        _send([_vk_event(_mod, keyup=True)])

    # 先退格删掉之前键入的占位（浮窗方案默认不用；保留参数向后兼容）
    VK_BACK = 0x08
    for _ in range(backspaces):
        _send([_vk_event(VK_BACK, keyup=False)])
        _send([_vk_event(VK_BACK, keyup=True)])

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


# ── 把焦点还给录音前的前台窗口（浮窗可能抢焦点，键入前必须恢复，否则 SendInput 打飞）──
def _restore_foreground(hwnd):
    if os.name != "nt" or not hwnd:
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        cur = u.GetForegroundWindow()
        if cur == hwnd:
            return
        t_cur = u.GetWindowThreadProcessId(cur, None)
        t_tgt = u.GetWindowThreadProcessId(hwnd, None)
        attached = False
        if t_cur and t_tgt and t_cur != t_tgt:
            attached = bool(u.AttachThreadInput(t_cur, t_tgt, True))
        u.SetForegroundWindow(hwnd)
        u.SetFocus(hwnd)
        if attached:
            u.AttachThreadInput(t_cur, t_tgt, False)
    except Exception:
        pass


# ── 置顶无边框小浮窗：线程安全（外部线程 put 命令，浮窗线程 mainloop 轮询执行）──
class Overlay:
    def __init__(self):
        self.q = queue.Queue()
        self.root = None
        self.label = None
        self._placed = False

    def start(self):
        # 浮窗跑在自己的线程，主线程留给 pynput（与早期能进输入框的版本一致）
        threading.Thread(target=self.run, daemon=True).start()

    # 在浮窗自己的线程调用：建窗 + 轮询 + 阻塞 mainloop
    def run(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)         # 无边框
        self.root.attributes("-topmost", True)   # 置顶
        try:
            self.root.attributes("-alpha", 0.93)
        except Exception:
            pass
        self.root.configure(bg="#14171c")
        self.label = tk.Label(
            self.root, text="", fg="#eaeaea", bg="#14171c",
            font=("Microsoft YaHei UI", 14), justify="left",
            wraplength=460, padx=18, pady=14, anchor="w",
        )
        self.label.pack(fill="both", expand=True)
        # Windows：让浮窗永不抢焦点，否则 SendInput 会把 final 打到浮窗而不是 Claude Code 输入框
        if os.name == "nt":
            try:
                import ctypes
                GWL_EXSTYLE = -20
                WS_EX_NOACTIVATE = 0x08000000
                WS_EX_TOOLWINDOW = 0x00000080
                GA_ROOT = 2
                u = ctypes.windll.user32
                self.root.update_idletasks()
                hwnd = u.GetAncestor(self.root.winfo_id(), GA_ROOT)
                ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
                u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
            except Exception:
                pass
        self.root.withdraw()                     # 初始隐藏
        self.root.after(30, self._poll)
        self.root.mainloop()

    def _poll(self):
        try:
            while True:
                cmd, arg = self.q.get_nowait()
                if cmd == "show":
                    self.label.config(text=arg or "")
                    self.root.deiconify()
                    self.root.update_idletasks()
                    self._place()
                elif cmd == "text":
                    self.label.config(text=arg)
                elif cmd == "hide":
                    self.root.withdraw()
                elif cmd == "quit":
                    self.root.destroy()
                    return
        except queue.Empty:
            pass
        self.root.after(30, self._poll)

    def _place(self):
        # 屏幕下方居中（固定一次锚点，避免 interim 变长时窗口乱跳）
        if self._placed:
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = 496
        x = (sw - w) // 2
        y = int(sh * 0.70)
        self.root.geometry("+%d+%d" % (x, y))
        self._placed = True

    # —— 线程安全外部接口 ——
    def show(self, text=""):
        self.q.put(("show", text))

    def set_text(self, text):
        self.q.put(("text", text))

    def hide(self):
        self.q.put(("hide", None))

    def quit(self):
        self.q.put(("quit", None))


class VoiceDaemon:
    def __init__(self):
        self.proc = None
        self.recording = False
        self.lock = threading.Lock()
        self.cur_wav = None
        self._last_interim = ""
        self.overlay = None     # 浮窗线程的 Overlay（无 tkinter 时为 None）
        self._target_hwnd = None  # 录音前的前台窗口（Claude Code 输入框），键入前恢复焦点

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
                    if self.overlay:
                        self.overlay.set_text("🎙  " + txt)
                    # 同一行刷新控制台预览（无浮窗时的兜底；静默后台看不到也无妨）
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
                if self.overlay:
                    self.overlay.hide()

    def _on_done(self, text, auto, wav):
        with self.lock:
            self.recording = False
        self._last_interim = ""
        if self.overlay:
            self.overlay.hide()
        sys.stdout.write("\r" + " " * 64 + "\r")
        sys.stdout.flush()
        text = fix_terms((text or "").strip())   # 专名同音纠错（翼德 等）
        if not text:
            log("（没听到内容，未键入）" + ("[静音自动停]" if auto else ""))
        else:
            log("✓ 键入：" + text + ("  [静音自动停]" if auto else ""))
            _restore_foreground(self._target_hwnd)   # 把焦点抢回 Claude Code 输入框
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
                if os.name == "nt":
                    try:
                        import ctypes
                        self._target_hwnd = ctypes.windll.user32.GetForegroundWindow()
                    except Exception:
                        self._target_hwnd = None
                try:
                    self.proc.stdin.write("START\t%s\n" % wav)
                    self.proc.stdin.flush()
                except Exception as e:
                    self.recording = False
                    log("⚠ 启动录音失败：%s" % e)
                    return
                log("● 录音中…（说中文；再按一次热键停，或停顿自动停）")
                if self.overlay:
                    self.overlay.show(PROMPT)          # 浮窗实时预览，转写完才键入输入框
            else:
                try:
                    self.proc.stdin.write("STOP\n")
                    self.proc.stdin.flush()
                except Exception:
                    pass
                # done 会从 _read_stt 回来；这里只置请求停
                log("… 收尾转写中")
                if self.overlay:
                    self.overlay.set_text("… 收尾转写中")

    def quit(self):
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.stdin.write("QUIT\n")
                self.proc.stdin.flush()
        except Exception:
            pass


def _selftest():
    # 在用户前台运行：逐环验证整条链并打印红绿报告（会弹一个测试输入框，自动键入后读回）。
    # 注意：必须前台运行才有 Windows 前台资格；后台/headless 跑键入环会失败，属正常。
    log("翼德语音 · 自检")
    log("—— 1) STT 依赖 / 认证 / API ——")
    if not os.path.exists(STT_SCRIPT):
        log("[STT] ✗ 找不到 stt_google.py：%s" % STT_SCRIPT)
        return
    rc = subprocess.call([PYTHON, STT_SCRIPT, "--check"])
    log("[STT] %s" % ("✓ 就绪" if rc == 0 else "✗ 见上方原因"))

    if os.name != "nt":
        log("（非 Windows，键入自检跳过）")
        return
    if tk is None:
        log("[浮窗] ✗ 无 tkinter，浮窗不可用")
        return

    log("—— 2) 浮窗 + 焦点恢复 + 键入链路（弹一个测试输入框，自动键入再读回）——")
    import ctypes
    from ctypes import wintypes
    u = ctypes.windll.user32
    u.CreateWindowExW.restype = wintypes.HWND
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                  wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    WS_OVERLAPPEDWINDOW = 0x00CF0000
    WS_VISIBLE = 0x10000000
    ES_MULTILINE = 0x0004
    ES_AUTOVSCROLL = 0x0040
    hwnd = u.CreateWindowExW(0, "EDIT", "翼德自检 · 测试输入框",
                             WS_OVERLAPPEDWINDOW | WS_VISIBLE | ES_MULTILINE | ES_AUTOVSCROLL,
                             200, 200, 660, 200, None, None, None, None)
    u.ShowWindow(hwnd, 5)
    u.SetForegroundWindow(hwnd)
    u.SetFocus(hwnd)

    overlay = Overlay()
    overlay.start()
    time.sleep(0.6)

    expect = "翼德 selftest 自动键入 PlayerController OK"
    res = {}

    def worker():
        time.sleep(0.6)
        overlay.show(PROMPT)
        time.sleep(0.6)
        overlay.set_text("🎙 自检键入…")
        time.sleep(0.4)
        overlay.hide()
        time.sleep(0.2)
        _restore_foreground(hwnd)
        time.sleep(0.25)
        u.SetWindowTextW(hwnd, "")
        type_unicode(expect)
        time.sleep(0.6)
        buf = ctypes.create_unicode_buffer(1024)
        u.GetWindowTextW(hwnd, buf, 1024)
        res["val"] = buf.value
        res["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    msg = wintypes.MSG()
    t0 = time.time()
    while time.time() - t0 < 8 and not res.get("done"):
        while u.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):  # PM_REMOVE
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.01)

    overlay.quit()
    got = (res.get("val") or "").strip()
    ok = got == expect
    log("[键入] %s" % ("✓ 成功打进输入框" if ok else "✗ 没进框 / 不完整"))
    log("       期望: %s" % expect)
    log("       实收: %r" % got)
    if not ok:
        log("       （前台运行仍失败=键入链路真有问题；后台跑失败=前台权限限制，正常）")
    time.sleep(1.2)
    u.DestroyWindow(hwnd)
    log("—— 自检完毕 ——")


def main():
    # 静默后台（VBS 隐藏窗口）时控制台 codepage 非 UTF-8，log 中文/emoji 会崩 —— 统一 UTF-8
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = [a for a in sys.argv[1:] if a]

    # 自检直接透传给 stt_google.py
    if args and args[0] in ("--check", "-check", "check"):
        if not os.path.exists(STT_SCRIPT):
            log("✗ 找不到 stt_google.py：%s" % STT_SCRIPT)
            sys.exit(2)
        sys.exit(subprocess.call([PYTHON, STT_SCRIPT, "--check"]))

    if args and args[0] in ("--selftest", "-selftest", "selftest"):
        _selftest()
        sys.stdout.flush()
        os._exit(0)   # 干净退出，避免浮窗线程 Tcl 清理在退出时报噪音

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

    if tk is not None:
        # 浮窗跑在自己的线程；主线程留给 pynput（与早期能进输入框的版本一致）
        overlay = Overlay()
        overlay.start()
        daemon.overlay = overlay
    else:
        log("⚠ 无 tkinter，浮窗不可用，回退控制台预览。")

    hk = keyboard.GlobalHotKeys({HOTKEY: daemon.toggle})
    try:
        with hk as h:
            h.join()
    except KeyboardInterrupt:
        pass
    finally:
        daemon.quit()
        if daemon.overlay:
            daemon.overlay.quit()
    log("\n再见。")


if __name__ == "__main__":
    main()
