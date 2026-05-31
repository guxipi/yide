#!/usr/bin/env node
// 翼德 · 把大脑里可移植的专家副本(~/.yide/experts/*.md)同步进 ~/.claude/agents/,
// 让蒸馏出的专家在"换了电脑、大脑随同步盘过来"后仍能直接召唤(subagent 不随大脑同步,这里补齐)。
// 幂等:仅当目标缺失或源更新时才覆盖。被 SessionStart 以函数方式调用(不打印,避免污染 hook stdout)。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function syncExperts() {
  try {
    const src = path.join(brainDir(), 'experts');
    const dst = path.join(os.homedir(), '.claude', 'agents');
    let files = [];
    try { files = fs.readdirSync(src).filter(n => /\.md$/i.test(n) && n !== 'README.md' && n !== 'index.md'); } catch { return 0; }
    if (!files.length) return 0;
    fs.mkdirSync(dst, { recursive: true });
    let n = 0;
    for (const f of files) {
      const s = path.join(src, f), d = path.join(dst, f);
      let copy = true;
      try { if (fs.existsSync(d) && fs.statSync(d).mtimeMs >= fs.statSync(s).mtimeMs) copy = false; } catch {}
      if (copy) { try { fs.copyFileSync(s, d); n++; } catch {} }
    }
    return n;
  } catch { return 0; }
}

module.exports = { syncExperts };
if (require.main === module) { const n = syncExperts(); if (n) console.log(`synced ${n} expert(s) → ~/.claude/agents/`); }
