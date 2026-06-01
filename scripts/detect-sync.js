#!/usr/bin/env node
// 翼德 · 探测可用的"同步盘"候选目录 + 在其中查找已有大脑(供 onboard 选位置 / 新设备自动认领)。
// 故意不含 OneDrive。CLI 打印候选;模块导出 candidates() 与 findSyncedBrain()。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

function candidates() {
  const home = os.homedir();
  const list = [];
  const add = (label, p) => { try { if (p && fs.existsSync(p) && fs.statSync(p).isDirectory()) list.push([label, p]); } catch {} };
  add('Google Drive', path.join(home, 'Google Drive'));
  add('Google Drive (My Drive)', path.join(home, 'Google Drive', 'My Drive'));
  add('Google Drive (My Drive)', path.join(home, 'My Drive'));
  if (process.platform === 'darwin') {
    try { const cs = path.join(home, 'Library', 'CloudStorage'); for (const n of fs.readdirSync(cs)) if (/^GoogleDrive-/.test(n)) add('Google Drive', path.join(cs, n, 'My Drive')); } catch {}
  }
  if (process.platform === 'win32') for (const d of ['G:', 'H:', 'I:', 'J:']) add('Google Drive (' + d + ')', path.join(d + '\\', 'My Drive'));
  add('Dropbox', path.join(home, 'Dropbox'));
  if (process.platform === 'darwin') add('iCloud Drive', path.join(home, 'Library', 'Mobile Documents', 'com~apple~CloudDocs'));
  // 去重
  const seen = new Set(); return list.filter(([, p]) => (seen.has(p) ? false : seen.add(p)));
}

// 在候选同步盘里找一个"已有大脑"(含 INDEX.md 的 yide-brain/.yide 文件夹)。返回路径或 null。
function findSyncedBrain() {
  for (const [, root] of candidates()) {
    for (const name of ['yide-brain', '.yide', 'yide']) {
      const p = path.join(root, name);
      try { if (fs.existsSync(path.join(p, 'INDEX.md'))) return p; } catch {}
    }
  }
  return null;
}

module.exports = { candidates, findSyncedBrain };

if (require.main === module) {
  const c = candidates();
  if (!c.length) process.stdout.write('NONE\t未发现同步盘候选;可用本地默认或手动粘贴路径。\n');
  else for (const [label, p] of c) process.stdout.write(label + '\t' + p + '\n');
  const b = findSyncedBrain();
  if (b) process.stdout.write('BRAIN\t' + b + '\t(同步盘里已发现大脑)\n');
}
