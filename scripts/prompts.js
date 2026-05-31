#!/usr/bin/env node
// 翼德 · prompt 库 CLI。
//   index           重建索引(写完/改完条目后调)
//   list            列出库里所有 prompt
//   use <slug>      用过一次 → uses+1(召回被采纳时调)
//   stats           概览
'use strict';
const fs = require('fs');
const path = require('path');
const { buildIndex, getIndex, scan, dir } = require(path.join(__dirname, 'prompts-lib.js'));

const cmd = process.argv[2] || 'list';
const arg = process.argv[3] || '';

if (cmd === 'index') {
  const l = buildIndex(); console.log(`OK\t已重建 prompt 索引,共 ${l.length} 条。`);
} else if (cmd === 'list') {
  const l = getIndex();
  if (!l.length) console.log('prompt 库还是空的。');
  else l.forEach(e => console.log(`- ${e.name}(${e.slug})[用过 ${e.uses || 0} 次] — ${e.when || ''}`));
} else if (cmd === 'use') {
  // uses+1:就地改条目 frontmatter
  const fp = path.join(dir(), arg.endsWith('.md') ? arg : arg + '.md');
  try {
    let raw = fs.readFileSync(fp, 'utf8');
    raw = /uses:\s*\d+/.test(raw) ? raw.replace(/uses:\s*(\d+)/, (m, n) => `uses: ${+n + 1}`) : raw.replace(/^---\n/, `---\nuses: 1\n`);
    fs.writeFileSync(fp, raw); buildIndex();
    console.log(`OK\t${arg} uses+1`);
  } catch (e) { console.log(`ERROR\t${e && e.message}`); }
} else {
  const l = scan();
  console.log(`prompt 库:${l.length} 条 · 累计被采纳 ${l.reduce((a, e) => a + (e.uses || 0), 0)} 次`);
}
