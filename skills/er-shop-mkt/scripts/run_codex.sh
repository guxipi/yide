#!/usr/bin/env bash
# Run one prompt file through codex image_gen and verify refs reached the image model.
# usage: bash run_codex.sh <work_dir> <name> <expected_ref_count>
#   work_dir holds p_<name>.txt (from mkprompt.py); image lands in work_dir/img/<name>.png, log in work_dir/log_<name>.txt
# Run several in parallel with run_in_background; never pipe Chinese through PowerShell.
set -u
W="$1"; N="$2"; R="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$W" || exit 2
codex exec --skip-git-repo-check --enable skip_host_skill_discovery -m gpt-6.1-sol -C "$(cygpath -m "$PWD" 2>/dev/null || pwd)" \
  "$(cat "p_$N.txt")" > "log_$N.txt" 2>&1
PYTHONIOENCODING=utf-8 py -3 "$HERE/check_rollout.py" "log_$N.txt" "$R" || { echo "REJECT $N: refs not passed or skill loaded, rerun"; exit 1; }
[ -f "img/$N.png" ] || { echo "REJECT $N: no image saved"; exit 1; }
echo "OK $N -> $W/img/$N.png"
