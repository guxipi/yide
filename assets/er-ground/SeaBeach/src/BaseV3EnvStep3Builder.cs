using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Meta.Base.Config;
using Meta.Base.Core;
using Meta.Base.Data;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

namespace Editor.Setup.BaseV3Env
{
    /// <summary>Explicit generator test states. Not save data: they only pick which static WIP nodes are shown.</summary>
    public enum BaseV3EnvTestState { Online, Test_Center3x3, Test_Cap15x15, Test_Center3x3_BeachRows }

    /// <summary>
    /// Base v3 terrain, Terra D3 step 3b (Library/BaseV3Env/terra_r3/DECISION_D3.md, on top of D2): static shore, sand, water and
    /// T01 forest under <c>BaseV3Env_WIP/Step3_Static</c>. Idempotent: the node is rebuilt, mesh assets are overwritten in place.
    ///
    /// Shore geometry is one curve family. G(u) = grass outline (D3 B / E control points, shape-preserving PCHIP), N(u) = normal
    /// sand width from G to the still-water line (B table W-G; outer values are a Step-3b design start, see report). Everything else
    /// is offset from G along its true normal (s): leaf edge (D3 A point list, s = leaf), flat sand to s0 = N - 0.933, 1.5 m Hermite
    /// descent to H-0.15 (the still-water line H-0.08 falls exactly at s = N), 1:10 bed rounding into the H-1.5 floor.
    /// Cap: G + (12 + c)·q(u), q = 1 - smootherstep((|u|-30)/30) (D3 E), c the smallest lift keeping G >= 30 over |u| <= 30.
    /// </summary>
    public static class BaseV3EnvStep3Builder
    {
        public const string NodeName = "Step3_Static";
        public const string UnderstoryNode = "Understory_SAMPLE_PendingApproval";
        const string OutDir = BaseV3EnvWipBuilder.ArtDir + "/Step3";
        const string KitDir = "Assets/Art/Expedition/JunglePlanet/Generated/J02SurfaceStyleLab/";
        const string PalmDir = "Assets/Art/Expedition/JunglePlanet/Generated/J01FoliageUnits/";
        const string WaterShaderPath = "Assets/Shaders/Lab/LabBaseWater.shader";
        const string SectionJson = "Library/BaseV3Env/step3b_sections.json";

        public const float DescentLength = 1.5f, DescentDrop = 0.15f, BedSlope = 0.1f, BedFloorDrop = 1.5f, WaterDrop = 0.08f;
        public const float OnlineEdgeV = 18f, CapEdgeV = 30f, Coverage = 130f, LeafHalf = 60f;
        const float MinExposedSand = 2.4f;
        /// <summary>D4 C: base-only vertex colour gains (linear) solved on the real base camera against J01 palette lit targets
        /// (sand_dry #FFE5AE, meadow #BCC95E). Settable for the calibration loop; the defaults are the calibrated result.</summary>
        public static Vector3 GrassMul = new Vector3(1.226f, 0.951f, 0.567f), SandMul = new Vector3(1.472f, 1.224f, 0.744f);   // 2026-11-12 base Day rig, dE00 sand 1.28 / meadow 0.62
        /// <summary>D4 A: the D3 leaf point list is retired; the grass outline stays the clean G curve.</summary>
        const bool UseD3LeafList = false;
        /// <summary>D4 H: contact dark edge off by default (1 = off).</summary>
        const float ContactEdgeMul = 1f;
        /// <summary>D4 E: deep-forest floor luminance relative to open grass (start 0.78).</summary>
        public static float ForestFloorY = 0.78f;
        const int Seed = 1112;

        static Vector2 s_pivot, s_origin; static float s_h;
        internal static Vector2 Pivot => s_pivot;
        internal static Vector2 Origin => s_origin;
        internal static float H => s_h;
        static JArray s_profiles;
        static float s_capExtra;
        static readonly List<string> s_sectionRows = new List<string>();
        static readonly StringBuilder s_checks = new StringBuilder();

