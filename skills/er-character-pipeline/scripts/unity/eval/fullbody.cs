// Full-body renders: PREFAB, CLIP=path#name|NONE, T=time, OUT, TAG. Views front/side/back/34 at 900x1500, light from camera.
var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{PREFAB}}");
var go = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pf); go.transform.position = new UnityEngine.Vector3(500, 0, 500); go.transform.rotation = UnityEngine.Quaternion.identity;
UnityEngine.AnimationClip clip = null; var spec = "{{CLIP}}";
if (spec != "NONE") { var parts = spec.Split('#'); foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(parts[0])) { var c = o as UnityEngine.AnimationClip; if (c != null && !c.name.StartsWith("__preview") && (parts.Length < 2 || c.name == parts[1])) { clip = c; break; } } }
var camGo = new UnityEngine.GameObject("c"); var cam = camGo.AddComponent<UnityEngine.Camera>(); var lg = new UnityEngine.GameObject("l"); var li = lg.AddComponent<UnityEngine.Light>(); li.type = UnityEngine.LightType.Directional; li.intensity = 1.1f;
int W = 900, H = 1500; var rt = new UnityEngine.RenderTexture(W, H, 24); cam.targetTexture = rt; cam.clearFlags = UnityEngine.CameraClearFlags.SolidColor; cam.backgroundColor = new UnityEngine.Color(0.35f, 0.37f, 0.42f); cam.orthographic = true; string log = "";
try {
  var an = go.GetComponentInChildren<UnityEngine.Animator>();
  UnityEditor.AnimationMode.StartAnimationMode();
  if (clip != null) for (int r = 0; r < 2; r++) { UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(an.gameObject, clip, {{T}}f); UnityEditor.AnimationMode.EndSampling(); }
  foreach (var smr in go.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;
  float s = an.transform.lossyScale.x; var hips = an.GetBoneTransform(UnityEngine.HumanBodyBones.Hips).position; var ctr = new UnityEngine.Vector3(hips.x, go.transform.position.y + 0.52f * s, hips.z);
  foreach (var v in new[] { "front", "side", "back", "34" }) {
    var d = v == "front" ? an.transform.forward : v == "back" ? -an.transform.forward : v == "side" ? an.transform.right : (an.transform.forward + an.transform.right).normalized;
    cam.orthographicSize = 0.58f * s; cam.transform.position = ctr + d * 4f * s; cam.transform.LookAt(ctr); lg.transform.rotation = UnityEngine.Quaternion.LookRotation(-d + UnityEngine.Vector3.down * 0.6f);
    cam.Render(); UnityEngine.RenderTexture.active = rt; var tx = new UnityEngine.Texture2D(W, H, UnityEngine.TextureFormat.RGB24, false); tx.ReadPixels(new UnityEngine.Rect(0, 0, W, H), 0, 0); tx.Apply();
    System.IO.File.WriteAllBytes("{{OUT}}/{{TAG}}_" + v + ".png", tx.EncodeToPNG()); UnityEngine.Object.DestroyImmediate(tx); log += v + " ";
  }
} finally { if (UnityEditor.AnimationMode.InAnimationMode()) UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.RenderTexture.active = null; UnityEngine.Object.DestroyImmediate(go); UnityEngine.Object.DestroyImmediate(camGo); UnityEngine.Object.DestroyImmediate(lg); rt.Release(); }
return "FULLBODY " + log;
