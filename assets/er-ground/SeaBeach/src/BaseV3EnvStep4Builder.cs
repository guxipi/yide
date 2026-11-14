using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;
using S3 = Editor.Setup.BaseV3Env.BaseV3EnvStep3Builder;

namespace Editor.Setup.BaseV3Env
{
    /// <summary>
    /// Base v3 terrain step 4b, state Start_3x3 (target picture Library/BaseV3Env/refs_bb/gou_1113_6.png, 勾哥 11-13 instructions):
    /// opened grass with a clean gentle arc (fine ragged turf edge, flush) onto one clean sand beach (no rocks / plants on it), Boom Beach colours,
    /// a band of round-crowned T05 trees hugging the camp (8-11 m deep, smooth outer arc), soft ground fog over everything beyond the band,
    /// one recoloured J01 cliff run behind, the 5-stop shore water ramp. Colours live in Library/BaseV3Env/step4b_calib.json (vertex colours /
    /// material colours, re-solved on the base camera). Since 11-13 the default base environment: <c>3DSceneContainer/BaseSceneRoot/EnvironmentV3</c>; idempotent.
    /// </summary>
    public static class BaseV3EnvStep4Builder
    {
        /// <summary>Default base environment root, child of <see cref="BaseRootPath"/> (scene path, HomeScreen).</summary>
        public const string NodeName = "EnvironmentV3";
        public const string BaseRootPath = "3DSceneContainer/BaseSceneRoot";
        /// <summary>Opened-land states the builder knows. Legacy_PlotsCover (TEMPORARY, legacy plot table transition): the opened set covers
        /// every legacy plot footprint + half a cell; once v3 plot data lands, the real opened set drives it. Start_3x3 = preview / reference.</summary>
        public const string StateLegacy = "Legacy_PlotsCover", StateStart = "Start_3x3";
        public const string PlaceholderNode = "Placeholder_Buildings";
        public const string AuditionNode = "Audition_TEST";
        const string OutDir = BaseV3EnvWipBuilder.ArtDir + "/Step4";
        const string KitDir = "Assets/Art/Expedition/JunglePlanet/Generated/J02SurfaceStyleLab/";
        public const string EarthMatPath = KitDir + "DrySand.mat";
        public const string CalibPath = "Library/BaseV3Env/step4b_calib.json";
        const string T05Path = "Assets/Art/Expedition/VegetationLibrary/ApprovedFlora/T05_RosetteLow.prefab";

        const float Ext = 110f, SeaEnd = 130f, LandLift = 0.004f, TrunkFront = 1.2f;
        /// <summary>Crown size levels (x the base scale whose top is treeTop); top level x1.3 stays under 2.9 m.</summary>
        static readonly float[] SizeLevels = { 0.7f, 0.9f, 1.0f, 1.15f, 1.3f };
        /// <summary>Level pick per hash byte (0-255): 10 % / 25 % / 30 % / 25 % / 10 %.</summary>
        static int SizePick(uint b) { b &= 255; return b < 26 ? 0 : b < 90 ? 1 : b < 166 ? 2 : b < 230 ? 3 : 4; }
        /// <summary>Opened 4 m land cells in base (u, v) (cell edges at 2 mod 4). Set by <see cref="Build"/> from the state.</summary>
        static List<Rect> s_open = StartCells();   // (edge tables are rebuilt lazily when it changes)
        static string s_state = StateStart;
        /// <summary>Shore variants (D4 = the seaward district): EnvironmentV3/Shore_D4 when D4 is unlocked, Shore_NoD4 otherwise.</summary>
        public const string D4 = "D4", ShoreD4 = "Shore_D4", ShoreNoD4 = "Shore_NoD4";
        static string s_tag = "";
        static List<Rect> StartCells()
        {
            var l = new List<Rect>();
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) l.Add(new Rect(-6f + 4f * i, -6f + 4f * j, 4f, 4f));
            return l;
        }
        /// <summary>TEMPORARY (legacy plot table transition): smallest set of 4 m cells covering every legacy plot footprint (district plots +
        /// the old type plots) grown by half a cell. grid x = v + HQ x, grid z = HQ z - u (HQ grid centre = HQ plot centre).</summary>
        public static List<Rect> LegacyPlotsCoverCells(out List<string> table, bool includeD4 = true)
        {
            var hq = Meta.Base.Data.BaseTownLayout.Plots.First(q => q.Type == Meta.Base.Data.BuildingType.HQ);
            var set = new HashSet<Vector2Int>(); var rows = new List<string>(); table = rows;
            void Add(string name, float gx, float gz, Vector2Int fp)
            {
                float u0 = hq.GridCenterZ - gz - fp.y * 0.5f, u1 = u0 + fp.y, v0 = gx - hq.GridCenterX - fp.x * 0.5f, v1 = v0 + fp.x;
                var cs = new List<Vector2Int>();
                for (int i = Mathf.FloorToInt((u0 - 0.5f - 2f) / 4f); i <= Mathf.FloorToInt((u1 + 0.5f - 2f - 1e-4f) / 4f); i++)
                    for (int j = Mathf.FloorToInt((v0 - 0.5f - 2f) / 4f); j <= Mathf.FloorToInt((v1 + 0.5f - 2f - 1e-4f) / 4f); j++) cs.Add(new Vector2Int(i, j));
                foreach (var c in cs) set.Add(c);
                rows.Add($"{name} uv({(u0 + u1) * 0.5f:0.##},{(v0 + v1) * 0.5f:0.##}) {fp.x}x{fp.y} cells " + string.Join(" ", cs.Select(c => $"[{4 * c.x + 2},{4 * c.y + 2}]")));
            }
            foreach (var d in Meta.Base.Data.BaseTownLayout.DistrictPlots) if (includeD4 || d.DistrictId != D4) Add($"{d.DistrictId} {d.Label}", d.GridCenterX, d.GridCenterZ, d.Footprint);
            foreach (var o in Meta.Base.Data.BaseTownLayout.Plots) Add("old " + o.Type, o.GridCenterX, o.GridCenterZ, o.Footprint);
            return set.OrderBy(c => c.x).ThenBy(c => c.y).Select(c => new Rect(4f * c.x + 2f, 4f * c.y + 2f, 4f, 4f)).ToList();
        }
        static bool InOpen(Vector2 p) { foreach (var r in s_open) if (r.Contains(p)) return true; return false; }
        static List<Vector2> s_hull;
        /// <summary>Distance from the opened set's convex hull (0 inside): the forest band and the fog are measured from it, so notches between
        /// opened cells stay open camp land.</summary>
        static float HullDist(Vector2 p)
        {
            if (s_hull == null) s_hull = Hull(s_open.SelectMany(r => new[] { r.min, new Vector2(r.xMax, r.yMin), r.max, new Vector2(r.xMin, r.yMax) }).ToList());
            if (InPoly(p, s_hull)) return 0f;
            float dd = float.MaxValue; for (int i = 0; i < s_hull.Count; i++) dd = Mathf.Min(dd, SegDist(p, s_hull[i], s_hull[(i + 1) % s_hull.Count]));
            return dd;
        }
        static float OpenDist(Vector2 p) { float d = float.MaxValue; foreach (var r in s_open) d = Mathf.Min(d, S3.RectDist(p, r)); return d; }
        static float PolyOpenDist(Vector2[] poly) { float d = float.MaxValue; foreach (var r in s_open) d = Mathf.Min(d, PolyRectDist(poly, r)); return d; }
        /// <summary>Bounding rect of the opened set in (u, v).</summary>
        static Rect OpenBounds() => Rect.MinMaxRect(s_open.Min(r => r.xMin), s_open.Min(r => r.yMin), s_open.Max(r => r.xMax), s_open.Max(r => r.yMax));
        /// <summary>Smooth seaward edge of the opened land over u: the start edge v = 6, raised over every cell reaching further seaward and
        /// eased back down over 6 m beyond that cell's u range (no step in the grass edge / shoreline).</summary>
        // 11-13 r3: the seaward edge hugs the opened set's sea side (start edge v = 6 where no cell reaches further) and every corner is a circular
        // fillet: concave corners filled with a FilletR arc (closing), convex corners rounded with min(FilletR, narrowest seaward run / 2) (opening),
        // so a narrow wing reads as a round-headed spit. The waterline follows that edge (see BuildEdgeTables). Both are tabulated over u
        // once per opened set.
        const float FilletR = 5.5f, SideBeach = 2.5f, WaterFilletR = 4f, TabU0 = -130f, TabStep = 0.05f;
        static float[] s_edgeTab, s_waterTab;
        static float[] Dilate(float[] f, Func<int, float> radius)
        {
            var g = new float[f.Length];
            for (int i = 0; i < f.Length; i++)
            {
                float r = radius(i); int k = Mathf.CeilToInt(r / TabStep); float best = float.MinValue;
                for (int d = -k; d <= k; d++) { int q = Mathf.Clamp(i + d, 0, f.Length - 1); float sx = d * TabStep; if (sx * sx > r * r) continue; best = Mathf.Max(best, f[q] + Mathf.Sqrt(r * r - sx * sx)); }
                g[i] = best;
            }
            return g;
        }
        static float[] Erode(float[] f, Func<int, float> radius)
        {
            var g = new float[f.Length];
            for (int i = 0; i < f.Length; i++)
            {
                float r = radius(i); int k = Mathf.CeilToInt(r / TabStep); float best = float.MaxValue;
                for (int d = -k; d <= k; d++) { int q = Mathf.Clamp(i + d, 0, f.Length - 1); float sx = d * TabStep; if (sx * sx > r * r) continue; best = Mathf.Min(best, f[q] - Mathf.Sqrt(r * r - sx * sx)); }
                g[i] = best;
            }
            return g;
        }
        static void BuildEdgeTables()
        {
            int n = Mathf.RoundToInt(2f * -TabU0 / TabStep) + 1; var f = new float[n];
            for (int i = 0; i < n; i++)
            {
                float u = TabU0 + i * TabStep; f[i] = StartSeaEdgeV;
                foreach (var r in s_open) if (u >= r.xMin && u <= r.xMax) f[i] = Mathf.Max(f[i], r.yMax);
            }
            // narrowest seaward run (a wing): its half width caps the convex fillet so the wing keeps its full reach
            float run = float.MaxValue; int start = -1;
            for (int i = 0; i <= n; i++)
            {
                bool up = i < n && f[i] > StartSeaEdgeV + 1e-3f;
                if (up && start < 0) start = i;
                if (!up && start >= 0) { run = Mathf.Min(run, (i - start) * TabStep); start = -1; }
            }
            float rc = FilletR, rv = Mathf.Min(FilletR, run * 0.5f);
            f = Erode(Dilate(f, _ => rc), _ => rc);                       // closing: concave corners -> FilletR arcs
            if (run < float.MaxValue) f = Dilate(Erode(f, _ => rv), _ => rv);   // opening: convex corners -> rv arcs
            s_edgeTab = f;
            // waterline: the start-camp beach depth straight seaward (keeps the sea as close as before in front of the camp), but never
            // closer than SideBeach along the normal (sand wraps a wing's sides), concave corners filled with a WaterFilletR arc
            var w = Dilate(f, _ => SideBeach);
            for (int i = 0; i < n; i++) w[i] = Mathf.Max(w[i], f[i] + BeachDepth(TabU0 + i * TabStep));
            s_waterTab = Erode(Dilate(w, _ => WaterFilletR), _ => WaterFilletR);
        }
        static float Tab(float[] t, float u)
        {
            float x = (u - TabU0) / TabStep; int i = Mathf.Clamp(Mathf.FloorToInt(x), 0, t.Length - 2);
            return Mathf.Lerp(t[i], t[i + 1], Mathf.Clamp01(x - i));
        }
        public static float SeaEdge(float u)
        {
            if (s_edgeTab == null) BuildEdgeTables();
            return Tab(s_edgeTab, u);
        }
        /// <summary>Approximate lit gains (screen linear / vertex colour) used only to seed the calibration file.</summary>
        static readonly Vector3 SandGain = new Vector3(2.14f, 2.05f, 1.62f), GrassGain = new Vector3(1.96f, 1.88f, 1.13f);

