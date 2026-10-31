// 翼德 · 开工复用闸(2026-10-31 勾哥:"我需要一个通用的开始做之前的 gate,检查是否已经有可以使用的 skill 或做法,
// 是否有东西可以直接复用")。
//
// 治的病:选 skill / 找现成件只在接活那一刻做一次;活中途变了样(问答 → 建模 → 照参考返工)不再回头查,
// 于是自己临时写脚本绕远路(10-31:14 个跑 Blender 的会话 0 个加载 reference-replicate、stage.py 现成不用另写;
// 10-24:Lab 现成做法卡零使用,反馈一来就新建)。文字规矩靠不住,所以在"开工动作"上拦。
//
// 规则:每一轮用户消息之后,第一次做"开工动作"前,本轮里必须已经
//   ① 有过至少一次查找(Grep / Glob / Skill / 读 SKILL.md / ls·grep·find 之类的 shell 查找),并且
//   ② 跑过一次 `node <插件>/scripts/reuse-check.js record --task … --skills … --reuse …` 登记结论,
//   ③ 登记里写了要用的 skill(--skills),本会话必须真用 Skill 工具加载过它们。
// "开工动作" = 新建代码文件(Write 到不存在的 .py/.js/.cs/.ps1/.sh/.shader…)、跑 Blender 脚本、派 codex、
// 派子 agent(Explore 等只读的除外)、起 Workflow。改已有文件不拦(小修小补不该被打断)。
// 读不到 transcript 不拦;Codex 宿主跳过;.meta/skill-gates.json 里 {"reuseGate":{"enabled":false}} 可关。
'use strict';
const fs = require('fs');
const path = require('path');

const CODE_EXT = /\.(py|js|mjs|cjs|ts|tsx|cs|ps1|psm1|sh|bat|cmd|shader|hlsl|cginc|compute|uss|uxml)$/i;
const READONLY_AGENTS = new Set(['Explore', 'claude-code-guide', 'statusline-setup', 'Plan']);
const SEARCH_BASH = /(^|[\s;&|(])(grep|rg|find|ls|Get-ChildItem|Select-String|gci|dir)\s/;
const NOT_A_TURN = /^\s*<(task-notification|side-sessions-event|ci-monitor-event|local-command|command-name|bash-)/;

function startAction(tool, ti) {
  if (tool === 'Write') {
    const p = typeof ti.file_path === 'string' ? ti.file_path : '';
    if (CODE_EXT.test(p) && !fs.existsSync(p)) return '新建代码文件 ' + path.basename(p);
    return null;
  }
  if (tool === 'Bash' || tool === 'PowerShell') {
    const c = typeof ti.command === 'string' ? ti.command : '';
    if (/reuse-check\.js/.test(c)) return null;
    if (/blender/i.test(c) && /\s-b\s/.test(c) && /\s(-P|--python|--python-expr)\s/.test(c)) return '跑 Blender 脚本';
    if (/\bcodex\s+exec\b|run_codex\.sh/.test(c)) return '派 codex(sol)';
    return null;
  }
  if (tool === 'mcp__blender__execute_blender_code' || tool === 'mcp__blender__execute_blender_code_for_cli') return '在 Blender 里执行代码';
  if (tool === 'Agent' || tool === 'Task') {
    const t = ti.subagent_type || 'general-purpose';
    return READONLY_AGENTS.has(t) ? null : '派子 agent(' + t + ')';
  }
  if (tool === 'Workflow') return '起 Workflow';
  if (/^mcp__coplay-mcp__(execute_script|create_|generate_)/.test(tool)) return '在 Unity 里新建/生成(' + tool.replace('mcp__coplay-mcp__', '') + ')';
  return null;
}

// 一行 transcript 是不是"新的一轮用户消息"(不是工具结果、不是系统注入、不是后台通知)。
function isUserTurn(o) {
  if (!o || o.type !== 'user' || o.isMeta) return false;
  const c = o.message && o.message.content;
  const texts = typeof c === 'string' ? [c]
    : Array.isArray(c) ? (c.some(x => x && x.type === 'tool_result') ? [] : c.filter(x => x && x.type === 'text').map(x => x.text || ''))
    : [];
  for (const t of texts) {
    const s = String(t).replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '').trim();
    if (s && !NOT_A_TURN.test(s)) return true;
  }
  return false;
}

function toolUses(o) {
  const c = o && o.type === 'assistant' && o.message && o.message.content;
  return Array.isArray(c) ? c.filter(x => x && x.type === 'tool_use') : [];
}

