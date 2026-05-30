#!/usr/bin/env node
// 翼德 · 每日进度 + 变比率奖励。由模型在完成一个小功能时调用:
//   node progress.js bump ["功能简述"]
// 触发阈值随机(通常 2–6 个),且自上次播放起每满 10 个必触发一次 —— 不确定性让人想多做。
// 触发时:浏览器播放"雷霆小鸡" + 一句鼓励(带今日完成数)。跨天自动归零。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, openUrl, today } = require(path.join(__dirname, 'lib.js'));

const REWARD_URL = 'https://www.bilibili.com/video/BV1kpwszhEDh/';
const GUARANTEE = 10; // 自上次播放起,最多 10 个必播
const stateFile = path.join(brainDir(), '.meta', 'daily-progress.json');

function randInt(a, b) { return a + Math.floor(Math.random() * (b - a + 1)); }
function load() { try { return JSON.parse(fs.readFileSync(stateFile, 'utf8')); } catch { return {}; } }
function save(s) {
  try { fs.mkdirSync(path.dirname(stateFile), { recursive: true }); fs.writeFileSync(stateFile, JSON.stringify(s, null, 2)); } catch {}
}

const PRAISE = [
  n => `🎉 勾哥真是太棒了,今天又完成了 ${n} 个!雷霆小鸡为你奏乐 🐔⚡`,
  n => `🔥 勾哥牛啊!今日第 ${n} 个搞定,这状态谁顶得住!`,
  n => `💪 稳!勾哥今天已收割 ${n} 个小功能,做完最光荣,继续乘胜追击!`,
  n => `🚀 又下一城!勾哥今日 ${n} 个达成,雷霆小鸡专属 BGM 走起 🎵`,
];

const cmd = process.argv[2] || 'status';
const desc = process.argv[3] || '';
let s = load();
const day = today();
if (s.date !== day) s = { date: day, count: 0, sinceLastPlay: 0, nextGap: randInt(2, 6), plays: 0 };
if (typeof s.nextGap !== 'number') s.nextGap = randInt(2, 6);

if (cmd === 'bump') {
  s.count += 1;
  s.sinceLastPlay = (s.sinceLastPlay || 0) + 1;
  const hit = s.sinceLastPlay >= s.nextGap || s.sinceLastPlay >= GUARANTEE;
  if (hit) {
    s.plays += 1; s.sinceLastPlay = 0; s.nextGap = randInt(2, 6);
    const ok = openUrl(REWARD_URL);
    let msg = PRAISE[randInt(0, PRAISE.length - 1)](s.count);
    if (desc) msg = `「${desc}」拿下!` + msg;
    if (!ok) msg += `(浏览器没自动开,手动听:${REWARD_URL})`;
    save(s);
    console.log(msg);
  } else {
    save(s);
    console.log(`🗡️ 今日 ${s.count} 个。做完 > 做大,别盲目扩 scale。再完成几个说不定就有惊喜 🎵`);
  }
} else if (cmd === 'reset') {
  save({ date: day, count: 0, sinceLastPlay: 0, nextGap: randInt(2, 6), plays: 0 });
  console.log('已重置今日进度。');
} else {
  console.log(`今日(${s.date})完成 ${s.count || 0} 个 · 已奖励 ${s.plays || 0} 次`);
}
