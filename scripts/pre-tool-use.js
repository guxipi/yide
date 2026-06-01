#!/usr/bin/env node
// 翼德 PreToolUse hook(权限层)。两件事,顺序固定:
//   1) 硬拦截(deny):读 .meta/hook-rules.json 正则,命中即 deny —— "记过的错绝不再犯"里唯一能真 block 的一环。
//   2) 自动放行(allow):只读/导航类安全操作免审批,治"勾哥每天开 Claude 一堆 approval"。
// 安全模型:
//   - deny 永远先跑;且 settings.json 里的 deny 规则也优先于本 hook 的 allow(deny-first,谁都盖不过)。
//   - 只放"确定安全"的(只读/导航);Write/Edit 永不在此放行(那正是翼德的把关价值)。
//   - 任何拿不准 → 不输出(defer),回落到 Claude 正常审批流程;宁可让勾哥点一下,绝不误放危险操作。
//   - 默认白名单烤在本文件;可被 ~/.yide/.meta/allow-rules.json 覆盖/扩展(勾哥可调)。
// 仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

const META = path.join(brainDir(), '.meta');
const RULES = path.join(META, 'hook-rules.json');
const ALLOW = path.join(META, 'allow-rules.json');

// 自动放行默认配置(保守:只读/导航)。可被 .meta/allow-rules.json 覆盖。
const DEFAULT_ALLOW = {
  tools: ['Read', 'Glob', 'Grep', 'NotebookRead', 'BashOutput', 'TodoWrite'],
  bashSafe: ['cd', 'ls', 'pwd', 'cat', 'head', 'tail', 'grep', 'egrep', 'fgrep', 'rg', 'find', 'echo', 'printf', 'which', 'type', 'wc', 'file', 'stat', 'tree', 'dirname', 'basename', 'realpath', 'date', 'whoami', 'hostname', 'uname', 'env', 'sort', 'uniq', 'cut', 'column', 'diff', 'cmp', 'git', 'adb'],
  gitSafe: ['status', 'diff', 'log', 'show', 'branch', 'remote', 'blame', 'rev-parse', 'describe', 'tag', 'ls-files', 'shortlog', 'config', 'cat-file', 'for-each-ref', 'symbolic-ref', 'reflog'],
  adbSafe: ['devices', 'logcat', 'pull', 'get-state', 'bugreport', 'version', 'start-server', 'kill-server'], // 只读/取证;shell·exec-out·install 等不放行(会落到正常审批)

  mcpAllow: ['read', 'get', 'list', 'search', 'console', 'log', 'describe', 'inspect', 'snapshot', 'query', 'info', 'status', 'fetch', 'test', 'find', 'view', 'show', 'count'],
  mcpDeny: ['manage', 'create', 'delete', 'write', 'update', 'modify', 'remove', 'rename', 'move', 'execute', 'exec', 'install', 'build', 'kill', 'stop', 'restart', 'run_command', 'set_', 'add_', 'apply', 'commit', 'push', 'reset', 'checkout', 'clean'],
};

function emit(decision, reason) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: decision, permissionDecisionReason: reason },
  }));
  process.exit(0);
}
function collect(v, out) {
  if (typeof v === 'string') out.push(v);
  else if (Array.isArray(v)) for (const x of v) collect(x, out);
  else if (v && typeof v === 'object') for (const k of Object.keys(v)) collect(v[k], out);
  return out;
}

// Bash 安全判定:整条命令拆成简单命令段(按 | && || ; & 切),每段首词都得在白名单;
// 有命令替换 $()/反引号、或输出重定向 > 即不放行(可能藏写操作/任意命令)。git 还要校验子命令。
function isSafeBash(cmd, conf) {
  if (!cmd || typeof cmd !== 'string') return false;
  if (/\$\(|`/.test(cmd)) return false;   // 命令替换 → 可能藏任意命令
  if (/>/.test(cmd)) return false;        // 输出重定向(写文件)→ 一律不放行(含 2>&1,从严)
  const safe = new Set(conf.bashSafe || []);
  const gitSafe = new Set(conf.gitSafe || []);
  const adbSafe = new Set(conf.adbSafe || []);
  const segs = cmd.split(/\||&&|\|\||;|&(?!&)/).map(s => s.trim()).filter(Boolean);
  if (!segs.length) return false;
  for (const seg of segs) {
    const toks = seg.split(/\s+/).filter(Boolean);
    let i = 0;
    while (i < toks.length && /^\w+=/.test(toks[i])) i++;  // 跳过 VAR=val 前缀赋值
    const verb = toks[i];
    if (!verb || !safe.has(verb)) return false;
    if (verb === 'git') {
      let j = i + 1;
      while (j < toks.length && toks[j].startsWith('-')) { if (toks[j] === '-C' || toks[j] === '-c') j++; j++; } // 跳过全局选项(-C/-c 带参)
      const sub = toks[j];
      if (!sub || !gitSafe.has(sub)) return false;
    }
    if (verb === 'adb') {
      let j = i + 1;
      while (j < toks.length && toks[j].startsWith('-')) { if (toks[j] === '-s') j++; j++; } // 跳过 -s <serial>/-d/-e 等选项
      const sub = toks[j];
      if (!sub || !adbSafe.has(sub)) return false; // 只放只读取证子命令;shell/exec-out/install 等落回审批
    }
  }
  return true;
}

// MCP 安全判定:工具名含任一 deny 子串即拒(回落审批);否则含 allow 子串才放行。
function isSafeMcp(tool, conf) {
  const name = String(tool).toLowerCase();
  if ((conf.mcpDeny || []).some(d => name.includes(d))) return false;
  return (conf.mcpAllow || []).some(a => name.includes(a));
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const tool = input.tool_name || '';
  const ti = input.tool_input || {};
  const blob = collect(ti, []).join('\n');

  // 1) 硬拦截(deny 优先)
  if (fs.existsSync(RULES)) {
    let conf = null;
    try { conf = JSON.parse(fs.readFileSync(RULES, 'utf8')); } catch {}
    const rules = conf && Array.isArray(conf.rules) ? conf.rules : [];
    for (const r of rules) {
      if (!r || !r.pattern) continue;
      const tools = Array.isArray(r.tools) && r.tools.length ? r.tools : ['*'];
      if (!tools.includes('*') && !tools.includes(tool)) continue;
      let re; try { re = new RegExp(r.pattern); } catch { continue; }
      if (re.test(blob)) emit('deny', '🗡️ 翼德拦截:' + (r.reason || ('命中规则 ' + r.pattern)));
    }
  }

  // 2) 自动放行(只读/导航;拿不准就 defer)
  let allowConf = DEFAULT_ALLOW;
  try {
    if (fs.existsSync(ALLOW)) {
      const c = JSON.parse(fs.readFileSync(ALLOW, 'utf8'));
      if (c && typeof c === 'object') allowConf = Object.assign({}, DEFAULT_ALLOW, c);
    }
  } catch {}

  let ok = false;
  if ((allowConf.tools || []).includes(tool)) ok = true;
  else if (tool === 'Bash') ok = isSafeBash(ti.command, allowConf);
  else if (/^mcp__/.test(tool)) ok = isSafeMcp(tool, allowConf);
  if (ok) emit('allow', '翼德放行(只读/安全操作,免审批)');

  process.exit(0);
} catch (e) { process.exit(0); }
