#!/usr/bin/env node
// 翼德 PostToolUse hook(把关 + scope 教训注入):写/改文件后,
//   ① 若是 .cs:按 Unity best practice lint;
//   ② 任意文件:浮现 scope/glob 命中该文件的 lessons;
// 都作为 advisory 喂给模型(非阻断)。带去重,避免刷屏。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { brainDir } = require(path.join(__dirname, 'lib.js'));
const { lint } = require(path.join(__dirname, 'lint-unity.js'));
const { matchByPath } = require(path.join(__dirname, 'lessons.js'));

function out(ctx) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: ctx } }));
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const fp = input.tool_input && input.tool_input.file_path;
  if (!fp) process.exit(0);

  // ① Unity lint(仅 .cs,文件须可读)
  let findings = [];
  if (/\.cs$/i.test(fp)) {
    try { findings = lint(fs.readFileSync(fp, 'utf8')); } catch {}
  }
  // ② scope 命中的 lessons
  let lessons = [];
  try { lessons = matchByPath(fp); } catch {}

  if (!findings.length && !lessons.length) process.exit(0);

  // 去重:同文件、同一组(findings + lesson ids)只提醒一次
  const sig = findings.map(f => f.line + f.msg).join('|') + '#' + lessons.map(l => l.id).join(',');
  const seenFile = path.join(brainDir(), '.meta', 'lint-seen.json');
  let seen = {};
  try { seen = JSON.parse(fs.readFileSync(seenFile, 'utf8')); } catch {}
  const hash = crypto.createHash('sha1').update(sig).digest('hex');
  if (seen[fp] === hash) process.exit(0);
  seen[fp] = hash;
  try { fs.mkdirSync(path.dirname(seenFile), { recursive: true }); fs.writeFileSync(seenFile, JSON.stringify(seen)); } catch {}

  let msg = '';
  if (lessons.length) {
    msg += `📌 翼德:这个文件命中 ${lessons.length} 条你定过的教训(务必遵守):\n`;
    for (const l of lessons) msg += `- [${l.id}][sev:${l.severity}] ${l.ruleText}\n`;
  }
  if (findings.length) {
    const top = findings.slice(0, 8);
    msg += `🗡️ 翼德把关 — \`${path.basename(fp)}\` 有 ${findings.length} 处可优化(Unity best practice,建议非强制):\n`;
    for (const f of top) msg += `- L${f.line} [${f.rule}] ${f.msg}\n`;
    if (findings.length > top.length) msg += `- …还有 ${findings.length - top.length} 处\n`;
  }
  msg += '请向用户简要说明并给修法建议;教训类必须遵守,把关类若用户有意为之则尊重,不擅自大改。';
  out(msg);
  process.exit(0);
} catch (e) { process.exit(0); }
