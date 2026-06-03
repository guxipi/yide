#!/usr/bin/env python3
# 翼德 · Google Cloud Speech-to-Text(Chirp 3 · v2)转写。海外可用、普通话准、带标点。
# 两种模式合一:
#   · 常驻服务(Unity 标注用):无参启动 → 打印一行 __READY__ → 从 stdin 一行一个 wav 路径,
#     每条转写好一行一个 JSON 到 stdout {"wav":"...","text":"...中文..."}。停录即出字。
#   · 批量(scripts/playtest.js 用):python stt_google.py a/voice.wav b/voice.wav …
#     每条一行 JSON 到 stdout,转完退出。
#
# 认证:service account JSON,环境变量 GOOGLE_APPLICATION_CREDENTIALS 指向它(库自动读)。
# 可选环境变量:YIDE_GCP_PROJECT(默认从 JSON 的 project_id 读)· YIDE_GCP_LOCATION(默认 us;Chirp 3 支持 us/eu 多区)
#              · YIDE_STT_LANG(默认 cmn-Hans-CN 普通话)· YIDE_STT_MODEL(默认 chirp_3)
# 装法:pip install google-cloud-speech(轻量,无 PyTorch)。详见 SETUP.md。
import os, sys, json


def emit(o):
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def fatal(msg, code):
    sys.stderr.write(json.dumps({"error": msg}, ensure_ascii=False) + "\n")
    sys.stderr.flush()
    sys.exit(code)


def main():
    wavs = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    server_mode = len(wavs) == 0

    try:
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech
        from google.api_core.client_options import ClientOptions
    except Exception as e:
        fatal("google-cloud-speech 未安装: %s(pip install google-cloud-speech)" % e, 3)

    # 认证两种都支持:
    #   ① service account JSON —— 环境变量 GOOGLE_APPLICATION_CREDENTIALS 指向它(库自动读)。
    #   ② gcloud ADC 登录 —— 无密钥文件(组织禁了密钥下载时用):先 `gcloud auth application-default login`。
    # 都不设也行:只要机器上有任一可用的默认凭证,SpeechClient() 会自动找到。
    project = os.environ.get("YIDE_GCP_PROJECT")
    if not project:
        cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if cred and os.path.exists(cred):
            try:
                with open(cred, "r", encoding="utf-8") as f:
                    project = json.load(f).get("project_id")
            except Exception:
                project = None
    if not project:
        try:
            import google.auth
            _, project = google.auth.default()   # ADC / 默认凭证里带的 project
        except Exception:
            project = None
    if not project:
        fatal("拿不到 GCP project_id(设 YIDE_GCP_PROJECT,或用 service account JSON / 先跑 gcloud auth application-default login 并 set-quota-project)", 5)

    location = os.environ.get("YIDE_GCP_LOCATION", "us").strip() or "us"   # Chirp 3: us / eu 多区
    lang = os.environ.get("YIDE_STT_LANG", "cmn-Hans-CN")                  # 普通话
    model = os.environ.get("YIDE_STT_MODEL", "chirp_3")

    try:
        # 非 global 区域要把 endpoint 切到 {区域}-speech.googleapis.com
        client = SpeechClient(client_options=ClientOptions(api_endpoint=location + "-speech.googleapis.com"))
    except Exception as e:
        fatal("STT 客户端初始化失败: %s" % e, 6)

    recognizer = "projects/%s/locations/%s/recognizers/_" % (project, location)
    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),   # 自动识别 wav 头
        language_codes=[lang],
        model=model,
        features=cloud_speech.RecognitionFeatures(enable_automatic_punctuation=True),
    )

    def transcribe(wav):
        try:
            with open(wav, "rb") as f:
                content = f.read()
            req = cloud_speech.RecognizeRequest(recognizer=recognizer, config=config, content=content)
            resp = client.recognize(request=req)
            text = "".join(r.alternatives[0].transcript for r in resp.results if r.alternatives).strip()
            return {"wav": wav, "text": text}
        except Exception as e:
            return {"wav": wav, "text": "", "error": str(e)}

    if not server_mode:
        for wav in wavs:
            emit(transcribe(wav))
        return

    # 常驻服务:告诉编辑器已就绪,然后逐行处理
    sys.stdout.write("__READY__\n")
    sys.stdout.flush()
    for line in sys.stdin:
        wav = line.strip().strip('"')
        if not wav:
            continue
        emit(transcribe(wav))


if __name__ == "__main__":
    main()
