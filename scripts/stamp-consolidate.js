#!/usr/bin/env node
// 翼德 · 记一个"刚整理过记忆"的时间戳(供 SessionStart 的 24h 到期判断)。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));
const f = path.join(brainDir(), '.meta', 'last-consolidate.txt');
try {
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, String(Date.now()));
  console.log('OK\t已记录整理时间戳:' + f);
} catch (e) { console.log('ERROR\t' + (e && e.message)); }
