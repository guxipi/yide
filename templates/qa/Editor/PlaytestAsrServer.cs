// 翼德 · Playtest 标注 — Google STT 实时流式转写的"编辑器端驱动"(放进任意 Editor/ 文件夹)。
// 标注一开始就把 stt_google.py 拉起来(常驻,省 Python 启动);F8 冻帧时发 START(让 Python 持麦+流式转写),
// 边说边把 interim 文字回填打字框;再按 F8 发 STOP,Python 收尾、落 voice.wav、回最终全文。
// 转写走 Google Cloud Speech-to-Text(Chirp 3 · v2 StreamingRecognize)。认证默认用 gcloud ADC,也支持 service account JSON。
// 纯编辑器代码,#if UNITY_EDITOR 包住,绝不进包。
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
        // Google service account JSON;留空则走 gcloud ADC(推荐)或进程已有的 GOOGLE_APPLICATION_CREDENTIALS。
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

        // type: interim(边说边更新)/ final(一段定稿)/ done(STOP 后,wav 已写)/ error
        // auto: done 时为 true 表示是"静音自动停"(非用户按停录)
        public struct Result { public string type; public string text; public string wav; public string error; public bool auto; }

        static Process _proc;
        static readonly ConcurrentQueue<string> _stdout = new ConcurrentQueue<string>();
        static readonly ConcurrentQueue<string> _stderr = new ConcurrentQueue<string>();
        static string _pendingStartWav;   // 还没发出去的 START(等服务 ready)

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

        // 冻帧开始:让 Python 持麦 + 流式转写,整段音频存到 wavPath。服务没 ready 就先存着,ready 后自动发。
        public static void BeginStream(string wavPath)
        {
            if (string.IsNullOrEmpty(wavPath)) return;
            if (_proc == null || _proc.HasExited) EnsureStarted();
            _pendingStartWav = wavPath;
            TryFlushStart();
        }

        // 停录:让 Python 收尾、落 wav、回最终全文。
        public static void EndStream()
        {
            _pendingStartWav = null;
            if (_proc == null || _proc.HasExited || Status != State.Ready) return;
            try { _proc.StandardInput.WriteLine("STOP"); _proc.StandardInput.Flush(); }
            catch (Exception ex) { Status = State.Failed; LastError = "写入失败:" + ex.Message; }
        }

        static void TryFlushStart()
        {
            if (_pendingStartWav == null || Status != State.Ready || _proc == null || _proc.HasExited) return;
            try
            {
                _proc.StandardInput.WriteLine("START\t" + _pendingStartWav);
                _proc.StandardInput.Flush();
                _pendingStartWav = null;
            }
            catch (Exception ex) { Status = State.Failed; LastError = "写入失败:" + ex.Message; }
        }

        // 编辑器每帧调:消化服务输出。got=true 表示本帧拿到一条结果(interim/final/done/error)。
        public static bool Poll(out Result result)
        {
            result = default;
            bool got = false;
            while (_stdout.TryDequeue(out var line))
            {
                line = (line ?? "").Trim();
                if (line.Length == 0) continue;
                if (line == "__READY__") { Status = State.Ready; TryFlushStart(); continue; }
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
                    try { _proc.StandardInput.WriteLine("QUIT"); _proc.StandardInput.Flush(); } catch { }
                    try { _proc.StandardInput.Close(); } catch { }
                    if (!_proc.WaitForExit(400)) _proc.Kill();
                }
            }
            catch { }
            _proc = null;
            _pendingStartWav = null;
            Status = State.Off;
            LastError = "";
            while (_stdout.TryDequeue(out _)) { }
            while (_stderr.TryDequeue(out _)) { }
        }

        [Serializable] class Resp { public string type; public string wav; public string text; public string error; public bool auto; }
        static Result ParseResult(string line)
        {
            try
            {
                var r = JsonUtility.FromJson<Resp>(line);
                if (r == null) return new Result { error = "结果解析失败" };
                return new Result { type = r.type, text = r.text ?? "", wav = r.wav, error = r.error, auto = r.auto };
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
