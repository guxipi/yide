#!/usr/bin/env node
// 会话标题:按会话主要目标起名,保留 SessionStart 打的"已就位 · 日期"底标。
//   标题 = "<目标名>_<底标>",例:"优化翼德_🗡️ 翼德已就位 · 2026-10-15"。
// 三处入口:
//   SessionStart      → forStart(sid, base):记下底标(resume/compact 不换日期),已有目标名就带上。
//   UserPromptSubmit  → onPrompt(sid, prompt):首句先用 prompt 粗取一个名字;模型起好的名字在下一句时换上。
//   模型 CLI          → node session-title.js set --session <sid> "目标名"(2-8 字)。
// Claude Code 只在 SessionStart / UserPromptSubmit 认 sessionTitle,所以模型起的名要等下一句才生效。
// 状态落本机私有 ~/.yide-local/session-titles.json(不同步,免多机抢写)。仅 Node 内置模块。
'use strict';
const path = require('path');
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));

const FILE = 'session-titles.json';
const MAX_SESSIONS = 200;
const MAX_GOAL = 12;

function load() { const o = readLocalJson(FILE, {}); return o && typeof o === 'object' ? o : {}; }
function save(map) {
  const ids = Object.keys(map);
  if (ids.length > MAX_SESSIONS) {
    ids.sort((a, b) => (map[a].t || 0) - (map[b].t || 0));
    for (const id of ids.slice(0, ids.length - MAX_SESSIONS)) delete map[id];
  }
  writeLocalJson(FILE, map);
}

function compose(e) { return e.goal ? `${e.goal}_${e.base}` : e.base; }

function cleanGoal(s) {
  return String(s || '').replace(/[\r\n\t_]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, MAX_GOAL).trim();
}

// 从首句 prompt 粗取目标名:去掉口头前缀,截到第一个标点。取不出像样的就返回空,标题保持底标。
const FILLER = /^(?:翼德|赤兔|勾哥|你好|hi|hello)?[,，\s]*(?:我想要|我想|我要|我需要|想要|需要|帮我|麻烦你?|请你?|能不能|能否|可以|你|给我|我们|咱们)+/i;
function guessGoal(prompt) {
  let s = String(prompt || '').trim();
  if (!s || s.startsWith('/') || s.startsWith('<')) return '';
  s = s.split(/[\r\n。.!！?？;；:：,，]/)[0].trim();
  for (let i = 0; i < 3; i++) { const n = s.replace(FILLER, '').trim(); if (n === s) break; s = n; }
  s = cleanGoal(s);
  if (s.length < 2 || /^(继续|好的?|ok|行|嗯|收工|是的?|对)$/i.test(s)) return '';
  return s;
}

// SessionStart:返回要设的标题。底标只在第一次记下(resume 不换成当天日期)。
function forStart(sid, base) {
  if (!sid || sid === 'nosid') return base;
  const map = load();
  const e = map[sid] || { base };
  if (!e.base) e.base = base;
  e.applied = compose(e);
  e.t = Date.now();
  map[sid] = e;
  save(map);
  return e.applied;
}

// UserPromptSubmit:标题需要变时返回 { title, ask },否则 null。ask=true 表示这是首句,该提醒模型起名。
function onPrompt(sid, prompt) {
  if (!sid || sid === 'nosid') return null;
  const map = load();
  const e = map[sid];
  if (!e || !e.base) return null; // 没经过 SessionStart(或别的宿主),不碰标题
  let ask = false;
  if (!e.asked) { e.asked = true; ask = true; }
  if (!e.goal) { const g = guessGoal(prompt); if (g) { e.goal = g; e.src = 'auto'; } }
  const title = compose(e);
  const changed = title !== e.applied;
  e.applied = title;
  e.t = Date.now();
  map[sid] = e;
  save(map);
  return (changed || ask) ? { title: changed ? title : null, ask } : null;
}

function setGoal(sid, goal) {
  const g = cleanGoal(goal);
  if (!sid || !g) return null;
  const map = load();
  const e = map[sid] || {};
  e.goal = g; e.src = 'model'; e.t = Date.now();
  map[sid] = e;
  save(map);
  return e.base ? compose(e) : g;
}

function instruction(sid, scriptPath) {
  return `🏷️ 会话命名:按本会话的主要目标起一个 2-8 字中文名(动宾短语,如"优化翼德""修金币HUD""DesertLab光影"),` +
    `跑 \`node "${scriptPath}" set --session ${sid} "名字"\`。标题会变成"名字_原底标"(底标的日期保留),下一句话起生效。` +
    `现在这个是从首句粗取的,准就不用改;目标明显换了再跑一次。静默做,不用汇报。`;
}

module.exports = { forStart, onPrompt, setGoal, guessGoal, compose, instruction };

if (require.main === module) {
  const a = process.argv.slice(2);
  const i = a.indexOf('--session');
  const sid = i >= 0 ? a[i + 1] : '';
  const rest = a.filter((_, k) => k !== i && k !== i + 1);
  if (rest[0] === 'set') {
    const r = setGoal(sid, rest.slice(1).join(' '));
    if (!r) { console.error('用法: session-title.js set --session <sid> "目标名"'); process.exit(1); }
    console.log('会话标题(下一句生效):' + r);
  } else if (rest[0] === 'show') {
    const e = load()[sid];
    console.log(e ? compose(e) : '(本会话没有记录)');
  } else {
    console.error('用法: session-title.js set|show --session <sid> ["目标名"]');
    process.exit(1);
  }
}
