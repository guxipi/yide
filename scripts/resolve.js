'use strict';
// 翼德 · 分层 resolver(唯一懂"发货层 vs 用户层"的地方)。
// 发货默认读自插件(templates/brain),用户层读自 ~/.yide,**在"读取时"合并**,不写盘、不拆旧大脑。
// 消费方只调 resolve(key, pluginRoot, brainDir) 拿合并好的结果。新增分层资源 = 给 MANIFEST 加一行。
// 合并靠去重/override/suppress:旧大脑里那份混合文件直接当用户层叠加,重复的按 key 塌缩。
// 静默更新的根:咕鸡在新版插件加/改默认 → 这里现读现合自动生效,~/.yide 一个字都不用动 → 零冲突。仅 Node 内置模块。
const fs = require('fs');
const path = require('path');

const MANIFEST = {
  // 红线:发货默认 + 用户自定义,按 (防XXX) tag 去重;用户同 tag = 改写(override),可在 redline-suppress.json 禁用某默认
  'hard-rules': { strategy: 'rules', shipped: 'core/hard-rules.md', user: 'core/hard-rules.md', suppress: 'redline-suppress.json' },
  // 工作准则:发货为主 + 可选用户补充(core/charter-extra.md)
  'charter': { strategy: 'append', shipped: 'core/charter.md', userExtra: 'core/charter-extra.md' },
};

function rd(p) { try { return fs.readFileSync(p, 'utf8'); } catch { return ''; } }
function shipped(pluginRoot, rel) { return path.join(pluginRoot, 'templates', 'brain', rel); }

// 把红线 md 解析成 [{key,line}]:默认以 (防XXX) 结尾作稳定 key;无 tag 的自定义用整行当 key
function parseRules(text) {
  const out = [];
  for (const raw of String(text || '').split('\n')) {
    if (!/^\s*\d+\.\s/.test(raw) || !/IMPORTANT/.test(raw)) continue;
    const m = raw.match(/\((防[^)）]+)\)/);
    out.push({ key: m ? m[1] : raw.trim(), line: raw.trim() });
  }
  return out;
}

function resolveRules(m, pluginRoot, brainDir) {
  const shippedRules = parseRules(rd(shipped(pluginRoot, m.shipped)));
  const userRules = parseRules(rd(path.join(brainDir, m.user)));
  let suppressed = [];
  try { const s = JSON.parse(rd(path.join(brainDir, '.meta', m.suppress))); if (Array.isArray(s)) suppressed = s; } catch {}
  const sup = new Set(suppressed);
  const userMap = new Map(userRules.map(r => [r.key, r.line]));
  const seen = new Set();
  const lines = [];
  for (const r of shippedRules) {                 // 发货默认:被禁用→跳;用户改写过同 tag→用他的;否则用默认
    seen.add(r.key);
    if (sup.has(r.key)) continue;
    lines.push(userMap.has(r.key) ? userMap.get(r.key) : r.line);
  }
  for (const r of userRules) {                     // 用户自定义(无对应默认)
    if (seen.has(r.key) || sup.has(r.key)) continue;
    seen.add(r.key);
    lines.push(r.line);
  }
  let n = 0;
  return lines.map(l => l.replace(/^\s*\d+\.\s*/, () => `${++n}. `)).join('\n\n');
}

function resolveAppend(m, pluginRoot, brainDir) {
  const base = rd(shipped(pluginRoot, m.shipped)).trim();
  const extra = m.userExtra ? rd(path.join(brainDir, m.userExtra)).trim() : '';
  return extra ? base + '\n\n---\n## 你的补充\n' + extra : base;
}

function resolve(key, pluginRoot, brainDir) {
  const m = MANIFEST[key];
  if (!m) return '';
  if (m.strategy === 'rules') return resolveRules(m, pluginRoot, brainDir);
  if (m.strategy === 'append') return resolveAppend(m, pluginRoot, brainDir);
  return '';
}

module.exports = { resolve, MANIFEST };
