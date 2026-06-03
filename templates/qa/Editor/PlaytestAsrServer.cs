// 翼德 · Playtest 标注 — Google STT 转写常驻服务的"编辑器端驱动"(放进任意 Editor/ 文件夹)。
// 它在标注录音一开始就把 integrations/playtest-capture/stt_google.py 拉起来(常驻,省 Python 启动),
// 停录时把 voice.wav 路径喂进去,几秒后拿到中文文字回填到打字框 —— 让勾哥"停说即看字、当场确认"。
// 转写走 Google Cloud Speech-to-Text(Chirp 3 · v2),认证用 service account JSON。纯编辑器代码,#if UNITY_EDITOR 包住,绝不进包。
#if UNITY_EDITOR
using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace Yide.Playtest
{
    static class PlaytestAsrServer
    {
        public enum State { Off, Starting, Ready, Failed }
        public static State Status { get; private set; } = State.Off;
        public static string LastError { get; private set; } = "";

        // 配置存 EditorPrefs(设一次永久记住),默认从环境变量种子。
        const string KPy = "Yide.Playtest.Python";
        const string KScript = "Yide.Playtest.AsrScript";
        const string KCred = "Yide.Playtest.GcpCredential";
        const string KRegion = "Yide.Playtest.GcpRegion";

        public static string PythonPath
        {
            get => EditorPrefs.GetString(KPy, EnvOr("YIDE_PYTHON", "python"));
            set => EditorPrefs.SetString(KPy, value);
        }
        public static string ScriptPath
        {
            get => EditorPrefs.GetString(KScript, EnvOr("YIDE_ASR_SCRIPT", ""));
            set => EditorPrefs.SetString(KScript, value);
        }
        // Google service account JSON(留空则用进程已有的 GOOGLE_APPLICATION_CREDENTIALS 环境变量)
        public static string CredentialPath
        {
            get => EditorPrefs.GetString(KCred, EnvOr("GOOGLE_APPLICATION_CREDENTIALS", ""));
            set => EditorPrefs.SetString(KCred, value);
        }
        public static string Region
        {
            get => EditorPrefs.GetString(KRegion, EnvOr("YIDE_GCP_LOCATION", "us"));
            set => EditorPrefs.SetString(KRegion, value);
        }
        static string EnvOr(string key, string fallback)
        {
            var v = Environment.GetEnvironmentVariable(key);
            return string.IsNullOrEmpty(v) ? fallback : v;
        }

        public struct Result { public string wav; public string text; public string error; }

        static Process _proc;
        static readonly ConcurrentQueue<string> _stdout = new ConcurrentQueue<string>();
        static readonly ConcurrentQueue<string> _stderr = new ConcurrentQueue<string>();
        static string _pending;   // 还没发出去的 wav(等服务 ready)

        // 拉起服务并预热(可重复调,已起则忽略)。返回 false=配置不全没法起。
        public static bool EnsureStarted()
        {
            if (_proc != null && !_proc.HasExited) return true;
            if (Status == State.Starting) return true;

            var py = PythonPath;
            var script = ScriptPath;
            if (string.IsNullOrEmpty(script) || !File.Exists(script))
            {
                Status = State.Failed;
                LastError = "未配置 stt_google.py 路径(展开下方「⚙ 转写设置」设一次)";
                return false;
            }
            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = py,
                    Arguments = "\"" + script + "\"",
                    UseShellExecute = false,
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = System.Text.Encoding.UTF8,
                    StandardErrorEncoding = System.Text.Encoding.UTF8,
                    CreateNoWindow = true,
                    WorkingDirectory = Path.GetDirectoryName(script),
                };
                if (!string.IsNullOrEmpty(CredentialPath))
                    psi.EnvironmentVariables["GOOGLE_APPLICATION_CREDENTIALS"] = CredentialPath;
                if (!string.IsNullOrEmpty(Region))
                    psi.EnvironmentVariables["YIDE_GCP_LOCATION"] = Region;
                psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                _proc = new Process { StartInfo = psi, EnableRaisingEvents = true };
                _proc.OutputDataReceived += (s, e) => { if (e.Data != null) _stdout.Enqueue(e.Data); };
                _proc.ErrorDataReceived += (s, e) => { if (e.Data != null) _stderr.Enqueue(e.Data); };
                _proc.Start();
                _proc.BeginOutputReadLine();
                _proc.BeginErrorReadLine();
                Status = State.Starting;
                LastError = "";
                return true;
            }
            catch (Exception ex)
            {
                Status = State.Failed;
                LastError = "启动失败:" + ex.Message;
                return false;
            }
        }

        // 提交一条 wav 去转写(服务没 ready 就先存着,ready 后自动发)。
        public static void Submit(string wavPath)
        {
            if (string.IsNullOrEmpty(wavPath)) return;
            if (_proc == null || _proc.HasExited) EnsureStarted();
            _pending = wavPath;
            TryFlushPending();
        }

        static void TryFlushPending()
        {
            if (_pending == null || Status != State.Ready || _proc == null || _proc.HasExited) return;
            try
            {
                _proc.StandardInput.WriteLine(_pending);
                _proc.StandardInput.Flush();
                _pending = null;
            }
            catch (Exception ex) { Status = State.Failed; LastError = "写入失败:" + ex.Message; }
        }

        // 编辑器每帧调:消化服务输出。got=true 表示本帧拿到一条转写结果。
        public static bool Poll(out Result result)
        {
            result = default;
            bool got = false;
            while (_stdout.TryDequeue(out var line))
            {
                line = (line ?? "").Trim();
                if (line.Length == 0) continue;
                if (line == "__READY__") { Status = State.Ready; TryFlushPending(); continue; }
                result = ParseResult(line);
                got = true;
            }
            while (_stderr.TryDequeue(out var eline))
            {
                eline = (eline ?? "").Trim();
                if (eline.Length == 0) continue;
                LastError = ExtractError(eline);
                Status = State.Failed;
            }
            if (_proc != null && _proc.HasExited && Status != State.Off && Status != State.Failed)
            {
                Status = State.Failed;
                if (string.IsNullOrEmpty(LastError)) LastError = "转写进程已退出(exit " + SafeExitCode() + ")";
            }
            return got;
        }

        static int SafeExitCode() { try { return _proc.ExitCode; } catch { return -1; } }

        public static void Stop()
        {
            try
            {
                if (_proc != null && !_proc.HasExited)
                {
                    try { _proc.StandardInput.Close(); } catch { }
                    _proc.Kill();
                }
            }
            catch { }
            _proc = null;
            _pending = null;
            Status = State.Off;
            LastError = "";
            while (_stdout.TryDequeue(out _)) { }
            while (_stderr.TryDequeue(out _)) { }
        }

        [Serializable] class Resp { public string wav; public string text; public string error; }
        static Result ParseResult(string line)
        {
            try
            {
                var r = JsonUtility.FromJson<Resp>(line);
                return new Result { wav = r != null ? r.wav : null, text = r != null ? r.text : "", error = r != null ? r.error : null };
            }
            catch { return new Result { error = "结果解析失败" }; }
        }
        static string ExtractError(string line)
        {
            try { var r = JsonUtility.FromJson<Resp>(line); if (r != null && !string.IsNullOrEmpty(r.error)) return r.error; }
            catch { }
            return line.Length > 160 ? line.Substring(0, 160) : line;
        }
    }

    // 生命周期:重编译 / 退编辑器 / 退出 Play 都把服务进程杀掉,避免留孤儿进程。
    [InitializeOnLoad]
    static class PlaytestAsrServerLifecycle
    {
        static PlaytestAsrServerLifecycle()
        {
            AssemblyReloadEvents.beforeAssemblyReload += PlaytestAsrServer.Stop;
            EditorApplication.quitting += PlaytestAsrServer.Stop;
            EditorApplication.playModeStateChanged += s =>
            {
                if (s == PlayModeStateChange.ExitingPlayMode) PlaytestAsrServer.Stop();
            };
        }
    }
}
#endif
