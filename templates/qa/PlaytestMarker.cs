// 翼德 · Playtest 冻帧标注工具(运行时)
// 勾哥试玩时按一个键(默认 F8)→ 冻帧 + 截当前帧 + 自动抓"命中的 UI/物体 + 场景 + 分辨率/FPS/版本"
// + 录一小段语音(语音为主)/ 也可在编辑器窗口里打字 → 一键归档成一个 marker 文件夹。
// 之后翼德跑 scripts/playtest.js:本地 SenseVoice 转写语音 + 读截图/上下文 → 出带定位的问题清单。
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
    /// <summary>运行时桥:把"当前待标注"数据暴露给编辑器窗口;窗口把打字内容写回这里。</summary>
    public static class PlaytestMarkerBridge
    {
        public static bool Active;                 // 是否正在标注(已冻帧)
        public static PendingMarker Pending;       // 当前这条
        public static string TypedNote = "";       // 编辑器窗口里打的字(可选)
        public static Action RequestSave;          // 窗口点"保存"回调
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
        [Header("单条语音最长秒数")]
        public int maxClipSeconds = 30;
        [Tooltip("采样率;SenseVoice 用 16k 即可")]
        public int sampleRate = 16000;

        int _count;
        string _sessionDir;
        float _prevTimeScale = 1f;
        AudioClip _clip;
        string _micDevice;
        bool _recording;

        void Awake()
        {
            _sessionDir = Path.Combine(BaseDir(), "QA", "playtest", "session-" + DateTime.Now.ToString("yyyyMMdd-HHmmss"));
            DontDestroyOnLoad(gameObject);
        }

        void Update()
        {
            if (Input.GetKeyDown(markKey))
            {
                if (!PlaytestMarkerBridge.Active) BeginMark();
                else SaveMark();           // 再按一次 = 保存本条(toggle,留出打字时间)
            }
            if (PlaytestMarkerBridge.Active && Input.GetKeyDown(KeyCode.Escape)) CancelMark();
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

            // 开录(语音为主)
            StartMic();

            PlaytestMarkerBridge.Pending = m;
            PlaytestMarkerBridge.TypedNote = "";
            PlaytestMarkerBridge.Active = true;
            PlaytestMarkerBridge.RequestSave = SaveMark;
            PlaytestMarkerBridge.RequestCancel = CancelMark;
            PlaytestMarkerBridge.Changed();   // 编辑器窗口在 Editor 程序集里监听此事件并自动弹出(运行时不能反向引用 Editor 类型)
            Debug.Log($"[翼德] ● 标注 #{_count} 开始:{m.scene} / {m.hitPath}");
        }

        // ── 保存本条:停录 + 写 wav + 写 context.json + 写 note.txt ──
        void SaveMark()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null) return;

            // 语音
            string wavRel = null;
            var samples = StopMic();
            if (samples != null && samples.Length > 0)
            {
                var wavPath = Path.Combine(m.folder, "voice.wav");
                File.WriteAllBytes(wavPath, EncodeWav(samples, 1, sampleRate));
                wavRel = "voice.wav";
            }

            // 打字补充
            var note = (PlaytestMarkerBridge.TypedNote ?? "").Trim();
            if (note.Length > 0) File.WriteAllText(Path.Combine(m.folder, "note.txt"), note, new UTF8Encoding(false));

            // 上下文
            File.WriteAllText(Path.Combine(m.folder, "context.json"), BuildContextJson(m, wavRel, note), new UTF8Encoding(false));

            EndMarkCommon();
            Debug.Log($"[翼德] ✓ 标注 #{m.index} 已存:{m.folder}");
        }

        void CancelMark()
        {
            StopMic();
            var m = PlaytestMarkerBridge.Pending;
            try { if (m != null && Directory.Exists(m.folder)) Directory.Delete(m.folder, true); } catch { }
            EndMarkCommon();
            Debug.Log("[翼德] ✗ 标注已取消");
        }

        void EndMarkCommon()
        {
            Time.timeScale = _prevTimeScale;   // 解冻
            PlaytestMarkerBridge.Active = false;
            PlaytestMarkerBridge.Pending = null;
            PlaytestMarkerBridge.Changed();
        }

        // ── 命中元素:先 UI(EventSystem),再世界物体(Physics) ──
        (string, string) ResolveHit()
        {
            // UI
            if (EventSystem.current != null)
            {
                var ped = new PointerEventData(EventSystem.current) { position = Input.mousePosition };
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
                var ray = cam.ScreenPointToRay(Input.mousePosition);
                if (Physics.Raycast(ray, out var rh, 1000f))
                    return (HierarchyPath(rh.collider.transform), DescribeSource(rh.collider.gameObject));
                // 2D
                var p = cam.ScreenToWorldPoint(Input.mousePosition);
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

        // ── 麦克风 ──
        void StartMic()
        {
            if (Microphone.devices.Length == 0) { Debug.LogWarning("[翼德] 没有麦克风设备,本条只存截图+上下文"); return; }
            _micDevice = Microphone.devices[0];
            _clip = Microphone.Start(_micDevice, false, maxClipSeconds, sampleRate);
            _recording = true;
        }

        float[] StopMic()
        {
            if (!_recording || _clip == null) return null;
            int pos = Microphone.GetPosition(_micDevice);
            Microphone.End(_micDevice);
            _recording = false;
            if (pos <= 0) pos = _clip.samples;
            var data = new float[pos * _clip.channels];
            _clip.GetData(data, 0);
            return data;
        }

        // ── 16-bit PCM WAV 编码(无依赖) ──
        static byte[] EncodeWav(float[] samples, int channels, int rate)
        {
            using (var ms = new MemoryStream())
            using (var bw = new BinaryWriter(ms))
            {
                int dataLen = samples.Length * 2;
                bw.Write(Encoding.ASCII.GetBytes("RIFF")); bw.Write(36 + dataLen);
                bw.Write(Encoding.ASCII.GetBytes("WAVE")); bw.Write(Encoding.ASCII.GetBytes("fmt "));
                bw.Write(16); bw.Write((short)1); bw.Write((short)channels);
                bw.Write(rate); bw.Write(rate * channels * 2); bw.Write((short)(channels * 2)); bw.Write((short)16);
                bw.Write(Encoding.ASCII.GetBytes("data")); bw.Write(dataLen);
                foreach (var s in samples) bw.Write((short)(Mathf.Clamp(s, -1f, 1f) * short.MaxValue));
                return ms.ToArray();
            }
        }

        static string J(string s) => "\"" + (s ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
        static string BuildContextJson(PendingMarker m, string wav, string note)
        {
            string res = m.screenW + "x" + m.screenH;
            var sb = new StringBuilder();
            sb.Append("{\n");
            sb.Append($"  \"index\": {m.index},\n");
            sb.Append($"  \"scene\": {J(m.scene)},\n");
            sb.Append($"  \"hitPath\": {J(m.hitPath)},\n");
            sb.Append($"  \"hitSource\": {J(m.hitSource)},\n");
            sb.Append($"  \"resolution\": {J(res)},\n");
            sb.Append($"  \"fps\": {m.fps},\n");
            sb.Append($"  \"version\": {J(m.version)},\n");
            sb.Append($"  \"timeInGame\": {m.timeInGame.ToString("0.0")},\n");
            sb.Append($"  \"shot\": \"shot.png\",\n");
            sb.Append($"  \"voice\": {(wav == null ? "null" : J(wav))},\n");
            sb.Append($"  \"typedNote\": {J(note)}\n");
            sb.Append("}\n");
            return sb.ToString();
        }

        // 项目根(编辑器=工程根;真机=persistentDataPath)
        static string BaseDir()
        {
#if UNITY_EDITOR
            return Directory.GetParent(Application.dataPath).FullName;
#else
            return Application.persistentDataPath;
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
