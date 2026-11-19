#!/usr/bin/env node
// 会话标题:按会话主要目标起名,保留 SessionStart 打的"已就位 · 日期"底标。
//   标题 = "<目标名>_<底标>",例:"翼德:会话命名优化_🗡️ 翼德已就位 · 2026-11-19"。
//   目标名由模型起,写成「系统:具体事」(勾哥 11-19:首句硬截的半句话不好读,同时管很多会话时找不到)。
// 三处入口:
//   SessionStart      → forStart(sid, base):记下底标(resume/compact 不换日期),已有目标名就带上。
//   UserPromptSubmit  → onPrompt(sid, prompt):首句先用 prompt 粗取一个占位名,并提醒模型起正式名;模型起好的名字在下一句时换上。
//   模型 CLI          → node session-title.js set --session <sid> "系统:具体事"。
// Claude Code 只在 SessionStart / UserPromptSubmit 认 sessionTitle,所以模型起的名走 hook 要等下一句才生效;
// 桌面 app 里模型可以再调 set_session_title(self) 让它马上生效(见 instruction)。
// 状态落本机私有 ~/.yide-local/session-titles.json(不同步,免多机抢写)。仅 Node 内置模块。
'use strict';
const path = require('path');
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));

const FILE = 'session-titles.json';
const MAX_SESSIONS = 200;
const MAX_GOAL = 12; // 首句粗取的占位名
const MAX_NAME = 24; // 模型起的正式名(提示里要求不超过 16 字,这里只是兜底)

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

function cleanGoal(s, max) {
  return String(s || '').replace(/[\r\n\t_]+/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max || MAX_GOAL).trim();
}

// 截到 MAX_GOAL 字;截点落在英文词 / 数字中间("…给每个sessi")就退到词头,不留半个词。
function cutGoal(s) {
  if (s.length <= MAX_GOAL) return s;
  let cut = s.slice(0, MAX_GOAL);
  if (/[A-Za-z0-9]/.test(s[MAX_GOAL]) && /[A-Za-z0-9]$/.test(cut)) {
    const back = cut.replace(/[A-Za-z0-9]+$/, '').trim();
    if (back.length >= 2) cut = back;
  }
  return cut.trim();
}

// 从首句 prompt 粗取目标名:去掉口头前缀,截到第一个标点。取不出像样的就返回空,标题保持底标。
const FILLER = /^(?:翼德|赤兔|勾哥|你好|hi|hello)?[,，\s]*(?:我想要|我想|我要|我需要|想要|需要|帮我|麻烦你?|请你?|能不能|能否|可以|你|给我|我们|咱们)+/i;
function guessGoal(prompt) {
  let s = String(prompt || '').trim();
  if (!s || s.startsWith('/') || s.startsWith('<')) return '';
  s = s.split(/[\r\n。.!！?？;；:：,，]/)[0].trim();
  for (let i = 0; i < 3; i++) { const n = s.replace(FILLER, '').trim(); if (n === s) break; s = n; }
  s = cutGoal(cleanGoal(s, 200));
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
  const g = cleanGoal(goal, MAX_NAME).replace(/\s*[：:]\s*/, ':');
  if (!sid || !g) return null;
  const map = load();
  const e = map[sid] || {};
  e.goal = g; e.src = 'model'; e.t = Date.now();
  map[sid] = e;
  save(map);
  return e.base ? compose(e) : g;
}

function instruction(sid, scriptPath) {
  return `🏷️ 会话命名(勾哥同时管很多会话,靠标题找会话):现在的标题是从首句硬截的半句话,不好认。` +
    `按这次会话要做的事起一个「系统:具体事」的名字:冒号前是系统 / 领域(基地、丛林、商店、UI、服务端、翼德…),冒号后是具体做什么,合计不超过 16 字,` +
    `不抄首句,不带"帮我 / 看看 / 继续"这类虚词。例:"翼德:会话命名优化""竞品:更新频次调研""基地:训兵玩法总结"。` +
    `和本回合第一批工具调用一起跑 \`node "${scriptPath}" set --session ${sid} "名字"\`,它会打印完整标题(名字_原底标,底标和日期保留),不单独占一轮。` +
    `有 mcp__ccd_session_mgmt__set_session_title 工具时(桌面 app;是 deferred 就先 ToolSearch 加载),再用 session_id "self" 把打印出来的完整标题设上,马上生效;没有这个工具就等下一句自动生效。` +
    `本会话是别的会话派出来的(首条消息是派单 brief)就跳过,标题派单方已经起好。会话目标明显换了再起一次。静默做,不用汇报。`;
}

module.exports = { forStart, onPrompt, setGoal, guessGoal, compose, instruction };

if (require.main === module) {
  const a = process.argv.slice(2);
  const i = a.indexOf('--session');
  const sid = i >= 0 ? a[i + 1] : '';
  const rest = a.filter((_, k) => k !== i && k !== i + 1);
  if (rest[0] === 'set') {
    const r = setGoal(sid, rest.slice(1).join(' '));
    if (!r) { console.error('用法: session-title.js set --session <sid> "系统:具体事"'); process.exit(1); }
    console.log('完整标题:' + r);
    console.log('(hook 在下一句话时换上;桌面 app 里把上面这行用 set_session_title 设给 self 可马上生效)');
  } else if (rest[0] === 'show') {
    const e = load()[sid];
    console.log(e ? compose(e) : '(本会话没有记录)');
  } else {
    console.error('用法: session-title.js set|show --session <sid> ["目标名"]');
    process.exit(1);
  }
}
