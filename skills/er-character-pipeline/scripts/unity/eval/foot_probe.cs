// foot pitch (deg, + = toes below ankle) for: bind pose of {{MODEL}} and {{ANIM}} instances, their skeleton T-poses, and {{CLIP}} sampled on the model prefab at times.
string log = ""; System.Func<UnityEngine.Vector3, string> P = (d) => (UnityEngine.Mathf.Atan2(-d.y, new UnityEngine.Vector2(d.x, d.z).magnitude) * UnityEngine.Mathf.Rad2Deg).ToString("F1");
foreach (var path in new[] { "{{MODEL}}", "{{ANIM}}" }) {
  var asset = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(path); var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(path); var hd = imp.humanDescription;
  var inst = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(asset, new UnityEngine.Vector3(800, 0, 800), UnityEngine.Quaternion.identity);
  try { var an = inst.GetComponentInChildren<UnityEngine.Animator>(); System.Func<UnityEngine.HumanBodyBones, UnityEngine.Transform> T = (b) => an.GetBoneTransform(b);
    var ft = T(UnityEngine.HumanBodyBones.LeftFoot); var to = T(UnityEngine.HumanBodyBones.LeftToes); var lo = T(UnityEngine.HumanBodyBones.LeftLowerLeg);
    log += path + " BIND foot->toes pitch=" + P(to.position - ft.position) + " shin->foot pitch=" + P(ft.position - lo.position) + " footUp=" + inst.transform.InverseTransformDirection(ft.up).ToString("F2") + "\n";
    var map = new System.Collections.Generic.Dictionary<string, UnityEngine.Transform>(); foreach (var t in inst.GetComponentsInChildren<UnityEngine.Transform>(true)) map[t.name] = t;
    foreach (var sb in hd.skeleton) { UnityEngine.Transform t; if (map.TryGetValue(sb.name, out t)) { if (t == inst.transform) { t.rotation = sb.rotation; } else { t.localPosition = sb.position; t.localRotation = sb.rotation; t.localScale = sb.scale; } } }
    log += path + " TPOSE foot->toes pitch=" + P(to.position - ft.position) + " shin->foot pitch=" + P(ft.position - lo.position) + "\n";
  } finally { UnityEngine.Object.DestroyImmediate(inst); } }
var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Art/3DModelsfromGu/0_Characters/Rook2/Rook2.prefab"); var go = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pf); go.transform.position = new UnityEngine.Vector3(900, 0, 900);
try { var an = go.GetComponentInChildren<UnityEngine.Animator>(); UnityEngine.AnimationClip clip = null; var parts = "{{CLIP}}".Split('#'); foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(parts[0])) { var c = o as UnityEngine.AnimationClip; if (c != null && !c.name.StartsWith("__preview") && (parts.Length < 2 || c.name == parts[1])) { clip = c; break; } }
  UnityEditor.AnimationMode.StartAnimationMode();
  foreach (var ts in new[] { 0.5f, 1.5f, 3f }) { for (int r = 0; r < 2; r++) { UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(an.gameObject, clip, ts); UnityEditor.AnimationMode.EndSampling(); }
    var ft = an.GetBoneTransform(UnityEngine.HumanBodyBones.LeftFoot); var to = an.GetBoneTransform(UnityEngine.HumanBodyBones.LeftToes); var lo = an.GetBoneTransform(UnityEngine.HumanBodyBones.LeftLowerLeg);
    log += "CLIP t=" + ts + " foot->toes pitch=" + P(to.position - ft.position) + " shin->foot pitch=" + P(ft.position - lo.position) + " footY=" + ft.position.y.ToString("F3") + " toesY=" + to.position.y.ToString("F3") + "\n"; }
} finally { UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.Object.DestroyImmediate(go); }
return log;
