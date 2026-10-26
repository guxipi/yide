// ucli.sh eval avatar_check.cs FBX=Assets/.../<Name>.fbx
// Acceptance for the Humanoid avatar (Rook R1 lesson: "ran the fix" is not evidence):
//   humanDescription.human >= 22 AND skeleton non-empty AND avatar isHuman && isValid.
// Also lists the importer material remaps so a stale remap (old tripo_mat_<uuid>) is visible.
var path = "{{FBX}}";
var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(path);
if (imp == null) return "no importer";
var hd = imp.humanDescription;
UnityEngine.Avatar av = null;
foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(path)) if (o is UnityEngine.Avatar) av = (UnityEngine.Avatar)o;
var remaps = "";
foreach (var kv in imp.GetExternalObjectMap()) remaps += kv.Key.name + "->" + (kv.Value != null ? kv.Value.name : "null") + "; ";
var embedded = "";
foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(path)) if (o is UnityEngine.Material) embedded += o.name + "; ";
int human = hd.human != null ? hd.human.Length : 0, skel = hd.skeleton != null ? hd.skeleton.Length : 0;
bool pass = human >= 22 && skel > 0 && av != null && av.isHuman && av.isValid;
return (pass ? "AVATAR PASS" : "AVATAR FAIL") + " human=" + human + " skeleton=" + skel + " isHuman=" + (av != null && av.isHuman) + " isValid=" + (av != null && av.isValid) + " | remaps: " + remaps + " | embedded: " + embedded;
