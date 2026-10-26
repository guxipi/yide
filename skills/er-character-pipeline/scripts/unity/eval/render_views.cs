// ucli.sh eval render_views.cs PREFAB=Assets/.../<Name>.prefab OUT=C:/abs/out/dir LIGHTSET=Assets/Prefabs/Environment/LightSet.prefab UNLIT=0|1
// UNLIT=1 swaps the INSTANCE's materials to URP/Unlit with the same _BaseMap/_BaseMap_ST (diagnosis: if Unlit matches
// the Tripo look, geometry+texture are fine and any 'broken' look is the ToonLit parameters).
// Edit-mode, controlled-angle renders with the real game light: temp instance far from the scene at (300,0,300),
// temp camera -> RenderTexture -> PNG written straight to OUT (absolute path, outside Assets), everything
// destroyed afterwards, scene not saved. Use this instead of capture_scene_view (blank when the scene view does
// not refresh, and it writes into Assets/Temp).
// Views: front, back34, side, top70 (game-like elevation), face close-up. Height-normalised to the prefab bounds.
var p = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{PREFAB}}");
if (p == null) return "prefab not found";
var inst = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(p); inst.name = "__QA_Char";
inst.transform.position = new UnityEngine.Vector3(300, 0, 300); inst.transform.rotation = UnityEngine.Quaternion.identity;
UnityEngine.GameObject ls = null; var lsp = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{LIGHTSET}}");
if (lsp != null) { ls = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(lsp); ls.name = "__QA_Light"; }
var rs = inst.GetComponentsInChildren<UnityEngine.Renderer>(true);
if ("{{UNLIT}}" == "1") { var ush = UnityEngine.Shader.Find("Universal Render Pipeline/Unlit");
  foreach (var r in rs) { var ms = r.sharedMaterials; var nm = new UnityEngine.Material[ms.Length];
    for (int i = 0; i < ms.Length; i++) { nm[i] = new UnityEngine.Material(ush); if (ms[i] != null && ms[i].HasProperty("_BaseMap")) { nm[i].SetTexture("_BaseMap", ms[i].GetTexture("_BaseMap")); nm[i].SetTextureScale("_BaseMap", ms[i].GetTextureScale("_BaseMap")); nm[i].SetTextureOffset("_BaseMap", ms[i].GetTextureOffset("_BaseMap")); } }
    r.sharedMaterials = nm; } }
var b = rs[0].bounds; foreach (var r in rs) b.Encapsulate(r.bounds);
float H = b.size.y; var c = b.center;
var go = new UnityEngine.GameObject("__QA_Cam"); var cam = go.AddComponent<UnityEngine.Camera>(); cam.fieldOfView = 30;
cam.clearFlags = UnityEngine.CameraClearFlags.SolidColor; cam.backgroundColor = new UnityEngine.Color(0.35f, 0.37f, 0.4f);
var rt = new UnityEngine.RenderTexture(1024, 1024, 24); cam.targetTexture = rt;
// model faces +Z in Unity after the -Z-forward FBX export; camera yaw 180 looks at its face
var views = new (string n, UnityEngine.Vector3 e, float d, float y)[] { ("front", new UnityEngine.Vector3(5, 180, 0), 3.2f * H, 0.5f), ("back34", new UnityEngine.Vector3(8, -35, 0), 3.2f * H, 0.5f), ("side", new UnityEngine.Vector3(5, 90, 0), 3.2f * H, 0.5f), ("top70", new UnityEngine.Vector3(70, 180, 0), 7f * H, 0.45f), ("face", new UnityEngine.Vector3(3, 180, 0), 1.0f * H, 0.88f) };
var outs = "";
foreach (var v in views) {
  var rot = UnityEngine.Quaternion.Euler(v.e); var tgt = new UnityEngine.Vector3(c.x, b.min.y + v.y * H, c.z);
  go.transform.rotation = rot; go.transform.position = tgt - rot * UnityEngine.Vector3.forward * v.d; cam.Render();
  UnityEngine.RenderTexture.active = rt; var tex = new UnityEngine.Texture2D(1024, 1024, UnityEngine.TextureFormat.RGB24, false);
  tex.ReadPixels(new UnityEngine.Rect(0, 0, 1024, 1024), 0, 0); tex.Apply();
  System.IO.File.WriteAllBytes("{{OUT}}/" + v.n + ".png", tex.EncodeToPNG()); UnityEngine.Object.DestroyImmediate(tex); outs += v.n + " ";
}
UnityEngine.RenderTexture.active = null; cam.targetTexture = null; UnityEngine.Object.DestroyImmediate(rt); UnityEngine.Object.DestroyImmediate(go);
UnityEngine.Object.DestroyImmediate(inst); if (ls != null) UnityEngine.Object.DestroyImmediate(ls);
return "rendered " + outs + "H=" + H.ToString("F2") + " -> {{OUT}} (lightset=" + (lsp != null) + ")";
