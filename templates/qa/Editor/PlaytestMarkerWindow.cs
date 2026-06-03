// 翼德 · Playtest 标注 — 编辑器停靠窗口(放进任意 Editor/ 文件夹)
// 它是独立的 EditorWindow,停靠在 Game 视图旁/下,绝不遮挡游戏画面。
// 冻帧时自动弹出:大图截图(可点开放大)+ 自动抓到的命中元素/上下文 + 语音转写自动回填的打字框 + 保存/取消。
// 流程(F8 三段):①开始录音 → ②停录(自动 Google STT 转写,几秒后中文回填到框,可改)→ ③保存。
#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Yide.Playtest
{
    // 编辑器侧轮询:① 标注一开始(冻帧)自动弹窗;② 录音一开始就预热转写服务;
    // ③ 停录拿到新一条就喂去转写、几秒后把中文回填到打字框。
    // 用轮询而非运行时直接调:运行时程序集不能引用 Editor 程序集的类型。
    [InitializeOnLoad]
    static class PlaytestMarkerAutoOpen
    {
        static bool _wasActive;
        static int _lastSubmittedJob;   // 已提交转写的 VoiceJobId,避免重复提交

        static PlaytestMarkerAutoOpen() { EditorApplication.update += Tick; }

        static void Tick()
        {
            // ① 冻帧即弹窗
            if (PlaytestMarkerBridge.Active && !_wasActive) PlaytestMarkerWindow.Open();
            _wasActive = PlaytestMarkerBridge.Active;

            // ② 录音中就预热服务(载模型约 10 秒,等勾哥说完停录时通常已就绪)
            if (PlaytestMarkerBridge.Phase == MarkPhase.Recording) PlaytestAsrServer.EnsureStarted();

            // ③ 来了新的一条(停录)→ 提交转写
            if (PlaytestMarkerBridge.VoiceJobId != _lastSubmittedJob && !string.IsNullOrEmpty(PlaytestMarkerBridge.VoiceWavPath))
            {
                _lastSubmittedJob = PlaytestMarkerBridge.VoiceJobId;
                if (PlaytestAsrServer.EnsureStarted())
                {
                    PlaytestMarkerBridge.TranscriptStatus = "转写中…(Google STT)";
                    PlaytestAsrServer.Submit(PlaytestMarkerBridge.VoiceWavPath);
                }
                else
                {
                    PlaytestMarkerBridge.TranscriptStatus = "转写不可用:" + PlaytestAsrServer.LastError + " — 可直接打字";
                }
                PlaytestMarkerBridge.Changed();
            }

            // 处理服务输出
            bool repaint = false;
            if (PlaytestAsrServer.Poll(out var res))
            {
                // 只认当前这条的结果(按 wav 路径对齐)
                if (PlaytestMarkerBridge.Active && res.wav == PlaytestMarkerBridge.VoiceWavPath)
                {
                    if (!string.IsNullOrEmpty(res.error))
                        PlaytestMarkerBridge.TranscriptStatus = "转写失败:" + res.error + " — 可直接打字";
                    else if (string.IsNullOrEmpty((res.text ?? "").Trim()))
                        PlaytestMarkerBridge.TranscriptStatus = "(没听清 — 可直接打字)";
                    else
                    {
                        // 框是空的就自动填;勾哥已经动手打了就不覆盖(状态里提示已转写)
                        if (string.IsNullOrEmpty((PlaytestMarkerBridge.TypedNote ?? "").Trim()))
                            PlaytestMarkerBridge.TypedNote = res.text.Trim();
                        PlaytestMarkerBridge.TranscriptStatus = "✓ 已转写(可改)";
                    }
                    repaint = true;
                }
            }
            // 服务启动失败也要刷新状态
            if (PlaytestMarkerBridge.Active && PlaytestAsrServer.Status == PlaytestAsrServer.State.Failed
                && PlaytestMarkerBridge.TranscriptStatus.IndexOf("转写") >= 0
                && PlaytestMarkerBridge.TranscriptStatus.IndexOf("失败") < 0
                && PlaytestMarkerBridge.TranscriptStatus.IndexOf("不可用") < 0)
            {
                PlaytestMarkerBridge.TranscriptStatus = "转写不可用:" + PlaytestAsrServer.LastError + " — 可直接打字";
                repaint = true;
            }
            if (repaint) PlaytestMarkerBridge.Changed();
        }
    }

    public class PlaytestMarkerWindow : EditorWindow
    {
        Texture2D _thumb;
        bool _showSettings;

        public static void Open()
        {
            var w = GetWindow<PlaytestMarkerWindow>(false, "翼德 标注", true);
            w.minSize = new Vector2(360, 460);
            w.Show();
            w.Repaint();
        }

        void OnEnable()  { PlaytestMarkerBridge.OnChanged += OnChanged; }
        void OnDisable() { PlaytestMarkerBridge.OnChanged -= OnChanged; }
        void OnChanged() { _thumb = null; Repaint(); }

        void OnGUI()
        {
            if (!PlaytestMarkerBridge.Active || PlaytestMarkerBridge.Pending == null)
            {
                EditorGUILayout.Space(8);
                EditorGUILayout.HelpBox("没有进行中的标注。\n在 Play 模式按 F8 冻帧并开始录音。", MessageType.Info);
                DrawSettings();
                return;
            }
            var m = PlaytestMarkerBridge.Pending;
            var phase = PlaytestMarkerBridge.Phase;

            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField($"◆ 本场第 {m.index} 条 · 场景 {m.scene}", EditorStyles.boldLabel);

            // 截图大图(按窗口高度自适应放大;点一下弹出全尺寸放大窗)
            if (_thumb == null && File.Exists(m.shotPath))
            {
                var bytes = File.ReadAllBytes(m.shotPath);
                _thumb = new Texture2D(2, 2);
                _thumb.LoadImage(bytes);
            }
            if (_thumb != null)
            {
                float w = EditorGUIUtility.currentViewWidth - 24f;
                // 给截图留窗口约一半高度,竖屏也能看清(原来死封 220 → 竖屏被压成细条)
                float maxH = Mathf.Clamp(position.height * 0.5f, 260f, 1000f);
                float h = Mathf.Min(maxH, w * _thumb.height / Mathf.Max(1, _thumb.width));
                var r = GUILayoutUtility.GetRect(w, h);
                GUI.DrawTexture(r, _thumb, ScaleMode.ScaleToFit);
                if (GUI.Button(r, GUIContent.none, GUIStyle.none)) PlaytestShotZoom.Show(m.shotPath);
                EditorGUILayout.LabelField("(点击截图可放大查看)", EditorStyles.centeredGreyMiniLabel);
            }
            else
            {
                EditorGUILayout.HelpBox("截图生成中…(冻帧后下一帧落盘)", MessageType.None);
            }

            // 自动抓到的上下文
            EditorGUILayout.Space(4);
            using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
            {
                EditorGUILayout.LabelField("▶ 命中元素(自动)", EditorStyles.miniBoldLabel);
                EditorGUILayout.SelectableLabel(m.hitPath, EditorStyles.wordWrappedLabel, GUILayout.Height(34));
                if (!string.IsNullOrEmpty(m.hitSource))
                    EditorGUILayout.LabelField("来源 " + m.hitSource, EditorStyles.miniLabel);
                EditorGUILayout.LabelField($"分辨率 {m.screenW}×{m.screenH} · FPS {m.fps} · 版本 {m.version} · t {m.timeInGame:0.0}s", EditorStyles.miniLabel);
            }

            // 语音 / 转写状态
            EditorGUILayout.Space(4);
            if (phase == MarkPhase.Recording)
            {
                var recOn = Microphone.IsRecording(null);
                EditorGUILayout.LabelField(recOn ? "🎙 正在听…说出这里的问题(说完按 F8 停录)" : "🎙 未检测到麦克风(可只打字,按 F8 继续)",
                    recOn ? EditorStyles.boldLabel : EditorStyles.miniLabel);
            }
            else // Reviewing
            {
                var st = string.IsNullOrEmpty(PlaytestMarkerBridge.TranscriptStatus) ? "复核文字" : PlaytestMarkerBridge.TranscriptStatus;
                EditorGUILayout.LabelField("📝 " + st, EditorStyles.boldLabel);
            }

            // 打字框(转写自动回填,可改)
            EditorGUILayout.Space(2);
            EditorGUILayout.LabelField("⌨ 语音转写 / 打字补充(确认无误后按 F8 保存)", EditorStyles.miniLabel);
            PlaytestMarkerBridge.TypedNote = EditorGUILayout.TextArea(
                PlaytestMarkerBridge.TypedNote ?? "", GUILayout.Height(84));

            // 按钮(标签随阶段变)
            EditorGUILayout.Space(8);
            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.backgroundColor = new Color(0.95f, 0.4f, 0.4f);
                if (GUILayout.Button("✗ 取消 (Esc)", GUILayout.Height(34))) PlaytestMarkerBridge.RequestCancel?.Invoke();
                GUI.backgroundColor = new Color(0.3f, 0.85f, 0.55f);
                var advLabel = phase == MarkPhase.Recording ? "■ 停录并转写 (F8)" : "✓ 保存并继续 (F8)";
                if (GUILayout.Button(advLabel, GUILayout.Height(34))) PlaytestMarkerBridge.RequestAdvance?.Invoke();
                GUI.backgroundColor = Color.white;
            }
            EditorGUILayout.LabelField("F8 开始录音 → 停录转写 → 保存 · Esc 取消 · 面板不挡游戏", EditorStyles.centeredGreyMiniLabel);

            DrawSettings();
        }

        // 一次性配置:Python / stt_google.py / Google 凭证(EditorPrefs 永久记住,默认从环境变量种子)
        void DrawSettings()
        {
            EditorGUILayout.Space(6);
            bool needScript = string.IsNullOrEmpty(PlaytestAsrServer.ScriptPath) || !File.Exists(PlaytestAsrServer.ScriptPath);
            bool needCred = string.IsNullOrEmpty(PlaytestAsrServer.CredentialPath) || !File.Exists(PlaytestAsrServer.CredentialPath);
            bool needSetup = needScript || needCred;
            if (needSetup)
                EditorGUILayout.HelpBox("Google 转写还没配好 → 停录后不会自动出字(可照常打字,事后再补转)。\n展开下方「⚙ 转写设置」:指向 stt_google.py + service account JSON,设一次即可。", MessageType.Warning);

            _showSettings = EditorGUILayout.Foldout(_showSettings || needSetup, "⚙ 转写设置(Google STT · 设一次)", true);
            if (!(_showSettings || needSetup)) return;

            using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
            {
                PlaytestAsrServer.PythonPath = EditorGUILayout.TextField("Python", PlaytestAsrServer.PythonPath);
                using (new EditorGUILayout.HorizontalScope())
                {
                    PlaytestAsrServer.ScriptPath = EditorGUILayout.TextField("stt_google.py", PlaytestAsrServer.ScriptPath);
                    if (GUILayout.Button("选择…", GUILayout.Width(56)))
                    {
                        var p = EditorUtility.OpenFilePanel("选择 stt_google.py", "", "py");
                        if (!string.IsNullOrEmpty(p)) PlaytestAsrServer.ScriptPath = p;
                    }
                }
                using (new EditorGUILayout.HorizontalScope())
                {
                    PlaytestAsrServer.CredentialPath = EditorGUILayout.TextField("服务账号 JSON", PlaytestAsrServer.CredentialPath);
                    if (GUILayout.Button("选择…", GUILayout.Width(56)))
                    {
                        var p = EditorUtility.OpenFilePanel("选择 Google service account JSON", "", "json");
                        if (!string.IsNullOrEmpty(p)) PlaytestAsrServer.CredentialPath = p;
                    }
                }
                PlaytestAsrServer.Region = EditorGUILayout.TextField("区域 (us/eu)", PlaytestAsrServer.Region);
                EditorGUILayout.LabelField("状态:" + PlaytestAsrServer.Status
                    + (string.IsNullOrEmpty(PlaytestAsrServer.LastError) ? "" : " · " + PlaytestAsrServer.LastError),
                    EditorStyles.miniLabel);
                EditorGUILayout.LabelField("需先 pip install google-cloud-speech;配置见 SETUP.md。海外区域填 eu 延迟更低。", EditorStyles.centeredGreyMiniLabel);
            }
        }
    }

    // 截图放大窗:点内联截图弹出,按窗口宽铺满、纵向滚动,竖屏长图也能看清。
    public class PlaytestShotZoom : EditorWindow
    {
        Texture2D _tex;
        Vector2 _scroll;

        public static void Show(string path)
        {
            if (!File.Exists(path)) return;
            var w = GetWindow<PlaytestShotZoom>(true, "截图放大", true);
            var t = new Texture2D(2, 2);
            t.LoadImage(File.ReadAllBytes(path));
            w._tex = t;
            w.minSize = new Vector2(420, 480);
            w.Show();
        }

        void OnGUI()
        {
            if (_tex == null) { EditorGUILayout.HelpBox("没有截图。", MessageType.Info); return; }
            float w = position.width - 4f;
            float h = w * _tex.height / Mathf.Max(1, _tex.width);
            _scroll = EditorGUILayout.BeginScrollView(_scroll);
            var r = GUILayoutUtility.GetRect(w, h);
            GUI.DrawTexture(r, _tex, ScaleMode.ScaleToFit);
            EditorGUILayout.EndScrollView();
        }
    }
}
#endif