function isSearch(u) {
  const n = u.name, i = u.input || {};
  if (n === 'Grep' || n === 'Glob' || n === 'Skill' || n === 'ToolSearch') return true;
  if (n === 'Read' && /SKILL\.md$|MEMORY\.md$|index-[\w-]+\.md$/i.test(String(i.file_path || ''))) return true;
  if ((n === 'Bash' || n === 'PowerShell') && SEARCH_BASH.test(String(i.command || ''))) return true;
  if (n === 'Agent' && READONLY_AGENTS.has(i.subagent_type)) return true;
  return false;
}

// 从 record 命令里取 --skills 的值。
function recordSkills(cmd) {
  const m = String(cmd).match(/--skills\s+(?:"([^"]*)"|'([^']*)'|(\S+))/);
  const v = m ? (m[1] ?? m[2] ?? m[3] ?? '') : '';
  if (/^\s*(none|无)\b/i.test(v)) return [];
  return v.split(/[,，、\s]+/).map(s => s.trim()).filter(s => /^[\w:-]+$/.test(s));
}

function skillLoaded(tx, skill) {
  const name = skill.replace(/^[^:]+:/, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp('"name":"Skill","input":\\{"skill":"(?:[\\w-]+:)?' + name + '"').test(tx);
}

// 列出可用 skill(插件 + 项目),给拦截消息用:逼着在开工那一刻把清单过一遍。
function skillList(pluginRoot, projectDir) {
  const out = [];
  const scan = (dir, prefix) => {
    let names = [];
    try { names = fs.readdirSync(dir); } catch { return; }
    for (const n of names) {
      const f = path.join(dir, n, 'SKILL.md');
      let head = '';
      try { head = fs.readFileSync(f, 'utf8').slice(0, 1200); } catch { continue; }
      const d = (head.match(/^description:\s*(.+)$/m) || [])[1] || '';
      out.push(`${prefix}${n} — ${d.replace(/^["']/, '').slice(0, 48)}`);
    }
  };
  scan(path.join(pluginRoot, 'skills'), 'yide:');
  if (projectDir) scan(path.join(projectDir, '.claude', 'skills'), '');
  return out;
}

// 返回 null = 放行;返回字符串 = 拦截理由。
function check(input, opts) {
  const tool = input.tool_name || '';
  const ti = input.tool_input || {};
  const action = startAction(tool, ti);
  if (!action) return null;
  let tx = '';
  try { tx = input.transcript_path ? fs.readFileSync(input.transcript_path, 'utf8') : ''; } catch { tx = ''; }
  if (!tx) return null;

  const lines = tx.split('\n');
  let searched = false, record = null;
  for (let k = lines.length - 1; k >= 0; k--) {
    if (!lines[k]) continue;
    let o; try { o = JSON.parse(lines[k]); } catch { continue; }
    if (isUserTurn(o)) break;
    for (const u of toolUses(o).reverse()) { // 倒序:同一条消息里先查后登记也算
      const c = u.input && u.input.command;
      if ((u.name === 'Bash' || u.name === 'PowerShell') && /^\s*node(?:\.exe)?\s+["']?[^"'\n]*reuse-check\.js["']?\s+record\b/m.test(String(c || ''))) {
        if (!record) record = String(c);
      } else if (record && isSearch(u)) searched = true; // 只算登记之前(倒序扫描里更早)的查找
    }
  }
  const script = path.join(opts.pluginRoot, 'scripts', 'reuse-check.js').split(path.sep).join('/');
  const cmd = `node "${script}" record --task "<这一轮要做什么>" --skills "<要用的 skill,逗号分隔;都不适用写 none:理由>" --reuse "<找到的现成脚本/做法卡/现成件和怎么用;没找到写搜了哪些地方>"`;
  const list = skillList(opts.pluginRoot, opts.projectDir);
  const head = `🗡️ 翼德开工复用闸:这一轮要「${action}」,开工前先查有没有现成的 skill、做法或可以直接复用的东西。\n`;
  const how = '要做的:① 对照下面的 skill 清单,该用的用 Skill 工具加载;② 搜现成件:yide 各 skill 的 scripts/ 和 references/、项目 .claude/skills、项目 Tools/ 与 Editor 工具、记忆 MEMORY.md 和分区子索引、当前工作目录里已有的脚本;③ 跑登记命令:\n' + cmd + '\n';
  const tail = list.length ? '可用 skill:\n- ' + list.join('\n- ') : '';
  if (!record) return head + how + tail;
  if (!searched) return head + '本轮登记之前没有任何查找动作(Grep/Glob/Skill/读 SKILL.md/ls·grep·find)。先真查,再重新登记。\n' + how;
  const missing = recordSkills(record).filter(s => !skillLoaded(tx, s));
  if (missing.length) return head + `登记里要用的 skill 本会话还没加载:${missing.join('、')}。用 Skill 工具加载后再继续。`;
  return null;
}

module.exports = { check, startAction, isUserTurn, recordSkills };
