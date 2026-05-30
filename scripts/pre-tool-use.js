#!/usr/bin/env node
// 翼德 PreToolUse hook:硬层。读 ~/.yide/.meta/hook-rules.json,对即将执行的动作做确定性正则匹配,
// 命中即 deny 并把原因告诉模型。这是"记过的错绝不再犯"里唯一能真正 block 的一环(仅 Claude Code)。
// 仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

const RULES = path.join(brainDir(), '.meta', 'hook-rules.json');

function deny(reason) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'deny',
      permissionDecisionReason: '🗡️ 翼德拦截:' + reason,
    },
  }));
  process.exit(0);
}
function collect(v, out) {
  if (typeof v === 'string') out.push(v);
  else if (Array.isArray(v)) for (const x of v) collect(x, out);
  else if (v && typeof v === 'object') for (const k of Object.keys(v)) collect(v[k], out);
  return out;
}

try {
  if (!fs.existsSync(RULES)) process.exit(0);
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const tool = input.tool_name || '';
  const blob = collect(input.tool_input || {}, []).join('\n');

  let conf;
  try { conf = JSON.parse(fs.readFileSync(RULES, 'utf8')); } catch { process.exit(0); }
  const rules = Array.isArray(conf.rules) ? conf.rules : [];

  for (const r of rules) {
    if (!r || !r.pattern) continue;
    const tools = Array.isArray(r.tools) && r.tools.length ? r.tools : ['*'];
    if (!tools.includes('*') && !tools.includes(tool)) continue;
    let re; try { re = new RegExp(r.pattern); } catch { continue; }
    if (re.test(blob)) deny(r.reason || ('命中规则 ' + r.pattern));
  }
  process.exit(0);
} catch (e) { process.exit(0); }
