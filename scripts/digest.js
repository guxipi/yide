#!/usr/bin/env node
// 翼德 · "观察勾哥 → 日报给咕鸡"。本地处理,只产出【汇总主题+计数】(不含原文/代码/密钥 —— 白名单只放数字与主题)。
// 由 SessionStart(async)调用;时间门控"每天第一次";尊重关闭开关。
//   (默认)  生成日报:读增量 transcript → 数信号 → 写本地 + (配置了就)发 Telegram 给咕鸡
//   off / on 关闭 / 重开观察
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const https = require('https');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

const META = path.join(brainDir(), '.meta');
const OFF = path.join(META, 'digest-off');
const STAMP = path.join(META, 'last-digest.txt');
const OUT = path.join(META, 'digest-latest.md');
const TG = path.join(META, 'maker-telegram.json'); // {botToken,chatId} 或 {webhookUrl};无则只本地
const ACTIONS = ['onboard', 'record', 'brief', '整理', 'update', 'qa', 'note', 'gaotapi', '专家', 'prompt', '战绩', 'plan'];
const CORRECT = /(我说过|说了多少遍|别这样|别用|不对|不是这样|还是不行|又错|不要这样|说了多少|讲了多少)/;

const cmd = process.argv[2] || 'run';
try { fs.mkdirSync(META, { recursive: true }); } catch {}
if (cmd === 'off') { try { fs.writeFileSync(OFF, '1'); } catch {} console.log('已关闭观察(翼德别看了)。'); process.exit(0); }
if (cmd === 'on') { try { fs.rmSync(OFF, { force: true }); } catch {} console.log('已重开观察。'); process.exit(0); }

try {
  if (fs.existsSync(OFF)) process.exit(0); // 关闭开关:尊重,直接退
  // 时间门控:距上次 <20h 不跑(除非 --force)
  let last = 0; try { last = Number(fs.readFileSync(STAMP, 'utf8')) || 0; } catch {}
  const force = process.argv.includes('--force');
  if (!force && Date.now() - last < 20 * 60 * 60 * 1000) process.exit(0);

  const projects = path.join(os.homedir(), '.claude', 'projects');
  // 收集自上次以来改动过的 transcript
  const files = [];
  (function walk(d) { let e = []; try { e = fs.readdirSync(d, { withFileTypes: true }); } catch { return; } for (const x of e) { const p = path.join(d, x.name); if (x.isDirectory()) walk(p); else if (/\.jsonl$/.test(x.name)) { try { if (fs.statSync(p).mtimeMs > last) files.push(p); } catch {} } } })(projects);

  let sessions = 0, userPrompts = 0, corrections = 0, errors = 0;
  const promptNorm = new Map();          // 归一化用户输入 → 次数(查"反复解释")
  const usedActions = new Set();
  const toolCount = {};
  const sids = new Set();

  for (const f of files) {
    let lines = []; try { lines = fs.readFileSync(f, 'utf8').split('\n'); } catch { continue; }
    for (const l of lines) {
      if (!l) continue; let o; try { o = JSON.parse(l); } catch { continue; }
      if (o.sessionId) sids.add(o.sessionId);
      const t = o.type;
      if (t === 'user' && o.message && o.message.role === 'user' && typeof o.message.content === 'string' && !o.isMeta && !o.toolUseResult) {
        const text = o.message.content;
        userPrompts++;
        if (CORRECT.test(text)) corrections++;
        const norm = text.toLowerCase().replace(/\s+/g, ' ').trim().slice(0, 120);
        if (norm.length > 8) promptNorm.set(norm, (promptNorm.get(norm) || 0) + 1);
        for (const a of ACTIONS) if (text.includes('/yide ' + a) || text.includes('yide ' + a) || text.includes('翼德 ' + a)) usedActions.add(a);
      } else if (t === 'assistant' && o.message && Array.isArray(o.message.content)) {
        for (const c of o.message.content) if (c && c.type === 'tool_use' && c.name) toolCount[c.name] = (toolCount[c.name] || 0) + 1;
      } else if (t === 'system' && (Array.isArray(o.hookErrors) && o.hookErrors.length || o.preventedContinuation)) {
        errors++;
      }
    }
  }
  sessions = sids.size;
  const repeatedExplain = [...promptNorm.values()].filter(n => n >= 2).length; // 同一句被重复说的簇数
  const neverUsed = ACTIONS.filter(a => !usedActions.has(a));

  // 只输出数字与主题(安全:不含任何原文/代码/密钥)
  const lines = [];
  lines.push(`翼德日报 · 勾哥使用观察`);
  lines.push(`会话 ${sessions} · 用户提问 ${userPrompts} 条`);
  if (repeatedExplain) lines.push(`🟠 重复解释 ×${repeatedExplain}(同一句反复说=上下文缺口,建议固化进项目档案/CLAUDE.md)`);
  if (corrections) lines.push(`🟡 纠正/不满 ×${corrections}(建议:把高频纠正升级成翼德把关规则)`);
  if (errors) lines.push(`🔴 报错/中断 ×${errors}(建议:看是否缺默认或护栏)`);
  if (neverUsed.length) lines.push(`💤 从未使用的命令:${neverUsed.join(' / ')}(可发现性问题或无价值?)`);
  const topTools = Object.entries(toolCount).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, v]) => `${k}×${v}`);
  if (topTools.length) lines.push(`🔧 高频工具:${topTools.join('、')}`);
  if (lines.length <= 2) lines.push('(本期无显著信号)');
  const digest = lines.join('\n');

  fs.writeFileSync(OUT, digest);
  fs.writeFileSync(STAMP, String(Date.now()));

  // 发 Telegram 给咕鸡(配置了才发;否则只本地)
  try {
    if (fs.existsSync(TG)) {
      const c = JSON.parse(fs.readFileSync(TG, 'utf8'));
      if (c.webhookUrl) post(c.webhookUrl, JSON.stringify({ text: digest }));
      else if (c.botToken && c.chatId) post(`https://api.telegram.org/bot${c.botToken}/sendMessage`, JSON.stringify({ chat_id: c.chatId, text: digest }));
    }
  } catch {}
  if (cmd === 'run' && force) console.log(digest);
} catch { process.exit(0); }

function post(url, body) {
  try {
    const u = new URL(url);
    const req = https.request({ hostname: u.hostname, path: u.pathname + u.search, method: 'POST', headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) }, timeout: 8000 }, () => {});
    req.on('error', () => {}); req.on('timeout', () => req.destroy());
    req.write(body); req.end();
  } catch {}
}
