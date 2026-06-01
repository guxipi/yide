#!/usr/bin/env node
// 翼德 UserPromptSubmit hook。你每发一句,翼德做两件事(都非阻断,合并成一次 additionalContext):
//   1) prompt 库召回:命中就温和推荐一条存过的好用 prompt(同会话不重复、低置信不推)。
//   2) 会话健康度:纠正太多次 / 会话太长 → 一次性提醒重开会话(且承诺"重开不丢")。
// 绝不阻断(exit 0);让勾哥"根本不用记"。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { readJson, writeJson } = require(path.join(__dirname, 'store.js'));
const { matchByText } = require(path.join(__dirname, 'prompts-lib.js'));
const { sessionNudge } = require(path.join(__dirname, 'session-health.js'));

const THRESHOLD = 2; // 至少命中 2 个关键词/标签才推,避免刷屏

function emit(text) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: text } }));
}

// 计算 prompt 库召回提示(命中则返回字符串,否则 null)。含同会话去重写盘。
function recallSuggestion(prompt, sid) {
  const m = matchByText(prompt);
  if (!m || m.score < THRESHOLD) return null;
  const slug = m.entry.slug;

  let log = readJson('prompt-suggest-log.json', {}) || {};
  const seen = log[sid] || [];
  if (seen.includes(slug)) return null; // 同会话不重复推荐(防 nagging)
  seen.push(slug); log[sid] = seen;
  if (Object.keys(log).length > 80) log = { [sid]: seen }; // 防无限增长
  writeJson('prompt-suggest-log.json', log);

  const uses = m.entry.uses || 0;
  return `📌 翼德(prompt 库提示,不强求):你存过一条也许适合这次的——「${m.entry.name}」` +
    (m.entry.when ? `(${m.entry.when})` : '') +
    (uses ? `,用过 ${uses} 次` : '') +
    `。要用就说一声,我直接套用(可填参数);不需要就忽略。`;
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const prompt = input.prompt || '';
  const sid = input.session_id || 'nosid';
  if (!prompt) process.exit(0);

  const parts = [];
  // 1) 会话健康度提醒(先评估:它的优先级更高,治最痛的"修6遍/上下文污染")
  try { const n = sessionNudge(input); if (n) parts.push(n); } catch {}
  // 2) prompt 库召回
  try { const r = recallSuggestion(prompt, sid); if (r) parts.push(r); } catch {}

  if (parts.length) emit(parts.join('\n\n'));
  process.exit(0);
} catch (e) { process.exit(0); }
