// er-lookdev:把遮蔽的三层(贴缝、形体、按高度的渐变)放进 Unity 实时光下拍,量侧壁从上到下的剖面。
// 先跑 ao_lab3_export.py 得到 van.json / ao_contact.png / ao_form.png,把那个目录写进环境变量 LOOKDEV_L3_DIR 或改下面的 Dir。
// unity command --timeout 240 script run --file unity_layer3_lab.cs --entry Layer3Lab.Run
// 预览场景 + 管线资产内存副本 + ShaderUtil.CreateShaderAsset 内存编译的 shader;不动打开的场景,不写 Assets。
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

public static class Layer3Lab
{
    const int W = 1080, H = 1080;
    static string Dir => Environment.GetEnvironmentVariable("LOOKDEV_L3_DIR") ?? Path.Combine(Path.GetTempPath(), "LookdevLab", "l3u");
    const BindingFlags BF = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;
    static readonly System.Globalization.CultureInfo Inv = System.Globalization.CultureInfo.InvariantCulture;
    [Serializable] class VanData { public float[] pos; public float[] nrm; public float[] uv; public int[] tri; }

    static void SetF(object o, string f, object v)
    {
        var t = o.GetType(); FieldInfo fi = null;
        while (t != null && fi == null) { fi = t.GetField(f, BF); t = t.BaseType; }
        if (fi == null) throw new Exception("no field " + f);
        if (fi.FieldType.IsEnum) v = Enum.ToObject(fi.FieldType, Convert.ToInt32(v));
        fi.SetValue(o, v);
    }

