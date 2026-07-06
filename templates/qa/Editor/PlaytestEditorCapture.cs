// 翼德 · Playtest 标注 — 编辑器侧捕获入口(放进任意 Editor/ 文件夹)。
// 把"截图来源"扩到运行时之外,但复用同一套核心(PlaytestMarkerBridge + ASR + 标注窗口 + context.json schema):
//   ① 编辑器内(非 Play)按 F8 → 截当前 Unity 窗口;
//   ② 📋 从剪贴板粘贴新建(系统截图进剪贴板即可,不依赖任何特定快捷键);
//   ③ 🖱 把图片文件拖进标注窗口;
//   ④ 📸 让 Unity 替你拉起系统区域截图(命令本机私有,存 EditorPref)。
// 截图/读剪贴板走 PowerShell(System.Drawing / Windows.Forms),与现有"shell 给 Python 跑 ASR"同套路,避开 Unity 不稳的 clipboard API。Windows 专用。
#if UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using System.Text;
using UnityEditor;
using UnityEditor.ShortcutManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace Yide.Playtest
{
    // 编辑器侧标注的驱动:建 marker 文件夹 + 喂 Bridge + 接管 Advance/Cancel。
    // 与运行时 PlaytestMarker 共用 Bridge / context.json schema / ASR / 标注窗口;只换"截图来源"和"上下文"。
    static class PlaytestEditorCapture
    {
        static int _count;
        static string _sessionDir;

        // ── 本机私有配置(EditorPrefs,跟 SessionRoot / Python 路径同规矩,换机器只改这里)──
        const string KSnip = "Yide.Playtest.SnipCommand";
        const string KHint = "Yide.Playtest.ScreenshotHint";
        // 拉起系统区域截图的命令;默认 Win11 Snip & Sketch 的区域截图 URI。
        public static string SnipCommand
        {
            get => EditorPrefs.GetString(KSnip, "ms-screenclip:");
            set => EditorPrefs.SetString(KSnip, value);
        }
        // 纯展示提示:本机用什么键截图(剪贴板入口本身不依赖它,只是给人看的备忘)。
        public static string ScreenshotHint
        {
            get => EditorPrefs.GetString(KHint, "Win + Shift + S");
            set => EditorPrefs.SetString(KHint, value);
        }

        public static string LastError { get; private set; } = "";

        // ── ① 编辑器内 F8(非 Play):截当前 Unity 窗口标注 ──
        // Play 模式交给运行时 PlaytestMarker(它走冻帧 + 指针命中);此处只管编辑器态。
        [Shortcut("Yide/Playtest Mark (edit mode)", KeyCode.F8)]
        static void MarkHotkey()
        {
            if (EditorApplication.isPlaying) return;                 // 运行时那条链负责 Play 模式
            if (PlaytestMarkerBridge.Active) { PlaytestMarkerBridge.RequestAdvance?.Invoke(); return; } // 进行中→推进
            BeginFromWindowCapture();
        }

        static void BeginFromWindowCapture()
        {
            var folder = NewMarkerFolder(out var idx);
            var shot = Path.Combine(folder, "shot.png");
            bool ok = CaptureWindow(shot);
            if (!ok) Debug.LogWarning("[翼德] 编辑器截窗失败(" + LastError + ")— 仍建标注,可拖图/粘贴补图。");

            string hitPath = "(编辑器窗口标注)";
            string hitSource = "";
            var sel = Selection.activeGameObject;
            if (sel != null) { hitPath = HierarchyPath(sel.transform); hitSource = DescribeSelection(sel); }

            BeginMarker(MakeMarker(idx, folder, shot, hitPath, hitSource));
        }

        // ── ② 📋 从剪贴板粘贴新建 ──
        public static void IngestFromClipboard()
        {
            if (PlaytestMarkerBridge.Active) return;
            var folder = NewMarkerFolder(out var idx);
            var shot = Path.Combine(folder, "shot.png");
            if (!CaptureClipboard(shot, out var status))
            {
                AbandonFolder(folder);
                EditorUtility.DisplayDialog("翼德 标注", status, "知道了");
                return;
            }
            BeginMarker(MakeMarker(idx, folder, shot, "(剪贴板图片)", ""));
        }

        // ── ③ 🖱 拖入图片文件 ──
        public static void IngestFromFile(string filePath)
        {
            if (PlaytestMarkerBridge.Active || string.IsNullOrEmpty(filePath) || !File.Exists(filePath)) return;
            var folder = NewMarkerFolder(out var idx);
            var shot = Path.Combine(folder, "shot.png");   // 统一存 shot.png(Texture2D.LoadImage 按字节识别格式,扩展名无所谓)
            try { File.Copy(filePath, shot, true); }
            catch (Exception e) { AbandonFolder(folder); EditorUtility.DisplayDialog("翼德 标注", "复制图片失败:" + e.Message, "知道了"); return; }
            BeginMarker(MakeMarker(idx, folder, shot, "(拖入图片) " + Path.GetFileName(filePath), ""));
        }

        // ── ④ 📸 让 Unity 拉起系统区域截图(截完进剪贴板,再点「📋 粘贴新建」)──
        public static void LaunchSnip()
        {
            try { Process.Start(new ProcessStartInfo { FileName = SnipCommand, UseShellExecute = true }); }
            catch (Exception e) { EditorUtility.DisplayDialog("翼德 标注", "拉起截图工具失败:" + e.Message + "\n当前命令:" + SnipCommand, "知道了"); }
        }

        // ── 对"进行中那条标注"的截图做增删改(来源无关,运行时/编辑器 marker 通用)──
        // Delete 键删掉当前截图;再点「粘贴截图」把剪贴板的图贴回这条标注(替换 shot.png)。
        public static void DeleteShot()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null || string.IsNullOrEmpty(m.shotPath)) return;
            try { if (File.Exists(m.shotPath)) File.Delete(m.shotPath); }
            catch (Exception e) { Debug.LogWarning("[翼德] 删截图失败:" + e.Message); return; }
            m.screenW = 0; m.screenH = 0;
            PlaytestMarkerBridge.Changed();   // 触发标注窗口重载缩略图(置空 _thumb)
            Debug.Log("[翼德] 截图已删除:" + m.shotPath);
        }

        public static void PasteShotFromClipboard()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null || string.IsNullOrEmpty(m.shotPath)) return;
            if (!CaptureClipboard(m.shotPath, out var status))
            {
                EditorUtility.DisplayDialog("翼德 标注", status, "知道了");
                return;
            }
            ReadImageSize(m.shotPath, out var w, out var h);
            m.screenW = w; m.screenH = h;
            PlaytestMarkerBridge.Changed();
            Debug.Log("[翼德] 截图已用剪贴板替换:" + m.shotPath);
        }

        // ── 标注生命周期(编辑器侧;不冻帧、不解析运行时命中)──
        static void BeginMarker(PendingMarker m)
        {
            PlaytestMarkerBridge.Pending = m;
            PlaytestMarkerBridge.TypedNote = "";
            PlaytestMarkerBridge.VoiceWavPath = Path.Combine(m.folder, "voice.wav");
            PlaytestMarkerBridge.TranscriptStatus = "";
            PlaytestMarkerBridge.Phase = MarkPhase.Recording;   // 走录音段:ASR 由 PlaytestMarkerAutoOpen.Tick 统一接管(与来源无关)
            PlaytestMarkerBridge.Active = true;
            PlaytestMarkerBridge.RequestAdvance = EditorAdvance;
            PlaytestMarkerBridge.RequestCancel = EditorCancel;
            PlaytestMarkerBridge.Changed();
            Debug.Log($"[翼德] ● 编辑器标注 #{m.index} 开始:{m.scene} / {m.hitPath}");
        }

        static void EditorAdvance()
        {
            switch (PlaytestMarkerBridge.Phase)
            {
                case MarkPhase.Recording: EditorStopRecord(); break;
                case MarkPhase.Reviewing: EditorSave();       break;
            }
        }

        static void EditorStopRecord()
        {
            PlaytestMarkerBridge.TranscriptStatus = "转写收尾…";
            PlaytestMarkerBridge.Phase = MarkPhase.Reviewing;
            PlaytestMarkerBridge.Changed();
        }

        static void EditorSave()
        {
            var m = PlaytestMarkerBridge.Pending;
            if (m == null) return;
            string wavRel = (PlaytestMarkerBridge.VoiceWavPath != null
                             && File.Exists(PlaytestMarkerBridge.VoiceWavPath)) ? "voice.wav" : null;
            var note = (PlaytestMarkerBridge.TypedNote ?? "").Trim();
            if (note.Length > 0) File.WriteAllText(Path.Combine(m.folder, "note.txt"), note, new UTF8Encoding(false));
            File.WriteAllText(Path.Combine(m.folder, "context.json"),
                PlaytestMarker.BuildContextJson(m, wavRel, note), new UTF8Encoding(false));   // 单一 schema 来源
            Debug.Log($"[翼德] ✓ 编辑器标注 #{m.index} 已存:{m.folder}");
            EditorEnd();
        }

        static void EditorCancel()
        {
            var m = PlaytestMarkerBridge.Pending;
            try { if (m != null && Directory.Exists(m.folder)) Directory.Delete(m.folder, true); } catch { }
            Debug.Log("[翼德] ✗ 编辑器标注已取消");
            EditorEnd();
        }

        static void EditorEnd()
        {
            PlaytestMarkerBridge.Active = false;
            PlaytestMarkerBridge.Phase = MarkPhase.Idle;
            PlaytestMarkerBridge.Pending = null;
            PlaytestMarkerBridge.VoiceWavPath = null;
            PlaytestMarkerBridge.TranscriptStatus = "";
            PlaytestMarkerBridge.Changed();
        }

        // ── 文件夹 / 上下文 ──
        static string NewMarkerFolder(out int idx)
        {
            if (string.IsNullOrEmpty(_sessionDir) || !Directory.Exists(_sessionDir))
            {
                _sessionDir = Path.Combine(PlaytestMarker.SessionRoot(),
                    "session-" + DateTime.Now.ToString("yyyyMMdd-HHmmss") + "-editor");
                _count = 0;
            }
            idx = ++_count;
            var folder = Path.Combine(_sessionDir, PlaytestMarker.MarkerFolderName(idx));
            Directory.CreateDirectory(folder);
            return folder;
        }

        static void AbandonFolder(string folder)
        {
            try { if (Directory.Exists(folder)) Directory.Delete(folder, true); } catch { }
            _count--;   // 回收序号,避免空洞
        }

        // 读 PNG/图片像素尺寸(Texture2D.LoadImage 按字节识别格式)
        static void ReadImageSize(string path, out int w, out int h)
        {
            w = 0; h = 0;
            try
            {
                if (File.Exists(path))
                {
                    var t = new Texture2D(2, 2);
                    if (t.LoadImage(File.ReadAllBytes(path))) { w = t.width; h = t.height; }
                    UnityEngine.Object.DestroyImmediate(t);
                }
            }
            catch { }
        }

        static PendingMarker MakeMarker(int idx, string folder, string shot, string hitPath, string hitSource)
        {
            ReadImageSize(shot, out var w, out var h);
            return new PendingMarker
            {
                index = idx,
                scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
                hitPath = hitPath,
                hitSource = hitSource,
                screenW = w,
                screenH = h,
                fps = 0,
                version = Application.version,
                timeInGame = 0f,
                folder = folder,
                shotPath = shot,
            };
        }

        static string HierarchyPath(Transform t)
        {
            var sb = new StringBuilder(t.name);
            for (var p = t.parent; p != null; p = p.parent) sb.Insert(0, p.name + "/");
            return sb.ToString();
        }

        static string DescribeSelection(GameObject go)
        {
            var names = new System.Collections.Generic.List<string>();
            foreach (var c in go.GetComponents<Component>())
                if (c != null && !(c is Transform)) names.Add(c.GetType().Name);
            string src = string.Join("+", names);
            var root = PrefabUtility.GetCorrespondingObjectFromSource(go);
            if (root != null)
            {
                var path = AssetDatabase.GetAssetPath(root);
                if (!string.IsNullOrEmpty(path)) src = Path.GetFileName(path) + " · " + src;
            }
            return src;
        }

        // ── PowerShell 捕获(Windows)──
        static bool CaptureWindow(string outPath)
        {
            try
            {
                long hwnd = Process.GetCurrentProcess().MainWindowHandle.ToInt64();
                if (hwnd == 0) { LastError = "拿不到 Unity 主窗口句柄"; return false; }
                var r = RunPs("yide_capwin.ps1", PS_CAPWIN, hwnd + " \"" + outPath + "\"");
                return r.EndsWith("OK") && File.Exists(outPath);
            }
            catch (Exception e) { LastError = e.Message; return false; }
        }

        static bool CaptureClipboard(string outPath, out string status)
        {
            status = "";
            try
            {
                var r = RunPs("yide_clip.ps1", PS_CLIP, "\"" + outPath + "\"");
                if (r.EndsWith("OK") && File.Exists(outPath)) return true;
                status = r.Contains("EMPTY")
                    ? "剪贴板里没有图片 —— 先用系统截图(本机:" + ScreenshotHint + ")截一张,或点「📸 截图」。"
                    : ("读剪贴板失败:" + (string.IsNullOrEmpty(LastError) ? r : LastError));
                return false;
            }
            catch (Exception e) { status = e.Message; return false; }
        }

        static string RunPs(string scriptName, string psContent, string args, int timeoutMs = 15000)
        {
            LastError = "";
            var path = Path.Combine(Path.GetTempPath(), scriptName);
            File.WriteAllText(path, psContent, new UTF8Encoding(false));
            var psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -STA -File \"" + path + "\" " + args,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
            };
            using (var p = Process.Start(psi))
            {
                string outp = p.StandardOutput.ReadToEnd();
                string err = p.StandardError.ReadToEnd();
                p.WaitForExit(timeoutMs);
                if (!string.IsNullOrEmpty(err)) LastError = err.Trim();
                return (outp ?? "").Trim();
            }
        }

        // 截当前 Unity 主窗口(按句柄取 rect,避免 powershell 抢前台导致截错窗)
        const string PS_CAPWIN =
            "param([long]$hwnd,[string]$out)\n" +
            "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public class W{[DllImport(\"user32.dll\")]public static extern bool GetWindowRect(IntPtr h,out RC r);[StructLayout(LayoutKind.Sequential)]public struct RC{public int Left;public int Top;public int Right;public int Bottom;}}'\n" +
            "Add-Type -AssemblyName System.Drawing\n" +
            "$r = New-Object W+RC\n" +
            "[void][W]::GetWindowRect([IntPtr]$hwnd,[ref]$r)\n" +
            "$w = $r.Right - $r.Left\n" +
            "$h = $r.Bottom - $r.Top\n" +
            "if ($w -le 0 -or $h -le 0) { Write-Error 'bad-rect'; exit 1 }\n" +
            "$bmp = New-Object System.Drawing.Bitmap $w,$h\n" +
            "$g = [System.Drawing.Graphics]::FromImage($bmp)\n" +
            "$sz = New-Object System.Drawing.Size $w,$h\n" +
            "$g.CopyFromScreen($r.Left,$r.Top,0,0,$sz)\n" +
            "$bmp.Save($out,[System.Drawing.Imaging.ImageFormat]::Png)\n" +
            "$g.Dispose()\n" +
            "$bmp.Dispose()\n" +
            "Write-Output 'OK'\n";

        const string PS_CLIP =
            "param([string]$out)\n" +
            "Add-Type -AssemblyName System.Windows.Forms\n" +
            "Add-Type -AssemblyName System.Drawing\n" +
            "$img = [System.Windows.Forms.Clipboard]::GetImage()\n" +
            "if ($img -eq $null) { Write-Output 'EMPTY'; exit 0 }\n" +
            "$img.Save($out,[System.Drawing.Imaging.ImageFormat]::Png)\n" +
            "Write-Output 'OK'\n";
    }
}
#endif
