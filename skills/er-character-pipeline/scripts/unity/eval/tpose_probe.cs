// For each asset in {{ASSETS}} (prefab or fbx, ';' separated): instantiate, measure rest-pose and zero-muscle-pose leg geometry.
string log = "";
foreach (var p in "{{ASSETS}}".Split(';')) {
  var pf = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(p); if (pf == null) { log += "missing " + p + "\n"; continue; }
  var go = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(pf, new UnityEngine.Vector3(700, 0, 700), UnityEngine.Quaternion.identity);
  try {
    var an = go.GetComponentInChildren<UnityEngine.Animator>(); if (an == null || !an.isHuman) { log += "no human animator " + p + "\n"; continue; }
    System.Func<string> M = () => {
      System.Func<UnityEngine.HumanBodyBones, UnityEngine.Vector3> B = (b) => an.GetBoneTransform(b).position;
      var lh = B(UnityEngine.HumanBodyBones.LeftUpperLeg); var rh = B(UnityEngine.HumanBodyBones.RightUpperLeg); var lf = B(UnityEngine.HumanBodyBones.LeftFoot); var rf = B(UnityEngine.HumanBodyBones.RightFoot);
      var lk = B(UnityEngine.HumanBodyBones.LeftLowerLeg); var rk = B(UnityEngine.HumanBodyBones.RightLowerLeg);
      var lat = lh - rh; lat.y = 0; float hw = lat.magnitude; lat.Normalize();
      var ld = (lf - lh).normalized; var rd = (rf - rh).normalized;
      return "hipW=" + hw.ToString("F3") + " ankleSpread/hip=" + (UnityEngine.Vector3.Dot(lf - rf, lat) / hw).ToString("F2") + " kneeSpread/hip=" + (UnityEngine.Vector3.Dot(lk - rk, lat) / hw).ToString("F2") + " Lleg dir(lat,y,fwd)=(" + UnityEngine.Vector3.Dot(ld, lat).ToString("F2") + "," + ld.y.ToString("F2") + ") Rleg=(" + UnityEngine.Vector3.Dot(rd, -lat).ToString("F2") + "," + rd.y.ToString("F2") + ")"; };
    log += p + "\n  rest: " + M() + "\n";
    var h = new UnityEngine.HumanPoseHandler(an.avatar, an.transform); var hp = new UnityEngine.HumanPose(); h.GetHumanPose(ref hp);
    log += "  rest muscles LUpLeg F/B,In/Out,Twist=" + hp.muscles[21].ToString("F2") + "," + hp.muscles[22].ToString("F2") + "," + hp.muscles[23].ToString("F2") + " RUpLeg=" + hp.muscles[29].ToString("F2") + "," + hp.muscles[30].ToString("F2") + "," + hp.muscles[31].ToString("F2") + "\n";
    for (int i = 0; i < hp.muscles.Length; i++) hp.muscles[i] = 0; hp.bodyRotation = UnityEngine.Quaternion.identity; hp.bodyPosition = new UnityEngine.Vector3(0, 1, 0); h.SetHumanPose(ref hp);
    log += "  zeroMuscle: " + M() + "\n";
  } finally { UnityEngine.Object.DestroyImmediate(go); }
}
log += "muscle names 21-23,29-31: " + UnityEngine.HumanTrait.MuscleName[21] + "|" + UnityEngine.HumanTrait.MuscleName[22] + "|" + UnityEngine.HumanTrait.MuscleName[23] + "|" + UnityEngine.HumanTrait.MuscleName[29] + "|" + UnityEngine.HumanTrait.MuscleName[30] + "|" + UnityEngine.HumanTrait.MuscleName[31];
return log;
