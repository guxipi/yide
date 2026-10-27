"""Verify a codex image job really passed its reference images to image_gen and loaded no host skill.

usage: py -3 check_rollout.py <codex exec log file> <expected ref count>
Reads 'session id: <uuid>' from the log, finds ~/.codex/sessions/**/rollout-*<uuid>.jsonl,
counts .png paths inside each tools.image_gen__imagegen({referenced_image_paths:[...]}) call.
Exit 0 = every image_gen call carried exactly the expected refs and no ER art skill was read.
"""
import glob, json, os, re, sys

log, want = sys.argv[1], int(sys.argv[2])
txt = open(log, encoding='utf-8', errors='replace').read()
m = re.search(r'session id:\s*([0-9a-f-]{36})', txt)
if not m:
    sys.exit(f'FAIL no session id in {log}')
sid = m.group(1)
hits = glob.glob(os.path.expanduser(f'~/.codex/sessions/**/rollout-*{sid}.jsonl'), recursive=True)
if not hits:
    sys.exit(f'FAIL rollout for {sid} not found')
calls, skill = [], 0
for line in open(hits[0], encoding='utf-8'):
    d = json.loads(line).get('payload', {})
    # the skill name always appears in codex's skill catalog; only count it when a tool call actually opens it
    if d.get('type') in ('custom_tool_call', 'function_call') and 'direct-extraction-raider-art' in json.dumps(d):
        skill += 1
    inp = d.get('input') if d.get('type') == 'custom_tool_call' else None
    if inp and 'image_gen__imagegen' in inp:
        arr = re.search(r'referenced_image_paths\s*:\s*\[(.*?)\]', inp, re.S)
        calls.append(len(re.findall(r'\.png', arr.group(1))) if arr else 0)
ok = bool(calls) and all(c == want for c in calls) and skill == 0
print(('PASS' if ok else 'FAIL'), f'image_gen calls={len(calls)} refs={calls} want={want} er-art-skill-hits={skill}', hits[0])
sys.exit(0 if ok else 1)
