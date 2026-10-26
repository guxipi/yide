// Canonical Humanoid T-pose for {{FBX}}: apply current humanDescription.skeleton to an instance (incl. root), then force
// spine/neck/head straight up, clavicles level, arms+forearms+hands along +-X with palms down, fingers straight along +-X,
// legs straight down with toes forward. Writes skeleton back + SaveAndReimport. Run on BOTH model and animation FBX.
var path = "{{FBX}}"; var imp = (UnityEditor.ModelImporter)UnityEditor.AssetImporter.GetAtPath(path); var hd = imp.humanDescription;
var asset = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(path);
var inst = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(asset, new UnityEngine.Vector3(800, 0, 800), UnityEngine.Quaternion.identity); string log = "";
try {
  var map = new System.Collections.Generic.Dictionary<string, UnityEngine.Transform>(); foreach (var t in inst.GetComponentsInChildren<UnityEngine.Transform>(true)) map[t.name] = t;
  int applied = 0; foreach (var sb in hd.skeleton) { UnityEngine.Transform t; if (map.TryGetValue(sb.name, out t)) { if (t == inst.transform) { t.rotation = sb.rotation; t.localScale = sb.scale; } else { t.localPosition = sb.position; t.localRotation = sb.rotation; t.localScale = sb.scale; } applied++; } }
  var an = inst.GetComponentInChildren<UnityEngine.Animator>(); var up = UnityEngine.Vector3.up; var X = UnityEngine.Vector3.right; var Z = UnityEngine.Vector3.forward;
  System.Func<UnityEngine.HumanBodyBones, UnityEngine.Transform> T = (b) => an.GetBoneTransform(b);
  System.Action<UnityEngine.Transform, UnityEngine.Vector3, UnityEngine.Vector3> Align = (bone, fromDir, toDir) => { if (bone == null) return; bone.rotation = UnityEngine.Quaternion.FromToRotation(fromDir.normalized, toDir.normalized) * bone.rotation; };
  System.Func<UnityEngine.Vector3, UnityEngine.Vector3, UnityEngine.Vector3> Perp = (v, axis) => { v -= UnityEngine.Vector3.Dot(v, axis) * axis; return v.normalized; };
  var hips = T(UnityEngine.HumanBodyBones.Hips); var spine = T(UnityEngine.HumanBodyBones.Spine); var chest = T(UnityEngine.HumanBodyBones.Chest); var uchest = T(UnityEngine.HumanBodyBones.UpperChest); var neck = T(UnityEngine.HumanBodyBones.Neck); var head = T(UnityEngine.HumanBodyBones.Head);
  var lul = T(UnityEngine.HumanBodyBones.LeftUpperLeg); var rul = T(UnityEngine.HumanBodyBones.RightUpperLeg);
  Align(hips, spine.position - hips.position, up); { var lat = Perp(lul.position - rul.position, up); hips.rotation = UnityEngine.Quaternion.FromToRotation(lat, -X) * hips.rotation; }
  var chain = new System.Collections.Generic.List<UnityEngine.Transform> { spine, chest, uchest, neck, head }; chain.RemoveAll(x => x == null);
  for (int i = 0; i < chain.Count - 1; i++) Align(chain[i], chain[i + 1].position - chain[i].position, up);
  { UnityEngine.Transform top = null; foreach (UnityEngine.Transform c in head) if (c.name.ToLower().Contains("top") || c.name.ToLower().Contains("end")) top = c; if (top != null) Align(head, top.position - head.position, up); else head.rotation = UnityEngine.Quaternion.FromToRotation(head.up, up) * head.rotation;
    var le = T(UnityEngine.HumanBodyBones.LeftEye); var re = T(UnityEngine.HumanBodyBones.RightEye); if (le != null && re != null) { var lat = Perp(le.position - re.position, up); head.rotation = UnityEngine.Quaternion.AngleAxis(UnityEngine.Vector3.SignedAngle(lat, -X, up), up) * head.rotation; } }
  log += "spine ok hipsLeft=" + Perp(lul.position - rul.position, up).ToString("F2") + " (expect -X); ";
  foreach (var side in new[] { "Left", "Right" }) {
    bool L = side == "Left"; float sx = L ? -1f : 1f; var AX = X * sx;
    var sh = T(L ? UnityEngine.HumanBodyBones.LeftShoulder : UnityEngine.HumanBodyBones.RightShoulder); var ua = T(L ? UnityEngine.HumanBodyBones.LeftUpperArm : UnityEngine.HumanBodyBones.RightUpperArm); var la = T(L ? UnityEngine.HumanBodyBones.LeftLowerArm : UnityEngine.HumanBodyBones.RightLowerArm); var hd2 = T(L ? UnityEngine.HumanBodyBones.LeftHand : UnityEngine.HumanBodyBones.RightHand);
    var idx = T(L ? UnityEngine.HumanBodyBones.LeftIndexProximal : UnityEngine.HumanBodyBones.RightIndexProximal); var lit = T(L ? UnityEngine.HumanBodyBones.LeftLittleProximal : UnityEngine.HumanBodyBones.RightLittleProximal); var mid = T(L ? UnityEngine.HumanBodyBones.LeftMiddleProximal : UnityEngine.HumanBodyBones.RightMiddleProximal);
    if (sh != null) { var d = ua.position - sh.position; var dh = Perp(d, up); if (dh.sqrMagnitude > 0) Align(sh, d, dh); }
    Align(ua, la.position - ua.position, AX); Align(la, hd2.position - la.position, AX); if (mid != null) Align(hd2, mid.position - hd2.position, AX);
    if (idx != null && lit != null) { var il = Perp(idx.position - lit.position, AX); ua.rotation = UnityEngine.Quaternion.AngleAxis(UnityEngine.Vector3.SignedAngle(il, Z, AX), AX) * ua.rotation;
      Align(la, hd2.position - la.position, AX); if (mid != null) Align(hd2, mid.position - hd2.position, AX);
      il = Perp(idx.position - lit.position, AX); hd2.rotation = UnityEngine.Quaternion.AngleAxis(UnityEngine.Vector3.SignedAngle(il, Z, AX), AX) * hd2.rotation; }
    foreach (var f in new[] { "Index", "Middle", "Ring", "Little" }) for (int k = 1; k <= 3; k++) {
      var bn = (UnityEngine.HumanBodyBones)System.Enum.Parse(typeof(UnityEngine.HumanBodyBones), side + f + (k == 1 ? "Proximal" : k == 2 ? "Intermediate" : "Distal")); var b = T(bn); if (b == null || b.childCount == 0) continue;
      Align(b, b.GetChild(0).position - b.position, AX); }
    var ul = T(L ? UnityEngine.HumanBodyBones.LeftUpperLeg : UnityEngine.HumanBodyBones.RightUpperLeg); var ll = T(L ? UnityEngine.HumanBodyBones.LeftLowerLeg : UnityEngine.HumanBodyBones.RightLowerLeg); var ft = T(L ? UnityEngine.HumanBodyBones.LeftFoot : UnityEngine.HumanBodyBones.RightFoot); var to = T(L ? UnityEngine.HumanBodyBones.LeftToes : UnityEngine.HumanBodyBones.RightToes);
    if (to != null) { var d = Perp(to.position - ft.position, up); ul.rotation = UnityEngine.Quaternion.AngleAxis(UnityEngine.Vector3.SignedAngle(d, Z, up), up) * ul.rotation; }
    Align(ul, ll.position - ul.position, -up); Align(ll, ft.position - ll.position, -up);
    if (to != null) { var footDir = new UnityEngine.Vector3(0f, -0.6428f, 0.7660f); Align(ft, to.position - ft.position, footDir); }
    log += side + " arm=" + (la.position - ua.position).normalized.ToString("F2") + " hand=" + (mid != null ? (mid.position - hd2.position).normalized.ToString("F2") : "-") + " idxlit=" + (idx != null ? Perp(idx.position - lit.position, AX).ToString("F2") : "-") + " leg=" + (ft.position - ul.position).normalized.ToString("F2") + " foot=" + (to != null ? (to.position - ft.position).normalized.ToString("F2") : "-") + "; ";
  }
  var skel = hd.skeleton; int patched = 0;
  for (int i = 0; i < skel.Length; i++) { UnityEngine.Transform t; if (map.TryGetValue(skel[i].name, out t) && t != inst.transform) { skel[i].position = t.localPosition; skel[i].rotation = t.localRotation; skel[i].scale = t.localScale; patched++; } }
  hd.skeleton = skel; imp.humanDescription = hd; UnityEditor.EditorUtility.SetDirty(imp); imp.SaveAndReimport(); log += "patched=" + patched + "/" + skel.Length;
} finally { UnityEngine.Object.DestroyImmediate(inst); }
var av = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.Avatar>(path); log += " avatar valid=" + (av != null && av.isValid);
return log;
