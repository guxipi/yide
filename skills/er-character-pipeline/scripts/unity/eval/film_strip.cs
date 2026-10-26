// Edit-mode film strip: ucli.sh eval film_strip.cs PREFAB=<Name>.prefab OUT=C:/abs/dir CLIPS="Assets/..a.fbx;Assets/..multi.fbx#clipName"
// 4 frames per clip x (front, back34, hip/armpit zoom) sampled with UnityEditor.AnimationMode; check crotch/armpit for white seams.
var p = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{PREFAB}}");
var inst = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(p); inst.name = "__QA_Film";
inst.transform.position = new UnityEngine.Vector3(300, 0, 300); inst.transform.rotation = UnityEngine.Quaternion.identity;
var lsp = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Prefabs/Environment/LightSet.prefab");
UnityEngine.GameObject ls = lsp != null ? (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(lsp) : null;
var go = new UnityEngine.GameObject("__QA_Cam"); var cam = go.AddComponent<UnityEngine.Camera>(); cam.fieldOfView = 30;
cam.clearFlags = UnityEngine.CameraClearFlags.SolidColor; cam.backgroundColor = new UnityEngine.Color(0.35f, 0.37f, 0.4f);
var rt = new UnityEngine.RenderTexture(768, 768, 24); cam.targetTexture = rt; var outs = "";
try {
 foreach (var cp in "{{CLIPS}}".Split(';')) {
  UnityEngine.AnimationClip clip = null;
  // "path.fbx#clipName" picks one clip out of a multi-clip FBX (10-08: Wren_Anims.fbx holds all Tripo presets)
  var fp = cp.Split('#')[0]; var want = cp.Contains("#") ? cp.Split('#')[1] : null;
  foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(fp)) if (o is UnityEngine.AnimationClip && !o.name.StartsWith("__preview") && (want == null || o.name == want || o.name.EndsWith("|" + want))) { clip = (UnityEngine.AnimationClip)o; break; }
  if (clip == null) { outs += "noclip " + cp + "; "; continue; }
  var tag = (want != null ? want : System.IO.Path.GetFileNameWithoutExtension(fp)).Replace(" ", "_");
  for (int k = 0; k < 4; k++) {
   float t = clip.length * (0.1f + 0.8f * k / 3f);
   // 10-08: AnimationClip.SampleAnimation / a hand-made PlayableGraph left stale poses in edit mode (every frame and clip came
   // out as the first sample, or as bind pose). AnimationMode is what the Animation window uses: reliable for Humanoid clips.
   if (!UnityEditor.AnimationMode.InAnimationMode()) {
     UnityEditor.AnimationMode.StartAnimationMode();
     // warm-up: the first sample after StartAnimationMode renders as bind pose (Wren 10-08), so throw one away
     UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(inst.GetComponentInChildren<UnityEngine.Animator>(true).gameObject, clip, t); UnityEditor.AnimationMode.EndSampling();
     foreach (var smr in inst.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;
     cam.Render();
   }
   UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(inst.GetComponentInChildren<UnityEngine.Animator>(true).gameObject, clip, t); UnityEditor.AnimationMode.EndSampling();
   // the sampled pose only reaches the camera if the skin is recomputed now (edit mode skins on the next editor tick)
   foreach (var smr in inst.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>(true)) smr.forceMatrixRecalculationPerRender = true;
   var rs = inst.GetComponentsInChildren<UnityEngine.Renderer>(true); var b = rs[0].bounds; foreach (var r in rs) b.Encapsulate(r.bounds);
   float H = b.size.y; var c = b.center;
   foreach (var v in new (string n, UnityEngine.Vector3 e, float d)[] { ("f", new UnityEngine.Vector3(5, 180, 0), 2.3f), ("b", new UnityEngine.Vector3(8, -35, 0), 2.3f), ("z", new UnityEngine.Vector3(10, 150, 0), 1.05f) }) {
     var rot = UnityEngine.Quaternion.Euler(v.e); go.transform.rotation = rot; go.transform.position = c - rot * UnityEngine.Vector3.forward * (v.d * H); cam.Render();
     UnityEngine.RenderTexture.active = rt; var tex = new UnityEngine.Texture2D(768, 768, UnityEngine.TextureFormat.RGB24, false);
     tex.ReadPixels(new UnityEngine.Rect(0, 0, 768, 768), 0, 0); tex.Apply();
     System.IO.File.WriteAllBytes("{{OUT}}/" + tag + "_" + k + "_" + v.n + ".png", tex.EncodeToPNG()); UnityEngine.Object.DestroyImmediate(tex);
   }
  }
  outs += tag + "(" + clip.name + " " + clip.length.ToString("F2") + "s humanMotion=" + clip.humanMotion + ") ";
 }
} finally {
 if (UnityEditor.AnimationMode.InAnimationMode()) UnityEditor.AnimationMode.StopAnimationMode();
 UnityEngine.RenderTexture.active = null; cam.targetTexture = null; UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(go);
 UnityEngine.Object.DestroyImmediate(inst); if (ls != null) UnityEngine.Object.DestroyImmediate(ls);
}
return "FILM " + outs;
