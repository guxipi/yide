'use strict';
// 翼德 · extraction 个人项目专属上下文(奖励 + 督促 + 张飞人格 + 彩蛋)。
// 从 session-start.js 拆出(它是开场注入里最大、最易变、最自成一体的一块)。
// 仅当项目路径含 "extraction" 且未在 extraction-fun.json 里关闭时,返回一段要追加进开场上下文的文本;否则返回 ''。
// 副作用:写本机私有 greet-state.json(~/.yide-local,开场问候 / 深夜守护各每天一次,state 门控不刷屏)。
//   本机私有 → 不进同步盘(否则多机同天各写各的会 conflicted copy);与 progress.js 的 game-state.json(耐久战绩,留共享)也各写各的。仅 Node 内置模块。
const fs = require('fs');
const path = require('path');
const { today } = require(path.join(__dirname, 'lib.js'));
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));

function extractionContext(BRAIN, PROJECT, PLUGIN_ROOT) {
  let fun = {};
  try { fun = JSON.parse(fs.readFileSync(path.join(BRAIN, '.meta', 'extraction-fun.json'), 'utf8')); } catch {}
  if (!/extraction/i.test(PROJECT) || fun.enabled === false) return '';

  const progressJs = path.join(PLUGIN_ROOT, 'scripts', 'progress.js');
  const musicPct = Math.round(((fun.music && fun.music.rate) || 0.15) * 100);
  const musicN = (fun.music && Array.isArray(fun.music.tracks) && fun.music.tracks.length) || 1;
  const sit = Array.isArray(fun.situational) ? fun.situational : [];
  const sitLines = sit.length
    ? sit.map(q => `  - ${q.when}(约 ${Math.round((q.rate || 0.3) * 100)}%):"${q.text}"`).join('\n')
    : '  -(无,见 .meta/extraction-fun.json)';

  // 开场问候 / 深夜守护:确定性、每天/每夜各一次(state 门控,不刷屏)
  const day = today();
  const hour = new Date().getHours();
  let gs = readLocalJson('greet-state.json', {}) || {};  // 本机私有:开场/守护每天一次的门控,不进同步盘
  let egg = '', dirty = false;
  if ((!fun.greeting || fun.greeting.enabled !== false) && gs.lastGreetDate !== day) {
    const g = hour < 6 ? '夜深了,勾哥还在肝?' : hour < 12 ? '早,勾哥!' : hour < 18 ? '勾哥,下午好!' : '勾哥,晚上好!';
    egg += `🗡️ ${g} 燕人张翼德在此,今日与你并肩斩将!\n`;
    gs.lastGreetDate = day; dirty = true;
  }
  const ng = fun.nightGuard || {};
  if (ng.enabled !== false && hour >= (ng.afterHour != null ? ng.afterHour : 1) && hour < 6 && gs.lastNightGuard !== day) {
    egg += `🌙 勾哥,身体是革命的本钱,张飞劝你早些收兵歇息。\n`;
    gs.lastNightGuard = day; dirty = true;
  }
  if (dirty) writeLocalJson('greet-state.json', gs, true);

  // ER 专属常驻(制作人/主程 mindset、收尾铁律、MCP SAVE)—— 从 charter-extra 迁出,只在 ER 会话注入(别打进别的项目)
  let erCharter = '';
  try { erCharter = fs.readFileSync(path.join(BRAIN, 'core', 'charter-extra-er.md'), 'utf8').replace(/^<!--[\s\S]*?-->\s*/, '').trim(); } catch {}

  return `\n---\n## 🎮 extraction 项目专属\n` +
    (egg ? `(开场问候:第一条回复开头带一句即可,不单独占一轮)\n${egg}\n` : '') +
    (erCharter ? `${erCharter}\n\n` : '') +
    `### 🐯 张飞人格(仅此个人放松项目)\n` +
    `你叫翼德,正是张翼德。可偶尔用张飞的豪爽幽默口吻插科打诨——但**幽默为辅,把事办对才是义气**(张飞粗中有细)。\n` +
    `情境台词(点缀,别整段文言;括号是大致频率,勾哥在配置里可调):\n${sitLines}\n` +
    `- 火候:在"完成/发现 bug/卡住"的节点才冒一句;一段最多一个梗 + 一个感叹号;梗 ≤ 一行,后面紧跟干货。\n` +
    `- 用户说"收工/今天到这" → 来句"收兵!今日辛苦了,勾哥"之类的收尾。\n` +
    `- 关掉彩蛋(说人话):线上事故 / 数据安全 / 严重 bug / 用户在赶时间 / 用户说"正经点"。\n` +
    `- 别自我解说"俺在学张飞"、别强凑文言、同一个梗别连用、别油腻。\n`;
}

module.exports = { extractionContext };
