'use strict';
// 翼德 · lessons 读取/匹配 + 编译索引(为长期规模设计)。
// 数据架构:
//   - 源真相:lessons/*.md(人可读、可 diff、可同步)。归档在 lessons/archive/(运行时不扫)。
//   - 编译索引:.meta/lessons-index.json(机器快查)。按 mtime 自愈:源比索引新就重建。
//   - 运行时(hook)只读索引,O(1) 量级;不必每次 glob+解析全部 md。
//   - 索引机械(scan/newestMtime/buildIndex/getIndex)抽到 index-util.js,与 prompts 共用。
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));
const { makeIndex } = require(path.join(__dirname, 'index-util.js'));

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

// 索引:源真相 = lessons/L-*.md(不含 archive/);编译缓存 = .meta/lessons-index.json
const idx = makeIndex({
  sourceDir: lessonsDir,
  indexPath,
  fileFilter: n => /^L-.*\.md$/i.test(n),
  parse: parseLesson,
  key: 'lessons',
});
function buildIndex() { return idx.buildIndex(); }
function getLessons() { return idx.getIndex(); }

function matchByPath(filePath) {
  const fp = String(filePath).replace(/\\/g, '/');
  return getLessons().filter(l => l.status === 'active' && (l.scope || []).some(s => {
    if (!isPathGlob(s)) return false;
    const re = globToRe(s); return re && re.test(fp);
  }));
}

function countActive() { return getLessons().filter(l => l.status === 'active').length; }

module.exports = { getLessons, matchByPath, buildIndex, countActive, globToRe };
