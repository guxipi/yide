#!/usr/bin/env node
// 翼德 · extraction 每日进度 + 可配置彩蛋。完成一个小功能时调:
//   node progress.js bump ["功能名"]
// 行为由 ~/.yide/.meta/extraction-fun.json 驱动(勾哥可调爆率):
//   - 每次完成:按 completion[] 的 weight 加权抽一条鼓励的话打印;
//   - 以 music.rate 的概率在浏览器放雷霆小鸡(默认已调低)。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, openUrl, today } = require(path.join(__dirname, 'lib.js'));

const stateFile = path.join(brainDir(), '.meta', 'daily-progress.json');
const cfgFile = path.join(brainDir(), '.meta', 'extraction-fun.json');

const DEFAULT_CFG = {
  music: { url: 'https://www.bilibili.com/video/BV1kpwszhEDh/', rate: 0.15 },
  completion: [
    { text: '张荣张誉!', weight: 3 },
    { text: '谁插彩鸭当空舞?', weight: 2 },
    { text: '我靠牛逼啊!', weight: 2 },
  ],
};
function loadCfg() {
  try {
    const c = JSON.parse(fs.readFileSync(cfgFile, 'utf8'));
    if (!c.music) c.music = DEFAULT_CFG.music;
    if (!Array.isArray(c.completion) || !c.completion.length) c.completion = DEFAULT_CFG.completion;
    return c;
  } catch { return DEFAULT_CFG; }
}
function weightedPick(arr) {
  const total = arr.reduce((s, x) => s + (x.weight || 1), 0);
  let r = Math.random() * total;
  for (const x of arr) { r -= (x.weight || 1); if (r <= 0) return x.text; }
  return arr[arr.length - 1].text;
}
function load() { try { return JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch { return {}; } }
function save(s) { try { fs.mkdirSync(path.dirname(stateFile), { recursive: true }); fs.writeFileSync(stateFile, JSON.stringify(s, null, 2)); } catch {} }

const cmd = process.argv[2] || 'status';
const desc = process.argv[3] || '';
let s = load();
const day = today();
if (s.date !== day) s = { date: day, count: 0, plays: 0 };

if (cmd === 'bump') {
  const cfg = loadCfg();
  s.count += 1;
  let msg = weightedPick(cfg.completion);
  if (desc) msg = `「${desc}」拿下!` + msg;
  msg += `(今日第 ${s.count} 个)`;
  const rate = (cfg.music && typeof cfg.music.rate === 'number') ? cfg.music.rate : 0.15;
  if (Math.random() < rate) {
    s.plays += 1;
    const ok = openUrl((cfg.music && cfg.music.url) || DEFAULT_CFG.music.url);
    msg += ok ? ' 🐔⚡(雷霆小鸡犒劳你!)' : '';
  }
  save(s);
  console.log(msg);
} else if (cmd === 'reset') {
  save({ date: day, count: 0, plays: 0 });
  console.log('已重置今日进度。');
} else {
  console.log(`今日(${s.date})完成 ${s.count || 0} 个 · 放歌 ${s.plays || 0} 次`);
}
