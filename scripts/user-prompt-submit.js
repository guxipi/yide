#!/usr/bin/env node
// 翼德 UserPromptSubmit hook(召回):你每发一句,自动匹配 prompt 库,命中就温和推荐一条。
// 绝不阻断(exit 0 + additionalContext);同会话不重复推荐同一条;低置信不推。让你"根本不用记"。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));
const { matchByText } = require(path.join(__dirname, 'prompts-lib.js'));

const THRESHOLD = 2; // 至少命中 2 个关键词/标签才推,避免刷屏

function emit(text) {
  process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: text } }));
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const prompt = input.prompt || '';
  const sid = input.session_id || 'nosid';
  if (!prompt) process.exit(0);

  const m = matchByText(prompt);
  if (!m || m.score < THRESHOLD) process.exit(0);
  const slug = m.entry.slug;

  // 同会话不重复推荐(防 nagging)
  const logFile = path.join(brainDir(), '.meta', 'prompt-suggest-log.json');
  let log = {};
  try { log = JSON.parse(fs.readFileSync(logFile, 'utf8')); } catch {}
  const seen = log[sid] || [];
  if (seen.includes(slug)) process.exit(0);
  seen.push(slug); log[sid] = seen;
  // 防无限增长:会话过多就只保留当前会话
  if (Object.keys(log).length > 80) log = { [sid]: seen };
  try { fs.mkdirSync(path.dirname(logFile), { recursive: true }); fs.writeFileSync(logFile, JSON.stringify(log)); } catch {}

  const uses = m.entry.uses || 0;
  emit(
    `📌 翼德(prompt 库提示,不强求):你存过一条也许适合这次的——「${m.entry.name}」` +
    (m.entry.when ? `(${m.entry.when})` : '') +
    (uses ? `,用过 ${uses} 次` : '') +
    `。要用就说一声,我直接套用(可填参数);不需要就忽略。`
  );
  process.exit(0);
} catch (e) { process.exit(0); }