        // ── menu ─────────────────────────────────────────────────────────────
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 Build (Online)")] static void MenuBuild() => Debug.Log(Build(BaseV3EnvTestState.Online));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 Build 12m Edge Sample")] static void MenuSample() => Debug.Log(Build(BaseV3EnvTestState.Online, new Vector2(-6f, 6f)));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 State Online")] static void MenuOnline() => Debug.Log(SetState(BaseV3EnvTestState.Online));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 State TEST Center3x3")] static void Menu3x3() => Debug.Log(SetState(BaseV3EnvTestState.Test_Center3x3));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 State TEST Cap15x15")] static void MenuCap() => Debug.Log(SetState(BaseV3EnvTestState.Test_Cap15x15));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 State TEST Center3x3 BeachRows")] static void MenuBeach() => Debug.Log(SetState(BaseV3EnvTestState.Test_Center3x3_BeachRows));
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 Toggle Wet Sand")] static void MenuWet() => Debug.Log(ToggleWetSand());
        [MenuItem("Tools/Setup/Base V3 Env WIP - Step3 Toggle Understory Sample")] static void MenuUnder() => Debug.Log(ToggleUnderstory());

        // ── coordinates ──────────────────────────────────────────────────────
        /// <summary>Initialises the coordinate statics if a domain reload cleared them (callers outside Build use this).</summary>
        internal static void EnsureInit() { if (s_profiles == null) Init(); }

        internal static void Init()
        {
            var config = AssetDatabase.LoadAssetAtPath<BaseConfig>("Assets/ScriptableObjects/Meta/Base/BaseConfig.asset");
            if (config == null) throw new InvalidOperationException("Missing BaseConfig.asset");
            s_pivot = config.PlacementBounds.center;
            if (!BaseTownLayout.TryGetPlot(BuildingType.HQ, out var hq)) throw new InvalidOperationException("No HQ plot");
            s_origin = new Vector2(hq.GridCenterX, hq.GridCenterZ);
            s_h = BaseTownLayout.DistrictGroundY("D1");
            var edge = JObject.Parse(File.ReadAllText("Tools/J02SurfaceStyleLab/edge_profile.json"));
            s_profiles = (JArray)edge["profiles"];
            float minG = float.MaxValue;
            for (float u = -30f; u <= 30f; u += 0.01f) minG = Mathf.Min(minG, GOnline(u));
            s_capExtra = Mathf.Max(0f, CapEdgeV - (minG + 12f)) + 0.001f;
        }

        /// <summary>(u, v) design metres → world (v = grid +X toward the sea, u = grid -Z).</summary>
        public static Vector3 UV(float u, float v, float y) => BaseVisualGrid.ToWorld(new Vector3(s_origin.x + v, y, s_origin.y - u), s_pivot);

        public static Vector2 WorldToUV(Vector3 w)
        {
            var g = BaseVisualGrid.ToGrid(w, s_pivot);
            return new Vector2(-(g.z - s_origin.y), g.x - s_origin.x);
        }

        // ── control curves (D3 B, E) ─────────────────────────────────────────
        static readonly float[] KnotU = { -60, -48, -36, -27, -18, -14, -10, -6, -2, 2, 6, 10, 14, 18, 27, 36, 48, 60 };
        static readonly float[] KnotG = { 16.8f, 17.2f, 17.6f, 18.0f, 18.25f, 18.30f, 18.20f, 18.45f, 18.20f, 18.15f, 18.40f, 18.20f, 18.35f, 18.25f, 18.45f, 18.15f, 17.75f, 17.5f };
        // normal sand width (G -> still-water line): |u| <= 18 from D3 B (W - G); outer knots are a Step-3b start inside D3 E's 2.6-3.4 m
        // step 3d (勾哥 11-13 "沙滩太窄", Boom Beach sand / grass depth ~14-18 %): every knot x2, same rhythm (wide u~-6 / 10, narrow u~2)
        static readonly float[] KnotN = { 5.90f, 6.50f, 5.80f, 6.20f, 5.60f, 5.90f, 6.70f, 6.70f, 6.50f, 5.90f, 5.90f, 7.00f, 6.60f, 5.60f, 5.90f, 6.60f, 5.70f, 6.20f };
        /// <summary>Rows follow the shore normal only up to this distance from G (G's tightest bend radius is ~10.8 m), then run straight in v.</summary>
        const float SNormalMax = 9.5f;
        /// <summary>Step 3d: 勾哥 "不需要草" - no G01 short grass (edge clusters or patches).</summary>
        public static bool EnableG01 = false;

        /// <summary>Fritsch-Carlson monotone cubic (no overshoot); flat beyond the end knots.</summary>
        internal static float Pchip(float[] x, float[] y, float t)
        {
            int n = x.Length;
            if (t <= x[0]) return y[0];
            if (t >= x[n - 1]) return y[n - 1];
            int k = 0; while (t > x[k + 1]) k++;
            float D(int i)
            {
                if (i == 0 || i == n - 1) return 0f;
                float d0 = (y[i] - y[i - 1]) / (x[i] - x[i - 1]), d1 = (y[i + 1] - y[i]) / (x[i + 1] - x[i]);
                if (d0 * d1 <= 0f) return 0f;
                float h0 = x[i] - x[i - 1], h1 = x[i + 1] - x[i], w1 = 2f * h1 + h0, w2 = h1 + 2f * h0;
                return (w1 + w2) / (w1 / d0 + w2 / d1);
            }
            float h = x[k + 1] - x[k], s = (t - x[k]) / h;
            float h00 = 2 * s * s * s - 3 * s * s + 1, h10 = s * s * s - 2 * s * s + s, h01 = -2 * s * s * s + 3 * s * s, h11 = s * s * s - s * s;
            return h00 * y[k] + h10 * h * D(k) + h01 * y[k + 1] + h11 * h * D(k + 1);
        }

        public static float GOnline(float u) => Pchip(KnotU, KnotG, u);
        public static float CapQ(float u) { float t = Mathf.Clamp01((Mathf.Abs(u) - 30f) / 30f); return 1f - t * t * t * (t * (t * 6f - 15f) + 10f); }
        public static float G(float u, bool cap) => GOnline(u) + (cap ? (12f + s_capExtra) * CapQ(u) : 0f);
        public static float N(float u) => Pchip(KnotU, KnotN, u);

        /// <summary>Test_Center3x3_BeachRows: the three unopened rows between the centre 3x3 and the sea are beach. Grass outline at
        /// v = 6.15 + 0..0.35 m gentle bend over |u| <= 18, smootherstep back onto GOnline over |u| 18 -> 30; waterline unchanged.</summary>
        const float BeachRowsV = 6.15f, BeachRowsBend = 0.35f;
        public static float GBeach(float u)
        {
            float a = Mathf.Abs(u);
            if (a <= 18f) return BeachRowsV + BeachRowsBend * 0.5f * (1f + Mathf.Cos(Mathf.PI * a / 18f));
            float t = Mathf.Clamp01((a - 18f) / 12f); t = t * t * t * (t * (t * 6f - 15f) + 10f);
            return Mathf.Lerp(BeachRowsV, GOnline(u), t);
        }
        public static float SlopeStart(float n) => n - WaterlineIntoDescent;

        static float s_wlInto = -1f;
        /// <summary>Distance into the Hermite descent where the bed crosses H-0.08 (0.933 m).</summary>
        public static float WaterlineIntoDescent
        {
            get
            {
                if (s_wlInto > 0f) return s_wlInto;
                float lo = 0f, hi = DescentLength;
                for (int i = 0; i < 50; i++) { float m = (lo + hi) * 0.5f; if (DescentDropAt(m) < WaterDrop) lo = m; else hi = m; }
                return s_wlInto = (lo + hi) * 0.5f;
            }
        }

        static float DescentDropAt(float d)
        {
            float t = Mathf.Clamp01(d / DescentLength);
            return DescentDrop * (-2f * t * t * t + 3f * t * t) + BedSlope * DescentLength * (t * t * t - t * t);
        }

        /// <summary>Bed height below H at normal distance s from G, for a local sand width n (slope start s0 = n - 0.933).</summary>
        public static float Drop(float s, float n)
        {
            float d = s - SlopeStart(n);
            if (d <= 0f) return 0f;
            if (d <= DescentLength) return DescentDropAt(d);
            float lin = DescentDrop + BedSlope * (d - DescentLength);
            const float k = 0.5f; float corner = BedFloorDrop - BedSlope * k;
            if (lin <= corner) return lin;
            float x = Mathf.Min((lin - corner) / BedSlope, 2f * k);
            return Mathf.Min(BedFloorDrop, corner + BedSlope * x - BedSlope * x * x / (4f * k));
        }

        static float WetWidth(float u) => 0.20f + 0.03f * Mathf.Sin(2f * Mathf.PI * u / 9.3f + 1.1f) + 0.02f * Mathf.Sin(2f * Mathf.PI * u / 5.9f + 0.3f);

        // ── G curve sampled by arc length ────────────────────────────────────
        sealed class Curve
        {
            public readonly List<Vector2> P = new List<Vector2>(); public readonly List<float> A = new List<float>();
            public Curve(Func<float, float> g)
            {
                for (float u = -Coverage; u <= Coverage + 1e-4f; u += 0.02f)
                {
                    var p = new Vector2(u, g(u));
                    A.Add(P.Count == 0 ? 0f : A[A.Count - 1] + Vector2.Distance(P[P.Count - 1], p)); P.Add(p);
                }
            }
            public float Length => A[A.Count - 1];
            int Index(float a) { int lo = 0, hi = A.Count - 1; while (hi - lo > 1) { int m = (lo + hi) / 2; if (A[m] <= a) lo = m; else hi = m; } return lo; }
            public Vector2 At(float a) { a = Mathf.Clamp(a, 0f, Length); int i = Mathf.Min(Index(a), P.Count - 2); float t = (a - A[i]) / Mathf.Max(1e-6f, A[i + 1] - A[i]); return Vector2.Lerp(P[i], P[i + 1], t); }
            public Vector2 Tangent(float a) { var d = At(a + 0.05f) - At(a - 0.05f); return d.normalized; }
            /// <summary>Seaward unit normal (toward +v).</summary>
            public Vector2 Normal(float a) { var t = Tangent(a); return new Vector2(-t.y, t.x); }
            public float ArcAtU(float u) { int i = Mathf.Clamp(Mathf.RoundToInt((u + Coverage) / 0.02f), 0, A.Count - 1); return A[i]; }
        }

        // ── grass leaf outline (D3 A) ────────────────────────────────────────
        static readonly float[,] LeafPts =
        {
            {0.00f,0.00f},{0.75f,0.00f},{1.10f,0.03f},{1.28f,0.11f},{1.38f,0.05f},{1.48f,0.25f},{1.58f,0.09f},{1.72f,0.19f},{1.85f,0.02f},{2.20f,0.00f},
            {3.10f,0.00f},{3.36f,0.04f},{3.52f,0.17f},{3.62f,0.06f},{3.76f,0.30f},{3.88f,0.11f},{4.02f,0.22f},{4.18f,0.07f},{4.35f,0.00f},
            {5.60f,0.00f},{6.05f,0.02f},{6.18f,0.13f},{6.28f,0.04f},{6.40f,0.21f},{6.53f,0.03f},{6.75f,0.00f},
            {7.75f,0.00f},{8.02f,0.06f},{8.18f,0.20f},{8.27f,0.08f},{8.40f,0.32f},{8.53f,0.13f},{8.67f,0.24f},{8.82f,0.08f},{9.00f,0.00f},
            {10.40f,0.00f},{10.65f,0.03f},{10.82f,0.16f},{10.93f,0.05f},{11.08f,0.23f},{11.23f,0.04f},{11.40f,0.00f},{12.00f,0.00f}
        };
        static readonly float[,] LeafSegs = { { 0f, 2.2f }, { 3.1f, 4.35f }, { 5.6f, 6.75f }, { 7.75f, 9f }, { 10.4f, 11.4f } };

        /// <summary>Piecewise-linear leaf offset along arc: the five D3 segments re-ordered, mirrored and spaced with varying quiet runs.</summary>
        static List<Vector2> BuildLeafProfile(float a0, float a1, out List<Vector2> clusters)
        {
            var pts = new List<Vector2>(); clusters = new List<Vector2>();
            var rng = new System.Random(Seed);
            float R(float x, float y) => x + (float)rng.NextDouble() * (y - x);
            float pos = a0 + R(0.3f, 1.5f); int prev = -1;
            pts.Add(new Vector2(a0 - 1f, 0f));
            while (pos < a1)
            {
                int seg; do seg = rng.Next(5); while (seg == prev); prev = seg;
                bool mirror = rng.NextDouble() < 0.5;
                float x0 = LeafSegs[seg, 0], x1 = LeafSegs[seg, 1], len = x1 - x0;
                var local = new List<Vector2>();
                for (int i = 0; i < LeafPts.GetLength(0); i++)
                {
                    float x = LeafPts[i, 0]; if (x < x0 - 1e-4f || x > x1 + 1e-4f) continue;
                    float lx = x - x0; local.Add(new Vector2(mirror ? len - lx : lx, LeafPts[i, 1]));
                }
                if (mirror) local.Reverse();
                if (pos + len > a1) break;
                foreach (var p in local) pts.Add(new Vector2(pos + p.x, p.y));
                clusters.Add(new Vector2(pos, pos + len));
                pos += len;
                pos += rng.NextDouble() < 0.25 ? R(3f, 5.5f) : R(0.6f, 2.2f);   // quiet run, varying
            }
            pts.Add(new Vector2(a1 + 1f, 0f));
            return pts;
        }

        static float LeafAt(List<Vector2> prof, float a)
        {
            int lo = 0, hi = prof.Count - 1;
            if (a <= prof[0].x || a >= prof[hi].x) return 0f;
            while (hi - lo > 1) { int m = (lo + hi) / 2; if (prof[m].x <= a) lo = m; else hi = m; }
            float t = (a - prof[lo].x) / Mathf.Max(1e-6f, prof[hi].x - prof[lo].x);
            return Mathf.Lerp(prof[lo].y, prof[hi].y, t);
        }

        // ── colour ───────────────────────────────────────────────────────────
        static float ColourActivity(float s)
        {
            const float span = 4.8f;
            int block = Mathf.FloorToInt(s / span); float phase = s / span - block;
            var row = (JArray)s_profiles[((block % 3) + 3) % 3 == 1 ? 1 : 0]["colour_activity"];
            if (((block % 4) + 4) % 4 >= 2) phase = 1f - phase;
            float q = phase * (row.Count - 1); int i = Mathf.Min((int)q, row.Count - 2);
            return Mathf.Max(0f, row[i].Value<float>() * (1f - (q - i)) + row[i + 1].Value<float>() * (q - i));
        }

        internal static Vector3 LinearHex(string hex) { ColorUtility.TryParseHtmlString("#" + hex, out var c); var l = c.linear; return new Vector3(l.r, l.g, l.b); }
        // kit grass field (prepare_mosaic.py grass_base) without its two blue-green centres 5C7561 / 5E8275 (D3 H: no large cyan-grey cast)
        static readonly string[] GrassHex = { "929E73", "7D996B", "86A175", "708C66", "85916E" };
        static readonly Vector4[] GrassCentres = { new(5, 10, 6, 4), new(15, 7, 7, 6), new(-15, -3, 9, 9), new(-5, -1, 7, 7), new(1, -12, 10, 5) };

        static Vector3 GrassBase(float x, float z)
        {
            var b = LinearHex("86A175") * 0.10f; float total = 0.10f;
            for (int i = 0; i < GrassCentres.Length; i++)
            {
                var c = GrassCentres[i];
                float q = (x - c.x) * (x - c.x) / (c.z * c.z) + (z - c.y) * (z - c.y) / (c.w * c.w);
                float w = Mathf.Exp(-1.7f * q * q); b += LinearHex(GrassHex[i]) * w; total += w;
            }
            // D3 H: the field's large patches read as fixed blotches at base scale (measured: they vanish with uniform vertex colour),
            // so only 35 % of its deviation from the base green is kept
            return Vector3.Lerp(LinearHex("86A175"), b / total, GrassFieldKeep);
        }

        const float GrassFieldKeep = 0.35f;

        /// <summary>Kit grass colour + sand-edge warm lift (strength 0.25), distToSand measured along the shore normal.</summary>
        static Color GrassColour(float u, float v, float distToSand, float arc)
        {
            var b = GrassBase(u, v - 14f); var col = b;
            float activity = ColourActivity(arc + 40f), width = 0.20f + 0.65f * activity, gain = Mathf.Pow(activity, 1.7f);
            if (distToSand >= 0f && distToSand < width)
            {
                float f = 1f - distToSand / width; f = f * f * (3f - 2f * f);
                float headroom = Mathf.Clamp01((0.32f - Vector3.Dot(b, new Vector3(0.2126f, 0.7152f, 0.0722f))) / 0.10f);
                col = Vector3.Lerp(col, Vector3.Scale(b, new Vector3(1.65f, 1.75f, 1.12f)), f * gain * 0.25f * headroom);
            }
            col = Vector3.Scale(col, GrassMul);
            return new Color(col.x, col.y, col.z, 1f);
        }

        // ── build ────────────────────────────────────────────────────────────
        /// <param name="leafWindow">u range carrying grass leaves and pebbles (null = whole shore); the 12 m sample uses (-6, 6).</param>
        public static string Build(BaseV3EnvTestState state, Vector2? leafWindow = null)
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Stop Play before building");
            var scene = SceneManager.GetSceneByPath(BaseV3EnvWipBuilder.ScenePath);
            if (!scene.IsValid() || !scene.isLoaded) throw new InvalidOperationException("HomeScreen not loaded");
            var root = scene.GetRootGameObjects().FirstOrDefault(g => g.name == BaseV3EnvWipBuilder.RootName);
            if (root == null) throw new InvalidOperationException(BaseV3EnvWipBuilder.RootName + " missing: run the step-1 builder first");
            Init(); s_sectionRows.Clear(); s_checks.Clear(); G01Report.Clear(); s_g01 = null;
            Folder(OutDir);
            var old = root.transform.Find(NodeName); if (old != null) Object.DestroyImmediate(old.gameObject);
            var node = new GameObject(NodeName).transform; node.SetParent(root.transform, false);

            var report = new StringBuilder();
            report.AppendLine($"pivot={s_pivot} O(grid)={s_origin} H={s_h} waterline into descent={WaterlineIntoDescent:F3} capLift={12f + s_capExtra:F3} leafWindow={(leafWindow.HasValue ? leafWindow.Value.ToString() : "all")}");
            var trees = new Dictionary<BaseV3EnvTestState, List<Vector2>>();
            var curves = new Dictionary<bool, Curve> { { false, new Curve(u => G(u, false)) }, { true, new Curve(u => G(u, true)) } };
            var candidates = Candidates();
            foreach (var st in AllStates)
                report.AppendLine(BuildForest(node, st, candidates, curves[st == BaseV3EnvTestState.Test_Cap15x15], trees));
            report.AppendLine(BuildGround(node, false, curves[false], leafWindow));
            report.AppendLine(BuildGround(node, true, curves[true], leafWindow));
            report.AppendLine(BuildBeachRowsGround(node));
            report.AppendLine(BuildUnderstorySample(node, trees[BaseV3EnvTestState.Online]));
            report.AppendLine(BuildScaleCompare(node));
            report.Append(s_checks); report.Append(G01Report);
            File.WriteAllText(SectionJson, "[" + string.Join(",", s_sectionRows) + "]");

            foreach (var name in new[] { "Sample_Shore12m", "Greybox" })
            {
                var t = root.transform.Find(name); if (t != null) t.gameObject.SetActive(false);
            }
            ApplyState(node, state, false);
            root.SetActive(false);
            EditorSceneManager.MarkSceneDirty(scene);
            AssetDatabase.SaveAssets();
            return "[BaseV3EnvStep3b] " + report;
        }

        static readonly BaseV3EnvTestState[] AllStates = { BaseV3EnvTestState.Online, BaseV3EnvTestState.Test_Center3x3, BaseV3EnvTestState.Test_Cap15x15, BaseV3EnvTestState.Test_Center3x3_BeachRows };
        const string BeachGroundName = "Ground_TEST_Center3x3_BeachRows_NotSaveData";

        static string ForestName(BaseV3EnvTestState st) => st == BaseV3EnvTestState.Online ? "Forest_Online" : st == BaseV3EnvTestState.Test_Center3x3 ? "Forest_TEST_Center3x3_NotSaveData"
            : st == BaseV3EnvTestState.Test_Cap15x15 ? "Forest_TEST_Cap15x15_NotSaveData" : "Forest_TEST_Center3x3_BeachRows_NotSaveData";
        static string StateTag(BaseV3EnvTestState st) => st == BaseV3EnvTestState.Online ? "Online" : st == BaseV3EnvTestState.Test_Center3x3 ? "Center3x3" : st == BaseV3EnvTestState.Test_Cap15x15 ? "Cap" : "Center3x3Beach";

        public static void ApplyState(Transform node, BaseV3EnvTestState state, bool? wetSand = null)
        {
            bool cap = state == BaseV3EnvTestState.Test_Cap15x15, beach = state == BaseV3EnvTestState.Test_Center3x3_BeachRows;
            Set(node, "Ground_Online", !cap);
            Set(node, "Ground_TEST_Cap15x15_NotSaveData", cap);
            Set(node, BeachGroundName, beach);
            // the beach state reuses the online sand / bed / water; its own node carries the grass edge and the sand wedge
            Set(node.Find("Ground_Online"), "GrassEdge", !beach);
            Set(node.Find("Ground_Online"), "Pebbles", !beach);
            foreach (var st in AllStates)
                Set(node, ForestName(st), st == state);
            if (wetSand.HasValue)
                foreach (var g in new[] { "Ground_Online", "Ground_TEST_Cap15x15_NotSaveData" })
                {
                    Set(node.Find(g), "WetBand_On", wetSand.Value);
                    Set(node.Find(g), "WetBand_Off", !wetSand.Value);
                }
        }

        static void Set(Transform parent, string name, bool on) { var t = parent != null ? parent.Find(name) : null; if (t != null) t.gameObject.SetActive(on); }

        static Transform StepNode(out Scene scene)
        {
            scene = SceneManager.GetSceneByPath(BaseV3EnvWipBuilder.ScenePath);
            if (!scene.IsValid() || !scene.isLoaded) return null;
            var root = scene.GetRootGameObjects().FirstOrDefault(g => g.name == BaseV3EnvWipBuilder.RootName);
            return root != null ? root.transform.Find(NodeName) : null;
        }

        public static string SetState(BaseV3EnvTestState state)
        {
            var node = StepNode(out var scene); if (node == null) return "no " + NodeName;
            ApplyState(node, state);
            if (!EditorApplication.isPlaying) EditorSceneManager.MarkSceneDirty(scene);
            return "state=" + state;
        }

        public static string ToggleWetSand()
        {
            var node = StepNode(out var scene); if (node == null) return "no " + NodeName;
            var on = node.Find("Ground_Online/WetBand_On"); bool next = on == null || !on.gameObject.activeSelf;
            foreach (var g in new[] { "Ground_Online", "Ground_TEST_Cap15x15_NotSaveData" })
            {
                Set(node.Find(g), "WetBand_On", next); Set(node.Find(g), "WetBand_Off", !next);
            }
            if (!EditorApplication.isPlaying) EditorSceneManager.MarkSceneDirty(scene);
            return "wetSand=" + next;
        }

        public static string ToggleUnderstory()
        {
            var node = StepNode(out var scene); if (node == null) return "no " + NodeName;
            var t = node.Find(UnderstoryNode); if (t == null) return "no " + UnderstoryNode;
            t.gameObject.SetActive(!t.gameObject.activeSelf);
            if (!EditorApplication.isPlaying) EditorSceneManager.MarkSceneDirty(scene);
            return "understory=" + t.gameObject.activeSelf;
        }

        // ── ground ───────────────────────────────────────────────────────────
        internal struct Col { public float a; public Vector2 p, n; public float u, nw, leaf; }

        static List<Col> Columns(Curve c, float fineStep, float coarseStep, List<float> extra, List<Vector2> leaf)
        {
            float aFine0 = c.ArcAtU(-LeafHalf), aFine1 = c.ArcAtU(LeafHalf);
            var arcs = new List<float>();
            for (float a = 0f; a < aFine0; a += coarseStep) arcs.Add(a);
            for (float a = aFine0; a <= aFine1; a += fineStep) arcs.Add(a);
            if (extra != null) arcs.AddRange(extra.Where(a => a > aFine0 && a < aFine1));
            for (float a = aFine1 + coarseStep; a <= c.Length; a += coarseStep) arcs.Add(a);
            arcs.Sort();
            var cols = new List<Col>();
            foreach (var a in arcs)
            {
                if (cols.Count > 0 && a - cols[cols.Count - 1].a < 0.008f) continue;
                var p = c.At(a); float nw = N(p.x);
                float lf = leaf != null ? Mathf.Clamp(LeafAt(leaf, a), 0f, Mathf.Max(0f, nw - MinExposedSand)) : 0f;
                cols.Add(new Col { a = a, p = p, n = c.Normal(a), u = p.x, nw = nw, leaf = lf });
            }
            return cols;
        }

        static string BuildGround(Transform node, bool cap, Curve c, Vector2? leafWindow)
        {
            string tag = cap ? "Cap" : "Online";
            var g = new GameObject(cap ? "Ground_TEST_Cap15x15_NotSaveData" : "Ground_Online").transform; g.SetParent(node, false);
            var grassMat = Load<Material>(KitDir + "MosaicGrass.mat");
            var dryMat = Load<Material>(KitDir + "DrySand.mat");
            var wetMat = Load<Material>(KitDir + "WetSand.mat");
            var waterMat = WaterMaterial();
            var dry = Vector3.Scale(LinearHex("99999F"), SandMul); var wetC = Vector3.Scale(LinearHex("8E8E94"), SandMul);
            var r = new List<string>();

            float wa0 = c.ArcAtU(leafWindow?.x ?? -LeafHalf), wa1 = c.ArcAtU(leafWindow?.y ?? LeafHalf);
            List<Vector2> leaf, clusters;
            if (UseD3LeafList) leaf = BuildLeafProfile(wa0, wa1, out clusters);
            else { leaf = new List<Vector2> { new Vector2(-1f, 0f), new Vector2(c.Length + 1f, 0f) }; clusters = new List<Vector2>(); }
            var leafArcs = UseD3LeafList ? leaf.Select(p => p.x).ToList() : null;
            var fine = Columns(c, 0.05f, 1f, leafArcs, leaf);
            var coarse = Columns(c, 0.5f, 2f, null, null);
            var bedCols = Columns(c, 1f, 2f, null, null);
            float[] sectionU = cap ? new[] { -45f, 45f } : new[] { 0f, -6f, 2f };
            string secTag = cap ? "cap" : "online";

            Vector2 Off(Col q, float s) => q.p + q.n * s;

            // grass edge strip along the true normal: s -2 .. leaf tip (rows -2, -0.85, -0.3, tip - 0.06, tip); contact dark edge under leaves
            float[] gs = { -2f, -0.85f, -0.3f, -0.06f, 0f };
            r.Add(Grid(g, "GrassEdge", grassMat, fine.Count, gs.Length - 1, (i, k) =>
            {
                var q = fine[i]; float s = k < 3 ? gs[k] : q.leaf + gs[k]; var p = Off(q, s); return (p.x, p.y, s_h);
            }, (i, k, u, v) =>
            {
                var q = fine[i]; float s = k < 3 ? gs[k] : q.leaf + gs[k];
                var col = GrassColour(u, v, q.leaf - s, q.a);
                if (k == 4 && q.leaf > 0.02f && ContactEdgeMul < 1f) col = new Color(col.r * ContactEdgeMul, col.g * ContactEdgeMul, col.b * ContactEdgeMul, 1f);
                return col;
            }, null, $"{OutDir}/BV3S3_{tag}_GrassEdge.asset", fine, sectionU, secTag + "_grass"));

            // flat dry sand (leaf tip -> slope start) and the dry part of the descent (-> wet start)
            r.Add(Grid(g, "DrySand", dryMat, fine.Count, 5, (i, k) =>
            {
                var q = fine[i]; float s0 = SlopeStart(q.nw), ws = q.nw - WetWidth(q.u);
                float s = k == 0 ? q.leaf : Mathf.Lerp(s0, ws, (k - 1) / 4f); var p = Off(q, s); return (p.x, p.y, s_h - Drop(s, q.nw));
            }, (i, k, u, v) => new Color(dry.x, dry.y, dry.z, 1f), null, $"{OutDir}/BV3S3_{tag}_DrySand.asset", fine, sectionU, secTag + "_sand"));

            // wet band (D3 D: off by default; On / Off share the shape)
            (float, float, float) WetVertex(int i, int k)
            {
                var q = fine[i]; float ws = q.nw - WetWidth(q.u);
                float s = k == 0 ? ws : k == 1 ? ws + 0.06f : Mathf.Lerp(ws + 0.06f, q.nw + 0.6f, (k - 1) / 4f);
                var p = Off(q, s); return (p.x, p.y, s_h - Drop(s, q.nw));
            }
            r.Add(Grid(g, "WetBand_On", wetMat, fine.Count, 5, WetVertex, (i, k, u, v) => k == 0 ? new Color(dry.x, dry.y, dry.z, 1f) : new Color(wetC.x, wetC.y, wetC.z, 1f), null, $"{OutDir}/BV3S3_{tag}_WetBandOn.asset", null, null, null));
            r.Add(Grid(g, "WetBand_Off", dryMat, fine.Count, 5, WetVertex, (i, k, u, v) => new Color(dry.x, dry.y, dry.z, 1f), null, $"{OutDir}/BV3S3_{tag}_WetBandOff.asset", fine, sectionU, secTag + "_wetOff"));
            g.Find("WetBand_On").gameObject.SetActive(false);

            // bed under the opaque water (coarse, seam ~5 cm under the surface)
            float[] bedS = { 0.6f, 1.5f, 3f, 5f, 8f, 11f, 14f, 17f, 21f };
            r.Add(Grid(g, "Bed", dryMat, bedCols.Count, bedS.Length - 1, (i, k) =>
            {
                // along the normal up to +5 m, then straight seaward in v (no fold at the tight bends), drop keeps following s
                var q = bedCols[i]; float s = q.nw + bedS[k];
                float sEnd = Mathf.Max(q.nw + 1.5f, SNormalMax);
                var p = s <= sEnd ? Off(q, s) : Off(q, sEnd) + new Vector2(0f, s - sEnd);
                return (p.x, p.y, s_h - Drop(s, q.nw));
            }, (i, k, u, v) => new Color(dry.x, dry.y, dry.z, 1f), null, $"{OutDir}/BV3S3_{tag}_Bed.asset", bedCols, sectionU, secTag + "_bed"));

            // water: true distance + arc along the still-water line in uv1 (D3 C bulges), first rows along the normal, then straight to the coverage
            var wl = new List<Vector2>(); var wlArc = new List<float>();
            foreach (var q in Columns(c, 0.1f, 1f, null, null)) { var p = Off(q, q.nw); wlArc.Add(wl.Count == 0 ? 0f : wlArc[wlArc.Count - 1] + Vector2.Distance(wl[wl.Count - 1], p)); wl.Add(p); }
            float arcOrigin = NearestOnLine(wl, wlArc, new Vector2(-18f, G(-18f, cap) + N(-18f))).arc;
            const int farRows = 10; int nearRows = 21;
            (float, float, float) WaterVertex(int i, int k)
            {
                var q = coarse[i];
                // normal rows stop at +5 m: G's tightest bend (radius ~10.8 m at u~2) would fold a +8 m offset
                float sEnd = Mathf.Max(q.nw + 1.5f, SNormalMax);
                Vector2 p = k <= nearRows ? Off(q, k == 0 ? q.nw - 0.5f : Mathf.Lerp(q.nw, sEnd, (k - 1) / (float)(nearRows - 1))) : Vector2.Lerp(Off(q, sEnd), new Vector2(Off(q, sEnd).x, Coverage), (k - nearRows) / (float)farRows);
                return (p.x, p.y, s_h - WaterDrop);
            }
            r.Add(Grid(g, "Water", waterMat, coarse.Count, nearRows + farRows, WaterVertex, null, (i, k, u, v) =>
            {
                var near = NearestOnLine(wl, wlArc, new Vector2(u, v));
                bool landSide = v < G(u, cap) + N(u) * 0.999f && k == 0;
                return new Vector2(landSide ? 0f : near.dist, ShallowWidth(near.arc - arcOrigin));
            }, $"{OutDir}/BV3S3_{tag}_Water.asset", coarse, sectionU, secTag + "_water"));

            // pebbles (approved kit Gravel_01..10 + Gravel_Blender.mat, colour recipe of SurfaceStyleLab.cs)
            var legal = cap ? new List<Rect> { Rect.MinMaxRect(-30, -30, 30, 30) } : new List<Rect> { Rect.MinMaxRect(-18, -18, 18, 18) };
            r.Add(BuildG01Edge(g, tag, c, fine, wa0, wa1, legal, out var g01Clusters));
            r.Add(BuildPebbles(g, tag, c, fine, g01Clusters));

            // checks
            CheckShore(tag, cap, c, fine);
            return $"{tag}: {string.Join(" ", r)}";
        }

        /// <summary>Test_Center3x3_BeachRows: grass edge strip (v GBeach-2 .. GBeach) over the whole shore and the dry-sand wedge
        /// GBeach .. GOnline over |u| <= 30, both as straight-v columns (no normal offsets, no fold in the 18 -> 30 bends). The online
        /// sand from GOnline seaward, bed and water are reused.</summary>
        static string BuildBeachRowsGround(Transform node)
        {
            var g = new GameObject(BeachGroundName).transform; g.SetParent(node, false);
            var grassMat = Load<Material>(KitDir + "MosaicGrass.mat");
            var dryMat = Load<Material>(KitDir + "DrySand.mat");
            var dry = Vector3.Scale(LinearHex("99999F"), SandMul);
            var cols = new List<float>();
            for (float u = -Coverage; u < -60f; u += 1f) cols.Add(u);
            for (float u = -60f; u <= 60f + 1e-3f; u += 0.05f) cols.Add(u);
            for (float u = 61f; u <= Coverage + 1e-3f; u += 1f) cols.Add(u);
            var wcols = cols.Where(u => Mathf.Abs(u) <= 30.001f).ToList();
            float[] gs = { -2f, -0.85f, -0.3f, -0.06f, 0f };
            var r = new List<string>();
            r.Add(Grid(g, "GrassEdge", grassMat, cols.Count, gs.Length - 1, (i, k) => (cols[i], GBeach(cols[i]) + gs[k], s_h),
                (i, k, u, v) => GrassColour(u, v, GBeach(u) - v, u), null, $"{OutDir}/BV3S3_Center3x3Beach_GrassEdge.asset", null, null, null));
            r.Add(Grid(g, "SandWedge", dryMat, wcols.Count, 6, (i, k) => (wcols[i], Mathf.Lerp(GBeach(wcols[i]), GOnline(wcols[i]), k / 6f), s_h),
                (i, k, u, v) => new Color(dry.x, dry.y, dry.z, 1f), null, $"{OutDir}/BV3S3_Center3x3Beach_SandWedge.asset", null, null, null));

            // checks: outline vs the opened 3x3, depth to the (online) waterline, self-intersections of the outline
            var plot = Rect.MinMaxRect(-6f, -6f, 6f, 6f); var line = new List<Vector2>();
            float minPlot = float.MaxValue, dMin = float.MaxValue, dMax = 0f, gMin = float.MaxValue, gMax = float.MinValue;
            for (float u = -60f; u <= 60f; u += 0.05f)
            {
                var p = new Vector2(u, GBeach(u)); line.Add(p);
                if (Mathf.Abs(u) <= 30f) minPlot = Mathf.Min(minPlot, RectDist(p, plot));
                if (Mathf.Abs(u) <= 18f) { float d = GOnline(u) + N(u) - p.y; dMin = Mathf.Min(dMin, d); dMax = Mathf.Max(dMax, d); gMin = Mathf.Min(gMin, p.y); gMax = Mathf.Max(gMax, p.y); }
            }
            s_checks.AppendLine($"CHECK Center3x3Beach: grass outline v (|u|<=18) {gMin:F2}..{gMax:F2}; sand depth outline -> still-water line (v, |u|<=18) {dMin:F2}..{dMax:F2} m (at u=0 {GOnline(0f) + N(0f) - GBeach(0f):F2}); " +
                $"min distance opened 3x3 -> sand start (|u|<=30) {minPlot:F3} m; outline self-intersections {SelfIntersections(line)}; online GrassEdge + Pebbles hidden in this state");
            return $"Center3x3Beach: {string.Join(" ", r)}";
        }

        /// <summary>True distance from p to the GBeach outline (positive landward).</summary>
        static float BeachCoastDist(Vector2 p)
        {
            float best = float.MaxValue;
            for (float u = p.x - 25f; u <= p.x + 25f; u += 0.1f) best = Mathf.Min(best, (new Vector2(u, GBeach(u)) - p).sqrMagnitude);
            return (p.y < GBeach(p.x) ? 1f : -1f) * Mathf.Sqrt(best);
        }

        /// <summary>D3 C: base 1.6 m plus three uneven bulges along the 36 m centre sample (a = 0 at u ~ -18).</summary>
        static float ShallowWidth(float a)
        {
            float w = 3.5f;   // step 3d: 1.6 -> 3.5 m, bulge reach x2 (positions / half widths unchanged)
            foreach (var (centre, half, extra) in new[] { (5f, 3f, 3f), (15.5f, 4.5f, 4f), (28f, 2.5f, 2.4f) })
            {
                float t = Mathf.Max(0f, 1f - Mathf.Abs(a - centre) / half); t = t * t * (3f - 2f * t);
                w += t * extra;
            }
            return w;
        }

        internal static (float dist, float arc) NearestOnLine(List<Vector2> line, List<float> arc, Vector2 p)
        {
            int lo = 0, hi = line.Count - 1;
            while (hi - lo > 1) { int m = (lo + hi) / 2; if (line[m].x <= p.x) lo = m; else hi = m; }
            int a = Mathf.Max(0, lo - 400), b = Mathf.Min(line.Count - 2, lo + 400);
            float best = float.MaxValue, bestArc = 0f;
            for (int j = a; j <= b; j++)
            {
                Vector2 s = line[j], d = line[j + 1] - s;
                float t = Mathf.Clamp01(Vector2.Dot(p - s, d) / Mathf.Max(1e-8f, d.sqrMagnitude));
                float dd = (s + d * t - p).sqrMagnitude;
                if (dd < best) { best = dd; bestArc = arc[j] + t * d.magnitude; }
            }
            return (Mathf.Sqrt(best), bestArc);
        }

        static void CheckShore(string tag, bool cap, Curve c, List<Col> fine)
        {
            float edge = cap ? CapEdgeV : OnlineEdgeV, half = cap ? 30f : 18f;
            float minExposed = float.MaxValue, maxExposed = 0f, minGrassV = float.MaxValue, minWlLegal = float.MaxValue, maxLeaf = 0f;
            float gMin = float.MaxValue, gMax = float.MinValue, wMin = float.MaxValue, wMax = float.MinValue;
            var legal = Rect.MinMaxRect(-half, -half, half, edge);
            var leafEdge = new List<Vector2>(); var slope = new List<Vector2>(); var wl = new List<Vector2>(); var w8 = new List<Vector2>();
            foreach (var q in fine)
            {
                var tip = q.p + q.n * q.leaf; var w = q.p + q.n * q.nw;
                leafEdge.Add(tip); slope.Add(q.p + q.n * SlopeStart(q.nw)); wl.Add(w); w8.Add(q.p + q.n * Mathf.Max(q.nw + 1.5f, SNormalMax));
                if (Mathf.Abs(q.u) > 60f) continue;
                minExposed = Mathf.Min(minExposed, q.nw - q.leaf); maxExposed = Mathf.Max(maxExposed, q.nw - q.leaf); maxLeaf = Mathf.Max(maxLeaf, q.leaf);
                if (Mathf.Abs(q.u) <= 42f) { gMin = Mathf.Min(gMin, q.p.y); gMax = Mathf.Max(gMax, q.p.y); wMin = Mathf.Min(wMin, w.y); wMax = Mathf.Max(wMax, w.y); }
                if (Mathf.Abs(q.p.x) <= half) minGrassV = Mathf.Min(minGrassV, q.p.y);
                minWlLegal = Mathf.Min(minWlLegal, RectDist(w, legal));
                minWlLegal = Mathf.Min(minWlLegal, RectDist(tip, legal) + 0f);
            }
            float maxBedUnderWater = float.MinValue;
            foreach (var q in fine) for (float s = q.nw; s < q.nw + 21f; s += 0.25f) maxBedUnderWater = Mathf.Max(maxBedUnderWater, s_h - Drop(s, q.nw));
            s_checks.AppendLine($"CHECK {tag}: G(|u|<=42) v {gMin:F2}..{gMax:F2}; waterline(|u|<=42) v {wMin:F2}..{wMax:F2}; exposed sand after leaves (normal, |u|<=60) {minExposed:F2}..{maxExposed:F2} m; max leaf {maxLeaf:F2} m; " +
                $"min G v over legal |u|<={half}: {minGrassV:F3} (edge {edge}); min distance legal plots -> sand start/waterline {minWlLegal:F3} m; max bed y seaward of the waterline {maxBedUnderWater:F3} (water {s_h - WaterDrop}); " +
                $"self-intersections: leafEdge {SelfIntersections(leafEdge)}, slopeStart {SelfIntersections(slope)}, waterline {SelfIntersections(wl)}, water@normalEnd {SelfIntersections(w8)}");
        }

        internal static int SelfIntersections(List<Vector2> pl)
        {
            int count = 0; var buckets = new Dictionary<int, List<int>>();
            for (int i = 0; i < pl.Count - 1; i++)
            {
                int b0 = Mathf.FloorToInt(Mathf.Min(pl[i].x, pl[i + 1].x)), b1 = Mathf.FloorToInt(Mathf.Max(pl[i].x, pl[i + 1].x));
                for (int b = b0; b <= b1; b++) { if (!buckets.TryGetValue(b, out var l)) buckets[b] = l = new List<int>(); l.Add(i); }
            }
            var seen = new HashSet<long>();
            foreach (var l in buckets.Values)
                for (int x = 0; x < l.Count; x++)
                    for (int y = x + 1; y < l.Count; y++)
                    {
                        int i = l[x], j = l[y]; if (Mathf.Abs(i - j) < 2) continue;
                        long key = (long)Mathf.Min(i, j) * 1000000 + Mathf.Max(i, j); if (!seen.Add(key)) continue;
                        if (SegmentsCross(pl[i], pl[i + 1], pl[j], pl[j + 1])) count++;
                    }
            return count;
        }

        static bool SegmentsCross(Vector2 a, Vector2 b, Vector2 c, Vector2 d)
        {
            float Cross(Vector2 o, Vector2 p, Vector2 q) => (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x);
            float d1 = Cross(c, d, a), d2 = Cross(c, d, b), d3 = Cross(a, b, c), d4 = Cross(a, b, d);
            return d1 * d2 < 0f && d3 * d4 < 0f;
        }

        static string BuildPebbles(Transform parent, string tag, Curve c, List<Col> fine, List<Vector2> clusters)
        {
            var mat = Load<Material>(GravelMatPath);
            GravelSources(out var meshes, out var mats);
            var rng = new System.Random(Seed + 7);
            float R(float x, float y) => x + (float)rng.NextDouble() * (y - x);
            var combines = new List<CombineInstance>(); var temps = new List<Mesh>(); int groups = 0, stones = 0, bigStones = 0;
            if (clusters.Count > 0)
            {
                float a0 = clusters[0].x, a1 = clusters[clusters.Count - 1].y;
                for (int w = 0; a0 + w * 12f < a1; w++)
                {
                    float wa = a0 + w * 12f, wb = wa + 12f;
                    var inWin = clusters.Where(cl => cl.x >= wa && cl.y < wb).ToList(); if (inWin.Count == 0) continue;
                    int nGroups = w % 2 == 0 ? Mathf.Min(3, inWin.Count) : (rng.NextDouble() < 0.5 ? 0 : 1);
                    foreach (var cl in inWin.OrderBy(_ => rng.Next()).Take(nGroups))
                    {
                        groups++;
                        float ga = R(cl.x, cl.y); var q = fine[Mathf.Clamp(fine.FindIndex(f => f.a >= ga), 0, fine.Count - 1)];
                        int n = 1 + rng.Next(3);
                        for (int k = 0; k < n; k++)
                        {
                            float s = Mathf.Min(R(0.05f, 0.6f), SlopeStart(q.nw) - 0.2f);
                            var p = q.p + q.n * s + new Vector2(-q.n.y, q.n.x) * R(-0.35f, 0.35f);
                            int vi = rng.Next(10); var mesh = meshes[vi];
                            var m = mats[vi];
                            var inst = ColouredGravel(mesh, m, vi); temps.Add(inst);
                            float sc = R(0.78f, 0.91f);
                            if (k == 0 && groups % 3 == 1)   // D4 G: about a third of the groups get one stone at 0.35-0.45 m long axis
                            {
                                var bsz = TransformBoundsSize(mesh.bounds, m); float longAxis = Mathf.Max(bsz.x, bsz.z);
                                sc = R(0.35f, 0.45f) / Mathf.Max(0.01f, longAxis); bigStones++;
                            }
                            var trs = Matrix4x4.TRS(UV(p.x, p.y, s_h + 0.005f), Quaternion.Euler(0f, R(0f, 360f), 0f), Vector3.one * sc);
                            combines.Add(new CombineInstance { mesh = inst, transform = trs * m }); stones++;
                        }
                    }
                }
            }
            if (combines.Count == 0) return "Pebbles:0";
            var combined = new Mesh { name = $"BV3S3_{tag}_Pebbles", indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
            combined.CombineMeshes(combines.ToArray(), true, true); combined.RecalculateBounds();
            foreach (var t in temps) Object.DestroyImmediate(t);
            combined = Keep(combined, $"{OutDir}/BV3S3_{tag}_Pebbles.asset");
            var go = new GameObject("Pebbles"); go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = combined;
            var rr = go.AddComponent<MeshRenderer>(); rr.sharedMaterial = mat; rr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            return $"Pebbles:{groups}groups/{stones}stones({bigStones} enlarged)/{combined.triangles.Length / 3}t";
        }

        internal const string GravelMatPath = KitDir + "Gravel_Blender.mat";
        /// <summary>Lit gain of the kit gravel recipe (SurfaceStyleLab): vertex colour = linear(target) / gain.</summary>
        internal static readonly Vector3 GravelGain = new Vector3(2.5394757f, 2.0665736f, 1.1984017f);

        /// <summary>Approved kit Gravel_01..10 meshes and their FBX import transforms.</summary>
        internal static void GravelSources(out Mesh[] meshes, out Matrix4x4[] mats)
        {
            meshes = new Mesh[10]; mats = new Matrix4x4[10];
            for (int i = 0; i < 10; i++)
            {
                var fbx = Load<GameObject>($"{KitDir}Debris/Gravel_{i + 1:00}.fbx");
                var mf = fbx.GetComponentInChildren<MeshFilter>(); if (mf == null) throw new InvalidOperationException("no mesh in Gravel_" + (i + 1));
                meshes[i] = mf.sharedMesh; mats[i] = fbx.transform.worldToLocalMatrix * mf.transform.localToWorldMatrix;   // FBX import transform, as SurfaceStyleLab
            }
        }

        /// <summary>Copy of one gravel mesh with the kit colour recipe in its vertex colours (caller destroys it).</summary>
        internal static Mesh ColouredGravel(Mesh mesh, Matrix4x4 m, int vi)
        {
            var inst = Object.Instantiate(mesh);
            float variation(Vector3 nn) => .98f + .035f * Mathf.Abs(Mathf.Sin((vi + 1) * 1.37f + nn.x * 2));
            inst.colors = mesh.normals.Select(n0 =>
            {
                var nn = m.MultiplyVector(n0).normalized;
                var target = nn.y > .65f ? new Color(230 / 255f, 195 / 255f, 151 / 255f, 1) : nn.y > .2f ? new Color(193 / 255f, 164 / 255f, 127 / 255f, 1) : new Color(184 / 255f, 156 / 255f, 121 / 255f, 1);
                var lin = target.linear; float vv = variation(nn);
                return new Color(lin.r / GravelGain.x * vv, lin.g / GravelGain.y * vv, lin.b / GravelGain.z * vv, 1);
            }).ToArray();
            return inst;
        }

        // ── G01 short grass (D4 A / B): approved kit GrassClump_02..17 blade meshes + their current materials ─────
        sealed class G01Variant { public Mesh[] meshes; public Material mat; public Vector3 centre; public Vector3 ext; }
        static List<G01Variant> s_g01;
        /// <summary>Instance scale of one kit clump (about 2.5-3.4 x 1.2-1.6 x 0.6 m at scale 1): along shore / height / across.
        /// Design start so one instance is ~0.9 m long, ~0.3 m tall, ~0.55 m across, letting 3-6 overlap in a 0.8-1.8 m cluster.</summary>
        static readonly Vector3 G01Scale = new Vector3(0.24f, 0.7f, 0.3f);
        public static readonly StringBuilder G01Report = new StringBuilder();

        static List<G01Variant> G01Variants()
        {
            if (s_g01 != null) return s_g01;
            s_g01 = new List<G01Variant>();
            for (int i = 2; i <= 17; i++)
            {
                var guids = AssetDatabase.FindAssets($"GrassClump_{i:00}_blade_ t:Mesh", new[] { KitDir.TrimEnd('/') });
                var meshes = guids.Select(gd => AssetDatabase.LoadAssetAtPath<Mesh>(AssetDatabase.GUIDToAssetPath(gd))).Where(m => m != null && m.name.StartsWith($"GrassClump_{i:00}_blade_")).ToArray();
                var mat = AssetDatabase.LoadAssetAtPath<Material>($"{KitDir}GrassClump_{i:00}_blades.mat");
                if (meshes.Length == 0 || mat == null) throw new InvalidOperationException("G01 source missing: GrassClump_" + i);
                var b = meshes[0].bounds; foreach (var m in meshes) b.Encapsulate(m.bounds);
                s_g01.Add(new G01Variant { meshes = meshes, mat = mat, centre = new Vector3(b.center.x, b.min.y, b.center.z), ext = b.extents });
            }
            return s_g01;
        }

        internal static Vector3 TransformBoundsSize(Bounds b, Matrix4x4 m)
        {
            var mn = Vector3.positiveInfinity; var mx = Vector3.negativeInfinity;
            for (int i = 0; i < 8; i++)
            {
                var p = m.MultiplyPoint3x4(new Vector3((i & 1) == 0 ? b.min.x : b.max.x, (i & 2) == 0 ? b.min.y : b.max.y, (i & 4) == 0 ? b.min.z : b.max.z));
                mn = Vector3.Min(mn, p); mx = Vector3.Max(mx, p);
            }
            return mx - mn;
        }

        /// <summary>Instance matrix: kit clump re-centred, local +x along alongUV, local +z the seaward side, at (u, v), y = H.</summary>
        static Matrix4x4 G01Matrix(G01Variant v, Vector2 at, Vector2 alongUV, float jitterDeg, Vector3 scale)
        {
            var w0 = UV(at.x, at.y, s_h); var wa = UV(at.x + alongUV.x, at.y + alongUV.y, s_h) - w0; wa.y = 0f; wa.Normalize();
            var wn = UV(at.x + alongUV.y, at.y - alongUV.x, s_h) - w0; wn.y = 0f; wn.Normalize();   // seaward normal (rotate along by +90 in u,v)
            var rot = Quaternion.LookRotation(wn, Vector3.up) * Quaternion.Euler(0f, jitterDeg, 0f);
            return Matrix4x4.TRS(w0, rot, scale) * Matrix4x4.Translate(-v.centre);
        }

        /// <summary>Footprint corners (u, v) of one instance (bbox of the kit clump under the matrix).</summary>
        static Vector2[] G01Corners(G01Variant v, Matrix4x4 m)
        {
            var c = new Vector2[4];
            for (int i = 0; i < 4; i++)
            {
                var lp = new Vector3(v.centre.x + ((i & 1) == 0 ? -v.ext.x : v.ext.x), v.centre.y, v.centre.z + ((i & 2) == 0 ? -v.ext.z : v.ext.z));
                c[i] = WorldToUV(m.MultiplyPoint3x4(lp));
            }
            return c;
        }

        static string CombineG01(Transform parent, string nodeName, string assetTag, Dictionary<int, List<Matrix4x4>> byVariant)
        {
            var vars = G01Variants();
            var node = new GameObject(nodeName).transform; node.SetParent(parent, false);
            int renderers = 0, tris = 0, inst = 0;
            foreach (var kv in byVariant.OrderBy(k => k.Key))
            {
                if (kv.Value.Count == 0) continue;
                var v = vars[kv.Key]; var ci = new List<CombineInstance>();
                foreach (var m in kv.Value) foreach (var mesh in v.meshes) ci.Add(new CombineInstance { mesh = mesh, transform = m });
                inst += kv.Value.Count;
                var combined = new Mesh { name = $"BV3S3_{assetTag}_G01_{kv.Key + 2:00}", indexFormat = UnityEngine.Rendering.IndexFormat.UInt32 };
                combined.CombineMeshes(ci.ToArray(), true, true); combined.RecalculateBounds();
                // same base-only calibration gain as the ground grass, on this combined copy's vertex colours (material untouched)
                var cols = combined.colors; for (int ii = 0; ii < cols.Length; ii++) cols[ii] = new Color(cols[ii].r * GrassMul.x, cols[ii].g * GrassMul.y, cols[ii].b * GrassMul.z, cols[ii].a); combined.colors = cols;
                combined = Keep(combined, $"{OutDir}/BV3S3_{assetTag}_G01_{kv.Key + 2:00}.asset");
                var go = new GameObject($"G01_GrassClump_{kv.Key + 2:00}"); go.transform.SetParent(node, false);
                go.AddComponent<MeshFilter>().sharedMesh = combined;
                var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = v.mat; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                renderers++; tris += combined.triangles.Length / 3;
            }
            return $"{nodeName}: {inst} instances, {renderers} renderers, {tris} tris";
        }

        /// <summary>D4 A: clusters along the clean grass outline, footprint kept off legal plots, tips over the sand.</summary>
        static string BuildG01Edge(Transform parent, string tag, Curve c, List<Col> fine, float a0, float a1, List<Rect> legal, out List<Vector2> clusters)
        {
            var vars = G01Variants();
            var rng = new System.Random(Seed + 51);
            float R(float x, float y) => x + (float)rng.NextDouble() * (y - x);
            clusters = new List<Vector2>();
            var byVariant = new Dictionary<int, List<Matrix4x4>>();
            var covered = new List<Vector2>();
            float minExposed = float.MaxValue, maxTip = 0f, minTip = float.MaxValue, minRootLegal = float.MaxValue, maxRootIn = 0f; int dropped = 0, nClusters = 0, nInst = 0;
            Col ColAt(float a) { int lo = 0, hi = fine.Count - 1; while (hi - lo > 1) { int m = (lo + hi) / 2; if (fine[m].a <= a) lo = m; else hi = m; } return fine[lo]; }
            float pos = a0 + R(0f, 1f); int prevVar = -1;
            while (pos < a1)
            {
                float len = R(0.8f, 1.8f); if (pos + len > a1) break;
                int n = 5 + rng.Next(3); bool any = false; float spanLo = float.MaxValue, spanHi = float.MinValue;
                for (int k = 0; k < n; k++)
                {
                    int vi; do vi = rng.Next(vars.Count); while (vi == prevVar && vars.Count > 1); prevVar = vi;
                    var v = vars[vi];
                    float halfLen = v.ext.x * G01Scale.x, inner = Mathf.Max(0f, len - 2f * halfLen);   // keep the footprint inside the cluster span
                    float a = pos + halfLen + inner * (k + 0.5f) / n + R(-0.1f, 0.1f) * inner;
                    var q = ColAt(a);
                    float halfAcross = v.ext.z * G01Scale.z;
                    float tip = rng.NextDouble() < 0.1 ? R(0.40f, 0.50f) : R(0.15f, 0.40f);
                    tip = Mathf.Min(tip, q.nw - MinExposedSand);
                    float centreS = tip - halfAcross;
                    var along = new Vector2(-q.n.y, q.n.x);
                    bool ok = false; Matrix4x4 m = default; Vector2[] corners = null;
                    for (int tries = 0; tries < 6 && !ok; tries++)
                    {
                        var at = q.p + q.n * centreS + along * R(-0.05f, 0.05f);
                        m = G01Matrix(v, at, along, R(-12f, 12f), G01Scale);
                        corners = G01Corners(v, m);
                        float worst = corners.Min(cn => legal.Min(r => RectDist(cn, r)));
                        ok = worst > 0.02f && tip >= 0.10f;
                        if (!ok) { tip = Mathf.Min(tip + 0.06f, Mathf.Min(0.5f, q.nw - MinExposedSand)); centreS = tip - halfAcross; }
                    }
                    if (ok)
                    {
                        // measured footprint tip (with the yaw jitter) must leave >= 2.4 m sand and stay <= 0.5 m past the edge
                        float tipNow = corners.Max(cn => Vector2.Dot(cn - q.p, q.n));
                        float over = Mathf.Max(tipNow - (q.nw - MinExposedSand), tipNow - 0.5f);
                        if (over > 0f)
                        {
                            var shift = WorldDelta(-q.n * (over + 0.01f));
                            m = Matrix4x4.Translate(shift) * m; corners = G01Corners(v, m);
                            ok = corners.Min(cn => legal.Min(r => RectDist(cn, r))) > 0.02f;
                        }
                    }
                    if (!ok) { dropped++; continue; }
                    if (!byVariant.TryGetValue(vi, out var list)) byVariant[vi] = list = new List<Matrix4x4>();
                    if (EnableG01) list.Add(m); any = true; nInst++;
                    float tipS = corners.Max(cn => Vector2.Dot(cn - q.p, q.n)), rootS = corners.Min(cn => Vector2.Dot(cn - q.p, q.n));
                    maxTip = Mathf.Max(maxTip, tipS); minTip = Mathf.Min(minTip, tipS); maxRootIn = Mathf.Max(maxRootIn, -rootS);
                    minExposed = Mathf.Min(minExposed, q.nw - Mathf.Max(0f, tipS));
                    minRootLegal = Mathf.Min(minRootLegal, corners.Min(cn => legal.Min(r => RectDist(cn, r))));
                    float lo2 = corners.Min(cn => Vector2.Dot(cn - q.p, along)) + q.a, hi2 = corners.Max(cn => Vector2.Dot(cn - q.p, along)) + q.a;
                    spanLo = Mathf.Min(spanLo, lo2); spanHi = Mathf.Max(spanHi, hi2);
                }
                if (any) { clusters.Add(new Vector2(pos, pos + len)); covered.Add(new Vector2(spanLo, spanHi)); nClusters++; }
                pos += len + (rng.NextDouble() < 0.10 ? R(2f, 3f) : R(0.5f, 1.4f));
            }
            var cov = new List<float>();
            for (float w = a0; w + 12f <= a1; w += 12f)
            {
                var spans = covered.Where(s => s.y > w && s.x < w + 12f).Select(s => new Vector2(Mathf.Max(w, s.x), Mathf.Min(w + 12f, s.y))).OrderBy(s => s.x).ToList();
                float sum = 0f, cur = w;
                foreach (var s in spans) { float lo = Mathf.Max(cur, s.x); if (s.y > lo) { sum += s.y - lo; cur = s.y; } }
                cov.Add(sum / 12f);
            }
            float per12 = nClusters / Mathf.Max(1f, (a1 - a0) / 12f);
            string res = EnableG01 ? CombineG01(parent, "G01_Edge", tag + "_Edge", byVariant) : "G01_Edge: off (EnableG01=false), " + nClusters + " spans kept as pebble anchors";
            G01Report.AppendLine($"G01 edge {tag}: clusters {nClusters} ({per12:F1} per 12 m), instances {nInst}, dropped {dropped}, footprint tip beyond edge {minTip:F2}..{maxTip:F2} m, footprint root into grass up to {maxRootIn:F2} m, " +
                $"min exposed sand behind tips {minExposed:F2} m, min footprint->legal plots {minRootLegal:F3} m, edge coverage per 12 m {(cov.Count > 0 ? cov.Min() : 0f):P0}..{(cov.Count > 0 ? cov.Max() : 0f):P0} (mean {(cov.Count > 0 ? cov.Average() : 0f):P0}, {cov.Count} windows)");
            return res;
        }

        /// <summary>D4 B: irregular 2-5 m patches on non-buildable grass (forest edge band, coastal grass off legal plots), per state.</summary>
        static string BuildG01Area(Transform parent, BaseV3EnvTestState state, Curve shore, List<Vector2> trees, List<Rect> forbidden)
        {
            var vars = G01Variants();
            bool cap = state == BaseV3EnvTestState.Test_Cap15x15;
            var blocked = new List<Rect>();   // current town / district plot footprints + 0.5 m
            foreach (var p in BaseTownLayout.Plots) blocked.Add(GridRectToUV(p.MinX, p.MaxX, p.MinZ, p.MaxZ, 0.5f));
            foreach (var p in BaseTownLayout.DistrictPlots) blocked.Add(GridRectToUV(p.MinX, p.MaxX, p.MinZ, p.MaxZ, 0.5f));
            float Forb(Vector2 q) { float d = 1e9f; foreach (var r in forbidden) d = Mathf.Min(d, RectDist(q, r)); return d; }
            bool TreeNear(Vector2 q, float r) => trees.Any(t => (t - q).sqrMagnitude < r * r);
            var rng = new System.Random(Seed + 77 + (int)state);
            float R(float x, float y) => x + (float)rng.NextDouble() * (y - x);
            var byVariant = new Dictionary<int, List<Matrix4x4>>(); int blobs = 0, inst = 0;
            const float cell = 5f;
            for (int i = -10; i <= 10; i++)
                for (int j = -10; j <= 10; j++)
                {
                    var cpos = new Vector2((i + 0.5f) * cell + (Hash(i, j, 91) - 0.5f) * 3f, (j + 0.5f) * cell + (Hash(i, j, 92) - 0.5f) * 3f);
                    if (Hash(i, j, 93) > 0.30f) continue;
                    float d = Forb(cpos), gCoast = G(cpos.x, cap) - cpos.y;
                    bool forestEdge = d >= 1.0f && d <= 12f && gCoast > 2f;
                    bool coastal = gCoast >= 0.3f && gCoast <= 2.0f && d > 0.5f;
                    if (!forestEdge && !coastal) continue;
                    float radius = R(1.0f, 2.5f); blobs++;
                    int n = Mathf.RoundToInt(Mathf.PI * radius * radius * R(0.3f, 0.6f));
                    for (int k = 0; k < n; k++)
                    {
                        float ang = R(0f, Mathf.PI * 2f), rr = radius * Mathf.Sqrt(R(0f, 1f));
                        if (R(0f, 1f) < Mathf.SmoothStep(0f, 1f, rr / radius) * 0.7f) continue;   // thin toward the rim
                        var q = cpos + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * rr * (0.75f + 0.5f * ValueNoise(ang * 1.3f, i + j, 94));
                        int vi = rng.Next(vars.Count); var v = vars[vi]; float yaw = R(0f, 6.283f);
                        var m = G01Matrix(v, q, new Vector2(Mathf.Cos(yaw), Mathf.Sin(yaw)), 0f, new Vector3(0.3f, 0.6f, 0.35f));
                        var corners = G01Corners(v, m);
                        if (corners.Any(cn => Forb(cn) < 0.3f || blocked.Any(b => b.Contains(cn)) || G(cn.x, cap) - cn.y < 0.1f)) continue;
                        if (TreeNear(q, 0.9f)) continue;
                        if (!byVariant.TryGetValue(vi, out var list)) byVariant[vi] = list = new List<Matrix4x4>();
                        list.Add(m); inst++;
                    }
                }
            string tag = StateTag(state);
            G01Report.AppendLine($"G01 area {tag}: {blobs} patches, {inst} instances");
            return CombineG01(parent, "G01_Area", tag + "_Area", byVariant);
        }

        /// <summary>World-space translation for a (u, v) displacement.</summary>
        static Vector3 WorldDelta(Vector2 duv) => UV(duv.x, duv.y, 0f) - UV(0f, 0f, 0f);

        static Rect GridRectToUV(float gx0, float gx1, float gz0, float gz1, float pad)
        {
            float v0 = gx0 - s_origin.x, v1 = gx1 - s_origin.x, u0 = -(gz1 - s_origin.y), u1 = -(gz0 - s_origin.y);
            return Rect.MinMaxRect(u0 - pad, v0 - pad, u1 + pad, v1 + pad);
        }

        static Material WaterMaterial()
        {
            string path = OutDir + "/BV3S3_BaseWater.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = AssetDatabase.LoadAssetAtPath<Shader>(WaterShaderPath);
                if (shader == null || ShaderUtil.ShaderHasError(shader)) throw new InvalidOperationException("Lab/LabBaseWater unavailable");
                mat = new Material(shader) { name = "BV3S3_BaseWater" };
                AssetDatabase.CreateAsset(mat, path);
            }
            // D3 C colour blocks: (u, v) centre, half axes along shore / seaward, relative brightness
            var blocks = new[] { (-13f, 28f, 5f, 2.5f, 0.05f), (-3f, 32f, 7f, 3.5f, -0.06f), (10f, 27f, 4.5f, 2.2f, 0.04f), (20f, 35f, 6f, 3f, -0.05f) };
            var amt = Vector4.zero;
            for (int i = 0; i < 4; i++)
            {
                var b = blocks[i]; var w = UV(b.Item1, b.Item2 + N(b.Item1) * 0.5f, 0f);   // step 3d: centre moves out with the waterline
                mat.SetVector("_Block" + i, new Vector4(w.x, w.z, b.Item3, b.Item4)); amt[i] = b.Item5;
            }
            mat.SetVector("_BlockAmount", amt);
            var o = UV(0f, 0f, 0f); var au = UV(1f, 0f, 0f) - o; var av = UV(0f, 1f, 0f) - o;
            mat.SetVector("_AxisAlong", new Vector4(au.x, au.z, 0f, 0f)); mat.SetVector("_AxisSea", new Vector4(av.x, av.z, 0f, 0f));
            EditorUtility.SetDirty(mat);
            return mat;
        }

        /// <summary>Column grid: cols x (rows + 1) vertices in (u, v, y); up-facing triangles; mesh asset kept in place.</summary>
        internal static string Grid(Transform parent, string name, Material mat, int cols, int rows,
            Func<int, int, (float u, float v, float y)> vertex, Func<int, int, float, float, Color> colour,
            Func<int, int, float, float, Vector2> uv1, string assetPath, List<Col> colInfo, float[] sectionU, string sectionTag)
        {
            var verts = new List<Vector3>(cols * (rows + 1)); var colours = new List<Color>(); var uv1s = new List<Vector2>();
            var secCols = new Dictionary<int, float>();
            if (colInfo != null && sectionU != null)
                foreach (float su in sectionU)
                {
                    int best = 0; for (int i = 1; i < colInfo.Count; i++) if (Mathf.Abs(colInfo[i].u - su) < Mathf.Abs(colInfo[best].u - su)) best = i;
                    secCols[best] = su;
                }
            for (int i = 0; i < cols; i++)
                for (int k = 0; k <= rows; k++)
                {
                    var (u, v, y) = vertex(i, k);
                    verts.Add(UV(u, v, y));
                    if (colour != null) colours.Add(colour(i, k, u, v));
                    if (uv1 != null) uv1s.Add(uv1(i, k, u, v));
                    if (secCols.TryGetValue(i, out float su))
                    {
                        var q = colInfo[i]; float s = Vector2.Dot(new Vector2(u, v) - q.p, q.n);
                        s_sectionRows.Add("{\"sec\":\"" + sectionTag + "@u" + su.ToString(System.Globalization.CultureInfo.InvariantCulture) + "\",\"s\":" + F(s) + ",\"u\":" + F(u) + ",\"v\":" + F(v) + ",\"y\":" + F(y) +
                            ",\"G\":" + F(q.p.y) + ",\"N\":" + F(q.nw) + ",\"leaf\":" + F(q.leaf) + "}");
                    }
                }
            var tris = new List<int>(cols * rows * 6);
            for (int i = 0; i < cols - 1; i++)
                for (int k = 0; k < rows; k++)
                {
                    int a = i * (rows + 1) + k, b = a + 1, c = a + rows + 1, d = c + 1;
                    Tri(tris, verts, a, b, c); Tri(tris, verts, b, d, c);
                }
            var mesh = new Mesh { name = Path.GetFileNameWithoutExtension(assetPath) };
            if (verts.Count > 65000) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;
            mesh.SetVertices(verts); mesh.SetTriangles(tris, 0);
            if (colour != null) mesh.SetColors(colours);
            mesh.SetUVs(0, verts.Select(p => new Vector2(p.x, p.z)).ToList());
            if (uv1 != null) mesh.SetUVs(1, uv1s);
            mesh.RecalculateNormals(); mesh.RecalculateBounds();
            mesh = Keep(mesh, assetPath);
            var go = new GameObject(name); go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = mat; r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            return $"{name}:{tris.Count / 3}t";
        }

        static string F(float x) => x.ToString("F4", System.Globalization.CultureInfo.InvariantCulture);

        static void Tri(List<int> tris, List<Vector3> v, int a, int b, int c)
        {
            var n = Vector3.Cross(v[b] - v[a], v[c] - v[a]);
            if (n.sqrMagnitude < 1e-12f) return;
            if (n.y < 0f) { tris.Add(a); tris.Add(c); tris.Add(b); } else { tris.Add(a); tris.Add(b); tris.Add(c); }
        }

        // ── forest (D3 F) ────────────────────────────────────────────────────
        static readonly string[] PalmNames = { "BigLeafPalm", "BigLeafPalm_02", "BigLeafPalm_03" };

        internal static float RectDist(Vector2 p, Rect r)
        {
            float dx = Mathf.Max(r.xMin - p.x, 0f, p.x - r.xMax), dy = Mathf.Max(r.yMin - p.y, 0f, p.y - r.yMax);
            if (dx > 0f || dy > 0f) return Mathf.Sqrt(dx * dx + dy * dy);
            return -Mathf.Min(Mathf.Min(p.x - r.xMin, r.xMax - p.x), Mathf.Min(p.y - r.yMin, r.yMax - p.y));
        }

        static float Hash(int a, int b, int c)
        {
            unchecked
            {
                uint h = (uint)(a * 73856093) ^ (uint)(b * 19349663) ^ (uint)(c * 83492791) ^ (uint)Seed;
                h ^= h >> 16; h *= 0x7feb352d; h ^= h >> 15; h *= 0x846ca68b; h ^= h >> 16;
                return (h & 0xffffff) / 16777216f;
            }
        }

        static float ValueNoise(float x, float y, int salt)
        {
            int ix = Mathf.FloorToInt(x), iy = Mathf.FloorToInt(y); float fx = x - ix, fy = y - iy;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            return Mathf.Lerp(Mathf.Lerp(Hash(ix, iy, salt), Hash(ix + 1, iy, salt), fx), Mathf.Lerp(Hash(ix, iy + 1, salt), Hash(ix + 1, iy + 1, salt), fx), fy);
        }

        struct Candidate { public Vector2 uv; public int variant; public float yaw; public float accept; }

        /// <summary>World-fixed candidates: one per 3.8 m cell, jitter <= 0.8 m per axis, fixed order, 2.5 m spacing applied once for all states.</summary>
        static List<Candidate> Candidates()
        {
            const float cell = 3.8f; var raw = new List<Candidate>();
            for (int i = -19; i <= 19; i++)
                for (int j = -19; j <= 19; j++)
                {
                    float vh = Hash(i, j, 3);
                    raw.Add(new Candidate
                    {
                        uv = new Vector2((i + 0.5f) * cell + (Hash(i, j, 1) * 2f - 1f) * 0.8f, (j + 0.5f) * cell + (Hash(i, j, 2) * 2f - 1f) * 0.8f),
                        variant = vh < 0.4f ? 0 : vh < 0.7f ? 1 : 2, yaw = Hash(i, j, 4) * 360f, accept = Hash(i, j, 5)
                    });
                }
            var kept = new List<Candidate>();
            foreach (var c in raw) if (!kept.Any(k => (k.uv - c.uv).sqrMagnitude < 2.5f * 2.5f)) kept.Add(c);
            return kept;
        }

        static string BuildForest(Transform node, BaseV3EnvTestState state, List<Candidate> candidates, Curve shore, Dictionary<BaseV3EnvTestState, List<Vector2>> treesOut)
        {
            var parent = new GameObject(ForestName(state)).transform; parent.SetParent(node, false);
            var treeParent = new GameObject("T01").transform; treeParent.SetParent(parent, false);
            bool cap = state == BaseV3EnvTestState.Test_Cap15x15;
            var reference = cap ? Rect.MinMaxRect(-30, -30, 30, 30) : Rect.MinMaxRect(-18, -18, 18, 18);
            var forbidden = new List<Rect>();
            bool beach = state == BaseV3EnvTestState.Test_Center3x3_BeachRows;
            if (state == BaseV3EnvTestState.Test_Center3x3 || beach) { forbidden.Add(Rect.MinMaxRect(-6, -6, 6, 6)); forbidden.Add(Rect.MinMaxRect(-18, 6, 18, 18)); }
            else forbidden.Add(reference);

            var foot = new Rect[3];
            for (int i = 0; i < 3; i++)
            {
                var tmp = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(PalmDir + PalmNames[i] + ".prefab"));
                tmp.hideFlags = HideFlags.HideAndDontSave; tmp.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
                var bb = new Bounds(); bool first = true;
                foreach (var rr in tmp.GetComponentsInChildren<Renderer>()) { if (first) { bb = rr.bounds; first = false; } else bb.Encapsulate(rr.bounds); }
                foot[i] = Rect.MinMaxRect(bb.min.x, bb.min.z, bb.max.x, bb.max.z);
                Object.DestroyImmediate(tmp);
            }
            float Forb(Vector2 p) { float d = 1e9f; foreach (var r in forbidden) d = Mathf.Min(d, RectDist(p, r)); return d; }
            float CrownClear(Vector2 t, int variant, float yaw)
            {
                var f = foot[variant]; var rot = Quaternion.Euler(0f, yaw, 0f); var w0 = UV(t.x, t.y, s_h); float min = 1e9f;
                for (int a = 0; a <= 2; a++)
                    for (int b = 0; b <= 2; b++)
                    {
                        if (a == 1 && b == 1) continue;
                        var local = new Vector3(Mathf.Lerp(f.xMin, f.xMax, a * 0.5f), 0f, Mathf.Lerp(f.yMin, f.yMax, b * 0.5f));
                        min = Mathf.Min(min, Forb(WorldToUV(w0 + rot * local)));
                    }
                return min;
            }

            var placed = new List<Vector2>(); int[] count = new int[3]; float minTrunk = 1e9f, minCrown = 1e9f; int crownRejected = 0;
            foreach (var c in candidates)
            {
                var p = c.uv; float d = Forb(p);
                if (d < 3f) continue;
                float limit = 24f + 6f * ValueNoise(p.x / 9f, p.y / 9f, 11);          // irregular outer edge of the sample forest
                if (RectDist(p, reference) > limit && !(cap && SeenByCapCameras(p))) continue;
                float gCoast = beach ? BeachCoastDist(p) : G(p.x, cap) - p.y;          // landward distance to the grass outline
                float coastMin = beach ? 3f : 6f;                                      // beach rows: forest edge from 3 m off the sand
                if (gCoast < coastMin) continue;
                float prob = d < 6f ? 0.40f : d < 10f ? 0.72f : 0.92f;
                prob *= Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(coastMin, coastMin + 8f, gCoast)); // ends retreat from the coast
                if (c.accept >= prob) continue;
                float yaw = c.yaw, clear = CrownClear(p, c.variant, yaw);
                for (int t = 1; t < 4 && clear < 0.5f; t++) { float y2 = c.yaw + 90f * t, c2 = CrownClear(p, c.variant, y2); if (c2 > clear) { clear = c2; yaw = y2; } }
                if (clear < 0.5f) { crownRejected++; continue; }
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(PalmDir + PalmNames[c.variant] + ".prefab"), node.gameObject.scene);
                inst.transform.SetParent(treeParent, false);
                inst.transform.SetPositionAndRotation(UV(p.x, p.y, s_h), Quaternion.Euler(0f, yaw, 0f));
                placed.Add(p); count[c.variant]++; minTrunk = Mathf.Min(minTrunk, d); minCrown = Mathf.Min(minCrown, clear);
            }
            treesOut[state] = placed;
            string grass = BuildFarGrass(parent, state, shore, placed);
            if (EnableG01) grass += "; " + BuildG01Area(parent, state, shore, placed, forbidden);
            return $"{ForestName(state)}: {placed.Count} T01 ({count[0]}/{count[1]}/{count[2]}), trunk->no-tree edge min {minTrunk:F2} m, crown->no-tree edge min {minCrown:F2} m, crownRejected {crownRejected}; {grass}";
        }

        /// <summary>Open-land grass for one state (u ±130, v -130 up under the shore strip), canopy darkening baked per state (D3 F understory, ~10 %).</summary>
        /// <summary>Step 3d: cap-state acceptance cameras (max zoom FOV 60 / d 42 at the cap ends and far corners, HQ max zoom),
        /// tested against the ground point and the crown top with one crown (3 m) of margin.</summary>
        static bool SeenByCapCameras(Vector2 p)
        {
            var foci = new[] { new Vector2(-30f, 30f), new Vector2(30f, 30f), new Vector2(-30f, -30f), new Vector2(30f, -30f), new Vector2(-1.005f, 0.495f) };
            var dir = new Vector3(0f, 23.81f, -13.75f).normalized;
            float tanV = Mathf.Tan(30f * Mathf.Deg2Rad), tanH = tanV * (1080f / 2340f);
            foreach (var f in foci)
            {
                var target = UV(f.x, f.y, 0f); var pos = target + dir * 42f;
                var fw = (target - pos).normalized; var rt = Vector3.Cross(Vector3.up, fw).normalized; var up = Vector3.Cross(fw, rt);
                foreach (float y in new[] { 0f, 4.8f })
                {
                    var d = UV(p.x, p.y, y) - pos; float z = Vector3.Dot(d, fw); if (z <= 0f) continue;
                    if (Mathf.Abs(Vector3.Dot(d, rt)) <= z * tanH + 3f && Mathf.Abs(Vector3.Dot(d, up)) <= z * tanV + 3f) return true;
                }
            }
            return false;
        }

        static string BuildFarGrass(Transform parent, BaseV3EnvTestState state, Curve shore, List<Vector2> trees)
        {
            bool cap = state == BaseV3EnvTestState.Test_Cap15x15;
            var grassMat = Load<Material>(KitDir + "MosaicGrass.mat");
            var cols = new List<float>();
            for (float u = -Coverage; u < -60f; u += 5f) cols.Add(u);
            for (float u = -60f; u <= 60f + 1e-3f; u += 1f) cols.Add(u);
            for (float u = 65f; u <= Coverage + 1e-3f; u += 5f) cols.Add(u);
            // inner boundary of the shore strip (s = -2 along the normal), as v(u)
            var inner = new List<Vector2>(); for (float a = 0f; a <= shore.Length; a += 0.25f) inner.Add(shore.At(a) - shore.Normal(a) * 2f);
            bool beach = state == BaseV3EnvTestState.Test_Center3x3_BeachRows;
            float Top(float u)
            {
                if (beach) return GBeach(u) - 2f + 0.08f;   // matches the beach grass edge strip (straight-v columns)
                int lo = 0, hi = inner.Count - 1; while (hi - lo > 1) { int m = (lo + hi) / 2; if (inner[m].x <= u) lo = m; else hi = m; }
                float t = Mathf.InverseLerp(inner[lo].x, inner[hi].x, u); return Mathf.Lerp(inner[lo].y, inner[hi].y, t) + 0.08f;
            }
            var bucket = new Dictionary<(int, int), List<Vector2>>();
            foreach (var t in trees) { var k = (Mathf.FloorToInt(t.x / 4f), Mathf.FloorToInt(t.y / 4f)); if (!bucket.TryGetValue(k, out var l)) bucket[k] = l = new List<Vector2>(); l.Add(t); }
            float Canopy(float u, float v)
            {
                float cov = 0f; int bx = Mathf.FloorToInt(u / 4f), by = Mathf.FloorToInt(v / 4f);
                for (int x = bx - 1; x <= bx + 1; x++) for (int y = by - 1; y <= by + 1; y++)
                        if (bucket.TryGetValue((x, y), out var l)) foreach (var t in l) cov = Mathf.Max(cov, 1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1.2f, 3.6f, Vector2.Distance(t, new Vector2(u, v)))));
                return cov;
            }
            const int rowsFar = 14, rowsNear = 90;
            string tag = StateTag(state);
            return Grid(parent, "GrassFar", grassMat, cols.Count, rowsFar + rowsNear, (i, k) =>
            {
                float u = cols[i], top = Top(u);
                float v = k <= rowsFar ? Mathf.Lerp(-Coverage, -60f, k / (float)rowsFar) : Mathf.Lerp(-60f, top, (k - rowsFar) / (float)rowsNear);
                return (u, v, s_h - 0.002f);
            }, (i, k, u, v) =>
            {
                var col = GrassColour(u, v, 99f, u);
                float dark = 1f - (1f - ForestFloorY) * Canopy(u, v);
                return new Color(col.r * dark, col.g * dark, col.b * dark, 1f);
            }, null, $"{OutDir}/BV3S3_{tag}_GrassFar.asset", null, null, null);
        }

        // ── understory sample (pending approval) ─────────────────────────────
        static string BuildUnderstorySample(Transform node, List<Vector2> trees)
        {
            var parent = new GameObject(UnderstoryNode).transform; parent.SetParent(node, false);
            var paths = new[]
            {
                "Assets/Art/Expedition/VegetationLibrary/ApprovedGroundcover/GC01_Spike.prefab",
                "Assets/Art/Expedition/VegetationLibrary/ApprovedGroundcover/GC02_LeafClump.prefab",
                "Assets/Art/Expedition/VegetationLibrary/ApprovedGroundcover/GC03_Rosette.prefab",
                "Assets/Art/Lab/JungleLab/ReferencePlants/Prefabs/Ref01_RoundedShrub.prefab"
            };
            var region = Rect.MinMaxRect(-10f, -34f, 10f, -21.5f);   // ~20 m of the online back forest edge
            var local = trees.Where(t => region.Contains(t)).ToList();
            var rng = new System.Random(Seed + 31);
            float R(float x, float y) => x + (float)rng.NextDouble() * (y - x);
            bool FreeOfTrunks(Vector2 p, float r) => local.All(t => (t - p).sqrMagnitude > r * r);
            int[] n = new int[4]; int tris = 0;
            void Put(int id, Vector2 p)
            {
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(paths[id]), node.gameObject.scene);
                inst.transform.SetParent(parent, false);
                inst.transform.SetPositionAndRotation(UV(p.x, p.y, s_h), Quaternion.Euler(0f, R(0f, 360f), 0f) * inst.transform.localRotation);
                foreach (var mf in inst.GetComponentsInChildren<MeshFilter>()) if (mf.sharedMesh) tris += mf.sharedMesh.triangles.Length / 3;
                n[id]++;
            }
            // GC02 / GC03 in groups between trunks under the canopy
            for (int g = 0; g < 40 && n[1] < 30; g++)
            {
                var c = new Vector2(R(region.xMin, region.xMax), R(-33f, -24f)); if (!FreeOfTrunks(c, 0.9f)) continue;
                if (local.All(t => (t - c).sqrMagnitude > 3.6f * 3.6f)) continue;   // stay under some canopy
                int id = rng.NextDouble() < 0.6 ? 1 : 2, m = id == 1 ? 3 + rng.Next(3) : 2 + rng.Next(2);
                for (int k = 0; k < m; k++) { var p = c + new Vector2(R(-0.8f, 0.8f), R(-0.8f, 0.8f)); if (FreeOfTrunks(p, 0.6f)) Put(id, p); }
            }
            // GC01 sparse along the forest edge
            for (int k = 0; k < 9; k++) { var p = new Vector2(R(region.xMin, region.xMax), R(-23.2f, -21.6f)); if (FreeOfTrunks(p, 0.6f)) Put(0, p); }
            // B01 in canopy gaps at the edge, few
            for (int k = 0, placed = 0; k < 40 && placed < 3; k++)
            {
                var p = new Vector2(R(region.xMin, region.xMax), R(-27f, -22.5f));
                if (!FreeOfTrunks(p, 2.6f)) continue;
                Put(3, p); placed++;
            }
            parent.gameObject.SetActive(false);
            return $"{UnderstoryNode}: GC01 {n[0]}, GC02 {n[1]}, GC03 {n[2]}, B01 {n[3]}, ~{tris} tris (inactive by default)";
        }

        static string BuildScaleCompare(Transform node)
        {
            var parent = new GameObject("T01_ScaleCompare_TEST").transform; parent.SetParent(node, false);
            var hqWorld = UV(0f, 0f, s_h);
            float[] xs = { 4.8f, 8.6f, 12.4f };
            for (int i = 0; i < 3; i++)
            {
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(Load<GameObject>(PalmDir + PalmNames[i] + ".prefab"), node.gameObject.scene);
                inst.transform.SetParent(parent, false);
                inst.transform.SetPositionAndRotation(new Vector3(xs[i], s_h, hqWorld.z - 1.0f), Quaternion.Euler(0f, 200f, 0f));
            }
            parent.gameObject.SetActive(false);
            return "T01_ScaleCompare_TEST: 3 palms at world z " + (hqWorld.z - 1f).ToString("F2");
        }

        // ── helpers ──────────────────────────────────────────────────────────
        internal static Mesh Keep(Mesh mesh, string path)
        {
            var existing = AssetDatabase.LoadAssetAtPath<Mesh>(path);
            if (existing == null) { AssetDatabase.CreateAsset(mesh, path); return mesh; }
            existing.Clear();
            EditorUtility.CopySerialized(mesh, existing);
            existing.name = Path.GetFileNameWithoutExtension(path);
            EditorUtility.SetDirty(existing);
            Object.DestroyImmediate(mesh);
            return existing;
        }

        internal static T Load<T>(string path) where T : Object
        {
            var a = AssetDatabase.LoadAssetAtPath<T>(path);
            if (a == null) throw new InvalidOperationException("Missing asset " + path);
            return a;
        }

        internal static void Folder(string path)
        {
            if (AssetDatabase.IsValidFolder(path)) return;
            string parent = Path.GetDirectoryName(path).Replace('\\', '/');
            Folder(parent);
            AssetDatabase.CreateFolder(parent, Path.GetFileName(path));
        }
    }
}
