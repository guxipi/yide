// 翼德 · Playtest 标注 — 编辑器停靠窗口(放进任意 Editor/ 文件夹)
// 它是独立的 EditorWindow,停靠在 Game 视图旁/下,绝不遮挡游戏画面。
// 冻帧时自动弹出:显示截图缩略 + 自动抓到的命中元素/场景/上下文 + 语音状态 + 打字补充框 + 保存/取消。
#if UNITY_EDITOR
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Yide.Playtest
{
    // 编辑器侧监听:标注一开始(冻帧)就自动弹出窗口。
    // 用轮询而非运行时直接调 Open():运行时程序集不能引用 Editor 程序集的类型。
    [InitializeOnLoad]
    static class PlaytestMarkerAutoOpen
    {
        static bool _wasActive;
        static PlaytestMarkerAutoOpen() { EditorApplication.update += Tick; }
        static void Tick()
        {
            if (PlaytestMarkerBridge.Active && !_wasActive) PlaytestMarkerWindow.Open();
            _wasActive = PlaytestMarkerBridge.Active;
        }
    }

    public class PlaytestMarkerWindow : EditorWindow
    {
        Texture2D _thumb;
        string _loadedShot;

        public static void Open()
        {
            var w = GetWindow<PlaytestMarkerWindow>(false, "翼德 标注", true);
            w.minSize = new Vector2(360, 320);
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
                EditorGUILayout.HelpBox("没有进行中的标注。\n在 Play 模式按 F8 冻帧并开始标注。", MessageType.Info);
                return;
            }
            var m = PlaytestMarkerBridge.Pending;

            EditorGUILayout.Space(6);
            EditorGUILayout.LabelField($"◆ 本场第 {m.index} 条 · 场景 {m.scene}", EditorStyles.boldLabel);

            // 截图缩略
            if (_thumb == null && File.Exists(m.shotPath))
            {
                _loadedShot = m.shotPath;
                var bytes = File.ReadAllBytes(m.shotPath);
                _thumb = new Texture2D(2, 2);
                _thumb.LoadImage(bytes);
            }
            if (_thumb != null)
            {
                float w = EditorGUIUtility.currentViewWidth - 24f;
                float h = Mathf.Min(220f, w * _thumb.height / Mathf.Max(1, _thumb.width));
                var r = GUILayoutUtility.GetRect(w, h);
                GUI.DrawTexture(r, _thumb, ScaleMode.ScaleToFit);
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

            // 语音状态
            EditorGUILayout.Space(4);
            var recOn = Microphone.IsRecording(null);
            EditorGUILayout.LabelField(recOn ? "🎙 正在听…说出这里的问题(语音为主)" : "🎙 未检测到麦克风(可只打字)",
                recOn ? EditorStyles.boldLabel : EditorStyles.miniLabel);

            // 打字补充
            EditorGUILayout.Space(2);
            EditorGUILayout.LabelField("⌨ 打字补充(可选 · 嫌吵/不方便说话时直接打)", EditorStyles.miniLabel);
            PlaytestMarkerBridge.TypedNote = EditorGUILayout.TextArea(
                PlaytestMarkerBridge.TypedNote ?? "", GUILayout.Height(72));

            // 按钮
            EditorGUILayout.Space(8);
            using (new EditorGUILayout.HorizontalScope())
            {
                GUI.backgroundColor = new Color(0.95f, 0.4f, 0.4f);
                if (GUILayout.Button("✗ 取消 (Esc)", GUILayout.Height(34))) PlaytestMarkerBridge.RequestCancel?.Invoke();
                GUI.backgroundColor = new Color(0.3f, 0.85f, 0.55f);
                if (GUILayout.Button("✓ 保存并继续 (F8)", GUILayout.Height(34))) PlaytestMarkerBridge.RequestSave?.Invoke();
                GUI.backgroundColor = Color.white;
            }
            EditorGUILayout.LabelField("F8 冻帧/保存本条 · Esc 取消 · 面板不挡游戏", EditorStyles.centeredGreyMiniLabel);
        }
    }
}
#endif
