// Build <Name>.prefab = FBX instance + Animator(avatar, HeroAnimationController) + face controller + SpringBones.
// Generate the exact command with: py -3 scripts/unity/spring_spec.py --config char.json   (fills every placeholder)
// Placeholders: FBX, PREFAB, CONTROLLER, FACE_TYPE ("Namespace.Class, Assembly-CSharp" or NONE), SPRING, COLLIDERS, MANAGER
//   SPRING    = "prefix|stiffness|drag|radius|colliderBone,colliderBone;prefix|..."  (bones whose name starts with prefix,
//               *_Tip excluded; hair chains get NO colliders: their roots sit inside head/neck spheres and get pushed
//               out into horizontal "wings" - shrinking radii does not help)
//   COLLIDERS = "bone:radius,bone:radius"   (SpringSphereCollider; Wren: legs only, for the skirt)
//   MANAGER   = "fps|dynamicRatio|gx|gy|gz|collision(0/1)|lengthLimits(0/1)|ground(0/1)"
// SpringBone package: com.unity.springbone (UnityChan SpringBone 1.2, git URL in references/08), namespace
// Unity.Animations.SpringBones (NOT UnityChan.*). To re-test spring settings: change the prefab, re-enter Play,
// spawn a NEW instance - toggling bones at runtime corrupts the simulation state.
var fbx = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>("{{FBX}}");
if (fbx == null) return "FBX not found";
var root = (UnityEngine.GameObject)UnityEditor.PrefabUtility.InstantiatePrefab(fbx);
var log = "";
try {
  root.name = System.IO.Path.GetFileNameWithoutExtension("{{PREFAB}}");
  var anim = root.GetComponent<UnityEngine.Animator>(); if (anim == null) anim = root.AddComponent<UnityEngine.Animator>();  // never use the null-coalescing operator on UnityEngine.Object (editor fake-null)
  foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath("{{FBX}}")) if (o is UnityEngine.Avatar) anim.avatar = (UnityEngine.Avatar)o;
  anim.runtimeAnimatorController = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.RuntimeAnimatorController>("{{CONTROLLER}}");
  anim.applyRootMotion = false;
  log += "avatar=" + (anim.avatar != null ? anim.avatar.name : "NULL") + " controller=" + (anim.runtimeAnimatorController != null) + "; ";
  if ("{{FACE_TYPE}}" != "NONE") {
    var ft = System.Type.GetType("{{FACE_TYPE}}");
    if (ft == null) return "face controller type not found: {{FACE_TYPE}}";
    if (root.GetComponent(ft) == null) root.AddComponent(ft);
    log += "face=" + ft.Name + "; ";
  }
  var all = root.GetComponentsInChildren<UnityEngine.Transform>(true);
  System.Func<string, UnityEngine.Transform> find = (n) => { foreach (var t in all) if (t.name == n) return t; return null; };
  var colliders = new System.Collections.Generic.Dictionary<string, Unity.Animations.SpringBones.SpringSphereCollider>();
  foreach (var c in "{{COLLIDERS}}".Split(new[] { ',' }, System.StringSplitOptions.RemoveEmptyEntries)) {
    var kv = c.Split(':'); var r = kv[kv.Length - 1]; var bn = c.Substring(0, c.Length - r.Length - 1);
    var t = find(bn); if (t == null) return "collider bone not found: " + bn;
    var sc = t.gameObject.AddComponent<Unity.Animations.SpringBones.SpringSphereCollider>();
    sc.radius = float.Parse(r, System.Globalization.CultureInfo.InvariantCulture); colliders[bn] = sc;
  }
  int n = 0;
  foreach (var spec in "{{SPRING}}".Split(new[] { ';' }, System.StringSplitOptions.RemoveEmptyEntries)) {
    var f = spec.Split('|');
    var cols = new System.Collections.Generic.List<Unity.Animations.SpringBones.SpringSphereCollider>();
    if (f.Length > 4) foreach (var cb in f[4].Split(new[] { ',' }, System.StringSplitOptions.RemoveEmptyEntries)) { if (!colliders.ContainsKey(cb)) return "collider not declared in COLLIDERS: " + cb; cols.Add(colliders[cb]); }
    foreach (var t in all) {
      if (!t.name.StartsWith(f[0]) || t.name.EndsWith("_Tip")) continue;
      var sb = t.gameObject.GetComponent<Unity.Animations.SpringBones.SpringBone>(); if (sb == null) sb = t.gameObject.AddComponent<Unity.Animations.SpringBones.SpringBone>();
      sb.stiffnessForce = float.Parse(f[1], System.Globalization.CultureInfo.InvariantCulture);
      sb.dragForce = float.Parse(f[2], System.Globalization.CultureInfo.InvariantCulture);
      sb.radius = float.Parse(f[3], System.Globalization.CultureInfo.InvariantCulture);
      sb.springForce = new UnityEngine.Vector3(0f, -0.0001f, 0f);
      sb.sphereColliders = cols.ToArray(); sb.capsuleColliders = new Unity.Animations.SpringBones.SpringCapsuleCollider[0]; sb.panelColliders = new Unity.Animations.SpringBones.SpringPanelCollider[0];
      if (t.childCount == 0) log += "WARN leaf spring bone without child: " + t.name + "; ";
      n++;
    }
  }
  var mg = root.GetComponent<Unity.Animations.SpringBones.SpringManager>(); if (mg == null) mg = root.AddComponent<Unity.Animations.SpringBones.SpringManager>();
  var m = "{{MANAGER}}".Split('|'); System.Func<int, float> F = (i) => float.Parse(m[i], System.Globalization.CultureInfo.InvariantCulture);
  mg.simulationFrameRate = (int)F(0); mg.dynamicRatio = F(1); mg.gravity = new UnityEngine.Vector3(F(2), F(3), F(4));
  mg.enableCollision = m[5] == "1"; mg.enableLengthLimits = m[6] == "1"; mg.collideWithGround = m[7] == "1";
  mg.FindSpringBones(true);
  log += "springBones=" + n + " colliders=" + colliders.Count + "; ";
  UnityEditor.PrefabUtility.SaveAsPrefabAsset(root, "{{PREFAB}}");
} finally { UnityEngine.Object.DestroyImmediate(root); }
return "PREFAB OK {{PREFAB}} " + log;
