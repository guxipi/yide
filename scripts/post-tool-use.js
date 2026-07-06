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
const host = require(path.join(__dirname, 'host.js'));
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));
const { lint } = require(path.join(__dirname, 'lint-unity.js'));
const { matchByPath, globToRe } = require(path.join(__dirname, 'lessons.js'));

function out(ctx) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: ctx } }));
}

try {
  // 归一 host 差异:Claude Code 的 Write/Edit 原样;Codex 的 apply_patch 解析出 file_path + 新增文本。
  const input = host.normalizeToolEvent(JSON.parse(fs.readFileSync(0, 'utf8') || '{}'));
  const fp = input.tool_input && input.tool_input.file_path;
  if (!fp) process.exit(0);

  // 把关配置:expertLevel(默认 expert,资深友好:只报非显而易见)+ 学到的静音
  let gate = { expertLevel: 'expert', suppressed: [] };
  try { gate = Object.assign(gate, JSON.parse(fs.readFileSync(path.join(brainDir(), '.meta', 'gatekeeper.json'), 'utf8'))); } catch {}

  // ① Unity lint(仅 .cs;带 Unity 版本 gating 过时 API;按 expertLevel 过滤;只看本次改动的行)
  let findings = [];
  if (/\.cs$/i.test(fp)) {
    let unityVersion = null, source = '';
    try {
      const proj = host.projectDir(input);
      const m = fs.readFileSync(path.join(proj, 'ProjectSettings', 'ProjectVersion.txt'), 'utf8').match(/m_EditorVersion:\s*(.+)/);
      if (m) unityVersion = m[1].trim();
    } catch {}
    try { source = fs.readFileSync(fp, 'utf8'); findings = lint(source, { unityVersion, expertLevel: gate.expertLevel, filePath: fp }); } catch {}

    // clean-as-you-code:只报"本次改动/新增的行",不翻旧账
    const ti = input.tool_input || {};
    let added = '';
    if (typeof ti.content === 'string') added = ti.content;            // Write:整文件即改动
    else {
      if (typeof ti.new_string === 'string') added += ti.new_string + '\n';
      if (Array.isArray(ti.edits)) for (const e of ti.edits) if (e && typeof e.new_string === 'string') added += e.new_string + '\n';
    }
    if (added) {
      const addedSet = new Set(added.split(/\r?\n/).map(s => s.trim()).filter(s => s.length > 3));
      const all = source.split(/\r?\n/);
      findings = findings.filter(f => addedSet.has((all[f.line - 1] || '').trim()));
    }
    // 学到的静音:{rule, glob} 命中则丢
    if (Array.isArray(gate.suppressed) && gate.suppressed.length) {
      const fpn = fp.replace(/\\/g, '/');
      findings = findings.filter(f => !gate.suppressed.some(s => s.rule === f.rule && (!s.glob || (globToRe(s.glob) || { test: () => true }).test(fpn))));
    }
  }
  // ② scope 命中的 lessons
  let lessons = [];
  try { lessons = matchByPath(fp); } catch {}

  if (!findings.length && !lessons.length) process.exit(0);

  // 去重:同文件、同一组(findings + lesson ids)只提醒一次
  const sig = findings.map(f => f.line + f.msg).join('|') + '#' + lessons.map(l => l.id).join(',');
  const SEEN = 'lint-seen.json';                          // 本机私有(会话去重状态,不进同步盘)
  let seen = readLocalJson(SEEN, {}) || {};
  const hash = crypto.createHash('sha1').update(sig).digest('hex');
  if (seen[fp] === hash) process.exit(0);
  delete seen[fp]; seen[fp] = hash;                       // 移到最新(LRU)
  const seenKeys = Object.keys(seen);                     // 防无界增长:只留最近 200 个文件(对象保插入序,裁最旧)
  if (seenKeys.length > 200) for (const k of seenKeys.slice(0, seenKeys.length - 200)) delete seen[k];
  writeLocalJson(SEEN, seen);

  let msg = '';
  if (lessons.length) {
    // 上下文保险:命中再多也只列高优先级前 5 条(按 severity 降序),其余只报数
    const sorted = lessons.slice().sort((a, b) => (b.severity || 0) - (a.severity || 0));
    const showL = sorted.slice(0, 5);
    msg += `📌 翼德:这个文件命中 ${lessons.length} 条你定过的教训(务必遵守):\n`;
    for (const l of showL) msg += `- [${l.id}][sev:${l.severity}] ${l.ruleText}\n`;
    if (lessons.length > showL.length) msg += `- …还有 ${lessons.length - showL.length} 条(按 severity 取前 5;全量见 ~/.yide/lessons)\n`;
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
