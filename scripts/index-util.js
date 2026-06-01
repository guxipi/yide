'use strict';
// 翼德 · 通用"mtime 自愈"索引(lessons.js / prompts-lib.js 共用,去掉两份重复机械)。
// 一个目录下的 .md 源文件 → 编译成机器快查的 JSON 索引;源比索引新就重建,否则直接读索引(O(1) 量级)。
// 数据架构理由见 lessons.js 顶部注释:源真相是人可读、可 diff、可同步的 md;索引只是派生缓存。
const fs = require('fs');
const path = require('path');

// opts:
//   sourceDir() -> 源 md 所在目录(函数,惰性求值,适配运行时 brainDir 变化)
//   indexPath() -> 编译索引 JSON 路径(函数)
//   fileFilter(name) -> 是否纳入索引的文件
//   parse(filePath, raw) -> 一条索引记录
//   key -> 索引 JSON 里数组字段名(如 'lessons' / 'prompts')
function makeIndex(opts) {
  const { sourceDir, indexPath, fileFilter, parse, key } = opts;

  function listFiles() {
    try { return fs.readdirSync(sourceDir()).filter(fileFilter); } catch { return []; }
  }
  function scan() {
    const out = [];
    for (const n of listFiles()) {
      const fp = path.join(sourceDir(), n);
      try { out.push(parse(fp, fs.readFileSync(fp, 'utf8'))); } catch {}
    }
    return out;
  }
  // 源文件最新 mtime(只看纳入索引的文件,用于自愈判断)
  function newestMtime() {
    let m = 0;
    for (const n of listFiles()) {
      try { const st = fs.statSync(path.join(sourceDir(), n)); if (st.mtimeMs > m) m = st.mtimeMs; } catch {}
    }
    return m;
  }
  function buildIndex() {
    const list = scan();
    try {
      fs.mkdirSync(path.dirname(indexPath()), { recursive: true });
      fs.writeFileSync(indexPath(), JSON.stringify({ builtAt: Date.now(), [key]: list }, null, 2));
    } catch {}
    return list;
  }
  // 索引新鲜就用索引,否则重建(自愈)
  function getIndex() {
    try {
      const st = fs.statSync(indexPath());
      if (st.mtimeMs >= newestMtime()) {
        const j = JSON.parse(fs.readFileSync(indexPath(), 'utf8'));
        if (j && Array.isArray(j[key])) return j[key];
      }
    } catch {}
    return buildIndex();
  }
  return { scan, newestMtime, buildIndex, getIndex };
}

module.exports = { makeIndex };
