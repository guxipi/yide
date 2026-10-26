// Spring safety for big motions (Wren 10-08): run AFTER prefab_build.cs, on the character prefab.
// Without this, laugh/jump/crouch flip the skirt up and shred the hair: SpringBone angle limits were off on every
// bone (and they are silently ignored unless pivotNode is set), and the thigh had colliders only at hip and knee,
// so the skirt fell through the middle of the thigh.
// What it does:
//   1. every SpringBone gets a "<bone>_LimitPivot" (child of the bone's parent) whose -X points along the rest bone
//      direction (SpringBone measures limits around -pivot.right) and y/z angle limits;
//   2. skirt bones: pivot up = radial outward from the hips, so the y limit is asymmetric: open OUTWARD (thighs can
//      push the skirt out) but barely inward (no folding into the legs); z = sideways swing;
//   3. a SpringCapsuleCollider along each thigh (UpLeg -> Leg) assigned to every skirt bone.
// Placeholders:
//   PREFAB  = prefab path
//   LIMITS  = "prefix|limitDeg|drag;prefix|limitDeg|drag"  for non-skirt chains (first matching prefix wins),
//             Wren: "Hair_F|25|0.45;Hair|45|0.45"
//   SKIRT   = "prefix|outwardDeg|inwardDeg|sideDeg|drag|stiffness|backOutwardDeg"  Wren: "Skirt|80|10|20|0.75|90|25"
//             (NONE = no skirt). Front panels need room for the thighs; the back panel has no thigh to push it and
//             bells up when a sprint start leans the body forward, so it gets backOutwardDeg (blended by facing).
//             outward 70 let the back panel flip up like a bell on sprint start (QA 10-08); 45 still lets thighs push it
//   THIGH_R = capsule radius as a fraction of thigh length  Wren: 0.5
//   DYN     = SpringManager.dynamicRatio  Wren: 1   (below 1 every frame blends back toward the animated skirt pose,
//             which is exactly where the lifted thigh is - the skirt gets pulled into the leg)
// ORDER MATTERS (SpringBone.UpdateSpring): collision runs BEFORE angle limits, so a limit tighter than the thigh lift
// drags the pushed skirt straight back into the leg. Front panels therefore need a wide outward limit (80) and the
// back panel a tight one (25, nothing pushes it, and it bells up on sprint start). Do not edit the package.
// Verify: re-enter Play, open the Gear tab and force big fidgets (laugh_01, jump_down) - see references/08.
var path = "{{PREFAB}}";
var root = UnityEditor.PrefabUtility.LoadPrefabContents(path);
var log = "";
try {
  System.Func<string, UnityEngine.Transform> F = n => { foreach (var t in root.GetComponentsInChildren<UnityEngine.Transform>(true)) if (t.name == n) return t; return null; };
  var hips = F("mixamorig:Hips");
  var caps = new System.Collections.Generic.List<Unity.Animations.SpringBones.SpringCapsuleCollider>();
  var skirtSpec = "{{SKIRT}}";
  if (skirtSpec != "NONE") {
    foreach (var side in new[] { "Left", "Right" }) {
      var up = F("mixamorig:" + side + "UpLeg"); var knee = F("mixamorig:" + side + "Leg");
      var old = up.Find("ThighCapsule"); if (old != null) UnityEngine.Object.DestroyImmediate(old.gameObject);
      var g = new UnityEngine.GameObject("ThighCapsule").transform; g.SetParent(up, false);
      g.localPosition = UnityEngine.Vector3.zero;
      g.rotation = UnityEngine.Quaternion.FromToRotation(UnityEngine.Vector3.up, (knee.position - up.position).normalized);
      var cc = g.gameObject.AddComponent<Unity.Animations.SpringBones.SpringCapsuleCollider>();
      cc.height = g.InverseTransformPoint(knee.position).y; cc.radius = {{THIGH_R}}f * cc.height; caps.Add(cc);
    }
  }
  var sk = skirtSpec.Split('|');
  // Character front from the feet (toe - foot), independent of how the model root is rotated.
  var toe = F("mixamorig:LeftToeBase"); var foot = F("mixamorig:LeftFoot");
  var front = toe != null && foot != null ? toe.position - foot.position : root.transform.forward;
  front -= UnityEngine.Vector3.Dot(front, root.transform.up) * root.transform.up; front.Normalize();
  var rules = "{{LIMITS}}".Split(';');
  int n = 0, skirtN = 0;
  foreach (var b in root.GetComponentsInChildren<Unity.Animations.SpringBones.SpringBone>(true)) {
    UnityEngine.Transform child = null; foreach (UnityEngine.Transform c in b.transform) { child = c; break; }
    if (child == null || b.transform.parent == null) { log += "NO_CHILD " + b.name + " "; continue; }
    var d = (child.position - b.transform.position).normalized;
    var pname = b.name + "_LimitPivot"; var oldp = b.transform.parent.Find(pname); if (oldp != null) UnityEngine.Object.DestroyImmediate(oldp.gameObject);
    var pv = new UnityEngine.GameObject(pname).transform; pv.SetParent(b.transform.parent, false); pv.position = b.transform.position;
    var right = -d; UnityEngine.Vector3 upv;
    bool isSkirt = skirtSpec != "NONE" && b.name.StartsWith(sk[0]);
    if (isSkirt) { var radial = b.transform.position - hips.position; radial -= UnityEngine.Vector3.Dot(radial, root.transform.up) * root.transform.up; upv = radial; }
    else { upv = UnityEngine.Mathf.Abs(UnityEngine.Vector3.Dot(UnityEngine.Vector3.up, right)) > 0.9f ? UnityEngine.Vector3.forward : UnityEngine.Vector3.up; }
    upv = (upv - UnityEngine.Vector3.Dot(upv, right) * right).normalized;
    pv.rotation = UnityEngine.Quaternion.LookRotation(UnityEngine.Vector3.Cross(right, upv), upv);
    b.pivotNode = pv; b.yAngleLimits.active = true; b.zAngleLimits.active = true;
    if (isSkirt) {
      // y side vector is -pivot.up (inward): negative angles open outward.
      float outward = float.Parse(sk[1]);
      if (sk.Length > 6) { float facing = UnityEngine.Vector3.Dot(upv, front); outward = UnityEngine.Mathf.Lerp(float.Parse(sk[6]), outward, UnityEngine.Mathf.Clamp01((facing + 1f) * 0.5f)); }
      b.yAngleLimits.min = -outward; b.yAngleLimits.max = float.Parse(sk[2]);
      b.zAngleLimits.min = -float.Parse(sk[3]); b.zAngleLimits.max = float.Parse(sk[3]);
      b.dragForce = float.Parse(sk[4]); if (sk.Length > 5) b.stiffnessForce = float.Parse(sk[5]); b.capsuleColliders = caps.ToArray(); skirtN++;
    } else {
      float lim = 20f;
      foreach (var r in rules) { var p = r.Split('|'); if (p.Length == 3 && b.name.StartsWith(p[0])) { lim = float.Parse(p[1]); b.dragForce = float.Parse(p[2]); break; } }
      b.yAngleLimits.min = -lim; b.yAngleLimits.max = lim; b.zAngleLimits.min = -lim; b.zAngleLimits.max = lim;
    }
    if ((-pv.right - d).magnitude > 0.01f) log += "AXIS_BAD " + b.name + " ";
    n++;
  }
  var mgr = root.GetComponentInChildren<Unity.Animations.SpringBones.SpringManager>(true);
  if (mgr != null) { mgr.enableAngleLimits = true; mgr.enableCollision = true; mgr.dynamicRatio = {{DYN}}f; } else log += "NO_SPRING_MANAGER ";
  UnityEditor.PrefabUtility.SaveAsPrefabAsset(root, path);
  log = "SPRING_LIMITS bones=" + n + " skirt=" + skirtN + " thighCapsules=" + caps.Count + " " + log;
} finally { UnityEditor.PrefabUtility.UnloadPrefabContents(root); }
return log;