    const string ShaderSrc = @"
Shader ""Hidden/LookdevLab/Layer3""
{
    Properties
    {
        _BaseColor(""Base"", Color) = (0.85,0.85,0.85,1)
        _AOContact(""Contact AO"", 2D) = ""white"" {}
        _AOForm(""Form AO"", 2D) = ""white"" {}
        _AOTint(""AO tint (linear)"", Vector) = (0.42,0.45,0.66,0)
        _FormMix(""Form mix"", Float) = 0.5
        _UseAO(""Use baked AO"", Float) = 1
        _UseHeight(""Use height gradient"", Float) = 1
        _KDirect(""AO on direct"", Float) = 1
        _HBottom(""Height bottom"", Float) = 0.4
        _HTop(""Height top"", Float) = 2.3
        _HFrac(""Gradient covers lower fraction"", Float) = 0.6
        _HPow(""Gradient power"", Float) = 1.5
        _GMin(""Gradient min"", Float) = 0.12
        _BandMid(""Band mid"", Float) = 0.5
        _BandSoft(""Band soft"", Float) = 0.25
    }
    SubShader
    {
        Tags { ""RenderType""=""Opaque"" ""RenderPipeline""=""UniversalPipeline"" ""Queue""=""Geometry"" }
        HLSLINCLUDE
        #include ""Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl""
        #include ""Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl""
        CBUFFER_START(UnityPerMaterial)
            half4 _BaseColor; float4 _AOTint;
            float _FormMix, _UseAO, _UseHeight, _KDirect, _HBottom, _HTop, _HFrac, _HPow, _GMin, _BandMid, _BandSoft;
        CBUFFER_END
        TEXTURE2D(_AOContact); SAMPLER(sampler_AOContact);
        TEXTURE2D(_AOForm); SAMPLER(sampler_AOForm);
        ENDHLSL
        Pass
        {
            Name ""ForwardLit"" Tags { ""LightMode""=""UniversalForward"" }
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE
            #pragma multi_compile_fragment _ _SHADOWS_SOFT _SHADOWS_SOFT_LOW _SHADOWS_SOFT_MEDIUM _SHADOWS_SOFT_HIGH
            struct A { float4 positionOS : POSITION; float3 normalOS : NORMAL; float2 uv : TEXCOORD0; };
            struct V { float4 positionCS : SV_POSITION; float3 positionWS : TEXCOORD0; float3 normalWS : TEXCOORD1; float2 uv : TEXCOORD2; float hObj : TEXCOORD3; };
            V vert(A i)
            {
                V o; o.positionWS = TransformObjectToWorld(i.positionOS.xyz); o.positionCS = TransformWorldToHClip(o.positionWS);
                o.normalWS = TransformObjectToWorldNormal(i.normalOS); o.uv = i.uv; o.hObj = i.positionOS.y; return o;
            }
            half4 frag(V i) : SV_Target
            {
                float3 n = normalize(i.normalWS);
                Light key = GetMainLight(TransformWorldToShadowCoord(i.positionWS));
                half hl = dot(n, key.direction) * 0.5 + 0.5;
                half t = smoothstep(_BandMid - _BandSoft, _BandMid + _BandSoft, hl) * key.shadowAttenuation;
                half3 ambient = SampleSH(n);
                // 三层遮蔽合成一个 0..1 的量
                half contact = SAMPLE_TEXTURE2D(_AOContact, sampler_AOContact, i.uv).r;
                half form = SAMPLE_TEXTURE2D(_AOForm, sampler_AOForm, i.uv).r;
                half occl = lerp(1.0, contact * lerp(1.0, form, _FormMix), _UseAO);
                half h = saturate((i.hObj - _HBottom) / max(_HTop - _HBottom, 1e-4));
                half g = lerp(_GMin, 1.0, pow(saturate(h / _HFrac), _HPow));
                occl *= lerp(1.0, g, _UseHeight);
                // 往带色相的颜色插值,不乘灰
                half3 o3 = lerp(_AOTint.rgb, half3(1, 1, 1), occl);
                half3 col = _BaseColor.rgb * (key.color * t * lerp(half3(1, 1, 1), o3, _KDirect) + ambient * o3);
                return half4(col, 1);
            }
            ENDHLSL
        }
        Pass
        {
            Name ""ShadowCaster"" Tags { ""LightMode""=""ShadowCaster"" }
            ZWrite On ZTest LEqual ColorMask 0
            HLSLPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include ""Packages/com.unity.render-pipelines.universal/ShaderLibrary/Shadows.hlsl""
            float3 _LightDirection;
            struct A { float4 positionOS : POSITION; float3 normalOS : NORMAL; };
            float4 vert(A i) : SV_POSITION
            {
                float3 pw = TransformObjectToWorld(i.positionOS.xyz); float3 nw = TransformObjectToWorldNormal(i.normalOS);
                return ApplyShadowClamping(TransformWorldToHClip(ApplyShadowBias(pw, nw, _LightDirection)));
            }
            half4 frag() : SV_Target { return 0; }
            ENDHLSL
        }
    }
}";

