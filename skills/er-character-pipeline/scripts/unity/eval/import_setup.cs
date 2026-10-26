// ucli.sh eval import_setup.cs FBX=Assets/Art/3DModelsfromGu/0_Characters/<Name>/<Name>.fbx
// Humanoid + Create From This Model, no animation import, import normals (switch to Calculate 30deg ONLY if
// the shading looks lumpy - Wren did not need it). Reimports once. Next: enforce_tpose.cs, avatar_check.cs.
var path = "{{FBX}}";
var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(path);
if (imp == null) return "no ModelImporter at " + path;
imp.animationType = UnityEditor.ModelImporterAnimationType.Human;
imp.avatarSetup = UnityEditor.ModelImporterAvatarSetup.CreateFromThisModel;
imp.importAnimation = false;
imp.importNormals = UnityEditor.ModelImporterNormals.Import;
imp.materialImportMode = UnityEditor.ModelImporterMaterialImportMode.ImportStandard;
imp.SaveAndReimport();
var mats = "";
foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(path)) if (o is UnityEngine.Material) mats += o.name + " | ";
return "ok animationType=" + imp.animationType + " embedded materials: " + mats + " (these names are the remap keys)";
