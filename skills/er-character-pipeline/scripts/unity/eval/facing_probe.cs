// zero-muscle facing check for {{ASSETS}}: LeftHand.x must be < 0 and toes.z > 0 in animator local space
string log = "";
foreach (var p in "{{ASSETS}}".Split(';')) { var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p); var go = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(pf, new UnityEngine.Vector3(700, 0, 700), UnityEngine.Quaternion.identity);
  try { var an = go.GetComponentInChildren<UnityEngine.Animator>(); var h = new UnityEngine.HumanPoseHandler(an.avatar, an.transform); var hp = new UnityEngine.HumanPose(); h.GetHumanPose(ref hp);
    for (int i = 0; i < hp.muscles.Length; i++) hp.muscles[i] = 0; hp.bodyRotation = UnityEngine.Quaternion.identity; hp.bodyPosition = new UnityEngine.Vector3(0, 1, 0); h.SetHumanPose(ref hp);
    System.Func<UnityEngine.HumanBodyBones, UnityEngine.Vector3> B = (b) => an.transform.InverseTransformPoint(an.GetBoneTransform(b).position);
    var lh = B(UnityEngine.HumanBodyBones.LeftHand); var lf = B(UnityEngine.HumanBodyBones.LeftFoot); var lt = B(UnityEngine.HumanBodyBones.LeftToes);
    log += p + " LHand.x=" + lh.x.ToString("F2") + " toes.z=" + (lt - lf).z.ToString("F2") + " => " + ((lh.x < 0 && (lt - lf).z > 0) ? "FACING OK" : "FACING WRONG") + "\n";
  } finally { UnityEngine.Object.DestroyImmediate(go); } }
return log;
