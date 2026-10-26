// ucli.sh eval materials_setup.cs DIR=Assets/Art/3DModelsfromGu/0_Characters/<Name> NAME=<Name> FBX=<DIR>/<Name>.fbx \
//     EMISSION=1 ER=0.12 EG=0.42 EB=0.32      (no glow: EMISSION=0 ER=0 EG=0 EB=0 - every placeholder must be filled)
// Creates/updates <Name>.mat and <Name>Face.mat (Custom/ToonLit) with the PAINTED-ALBEDO parameters, remaps every
// embedded FBX material onto them (face = name containing "Face", everything else = body), reimports.
// Why these numbers: engineer.mat's ToonLit values (outline 20, shadow 0.6/0.5/0.6, threshold 0.746, smoothing 0.06,
// rim 0.351) are for flat KayKit models; on a painted Tripo albedo they shade twice and ink every hair strand
// ("looks like a different, broken character", Wren 2026-10-07). Wren-calibrated values below.
// Textures expected: <DIR>/Textures/<Name>_basecolor.png, <Name>_face_atlas.png, optional <Name>_emission.png.
var dir = "{{DIR}}"; var name = "{{NAME}}"; var fbx = "{{FBX}}";
var sh = UnityEngine.Shader.Find("Custom/ToonLit");
if (sh == null) return "Custom/ToonLit not found";
System.Func<string, UnityEngine.Material> get = (p) => {
  var m = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>(p);
  if (m == null) { m = new UnityEngine.Material(sh); UnityEditor.AssetDatabase.CreateAsset(m, p); }
  m.shader = sh; return m; };
var body = get(dir + "/" + name + ".mat"); var face = get(dir + "/" + name + "Face.mat");
var baseTex = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_basecolor.png");
var atlas = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_face_atlas.png");
if (baseTex == null || atlas == null) return "missing textures under " + dir + "/Textures";
System.Func<string, float> F = (x) => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture);
var sc = "{{SHADOW}}".Split(','); float bc = F("{{BASE}}");
foreach (var m in new[] { body, face }) {
  m.SetColor("_BaseColor", new UnityEngine.Color(bc, bc, bc, 1f));
  m.SetColor("_ShadowColor", new UnityEngine.Color(F(sc[0]), F(sc[1]), F(sc[2]), 1f));
  m.SetFloat("_ShadowThreshold", F("{{THRESH}}")); m.SetFloat("_ShadowSmoothing", F("{{SMOOTH}}"));
  m.SetFloat("_OutlineWidth", F("{{OUTLINE}}")); m.SetColor("_OutlineColor", UnityEngine.Color.black);
  m.SetFloat("_RimThreshold", F("{{RIM}}")); m.SetFloat("_RimPower", 5.37f); m.SetColor("_RimColor", UnityEngine.Color.white);
  m.SetFloat("_AmbientStrength", 0.3f);
  UnityEditor.EditorUtility.SetDirty(m);
}
body.SetTexture("_BaseMap", baseTex); body.SetTextureScale("_BaseMap", UnityEngine.Vector2.one); body.SetTextureOffset("_BaseMap", UnityEngine.Vector2.zero);
face.SetTexture("_BaseMap", atlas); face.SetTextureScale("_BaseMap", new UnityEngine.Vector2(0.25f, 1f / 3f)); face.SetTextureOffset("_BaseMap", UnityEngine.Vector2.zero);
var em = "none";
if ("{{EMISSION}}" == "1") {
  var et = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_emission.png");
  if (et == null) return "EMISSION=1 but Textures/" + name + "_emission.png missing";
  body.SetTexture("_EmissionMap", et); body.SetColor("_EmissionColor", new UnityEngine.Color({{ER}}f, {{EG}}f, {{EB}}f, 1f)); em = et.name;
}
UnityEditor.AssetDatabase.SaveAssets();
var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(fbx);
var mapped = "";
foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(fbx)) {
  if (!(o is UnityEngine.Material)) continue;
  var target = o.name.Contains("Face") ? face : body;
  imp.AddRemap(new UnityEditor.AssetImporter.SourceAssetIdentifier(typeof(UnityEngine.Material), o.name), target);
  mapped += o.name + "->" + target.name + "; ";
}
imp.SaveAndReimport();
return "materials ok, emission=" + em + " | remapped: " + mapped + " | re-run avatar_check.cs to see the remap list";
