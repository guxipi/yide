// ucli.sh eval materials_setup.cs DIR=Assets/Art/3DModelsfromGu/0_Characters/<Name> NAME=<Name> FBX=<DIR>/<Name>.fbx \
//     EMISSION=1 ER=0.12 EG=0.42 EB=0.32      (no glow: EMISSION=0 ER=0 EG=0 EB=0 - every placeholder must be filled)
//     BASE=0.82 THRESH=-0.03 SOFT=0.82 TINT=0.74,0.76,0.9 AMB=0.32 RIM=0.55,0.65,0.85,0 RIMPOW=5.37
// Creates/updates <Name>.mat and <Name>Face.mat (Lab/LabLit, Assets/Shaders/Lab/LabLit.shader), remaps every embedded
// FBX material onto them (face = name containing "Face", everything else = body), reimports.
// Defaults = battery_goblin_revised.mat (J01Creatures_20261030, LabLit since 2026-10-30); spring_spec.py fills them
// from char_config unity.lablit. LabLit has no outline; _RimColor alpha is the rim strength (0 = off).
// Glow = _UseEmissionMap 1 + keyword _EMISSION + _EmissionMap x _EmissionColor (_EmissionColor is always added, black = none).
// Textures expected: <DIR>/Textures/<Name>_basecolor.png, <Name>_face_atlas.png, optional <Name>_emission.png.
var dir = "{{DIR}}"; var name = "{{NAME}}"; var fbx = "{{FBX}}";
var sh = UnityEngine.Shader.Find("Lab/LabLit");
if (sh == null) return "Lab/LabLit not found";
System.Func<string, UnityEngine.Material> get = (p) => {
  var m = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Material>(p);
  if (m == null) { m = new UnityEngine.Material(sh); UnityEditor.AssetDatabase.CreateAsset(m, p); }
  m.shader = sh; return m; };
var body = get(dir + "/" + name + ".mat"); var face = get(dir + "/" + name + "Face.mat");
var baseTex = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_basecolor.png");
var atlas = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_face_atlas.png");
if (baseTex == null || atlas == null) return "missing textures under " + dir + "/Textures";
System.Func<string, float> F = (x) => float.Parse(x, System.Globalization.CultureInfo.InvariantCulture);
var tint = "{{TINT}}".Split(','); var rim = "{{RIM}}".Split(','); float bc = F("{{BASE}}");
if (tint.Length != 3 || rim.Length != 4) return "TINT needs r,g,b and RIM needs r,g,b,a";
foreach (var m in new[] { body, face }) {
  m.SetColor("_BaseColor", new UnityEngine.Color(bc, bc, bc, 1f));
  m.SetFloat("_ShadowThreshold", F("{{THRESH}}")); m.SetFloat("_ShadowSoftness", F("{{SOFT}}"));
  m.SetColor("_ShadowTint", new UnityEngine.Color(F(tint[0]), F(tint[1]), F(tint[2]), 1f));
  m.SetFloat("_AmbientStrength", F("{{AMB}}"));
  m.SetColor("_RimColor", new UnityEngine.Color(F(rim[0]), F(rim[1]), F(rim[2]), F(rim[3])));
  m.SetFloat("_RimPower", F("{{RIMPOW}}"));
  m.SetFloat("_UseEmissionMap", 0f); m.DisableKeyword("_EMISSION"); m.SetColor("_EmissionColor", UnityEngine.Color.black);
  UnityEditor.EditorUtility.SetDirty(m);
}
body.SetTexture("_BaseMap", baseTex); body.SetTextureScale("_BaseMap", UnityEngine.Vector2.one); body.SetTextureOffset("_BaseMap", UnityEngine.Vector2.zero);
face.SetTexture("_BaseMap", atlas); face.SetTextureScale("_BaseMap", new UnityEngine.Vector2(0.25f, 1f / 3f)); face.SetTextureOffset("_BaseMap", UnityEngine.Vector2.zero);
var em = "none";
if ("{{EMISSION}}" == "1") {
  var et = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Texture2D>(dir + "/Textures/" + name + "_emission.png");
  if (et == null) return "EMISSION=1 but Textures/" + name + "_emission.png missing";
  body.SetFloat("_UseEmissionMap", 1f); body.EnableKeyword("_EMISSION");
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
return "materials ok (Lab/LabLit), emission=" + em + " | remapped: " + mapped + " | re-run avatar_check.cs to see the remap list";
