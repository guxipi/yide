// 翼德 · Playtest 冻帧标注工具(运行时)
// 勾哥试玩时按一个键(默认 F8)→ 冻帧 + 截当前帧 + 自动抓"命中的 UI/物体 + 场景 + 分辨率/FPS/版本"
// + 实时语音转写(编辑器侧由 Python 持麦走 Google STT,边说边出字)/ 也可打字 → 一键归档成一个 marker 文件夹。
// 之后翼德跑 scripts/playtest.js:Google STT 补转未确认的语音 + 读截图/上下文 → 出带定位的问题清单。
//
// 放置:把本文件放进项目任意 Scripts 目录;再把 Editor/PlaytestMarkerWindow.cs 放进一个 Editor/ 文件夹。
// 用法:场景里随便挂一个空物体加本组件(或让它在 RuntimeInitializeOnLoad 自动生成,见底部)。
// 安全:整体用 #if 包住,只在编辑器 / Development Build 编译,绝不进正式上线包(省性能、避隐私)。
#if UNITY_EDITOR || DEVELOPMENT_BUILD
using System;
using System.IO;
using System.Text;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.EventSystems;
#if UNITY_EDITOR
using UnityEditor;
#endif

namespace Yide.Playtest
{
    // 标注三阶段:Idle 空闲 → Recording 冻帧录音中 → Reviewing 已停录、转写/复核中。
    public enum MarkPhase { Idle = 0, Recording = 1, Reviewing = 2 }

    /// <summary>运行时桥:把"当前待标注"数据暴露给编辑器窗口;窗口把转写/打字内容写回这里。</summary>
    public static class PlaytestMarkerBridge
    {
        public static bool Active;                 // 是否正在标注(Phase != Idle)
        public static MarkPhase Phase;             // 当前阶段
        public static PendingMarker Pending;       // 当前这条
        public static string TypedNote = "";       // 框里的文字(转写自动填入 + 勾哥可改)

        // 转写(编辑器侧消费):冻帧时运行时把目标 wav 路径递过来,编辑器驱动 Python 持麦流式转写。
        public static string VoiceWavPath;         // 本条 voice.wav 的目标绝对路径(Python 写入)
        public static string TranscriptStatus = "";// 编辑器写回的状态:"🎙 听写中…"/"✓ 已转写"/"转写失败:…"

        public static Action RequestAdvance;       // 窗口绿钮 / F8:推进到下一阶段
        public static Action RequestCancel;        // 窗口点"取消"回调
        public static event Action OnChanged;      // 数据变了通知窗口刷新
        public static void Changed() { OnChanged?.Invoke(); }
    }

    [Serializable]
    public class PendingMarker
    {
        public int index;
        public string scene;
        public string hitPath;        // 命中元素层级路径
        public string hitSource;      // 来源 Prefab / 组件
        public int screenW, screenH;
        public int fps;
        public string version;
        public float timeInGame;
        public string shotPath;       // 截图文件
        public string folder;         // 本条 marker 目录
    }

    public class PlaytestMarker : MonoBehaviour
    {
        [Header("标注键(默认 F8;空格常被游戏占用,别用)")]
        public KeyCode markKey = KeyCode.F8;

        int _count;
        string _sessionDir;
        float _prevTimeScale = 1f;

