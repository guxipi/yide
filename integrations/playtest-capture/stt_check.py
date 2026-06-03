#!/usr/bin/env python3
# 翼德 · Google STT 一键自检(进 Unity 前先跑这个,确认"云那条链路"全通)。
# 用法:python stt_check.py
#   它会逐步检查:库装没装 → 凭证/项目(ADC 或 service account JSON)→ 真调一次 Chirp 3。
#   用一段静音做测试,所以转写出来是空字符串——这是正常的,关键看"有没有报错"。
# 区域默认 eu(海外低延迟),可设 YIDE_GCP_LOCATION 改;项目默认从凭证自动取,可设 YIDE_GCP_PROJECT 覆盖。
import os, sys, tempfile, wave


def ok(m):  print("  [OK] " + m)
def bad(m): print("  [X]  " + m)


def main():
    location = os.environ.get("YIDE_GCP_LOCATION", "eu").strip() or "eu"
    lang = os.environ.get("YIDE_STT_LANG", "cmn-Hans-CN")
    model = os.environ.get("YIDE_STT_MODEL", "chirp_3")

    print("== 翼德 Google STT 自检 ==")
    print("区域=%s  语言=%s  模型=%s" % (location, lang, model))

    # 1) 库
    print("\n1) 检查 google-cloud-speech 是否装好…")
    try:
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech
        from google.api_core.client_options import ClientOptions
        import google.auth
        ok("库已安装")
    except Exception as e:
        bad("库没装好:%s" % e)
        print("\n→ 跑:pip install google-cloud-speech")
        sys.exit(1)

    # 2) 凭证 + 项目
    print("\n2) 检查凭证与项目(ADC 登录 或 service account JSON)…")
    project = os.environ.get("YIDE_GCP_PROJECT")
    try:
        creds, adc_project = google.auth.default()
        ok("找到默认凭证(ADC / 密钥)")
        if not project:
            project = adc_project
    except Exception as e:
        bad("找不到凭证:%s" % e)
        print("\n→ 跑:gcloud auth application-default login   再  gcloud auth application-default set-quota-project <项目ID>")
        print("   或在 Unity ⚙ 填 service account JSON。")
        sys.exit(2)
    if not project:
        bad("拿不到项目 ID(凭证里没带)")
        print("\n→ 跑:gcloud auth application-default set-quota-project <项目ID>")
        print("   或设环境变量 YIDE_GCP_PROJECT=<项目ID> 再跑本自检。")
        sys.exit(3)
    ok("项目 ID = %s" % project)

    # 3) 造一段 1 秒静音 wav
    wav_path = os.path.join(tempfile.gettempdir(), "yide_stt_check.wav")
    w = wave.open(wav_path, "wb")
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b"\x00\x00" * 16000)
    w.close()

    # 4) 真调一次 Chirp 3
    print("\n3) 真调一次 Chirp 3(静音测试,出空字是正常的,看有没有报错)…")
    try:
        client = SpeechClient(client_options=ClientOptions(api_endpoint=location + "-speech.googleapis.com"))
        recognizer = "projects/%s/locations/%s/recognizers/_" % (project, location)
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=[lang],
            model=model,
            features=cloud_speech.RecognitionFeatures(enable_automatic_punctuation=True),
        )
        with open(wav_path, "rb") as f:
            content = f.read()
        resp = client.recognize(request=cloud_speech.RecognizeRequest(
            recognizer=recognizer, config=config, content=content))
        text = "".join(r.alternatives[0].transcript for r in resp.results if r.alternatives).strip()
        ok("Chirp 3 调通!转写返回:\"%s\"(静音→空,正常)" % text)
        print("\n✅ 全通过 —— 云那条链路 working,可以进 Unity 了。")
    except Exception as e:
        bad("调用失败:%s" % e)
        msg = str(e)
        print("\n→ 常见原因:")
        if "PERMISSION_DENIED" in msg or "permission" in msg.lower():
            print("   · 登录的账号没 Cloud Speech Client 权限,或 Speech-to-Text API 没启用(刚启用等 1-2 分钟)。")
        elif "quota" in msg.lower() or "billing" in msg.lower():
            print("   · quota 项目没设:gcloud auth application-default set-quota-project <项目ID>;或结算没开。")
        else:
            print("   · 把上面这行 [X] 整句发给翼德,他看是哪坏了。")
        sys.exit(4)


if __name__ == "__main__":
    main()
