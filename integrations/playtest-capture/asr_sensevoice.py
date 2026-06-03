#!/usr/bin/env python3
# 翼德 · 本地中文转写(SenseVoice,离线、免费、不上云)。
# 由 scripts/playtest.js 调用:一次传本场所有 marker 的 voice.wav,加载模型一次、批量转写。
# 输出:每行一个 JSON {"wav": "<路径>", "text": "<中文带标点>"} 到 stdout。
# 装法见 SETUP.md(pip install funasr;首次自动拉 ~400MB 模型;纯 CPU 可跑)。
#
# 用法:python asr_sensevoice.py a/voice.wav b/voice.wav ...
import sys, json

def main():
    wavs = [a for a in sys.argv[1:] if a and not a.startswith("-")]
    if not wavs:
        print(json.dumps({"error": "no wav given"}), file=sys.stderr)
        sys.exit(2)
    try:
        from funasr import AutoModel
        from funasr.utils.postprocess_utils import rich_transcription_postprocess
    except Exception as e:
        print(json.dumps({"error": "funasr 未安装: %s" % e}), file=sys.stderr)
        sys.exit(3)

    # 加载一次:SenseVoice-Small + VAD(切分) + ITN(标点/数字规整)
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        vad_model="fsmn-vad",
        vad_kwargs={"max_single_segment_time": 30000},
        device="cpu",
        disable_update=True,
    )
    for wav in wavs:
        try:
            res = model.generate(input=wav, cache={}, language="zh", use_itn=True, batch_size_s=60)
            text = rich_transcription_postprocess(res[0]["text"]) if res else ""
            print(json.dumps({"wav": wav, "text": text}, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"wav": wav, "text": "", "error": str(e)}, ensure_ascii=False))
        sys.stdout.flush()

if __name__ == "__main__":
    main()
