// er-lookdev Unity 实验:在预览场景里内存渲染,不动打开的场景、不改工程资产、不存盘。
// unity command script run --file LookdevLab.cs --entry LookdevLab.Run
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.SceneManagement;
using Object = UnityEngine.Object;

public static class LookdevLab
{
    const int W = 1080, H = 2340;
    static readonly string OutDir = Path.Combine(Path.GetTempPath(), "LookdevLab");
    const BindingFlags BF = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
    static readonly System.Globalization.CultureInfo Inv = System.Globalization.CultureInfo.InvariantCulture;

    static void SetF(object o, string f, object v)
    {
        var t = o.GetType(); FieldInfo fi = null;
        while (t != null && fi == null) { fi = t.GetField(f, BF); t = t.BaseType; }
        if (fi == null) throw new Exception("no field " + f + " on " + o.GetType().Name);
        if (fi.FieldType.IsEnum) v = Enum.ToObject(fi.FieldType, Convert.ToInt32(v));
        fi.SetValue(o, v);
    }
    static object GetF(object o, string f)
    {
        var t = o.GetType(); FieldInfo fi = null;
        while (t != null && fi == null) { fi = t.GetField(f, BF); t = t.BaseType; }
        if (fi == null) throw new Exception("no field " + f + " on " + o.GetType().Name);
        return fi.GetValue(o);
    }