        void Awake()
        {
            _sessionDir = Path.Combine(SessionRoot(), "session-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
            DontDestroyOnLoad(gameObject);
        }

        void Update()
        {
            if (KeyDown(markKey)) Advance();
            if (PlaytestMarkerBridge.Active && KeyDown(KeyCode.Escape)) CancelMark();
        }

        // F8 / 绿钮:按当前阶段推进。①Idle→开始 ②Recording→停录(触发转写) ③Reviewing→保存。
        void Advance()
        {
            switch (PlaytestMarkerBridge.Phase)
            {
                case MarkPhase.Idle:      BeginMark();  break;
                case MarkPhase.Recording: StopRecord(); break;   // 停录,留出转写+复核时间
                case MarkPhase.Reviewing: SaveMark();   break;
            }
        }

        // ── 输入:同时兼容 新 / 旧 / Both 输入系统(Unity 按 Active Input Handling 自动定义这两个宏)──
        // 默认键 F8、Escape 的名字在新旧两套里一致,可直接映射;换成别的键时优先用 F 系列/Escape。
        static bool KeyDown(KeyCode key)
        {
#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.GetKeyDown(key);
#elif ENABLE_INPUT_SYSTEM
            var kb = UnityEngine.InputSystem.Keyboard.current;
            if (kb == null) return false;
            if (System.Enum.TryParse<UnityEngine.InputSystem.Key>(key.ToString(), out var k))
                return kb[k].wasPressedThisFrame;
            return false;
#else
            return false;
#endif
        }

        static Vector3 PointerPos()
        {
#if ENABLE_LEGACY_INPUT_MANAGER
            return Input.mousePosition;
#elif ENABLE_INPUT_SYSTEM
            var m = UnityEngine.InputSystem.Mouse.current;
            if (m != null) return m.position.ReadValue();
            var t = UnityEngine.InputSystem.Touchscreen.current;
            if (t != null) return t.primaryTouch.position.ReadValue();
            return new Vector3(Screen.width / 2f, Screen.height / 2f, 0f);
#else
            return new Vector3(Screen.width / 2f, Screen.height / 2f, 0f);
#endif
        }

        // ── 开始标注:冻帧 + 截图 + 抓上下文 + 开录 ──
        void BeginMark()
        {
            _count++;
            var m = new PendingMarker { index = _count };
            m.scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
            m.screenW = Screen.width; m.screenH = Screen.height;
            m.fps = Mathf.RoundToInt(1f / Mathf.Max(0.0001f, Time.unscaledDeltaTime));
            m.version = Application.version;
            m.timeInGame = Time.time;

            var hit = ResolveHit();
            m.hitPath = hit.Item1; m.hitSource = hit.Item2;

            m.folder = Path.Combine(_sessionDir, "marker-" + _count.ToString("00"));
            Directory.CreateDirectory(m.folder);
            m.shotPath = Path.Combine(m.folder, "shot.png");
            ScreenCapture.CaptureScreenshot(m.shotPath);  // 下一帧落盘(已冻帧,无妨)

            // 冻帧
            _prevTimeScale = Time.timeScale;
            Time.timeScale = 0f;

            // 语音:不在 Unity 录;编辑器侧让 Python 持麦+流式转写,整段音频存到这个 wav。
            PlaytestMarkerBridge.Pending = m;
            PlaytestMarkerBridge.TypedNote = "";
            PlaytestMarkerBridge.VoiceWavPath = Path.Combine(m.folder, "voice.wav");
            PlaytestMarkerBridge.TranscriptStatus = "";
            PlaytestMarkerBridge.Phase = MarkPhase.Recording;
            PlaytestMarkerBridge.Active = true;
            PlaytestMarkerBridge.RequestAdvance = Advance;
            PlaytestMarkerBridge.RequestCancel = CancelMark;
            PlaytestMarkerBridge.Changed();   // 编辑器窗口在 Editor 程序集里监听此事件并自动弹出(运行时不能反向引用 Editor 类型)
            Debug.Log($"[翼德] ● 标注 #{_count} 开始录音:{m.scene} / {m.hitPath}");
        }

        // ── 第②步:停录 + 写 wav → 让编辑器侧去转写填框(此时仍冻帧,留足复核时间)──
        void StopRecord()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null) return;

            // 停录:编辑器侧发 STOP 给 Python 收尾、落 wav、回最终全文(此时仍冻帧,留足复核时间)。
            PlaytestMarkerBridge.TranscriptStatus = "转写收尾…";
            PlaytestMarkerBridge.Phase = MarkPhase.Reviewing;
            PlaytestMarkerBridge.Changed();
            Debug.Log($"[翼德] ■ 标注 #{m.index} 停录,转写收尾…(确认文字后再按 F8 保存)");
        }

