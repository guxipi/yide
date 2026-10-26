// ucli.sh eval hero_swap.cs HERO=Assets/Prefabs/Heroes/Hero.prefab NEWPREFAB=Assets/.../<Name>.prefab RATIO=0.9
// LOCAL ACCEPTANCE SWAP - do not commit Hero.prefab unless the user decided this character replaces the hero.
// 1. backs up HERO to Assets/Temp/HeroOld.prefab (first run only; weapon_mount.cs needs it; delete it at the end)
// 2. measures the old model's visible height, instantiates NEWPREFAB in its place
// 3. puts scale AND the 180deg Y turn on the ANIMATOR node itself, wrapper parent stays identity:
//    CharacterPreviewController keeps only the Animator GameObject, so anything on a wrapper is lost in the Gear-tab
//    preview (Wren showed up tiny and back-to-camera); the 180deg is the player negative-forward convention
// 4. grounds the feet on the old feet plane, copies UnitAnimator onto the new Animator node and re-points every
//    serialized reference that pointed into the old model (matched by object name), then deletes the old model.
var heroPath = "{{HERO}}"; var newPath = "{{NEWPREFAB}}"; float ratio = {{RATIO}}f;
if (UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Temp/HeroOld.prefab") == null) {
  if (!UnityEditor.AssetDatabase.IsValidFolder("Assets/Temp")) UnityEditor.AssetDatabase.CreateFolder("Assets", "Temp");
  UnityEditor.AssetDatabase.CopyAsset(heroPath, "Assets/Temp/HeroOld.prefab");
}
var newP = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(newPath);
if (newP == null) return "new prefab not found";
var root = UnityEditor.PrefabUtility.LoadPrefabContents(heroPath);
var log = "";
try {
  var oldAnim = root.GetComponentInChildren<UnityEngine.Animator>(true);
  var oldModel = oldAnim.gameObject; var parent = oldModel.transform.parent;
  System.Func<UnityEngine.GameObject, UnityEngine.Bounds> B = (g) => {
    var rs = g.GetComponentsInChildren<UnityEngine.Renderer>(true); var b = rs[0].bounds;
    foreach (var r in rs) if (r is UnityEngine.SkinnedMeshRenderer || r is UnityEngine.MeshRenderer) b.Encapsulate(r.bounds); return b; };
  var ob = B(oldModel); float oldH = ob.size.y;
  var nm = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(newP, parent);
  nm.transform.localPosition = UnityEngine.Vector3.zero; nm.transform.localRotation = UnityEngine.Quaternion.Euler(0, 180, 0); nm.transform.localScale = UnityEngine.Vector3.one;
  var nb = B(nm); float s = oldH * ratio / nb.size.y;
  nm.transform.localScale = UnityEngine.Vector3.one * s;
  nb = B(nm); nm.transform.position += new UnityEngine.Vector3(0, ob.min.y - nb.min.y, 0);
  log += "oldH=" + oldH.ToString("F3") + " newScale=" + s.ToString("F4") + " newH=" + B(nm).size.y.ToString("F3") + "; ";
  var newAnim = nm.GetComponent<UnityEngine.Animator>();
  var oldUA = oldModel.GetComponent("UnitAnimator");
  if (oldUA != null) {
    UnityEditorInternal.ComponentUtility.CopyComponent(oldUA);
    UnityEditorInternal.ComponentUtility.PasteComponentAsNew(nm);
    var nua = nm.GetComponent("UnitAnimator");
    var so = new UnityEditor.SerializedObject(nua); var p = so.FindProperty("_animator");
    if (p != null) { p.objectReferenceValue = newAnim; so.ApplyModifiedPropertiesWithoutUndo(); }
    log += "UnitAnimator copied; ";
  }
  var oldSet = new System.Collections.Generic.HashSet<UnityEngine.Object>();
  foreach (var t in oldModel.GetComponentsInChildren<UnityEngine.Transform>(true)) { oldSet.Add(t); oldSet.Add(t.gameObject); foreach (var c in t.GetComponents<UnityEngine.Component>()) oldSet.Add(c); }
  var newByName = new System.Collections.Generic.Dictionary<string, UnityEngine.Transform>();
  foreach (var t in nm.GetComponentsInChildren<UnityEngine.Transform>(true)) if (!newByName.ContainsKey(t.name)) newByName[t.name] = t;
  int repointed = 0; var missed = "";
  foreach (var comp in root.GetComponentsInChildren<UnityEngine.Component>(true)) {
    if (comp == null || oldSet.Contains(comp)) continue;
    var so = new UnityEditor.SerializedObject(comp); var it = so.GetIterator(); bool changed = false;
    while (it.Next(true)) {
      if (it.propertyType != UnityEditor.SerializedPropertyType.ObjectReference || it.objectReferenceValue == null || !oldSet.Contains(it.objectReferenceValue)) continue;
      var ov = it.objectReferenceValue; UnityEngine.Object nv = null;
      if (ov is UnityEngine.Animator) nv = newAnim;
      else {
        var tname = ov is UnityEngine.GameObject ? ((UnityEngine.GameObject)ov).name : ((UnityEngine.Component)ov).gameObject.name;
        if (newByName.ContainsKey(tname)) {
          var nt = newByName[tname];
          nv = ov is UnityEngine.GameObject ? (UnityEngine.Object)nt.gameObject : ov is UnityEngine.Transform ? (UnityEngine.Object)nt : nt.GetComponent(ov.GetType());
        }
      }
      if (nv != null) { it.objectReferenceValue = nv; changed = true; repointed++; }
      else missed += comp.GetType().Name + "." + it.propertyPath + "(" + ov.name + ") ";
    }
    if (changed) so.ApplyModifiedPropertiesWithoutUndo();
  }
  log += "repointed=" + repointed + (missed.Length > 0 ? " UNRESOLVED: " + missed + "(weapon_mount.cs fixes WeaponHolder._mountPoint)" : "") + "; ";
  UnityEngine.Object.DestroyImmediate(oldModel);
  UnityEditor.PrefabUtility.SaveAsPrefabAsset(root, heroPath);
} finally { UnityEditor.PrefabUtility.UnloadPrefabContents(root); }
return "HERO SWAP OK " + log;
