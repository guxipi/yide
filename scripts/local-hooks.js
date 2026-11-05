#!/usr/bin/env node
// 翼德 · 本机附加脚本(local hooks)。
//
// 让某一台机器在翼德已有的 SessionStart / Stop hook 上顺带跑自己的脚本,不改 Claude Code 的 settings,
// 也不影响别的机器。配置是本机私有文件 ~/.yide-local/local-hooks.json(不同步、不进仓库),形如:
//   { "SessionStart": [{ "node": "<脚本绝对路径>", "args": [] }],
//     "Stop":         [{ "node": "<脚本绝对路径>" }] }
// 没有这个文件 = 什么都不跑。每条都用 node 分离到后台(detached + unref),翼德 hook 立刻继续,
// 不等结果、不读输出;脚本不存在就跳过;任何异常都吞掉,绝不影响翼德本身的简报 / 审计。
// (lib.js 的 openUrl 也是 detached,但那是开网址用的,不通用。)
// 第一个用户:DuckCenter 的 ER 记忆清单生成器(勾哥 11-05「挂进 yide 插件自己的 hook」)。
'use strict';
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { readLocalJson } = require(path.join(__dirname, 'store.js'));

function entries(event) {
  const cfg = readLocalJson('local-hooks.json', {});
  const list = cfg && Array.isArray(cfg[event]) ? cfg[event] : [];
  return list.filter(e => e && typeof e.node === 'string' && e.node);
}

// 返回实际拉起的条数(测试用)
function fire(event) {
  let n = 0;
  try {
    for (const e of entries(event)) {
      try {
        if (!fs.existsSync(e.node)) continue;
        const args = Array.isArray(e.args) ? e.args.map(String) : [];
        const child = spawn(process.execPath, [e.node, ...args], { detached: true, stdio: 'ignore', windowsHide: true });
        child.on('error', () => {});
        child.unref();
        n++;
      } catch {}
    }
  } catch {}
  return n;
}

module.exports = { fire, entries };
