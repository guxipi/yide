#!/usr/bin/env node
// 翼德 · 记忆桥(只挂在 Codex 的 SessionStart 上;Claude Code 原生自动加载 MEMORY.md,不需要它)。
//
// 目的:Claude Code 与 Codex 共用同一份项目记忆,不做第二份拷贝。
//   - 真源 = Claude Code 的项目记忆目录 ~/.claude/projects/<slug>/memory/(MEMORY.md 索引 + 一事一文件)。
//   - 本脚本按 session cwd 向上逐级找对应的记忆目录,把 MEMORY.md 索引 + 写回规则 + 宿主差异
//     作为 additionalContext 注入 Codex。Codex 学到的新事实也写回同一目录,两边下次开会话都能看到。
// slug 规则与 Claude Code 一致:绝对路径里非 [A-Za-z0-9] 的字符一律换成 '-'(盘符大小写不敏感)。
// 安全模型:任何异常一律静默退出 0,绝不挡会话。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');

const PROJECTS = process.env.YIDE_CLAUDE_PROJECTS || path.join(os.homedir(), '.claude', 'projects');

function slugOf(p) { return String(p).replace(/[^A-Za-z0-9]/g, '-'); }

// cwd 向上逐级找,返回 { dir, root }:dir=记忆目录,root=它对应的项目根。
function findMemory(cwd) {
  let names;
  try { names = fs.readdirSync(PROJECTS); } catch { return null; }
  const byLower = new Map(names.map(n => [n.toLowerCase(), n]));
  let cur = path.resolve(cwd);
  for (;;) {
    const hit = byLower.get(slugOf(cur).toLowerCase());
    if (hit) {
      const dir = path.join(PROJECTS, hit, 'memory');
      if (fs.existsSync(path.join(dir, 'MEMORY.md'))) return { dir, root: cur };
    }
    const up = path.dirname(cur);
    if (up === cur) return null;
    cur = up;
  }
}

const HOST_NOTES =
  '## 宿主差异(你在 Codex 里,翼德规矩原文是按 Claude Code 写的)\n' +
  '- 规矩里的"弹窗问 / AskUserQuestion"= 你这边的提问方式(有 request_user_input 就用它给选项,否则在回复里列选项并停下等勾哥)。\n' +
  '- Read/Grep/Glob/Edit/Write = 你的 shell 与 apply_patch;Coplay MCP 工具名一致(mcp__coplay-mcp__*)。\n' +
  '- 翼德 skills 已随插件装进来,同名可直接用;skill 正文里的 Claude 专属工具名按上面两条换算。\n' +
  '- scope 契约照常用:简报里给的 scope.js 路径和 sid 就是你这边的,Stop 闸会按它拦未收敛条目。' +
  '沙箱里 check 起不了子进程(EPERM)时,自己用 shell 跑 verify 命令,再 attest 贴退出码和关键输出。\n' +
  '- 翼德在你这边多两道闸(勾哥 2026-10-15 要求):改写闸——一个补丁删改 60 行以上既有代码、而用户本轮没要求重构时会被拦;' +
  '查证闸——交互会话里一个工具没调就长篇作答,收尾时会被拦一次。被拦就照提示做,不要绕。\n';

function writeRules(dir) {
  return '## 写回规则(共用一源,别另存副本)\n' +
    `- 记忆目录:\`${dir}\`。一事一文件,frontmatter 三字段:name(短 kebab slug)/ description(一行,供召回判断)/ metadata.type(user|feedback|project|reference);` +
    'feedback/project 正文后接 **Why:** 和 **How to apply:** 两行;相关条目用 [[name]] 互链。\n' +
    '- 写完在 MEMORY.md 加一行指针 `- [标题](文件.md) — 一句话钩子`;已有条目覆盖同一事实就改原文件,不新建重复;发现错了就删。\n' +
    '- 不记代码结构、git 历史、CLAUDE.md 已写的东西;相对日期一律换成绝对日期。\n' +
    '- 不要写进 Codex 自己的 memories 或别的笔记文件:Claude Code 读不到,就又成两份了。\n' +
    '- 设计口径(玩法/系统/数值定义)的真源是 vault 设计文档,改口径写文档,记忆里只记"拍板了什么、真源在哪"。\n';
}

try {
  let input = {};
  try { input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}'); } catch {}
  const cwd = (typeof input.cwd === 'string' && input.cwd) || process.cwd();
  const mem = findMemory(cwd);

  let ctx = '# 翼德 · 共用项目记忆(与 Claude Code 同一份)\n\n';
  if (mem) {
    let index = '';
    try { index = fs.readFileSync(path.join(mem.dir, 'MEMORY.md'), 'utf8').trim(); } catch {}
    ctx += `本项目(${mem.root})的记忆索引如下。每行是一条记忆的指针;要细节就读对应文件(在 \`${mem.dir}\` 下),` +
      '别凭索引一句话下结论。条目带日期,反映写入时的事实;涉及文件、函数、开关的,用前先核实还在。\n\n' +
      index + '\n\n' + writeRules(mem.dir) + '\n';
  } else {
    ctx += `当前目录(${cwd})没有对应的 Claude Code 项目记忆。若要新开,目录为 ${PROJECTS}\\<cwd 非字母数字换成 - 的 slug>\\memory\\。\n\n`;
  }
  ctx += HOST_NOTES;

  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: ctx },
  }));
} catch { /* 静默放行 */ }
process.exit(0);