    public static string Run()
    {
        if (EditorApplication.isPlayingOrWillChangePlaymode) return "REFUSED: play mode";
        if (EditorApplication.isCompiling) return "REFUSED: compiling";
        string dir = Dir; string outDir = Path.Combine(dir, "out"); Directory.CreateDirectory(outDir);
        var log = new StringBuilder(); var json = new StringBuilder("{\n");
        var srcAsset = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/Mobile_RPAsset.asset");
        var srcRenderer = AssetDatabase.LoadAssetAtPath<UniversalRendererData>("Assets/Settings/Mobile_Renderer.asset");
        var prevQ = QualitySettings.renderPipeline;
        bool asyncWas = ShaderUtil.allowAsyncCompilation; ShaderUtil.allowAsyncCompilation = false;
        var trash = new List<Object>(); Scene scene = default; bool overrideOn = false, swapped = false;
        try
        {
            var asset = Object.Instantiate(srcAsset); asset.hideFlags = HideFlags.HideAndDontSave; trash.Add(asset);
            var rdata = Object.Instantiate(srcRenderer); rdata.hideFlags = HideFlags.HideAndDontSave; trash.Add(rdata);
            SetF(rdata, "m_RendererFeatures", new List<ScriptableRendererFeature>());
            SetF(asset, "m_RendererDataList", new ScriptableRendererData[] { rdata }); SetF(asset, "m_DefaultRendererIndex", 0);
            SetF(asset, "m_ShadowDistance", 60f); SetF(asset, "m_MainLightShadowmapResolution", 2048); SetF(asset, "m_ShadowCascadeCount", 1);
            SetF(asset, "m_SoftShadowsSupported", true); SetF(asset, "m_SoftShadowQuality", 2); SetF(asset, "m_RenderScale", 1f);
            QualitySettings.renderPipeline = asset; swapped = true;

            scene = EditorSceneManager.NewPreviewScene();
            Unsupported.SetOverrideLightingSettings(scene); overrideOn = true;
            RenderSettings.fog = false; RenderSettings.skybox = null; RenderSettings.ambientMode = AmbientMode.Trilight; RenderSettings.ambientIntensity = 1f;
            RenderSettings.ambientSkyColor = new Color(.60f, .68f, .95f); RenderSettings.ambientEquatorColor = new Color(.52f, .56f, .78f); RenderSettings.ambientGroundColor = new Color(.42f, .44f, .62f);
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom; RenderSettings.reflectionIntensity = 0f;

            var shader = ShaderUtil.CreateShaderAsset(ShaderSrc, true); shader.hideFlags = HideFlags.HideAndDontSave; trash.Add(shader);
            int msgs = ShaderUtil.GetShaderMessageCount(shader);
            if (msgs > 0) foreach (var m in ShaderUtil.GetShaderMessages(shader)) log.AppendLine("SHADER " + m.severity + " L" + m.line + ": " + m.message);
            if (!shader.isSupported) throw new Exception("shader not supported");

            Texture2D Load(string f) { var t = new Texture2D(2, 2, TextureFormat.RGBA32, true, true) { hideFlags = HideFlags.HideAndDontSave }; t.LoadImage(File.ReadAllBytes(Path.Combine(dir, f))); t.wrapMode = TextureWrapMode.Clamp; trash.Add(t); return t; }
            var texC = Load("ao_contact.png"); var texF = Load("ao_form.png");
            var vd = JsonUtility.FromJson<VanData>(File.ReadAllText(Path.Combine(dir, "van.json")));
            int nv = vd.pos.Length / 3; var vs = new Vector3[nv]; var ns = new Vector3[nv]; var us = new Vector2[nv];
            for (int i = 0; i < nv; i++) { vs[i] = new Vector3(vd.pos[i * 3], vd.pos[i * 3 + 1], vd.pos[i * 3 + 2]); ns[i] = new Vector3(vd.nrm[i * 3], vd.nrm[i * 3 + 1], vd.nrm[i * 3 + 2]); us[i] = new Vector2(vd.uv[i * 2], vd.uv[i * 2 + 1]); }
            var mesh = new Mesh { hideFlags = HideFlags.HideAndDontSave }; trash.Add(mesh);
            mesh.vertices = vs; mesh.normals = ns; mesh.uv = us; mesh.triangles = vd.tri; mesh.RecalculateBounds();

            var mat = new Material(shader) { hideFlags = HideFlags.HideAndDontSave }; trash.Add(mat);
            mat.SetTexture("_AOContact", texC); mat.SetTexture("_AOForm", texF);
            var vanGo = new GameObject("van"); SceneManager.MoveGameObjectToScene(vanGo, scene);
            vanGo.AddComponent<MeshFilter>().sharedMesh = mesh; var mr = vanGo.AddComponent<MeshRenderer>(); mr.sharedMaterial = mat;

            var lit = Shader.Find("Universal Render Pipeline/Lit");
            var gm = new Material(lit) { hideFlags = HideFlags.HideAndDontSave }; trash.Add(gm);
            gm.SetColor("_BaseColor", new Color(.55f, .62f, .80f)); gm.SetFloat("_Smoothness", 0); gm.SetFloat("_SpecularHighlights", 0); gm.EnableKeyword("_SPECULARHIGHLIGHTS_OFF"); gm.SetFloat("_EnvironmentReflections", 0); gm.EnableKeyword("_ENVIRONMENTREFLECTIONS_OFF");
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane); Object.DestroyImmediate(ground.GetComponent<Collider>()); SceneManager.MoveGameObjectToScene(ground, scene);
            ground.transform.localScale = new Vector3(8, 1, 8); ground.GetComponent<MeshRenderer>().sharedMaterial = gm;

            var sunGo = new GameObject("sun"); SceneManager.MoveGameObjectToScene(sunGo, scene);
            var sun = sunGo.AddComponent<Light>(); sun.type = LightType.Directional; sun.color = new Color(1f, .96f, .88f); sun.intensity = 1.0f;
            sun.shadows = LightShadows.Soft; sun.shadowBias = 0.05f; sun.shadowNormalBias = 0.4f; sunGo.AddComponent<UniversalAdditionalLightData>();
            // 朝光方向 (0.35, 0.85, 0.4):车顶正受光,+x 侧壁掠射受光,车头(-z)背光
            sunGo.transform.rotation = Quaternion.LookRotation(-new Vector3(0.35f, 0.85f, 0.4f).normalized);

            var camGo = new GameObject("cam"); SceneManager.MoveGameObjectToScene(camGo, scene);
            var cam = camGo.AddComponent<Camera>(); cam.scene = scene; cam.cameraType = CameraType.Game; cam.fieldOfView = 25f; cam.nearClipPlane = 0.5f; cam.farClipPlane = 300f; cam.aspect = 1f;
            cam.clearFlags = CameraClearFlags.SolidColor; cam.backgroundColor = new Color(.3f, .35f, .5f); cam.allowHDR = true; cam.allowMSAA = true;
            var cd = camGo.AddComponent<UniversalAdditionalCameraData>(); cd.renderPostProcessing = false; cd.renderShadows = true; cd.SetRenderer(0);
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4, hideFlags = HideFlags.HideAndDontSave }; trash.Add(rt);
            cam.targetTexture = rt; var tex = new Texture2D(W, H, TextureFormat.RGBA32, false, false) { hideFlags = HideFlags.HideAndDontSave }; trash.Add(tex);
            Color32[] px = null;
            void Cam(float dist) { var rot = Quaternion.Euler(50, -40, 0); camGo.transform.SetPositionAndRotation(new Vector3(0, 1.2f, 0.2f) - rot * Vector3.forward * dist, rot); }
            void Shoot(string id) { cam.Render(); cam.Render(); var prev = RenderTexture.active; RenderTexture.active = rt; tex.ReadPixels(new Rect(0, 0, W, H), 0, 0); tex.Apply(); RenderTexture.active = prev; File.WriteAllBytes(Path.Combine(outDir, id + ".png"), tex.EncodeToPNG()); px = tex.GetPixels32(); }
            float[] Med(Vector3 world, int r = 2)
            {
                var v = cam.WorldToViewportPoint(world); int cx = Mathf.RoundToInt(v.x * W), cy = Mathf.RoundToInt(v.y * H); var rs = new List<int>(); var gs = new List<int>(); var bs = new List<int>();
                for (int y = cy - r; y <= cy + r; y++) for (int x = cx - r; x <= cx + r; x++) { if (x < 0 || y < 0 || x >= W || y >= H) continue; var c = px[y * W + x]; rs.Add(c.r); gs.Add(c.g); bs.Add(c.b); }
                rs.Sort(); gs.Sort(); bs.Sort(); return new float[] { rs[rs.Count / 2], gs[gs.Count / 2], bs[bs.Count / 2] };
            }
            string F(float v) => v.ToString("0.###", Inv);
            float[] REF = { 1.0f, 0.967f, 0.945f, 0.956f, 0.941f, 0.855f, 0.833f, 0.788f, 0.754f, 0.708f };
            // +x 侧壁(x = 1.0,z = 0.1,避开轮子)从上到下 10 个点;顶板上表面 5 个点
            string Measure()
            {
                var ls = new float[10]; var cols = new string[10];
                for (int i = 0; i < 10; i++) { float y = Mathf.Lerp(2.2f, 0.5f, i / 9f); var c = Med(new Vector3(1.0f, y, 0.1f)); ls[i] = (0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]) / 255f; cols[i] = $"\"#{(int)c[0]:X2}{(int)c[1]:X2}{(int)c[2]:X2}\""; }
                float rms = Mathf.Sqrt(Enumerable.Range(0, 10).Select(i => Mathf.Pow(ls[i] / ls[0] - REF[i], 2)).Average());
                var roof = new[] { new Vector3(0, 2.391f, 0.4f), new Vector3(-.4f, 2.391f, -.4f), new Vector3(.4f, 2.391f, 1.2f), new Vector3(.4f, 2.391f, -.4f), new Vector3(-.4f, 2.391f, 1.2f) }.Select(p => { var c = Med(p); return (0.2126f * c[0] + 0.7152f * c[1] + 0.0722f * c[2]) / 255f; }).ToArray();
                var front = Med(new Vector3(0.3f, 1.2f, -2.4f));   // 车头正面(背光)
                return $"{{\"wall_L_norm\":[{string.Join(",", ls.Select(v => F(v / ls[0])))}],\"wall_top_L\":{F(ls[0])},\"wall_hex\":[{string.Join(",", cols)}],\"rms_vs_ref\":{F(rms)},\"roof_L_min\":{F(roof.Min())},\"roof_L_max\":{F(roof.Max())},\"cab_front_shade\":\"#{(int)front[0]:X2}{(int)front[1]:X2}{(int)front[2]:X2}\"}}";
            }
            void Variant(float useAO, float useH, float kDirect, Vector4 tint) { mat.SetFloat("_UseAO", useAO); mat.SetFloat("_UseHeight", useH); mat.SetFloat("_KDirect", kDirect); mat.SetVector("_AOTint", tint); }
            var LILAC = new Vector4(.42f, .45f, .66f, 0); var GREY = new Vector4(0, 0, 0, 0);
            var variants = new (string, float, float, float, Vector4)[] {
                ("A_no_ao", 0, 0, 1, LILAC), ("B_two_layers", 1, 0, 1, LILAC), ("C_three_layers", 1, 1, 1, LILAC),
                ("D_three_ambient_only", 1, 1, 0, LILAC), ("E_three_kdirect05", 1, 1, 0.5f, LILAC), ("F_three_black_multiply", 1, 1, 1, GREY) };
            Cam(14f); Variant(0, 0, 1, LILAC); Shoot("_warmup"); Shoot("_warmup");
            json.Append("\"close\":{\n");
            for (int i = 0; i < variants.Length; i++) { var v = variants[i]; Variant(v.Item2, v.Item3, v.Item4, v.Item5); Shoot("close_" + v.Item1); json.Append($" \"{v.Item1}\":{Measure()}{(i < variants.Length - 1 ? "," : "")}\n"); }
            json.Append("},\n\"game40m\":{\n");
            Cam(40f);
            for (int i = 0; i < 3; i++) { var v = variants[i]; Variant(v.Item2, v.Item3, v.Item4, v.Item5); Shoot("game_" + v.Item1); json.Append($" \"{v.Item1}\":{Measure()}{(i < 2 ? "," : "")}\n"); }
            json.Append("}\n}\n");
            File.WriteAllText(Path.Combine(outDir, "results_l3.json"), json.ToString());
            cam.targetTexture = null; log.AppendLine("out " + outDir);
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
