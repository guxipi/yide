'use strict';
// 翼德 · lessons 读取/匹配 + 编译索引(为长期规模设计)。
// 数据架构:
//   - 源真相:lessons/*.md(人可读、可 diff、可同步)。归档在 lessons/archive/(运行时不扫)。
//   - 编译索引:.meta/lessons-index.json(机器快查)。按 mtime 自愈:源比索引新就重建。
//   - 运行时(hook)只读索引,O(1) 量级;不必每次 glob+解析全部 md。
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function lessonsDir() { return path.join(brainDir(), 'lessons'); }
function indexPath() { return path.join(brainDir(), '.meta', 'lessons-index.json'); }

// glob → 正则(逐字符解析)。支持 **/(任意层目录) ** (任意) *(单层) ?(单字符)。
function globToRe(glob) {
  const g = String(glob).replace(/\\/g, '/');
  let re = '';
  for (let i = 0; i < g.length; i++) {
    const c = g[i];
    if (c === '*') {
      if (g[i + 1] === '*') { i++; if (g[i + 1] === '/') { i++; re += '(?:.*/)?'; } else re += '.*'; }
      else re += '[^/]*';
    } else if (c === '?') re += '.';
    else if ('.+^${}()|[]\\'.includes(c)) re += '\\' + c;
    else re += c;
  }
  try { return new RegExp('(^|/)' + re + '$'); } catch { return null; }
}
function isPathGlob(s) { return /[*/]/.test(s) || /\.\w+$/.test(s); }

function parseLesson(file, raw) {
  const fm = raw.match(/^---\n([\s\S]*?)\n---/);
  let scope = [], severity = 5, status = 'active', id = path.basename(file, '.md'), enforce = 'context';
  if (fm) {
    const f = fm[1];
    const sc = f.match(/scope:\s*\[([^\]]*)\]/);
    if (sc) scope = [...sc[1].matchAll(/"([^"]*)"|'([^']*)'/g)].map(m => m[1] != null ? m[1] : m[2]);
    const sv = f.match(/severity:\s*(\d+)/); if (sv) severity = +sv[1];
    const st = f.match(/status:\s*(\w+)/); if (st) status = st[1];
    const idm = f.match(/id:\s*(\S+)/); if (idm) id = idm[1];
    const en = f.match(/enforce:\s*(\w+)/); if (en) enforce = en[1];
  }
  const body = raw.replace(/^---\n[\s\S]*?\n---\n?/, '');
  const ruleM = body.match(/##\s*规则[^\n]*\n([\s\S]*?)(\n##\s|$)/);
  const ruleText = (ruleM ? ruleM[1] : body).trim().split(/\n/).slice(0, 4).join(' ').trim();
  return { id, file, scope, severity, status, enforce, ruleText };
}

// 直接扫描源 md(不含 archive/)
function scanLessons() {
  const dir = lessonsDir();
  let files = [];
  try { files = fs.readdirSync(dir).filter(n => /^L-.*\.md$/i.test(n)); } catch { return []; }
  const out = [];
  for (const n of files) {
    const fp = path.join(dir, n);
    try { out.push(parseLesson(fp, fs.readFileSync(fp, 'utf8'))); } catch {}
  }
  return out;
}

// 源文件最新 mtime(用于索引自愈判断)
function newestSourceMtime() {
  const dir = lessonsDir();
  let m = 0;
  try {
    for (const n of fs.readdirSync(dir)) {
      if (!/^L-.*\.md$/i.test(n)) continue;
      const st = fs.statSync(path.join(dir, n)); if (st.mtimeMs > m) m = st.mtimeMs;
    }
  } catch {}
  return m;
}

function buildIndex() {
  const list = scanLessons();
  try {
    fs.mkdirSync(path.dirname(indexPath()), { recursive: true });
    fs.writeFileSync(indexPath(), JSON.stringify({ builtAt: Date.now(), lessons: list }, null, 2));
  } catch {}
  return list;
}

// 读取:索引新鲜就用索引,否则重建(自愈)
function getLessons() {
  try {
    const st = fs.statSync(indexPath());
    if (st.mtimeMs >= newestSourceMtime()) {
      const j = JSON.parse(fs.readFileSync(indexPath(), 'utf8'));
      if (j && Array.isArray(j.lessons)) return j.lessons;
    }
  } catch {}
  return buildIndex();
}

function matchByPath(filePath) {
  const fp = String(filePath).replace(/\\/g, '/');
  return getLessons().filter(l => l.status === 'active' && (l.scope || []).some(s => {
    if (!isPathGlob(s)) return false;
    const re = globToRe(s); return re && re.test(fp);
  }));
}

function countActive() { return getLessons().filter(l => l.status === 'active').length; }

module.exports = { getLessons, matchByPath, buildIndex, countActive, globToRe };
