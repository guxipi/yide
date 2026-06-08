#!/usr/bin/env python3
# 翼德 · Google Cloud Speech-to-Text(Chirp 3 · v2)实时流式转写。海外可用、普通话准、带标点。
# 设计:Python 直接持麦 + StreamingRecognize 边说边出字(interim)。Unity 只发开/停指令、实时显示。
#
# 三种模式:
#   · 常驻流式服务(Unity 标注用,默认):无参启动 → 打印一行 __READY__ → 从 stdin 收指令:
#       START\t<voice.wav 绝对路径>   开始持麦 + 流式转写,把整段音频同时存成该 wav
#       STOP                          停录、收尾,落 wav
#     stdout 逐行 JSON:
#       {"type":"interim","text":"…运行中的全文…"}   边说边更新(含已定稿+当前未定稿)
#       {"type":"final","text":"…已定稿全文…"}        一个语音段定稿
#       {"type":"done","wav":"…","text":"…最终全文…"} STOP 后、wav 已写好
#       {"type":"error","error":"…"}                  出错(Unity 照常可打字)
#   · 批量(scripts/playtest.js 用):python stt_google.py a/voice.wav b/voice.wav …
#       每条一行 {"wav":"…","text":"…"} 到 stdout,转完退出。
#   · 自检:python stt_google.py --check  → 验证依赖/认证/project 是否就绪,给出可读结论。
#
# 认证(任一即可,库自动找):① gcloud ADC —— 先 `gcloud auth application-default login`(推荐,无密钥文件);
#   ② service account JSON —— 环境变量 GOOGLE_APPLICATION_CREDENTIALS 指向它。
# 可选环境变量:YIDE_GCP_PROJECT(默认从凭证/ADC 读)· YIDE_GCP_LOCATION(默认 us;chirp_3 支持 us/eu 多区)
#              · YIDE_STT_LANG(默认 cmn-Hans-CN)· YIDE_STT_MODEL(默认 chirp_3)
# 装法:pip install google-cloud-speech sounddevice(都轻量、无 PyTorch)。详见 SETUP.md。
import os, sys, json, wave, queue, threading, time

SAMPLE_RATE = 16000          # chirp 流式用 16k 单声道 LINEAR16
CHANNELS = 1
BLOCK = 800                  # 每帧 50ms:更小的帧 → 音频更快送达 → interim 更快(降延迟)
SILENCE_SEC = float(os.environ.get("YIDE_STT_SILENCE_SEC", "30") or 30)  # 多少秒听不到语音就自动停(省 API)


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def fatal(msg, code):
    sys.stderr.write(json.dumps({"error": msg}, ensure_ascii=False) + "\n")
    sys.stderr.flush()
    sys.exit(code)


def _gcloud_config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA", "")
        return os.path.join(base, "gcloud") if base else None
    return os.path.join(os.path.expanduser("~"), ".config", "gcloud")


def _adc_well_known_path():
    d = _gcloud_config_dir()
    return os.path.join(d, "application_default_credentials.json") if d else None


def _gcloud_active_project():
    d = _gcloud_config_dir()
    if not d:
        return None
    cfg = os.path.join(d, "configurations", "config_default")
    if not os.path.exists(cfg):
        return None
    try:
        import configparser
        cp = configparser.ConfigParser()
        cp.read(cfg, encoding="utf-8")
        if cp.has_option("core", "project"):
            return cp.get("core", "project") or None
    except Exception:
        pass
    return None


def resolve_project():
    # 1) 显式环境变量优先
    for k in ("YIDE_GCP_PROJECT", "GOOGLE_CLOUD_PROJECT", "GCLOUD_PROJECT"):
        v = os.environ.get(k)
        if v:
            return v
    # 2) service account JSON 的 project_id
    cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred and os.path.exists(cred):
        try:
            with open(cred, "r", encoding="utf-8") as f:
                data = json.load(f)
            p = data.get("project_id") or data.get("quota_project_id")
            if p:
                return p
        except Exception:
            pass
    # 3) google.auth 默认解析(service account 能拿到 project)
    try:
        import google.auth
        _, project = google.auth.default()
        if project:
            return project
    except Exception:
        pass
    # 4) 用户 ADC:default() 通常不返回 project —— 直接读 ADC 文件的 quota_project_id
    adc = _adc_well_known_path()
    if adc and os.path.exists(adc):
        try:
            with open(adc, "r", encoding="utf-8") as f:
                p = json.load(f).get("quota_project_id")
            if p:
                return p
        except Exception:
            pass
    # 5) 退到 gcloud 活动配置的 core/project
    return _gcloud_active_project()


