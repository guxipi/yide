// PLAY MODE ONLY. ucli.sh eval anim_state.cs NAME=<avatar name part> STATE=Sprint LAYER=0 T=0.35   (LAYER = index or name)
// Forces the in-game character's Animator into a controller state at normalized time T and freezes it (speed 0) so
// a capture shows that pose; RESET with STATE=__resume. States used on Wren: idle (default), Sprint, death;
// HeroPistolRecoil lives on the WeaponHold layer (LAYER=<index of WeaponHold>; list layers with STATE=__layers).
// This samples states - it does not prove input->movement works; that needs a real run (joystick/keyboard).
UnityEngine.Animator a = null;
foreach (var x in UnityEngine.Object.FindObjectsByType<UnityEngine.Animator>(UnityEngine.FindObjectsSortMode.None))
  if (x.avatar != null && x.avatar.name.Contains("{{NAME}}")) { a = x; break; }
if (a == null) return "no animator with avatar containing {{NAME}}";
if ("{{STATE}}" == "__layers") { var s = ""; for (int i = 0; i < a.layerCount; i++) s += i + ":" + a.GetLayerName(i) + " w=" + a.GetLayerWeight(i).ToString("F2") + " "; return s; }
if ("{{STATE}}" == "__resume") { a.speed = 1f; return "resumed"; }
int layer; if (!int.TryParse("{{LAYER}}", out layer)) layer = a.GetLayerIndex("{{LAYER}}");
if (layer < 0) return "layer not found: {{LAYER}}";
a.speed = 1f; a.Play("{{STATE}}", layer, {{T}}f); a.Update(0f); a.speed = 0f;
return "playing {{STATE}} on layer " + a.GetLayerName(layer) + " t={{T}} (frozen; send STATE=__resume when done)";
