#!/usr/bin/env node
// 翼德 · 开工复用登记(配合 reuse-gate.js)。用法:
//   node reuse-check.js record --task "<这一轮要做什么>" --skills "<要用的 skill,逗号分隔 | none:理由>" --reuse "<现成件和怎么用 | 搜了哪些地方没找到>"
// 本脚本只校验写得够具体并回显;PreToolUse 闸从会话记录里读这条命令,核对本轮之前有过查找、--skills 里的 skill 已加载。
'use strict';
const a = process.argv.slice(2);
if (a[0] !== 'record') { console.log('用法:node reuse-check.js record --task "…" --skills "…" --reuse "…"'); process.exit(2); }
const get = k => { const i = a.indexOf('--' + k); return i >= 0 && i + 1 < a.length ? String(a[i + 1]).trim() : ''; };
const task = get('task'), skills = get('skills'), reuse = get('reuse');
const bad = [];
if (task.length < 2) bad.push('--task 写清这一轮要做什么');
if (!skills) bad.push('--skills 写要用的 skill;都不适用写 "none:理由"');
else if (/^(none|无)\s*$/i.test(skills)) bad.push('--skills 写 none 要带理由("none:理由")');
if (reuse.length < 10 || /^(无|没有|none|n\/a)$/i.test(reuse)) bad.push('--reuse 写找到的现成件和怎么用;没找到要写搜了哪些地方');
if (bad.length) { console.log('登记不合格:\n- ' + bad.join('\n- ')); process.exit(1); }
console.log(`已登记开工复用检查\n任务:${task}\nskill:${skills}\n复用:${reuse}`);
