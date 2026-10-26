#!/usr/bin/env bash
# In-game verification run (the real player path, not an isolated render):
#   Play (from Boot) -> Home -> Gear tab (Button_02 under TabButtonContainer) -> capture
#   -> START (PlayButton) -> Briefing -> DEPLOY (Button_Deploy) -> wait for scene "Expedition" -> find the character
#   -> capture full + high-res -> editor_stop (always, also on failure).
# usage: ingame_check.sh <AvatarNameContains> <OUTDIR> [STATES]
#   STATES = "state:layer:t,..." frozen-pose captures after the expedition capture
#            (default "Sprint:0:0.35,HeroPistolRecoil:WeaponHold:0.35,death:0:0.55" - death last, see below; layer = index or name)
# Prerequisites: `ucli.sh guard` OK; Hero.prefab locally swapped (hero_swap.cs); nobody else is using Play.
# Output: OUTDIR/{home,gear,briefing,expedition,expedition_hi,state_*}.png + ingame.log. A missing capture or "no <name>"
# in the log = FAIL. Then Opus crops/looks at: gear (size, faces camera, gun in hand, no giant objects),
# expedition (top-down readability, feet on ground, hair/skirt not exploding, HP bar position).
set -uo pipefail
NAME="${1:?avatar name substring}"; OUT="${2:?outdir}"; mkdir -p "$OUT"
STATES="${3:-Sprint:0:0.35,HeroPistolRecoil:WeaponHold:0.35,death:0:0.55}"  # death LAST: anim_state only switches the named layer, the base layer stays frozen in the previous state (10-08 Rook: recoil shot inherited the death fall)
U="$(dirname "$0")/ucli.sh"; UNITY="${UNITY_CLI:-C:/Users/kryst/AppData/Local/Unity/bin/unity.exe}"
LOG="$OUT/ingame.log"; : > "$LOG"
say() { echo "$*" | tee -a "$LOG"; }
cleanup() { say "stop: $(bash "$U" stop)"; }
trap cleanup EXIT
bash "$U" guard | tee -a "$LOG" || exit 1
say "start scene: $("$UNITY" cmd eval --code 'return UnityEditor.SceneManagement.EditorSceneManager.playModeStartScene==null?"(current scene)":UnityEditor.SceneManagement.EditorSceneManager.playModeStartScene.name;' 2>&1 | grep -oE '"result":"[^"]*"')"
say "play: $(bash "$U" play)"
sleep 25
say "scenes: $(bash "$U" scenes)"
bash "$U" capture home "$OUT" >>"$LOG"
say "gear tab: $(bash "$U" click Button_02 TabButtonContainer)"; sleep 4
bash "$U" capture gear "$OUT" >>"$LOG"
# 10-07 Vesper: PlayButton lives on the HOME tab (UIHomeScreenPanel), not on Gear -> go back to Home (Button_03) first
say "home tab: $(bash "$U" click Button_03 TabButtonContainer)"; sleep 3
say "start: $(bash "$U" click PlayButton)"; sleep 5
bash "$U" capture briefing "$OUT" >>"$LOG"
say "deploy: $(bash "$U" click Button_Deploy)"
for i in $(seq 1 40); do s=$(bash "$U" scenes); echo "$s" | grep -q Expedition && break; sleep 3; done
say "scenes: $s"; sleep 15
say "character: $("$UNITY" cmd eval --code "foreach(var a in UnityEngine.Object.FindObjectsByType<UnityEngine.Animator>(UnityEngine.FindObjectsSortMode.None)) if(a.avatar!=null&&a.avatar.name.Contains(\"$NAME\")) return \"found at \"+a.transform.position.ToString(\"F1\")+\" root=\"+a.transform.root.name+\" lossyScale=\"+a.transform.lossyScale.x.ToString(\"F2\"); return \"no $NAME\";" 2>&1 | grep -oE '"result":"[^"]*"')"
say "all instances: $("$UNITY" cmd eval --code "var s=\"\"; foreach(var a in UnityEngine.Object.FindObjectsByType<UnityEngine.Animator>(UnityEngine.FindObjectsSortMode.None)) if(a.avatar!=null&&a.avatar.name.Contains(\"$NAME\")) s+=a.transform.root.name+\"@\"+a.transform.position.ToString(\"F0\")+\" \"; return s;" 2>&1 | grep -oE '"result":"[^"]*"')"
bash "$U" capture expedition "$OUT" >>"$LOG"
bash "$U" capture expedition_hi "$OUT" 1440 2560 >>"$LOG"
EV="$(dirname "$0")/eval/anim_state.cs"
IFS=',' read -ra ST <<<"$STATES"
for spec in "${ST[@]}"; do
  IFS=':' read -r sn sl stt <<<"$spec"
  say "state $sn: $(bash "$U" eval "$EV" NAME="$NAME" STATE="$sn" LAYER="$sl" T="$stt")"; sleep 1
  bash "$U" capture "state_$sn" "$OUT" 1080 1920 >>"$LOG"
done
say "resume: $(bash "$U" eval "$EV" NAME="$NAME" STATE=__resume LAYER=0 T=0)"
say "console errors (last 20):"
"$UNITY" cmd console 2>&1 | grep -iE "error|exception" | grep -viE "vivox|chat" | tail -20 >>"$LOG"
say "done -> $OUT"