        static readonly StringBuilder s_checks = new StringBuilder();
        static JObject s_cal;

        [MenuItem("Tools/Setup/Base V3 Env - Build Default Environment (Legacy_PlotsCover)")] static void MenuBuild() => Debug.Log(Build(StateLegacy));
        [MenuItem("Tools/Setup/Base V3 Env - Build Start_3x3 (preview state)")] static void MenuBuildStart() => Debug.Log(Build(StateStart));

        // ── calibration file ─────────────────────────────────────────────────
        static Vector3 SeedVC(string hex, Vector3 gain) { var l = S3.LinearHex(hex); return new Vector3(l.x / gain.x, l.y / gain.y, l.z / gain.z); }
        static JArray A(Vector3 v) => new JArray(Math.Round(v.x, 5), Math.Round(v.y, 5), Math.Round(v.z, 5));

        static JObject DefaultCal() => new JObject
        {
            ["note"] = "vertex colours are linear rgb; material colours sRGB hex; canopy = per-level multipliers on the T05 vertex colours",
            ["grass"] = A(SeedVC("80AB3F", GrassGain)), ["grassVar"] = 0.05,
            ["forestFloor"] = A(SeedVC("2F6221", GrassGain)),
            ["earth"] = A(SeedVC("A2825E", SandGain)),
            ["sandNear"] = A(SeedVC("E9E3D1", SandGain)), ["sandFar"] = A(SeedVC("E8D3BA", SandGain)),
            ["canopy"] = new JArray(A(new Vector3(1f, 1f, 1f)), A(new Vector3(0.88f, 0.88f, 0.88f)), A(new Vector3(0.76f, 0.76f, 0.76f))),
            ["treeTop"] = 2.8, ["treeCrownSpacing"] = 0.65,
            ["water"] = new JObject { ["c0"] = "#C4CCBD", ["c1"] = "#9CC7B4", ["c2"] = "#68C6B6", ["c3"] = "#43C0B3", ["c4"] = "#27BBB0", ["far"] = "#26677F",
                                      ["stops"] = new JArray(1.3, 3.0, 5.0, 7.0), ["farStart"] = 25.0, ["farEnd"] = 60.0 },
            ["fog"] = "#EEF2F0",
            ["cliffPick"] = new JArray("J01v7_cape-00_06_34", "J01v7_cape-03_07_34"),
            ["cliffTop"] = 5.5,
            ["cliff"] = new JObject { ["bright"] = A(SeedVC("FBD8AA", SandGain)), ["main"] = A(SeedVC("EAC38E", SandGain)), ["mid"] = A(SeedVC("C5986E", SandGain)),
                                      ["dark"] = A(SeedVC("716046", SandGain)), ["crown"] = A(SeedVC("5BA432", GrassGain)) },
        };

        static JObject Cal()
        {
            if (s_cal != null) return s_cal;
            if (!File.Exists(CalibPath)) File.WriteAllText(CalibPath, DefaultCal().ToString());
            s_cal = JObject.Parse(File.ReadAllText(CalibPath));
            foreach (var kv in DefaultCal()) if (s_cal[kv.Key] == null) s_cal[kv.Key] = kv.Value;
            return s_cal;
        }

        static Color VC(JToken t) => new Color(t[0].Value<float>(), t[1].Value<float>(), t[2].Value<float>(), 1f);
        static Color Hx(string h) { ColorUtility.TryParseHtmlString(h, out var c); return c; }

        // ── waterline: sea edge of the opened plots + a beach-depth profile (r3: start waterline pulled in to v ~ 7.6-11.8) ───
        static readonly float[] WU = { -30, -24, -18, -12, -6, 0, 6, 12, 18, 24, 30 };
        static readonly float[] WV = { 7.6f, 8.0f, 8.8f, 10.2f, 11.3f, 11.8f, 11.6f, 10.4f, 9.0f, 8.2f, 7.8f };
        const float StartSeaEdgeV = 6f;
        /// <summary>Beach depth (m, along v) past the opened plots' sea edge: the r3 start profile, a full outward bulge widest in front of the camp.</summary>
        static float BeachDepth(float u) => S3.Pchip(WU, WV, u) - StartSeaEdgeV;
        /// <summary>Still-water line for a set of opened plots (u, v rects): the seaward-most opened edge over u (the start camp edge v = 6 where no plot
        /// covers u) plus <see cref="BeachDepth"/>. Reclaiming land seaward (opening sea-side plots) pushes the shore out with it. Only Start_3x3 is built.</summary>
        public static float WaterlineFor(IList<Rect> openPlots, float u)
        {
            var keep = s_open; var ke = s_edgeTab; var kw = s_waterTab;
            s_open = openPlots.ToList(); s_edgeTab = null;
            try { return W(u); } finally { s_open = keep; s_edgeTab = ke; s_waterTab = kw; }
        }
        public static float W(float u)
        {
            if (s_edgeTab == null) BuildEdgeTables();
            return Tab(s_waterTab, u);
        }

