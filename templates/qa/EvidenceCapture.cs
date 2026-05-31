// 翼德 · 游戏内证据捕获(把它挂到一个常驻 GameObject 上)。
// 出 bug 时按热键(默认 F9)打包:运行日志 + 截图 + 设备/构建信息 JSON,
// 全部写到 Application.persistentDataPath/yide-evidence/,方便附进 bug 报告。
// 研究依据:Application.logMessageReceived + ScreenCapture.CaptureScreenshot。
using System;
using System.IO;
using System.Text;
using UnityEngine;

public class EvidenceCapture : MonoBehaviour
{
    [SerializeField] private KeyCode captureKey = KeyCode.F9;
    private string dir;
    private StringBuilder log = new StringBuilder();

    void Awake()
    {
        DontDestroyOnLoad(gameObject);
        dir = Path.Combine(Application.persistentDataPath, "yide-evidence");
        Directory.CreateDirectory(dir);
    }

    void OnEnable()  { Application.logMessageReceived += OnLog; }
    void OnDisable() { Application.logMessageReceived -= OnLog; }

    private void OnLog(string msg, string stack, LogType type)
    {
        log.AppendLine($"[{DateTime.Now:HH:mm:ss}] {type}: {msg}");
        if (type == LogType.Exception || type == LogType.Error) log.AppendLine(stack);
        if (log.Length > 200000) log.Remove(0, 100000); // 防爆,保留近况
    }

    void Update()
    {
        if (Input.GetKeyDown(captureKey)) Capture();
    }

    public void Capture()
    {
        string ts = DateTime.Now.ToString("yyyyMMdd-HHmmss");
        // 1) 日志
        File.WriteAllText(Path.Combine(dir, $"log-{ts}.txt"), log.ToString());
        // 2) 截图
        ScreenCapture.CaptureScreenshot(Path.Combine(dir, $"shot-{ts}.png"));
        // 3) 设备/构建信息
        string info =
            "{\n" +
            $"  \"version\": \"{Application.version}\",\n" +
            $"  \"unity\": \"{Application.unityVersion}\",\n" +
            $"  \"platform\": \"{Application.platform}\",\n" +
            $"  \"device\": \"{SystemInfo.deviceModel}\",\n" +
            $"  \"os\": \"{SystemInfo.operatingSystem}\",\n" +
            $"  \"scene\": \"{UnityEngine.SceneManagement.SceneManager.GetActiveScene().name}\",\n" +
            $"  \"time\": \"{DateTime.Now:o}\"\n" +
            "}";
        File.WriteAllText(Path.Combine(dir, $"info-{ts}.json"), info);
        Debug.Log($"[翼德] 证据已保存到 {dir}(log/shot/info-{ts})");
    }
}
