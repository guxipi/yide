// Full-body front contact frames + knee metrics for each clip in {{CLIPS}} ("path#name;path#name"), rendered to {{OUT}}.
// Knee metric per leg: signed outward offset of the knee from the hip->ankle line, in units of body height (+ = knee outward).
// Also kneeGap/hipGap (knee separation / hip separation).
var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{PREFAB}}");
var go = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pf); go.transform.position = new UnityEngine.Vector3(600, 0, 600); go.transform.rotation = UnityEngine.Quaternion.identity;
var camGo = new UnityEngine.GameObject("c"); var cam = camGo.AddComponent<UnityEngine.Camera>(); var lg = new UnityEngine.GameObject("l"); var li = lg.AddComponent<UnityEngine.Light>(); li.type = UnityEngine.LightType.Directional; li.intensity = 1.1f;
var rt = new UnityEngine.RenderTexture(360, 540, 24); cam.targetTexture = rt; cam.clearFlags = UnityEngine.CameraClearFlags.SolidColor; cam.backgroundColor = new UnityEngine.Color(0.35f, 0.37f, 0.42f); cam.orthographic = true;
string log = "";
try {
  var an = go.GetComponentInChildren<UnityEngine.Animator>();
  if (!UnityEditor.AnimationMode.InAnimationMode()) UnityEditor.AnimationMode.StartAnimationMode();
  System.Action<UnityEngine.AnimationClip,float> SAMPLE = (cl, tt) => { UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(an.gameObject, cl, tt); UnityEditor.AnimationMode.EndSampling(); };
  float s = an.transform.lossyScale.x;
  foreach (var spec in "{{CLIPS}}".Split(new[] { ';' }, System.StringSplitOptions.RemoveEmptyEntries)) {
    var parts = spec.Split('#'); UnityEngine.AnimationClip clip = null;
    foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(parts[0])) { var c = o as UnityEngine.AnimationClip; if (c != null && !c.name.StartsWith("__preview") && (parts.Length < 2 || c.name == parts[1])) { clip = c; break; } }
    if (clip == null) { log += "MISSING " + spec + "\n"; continue; }
    float worstL = 9, worstR = 9, worstGap = 9;
    int N = {{N}};
    for (int k = 0; k < N; k++) {
      float t = clip.length * k / (N - 1);
      if (k == 0) { SAMPLE(clip, t); foreach (var smr in go.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true; cam.Render(); } SAMPLE(clip, t); cam.Render(); foreach (var smr in go.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;
      System.Func<UnityEngine.HumanBodyBones, UnityEngine.Vector3> B = (b) => an.transform.InverseTransformPoint(an.GetBoneTransform(b).position) / 1f;
      var lh = B(UnityEngine.HumanBodyBones.LeftUpperLeg); var lk = B(UnityEngine.HumanBodyBones.LeftLowerLeg); var la = B(UnityEngine.HumanBodyBones.LeftFoot);
      var rh = B(UnityEngine.HumanBodyBones.RightUpperLeg); var rk = B(UnityEngine.HumanBodyBones.RightLowerLeg); var ra = B(UnityEngine.HumanBodyBones.RightFoot);
      float H = 1f / 1f; // model-local units, model ~1 tall
      var lat = lh - rh; lat.y = 0; lat.Normalize();   // body's own left direction
      System.Func<UnityEngine.Vector3, float> X = (v) => UnityEngine.Vector3.Dot(v, lat);
      System.Func<UnityEngine.Vector3, UnityEngine.Vector3, UnityEngine.Vector3, float, float> outward = (hip, knee, ank, sd) => {
        float u = UnityEngine.Mathf.Clamp01((knee.y - hip.y) / (ank.y - hip.y + 1e-5f)); float lineX = X(hip) + (X(ank) - X(hip)) * u; return (X(knee) - lineX) * sd; };
      float oL = outward(lh, lk, la, 1f), oR = outward(rh, rk, ra, -1f);
      float gap = (X(lk) - X(rk)) / (X(lh) - X(rh) + 1e-5f);
      worstL = UnityEngine.Mathf.Min(worstL, oL); worstR = UnityEngine.Mathf.Min(worstR, oR); worstGap = UnityEngine.Mathf.Min(worstGap, gap);
      if ("{{OUT}}" != "NONE") {
        var hips = an.GetBoneTransform(UnityEngine.HumanBodyBones.Hips).position;
        var ctr = new UnityEngine.Vector3(hips.x, go.transform.position.y + 0.5f * s * 1.0f, hips.z);
        cam.orthographicSize = 0.62f * s; cam.transform.position = ctr + ("{{VIEW}}" == "side" ? an.transform.right : an.transform.forward) * 4f * s; cam.transform.LookAt(ctr);
        lg.transform.rotation = UnityEngine.Quaternion.LookRotation(-("{{VIEW}}" == "side" ? an.transform.right : an.transform.forward) + UnityEngine.Vector3.down * 0.7f);
        cam.Render(); UnityEngine.RenderTexture.active = rt; var tx = new UnityEngine.Texture2D(360, 540, UnityEngine.TextureFormat.RGB24, false); tx.ReadPixels(new UnityEngine.Rect(0, 0, 360, 540), 0, 0); tx.Apply();
        System.IO.File.WriteAllBytes("{{OUT}}/" + clip.name + "_" + k + ".png", tx.EncodeToPNG()); UnityEngine.Object.DestroyImmediate(tx);
      }
    }
    log += clip.name + " len=" + clip.length.ToString("F2") + " minKneeOut L=" + worstL.ToString("F3") + " R=" + worstR.ToString("F3") + " minKneeGap/hipGap=" + worstGap.ToString("F2") + "\n";
  }
} finally { if (UnityEditor.AnimationMode.InAnimationMode()) UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.RenderTexture.active = null; UnityEngine.Object.DestroyImmediate(go); UnityEngine.Object.DestroyImmediate(camGo); UnityEngine.Object.DestroyImmediate(lg); rt.Release(); }
return log;
