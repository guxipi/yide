#!/usr/bin/env node
// 翼德 · 探测可用的"同步盘"候选目录,供 onboard 用选择题让用户挑(无需命令行)。
// 故意不含 OneDrive。输出每行一个存在的候选:`<标签>\t<绝对路径>`。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const home = os.homedir();
const candidates = [];
function add(label, p) { try { if (p && fs.existsSync(p) && fs.statSync(p).isDirectory()) candidates.push([label, p]); } catch {} }

// Google Drive(桌面版常见位置)
add('Google Drive', path.join(home, 'Google Drive'));
add('Google Drive (My Drive)', path.join(home, 'Google Drive', 'My Drive'));
add('Google Drive (My Drive)', path.join(home, 'My Drive'));
if (process.platform === 'darwin') {
  // macOS:~/Library/CloudStorage/GoogleDrive-xxx/My Drive
  try {
    const cs = path.join(home, 'Library', 'CloudStorage');
    for (const n of fs.readdirSync(cs)) {
      if (/^GoogleDrive-/.test(n)) add('Google Drive', path.join(cs, n, 'My Drive'));
    }
  } catch {}
}
if (process.platform === 'win32') {
  // Windows:Google Drive 常映射为某盘符的 \My Drive
  for (const d of ['G:', 'H:', 'I:', 'J:']) add('Google Drive (' + d + ')', path.join(d + '\\', 'My Drive'));
}
// Dropbox / iCloud(也可作同步盘)
add('Dropbox', path.join(home, 'Dropbox'));
if (process.platform === 'darwin') add('iCloud Drive', path.join(home, 'Library', 'Mobile Documents', 'com~apple~CloudDocs'));

// 去重
const seen = new Set();
for (const [label, p] of candidates) {
  if (seen.has(p)) continue; seen.add(p);
  process.stdout.write(label + '\t' + p + '\n');
}
if (!seen.size) process.stdout.write('NONE\t未发现同步盘候选;可用本地默认或手动粘贴路径。\n');