def build_clients_and_config():
    """返回 (client, recognizer 路径, RecognitionConfig)。失败抛异常带可读信息。"""
    from google.cloud.speech_v2 import SpeechClient
    from google.cloud.speech_v2.types import cloud_speech
    from google.api_core.client_options import ClientOptions

    project = resolve_project()
    if not project:
        raise RuntimeError(
            "拿不到 GCP project_id —— 先跑 `gcloud auth application-default login` "
            "再 `gcloud auth application-default set-quota-project <项目ID>`;或设环境变量 YIDE_GCP_PROJECT。")

    location = (os.environ.get("YIDE_GCP_LOCATION", "us").strip() or "us")   # us / eu 多区
    lang = os.environ.get("YIDE_STT_LANG", "cmn-Hans-CN")
    model = os.environ.get("YIDE_STT_MODEL", "chirp_3")

    # 非 global 区域要把 endpoint 切到 {区域}-speech.googleapis.com
    client = SpeechClient(client_options=ClientOptions(api_endpoint=location + "-speech.googleapis.com"))
    recognizer = "projects/%s/locations/%s/recognizers/_" % (project, location)

    # 麦克风是裸 PCM,用显式解码(LINEAR16/16k/单声道),不用 AutoDetect(那是给带头的文件用的)
    config = cloud_speech.RecognitionConfig(
        explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
            encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=SAMPLE_RATE,
            audio_channel_count=CHANNELS,
        ),
        # 逗号分隔多语言码(如 cmn-Hans-CN,en-US)做中英 code-switching;单值则纯单语
        language_codes=[c.strip() for c in lang.split(",") if c.strip()],
        model=model,
        features=cloud_speech.RecognitionFeatures(enable_automatic_punctuation=True),
    )
    return client, recognizer, config, cloud_speech


def write_wav(path, pcm_bytes):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except Exception:
        pass
    with wave.open(path, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)          # 16-bit
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm_bytes)


# ── 一次流式会话:持麦 → 流式识别 → 落 wav ──
class StreamSession:
    def __init__(self, client, recognizer, config, cloud_speech, wav_path):
        self.client = client
        self.recognizer = recognizer
        self.config = config
        self.cs = cloud_speech
        self.wav_path = wav_path
        self.audio_q = queue.Queue()
        self.stop_flag = threading.Event()
        self.captured = bytearray()
        self.last_activity = 0.0       # 上次"听到语音"(收到非空转写)的时刻
        self.auto_stopped = False      # 是否因静音自动停的
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.stop_flag.set()

    def _requests(self):
        # 第一条:recognizer + streaming_config;之后每条:一块音频
        streaming_config = self.cs.StreamingRecognitionConfig(
            config=self.config,
            streaming_features=self.cs.StreamingRecognitionFeatures(
                interim_results=True,
                # P1：说完尽快出 final（砍掉 endpointing 收尾等待）；SUPERSHORT 最激进
                endpointing_sensitivity=self.cs.StreamingRecognitionFeatures.EndpointingSensitivity.ENDPOINTING_SENSITIVITY_SUPERSHORT,
            ),
        )
        yield self.cs.StreamingRecognizeRequest(recognizer=self.recognizer, streaming_config=streaming_config)
        while True:
            if self.stop_flag.is_set():
                break
            # 静音自动停:SILENCE_SEC 秒内没"听到语音"(无非空转写)→ 关流省 API。
            # 注意:麦克风一直在往队列灌音频,队列几乎从不空,所以这判断必须放每轮开头,不能塞在 queue.Empty 分支里。
            if self.last_activity and (time.monotonic() - self.last_activity) > SILENCE_SEC:
                self.auto_stopped = True
                self.stop_flag.set()
                break
            try:
                chunk = self.audio_q.get(timeout=0.1)
            except queue.Empty:
                continue
            if chunk is None:
                break
            yield self.cs.StreamingRecognizeRequest(audio=chunk)

    def _run(self):
        try:
            import sounddevice as sd
        except Exception as e:
            emit({"type": "error", "error": "sounddevice 未安装: %s(pip install sounddevice)" % e})
            return

        def callback(indata, frames, time_info, status):
            b = bytes(indata)
            self.captured.extend(b)
            self.audio_q.put(b)

        final_text = ""
        self.last_activity = time.monotonic()   # 起算:开流即开始计静音
        try:
            with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=CHANNELS,
                                   dtype="int16", blocksize=BLOCK, callback=callback):
                responses = self.client.streaming_recognize(requests=self._requests())
                for response in responses:
                    for result in response.results:
                        if not result.alternatives:
                            continue
                        piece = result.alternatives[0].transcript
                        if piece.strip():
                            self.last_activity = time.monotonic()   # 听到语音 → 重置静音计时
                        if result.is_final:
                            final_text += piece
                            emit({"type": "final", "text": final_text})
                        else:
                            emit({"type": "interim", "text": final_text + piece})
        except Exception as e:
            emit({"type": "error", "error": str(e)})

        # 落 wav(把这段录音存下来,供归档/事后复转)
        try:
            wav = self.wav_path if self.captured else None
            if self.captured:
                write_wav(self.wav_path, bytes(self.captured))
            emit({"type": "done", "wav": wav, "text": final_text.strip(), "auto": self.auto_stopped})
        except Exception as e:
            emit({"type": "error", "error": "写 wav 失败: %s" % e})


