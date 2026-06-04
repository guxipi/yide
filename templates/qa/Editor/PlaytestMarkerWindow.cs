// 翼德 · Playtest 标注 — 编辑器停靠窗口(放进任意 Editor/ 文件夹)
// 它是独立的 EditorWindow,停靠在 Game 视图旁/下,绝不遮挡游戏画面。
// 冻帧时自动弹出:大图截图(可点开放大)+ 自动抓到的命中元素/上下文 + 语音实时转写自动回填的打字框 + 保存/取消。
// 流程(F8 三段):①开始(Python 持麦,边说边出字)→ ②停录(收尾出最终稿,可改)→ ③保存。
#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Yide.Playtest
{
    // 编辑器侧轮询:① 标注一开始(冻帧)自动弹窗;② 进入录音 → 拉起服务并发 START(Python 持麦+流式转写);
    // ③ 边说边把 interim 文字实时回填打字框;④ 离开录音(停录/取消/保存)发 STOP 收尾。
    // 用轮询而非运行时直接调:运行时程序集不能引用 Editor 程序集的类型。
    [InitializeOnLoad]
    static class PlaytestMarkerAutoOpen
    {
        static bool _wasActive;
        static MarkPhase _lastPhase = MarkPhase.Idle;
        static string _lastAuto = "";   // 上次由转写自动写进框的值,用于判断勾哥是否手改过

        static PlaytestMarkerAutoOpen() { EditorApplication.update += Tick; }

        static void Tick()
        {
            // ① 冻帧即弹窗
            if (PlaytestMarkerBridge.Active && !_wasActive) PlaytestMarkerWindow.Open();
            _wasActive = PlaytestMarkerBridge.Active;

            // ⓪ 预热:进 Play 就把转写服务拉起来(纯 python 进程 + 建 client,空闲不烧 API)。
            // 这样按 F8 时进程已 Ready、立刻发 START,只剩开麦那一下 → 开启延迟压进 1 秒内。
            if (EditorApplication.isPlaying && PlaytestAsrServer.Status == PlaytestAsrServer.State.Off
                && !string.IsNullOrEmpty(PlaytestAsrServer.ScriptPath) && File.Exists(PlaytestAsrServer.ScriptPath))
                PlaytestAsrServer.EnsureStarted();

            var phase = PlaytestMarkerBridge.Phase;

            // ② 进入录音:拉起服务并发 START(Python 持麦 + 流式转写到 voice.wav)
            if (phase == MarkPhase.Recording && _lastPhase != MarkPhase.Recording)
            {
                _lastAuto = "";
                if (PlaytestAsrServer.EnsureStarted())
                {
                    PlaytestMarkerBridge.TranscriptStatus = "🎙 听写中…(Google 实时)";
                    PlaytestAsrServer.BeginStream(PlaytestMarkerBridge.VoiceWavPath);
                }
                else
                {
                    PlaytestMarkerBridge.TranscriptStatus = "转写不可用:" + PlaytestAsrServer.LastError + " — 可直接打字";
                }
                PlaytestMarkerBridge.Changed();
            }
            // ③ 离开录音(停录/取消/保存)→ 发 STOP 收尾
            if (phase != MarkPhase.Recording && _lastPhase == MarkPhase.Recording)
                PlaytestAsrServer.EndStream();
            _lastPhase = phase;

            // ④ 消化服务输出:边说边把文字回填打字框
            bool repaint = false;
            if (PlaytestAsrServer.Poll(out var res))
            {
                if (PlaytestMarkerBridge.Active)
                {
                    if (!string.IsNullOrEmpty(res.error))
                    {
                        PlaytestMarkerBridge.TranscriptStatus = "转写失败:" + res.error + " — 可直接打字";
                    }
                    else if (res.type == "interim" || res.type == "final")
                    {
                        // 录音中:实时把全文写进框(此时勾哥在说不在打字)
                        if (PlaytestMarkerBridge.Phase == MarkPhase.Recording)
                        {
                            PlaytestMarkerBridge.TypedNote = res.text ?? "";
                            _lastAuto = PlaytestMarkerBridge.TypedNote;
                            PlaytestMarkerBridge.TranscriptStatus = "🎙 听写中…(实时)";
                        }
                    }
                    else if (res.type == "done")
                    {
                        var t = (res.text ?? "").Trim();
                        // 框空、或还是转写自动填的值(勾哥没手改)→ 用最终稿覆盖;手改过就不动
                        if (t.Length > 0)
                        {
                            var cur = PlaytestMarkerBridge.TypedNote ?? "";
                            if (cur.Trim().Length == 0 || cur == _lastAuto)
                            {
                                PlaytestMarkerBridge.TypedNote = t;
                                _lastAuto = t;
                            }
                        }
                        // done 到达时仍在 Recording = 静音自动停(用户按停录会先切到 Reviewing)→ 等同停录,推进到复核
                        bool autoStop = PlaytestMarkerBridge.Phase == MarkPhase.Recording;
                        if (autoStop) PlaytestMarkerBridge.RequestAdvance?.Invoke();
                        PlaytestMarkerBridge.TranscriptStatus = autoStop
                            ? "⏸ 30秒静音,已自动停转写(省 API)· " + (t.Length == 0 ? "没听到话,可直接打字" : "已转写,可改后保存")
                            : (t.Length == 0 ? "(没听清 — 可直接打字)" : "✓ 已转写(可改)");
                    }
                    repaint = true;
                }
            }
            // 服务启动失败也要刷新状态
            if (PlaytestMarkerBridge.Active && PlaytestAsrServer.Status == PlaytestAsrServer.State.Failed
                && PlaytestMarkerBridge.TranscriptStatus.IndexOf("失败") < 0
                && PlaytestMarkerBridge.TranscriptStatus.IndexOf("不可用") < 0)
            {
                PlaytestMarkerBridge.TranscriptStatus = "转写不可用:" + PlaytestAsrServer.LastError + " — 可直接打字";
                repaint = true;
            }
            if (repaint) PlaytestMarkerBridge.Changed();
        }
    }

    // session 自动清理:删掉 N 天没改动的 playtest session(产物在 Drive,别越积越多)。
    // 判据用"最后修改时间"(Windows 的"最后访问时间"默认关闭、不可靠);翼德读某 session 时会 touch 它当续期。
    [InitializeOnLoad]
    static class PlaytestSessionCleanup
    {
        const int KeepDays = 7;

        static PlaytestSessionCleanup()
        {
            EditorApplication.delayCall += Prune;                       // 编辑器加载后跑一次
            EditorApplication.playModeStateChanged += s =>
            { if (s == PlayModeStateChange.EnteredPlayMode) Prune(); };  // 每次进 Play 也清一次
        }

        static void Prune()
        {
            try
            {
                var root = SessionRoot();
                if (!Directory.Exists(root)) return;
                var cutoff = System.DateTime.Now.AddDays(-KeepDays);
                foreach (var dir in Directory.GetDirectories(root, "session-*"))
                {
                    try
                    {
                        if (Directory.GetLastWriteTime(dir) < cutoff)
                        {
                            Directory.Delete(dir, true);
                            Debug.Log($"[翼德] 清理过期 playtest session(>{KeepDays}天未改动):{Path.GetFileName(dir)}");
                        }
                    }
                    catch { /* 单个删不掉(占用/同步中)就跳过,下次再清 */ }
                }
            }
            catch { }
        }

        // 与 PlaytestMarker.SessionRoot 同源(同一个 EditorPrefs 键)
        static string SessionRoot()
        {
            var custom = EditorPrefs.GetString("Yide.Playtest.SessionRoot", "");
            if (!string.IsNullOrEmpty(custom)) return custom;
            return Path.Combine(Directory.GetParent(Application.dataPath).FullName, "QA", "playtest");
        }
    }

    public class PlaytestMarkerWindow : EditorWindow
    {
        Texture2D _thumb;
        bool _showSettings;
        GUIStyle _noteStyle;   // 打字框样式:自动换行

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
                var status = PlaytestAsrServer.Status;
                bool ready = status == PlaytestAsrServer.State.Ready;
                string msg = ready ? "🎙 正在听…说出这里的问题(边说边出字,说完按 F8 停录)"
                           : status == PlaytestAsrServer.State.Starting ? "🎙 转写服务启动中…(可先说,稍后回填;或直接打字)"
                           : "🎙 转写未就绪:可直接打字,按 F8 继续";
                EditorGUILayout.LabelField(msg, ready ? EditorStyles.boldLabel : EditorStyles.miniLabel);
            }
            else // Reviewing
            {
                var st = string.IsNullOrEmpty(PlaytestMarkerBridge.TranscriptStatus) ? "复核文字" : PlaytestMarkerBridge.TranscriptStatus;
                EditorGUILayout.LabelField("📝 " + st, EditorStyles.boldLabel);
            }

            // 打字框(转写自动回填,可改)
            EditorGUILayout.Space(2);
            EditorGUILayout.LabelField("⌨ 语音转写 / 打字补充(确认无误后按 F8 保存)", EditorStyles.miniLabel);
            if (_noteStyle == null) _noteStyle = new GUIStyle(EditorStyles.textArea) { wordWrap = true };
            PlaytestMarkerBridge.TypedNote = EditorGUILayout.TextArea(
                PlaytestMarkerBridge.TypedNote ?? "", _noteStyle, GUILayout.Height(84));

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
            if (needScript)
                EditorGUILayout.HelpBox("Google 转写还没配好 → 录音不会自动出字(可照常打字,事后再补转)。\n展开下方「⚙ 转写设置」:指向 stt_google.py,设一次即可。\n认证默认走 gcloud ADC(先 gcloud auth application-default login);用 service account 才需填 JSON。", MessageType.Warning);

            _showSettings = EditorGUILayout.Foldout(_showSettings || needScript, "⚙ 转写设置(Google STT · 设一次)", true);
            if (!(_showSettings || needScript)) return;

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
                    PlaytestAsrServer.CredentialPath = EditorGUILayout.TextField("服务账号 JSON(可留空)", PlaytestAsrServer.CredentialPath);
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
                EditorGUILayout.LabelField("需先 pip install google-cloud-speech sounddevice;JSON 留空走 gcloud ADC。区域 us/eu。", EditorStyles.centeredGreyMiniLabel);
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
