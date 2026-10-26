var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("Assets/Art/3DModelsfromGu/0_Characters/Rook2/Rook2.prefab");
var go = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(pf); go.transform.position = new UnityEngine.Vector3(1500, 0, 1500); string log = "";
try { var an = go.GetComponentInChildren<UnityEngine.Animator>(); UnityEngine.AnimationClip clip = null; foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath("{{FBX}}")) { var c = o as UnityEngine.AnimationClip; if (c != null && c.name == "{{CLIP}}") clip = c; }
  UnityEditor.AnimationMode.StartAnimationMode();
  foreach (var ts in "1.5,3,4.5,6,7.5,9,10.5,12,13.5,15".Split(',')) { float t = float.Parse(ts, System.Globalization.CultureInfo.InvariantCulture);
    for (int r = 0; r < 2; r++) { UnityEditor.AnimationMode.BeginSampling(); UnityEditor.AnimationMode.SampleAnimationClip(an.gameObject, clip, t); UnityEditor.AnimationMode.EndSampling(); }
    System.Func<UnityEngine.HumanBodyBones, UnityEngine.Vector3> B = (b) => an.GetBoneTransform(b).position;
    var lh = B(UnityEngine.HumanBodyBones.LeftUpperLeg); var rh = B(UnityEngine.HumanBodyBones.RightUpperLeg); var lk = B(UnityEngine.HumanBodyBones.LeftLowerLeg); var rk = B(UnityEngine.HumanBodyBones.RightLowerLeg); var lf = B(UnityEngine.HumanBodyBones.LeftFoot); var rf = B(UnityEngine.HumanBodyBones.RightFoot);
    var lat = lh - rh; lat.y = 0; float hw = lat.magnitude; lat.Normalize();
    log += "t=" + ts + " kneeSpread/hip=" + (UnityEngine.Vector3.Dot(lk - rk, lat) / hw).ToString("F2") + " ankleSpread/hip=" + (UnityEngine.Vector3.Dot(lf - rf, lat) / hw).ToString("F2") + "\n"; }
} finally { UnityEditor.AnimationMode.StopAnimationMode(); UnityEngine.Object.DestroyImmediate(go); }
return log;
