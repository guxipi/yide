#!/usr/bin/env node
// 翼德 · 同步盘冲突副本巡检。大脑放在 Google Drive / Dropbox 同步盘,多机同天写同一文件会留下
// "conflicted copy / 的冲突副本 / name (1).ext" 之类的副本 —— 静默堆积会污染大脑。
// consolidate 时列出让勾哥裁决;doctor 也复用。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

// 命中即疑似同步盘冲突副本(文件名层面):Drive 英文/中文冲突副本、Drive 数字去重 name (1).ext。
const CONFLICT_RE = [
  /conflicted copy/i,
  /冲突副本/,
  /\bconflict\b/i,
  / \(\d+\)(\.[^.\\/]+)?$/,   // "note (1).md" / "note (2)"
];

function isConflictName(name) { return CONFLICT_RE.some(re => re.test(name)); }

// 递归扫描 dir,返回疑似冲突副本的绝对路径清单。跳过 .git / archive(归档区不算活跃污染)。
function findConflicts(dir) {
  const hits = [];
  const SKIP = new Set(['.git', 'node_modules', 'archive', 'shipped-base']);
  function walk(d) {
    let ents = [];
    try { ents = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of ents) {
      if (e.isDirectory()) {
        if (SKIP.has(e.name)) continue;
        walk(path.join(d, e.name));
      } else if (isConflictName(e.name)) {
        hits.push(path.join(d, e.name));
      }
    }
  }
  try { if (fs.existsSync(dir)) walk(dir); } catch {}
  return hits;
}

module.exports = { findConflicts, isConflictName };

if (require.main === module) {
  const dir = process.argv[2] || brainDir();
  const hits = findConflicts(dir);
  if (!hits.length) { process.stdout.write('CLEAN\t未发现同步盘冲突副本。\n'); }
  else { process.stdout.write(`CONFLICTS\t${hits.length}\t发现疑似同步盘冲突副本,请裁决(留哪份/删哪份):\n`); for (const h of hits) process.stdout.write('  - ' + h + '\n'); }
}