def server_loop():
    try:
        client, recognizer, config, cloud_speech = build_clients_and_config()
    except Exception as e:
        # 起不来也要让 Unity 看到原因;打 __READY__ 前先报错并退出
        fatal(str(e), 5)

    sys.stdout.write("__READY__\n")
    sys.stdout.flush()

    session = None
    # 用 readline() 而非 `for line in sys.stdin`:后者带预读缓冲,管道下不会实时交出单行,
    # 会导致 Unity 发来的 START/STOP 收不到、永不触发转写。readline() 是行缓冲,来一行处理一行。
    while True:
        line = sys.stdin.readline()
        if not line:          # EOF:stdin 关闭
            break
        line = line.rstrip("\n").rstrip("\r")
        if not line:
            continue
        parts = line.split("\t", 1)
        cmd = parts[0].strip().upper()
        if cmd == "START":
            wav = (parts[1].strip().strip('"') if len(parts) > 1 else "")
            if not wav:
                emit({"type": "error", "error": "START 缺 wav 路径"})
                continue
            if session is not None:
                session.stop()
            session = StreamSession(client, recognizer, config, cloud_speech, wav)
            session.start()
        elif cmd == "STOP":
            if session is not None:
                session.stop()
                session = None
        elif cmd == "QUIT":
            if session is not None:
                session.stop()
            break


def batch(wavs):
    """批量:对已有 wav 文件跑同步 recognize(scripts/playtest.js 用)。"""
    try:
        client, recognizer, config, cloud_speech = build_clients_and_config()
    except Exception as e:
        fatal(str(e), 5)
    # 文件带 wav 头,用自动解码更稳
    config.explicit_decoding_config = None
    config.auto_decoding_config = cloud_speech.AutoDetectDecodingConfig()
    for wav in wavs:
        try:
            with open(wav, "rb") as f:
                content = f.read()
            req = cloud_speech.RecognizeRequest(recognizer=recognizer, config=config, content=content)
            resp = client.recognize(request=req)
            text = "".join(r.alternatives[0].transcript for r in resp.results if r.alternatives).strip()
            emit({"wav": wav, "text": text})
        except Exception as e:
            emit({"wav": wav, "text": "", "error": str(e)})


def check():
    """自检:依赖 + 认证 + project 是否就绪。给 Unity 之外先验一遍。"""
    try:
        import google.cloud.speech_v2  # noqa
        import sounddevice as sd       # noqa
    except Exception as e:
        print("✗ 依赖缺失:%s\n  装:pip install google-cloud-speech sounddevice" % e)
        return 1
    project = resolve_project()
    if not project:
        print("✗ 拿不到 GCP project。先:\n"
              "  gcloud auth application-default login\n"
              "  gcloud auth application-default set-quota-project <你的项目ID>")
        return 1
    try:
        client, recognizer, config, _ = build_clients_and_config()
    except Exception as e:
        print("✗ 客户端/认证初始化失败:%s" % e)
        return 1
    try:
        import sounddevice as sd
        ins = [d for d in sd.query_devices() if d.get("max_input_channels", 0) > 0]
        mic = ins[0]["name"] if ins else "(未检测到输入设备!)"
    except Exception as e:
        mic = "(查询麦克风失败:%s)" % e
    loc = os.environ.get("YIDE_GCP_LOCATION", "us")
    model = os.environ.get("YIDE_STT_MODEL", "chirp_3")
    lang = os.environ.get("YIDE_STT_LANG", "cmn-Hans-CN")
    print("✓ 依赖就绪(google-cloud-speech + sounddevice)")
    print("✓ project = %s" % project)
    print("✓ 区域 = %s · 模型 = %s · 语言 = %s" % (loc, model, lang))
    print("✓ recognizer = %s" % recognizer)
    print("✓ 麦克风 = %s" % mic)

    # 真实 API 可达探测:当场暴露 billing 没开 / Speech API 没启用 / 权限不足,别留到 Unity 里才炸
    try:
        list(client.list_recognizers(parent="projects/%s/locations/%s" % (project, loc)))
        print("✓ API 可达(billing + Speech-to-Text API 已就绪)")
    except Exception as e:
        msg = str(e)
        hint = ""
        if "billing" in msg.lower() or "BILLING" in msg:
            hint = "\n  → 这个项目没开 billing。去 https://console.cloud.google.com/billing 给项目关联结算账号。"
        elif "SERVICE_DISABLED" in msg or "has not been used" in msg or "not enabled" in msg.lower():
            hint = "\n  → Speech API 没启用。开 billing 后:gcloud services enable speech.googleapis.com"
        print("✗ API 调用失败(billing/API/权限其一):\n  %s%s" % (msg, hint))
        return 1

    print("→ 就绪。可在 Unity 里按 F8 实时转写了。")
    return 0


def main():
    # 统一 UTF-8 输出:Windows 控制台默认 cp1252,直接 print 中文/符号会崩(服务模式 Unity 另设了 PYTHONIOENCODING)。
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    args = [a for a in sys.argv[1:] if a]
    if args and args[0] in ("--check", "-check", "check"):
        sys.exit(check())
    wavs = [a for a in args if not a.startswith("-")]
    if wavs:
        batch(wavs)
        return
    server_loop()


if __name__ == "__main__":
    main()
