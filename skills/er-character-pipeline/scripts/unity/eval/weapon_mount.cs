// ucli.sh eval weapon_mount.cs HERO=Assets/Prefabs/Heroes/Hero.prefab OLDHERO=Assets/Temp/HeroOld.prefab \
//     CLIP="Assets/Art/3DModelsfromGu/1_Animation/Humanoid/Breathing Idle.fbx"
// Creates <RightHand>/WeaponMount on the new model so every gun keeps its existing grip numbers
// (GunClassVisualLibrary GripRotation etc. were tuned on the old hero's hand): both heroes sample the SAME clip at
// t=0, the old WeaponMount pose relative to the old hand is transferred to the new hand, and WeaponHolder._mountPoint
// is pointed at it. (Verified on Wren 2026-10-07; side-by-side hold comparison: hold_ab.png.)
var clip = System.Linq.Enumerable.First(UnityEditor.AssetDatabase.LoadAllAssetsAtPath("{{CLIP}}"), o => o is UnityEngine.AnimationClip && !o.name.StartsWith("__")) as UnityEngine.AnimationClip;
var oldP = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{OLDHERO}}");
var newPath = "{{HERO}}"; var newP = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(newPath);
if (clip == null || oldP == null || newP == null) return "missing clip/old/new";
var o = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(oldP); var n = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(newP);
o.transform.position = UnityEngine.Vector3.zero; n.transform.position = UnityEngine.Vector3.zero;
var oa = o.GetComponentInChildren<UnityEngine.Animator>(true); var na = n.GetComponentInChildren<UnityEngine.Animator>(true);
UnityEditor.AnimationMode.StartAnimationMode(); UnityEditor.AnimationMode.BeginSampling();
UnityEditor.AnimationMode.SampleAnimationClip(oa.gameObject, clip, 0f); UnityEditor.AnimationMode.SampleAnimationClip(na.gameObject, clip, 0f);
UnityEditor.AnimationMode.EndSampling();
UnityEngine.Transform om = null; foreach (var t in o.GetComponentsInChildren<UnityEngine.Transform>(true)) if (t.name == "WeaponMount") om = t;
if (om == null) { foreach (var c in o.GetComponentsInChildren<UnityEngine.MonoBehaviour>(true)) if (c != null && c.GetType().Name == "WeaponHolder") om = (UnityEngine.Transform)new UnityEditor.SerializedObject(c).FindProperty("_mountPoint").objectReferenceValue; }
if (om == null) { UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.Object.DestroyImmediate(o); UnityEngine.Object.DestroyImmediate(n); return "old mount not found"; }
var nh = na.GetBoneTransform(UnityEngine.HumanBodyBones.RightHand); var ohh = oa.GetBoneTransform(UnityEngine.HumanBodyBones.RightHand);
var lrot = UnityEngine.Quaternion.Inverse(nh.rotation) * om.rotation;
var lpos = nh.InverseTransformPoint(nh.position + (om.position - ohh.position));
var lscl = new UnityEngine.Vector3(om.lossyScale.x / nh.lossyScale.x, om.lossyScale.y / nh.lossyScale.y, om.lossyScale.z / nh.lossyScale.z);
var info = "lrot=" + lrot.eulerAngles.ToString("F1") + " lpos=" + lpos.ToString("F3") + " lscl=" + lscl.ToString("F3");
var handName = nh.name;
UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.Object.DestroyImmediate(o); UnityEngine.Object.DestroyImmediate(n);
var root = UnityEditor.PrefabUtility.LoadPrefabContents(newPath);
try {
  var a = root.GetComponentInChildren<UnityEngine.Animator>(true); var hand = a.transform;
  foreach (var t in a.GetComponentsInChildren<UnityEngine.Transform>(true)) if (t.name == handName) hand = t;
  var ex = hand.Find("WeaponMount"); if (ex != null) UnityEngine.Object.DestroyImmediate(ex.gameObject);
  var m = new UnityEngine.GameObject("WeaponMount").transform; m.SetParent(hand, false); m.localPosition = lpos; m.localRotation = lrot; m.localScale = lscl;
  foreach (var c in root.GetComponentsInChildren<UnityEngine.MonoBehaviour>(true)) if (c != null && c.GetType().Name == "WeaponHolder") { var so = new UnityEditor.SerializedObject(c); so.FindProperty("_mountPoint").objectReferenceValue = m; so.ApplyModifiedPropertiesWithoutUndo(); info += " assigned"; }
  UnityEditor.PrefabUtility.SaveAsPrefabAsset(root, newPath);
} finally { UnityEditor.PrefabUtility.UnloadPrefabContents(root); }
return "WEAPON MOUNT OK " + info + " (lscl should be ~0.1-3; ~100x means the FBX root scale bug is back)";
