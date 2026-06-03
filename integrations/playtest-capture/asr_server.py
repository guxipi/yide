#!/usr/bin/env python3
# 翼德 · 本地中文转写 · 常驻服务版(给 Unity 编辑器在标注时"停录即出字"用)。
# 和 asr_sensevoice.py 同一个 SenseVoice 模型/配置,区别只在:模型只加载一次、之后常驻,
# 从 stdin 一行一个 wav 路径喂进来,转写好一行一个 JSON 吐到 stdout。首条因为冷启会慢
# (载模型约 10 秒),之后每条 1-3 秒。Unity 编辑器在录音一开始就预热它,停录时通常已就绪。
#
# 协议(编辑器侧按此读)：
#   · 模型加载完成 → stdout 打印一行  __READY__
#   · 每收到一行 wav 路径 → stdout 打印一行 {"wav": "...", "text": "...中文..."}(失败带 "error")
#   · stdin 关闭 / 收到空行串 EOF → 退出
#   · 加载/致命错误 → stderr 打印一行 {"error": "..."} 并以非 0 退出
#
# 用法：python asr_server.py        （然后往它 stdin 逐行写 wav 路径）
import os, sys, json


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def fatal(msg, code):
    sys.stderr.write(json.dumps({"error": msg}, ensure_ascii=False) + "\n")
    sys.stderr.flush()
    sys.exit(code)


def main():
    try:
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
    except Exception as e:
        fatal("funasr 未安装: %s" % e, 3)

    # 源:默认 ModelScope(ms);海外慢可设 YIDE_ASR_HUB=hf 切到 HuggingFace。与 asr_sensevoice.py 一致。
    hub = os.environ.get("YIDE_ASR_HUB", "ms").lower()
    model_id = "FunAudioLLM/SenseVoiceSmall" if hub == "hf" else "iic/SenseVoiceSmall"

    try:
        model = AutoModel(
            model=model_id,
            hub=hub,
            trust_remote_code=True,
            vad_model="fsmn-vad",
            vad_kwargs={"max_single_segment_time": 30000},
            device="cpu",
            disable_update=True,
        )
    except Exception as e:
        fatal("模型加载失败: %s" % e, 4)

    # 告诉编辑器:已就绪,可以喂 wav 了。
    sys.stdout.write("__READY__\n")
    sys.stdout.flush()

    # 常驻:一行一个 wav 路径
    for line in sys.stdin:
        wav = line.strip().strip('"')
        if not wav:
            continue
        try:
            res = model.generate(input=wav, cache={}, language="zh", use_itn=True,
                                 batch_size_s=60, merge_vad=True, merge_length_s=15)
            text = rich_transcription_postprocess(res[0]["text"]) if res else ""
            emit({"wav": wav, "text": text})
        except Exception as e:
            emit({"wav": wav, "text": "", "error": str(e)})


if __name__ == "__main__":
    main()
