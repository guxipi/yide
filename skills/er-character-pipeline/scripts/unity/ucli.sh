#!/usr/bin/env bash
# Thin wrapper around the Unity CLI (unity.exe + com.unity.pipeline) for the character pipeline.
# ALWAYS call from Git Bash (PowerShell eats the double quotes inside eval code).
#
#   ucli.sh status                      -> prints playMode / compiling
#   ucli.sh guard                       -> exit 1 if the editor is playing or compiling (run before ANY .cs write)
#   ucli.sh eval FILE.cs [K=V ...]      -> substitutes {{K}} in FILE, runs it as `unity cmd eval` (statement form,
#                                          must end with `return <expr>;`), prints the result string
#                                          UCLI_DRY=1: only print the substituted code; UCLI_COMPILE_ONLY=1: compile it
#                                          inside a never-called lambda (syntax/type check with zero side effects)
#   ucli.sh play | stop                 -> enter/exit Play and WAIT until the state really changed
#   ucli.sh capture NAME OUTDIR [W H]   -> capture_game_view; the CLI saves under Assets/Temp/, this moves the PNG
#                                          to OUTDIR and deletes the Assets/Temp copy + .meta (never leave it there)
#   ucli.sh click BUTTON_NAME [PARENT]  -> invoke onClick of the first ACTIVE UnityEngine.UI.Button with that name
#   ucli.sh scenes                      -> names of loaded scenes
#   ucli.sh buttons                     -> active interactable buttons: name(parent)[label] (when a click says "none")
#
# Rules baked in (2026-09/10 lessons):
#   - eval runs on the main thread: never block on async (.Result/.Wait()/GetAwaiter().GetResult()) -> editor deadlock
#   - eval code is statement form: `return expr;`
#   - another session may be using the editor: `guard` before writing any .cs, and never leave Play running
set -uo pipefail
UNITY="${UNITY_CLI:-C:/Users/kryst/AppData/Local/Unity/bin/unity.exe}"
PROJ="${UNITY_PROJECT:-F:/GitManagedUnityProjects/Extraction}"
cmd="${1:-}"; shift || true

result() { grep -oE '"result":"([^"\\]|\\.)*"' | head -1 | sed -e 's/^"result":"//' -e 's/"$//' -e 's/\\n/\n/g' -e 's/\\"/"/g'; }
state() { "$UNITY" cmd editor_status 2>&1 | grep -oE '"playMode":"[a-z]+"' | head -1 | cut -d'"' -f4; }

case "$cmd" in
  status)
    "$UNITY" cmd editor_status 2>&1 | grep -oE '"(status|playMode|compiling|domainReloadInProgress)":[^,}]*' ;;
  guard)
    s=$(state); c=$("$UNITY" cmd editor_status 2>&1 | grep -oE '"(compiling|domainReloadInProgress)":true' || true)
    if [ "$s" != "stopped" ] || [ -n "$c" ]; then echo "GUARD FAIL: playMode=$s $c - do NOT write .cs now (ask / wait)"; exit 1; fi
    echo "GUARD OK: editor stopped and not compiling (still check that no other session is about to Play)";;
  eval)
    f="$1"; shift
    code=$(cat "$f")
    for kv in "$@"; do k="${kv%%=*}"; v="${kv#*=}"; code="${code//\{\{$k\}\}/$v}"; done
    if grep -q '{{[A-Z_]*}}' <<<"$code"; then echo "unfilled placeholders: $(grep -oE '\{\{[A-Z_]+\}\}' <<<"$code" | sort -u | tr '\n' ' ')"; exit 2; fi
    if [ "${UCLI_DRY:-0}" = 1 ]; then echo "$code"; exit 0; fi
    # compile-only: wrap the snippet in a lambda that is never invoked -> the editor compiles it, nothing runs
    if [ "${UCLI_COMPILE_ONLY:-0}" = 1 ]; then code="System.Func<string> __f = () => { $code
    }; return \"COMPILED\";"; fi
    out=$("$UNITY" cmd eval --code "$code" --timeout "${EVAL_TIMEOUT:-180}" 2>&1)
    r=$(result <<<"$out")
    if [ -z "$r" ]; then echo "$out" | grep -iE 'error|diagnostic|exception' | head -20; exit 1; fi
    echo "$r";;
  play)
    "$UNITY" cmd editor_play >/dev/null 2>&1
    for i in $(seq 1 40); do [ "$(state)" = "playing" ] && { echo playing; exit 0; }; sleep 3; done; echo "TIMEOUT entering play"; exit 1;;
  stop)
    "$UNITY" cmd editor_stop >/dev/null 2>&1
    for i in $(seq 1 30); do [ "$(state)" = "stopped" ] && { echo stopped; exit 0; }; sleep 2; done
    echo "STOP NOT CONFIRMED - send ONE more stop, then ask the user to press Ctrl+P (do not hammer)"; exit 1;;
  capture)
    name="$1"; outdir="$2"; w="${3:-720}"; h="${4:-1280}"; mkdir -p "$outdir"
    "$UNITY" cmd capture_game_view --save_path "$PROJ/Temp/$name.png" --width "$w" --height "$h" >/dev/null 2>&1
    for p in "$PROJ/Assets/Temp/$name.png" "$PROJ/Temp/$name.png"; do
      if [ -f "$p" ]; then mv -f "$p" "$outdir/$name.png"; rm -f "$p.meta"; echo "$outdir/$name.png"; exit 0; fi
    done
    echo "capture not found (game view not rendering? use eval/render_views.cs)"; exit 1;;
  click)
    b="$1"; par="${2:-}"
    cond="b.gameObject.name==\"$b\"&&b.gameObject.activeInHierarchy"
    [ -n "$par" ] && cond="$cond&&b.transform.parent!=null&&b.transform.parent.name==\"$par\""
    "$UNITY" cmd eval --code "foreach(var b in UnityEngine.Object.FindObjectsByType<UnityEngine.UI.Button>(UnityEngine.FindObjectsSortMode.None)) if($cond){ b.onClick.Invoke(); return \"clicked\"; } return \"none\";" 2>&1 | result;;
  buttons)
    "$UNITY" cmd eval --code 'var s=""; foreach(var b in UnityEngine.Object.FindObjectsByType<UnityEngine.UI.Button>(UnityEngine.FindObjectsSortMode.None)) if(b.gameObject.activeInHierarchy&&b.interactable){ var tx=b.GetComponentInChildren<TMPro.TMP_Text>(); s+=b.gameObject.name+"("+(b.transform.parent!=null?b.transform.parent.name:"")+")["+(tx!=null?tx.text:"")+"] "; } return s;' 2>&1 | result;;
  scenes)
    "$UNITY" cmd eval --code 'var s=""; for(int i=0;i<UnityEngine.SceneManagement.SceneManager.sceneCount;i++) s+=UnityEngine.SceneManagement.SceneManager.GetSceneAt(i).name+" "; return s;' 2>&1 | result;;
  ""|-h|--help)
    sed -n '2,22p' "$0";;
  *) echo "unknown: $cmd"; exit 2;;
esac