    public static string Run()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode) return "REFUSED: play mode";
        if (EditorApplication.isCompiling) return "REFUSED: compiling";
        Directory.CreateDirectory(OutDir);
        var log = new StringBuilder();
        var json = new StringBuilder("{\n");
        var srcAsset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/Mobile_RPAsset.asset");
        var srcRenderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/Settings/Mobile_Renderer.asset");
        var prevQ = QualitySettings.renderPipeline;
        bool asyncWas = ShaderUtil.allowAsyncCompilation; ShaderUtil.allowAsyncCompilation = false;
        var trash = new List<Object>();
        Scene scene = default; bool overrideOn = false; bool swapped = false;
        try
        {
            // ---- 管线资产和渲染器的内存副本(原件一个字段都不碰) ----
            var asset = Object.Instantiate(srcAsset); asset.name = "LookdevLab_RP"; asset.hideFlags = HideFlags.HideAndDontSave; trash.Add(asset);
            var rdata = Object.Instantiate(srcRenderer); rdata.name = "LookdevLab_Renderer"; rdata.hideFlags = HideFlags.HideAndDontSave; trash.Add(rdata);
            var ssaoSrc = srcRenderer.rendererFeatures.First(f => f != null && f.GetType().Name == "ScreenSpaceAmbientOcclusion");
            var ssao = Object.Instantiate(ssaoSrc); ssao.name = "SSAO_lab"; ssao.hideFlags = HideFlags.HideAndDontSave; trash.Add(ssao);
            SetF(rdata, "m_RendererFeatures", new List<ScriptableRendererFeature> { ssao });
            SetF(asset, "m_RendererDataList", new ScriptableRendererData[] { rdata });
            SetF(asset, "m_DefaultRendererIndex", 0);
            var ssaoSet = GetF(ssao, "m_Settings");
            ssao.SetActive(false);
            QualitySettings.renderPipeline = asset; swapped = true;

            // ---- 预览场景和光照设置覆盖 ----
            scene = EditorSceneManager.NewPreviewScene();
            Unsupported.SetOverrideLightingSettings(scene); overrideOn = true;
            RenderSettings.fog = false; RenderSettings.skybox = null;
            RenderSettings.ambientMode = AmbientMode.Trilight; RenderSettings.ambientIntensity = 1f;
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom; RenderSettings.reflectionIntensity = 0f;

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            Material Mat(string n, Color srgb, Texture2D occ = null)
            {
                var m = new Material(lit) { name = n, hideFlags = HideFlags.HideAndDontSave }; trash.Add(m);
                m.SetColor("_BaseColor", srgb); m.SetFloat("_Smoothness", 0f); m.SetFloat("_Metallic", 0f);
                m.SetFloat("_SpecularHighlights", 0f); m.EnableKeyword("_SPECULARHIGHLIGHTS_OFF");
                m.SetFloat("_EnvironmentReflections", 0f); m.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");
                if (occ != null) { m.SetTexture("_OcclusionMap", occ); m.SetFloat("_OcclusionStrength", 1f); m.EnableKeyword("_OCCLUSIONMAP"); }
                return m;
            }
            var occTex = new Texture2D(4, 4, TextureFormat.RGBA32, false, true) { hideFlags = HideFlags.HideAndDontSave }; trash.Add(occTex);
            occTex.SetPixels32(Enumerable.Repeat(new Color32(128, 128, 128, 255), 16).ToArray()); occTex.Apply();
            var mGround = Mat("ground", new Color(.6f, .6f, .6f));
            var mGroundOcc = Mat("groundOcc", new Color(.6f, .6f, .6f), occTex);
            var mWhite = Mat("white", new Color(.85f, .85f, .85f));
            var mYellow = Mat("yellow", new Color(.95f, .78f, .15f));

            GameObject Prim(PrimitiveType t, string n, Vector3 pos, Vector3 scale, Material m, Vector3 euler = default, bool cast = true)
            {
                var g = GameObject.CreatePrimitive(t); g.name = n; Object.DestroyImmediate(g.GetComponent<Collider>());
                SceneManager.MoveGameObjectToScene(g, scene);
                g.transform.position = pos; g.transform.localScale = scale; g.transform.eulerAngles = euler;
                var r = g.GetComponent<MeshRenderer>(); r.sharedMaterial = m; r.shadowCastingMode = cast ? ShadowCastingMode.On : ShadowCastingMode.Off;
                return g;
            }
            // 地面(Plane 基元 10 m,放大 8 倍)
            Prim(PrimitiveType.Plane, "ground", Vector3.zero, new Vector3(8, 1, 8), mGround, default, false);
            // A 楼块 2.5 x 4 x 2.5
            Prim(PrimitiveType.Cube, "boxA", new Vector3(-2.2f, 2f, 3f), new Vector3(2.5f, 4f, 2.5f), mWhite);
            // 细杆和栅栏
            Prim(PrimitiveType.Cylinder, "pole", new Vector3(0.5f, 1.5f, 6f), new Vector3(0.1f, 1.5f, 0.1f), mWhite);
            for (int i = 0; i < 6; i++) Prim(PrimitiveType.Cube, "slat" + i, new Vector3(1.6f + i * 0.16f, 0.6f, 8f), new Vector3(0.04f, 1.2f, 0.04f), mWhite);
            // 角色大小的胶囊
            Prim(PrimitiveType.Capsule, "char", new Vector3(1.4f, 0.9f, -1.5f), new Vector3(0.6f, 0.9f, 0.6f), mYellow);
            // 环境光探针球(架在细柱上)
            var sphC = new Vector3(-2.2f, 1.5f, -4.5f); const float sphR = 0.8f;
            Prim(PrimitiveType.Sphere, "sphere", sphC, Vector3.one * sphR * 2f, mWhite);
            Prim(PrimitiveType.Cylinder, "stand", new Vector3(-2.2f, 0.35f, -4.5f), new Vector3(0.12f, 0.35f, 0.12f), mWhite);
            // 遮蔽测试方块 1.5 m,两侧各半条带烘焙遮蔽(0.5)的地面条
            Prim(PrimitiveType.Cube, "aoBox", new Vector3(1.8f, 0.75f, -6.5f), Vector3.one * 1.5f, mWhite);
            var s1 = Prim(PrimitiveType.Quad, "stripLit", new Vector3(0.85f, 0.002f, -6.875f), new Vector3(0.4f, 0.75f, 1f), mGroundOcc, new Vector3(90, 0, 0), false);
            var s2 = Prim(PrimitiveType.Quad, "stripShade", new Vector3(2.175f, 0.002f, -7.45f), new Vector3(0.75f, 0.4f, 1f), mGroundOcc, new Vector3(90, 0, 0), false);

            // 太阳
            var sunGo = new GameObject("sun"); SceneManager.MoveGameObjectToScene(sunGo, scene);
            var sun = sunGo.AddComponent<Light>(); sun.type = LightType.Directional; sun.color = new Color(1f, .95f, .85f); sun.intensity = 1.3f;
            sun.shadows = LightShadows.Soft; sun.shadowStrength = 1f; sun.shadowBias = 0.05f; sun.shadowNormalBias = 0.4f;
            sunGo.transform.eulerAngles = new Vector3(50, 120, 0);
            var sunData = sunGo.AddComponent<UniversalAdditionalLightData>();
            Vector3 L = -sunGo.transform.forward; Vector3 hdir = new Vector3(sunGo.transform.forward.x, 0, sunGo.transform.forward.z).normalized;
            float cot = Mathf.Cos(50 * Mathf.Deg2Rad) / Mathf.Sin(50 * Mathf.Deg2Rad);

            // 相机:俯角 46、FOV 25、离脚下 40 m,脚下在画面正中
            var camGo = new GameObject("cam"); SceneManager.MoveGameObjectToScene(camGo, scene);
            var cam = camGo.AddComponent<Camera>(); cam.scene = scene; cam.cameraType = CameraType.Game;
            cam.fieldOfView = 25f; cam.nearClipPlane = 0.5f; cam.farClipPlane = 300f; cam.aspect = (float)W / H;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(.2f, .25f, .4f); cam.allowHDR = true; cam.allowMSAA = true;
            var rot = Quaternion.Euler(46, 0, 0); camGo.transform.SetPositionAndRotation(-(rot * Vector3.forward) * 40f, rot);
            var cd = camGo.AddComponent<UniversalAdditionalCameraData>(); cd.renderPostProcessing = false; cd.renderShadows = true; cd.SetRenderer(0);
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4, hideFlags = HideFlags.HideAndDontSave }; trash.Add(rt);
            cam.targetTexture = rt;
            var tex = new Texture2D(W, H, TextureFormat.RGBA32, false, false) { hideFlags = HideFlags.HideAndDontSave }; trash.Add(tex);
            Color32[] px = null;

            // 镜头能看到的最远地面点(四个角的视线和 y=0 求交)
            float farGround = 0, nearGround = 1e9f;
            foreach (var vp in new[] { new Vector3(0, 0, 0), new Vector3(1, 0, 0), new Vector3(0, 1, 0), new Vector3(1, 1, 0), new Vector3(.5f, .5f, 0) })
            {
                var ray = cam.ViewportPointToRay(vp); float t = -ray.origin.y / ray.direction.y; farGround = Mathf.Max(farGround, t); nearGround = Mathf.Min(nearGround, t);
            }
            float fit = Mathf.Ceil(farGround + 1f);
            log.AppendLine($"depth feet {cam.WorldToViewportPoint(Vector3.zero).z:F1} aoBox {cam.WorldToViewportPoint(new Vector3(1.8f, 0, -7.25f)).z:F1} boxA {cam.WorldToViewportPoint(new Vector3(-2.2f, 0, 1.75f)).z:F1}");
            log.AppendLine($"camera dist to ground: near {nearGround:F1} m, far {farGround:F1} m, fit shadow distance {fit:F0} m");

            void Shoot(string id)
            {
                cam.Render(); cam.Render();
                var prev = RenderTexture.active; RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = prev;
                File.WriteAllBytes(Path.Combine(OutDir, id + ".png"), tex.EncodeToPNG());
                px = tex.GetPixels32();
            }
            float[] Med(Vector3 world, int r = 3)
            {
                var v = cam.WorldToViewportPoint(world); int cx = Mathf.RoundToInt(v.x * W), cy = Mathf.RoundToInt(v.y * H);
                var rs = new List<int>(); var gs = new List<int>(); var bs = new List<int>();
                for (int y = cy - r; y <= cy + r; y++) for (int x = cx - r; x <= cx + r; x++)
                {
                    if (x < 0 || y < 0 || x >= W || y >= H) continue; var c = px[y * W + x]; rs.Add(c.r); gs.Add(c.g); bs.Add(c.b);
                }
                if (rs.Count == 0) return new float[] { -1, -1, -1, cx, cy };
                rs.Sort(); gs.Sort(); bs.Sort(); return new float[] { rs[rs.Count / 2], gs[gs.Count / 2], bs[bs.Count / 2], cx, cy };
            }
            string J(float[] a) => "[" + string.Join(",", a.Select(x => x.ToString("0.##", Inv))) + "]";
            float Lum(Vector3 world) { var v = cam.WorldToViewportPoint(world); int cx = Mathf.Clamp(Mathf.RoundToInt(v.x * W), 0, W - 1), cy = Mathf.Clamp(Mathf.RoundToInt(v.y * H), 0, H - 1); var c = px[cy * W + cx]; return (0.2126f * c.r + 0.7152f * c.g + 0.0722f * c.b) / 255f; }
            float[] Series(Vector3 a, Vector3 b, int n) { var ls = new float[n]; for (int i = 0; i < n; i++) ls[i] = Lum(Vector3.Lerp(a, b, i / (n - 1f))); return ls; }
            string Fm(float v) => v.ToString("0.###", Inv);
            // 影子边:从影子里扫到受光处,给 10%–90% 过渡宽度(米)
            string Edge(Vector3 a, Vector3 b, int n)
            {
                var ls = Series(a, b, n); float lo = ls.Take(n / 8).Average(), hi = ls.Skip(n - n / 8).Average(); float len = (b - a).magnitude;
                float t10 = lo + (hi - lo) * 0.1f, t90 = lo + (hi - lo) * 0.9f; int i10 = -1, i90 = -1;
                for (int i = 0; i < n; i++) { if (i10 < 0 && ls[i] >= t10) i10 = i; if (ls[i] >= t90) { i90 = i; break; } }
                return "{\"lo\":" + Fm(lo) + ",\"hi\":" + Fm(hi) + ",\"edge10_90_m\":" + Fm((i90 - i10) * len / (n - 1)) + "}";
            }
            // 细条影子:横切,给最暗处的对比、低于半高的总宽(米)、能数出几条
            string Dips(Vector3 a, Vector3 b, int n)
            {
                var ls = Series(a, b, n); float hi = ls.Max(), lo = ls.Min(); float len = (b - a).magnitude; float half = (hi + lo) / 2;
                int below = ls.Count(v => v < half); int dips = 0; bool inDip = false;
                for (int i = 0; i < n; i++) { bool d = ls[i] < hi - 0.03f; if (d && !inDip) dips++; inDip = d; }
                return "{\"contrast\":" + Fm(1 - lo / Mathf.Max(hi, 1e-4f)) + ",\"below_half_m\":" + Fm(below * len / (n - 1)) + ",\"dips\":" + dips + "}";
            }
            string Sphere() { var v = Shader.GetGlobalVector("_CascadeShadowSplitSpheres0"); var sz = Shader.GetGlobalVector("_MainLightShadowmapSize"); float r = Mathf.Sqrt(Mathf.Max(v.w, 0)); return "{\"sphere_r_m\":" + Fm(r) + ",\"map_px\":" + Fm(sz.z) + ",\"texel_m\":" + Fm(2 * r / Mathf.Max(sz.z, 1)) + "}"; }

            void Shadow(float dist, int res, int cascades, int soft /*0 hard,1 low,2 med,3 high*/)
            {
                SetF(asset, "m_ShadowDistance", dist); SetF(asset, "m_MainLightShadowmapResolution", res); SetF(asset, "m_ShadowCascadeCount", cascades);
                SetF(asset, "m_SoftShadowsSupported", soft > 0); if (soft > 0) SetF(asset, "m_SoftShadowQuality", soft);
                sun.shadows = soft > 0 ? LightShadows.Soft : LightShadows.Hard;
            }
            void Ambient(Color sky, Color eq, Color gr) { RenderSettings.ambientSkyColor = sky; RenderSettings.ambientEquatorColor = eq; RenderSettings.ambientGroundColor = gr; }
            void Ssao(bool on, bool afterOpaque, float intensity, float radius, float direct, float falloff = 60f)
            {
                ssao.SetActive(on); SetF(ssaoSet, "Falloff", falloff); SetF(ssaoSet, "AfterOpaque", afterOpaque); SetF(ssaoSet, "Intensity", intensity); SetF(ssaoSet, "Radius", radius); SetF(ssaoSet, "DirectLightingStrength", direct);
            }
            var SKY = new Color(.55f, .65f, .95f); var EQ = new Color(.45f, .50f, .70f); var WARM = new Color(.95f, .60f, .30f);

            // 探针点
            Vector3 SphP(Vector3 n) => sphC + n.normalized * sphR;
            var probes = new (string, Vector3)[] {
                ("sphere_up45_shade", SphP(new Vector3(.6f, .5f, -.62f))), ("sphere_side_shade", SphP(new Vector3(.5f, 0, -.866f))), ("sphere_down30_shade", SphP(new Vector3(.4f, -.5f, -.77f))),
                ("sphere_top_lit", SphP(new Vector3(-.2f, .9f, -.3f))),
                ("boxA_wall_shade_top", new Vector3(-2.2f, 3.6f, 1.75f)), ("boxA_wall_shade_mid", new Vector3(-2.2f, 2.0f, 1.75f)), ("boxA_wall_shade_low", new Vector3(-2.2f, 0.3f, 1.75f)),
                ("boxA_roof_lit", new Vector3(-2.2f, 4f, 3f)), ("ground_lit", new Vector3(0.2f, 0, -3f)), ("ground_in_boxA_shadow", new Vector3(-0.2f, 0, 1.2f)),
            };
            string ProbeJson() => "{" + string.Join(",", probes.Select(p => $"\"{p.Item1}\":{J(Med(p.Item2))}")) + "}";

            Ambient(SKY, EQ, EQ); Shadow(53f, 2048, 1, 2); Shoot("_warmup"); Shoot("_warmup");
            // ================= E1 三色环境光的地面色 =================
            Shadow(fit, 2048, 1, 2); Ssao(false, false, 1, .15f, .3f);
            json.Append("\"E1_ambient\":{\n");
            foreach (var (id, gr) in new[] { ("ground_eq_equator", EQ), ("ground_warm", WARM), ("ground_black", Color.black) })
            {
                Ambient(SKY, EQ, gr);
                var dirs = new[] { Vector3.up, new Vector3(0, .5f, -.866f), new Vector3(0, 0, -1), new Vector3(0, -.5f, -.866f), Vector3.down }; var outc = new Color[5];
                RenderSettings.ambientProbe.Evaluate(dirs, outc);
                Shoot("E1_" + id);
                json.Append($" \"{id}\":{{\"sh_up_up30_side_down30_down\":[{string.Join(",", outc.Select(c => $"[{c.r.ToString("0.###", Inv)},{c.g.ToString("0.###", Inv)},{c.b.ToString("0.###", Inv)}]"))}],\"probes\":{ProbeJson()}}},\n");
            }
            json.Append(" \"note\":\"probe = sRGB 0-255 median 7x7, then pixel x,y\"},\n");
            Ambient(SKY, EQ, EQ);

            // ================= E2 阴影距离 =================
            // 楼块右上棱的影子边:x = -0.95 + 4*cot*hdir.x,扫 z=1.3 这条线
            float edgeX = -0.95f + 4f * cot * hdir.x;
            Vector3 eA = new Vector3(edgeX - 1.2f, 0, 1.3f), eB = new Vector3(edgeX + 1.2f, 0, 1.3f);
            // 细杆影子:离杆脚 1.2 m 处横切
            Vector3 pc = new Vector3(0.5f, 0, 6f) + hdir * 1.2f; Vector3 pperp = new Vector3(-hdir.z, 0, hdir.x);
            Vector3 pA = pc - pperp * 0.5f, pB = pc + pperp * 0.5f;
            Vector3 fc = new Vector3(2.0f, 0, 8f) + hdir * 0.6f; Vector3 fA = fc - pperp * 0.6f, fB = fc + pperp * 0.6f;
            json.Append("\"E2_shadow_distance\":{\n");
            foreach (var (id, dist, res, casc, soft) in new[] {
                ("d90_r2048_hard", 90f, 2048, 1, 0), ($"d{fit:F0}_r2048_hard", fit, 2048, 1, 0), ("d90_r1024_hard", 90f, 1024, 1, 0), ($"d{fit:F0}_r1024_hard", fit, 1024, 1, 0),
                ("d90_r2048_softMed", 90f, 2048, 1, 2), ($"d{fit:F0}_r2048_softMed", fit, 2048, 1, 2), ($"d{fit:F0}_r1024_softMed", fit, 1024, 1, 2), ("d90_r2048_c2_hard", 90f, 2048, 2, 0) })
            {
                Shadow(dist, res, casc, soft); Shoot("E2_" + id);
                json.Append($" \"{id}\":{{\"box_edge\":{Edge(eA, eB, 480)},\"pole\":{Dips(pA, pB, 260)},\"fence\":{Dips(fA, fB, 320)},\"map\":{Sphere()}}},\n");
            }
            json.Append($" \"fit_m\":{fit.ToString("0", Inv)},\"far_ground_m\":{farGround.ToString("0.#", Inv)},\"near_ground_m\":{nearGround.ToString("0.#", Inv)}}},\n");

            // ================= E4 软阴影三档 =================
            json.Append("\"E4_soft\":{\n");
            foreach (var (id, res, soft) in new[] { ("r2048_hard", 2048, 0), ("r2048_low", 2048, 1), ("r2048_med", 2048, 2), ("r2048_high", 2048, 3), ("r1024_low", 1024, 1), ("r1024_med", 1024, 2), ("r1024_high", 1024, 3) })
            {
                Shadow(fit, res, 1, soft); Shoot("E4_" + id);
                json.Append($" \"{id}\":{{\"box_edge\":{Edge(eA, eB, 480)},\"pole\":{Dips(pA, pB, 260)},\"fence\":{Dips(fA, fB, 320)},\"map\":{Sphere()}}},\n");
            }
            json.Append(" \"note\":\"shadow distance = fit, 1 cascade\"},\n");

            // ================= E3 SSAO 和烘焙遮蔽叠加 =================
            Shadow(fit, 2048, 1, 2);
            var aoProbes = new (string, Vector3)[] {
                ("lit_baked_4cm", new Vector3(1.01f, 0, -6.9f)), ("lit_bare_4cm", new Vector3(1.01f, 0, -6.1f)), ("lit_baked_10cm", new Vector3(0.95f, 0, -6.9f)), ("lit_bare_10cm", new Vector3(0.95f, 0, -6.1f)),
                ("lit_baked_30cm", new Vector3(0.75f, 0, -6.9f)), ("lit_bare_30cm", new Vector3(0.75f, 0, -6.1f)),
                ("shade_baked_4cm", new Vector3(2.2f, 0, -7.29f)), ("shade_bare_4cm", new Vector3(1.5f, 0, -7.29f)), ("shade_baked_10cm", new Vector3(2.2f, 0, -7.35f)), ("shade_bare_10cm", new Vector3(1.5f, 0, -7.35f)),
                ("shade_baked_30cm", new Vector3(2.2f, 0, -7.55f)), ("shade_bare_30cm", new Vector3(1.6f, 0, -7.55f)),
                ("open_ground_lit", new Vector3(-0.5f, 0, -7.5f)), ("aoBox_wall_shade_4cm_up", new Vector3(1.8f, 0.04f, -7.25f)), ("aoBox_wall_shade_60cm_up", new Vector3(1.8f, 0.6f, -7.25f)),
                ("boxA_far_wall_shade_4cm_up", new Vector3(-2.2f, 0.04f, 1.75f)), ("boxA_far_ground_shade_4cm", new Vector3(-2.2f, 0, 1.71f)), ("boxA_far_ground_shade_60cm", new Vector3(-2.2f, 0, 1.15f)),
            };
            json.Append("\"E3_ssao\":{\n");
            foreach (var (id, on, after, inten, rad, direct, fall) in new[] {
                ("off", false, false, 1f, .15f, .3f, 60f), ("afterOpaque_I1_R015_F60", true, true, 1f, .15f, .3f, 60f), ("afterOpaque_I1_R015_F300", true, true, 1f, .15f, .3f, 300f),
                ("afterOpaque_I16_R04_F60", true, true, 1.6f, .4f, .25f, 60f), ("afterOpaque_I16_R04_F300", true, true, 1.6f, .4f, .25f, 300f),
                ("inShader_I16_R04_D025_F300", true, false, 1.6f, .4f, .25f, 300f), ("inShader_I16_R04_D0_F300", true, false, 1.6f, .4f, 0f, 300f), ("inShader_I16_R04_D1_F300", true, false, 1.6f, .4f, 1f, 300f) })
            {
                Ssao(on, after, inten, rad, direct, fall); Shoot("E3_" + id);
                json.Append($" \"{id}\":{{" + string.Join(",", aoProbes.Select(p => $"\"{p.Item1}\":{J(Med(p.Item2, 1))}")) + "},\n");
            }
            json.Append(" \"note\":\"baked strip occlusion map = 0.5 (URP Lit: indirect only)\"},\n");
            // ---- E3b 太阳转到正面:方块朝镜头的墙和墙脚地面都受光 ----
            sunGo.transform.eulerAngles = new Vector3(50, -20, 0);
            json.Append("\"E3b_ssao_sunlit_corner\":{\n");
            var litProbes = new (string, Vector3)[] {
                ("ground_baked_4cm", new Vector3(2.2f, 0, -7.29f)), ("ground_bare_4cm", new Vector3(1.5f, 0, -7.29f)), ("ground_baked_10cm", new Vector3(2.2f, 0, -7.35f)), ("ground_bare_10cm", new Vector3(1.5f, 0, -7.35f)),
                ("ground_bare_60cm", new Vector3(1.5f, 0, -7.85f)), ("wall_4cm_up", new Vector3(1.8f, 0.04f, -7.25f)), ("wall_60cm_up", new Vector3(1.8f, 0.6f, -7.25f)) };
            foreach (var (id, on, after, direct) in new[] { ("off", false, false, .25f), ("afterOpaque", true, true, .25f), ("inShader_D0", true, false, 0f), ("inShader_D025", true, false, .25f), ("inShader_D1", true, false, 1f) })
            {
                Ssao(on, after, 1.6f, .4f, direct, 300f); Shoot("E3b_" + id);
                json.Append($" \"{id}\":{{" + string.Join(",", litProbes.Select(p => $"\"{p.Item1}\":{J(Med(p.Item2, 1))}")) + "},\n");
            }
            json.Append(" \"note\":\"SSAO I1.6 R0.4 Falloff300\"}\n}\n");
            File.WriteAllText(Path.Combine(OutDir, "results.json"), json.ToString());
            cam.targetTexture = null;
        }
        catch (Exception e) { log.AppendLine("EXCEPTION " + e); }
        finally
        {
            if (swapped) QualitySettings.renderPipeline = prevQ;
            if (overrideOn) Unsupported.RestoreOverrideLightingSettings();
            if (scene.IsValid()) EditorSceneManager.ClosePreviewScene(scene);
            foreach (var o in trash) if (o != null) Object.DestroyImmediate(o);
            ShaderUtil.allowAsyncCompilation = asyncWas;
        }
        var act = SceneManager.GetActiveScene();
        log.AppendLine($"after: rp={GraphicsSettings.currentRenderPipeline.name} scene={act.name} dirty={act.isDirty}");
        return log.ToString();
    }
}
