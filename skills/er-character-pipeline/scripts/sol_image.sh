#!/usr/bin/env bash
# Run one sol (gpt-5.6-sol via codex CLI) image job: prompt file on STDIN + reference images.
# usage: sol_image.sh --ws <workspace> --prompt <prompt.txt> [-i ref1.png -i ref2.png ...] [--model gpt-5.6-sol] [--dry]
# Several jobs in parallel: run them in ONE shell with '&' and then 'wait' (a nested '( ... & )' kills them).
# Known traps (2026-10-06/07):
#   - the prompt must go through stdin ("- < file"); passing "$(cat file)" as an argument arrives empty
#   - the workspace is not a git repo -> --skip-git-repo-check is mandatory
#   - the permission rule Bash(codex exec:*) must be allowed, otherwise auto mode silently denies it
#   - feeding an older version of the character with -i locks the face/pose: for face-structure changes drop it
set -euo pipefail
WS=""; PROMPT=""; MODEL="gpt-5.6-sol"; DRY=0; IMGS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ws) WS="$2"; shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    -i) IMGS+=("-i" "$2"); shift 2;;
    --model) MODEL="$2"; shift 2;;
    --dry) DRY=1; shift;;
    -h|--help) sed -n '2,10p' "$0"; exit 0;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
[ -n "$WS" ] && [ -n "$PROMPT" ] || { echo "need --ws and --prompt" >&2; exit 2; }
[ -f "$PROMPT" ] || { echo "prompt not found: $PROMPT" >&2; exit 2; }
for ((k=1; k<${#IMGS[@]}; k+=2)); do [ -f "${IMGS[$k]}" ] || { echo "ref image not found: ${IMGS[$k]}" >&2; exit 2; }; done
LOG="${PROMPT%.txt}-log.txt"
CMD=(codex exec --skip-git-repo-check -m "$MODEL" "${IMGS[@]}" -)
if [ "$DRY" = 1 ]; then echo "cd \"$WS\" && ${CMD[*]} < \"$PROMPT\" > \"$LOG\" 2>&1"; exit 0; fi
cd "$WS"
"${CMD[@]}" < "$PROMPT" > "$LOG" 2>&1 || { echo "sol failed, see $LOG" >&2; exit 1; }
tail -n 6 "$LOG"