        /// <summary>Seaward edge of the land mesh: a clean gentle arc 0-0.35 m past v = 6 over the camp, a slow 0.3 m wave further out.</summary>
        public static float LandEdge(float u)
        {
            float camp = 0.35f * Mathf.Max(0f, 1f - (u / 6.5f) * (u / 6.5f));
            float outer = 0.3f * Mathf.Sin(u * 0.13f + 0.6f);
            float w = Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(5.5f, 9f, Mathf.Abs(u)));
            // fine natural raggedness of the turf edge (Boom Beach edge zoom): 0.03-0.1 m, no tongues
            // 4c: only a soft, low (<= 0.04 m) wobble of 0.4-1.2 m wavelength; the r3 high-frequency rag sampled into stair steps
            float rag = 0.024f * (2f * Noise1(u * 1.4f, 15) - 1f) + 0.016f * (2f * Noise1(u * 2.3f, 16) - 1f);
            return SeaEdge(u) + Mathf.Lerp(camp, outer, w) + rag;
        }

        // ── forest band: rounded super-ellipse around the camp, narrowing toward the sea ───
        const float BandU = 16f;
        /// <summary>&lt; 1 inside the band's outer arc. Over v &gt; 0 the half width narrows to ~65 % at v = 6 so both ends taper onto the beach.</summary>
        public static float BandE(Vector2 p) => 1f + BandOut(p) / 14f;
        /// <summary>Metres outside the band's outer edge (negative inside): band depth ~10 m (BandU - 6) from the opened set, a slow wobble,
        /// narrowing to ~44 % over the last 6 m before the opened land's sea edge so both ends taper onto the beach.</summary>
        static float BandOut(Vector2 p)
        {
            float wob = 1f + 0.05f * (2f * Noise2(p.x * 0.11f + 5.1f, p.y * 0.11f, 47) - 1f);
            float depth = (BandU - 6f) * wob * Mathf.Lerp(1f, 0.44f, Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((p.y - (SeaEdge(p.x) - 6f)) / 6f)));
            return HullDist(p) - depth;
        }

        // ── build ────────────────────────────────────────────────────────────
        static Transform BaseRoot(Scene scene)
        {
            var parts = BaseRootPath.Split('/');
            var top = scene.GetRootGameObjects().FirstOrDefault(g => g.name == parts[0]);
            return top != null ? top.transform.Find(parts[1]) : null;
        }

        /// <summary>Builds the default base environment under <see cref="BaseRootPath"/>/<see cref="NodeName"/> (active; the old
        /// GrasslandGround is saved inactive, never deleted) for an opened-land state; world coordinates unchanged.</summary>
        public static string Build(string state = StateLegacy)
        {
            if (EditorApplication.isPlayingOrWillChangePlaymode) throw new InvalidOperationException("Stop Play before building");
            var scene = SceneManager.GetSceneByPath(BaseV3EnvWipBuilder.ScenePath);
            if (!scene.IsValid() || !scene.isLoaded) throw new InvalidOperationException("HomeScreen not loaded");
            var baseRoot = BaseRoot(scene);
            if (baseRoot == null) throw new InvalidOperationException(BaseRootPath + " missing");
            S3.Init(); s_checks.Clear(); s_cal = null; s_trunk = null; Cal();
            List<string> table = null;
            s_state = state; s_open = state == StateStart ? StartCells() : LegacyPlotsCoverCells(out table); s_hull = null; s_edgeTab = null;
            S3.Folder(OutDir);
            // the pre-switch location (BaseV3Env_WIP/Step4_Static) is retired; the WIP root keeps only its older steps (inactive)
            var wip = scene.GetRootGameObjects().FirstOrDefault(g => g.name == BaseV3EnvWipBuilder.RootName);
            var oldStep = wip != null ? wip.transform.Find("Step4_Static") : null; if (oldStep != null) Object.DestroyImmediate(oldStep.gameObject);
            var old = baseRoot.Find(NodeName); if (old != null) Object.DestroyImmediate(old.gameObject);
            var node = new GameObject(NodeName).transform; node.SetParent(baseRoot, false);

            var report = new StringBuilder();
            var ob = OpenBounds();
            report.AppendLine($"H={S3.H} W(0)={W(0f):F2} state={state} cells={s_open.Count} bounds u[{ob.xMin},{ob.xMax}] v[{ob.yMin},{ob.yMax}] calib={CalibPath}");
            report.AppendLine("CELLS " + string.Join(" ", s_open.Select(r => $"[{r.xMin},{r.yMin}]")));
            if (table != null) foreach (var t in table) report.AppendLine("PLOT " + t);
            var buildings = Placeholders();
            report.AppendLine(BuildPlaceholders(node, buildings));
            var cliffFoot = new List<Vector2[]>(); var cliffTop = new List<(Vector2 uv, float y, bool rim)>();
            report.AppendLine(BuildCliff(node, cliffFoot, cliffTop));
            foreach (var f in new[] { "BV3S4_Land", "BV3S4_Sand", "BV3S4_Bed", "BV3S4_Water", "BV3S4_FogSheet0", "BV3S4_FogSheet1", "BV3S4_FogSheet2" })
                AssetDatabase.DeleteAsset($"{OutDir}/{f}.asset");   // pre-split names
            if (AssetDatabase.IsValidFolder(OutDir + "/ForestMats")) AssetDatabase.DeleteAsset(OutDir + "/ForestMats");
            S3.Folder(OutDir + "/ForestMats"); s_worldMat.Clear(); s_tintMat.Clear();
            // shore-dependent parts per variant (Legacy_PlotsCover: with / without the D4 plots; Start_3x3: one variant)
            var variants = state == StateStart ? new[] { (name: ShoreNoD4, cells: s_open) }
                : new[] { (name: ShoreNoD4, cells: LegacyPlotsCoverCells(out _, false)), (name: ShoreD4, cells: LegacyPlotsCoverCells(out _, true)) };
            var shoreTrees = new List<(Transform node, List<TreeInst> trees)>();
            foreach (var v in variants)
            {
                s_open = v.cells; s_hull = null; s_edgeTab = null; s_tag = "_" + v.name.Substring("Shore_".Length);
                var vn = new GameObject(v.name).transform; vn.SetParent(node, false);
                report.AppendLine($"{v.name}: {s_open.Count} cells, W(0)={W(0f):F2}");
                report.AppendLine(BuildLand(vn));
                report.AppendLine(BuildSandAndWater(vn));
                report.AppendLine(BuildForest(vn, buildings, cliffFoot, cliffTop));
                shoreTrees.Add((vn, s_lastTrees));
                report.AppendLine(BuildFog(vn));
            }
            // trees standing in every variant go to the shared EnvironmentV3/Forest_T05, the rest to their variant's own Forest_T05
            string Key(TreeInst t) => $"{t.uv.x:F3},{t.uv.y:F3},{t.y:F3},{t.size},{t.yaw:F1}";
            var common = new HashSet<string>(shoreTrees[0].trees.Select(Key));
            foreach (var st in shoreTrees.Skip(1)) common.IntersectWith(st.trees.Select(Key));
            var shared = new GameObject("Forest_T05").transform; shared.SetParent(node, false);
            PlaceForest(shared, shoreTrees[0].trees.Where(t => common.Contains(Key(t))).ToList(), s_lastSrc, out int rs, out long ts);
            report.AppendLine($"Forest_T05 shared: {common.Count} trees, {rs} renderers, {ts} tris, {s_tintMat.Count} tinted materials");
            foreach (var st in shoreTrees)
            {
                var own = st.trees.Where(t => !common.Contains(Key(t))).ToList();
                var fp = new GameObject("Forest_T05").transform; fp.SetParent(st.node, false);
                PlaceForest(fp, own, s_lastSrc, out int r2, out long t2);
                report.AppendLine($"{st.node.name}/Forest_T05: {own.Count} trees, {r2} renderers");
            }
            node.Find(ShoreD4)?.gameObject.SetActive(false);   // runtime picks the variant (BaseEnvironmentV3)
            report.AppendLine(AttachRuntime(node));
            report.Append(s_checks);

            node.Find(PlaceholderNode).gameObject.SetActive(false);
            var grass = baseRoot.Find(Meta.Base.Environment.BaseEnvironmentMode.OldGroundPath);
            if (grass != null) grass.gameObject.SetActive(false);   // kept for the switch back (BaseEnvironmentMode sets it at runtime)
            node.gameObject.SetActive(true);
            EditorSceneManager.MarkSceneDirty(scene);
            AssetDatabase.SaveAssets();
            return "[BaseV3EnvStep4] " + report;
        }

        /// <summary>Runtime side on the environment root: camera opened-land rect (bounding rect of the opened cells, grid space), the world
        /// ground rect the camera view must stay inside, and the building pad settings.</summary>
        static string AttachRuntime(Transform node)
        {
            var env = node.gameObject.AddComponent<Meta.Base.Environment.BaseEnvironmentV3>();
            var ob = OpenBounds();
            // grid x = origin.x + v, grid z = origin.y - u (S3.UV)
            var grid = Rect.MinMaxRect(S3.Origin.x + ob.yMin, S3.Origin.y - ob.xMax, S3.Origin.x + ob.yMax, S3.Origin.y - ob.xMin);
            // fallback camera rect (no buildings): the Start_3x3 plots; with buildings, BaseEnvironmentV3 feeds the footprint bounds of the plots in use
            grid = Rect.MinMaxRect(S3.Origin.x - 6f, S3.Origin.y - 6f, S3.Origin.x + 6f, S3.Origin.y + 6f);
            var target = new Color(205 / 255f, 178 / 255f, 140 / 255f).linear;
            var so = new SerializedObject(env);
            so.FindProperty("_openedGridRect").rectValue = grid;
            so.FindProperty("_groundLimitWorld").rectValue = BaseV3EnvWipPreview.PreviewLimit;
            so.FindProperty("_padOutset").floatValue = BaseV3EnvWipPreview.PadOutset;
            so.FindProperty("_padMaterial").objectReferenceValue = AssetDatabase.LoadAssetAtPath<Material>(EarthMatPath);
            so.FindProperty("_padColour").colorValue = new Color(target.r / SandGain.x, target.g / SandGain.y, target.b / SandGain.z, 1f);
            so.ApplyModifiedPropertiesWithoutUndo();
            return $"Runtime: BaseEnvironmentV3 opened grid rect {grid} (state {s_state}), ground limit {BaseV3EnvWipPreview.PreviewLimit}, pad outset {BaseV3EnvWipPreview.PadOutset}";
        }

        static Transform StepNode()
        {
            var scene = SceneManager.GetSceneByPath(BaseV3EnvWipBuilder.ScenePath);
            if (!scene.IsValid() || !scene.isLoaded) return null;
            var root = BaseRoot(scene);
            return root != null ? root.Find(NodeName) : null;
        }

        /// <summary>Shows / hides a direct child of EnvironmentV3 (placeholders, audition, fog, cliff ...); works in Edit and Play.</summary>
        public static string SetChild(string name, bool on)
        {
            var node = StepNode(); if (node == null) return "no " + NodeName;
            var t = node.Find(name); if (t == null) return "no " + name;
            t.gameObject.SetActive(on);
            if (!EditorApplication.isPlaying) EditorSceneManager.MarkSceneDirty(node.gameObject.scene);
            return name + "=" + t.gameObject.activeSelf;
        }

        public static string SetPlaceholders(bool on) => SetChild(PlaceholderNode, on);

        // ── placeholders (D5 A table; off by default, used to measure tree / HQ height) ───
        struct Box { public string name; public Vector2 c, size; public float h; }

        static List<Box> Placeholders() => new List<Box>
        {
            new Box { name = "HQ", c = new Vector2(0, 0), size = new Vector2(3, 3), h = 2.8f },
            new Box { name = "Warehouse", c = new Vector2(-4, -3.8f), size = new Vector2(2, 2), h = 1.4f },
            new Box { name = "Medical", c = new Vector2(4, -3.8f), size = new Vector2(2, 2), h = 1.4f },
            new Box { name = "Ammo", c = new Vector2(-4, 0), size = new Vector2(2, 2), h = 1.4f },
            new Box { name = "Smelter", c = new Vector2(4, 0), size = new Vector2(2, 2), h = 1.4f },
            new Box { name = "Turret", c = new Vector2(0, -4.4f), size = new Vector2(1.4f, 1.4f), h = 1.2f },
            new Box { name = "House_L", c = new Vector2(-4, 4), size = new Vector2(1, 1), h = 1.0f },
            new Box { name = "House_C", c = new Vector2(0, 4), size = new Vector2(1, 1), h = 1.0f },
            new Box { name = "House_R", c = new Vector2(4, 4), size = new Vector2(1, 1), h = 1.0f },
        };

        static Rect BoxRect(Box b) => new Rect(b.c - b.size * 0.5f, b.size);

        static Quaternion UVRotation()
        {
            var o = S3.UV(0f, 0f, 0f); var av = S3.UV(0f, 1f, 0f) - o;
            return Quaternion.LookRotation(av.normalized, Vector3.up);
        }

        static string BuildPlaceholders(Transform node, List<Box> boxes)
        {
            var parent = new GameObject(PlaceholderNode).transform; parent.SetParent(node, false);
            var mat = S3.Load<Material>(S3.GravelMatPath);
            var hqMesh = BoxMesh(S3.LinearHex("C9D3DD"), $"{OutDir}/BV3S4_PlaceholderBox_HQ.asset");
            var mesh = BoxMesh(S3.LinearHex("D9D4CC"), $"{OutDir}/BV3S4_PlaceholderBox.asset");
            var rot = UVRotation();
            foreach (var b in boxes)
            {
                var go = new GameObject("Placeholder_" + b.name); go.transform.SetParent(parent, false);
                go.transform.SetPositionAndRotation(S3.UV(b.c.x, b.c.y, S3.H), rot);
                go.transform.localScale = new Vector3(b.size.x, b.h, b.size.y);
                go.AddComponent<MeshFilter>().sharedMesh = b.name == "HQ" ? hqMesh : mesh;
                go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            }
            return $"{PlaceholderNode}: {boxes.Count} boxes (inactive by default)";
        }

        static void AddRenderer(Transform parent, string name, Mesh mesh, Material mat, bool shadows)
        {
            var go = new GameObject(name); go.transform.SetParent(parent, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>(); r.sharedMaterial = mat;
            r.shadowCastingMode = shadows ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        static Mesh BoxMesh(Vector3 targetLin, string path)
        {
            var c = new Color(targetLin.x / S3.GravelGain.x, targetLin.y / S3.GravelGain.y, targetLin.z / S3.GravelGain.z, 1f);
            var v = new List<Vector3>(); var t = new List<int>();
            void Quad(Vector3 a, Vector3 b, Vector3 cc, Vector3 d) { int i = v.Count; v.Add(a); v.Add(b); v.Add(cc); v.Add(d); t.AddRange(new[] { i, i + 1, i + 2, i, i + 2, i + 3 }); }
            float x0 = -0.5f, x1 = 0.5f, z0 = -0.5f, z1 = 0.5f;
            Quad(new(x0, 1, z0), new(x0, 1, z1), new(x1, 1, z1), new(x1, 1, z0));
            Quad(new(x0, 0, z0), new(x0, 1, z0), new(x1, 1, z0), new(x1, 0, z0));
            Quad(new(x1, 0, z1), new(x1, 1, z1), new(x0, 1, z1), new(x0, 0, z1));
            Quad(new(x0, 0, z1), new(x0, 1, z1), new(x0, 1, z0), new(x0, 0, z0));
            Quad(new(x1, 0, z0), new(x1, 1, z0), new(x1, 1, z1), new(x1, 0, z1));
            for (int i = 0; i < t.Count; i += 3)
            {
                var nrm = Vector3.Cross(v[t[i + 1]] - v[t[i]], v[t[i + 2]] - v[t[i]]);
                var outward = (v[t[i]] + v[t[i + 1]] + v[t[i + 2]]) / 3f - new Vector3(0f, 0.5f, 0f);
                if (Vector3.Dot(nrm, outward) < 0f) { int tmp = t[i + 1]; t[i + 1] = t[i + 2]; t[i + 2] = tmp; }
            }
            var m = new Mesh { name = Path.GetFileNameWithoutExtension(path) };
            m.SetVertices(v); m.SetTriangles(t, 0); m.SetColors(Enumerable.Repeat(c, v.Count).ToList());
            m.RecalculateNormals(); m.RecalculateBounds();
            return S3.Keep(m, path);
        }

        /// <summary>Trodden-earth pads: one per footprint rect (u, v), flush with the ground (+8 mm against z-fight), edge worn inward
        /// 0.02-0.18 m with irregular notches and softened corners. Warm light earth (screen target ~#CDB28C, L* ~74, hue ~35 deg).
        /// Returns an unsaved mesh (the preview builds one at runtime for the real buildings).</summary>
        public static Mesh EarthPadMesh(List<Rect> rects, string name)
        {
            var target = new Color(205 / 255f, 178 / 255f, 140 / 255f).linear;
            var ec = new Color(target.r / SandGain.x, target.g / SandGain.y, target.b / SandGain.z, 1f);
            var verts = new List<Vector3>(); var tris = new List<int>(); int bi = 0;
            foreach (var rect in rects)
            {
                var ring = new List<Vector2>(); float per = 2f * (rect.width + rect.height);
                for (float s = 0f; s < per - 1e-4f; s += 0.08f)
                {
                    Vector2 p, inward;
                    if (s < rect.width) { p = new Vector2(rect.xMin + s, rect.yMin); inward = Vector2.up; }
                    else if (s < rect.width + rect.height) { p = new Vector2(rect.xMax, rect.yMin + s - rect.width); inward = Vector2.left; }
                    else if (s < 2f * rect.width + rect.height) { p = new Vector2(rect.xMax - (s - rect.width - rect.height), rect.yMax); inward = Vector2.down; }
                    else { p = new Vector2(rect.xMin, rect.yMax - (s - 2f * rect.width - rect.height)); inward = Vector2.right; }
                    float notch = Noise1(s * 0.9f, bi * 17 + 9) > 0.72f ? 0.08f : 0f;
                    float inset = Mathf.Clamp(0.02f + 0.10f * Noise1(s * 2.2f, bi * 17 + 3) + notch, 0f, 0.18f);
                    float cd = Mathf.Min(p.x - rect.xMin, rect.xMax - p.x) + Mathf.Min(p.y - rect.yMin, rect.yMax - p.y);
                    var cornerIn = cd < 0.2f ? (rect.center - p).normalized * (0.2f - cd) * 0.5f : Vector2.zero;
                    ring.Add(p + inward * inset + cornerIn);
                }
                int c0 = verts.Count; verts.Add(S3.UV(rect.center.x, rect.center.y, S3.H + 0.008f));
                foreach (var p in ring) verts.Add(S3.UV(p.x, p.y, S3.H + 0.008f));
                for (int i = 0; i < ring.Count; i++)
                {
                    int a = c0 + 1 + i, b = c0 + 1 + (i + 1) % ring.Count;
                    var nrm = Vector3.Cross(verts[a] - verts[c0], verts[b] - verts[c0]);
                    if (nrm.y < 0f) tris.AddRange(new[] { c0, b, a }); else tris.AddRange(new[] { c0, a, b });
                }
                bi++;
            }
            var mesh = new Mesh { name = name };
            mesh.SetVertices(verts); mesh.SetTriangles(tris, 0); mesh.SetColors(Enumerable.Repeat(ec, verts.Count).ToList());
            mesh.SetUVs(0, verts.Select(p => new Vector2(p.x, p.z)).ToList());
            mesh.RecalculateNormals(); mesh.RecalculateBounds();
            return mesh;
        }

        // ── noise ────────────────────────────────────────────────────────────
        static float H01(int a, int salt)
        {
            unchecked { uint h = (uint)(a * 73856093) ^ (uint)(salt * 19349663) ^ 15937u; h ^= h >> 16; h *= 0x7feb352d; h ^= h >> 15; h *= 0x846ca68b; h ^= h >> 16; return (h & 0xffffff) / 16777216f; }
        }
        static float Noise1(float x, int salt) { int i = Mathf.FloorToInt(x); float f = x - i; f = f * f * (3f - 2f * f); return Mathf.Lerp(H01(i, salt), H01(i + 1, salt), f); }
        static float H2(int a, int b, int salt) => H01(a * 92821 + b, salt);
        static float Noise2(float x, float y, int salt)
        {
            int ix = Mathf.FloorToInt(x), iy = Mathf.FloorToInt(y); float fx = x - ix, fy = y - iy;
            fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
            return Mathf.Lerp(Mathf.Lerp(H2(ix, iy, salt), H2(ix + 1, iy, salt), fx), Mathf.Lerp(H2(ix, iy + 1, salt), H2(ix + 1, iy + 1, salt), fx), fy);
        }

        // ── land: opened grass (clean edge) + deep-green floor everywhere outside the camp ───
        /// <summary>Our copy of the kit grass material: shadows lean green (_ShadowTint + _VegShadowHue); _VegShadowDark is left as is (lighting session).</summary>
        static Material GrassMaterial()
        {
            var src = S3.Load<Material>(KitDir + "MosaicGrass.mat");
            string path = $"{OutDir}/BV3S4_Grass.mat";
            var copy = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (copy == null) { copy = new Material(src) { name = "BV3S4_Grass" }; AssetDatabase.CreateAsset(copy, path); }
            else { copy.shader = src.shader; copy.CopyPropertiesFromMaterial(src); copy.shaderKeywords = src.shaderKeywords; }
            copy.SetColor("_ShadowTint", Hx((string)(Cal()["grassShadowTint"] ?? "#CCFFC4")));
            copy.SetFloat("_VegShadowHue", Cal()["grassShadowHue"]?.Value<float>() ?? 0.5f);
            EditorUtility.SetDirty(copy);
            return copy;
        }

        static string BuildLand(Transform node)
        {
            var mat = GrassMaterial();
            var grass = VC(Cal()["grass"]); float gv = Cal()["grassVar"].Value<float>();
            Color Colour(float u, float v)
            {
                // one grass colour everywhere (camp, under the band, at the cliff feet, under the fog) with a very light low-frequency
                // brightness variation; no painted shade anywhere: darkness comes only from the lighting's shadows and crown occlusion
                float k = 1f + gv * (2f * Noise2(u * 0.18f, v * 0.18f, 41) - 1f);
                return new Color(grass.r * k, grass.g * k, grass.b * k, 1f);
            }
            var cols = new List<float>();
            // 11-13: 0.25 m columns over the shore span (the edge is a smooth curve now), 2 m outside; rows only carry the low-frequency colour
            for (float u = -Ext; u < -42f; u += 2f) cols.Add(u);
            for (float u = -42f; u <= 42f + 1e-3f; u += 0.25f) cols.Add(u);
            for (float u = 44f; u <= Ext + 1e-3f; u += 2f) cols.Add(u);
            const int farRows = 12, nearRows = 50;
            string r = S3.Grid(node, "Land", mat, cols.Count, farRows + nearRows, (i, k) =>
            {
                float u = cols[i];
                float v = k <= farRows ? Mathf.Lerp(-Ext, -30f, k / (float)farRows) : Mathf.Lerp(-30f, LandEdge(u), (k - farRows) / (float)nearRows);
                return (u, v, S3.H + LandLift);
            }, (i, k, u, v) => Colour(u, v), null, $"{OutDir}/BV3S4_Land{s_tag}.asset", null, null, null);
            float lo = 9f, hi = 0f; for (float u = -6f; u <= 6f; u += 0.05f) { float b = LandEdge(u) - 6f; lo = Mathf.Min(lo, b); hi = Mathf.Max(hi, b); }
            s_checks.AppendLine($"CHECK land: camp sea edge clean arc v=6+{lo:F2}..{hi:F2} m (no jitter, grass only reaches outward); one grass colour everywhere, no painted shade");
            return "Land: " + r;
        }

        // ── sand (earth edge -> pale -> warm), bed, water ramp ───────────────
        static float GroundDrop(float d) => S3.Drop(d, 0f);
        static float ShallowWidth(float u) => Mathf.Clamp(2.55f + 0.30f * Mathf.Sin(2f * Mathf.PI * u / 23f + 0.7f) + 0.15f * Mathf.Sin(2f * Mathf.PI * u / 9.7f + 2.1f), 2.1f, 3.0f);
        const float EarthWidth = 0.16f;

        static string BuildSandAndWater(Transform node)
        {
            var parent = new GameObject("Shore").transform; parent.SetParent(node, false);
            var dryMat = S3.Load<Material>(KitDir + "DrySand.mat");
            var waterMat = WaterMaterial();
            Color earth = VC(Cal()["earth"]), near = VC(Cal()["sandNear"]), far = VC(Cal()["sandFar"]);
            var cols = new List<float>();
            for (float u = -Ext; u < -40f; u += 2f) cols.Add(u);
            for (float u = -40f; u <= 40f + 1e-3f; u += 0.25f) cols.Add(u);
            for (float u = 42f; u <= Ext + 1e-3f; u += 2f) cols.Add(u);
            float wl = S3.WaterlineIntoDescent;
            // rows: under the land, land edge, earth strip end, strip blend end, 30 flat rows to the slope start, descent rows to the bed
            const int flat = 30; float[] desc = { -wl + 0.3f, -wl + 0.6f, -wl + 0.9f, -wl + 1.2f, -wl + 1.5f, 0.6f };
            int rows = 3 + flat + desc.Length;
            (float v, float y) Row(int i, int k)
            {
                float u = cols[i], w = W(u), le = LandEdge(u);
                if (k == 0) return (4.5f, S3.H);
                if (k == 1) return (le, S3.H);
                if (k == 2) return (le + EarthWidth, S3.H);
                if (k == 3) return (le + EarthWidth + 0.06f, S3.H);
                if (k <= 3 + flat) return (Mathf.Lerp(le + EarthWidth + 0.06f, Mathf.Max(le + EarthWidth + 0.1f, w - wl), (k - 3) / (float)flat), S3.H);
                float d = desc[k - 4 - flat]; return (w + d, S3.H - GroundDrop(d));
            }
            Color SandColour(int i, int k, float u, float v)
            {
                if (k <= 2) return near;   // r3: no earth strip, grass meets sand directly
                float le = LandEdge(u) + EarthWidth + 0.06f, t = Mathf.Clamp01((v - le) / Mathf.Max(0.1f, W(u) - le));
                // first 60 % pale, last 40 % warming toward the water (Boom Beach profile)
                var c = t < 0.6f ? near : Color.Lerp(near, far, Mathf.SmoothStep(0f, 1f, (t - 0.6f) / 0.4f));
                float kk = 1f + 0.04f * (2f * Noise2(u * 0.08f + 3.7f, v * 0.08f, 43) - 1f);
                return new Color(c.r * kk, c.g * kk, c.b * kk, 1f);
            }
            var r = new List<string>();
            r.Add(S3.Grid(parent, "Sand", dryMat, cols.Count, rows, (i, k) => { var q = Row(i, k); return (cols[i], q.v, q.y); }, SandColour, null, $"{OutDir}/BV3S4_Sand{s_tag}.asset", null, null, null));
            float[] bedD = { 0.6f, 1.5f, 3f, 5f, 8f, 11f, 14f, 17f, 21f, SeaEnd };
            r.Add(S3.Grid(parent, "Bed", dryMat, cols.Count, bedD.Length - 1, (i, k) =>
            {
                float u = cols[i], w = W(u); float v = k == bedD.Length - 1 ? SeaEnd : w + bedD[k];
                return (u, v, S3.H - GroundDrop(v - w));
            }, (i, k, u, v) => far, null, $"{OutDir}/BV3S4_Bed{s_tag}.asset", null, null, null));

            var line = new List<Vector2>(); var arc = new List<float>();
            for (float u = -Ext - 5f; u <= Ext + 5f; u += 0.25f) { var p = new Vector2(u, W(u)); arc.Add(line.Count == 0 ? 0f : arc[arc.Count - 1] + Vector2.Distance(line[line.Count - 1], p)); line.Add(p); }
            var wcols = cols.Where((u, i) => i % 2 == 0 || Mathf.Abs(u) > 40f).ToList();
            float[] waterD = { -0.5f, 0f, 0.3f, 0.6f, 0.9f, 1.2f, 1.6f, 2.0f, 2.5f, 3.0f, 3.5f, 4.2f, 5f, 6f, 7f, 8.5f, 11f, 15f, 21f, 30f, 45f, 70f, SeaEnd };
            r.Add(S3.Grid(parent, "Water", waterMat, wcols.Count, waterD.Length - 1, (i, k) =>
            {
                float u = wcols[i], w = W(u); float v = k == waterD.Length - 1 ? SeaEnd : w + waterD[k];
                return (u, v, S3.H - S3.WaterDrop);
            }, null, (i, k, u, v) =>
            {
                var near0 = S3.NearestOnLine(line, arc, new Vector2(u, v));
                return new Vector2(v < W(u) ? 0f : near0.dist, ShallowWidth(u));
            }, $"{OutDir}/BV3S4_Water{s_tag}.asset", null, null, null));

            float beachMin = 99f, beachMax = 0f, bMin = 99f, bMax = 0f, beachArea = 0f;
            for (float u = -24f; u <= 24f; u += 0.05f)
            {
                float d = W(u) - LandEdge(u); bMin = Mathf.Min(bMin, d); bMax = Mathf.Max(bMax, d); beachArea += Mathf.Max(0f, d) * 0.05f;
                if (Mathf.Abs(u) <= 6f) { beachMin = Mathf.Min(beachMin, W(u) - 6f); beachMax = Mathf.Max(beachMax, W(u) - 6f); }
            }
            var wlPts = new List<Vector2>(); float minPlot = float.MaxValue;
            for (float u = -60f; u <= 60f; u += 0.25f) { var p = new Vector2(u, W(u)); wlPts.Add(p); minPlot = Mathf.Min(minPlot, OpenDist(p)); }
            s_checks.AppendLine($"CHECK shore: waterline self-intersections {S3.SelfIntersections(wlPts)}, min distance to opened 3x3 {minPlot:F2} m; no earth strip (grass flush on sand); camp edge (v=6) -> waterline {beachMin:F2}..{beachMax:F2} m over |u|<=6, beach (land edge -> waterline) {bMin:F2}..{bMax:F2} m over |u|<=24; start-state beach area |u|<=24 {beachArea:F1} m2; nothing placed on the beach");
            return "Shore: " + string.Join(" ", r);
        }

        static Material WaterMaterial()
        {
            string path = OutDir + "/BV3S4_BaseWater.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null)
            {
                var shader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/Shaders/Lab/LabBaseWater.shader");
                mat = new Material(shader) { name = "BV3S4_BaseWater" }; AssetDatabase.CreateAsset(mat, path);
            }
            var w = (JObject)Cal()["water"];
            mat.SetFloat("_RampMode", 1f);
            mat.SetColor("_RampC0", Hx((string)w["c0"])); mat.SetColor("_RampC1", Hx((string)w["c1"])); mat.SetColor("_RampC2", Hx((string)w["c2"]));
            mat.SetColor("_RampC3", Hx((string)w["c3"])); mat.SetColor("_RampC4", Hx((string)w["c4"])); mat.SetColor("_FarColor", Hx((string)w["far"]));
            var st = (JArray)w["stops"]; mat.SetVector("_RampStops", new Vector4(st[0].Value<float>(), st[1].Value<float>(), st[2].Value<float>(), st[3].Value<float>()));
            mat.SetFloat("_RampRefWidth", 2.55f); mat.SetFloat("_FarStartM", w["farStart"].Value<float>()); mat.SetFloat("_FarEndM", w["farEnd"].Value<float>());
            // low-contrast large brightness blocks in the water body (world XZ centre, half axes along shore / seaward, relative brightness)
            var blocks = new[] { (-13f, 19f, 7.5f, 5f, 0.05f), (-1f, 26f, 6.5f, 4.5f, -0.06f), (11f, 20f, 6f, 5f, 0.055f), (22f, 29f, 7f, 5.5f, -0.05f) };
            var amt = Vector4.zero;
            for (int i = 0; i < 4; i++) { var b = blocks[i]; var wpos = S3.UV(b.Item1, b.Item2, 0f); mat.SetVector("_Block" + i, new Vector4(wpos.x, wpos.z, b.Item3, b.Item4)); amt[i] = b.Item5; }
            mat.SetVector("_BlockAmount", amt);
            var o = S3.UV(0f, 0f, 0f); var au = S3.UV(1f, 0f, 0f) - o; var av = S3.UV(0f, 1f, 0f) - o;
            mat.SetVector("_AxisAlong", new Vector4(au.x, au.z, 0f, 0f)); mat.SetVector("_AxisSea", new Vector4(av.x, av.z, 0f, 0f));
            mat.SetFloat("_FarPatchAmount", 0.05f); mat.SetFloat("_FarPatchScaleM", 12f);
            // 4c: deeper second far colour, sand showing through the shallows, world ripple net, soft foam rim
            mat.SetColor("_FarColor2", Hx((string)(w["far2"] ?? "#26677F"))); mat.SetFloat("_Far2StartM", w["far2Start"]?.Value<float>() ?? 30f); mat.SetFloat("_Far2EndM", w["far2End"]?.Value<float>() ?? 70f);
            mat.SetColor("_WetSandCol", Hx((string)(w["wetSand"] ?? "#D2C3A2"))); mat.SetFloat("_BedSlope", 0.12f); mat.SetFloat("_ShallowDepthM", w["shallowDepth"]?.Value<float>() ?? 0.32f);
            string ripPath = OutDir + "/BV3S4_WaterRipple.png";
            if (AssetImporter.GetAtPath(ripPath) is TextureImporter ti && (ti.sRGBTexture || ti.wrapMode != TextureWrapMode.Repeat || ti.textureCompression != TextureImporterCompression.Uncompressed))
            { ti.sRGBTexture = false; ti.wrapMode = TextureWrapMode.Repeat; ti.mipmapEnabled = true; ti.textureCompression = TextureImporterCompression.Uncompressed; ti.SaveAndReimport(); }
            mat.SetTexture("_RippleTex", AssetDatabase.LoadAssetAtPath<Texture2D>(ripPath));
            mat.SetFloat("_RippleAmt", w["ripple"]?.Value<float>() ?? 0.08f); mat.SetFloat("_RippleScale1", 14f); mat.SetFloat("_RippleScale2", 9.5f); mat.SetFloat("_RippleSpeed", 0.06f);
            mat.SetColor("_FoamCol", Hx("#F4F6F0")); mat.SetFloat("_FoamWidthM", 0.45f); mat.SetFloat("_FoamAlpha", 0.6f); mat.SetFloat("_FoamNoiseM", 1.6f); mat.SetFloat("_FoamAmpM", 0.15f); mat.SetFloat("_FoamPeriodS", 7f);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        // ── T05 round-crown forest band ──────────────────────────────────────
        sealed class TreeSource
        {
            public string path; public float scale, height, crown; public List<Vector2> hull;
            public List<(Mesh mesh, Matrix4x4 m, Material[] mats, UnityEngine.Rendering.ShadowCastingMode shadow)> parts = new();
        }
        struct TreeInst { public Vector2 uv; public int size, tint; public float yaw; public Vector2[] hull; public float y; }

        static TreeSource Measure(string path, float? topTarget)
        {
            var src = new TreeSource { path = path };
            var tmp = (GameObject)PrefabUtility.InstantiatePrefab(S3.Load<GameObject>(path));
            tmp.hideFlags = HideFlags.HideAndDontSave; tmp.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            var pts = new List<Vector2>(); float top = 0f;
            foreach (var mf in tmp.GetComponentsInChildren<MeshFilter>())
            {
                var r = mf.GetComponent<MeshRenderer>(); if (r == null || mf.sharedMesh == null) continue;
                var m = mf.transform.localToWorldMatrix;
                foreach (var v in mf.sharedMesh.vertices) { var w = m.MultiplyPoint3x4(v); pts.Add(new Vector2(w.x, w.z)); top = Mathf.Max(top, w.y); }
                src.parts.Add((mf.sharedMesh, m, r.sharedMaterials, r.shadowCastingMode));
            }
            Object.DestroyImmediate(tmp);
            src.hull = Hull(pts); src.height = top;
            src.scale = topTarget.HasValue ? topTarget.Value / top : 1f;
            float diam = 0f; foreach (var a in src.hull) foreach (var b in src.hull) diam = Mathf.Max(diam, (a - b).magnitude);
            src.crown = diam;
            return src;
        }

        static Vector2[] InstHull(TreeSource s, Vector2 uv, float yaw, float sizeMul)
        {
            var rot = Quaternion.Euler(0f, yaw, 0f); var w0 = S3.UV(uv.x, uv.y, S3.H); float sc = s.scale * sizeMul;
            return s.hull.Select(h => S3.WorldToUV(w0 + rot * new Vector3(h.x * sc, 0f, h.y * sc))).ToArray();
        }

        static List<Vector2> Hull(List<Vector2> pts)
        {
            var p = pts.OrderBy(a => a.x).ThenBy(a => a.y).ToList(); if (p.Count < 3) return p;
            float Cr(Vector2 o, Vector2 a, Vector2 b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
            var h = new List<Vector2>();
            foreach (var pt in p) { while (h.Count >= 2 && Cr(h[h.Count - 2], h[h.Count - 1], pt) <= 0) h.RemoveAt(h.Count - 1); h.Add(pt); }
            int lower = h.Count + 1;
            for (int i = p.Count - 2; i >= 0; i--) { var pt = p[i]; while (h.Count >= lower && Cr(h[h.Count - 2], h[h.Count - 1], pt) <= 0) h.RemoveAt(h.Count - 1); h.Add(pt); }
            h.RemoveAt(h.Count - 1); return h;
        }

        static bool InPoly(Vector2 p, IList<Vector2> poly)
        {
            bool inside = false;
            for (int i = 0, j = poly.Count - 1; i < poly.Count; j = i++)
                if ((poly[i].y > p.y) != (poly[j].y > p.y) && p.x < (poly[j].x - poly[i].x) * (p.y - poly[i].y) / (poly[j].y - poly[i].y) + poly[i].x) inside = !inside;
            return inside;
        }
        static bool SegCross(Vector2 a, Vector2 b, Vector2 c, Vector2 d)
        {
            float Cr(Vector2 o, Vector2 p, Vector2 q) => (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x);
            return Cr(c, d, a) * Cr(c, d, b) < 0f && Cr(a, b, c) * Cr(a, b, d) < 0f;
        }
        static bool PolyOverlap(IList<Vector2> a, IList<Vector2> b)
        {
            if (a.Any(p => InPoly(p, b)) || b.Any(p => InPoly(p, a))) return true;
            for (int i = 0; i < a.Count; i++) for (int j = 0; j < b.Count; j++) if (SegCross(a[i], a[(i + 1) % a.Count], b[j], b[(j + 1) % b.Count])) return true;
            return false;
        }
        static Vector2[] RectPoly(Rect r) => new[] { new Vector2(r.xMin, r.yMin), new Vector2(r.xMax, r.yMin), new Vector2(r.xMax, r.yMax), new Vector2(r.xMin, r.yMax) };
        static float SegDist(Vector2 p, Vector2 a, Vector2 b) { var d = b - a; float t = Mathf.Clamp01(Vector2.Dot(p - a, d) / Mathf.Max(1e-8f, d.sqrMagnitude)); return Vector2.Distance(p, a + d * t); }
        static float PolyRectDist(Vector2[] poly, Rect r)
        {
            if (PolyOverlap(poly, RectPoly(r))) return -1f;
            float d = poly.Min(p => S3.RectDist(p, r));
            foreach (var c in RectPoly(r)) for (int i = 0; i < poly.Length; i++) d = Mathf.Min(d, SegDist(c, poly[i], poly[(i + 1) % poly.Length]));
            return d;
        }

        static string BuildForest(Transform node, List<Box> boxes, List<Vector2[]> cliffFoot, List<(Vector2 uv, float y, bool rim)> cliffTop)
        {
            float top = Cal()["treeTop"].Value<float>(), spacingK = Cal()["treeCrownSpacing"].Value<float>();
            var src = Measure(T05Path, top);
            float crown = src.crown * src.scale, cell = spacingK * crown, jitter = 0.35f * cell;
            var trees = new List<TreeInst>();
            var cliffIn = cliffFoot.Select(f => { var c = f.Aggregate(Vector2.zero, (s0, q) => s0 + q) / f.Length; return f.Select(q => c + (q - c) * 0.9f).ToArray(); }).ToList();
            float NearCliff(Vector2 p) { float d = float.MaxValue; foreach (var f in cliffFoot) for (int i = 0; i < f.Length; i++) d = Mathf.Min(d, SegDist(p, f[i], f[(i + 1) % f.Length])); return d; }
            var openHull = Hull(s_open.SelectMany(r => new[] { r.min, new Vector2(r.xMax, r.yMin), r.max, new Vector2(r.xMin, r.yMax) }).ToList());
            bool InDomain(Vector2 p) => BandE(p) < 1f && !InOpen(p) && !InPoly(p, openHull) && p.y < LandEdge(p.x) - 0.6f && !cliffIn.Any(f => InPoly(p, f));
            bool Legal(Vector2 p, Vector2[] hull, float trunkMin) => InDomain(p) && OpenDist(p) >= trunkMin && PolyOpenDist(hull) >= 0f && hull.All(q => q.y <= LandEdge(q.x) + 0.6f);
            // clumps of 3-5 crowns on a coarse world grid: inside a clump the crowns sit 0.35-0.5 crown apart (deep overlap), clumps a bit looser
            float clumpCell = cell * 1.7f; var ob = OpenBounds(); int span = Mathf.CeilToInt((Mathf.Max(Mathf.Max(-ob.xMin, ob.xMax), Mathf.Max(-ob.yMin, ob.yMax)) + BandU) / clumpCell);
            for (int j = -span; j <= span; j++)
                for (int i = -span; i <= span; i++)
                {
                    uint h; unchecked { h = ((uint)(i * 73856093) ^ (uint)(j * 19349663) ^ 15937u); }
                    var c0 = new Vector2(clumpCell * i + (j % 2 == 0 ? clumpCell * 0.5f : 0f) + ((h & 255) / 255f - 0.5f) * clumpCell * 0.5f, clumpCell * j + (((h >> 8) & 255) / 255f - 0.5f) * clumpCell * 0.5f);
                    int n = 4 + (int)((h >> 16) % 3);
                    for (int m = 0; m < n; m++)
                    {
                        uint g; unchecked { g = h * 2654435761u + (uint)(m * 40503); g ^= g >> 13; g *= 0x5bd1e995; g ^= g >> 15; }
                        float ang = (g & 1023) / 1023f * Mathf.PI * 2f, rad = m == 0 ? 0f : crown * (0.35f + 0.15f * ((g >> 10) & 255) / 255f);
                        var p = c0 + new Vector2(Mathf.Cos(ang), Mathf.Sin(ang)) * rad;
                        if (!InDomain(p) || OpenDist(p) < crown * 0.5f + 0.6f) continue;   // front row placed separately
                        if (trees.Any(t => (t.uv - p).sqrMagnitude < 0.8f * 0.8f)) continue;
                        int size = SizePick(g >> 18), tint = (int)((g >> 26) % 3); float yaw = ((g >> 20) % 24) * 15f;
                        var hull = InstHull(src, p, yaw, SizeLevels[size]);
                        if (!Legal(p, hull, crown * 0.5f + 0.6f)) continue;
                        trees.Add(new TreeInst { uv = p, size = size, tint = tint, yaw = yaw, hull = hull });
                    }
                }
            int grid = trees.Count;
            // outer edges of the opened set (cell sides with no opened neighbour), except the sea-facing ones
            var edges = new List<(Vector2, Vector2, Vector2)>();
            foreach (var r in s_open)
            {
                if (!InOpen(new Vector2(r.xMin - 0.5f, r.center.y))) edges.Add((new Vector2(r.xMin, r.yMin), new Vector2(r.xMin, r.yMax), new Vector2(-1f, 0f)));
                if (!InOpen(new Vector2(r.xMax + 0.5f, r.center.y))) edges.Add((new Vector2(r.xMax, r.yMin), new Vector2(r.xMax, r.yMax), new Vector2(1f, 0f)));
                if (!InOpen(new Vector2(r.center.x, r.yMin - 0.5f))) edges.Add((new Vector2(r.xMin, r.yMin), new Vector2(r.xMax, r.yMin), new Vector2(0f, -1f)));
            }
            // front row: crown front 0-0.3 m from the opened edge, trunk >= 1.2 m
            foreach (var (a, b, nrm) in edges)
            {
                float len = Vector2.Distance(a, b); var d = (b - a) / len;
                for (float s = -0.4f; s <= len + 0.4f; s += cell * 0.85f)
                {
                    uint h; unchecked { h = ((uint)(Mathf.RoundToInt((a.x + d.x * s) * 10f) * 73856093) ^ (uint)(Mathf.RoundToInt((a.y + d.y * s) * 10f) * 19349663) ^ 15937u); }
                    int size = SizePick(h >> 16), tint = (int)((h >> 24) % 3); float yaw = ((h >> 20) % 24) * 15f;
                    float reach = InstHull(src, Vector2.zero, yaw, SizeLevels[size]).Max(x => Vector2.Dot(x, -nrm));
                    var e = a + d * (s + (((h >> 12) & 15) / 15f - 0.5f) * 0.4f);
                    var p = e + nrm * Mathf.Max(TrunkFront, reach + ((h >> 4) & 255) / 255f * 0.28f + 0.01f);
                    var hull = InstHull(src, p, yaw, SizeLevels[size]);
                    for (int k = 0; k < 10 && PolyOpenDist(hull) < 0f; k++) { p += nrm * 0.05f; hull = InstHull(src, p, yaw, SizeLevels[size]); }
                    if (!Legal(p, hull, TrunkFront) || trees.Any(t => (t.uv - p).sqrMagnitude < 0.7f * 0.7f * cell * cell)) continue;
                    trees.Add(new TreeInst { uv = p, size = size, tint = tint, yaw = yaw, hull = hull });
                }
            }
            int front = trees.Count - grid;
            // cliff tops: sparser T05 on the mesa tops, a few on the rim leaning out over the edge
            int onTop = 0;
            foreach (var (uv, y, rim) in cliffTop)
            {
                uint h; unchecked { h = ((uint)(Mathf.RoundToInt(uv.x * 10f) * 73856093) ^ (uint)(Mathf.RoundToInt(uv.y * 10f) * 19349663) ^ 0x51u); }
                int size = rim ? 2 + (int)((h >> 16) % 3) : SizePick(h >> 16);
                trees.Add(new TreeInst { uv = uv, y = y, size = size, tint = (int)((h >> 24) % 3), yaw = ((h >> 20) % 24) * 15f, hull = InstHull(src, uv, 0f, SizeLevels[size]) }); onTop++;
            }

            s_lastTrees = trees; s_lastSrc = src;   // instantiated by PlaceForest (shared / per-shore split in Build)

            var fr = trees.Skip(grid).Select(t => PolyOpenDist(t.hull)).ToList();
            var ft = trees.Skip(grid).Select(t => OpenDist(t.uv)).ToList();
            float depthMax = trees.Where(t => t.y < 0.01f).Max(t => OpenDist(t.uv) + crown * 0.5f);
            int intr = trees.Count(t => PolyOpenDist(t.hull) < 0f);
            s_checks.AppendLine($"CHECK forest T05: source top {src.height:F2} m, crown dia {src.crown:F2} m (scale 1); scale {src.scale:F3} x size {string.Join("/", SizeLevels)} -> tops {string.Join("/", SizeLevels.Select(x => (x * top).ToString("F2")))} m, crown {crown:F2} m at 1.0; " +
                $"cell {cell:F2} m ({spacingK} x crown), jitter +-{jitter:F2}; {trees.Count} trees ({grid} band + {front} front row + {onTop} on the cliff tops); front row trunk {(ft.Count > 0 ? ft.Min() : 0f):F2}..{(ft.Count > 0 ? ft.Max() : 0f):F2} m, crown front {(fr.Count > 0 ? fr.Min() : 0f):F2}..{(fr.Count > 0 ? fr.Max() : 0f):F2} m; " +
                $"band depth to the outermost crown {depthMax:F1} m; crowns intruding the opened 3x3: {intr}");
            return $"Forest_T05 [{s_tag}]: {trees.Count} trees";
        }

        static List<TreeInst> s_lastTrees; static TreeSource s_lastSrc;
        static readonly Dictionary<(Material, int), Material> s_worldMat = new Dictionary<(Material, int), Material>(), s_tintMat = new Dictionary<(Material, int), Material>();
        /// <summary>Instantiates trees as linked T05 prefab instances under parent (material copies cached across calls of one Build).</summary>
        static void PlaceForest(Transform parent, List<TreeInst> trees, TreeSource src, out int renderers, out long tris)
        {
            // 11-13: linked T05 prefab instances (no baked forest meshes): one shared mesh set, our material copies (world-space gradient per size
            // level, canopy tint per material), Batching Static so the canopy combines at load; the master's blob card is switched off
            var canopy = (JArray)Cal()["canopy"];
            var prefab = S3.Load<GameObject>(T05Path); var rootScale = prefab.transform.localScale;
            var worldMat = s_worldMat; var tintMat = s_tintMat;
            Material Tint(Material m, int tint)
            {
                if (m == null || !m.HasProperty("_BaseColor")) return m;
                if (tintMat.TryGetValue((m, tint), out var c)) return c;
                string path = $"{OutDir}/ForestMats/{m.name}_t{tint}.mat";
                c = new Material(m) { name = Path.GetFileNameWithoutExtension(path) };
                // the r3 canopy tint was a linear vertex-colour multiplier on leaf / mist vertices: the same multiplier on _BaseColor (linear)
                var b = m.GetColor("_BaseColor"); var bl = b.linear; var k = VC(canopy[tint]);
                c.SetColor("_BaseColor", new Color(Mathf.LinearToGammaSpace(bl.r * k.r), Mathf.LinearToGammaSpace(bl.g * k.g), Mathf.LinearToGammaSpace(bl.b * k.b), b.a));
                AssetDatabase.CreateAsset(c, path); tintMat[(m, tint)] = c; return c;
            }
            renderers = 0; tris = 0;
            foreach (var t in trees)
            {
                float sc = src.scale * SizeLevels[t.size];
                var inst = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent.gameObject.scene);
                inst.transform.SetParent(parent, false);
                inst.transform.SetPositionAndRotation(S3.UV(t.uv.x, t.uv.y, S3.H + t.y), Quaternion.Euler(0f, t.yaw, 0f));
                inst.transform.localScale = rootScale * sc;
                var toRoot = inst.transform.worldToLocalMatrix;
                foreach (var r in inst.GetComponentsInChildren<MeshRenderer>(true))
                {
                    var mats = r.sharedMaterials;
                    // 4d: the master's fake ground-shadow card is dropped once the canopy casts real shadows (no double shadow)
                    if (mats.Any(m => m != null && m.shader != null && m.shader.name == "Lab/LabBlobShade")) { r.enabled = false; continue; }
                    var partM = Matrix4x4.Scale(rootScale) * (toRoot * r.transform.localToWorldMatrix);
                    var nm = new Material[mats.Length]; bool opaque = false;
                    for (int sm = 0; sm < mats.Length; sm++)
                    {
                        if (mats[sm] == null) continue;
                        nm[sm] = mats[sm].name.Contains("Trunk") ? TrunkMaterial(mats[sm]) : Tint(WorldSpaceMaterial(mats[sm], partM, sc, t.size, worldMat, t.y), t.tint);
                        opaque |= nm[sm].renderQueue <= 2500;
                    }
                    r.sharedMaterials = nm;
                    // 4d: opaque canopy / trunk cast real shadows (the master T05 has casting off and relies on the blob card)
                    r.shadowCastingMode = opaque ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.Off;
                    var mf = r.GetComponent<MeshFilter>(); if (mf != null && mf.sharedMesh != null) tris += mf.sharedMesh.triangles.Length / 3;
                    renderers++;
                }
                foreach (var tr in inst.GetComponentsInChildren<Transform>(true)) GameObjectUtility.SetStaticEditorFlags(tr.gameObject, StaticEditorFlags.BatchingStatic);
            }
        }

        static Material s_trunk;
        /// <summary>Bark tone copy of the T05 trunk material (screen target ~#4A3526); the shared material stays untouched.</summary>
        static Material TrunkMaterial(Material src)
        {
            if (s_trunk != null) return s_trunk;
            string path = $"{OutDir}/BV3S4_T05Trunk.mat";
            var copy = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (copy == null) { copy = new Material(src) { name = "BV3S4_T05Trunk" }; AssetDatabase.CreateAsset(copy, path); }
            else { copy.shader = src.shader; copy.CopyPropertiesFromMaterial(src); copy.shaderKeywords = src.shaderKeywords; }
            copy.SetColor("_BaseColor", Hx((string)(Cal()["trunk"] ?? "#2C2118")));
            EditorUtility.SetDirty(copy);
            return s_trunk = copy;
        }

        // 灯光会话 11-13 试定
        const float LeafVegShadowDark = 0.40f, LeafFluffyWrap = 0.42f;
        static readonly Color LeafGradBottom = new Color(0.42f, 0.54f, 0.44f, 1f);

        static Material WorldSpaceMaterial(Material m, Matrix4x4 part, float scale, int sizeLevel, Dictionary<(Material, int), Material> cache, float yBase = 0f)
        {
            if (m == null || !m.IsKeywordEnabled("_LAB_FLUFFY") || !m.HasProperty("_GradRange")) return m;
            int yKey = Mathf.RoundToInt(yBase * 10f); int key = sizeLevel + yKey * 100;
            if (cache.TryGetValue((m, key), out var c)) return c;
            string path = $"{OutDir}/BV3S4_{m.name}_World_s{sizeLevel}{(yBase > 0.01f ? "_cliff" + yKey : "")}.mat";
            var copy = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (copy == null) { copy = new Material(m) { name = Path.GetFileNameWithoutExtension(path) }; AssetDatabase.CreateAsset(copy, path); }
            else { copy.shader = m.shader; copy.CopyPropertiesFromMaterial(m); copy.shaderKeywords = m.shaderKeywords; }
            var g = m.GetVector("_GradRange");
            // cliff-top trees: one copy per size level and mesa height (gradient shifted by yBase)
            float Y(float os) => part.MultiplyPoint3x4(new Vector3(0f, os, 0f)).y * scale + S3.H + yBase;
            copy.SetVector("_GradRange", new Vector4(Y(g.x), Y(g.y), g.z, g.w));
            // 灯光会话 11-13 试定 (one set, always together): darker crown undersides / gaps
            copy.SetFloat("_VegShadowDark", LeafVegShadowDark); copy.SetColor("_GradBottom", LeafGradBottom); copy.SetFloat("_FluffyWrap", LeafFluffyWrap);
            EditorUtility.SetDirty(copy);
            cache[(m, key)] = copy;
            return copy;
        }

        // ── fog (r3, 勾哥 11-13: back to the pre-research fog): three stacked soft sheets over everything outside the band and the beach ends ───
        static Material FogMaterial(string name, float clump, float clumpScale, float variation)
        {
            string path = $"{OutDir}/{name}.mat";
            var mat = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (mat == null) { mat = new Material(AssetDatabase.LoadAssetAtPath<Shader>("Assets/Shaders/Lab/LabBaseFog.shader")) { name = name }; AssetDatabase.CreateAsset(mat, path); }
            mat.SetColor("_BaseColor", Hx((string)(Cal()["fogLight"] ?? "#E6EEEA"))); mat.SetColor("_DarkColor", Hx((string)(Cal()["fogDark"] ?? "#C9D8D2")));
            mat.SetFloat("_Clump", clump); mat.SetFloat("_ClumpScaleM", clumpScale); mat.SetFloat("_Variation", variation);
            EditorUtility.SetDirty(mat);
            return mat;
        }

        static string BuildFog(Transform node)
        {
            var parent = new GameObject("Fog").transform; parent.SetParent(node, false);
            var cols = new List<float>();
            for (float u = -Ext; u <= Ext + 1e-3f; u += 2f) cols.Add(u);   // one uniform column spacing (the r2 seam sat where 0.5 m met 3 m columns)
            float Mask(float u, float v)
            {
                float e = Mathf.Sqrt(Mathf.Pow((u - CliffCentre.x) / CliffHalf.x, 2f) + Mathf.Pow((v - CliffCentre.y) / CliffHalf.y, 2f));
                // 4e: the shore-side exit band is pushed +-1.3 m by low-frequency noise along u (no soft edge running parallel to the shore)
                float push = 2.6f * (Noise1(u * 0.22f, 91) * 0.7f + Noise1(u * 0.61f, 92) * 0.3f - 0.5f);
                return Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(0.7f, 1.1f, e)) * (1f - Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(W(u) - 3f - 1.3f + push, W(u) - 0.3f - 1.3f + push, v)));
            }
            // beach fog starts 14 -> 18 m from the opened land (= |u| 20 -> 24 for Start_3x3)
            float Beach(float u, float v) => Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(14f, 18f, HullDist(new Vector2(u, v))));
            // low sheet: 0 -> 0.2 over the last metre of the band, 0.2 -> 0.6 over the first 4 m outside, 0.6 -> 0.9 by 12 m
            float Low(float u, float v)
            {
                if (v > LandEdge(u)) return 0.85f * Beach(u, v) * Mask(u, v);
                float d = BandOut(new Vector2(u, v));
                float a = d < 0f ? 0.2f * Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(-1f, 0f, d)) : d < 4f ? Mathf.Lerp(0.2f, 0.6f, d / 4f) : Mathf.Lerp(0.6f, 0.9f, Mathf.Clamp01((d - 4f) / 8f));
                return a * Mask(u, v);
            }
            float CloudA(float u, float v) => (v > LandEdge(u) ? Beach(u, v) : Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(1f, 8f, BandOut(new Vector2(u, v))))) * 0.95f * Mask(u, v);
            float CloudB(float u, float v) => (v > LandEdge(u) ? Beach(u, v) : Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(4f, 14f, BandOut(new Vector2(u, v))))) * 0.92f * Mask(u, v);
            var layers = new (float y, Func<float, float, float> a, Material mat)[]
            {
                (0.4f, Low, FogMaterial("BV3S4_BaseFog_Low", 0f, 10f, 0.05f)),
                (1.6f, CloudA, FogMaterial("BV3S4_BaseFog_CloudA", 0.75f, 12f, 0.08f)),
                (3.2f, CloudB, FogMaterial("BV3S4_BaseFog_CloudB", 1.0f, 20f, 0.1f)),
            };
            var r = new List<string>(); int li = 0;
            foreach (var (y, a, mat) in layers)
            {
                const int rows = 90;
                r.Add(S3.Grid(parent, $"FogSheet_{y:F1}m", mat, cols.Count, rows, (i, k) =>
                {
                    float u = cols[i], vEnd = W(u) - 0.3f;
                    float v = Mathf.Lerp(-Ext, vEnd, k / (float)rows);
                    return (u, v, S3.H + y);
                }, (i, k, u, v) => new Color(1f, 1f, 1f, a(u, v)), null, $"{OutDir}/BV3S4_FogSheet{li}{s_tag}.asset", null, null, null));
                li++;
            }
            s_checks.AppendLine("CHECK fog (r3 sheets): low 0.4 m (0.2 -> 0.6 over 4 m outside the band, -> 0.9 by 12 m), cloud puffs 1.6 m (to 0.95) and 3.2 m (to 0.92); " +
                "fogLight / fogDark from the calibration file; beach fog 14 -> 18 m from the opened land; ends 1.6-4.3 m before the waterline (noise-pushed), never over the water");
            return "Fog: " + string.Join(" ", r);
        }

        // ── cliff behind the camp: BaseCliffD6 (one stepped rock body, one turf cap volume per tier) ────────────
        // 勾哥 11-14: the J01-cape pieces + recolour + boundary-grown turf skirts are retired, nothing of them is kept.
        /// <summary>Fog-mask ellipse around the cliff (uv metres).</summary>
        static readonly Vector2 CliffCentre = new Vector2(-5f, -21f), CliffHalf = new Vector2(9f, 6f);

        static string BuildCliff(Transform node, List<Vector2[]> foot, List<(Vector2 uv, float y, bool rim)> topTrees)
        {
            // outputs of the retired pipeline
            foreach (var f in new[] { "Cliff", "CliffTurf" }) if (AssetDatabase.IsValidFolder($"{OutDir}/{f}")) AssetDatabase.DeleteAsset($"{OutDir}/{f}");
            foreach (var f in new[] { "BV3S4_CliffRimSkirt.asset", "BV3S4_CliffWall.mat", "BV3S4_CliffTurf.mat" }) AssetDatabase.DeleteAsset($"{OutDir}/{f}");
            foreach (var guid in AssetDatabase.FindAssets("_cliff t:Material", new[] { OutDir }))
            {
                string path = AssetDatabase.GUIDToAssetPath(guid);
                if (Path.GetFileNameWithoutExtension(path).EndsWith("_cliff")) AssetDatabase.DeleteAsset(path);   // pre-D6 name (one mesa height)
            }
            BaseCliffD6.Grass = VC(Cal()["grass"]); BaseCliffD6.Rock = VC(Cal()["cliff"]["main"]);
            string line = BaseCliffD6.Build(node, w => S3.WorldToUV(w), foot, topTrees);
            s_checks.AppendLine("CHECK cliff: " + line);
            return line;
        }
    }
}
