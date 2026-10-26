// ucli.sh eval fix_animator_node.cs HERO=Assets/Prefabs/Heroes/Hero.prefab
// Repair for a hero whose scale/180deg turn sit on a WRAPPER above the Animator node (symptom: tiny + back to the
// camera in the Gear-tab preview, because CharacterPreviewController only keeps the Animator GameObject).
// Moves the wrapper's uniform scale onto the Animator node, sets the node to (0,180,0), wrapper to identity.
var path = "{{HERO}}"; var root = UnityEditor.PrefabUtility.LoadPrefabContents(path); var s = "";
try {
  var a = root.GetComponentInChildren<UnityEngine.Animator>(true); var model = a.transform; var wrap = model.parent;
  float sc = wrap.localScale.x * model.localScale.x; s += "wrap=" + wrap.name + " combinedScale=" + sc;
  wrap.localScale = UnityEngine.Vector3.one; wrap.localRotation = UnityEngine.Quaternion.identity;
  model.localScale = UnityEngine.Vector3.one * sc; model.localRotation = UnityEngine.Quaternion.Euler(0, 180, 0);
  UnityEditor.PrefabUtility.SaveAsPrefabAsset(root, path);
  s += " -> animator node scale=" + model.localScale.x + " rotY=" + model.localEulerAngles.y;
} finally { UnityEditor.PrefabUtility.UnloadPrefabContents(root); }
return s;
