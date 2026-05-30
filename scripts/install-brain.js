#!/usr/bin/env node
// 翼德 · 跨平台建大脑(替代 cp -R / ls,Windows 也能跑)。
//   node install-brain.js                  → 在默认/指针位置建大脑
//   node install-brain.js "<目标文件夹>"   → 先把大脑位置指向该文件夹(写指针文件),再在那里建大脑
// 已存在则不覆盖(跨设备:同步盘里已有大脑会被直接复用)。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, locationPointerPath } = require(path.join(__dirname, 'lib.js'));

const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, '..');
const TEMPLATE = path.join(PLUGIN_ROOT, 'templates', 'brain');

try {
  // 可选:把大脑位置指向用户选定的同步盘文件夹(写指针,不需环境变量/命令行)
  const target = process.argv[2];
  if (target && target.trim()) {
    const loc = path.resolve(target.trim());
    fs.mkdirSync(loc, { recursive: true });
    fs.writeFileSync(locationPointerPath(), loc);
    console.log(`LOCATION\t${loc}\t已记住大脑位置(指针文件 ~/.yide-location)。`);
  }

  const BRAIN = brainDir(); // 在写完指针后解析,确保用新位置
  if (fs.existsSync(BRAIN) && fs.existsSync(path.join(BRAIN, 'INDEX.md'))) {
    console.log(`EXISTS\t${BRAIN}\t大脑已存在(可能来自其他设备同步),未覆盖。`);
    process.exit(0);
  }
  if (!fs.existsSync(TEMPLATE)) {
    console.log(`ERROR\t找不到模板:${TEMPLATE}`);
    process.exit(0);
  }
  fs.cpSync(TEMPLATE, BRAIN, { recursive: true });
  console.log(`CREATED\t${BRAIN}\t已从模板建立大脑。`);
} catch (e) {
  console.log(`ERROR\t${e && e.message}`);
}
