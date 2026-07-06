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

        // 与 PlaytestMarker.SessionRoot 同源(同一个 EditorPrefs 键);规范落工程内 "QA/playtest"(消费端 playtest.js / .gitignore 同此)。
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
        GUIStyle _noteStyle, _stepOn, _stepOff;   // 缓存:每帧 new GUIStyle 会爆 GC,IMGUI 规范是建一次复用

        void EnsureStyles()
        {
            if (_noteStyle != null) return;
            _noteStyle = new GUIStyle(EditorStyles.textArea) { wordWrap = true };
            _stepOff   = new GUIStyle(EditorStyles.miniLabel) { alignment = TextAnchor.MiddleCenter };
            _stepOn    = new GUIStyle(_stepOff) { fontStyle = FontStyle.Bold };
            _stepOn.normal.textColor = new Color(0.30f, 0.85f, 0.55f);
        }

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
            EnsureStyles();

            if (!PlaytestMarkerBridge.Active || PlaytestMarkerBridge.Pending == null)
            {
                DrawIdle();
                return;
            }

            var m = PlaytestMarkerBridge.Pending;
            var phase = PlaytestMarkerBridge.Phase;

            HandleKeys();

            EditorGUILayout.Space(8);
            DrawHeader(m, phase);
            EditorGUILayout.Space(8);
            DrawShot(m);
            EditorGUILayout.Space(6);
            DrawContext(m);
            EditorGUILayout.Space(6);
            DrawNote(phase);
            EditorGUILayout.Space(10);
            DrawActions(phase);

            DrawSettings();
        }

        // ── 空闲态:三种新建入口(配置项收进 ⚙ 设置,这里只留动作)──
        void DrawIdle()
        {
            EditorGUILayout.Space(8);
            using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
            {
                EditorGUILayout.LabelField("没有进行中的标注", EditorStyles.boldLabel);
                EditorGUILayout.LabelField("按 F8 截当前 Unity 窗口(Play 模式则冻帧并录音)。", EditorStyles.wordWrappedMiniLabel);
                EditorGUILayout.LabelField("网页 / 任意图:系统截图进剪贴板后点下方粘贴,或把图片拖进来。", EditorStyles.wordWrappedMiniLabel);
            }

            EditorGUILayout.Space(8);
            EditorGUILayout.LabelField("新建标注", EditorStyles.miniBoldLabel);
            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("📋 粘贴剪贴板", GUILayout.Height(34))) PlaytestEditorCapture.IngestFromClipboard();
                if (GUILayout.Button("📸 截图", GUILayout.Width(84), GUILayout.Height(34))) PlaytestEditorCapture.LaunchSnip();
            }
            DrawDropArea();

            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField("测完回 Claude Code 说「翼德看下截图」,按这批截图汇总 todo。", EditorStyles.centeredGreyMiniLabel);

            DrawSettings();
        }

        // Del/Backspace 删图、Esc 取消(打字框聚焦时不抢键,交给文本编辑)。
        // 键盘只发给聚焦中的窗口 → 没反应时先点本窗口,或用下方按钮(不依赖焦点)。
        void HandleKeys()
        {
            var ev = Event.current;
            if (ev.type != EventType.KeyDown || EditorGUIUtility.editingTextField) return;
            if (ev.keyCode == KeyCode.Delete || ev.keyCode == KeyCode.Backspace)
            {
                PlaytestEditorCapture.DeleteShot();
                ev.Use();
            }
            else if (ev.keyCode == KeyCode.Escape)
            {
                PlaytestMarkerBridge.RequestCancel?.Invoke();
                ev.Use();
            }
        }

        // 顶部:第几条 + 三段流程进度条(当前步高亮)
        void DrawHeader(PendingMarker m, MarkPhase phase)
        {
            EditorGUILayout.LabelField($"◆ 第 {m.index} 条 · 场景 {m.scene}", EditorStyles.boldLabel);
            int step = phase == MarkPhase.Recording ? 0 : 1;
            using (new EditorGUILayout.HorizontalScope())
            {
                DrawStep("① 录音", step == 0);
                DrawArrow();
                DrawStep("② 转写", step == 1);
                DrawArrow();
                DrawStep("③ 保存", false);
            }
        }

        void DrawStep(string label, bool active) =>
            GUILayout.Label(label, active ? _stepOn : _stepOff, GUILayout.Height(16));
        void DrawArrow() =>
            GUILayout.Label("▸", _stepOff, GUILayout.Width(14), GUILayout.Height(16));

        // 截图大图(按窗口高度自适应;点一下弹出全尺寸放大窗)+ 粘贴/删除
        void DrawShot(PendingMarker m)
        {
            if (_thumb == null && File.Exists(m.shotPath))
            {
                _thumb = new Texture2D(2, 2);
                _thumb.LoadImage(File.ReadAllBytes(m.shotPath));
            }
            if (_thumb != null)
            {
                float w = EditorGUIUtility.currentViewWidth - 24f;
                float maxH = Mathf.Clamp(position.height * 0.45f, 220f, 1000f);   // 竖屏长图也看得清
                float h = Mathf.Min(maxH, w * _thumb.height / Mathf.Max(1, _thumb.width));
                var r = GUILayoutUtility.GetRect(w, h);
                GUI.DrawTexture(r, _thumb, ScaleMode.ScaleToFit);
                if (GUI.Button(r, GUIContent.none, GUIStyle.none)) PlaytestShotZoom.Show(m.shotPath);
                EditorGUILayout.LabelField("点击放大", EditorStyles.centeredGreyMiniLabel);
            }
            else
            {
                EditorGUILayout.HelpBox("当前没有截图(已删除 / 生成中)。点下方「粘贴截图」把剪贴板的图贴进来。", MessageType.None);
            }

            using (new EditorGUILayout.HorizontalScope())
            {
                if (GUILayout.Button("📋 粘贴截图", GUILayout.Height(24))) PlaytestEditorCapture.PasteShotFromClipboard();
                using (new EditorGUI.DisabledScope(!File.Exists(m.shotPath)))
                    if (GUILayout.Button("🗑 删除 (Del)", GUILayout.Width(110), GUILayout.Height(24))) PlaytestEditorCapture.DeleteShot();
            }
        }

        // 自动抓到的上下文(fps / t 仅运行时有意义,为 0 不显示)
        void DrawContext(PendingMarker m)
        {
            using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
            {
                EditorGUILayout.LabelField("▶ 上下文(自动)", EditorStyles.miniBoldLabel);
                EditorGUILayout.SelectableLabel(m.hitPath, EditorStyles.wordWrappedLabel, GUILayout.Height(32));
                if (!string.IsNullOrEmpty(m.hitSource))
                    EditorGUILayout.LabelField("来源 " + m.hitSource, EditorStyles.miniLabel);
                string meta = $"{m.screenW}×{m.screenH} · v{m.version}";
                if (m.fps > 0 || m.timeInGame > 0f) meta += $" · {m.fps}fps · {m.timeInGame:0.0}s";
                EditorGUILayout.LabelField(meta, EditorStyles.miniLabel);
            }
        }

        // 阶段状态横幅 + 备注打字框(转写自动回填,可改)
        void DrawNote(MarkPhase phase)
        {
            if (phase == MarkPhase.Recording)
            {
                var status = PlaytestAsrServer.Status;
                bool ready = status == PlaytestAsrServer.State.Ready;
                string msg = ready ? "🎙 正在听…说出问题,说完按 F8 停录"
                           : status == PlaytestAsrServer.State.Starting ? "🎙 转写启动中…可先说或直接打字"
                           : "🎙 转写未就绪,可直接打字,按 F8 继续";
                EditorGUILayout.LabelField(msg, ready ? EditorStyles.boldLabel : EditorStyles.miniLabel);
            }
            else // Reviewing
            {
                var st = string.IsNullOrEmpty(PlaytestMarkerBridge.TranscriptStatus) ? "复核文字" : PlaytestMarkerBridge.TranscriptStatus;
                EditorGUILayout.LabelField("📝 " + st, EditorStyles.boldLabel);
            }

            EditorGUILayout.LabelField("⌨ 备注(语音自动回填,可改)", EditorStyles.miniLabel);
            PlaytestMarkerBridge.TypedNote = EditorGUILayout.TextArea(
                PlaytestMarkerBridge.TypedNote ?? "", _noteStyle, GUILayout.Height(84));
        }

        // 主操作:取消 / 推进(标签随阶段变)
        void DrawActions(MarkPhase phase)
        {
            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.backgroundColor = new Color(0.95f, 0.4f, 0.4f);
                if (GUILayout.Button("✗ 取消 (Esc)", GUILayout.Height(34))) PlaytestMarkerBridge.RequestCancel?.Invoke();
                GUI.backgroundColor = new Color(0.3f, 0.85f, 0.55f);
                var advLabel = phase == MarkPhase.Recording ? "■ 停录并转写 (F8)" : "✓ 保存并继续 (F8)";
                if (GUILayout.Button(advLabel, GUILayout.Height(34))) PlaytestMarkerBridge.RequestAdvance?.Invoke();
                GUI.backgroundColor = Color.white;
            }
        }

        // 拖入图片文件 → 新建标注(来源不限:网页另存、参考图、外部截图工具存的文件)
        void DrawDropArea()
        {
            var r = GUILayoutUtility.GetRect(0, 44, GUILayout.ExpandWidth(true));
            GUI.Box(r, "🖱 把截图文件拖到这里新建标注", EditorStyles.helpBox);
            var e = Event.current;
            if ((e.type == EventType.DragUpdated || e.type == EventType.DragPerform) && r.Contains(e.mousePosition))
            {
                DragAndDrop.visualMode = DragAndDropVisualMode.Copy;
                if (e.type == EventType.DragPerform)
                {
                    DragAndDrop.AcceptDrag();
                    foreach (var p in DragAndDrop.paths)
                        if (IsImage(p)) { PlaytestEditorCapture.IngestFromFile(p); break; }
                }
                e.Use();
            }
        }

        static bool IsImage(string p)
        {
            var ext = Path.GetExtension(p ?? "").ToLowerInvariant();
            return ext == ".png" || ext == ".jpg" || ext == ".jpeg" || ext == ".bmp" || ext == ".gif";
        }

        // 一次性配置:截图入口(本机)+ Python / stt_google.py / Google 凭证(EditorPrefs 永久记住)
        void DrawSettings()
        {
            EditorGUILayout.Space(8);
            bool needScript = string.IsNullOrEmpty(PlaytestAsrServer.ScriptPath) || !File.Exists(PlaytestAsrServer.ScriptPath);
            if (needScript)
                EditorGUILayout.HelpBox("Google 转写未配置 → 录音不会自动出字(可照常打字,事后补转)。展开「⚙ 设置」指向 stt_google.py,设一次即可。", MessageType.Warning);

            _showSettings = EditorGUILayout.Foldout(_showSettings || needScript, "⚙ 设置(截图入口 + Google STT · 设一次)", true);
            if (!(_showSettings || needScript)) return;

            using (new EditorGUILayout.VerticalScope(EditorStyles.helpBox))
            {
                EditorGUILayout.LabelField("截图入口(本机)", EditorStyles.miniBoldLabel);
                PlaytestEditorCapture.ScreenshotHint = EditorGUILayout.TextField("截图键(备忘)", PlaytestEditorCapture.ScreenshotHint);
                PlaytestEditorCapture.SnipCommand    = EditorGUILayout.TextField("📸 拉起命令", PlaytestEditorCapture.SnipCommand);

                EditorGUILayout.Space(6);
                EditorGUILayout.LabelField("语音转写(Google STT)", EditorStyles.miniBoldLabel);
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
