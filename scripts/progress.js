#!/usr/bin/env node
// 翼德 · extraction 彩蛋引擎(模型在事件点调用,全部读 ~/.yide/.meta/extraction-fun.json,可调可关)。
//   bump ["功能名"]  完成一个小功能:鼓励语(加权)+ 概率放歌 + 连斩++ + 成就检查
//   win              测试全绿/构建过:今日首胜 + 打卡链 + 连斩++ + 成就检查
//   fail             出错/测试红:连斩归零(温和,不羞辱)
//   achieve <id>     模型触发的成就(shoubu 取上将首级 / cuzhong 粗中有细)
//   stats            战绩面板(/yide 战绩 用)
// 状态:~/.yide/.meta/game-state.json。Date/Math.random 在真 Node 进程可用。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, openUrl, today } = require(path.join(__dirname, 'lib.js'));

const stateFile = path.join(brainDir(), '.meta', 'game-state.json');
const cfgFile = path.join(brainDir(), '.meta', 'extraction-fun.json');
const DEF_CFG = { music: { url: 'https://www.bilibili.com/video/BV1kpwszhEDh/', rate: 0.15 },
  completion: [{ text: '张荣张誉!', weight: 3 }, { text: '谁插彩鸭当空舞?', weight: 2 }, { text: '我靠牛逼啊!', weight: 2 }],
  combo: { thresholds: { '3': '三连斩!', '5': '五连斩,燕人咆哮!', '10': '十连斩!万军辟易!' } },
  achievements: [] };

function loadCfg() { try { return Object.assign({}, DEF_CFG, JSON.parse(fs.readFileSync(cfgFile, 'utf8'))); } catch { return DEF_CFG; } }
function load() { try { return JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch { return {}; } }
function save(s) { try { fs.mkdirSync(path.dirname(stateFile), { recursive: true }); fs.writeFileSync(stateFile, JSON.stringify(s, null, 2)); } catch {} }
function pick(arr) { const t = arr.reduce((a, x) => a + (x.weight || 1), 0); let r = Math.random() * t; for (const x of arr) { r -= (x.weight || 1); if (r <= 0) return x.text; } return arr[arr.length - 1].text; }
function yesterday(d) { const p = d.split('-').map(Number); const dt = new Date(p[0], p[1] - 1, p[2] - 1); const z = n => String(n).padStart(2, '0'); return `${dt.getFullYear()}-${z(dt.getMonth() + 1)}-${z(dt.getDate())}`; }

function init() {
  let s = load();
  s.total = s.total || 0; s.combo = s.combo || 0; s.bestCombo = s.bestCombo || 0;
  s.achievements = s.achievements || {};
  s.streak = s.streak || { lastWinDate: '', days: 0 };
  const day = today();
  if (s.date !== day) { s.date = day; s.count = 0; s.plays = 0; s.winToday = false; }
  return s;
}
// 检查并返回本次新解锁的成就标题
function checkAchievements(s, cfg) {
  const out = [];
  for (const a of (cfg.achievements || [])) {
    if (s.achievements[a.id]) continue;
    let ok = false;
    if (a.type === 'total') ok = s.total >= (a.n || 1);
    else if (a.type === 'streak') ok = (s.streak.days || 0) >= (a.n || 1);
    // flag 类由 achieve 命令单独解锁
    if (ok) { s.achievements[a.id] = true; out.push(a.title); }
  }
  return out;
}
function comboLine(cfg, combo) { const t = cfg.combo && cfg.combo.thresholds; return (t && t[String(combo)]) || ''; }

const cmd = process.argv[2] || 'stats';
const arg = process.argv[3] || '';
const cfg = loadCfg();
let s = init();
let msg = '';

if (cmd === 'bump') {
  s.total++; s.count++; s.combo++; if (s.combo > s.bestCombo) s.bestCombo = s.combo;
  msg = pick(cfg.completion); if (arg) msg = `「${arg}」拿下!` + msg;
  msg += `(今日第 ${s.count} 个)`;
  const rate = (cfg.music && typeof cfg.music.rate === 'number') ? cfg.music.rate : 0.15;
  if (Math.random() < rate) { s.plays++; if (openUrl((cfg.music && cfg.music.url) || DEF_CFG.music.url)) msg += ' 🐔⚡'; }
  const cl = comboLine(cfg, s.combo); if (cl) msg += ` —— ${cl}`;
  const un = checkAchievements(s, cfg); if (un.length) msg += `\n🏅 解锁成就:${un.join('、')}`;
  save(s); console.log(msg);
} else if (cmd === 'win') {
  s.combo++; if (s.combo > s.bestCombo) s.bestCombo = s.combo;
  if (!s.winToday) {
    s.winToday = true;
    if (s.streak.lastWinDate === yesterday(today())) s.streak.days++;
    else if (s.streak.lastWinDate !== today()) s.streak.days = 1;
    s.streak.lastWinDate = today();
    msg = `今日首胜!打卡链 ${s.streak.days} 天。`;
  } else msg = '又下一城!';
  const cl = comboLine(cfg, s.combo); if (cl) msg += ` ${cl}`;
  const un = checkAchievements(s, cfg); if (un.length) msg += `\n🏅 解锁成就:${un.join('、')}`;
  save(s); console.log(msg);
} else if (cmd === 'fail') {
  s.combo = 0; save(s); console.log('连斩断了——无妨,明日再战!');
} else if (cmd === 'achieve') {
  const a = (cfg.achievements || []).find(x => x.id === arg);
  if (a && !s.achievements[a.id]) { s.achievements[a.id] = true; save(s); console.log(`🏅 解锁成就:${a.title}`); }
  else console.log('(已解锁或无此成就)');
} else { // stats —— 战绩面板
  const titles = (cfg.achievements || []).filter(a => s.achievements[a.id]).map(a => a.title);
  console.log(
    `🗡️ 翼德战绩\n` +
    `今日完成:${s.count || 0} 个 · 累计:${s.total || 0}\n` +
    `当前连斩:${s.combo || 0} · 最高连斩:${s.bestCombo || 0}\n` +
    `打卡链:${(s.streak && s.streak.days) || 0} 天\n` +
    `今日放歌:${s.plays || 0} 次\n` +
    `已解锁称号(${titles.length}):${titles.join('、') || '暂无,速去斩将!'}`
  );
}
