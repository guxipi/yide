'use strict';
// 翼德 · prompt 库:解析条目 + 编译索引 + 按文本匹配(供 UserPromptSubmit hook 快速召回)。
// 条目 = ~/.yide/prompts/<slug>.md(frontmatter + 正文)。索引 = prompts/index.json(mtime 自愈)。
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function dir() { return path.join(brainDir(), 'prompts'); }
function indexPath() { return path.join(dir(), 'index.json'); }

function parse(file, raw) {
  const fm = raw.match(/^---\n([\s\S]*?)\n---/);
  const e = { slug: path.basename(file, '.md'), name: '', when: '', tags: [], keywords: [], globs: [], uses: 0, suggests: 0 };
  if (fm) {
    const f = fm[1];
    const s = (k) => { const m = f.match(new RegExp('^' + k + ':\\s*(.+)$', 'm')); return m ? m[1].trim().replace(/^["\']|["\']$/g, '') : ''; };
    const arr = (k) => { const m = f.match(new RegExp(k + ':\\s*\\[([^\\]]*)\\]')); return m ? m[1].split(',').map(x => x.trim().replace(/^["\']|["\']$/g, '')).filter(Boolean) : []; };
    e.name = s('name') || e.slug;
    e.when = s('description') || s('when_to_use');
    e.tags = arr('tags'); e.keywords = arr('keywords'); e.globs = arr('globs');
    const u = f.match(/uses:\s*(\d+)/); if (u) e.uses = +u[1];
    const sg = f.match(/suggests:\s*(\d+)/); if (sg) e.suggests = +sg[1];
  }
  return e;
}

function scan() {
  let files = [];
  try { files = fs.readdirSync(dir()).filter(n => /\.md$/i.test(n) && n !== 'README.md'); } catch { return []; }
  const out = [];
  for (const n of files) { try { out.push(parse(n, fs.readFileSync(path.join(dir(), n), 'utf8'))); } catch {} }
  return out;
}
function newestMtime() {
  let m = 0; try { for (const n of fs.readdirSync(dir())) { if (!/\.md$/i.test(n)) continue; const st = fs.statSync(path.join(dir(), n)); if (st.mtimeMs > m) m = st.mtimeMs; } } catch {} return m;
}
function buildIndex() {
  const list = scan();
  try { fs.mkdirSync(dir(), { recursive: true }); fs.writeFileSync(indexPath(), JSON.stringify({ builtAt: Date.now(), prompts: list }, null, 2)); } catch {}
  return list;
}
function getIndex() {
  try { const st = fs.statSync(indexPath()); if (st.mtimeMs >= newestMtime()) { const j = JSON.parse(fs.readFileSync(indexPath(), 'utf8')); if (j && Array.isArray(j.prompts)) return j.prompts; } } catch {}
  return buildIndex();
}

// 子串匹配(适配中文,无需分词):统计 keywords/tags/name 在文本中的命中数
function matchByText(text) {
  const t = String(text || '').toLowerCase();
  if (!t) return null;
  let best = null;
  for (const e of getIndex()) {
    let score = 0;
    for (const k of [...(e.keywords || []), ...(e.tags || [])]) {
      if (k && t.includes(String(k).toLowerCase())) score++;
    }
    if (e.name && t.includes(String(e.name).toLowerCase())) score++;
    if (score > 0 && (!best || score > best.score || (score === best.score && (e.uses || 0) > (best.entry.uses || 0)))) {
      best = { entry: e, score };
    }
  }
  return best;
}

module.exports = { scan, buildIndex, getIndex, matchByText, indexPath, dir };