        // ── 第③步:保存本条(wav 已在停录时写好)→ 写 note.txt(转写+改) + context.json ──
        void SaveMark()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null) return;

            string wavRel = (PlaytestMarkerBridge.VoiceWavPath != null
                             && File.Exists(PlaytestMarkerBridge.VoiceWavPath)) ? "voice.wav" : null;

            // 框里的文字 = 转写自动填 + 勾哥改;有内容就落 note.txt(它成为人确认过的权威文本)
            var note = (PlaytestMarkerBridge.TypedNote ?? "").Trim();
            if (note.Length > 0) File.WriteAllText(Path.Combine(m.folder, "note.txt"), note, new UTF8Encoding(false));

            File.WriteAllText(Path.Combine(m.folder, "context.json"), BuildContextJson(m, wavRel, note), new UTF8Encoding(false));

            EndMarkCommon();
            Debug.Log($"[翼德] ✓ 标注 #{m.index} 已存:{m.folder}");
        }

        void CancelMark()
        {
            var m = PlaytestMarkerBridge.Pending;
            try { if (m != null && Directory.Exists(m.folder)) Directory.Delete(m.folder, true); } catch { }
            EndMarkCommon();
            Debug.Log("[翼德] ✗ 标注已取消");
        }

        void EndMarkCommon()
        {
            Time.timeScale = _prevTimeScale;   // 解冻
            PlaytestMarkerBridge.Active = false;
            PlaytestMarkerBridge.Phase = MarkPhase.Idle;
            PlaytestMarkerBridge.Pending = null;
            PlaytestMarkerBridge.VoiceWavPath = null;
            PlaytestMarkerBridge.TranscriptStatus = "";
            PlaytestMarkerBridge.Changed();
        }

        // ── 命中元素:先 UI(EventSystem),再世界物体(Physics) ──
        (string, string) ResolveHit()
        {
            var ptr = PointerPos();
            // UI
            if (EventSystem.current != null)
            {
                var ped = new PointerEventData(EventSystem.current) { position = ptr };
                var results = new List<RaycastResult>();
                EventSystem.current.RaycastAll(ped, results);
                if (results.Count > 0)
                {
                    var go = results[0].gameObject;
                    return (HierarchyPath(go.transform), DescribeSource(go));
                }
            }
            // 世界物体(3D)
            var cam = Camera.main;
            if (cam != null)
            {
                var ray = cam.ScreenPointToRay(ptr);
                if (Physics.Raycast(ray, out var rh, 1000f))
                    return (HierarchyPath(rh.collider.transform), DescribeSource(rh.collider.gameObject));
                // 2D
                var p = cam.ScreenToWorldPoint(ptr);
                var c2d = Physics2D.OverlapPoint(p);
                if (c2d != null) return (HierarchyPath(c2d.transform), DescribeSource(c2d.gameObject));
            }
            return ("(指针下无对象)", "");
        }

        static string HierarchyPath(Transform t)
        {
            var sb = new StringBuilder(t.name);
            for (var p = t.parent; p != null; p = p.parent) sb.Insert(0, p.name + "/");
            return sb.ToString();
        }

        static string DescribeSource(GameObject go)
        {
            var comps = go.GetComponents<Component>();
            var names = new List<string>();
            foreach (var c in comps) if (c != null && !(c is Transform)) names.Add(c.GetType().Name);
            string src = string.Join("+", names);
#if UNITY_EDITOR
            var root = PrefabUtility.GetCorrespondingObjectFromSource(go);
            if (root != null)
            {
                var path = AssetDatabase.GetAssetPath(root);
                if (!string.IsNullOrEmpty(path)) src = Path.GetFileName(path) + " · " + src;
            }
#endif
            return src;
        }

        static string J(string s) => "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        static string BuildContextJson(PendingMarker m, string wav, string note)
        {
            string res = m.screenW + "x" + m.screenH;
            string timeStr = m.timeInGame.ToString("0.0");
            string voiceVal = wav == null ? "null" : J(wav);
            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.Append($"  \"index\": {m.index},\n");
            sb.Append($"  \"scene\": {J(m.scene)},\n");
            sb.Append($"  \"hitPath\": {J(m.hitPath)},\n");
            sb.Append($"  \"hitSource\": {J(m.hitSource)},\n");
            sb.Append($"  \"resolution\": {J(res)},\n");
            sb.Append($"  \"fps\": {m.fps},\n");
            sb.Append($"  \"version\": {J(m.version)},\n");
            sb.Append($"  \"timeInGame\": {timeStr},\n");
            sb.Append($"  \"shot\": \"shot.png\",\n");
            sb.Append($"  \"voice\": {voiceVal},\n");
            sb.Append($"  \"project\": {J(ProjectId())},\n");
            sb.Append($"  \"typedNote\": {J(note)}\n");
            sb.Append("}\n");
            return sb.ToString();
        }

        // 来源项目标识(跨项目护栏):工程文件夹名,天然每个 Unity 工程唯一。
        // playtest.js 读到后校验:同一 QA/playtest 里混入别的项目 = SessionRoot 全局键串了,会告警。
        static string ProjectId()
        {
#if UNITY_EDITOR
            try { return new DirectoryInfo(Directory.GetParent(Application.dataPath).FullName).Name; }
            catch { return Application.productName; }
#else
            return Application.productName;
#endif
        }

        // session 根目录:编辑器优先读 EditorPrefs(本机已指到 Google Drive),否则工程内 QA/playtest;真机用 persistentDataPath。
        static string SessionRoot()
        {
#if UNITY_EDITOR
            var custom = UnityEditor.EditorPrefs.GetString("Yide.Playtest.SessionRoot", "");
            if (!string.IsNullOrEmpty(custom)) return custom;
            return Path.Combine(Directory.GetParent(Application.dataPath).FullName, "QA", "playtest");
#else
            return Path.Combine(Application.persistentDataPath, "QA", "playtest");
#endif
        }

        // 懒人:不用手动挂,进 Play 自动生成一个
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void AutoSpawn()
        {
            if (FindObjectOfType<PlaytestMarker>() == null)
                new GameObject("~YidePlaytestMarker").AddComponent<PlaytestMarker>();
        }
    }
}
#endif
