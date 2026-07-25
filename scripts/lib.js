'use strict';
// 翼德 · 公共工具:大脑路径、跨平台开浏览器、今日日期。
const os = require('os');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

// 大脑位置解析(让用户无需命令行/环境变量也能放到同步盘):
//   1) 环境变量 YIDE_HOME(高级用户)
//   2) 指针文件 ~/.yide-location(内含一行路径;由 onboard 用选择题帮用户写入)
//   3) 默认 ~/.yide
function locationPointerPath() { return path.join(os.homedir(), '.yide-location'); }
function brainDir() {
  if (process.env.YIDE_HOME) return process.env.YIDE_HOME;
  try {
    const loc = fs.readFileSync(locationPointerPath(), 'utf8').trim();
    if (loc) return loc;
  } catch {}
  return path.join(os.homedir(), '.yide');
}

// 跨平台在默认浏览器打开 URL(Windows / macOS / Linux)
// 设环境变量 YIDE_NO_OPEN=1 可静音(测试或不想被打扰时)。
function openUrl(url) {
  if (process.env.YIDE_NO_OPEN) return false;
  let command, args, opts = { stdio: 'ignore', detached: true };
  if (process.platform === 'darwin') { command = 'open'; args = [url]; }
  else if (process.platform === 'win32') {
    // cmd 的 start:第一个引号串会被当成窗口标题,故必须有空 "" 占位
    command = 'cmd'; args = ['/c', 'start', '""', url];
    opts.windowsVerbatimArguments = true;
  } else { command = 'xdg-open'; args = [url]; }
  try {
    const c = spawn(command, args, opts);
    c.on('error', () => {});
    c.unref();
    return true;
  } catch { return false; }
}

function today() {
  // 真 Node 进程,Date 可用;取本地日期 YYYY-MM-DD
  const d = new Date();
  const p = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

// glob → 正则(逐字符解析)。支持 **/(任意层目录) ** (任意) *(单层) ?(单字符)。
// 原属 lessons.js(教训 scope 匹配);2026-07-25 教训自动浮现退役后,只剩把关器的 suppressed 规则在用,故迁到公共层。
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

module.exports = { brainDir, openUrl, today, locationPointerPath, globToRe };
