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
const host = require(path.join(__dirname, 'host.js'));
const { readCodexTurn } = require(path.join(__dirname, 'codex-turn.js'));

// Codex 改写闸参数。
const REWRITE_LINES = 60;
const CODE_EXT_RE = /\.(cs|shader|hlsl|cginc|compute|js|mjs|cjs|ts|tsx|py|uss|uxml)$/i;
// 用户本轮话里有这些"要大改"的意思就放行(宁可漏拦,不误伤明确的指令)。
const REWRITE_OK_RE = /重构|重写|推倒|重做|删|移除|替换|换成|整个|全部改|精简|简化|清理|清空|拆掉|合并|rewrite|refactor|remove|delete|replace|simplify|clean ?up|同意|批准|go ahead/i;

// 数 apply_patch 信封里对代码文件删掉的旧行:Update 块里 - 开头的行;Delete File 按现有文件行数算。
function rewriteSize(command, cwd) {
  const out = { removed: 0, files: [] };
  if (typeof command !== 'string') return out;
  let cur = null;
  for (const line of command.split(/\r?\n/)) {
    const m = line.match(/^\*\*\*\s+(Update|Add|Delete)\s+File:\s+(.+?)\s*$/);
    if (m) {
      cur = CODE_EXT_RE.test(m[2]) && m[1] !== 'Add' ? m[2] : null;
      if (cur && m[1] === 'Delete') {
        try {
          const p = path.isAbsolute(cur) ? cur : path.join(cwd || process.cwd(), cur);
          out.removed += fs.readFileSync(p, 'utf8').split(/\r?\n/).length;
        } catch {}
        out.files.push(path.basename(cur));
        cur = null;
      } else if (cur) out.files.push(path.basename(cur));
      continue;
    }
    if (cur && /^-/.test(line) && !/^---/.test(line)) out.removed++;
  }
  out.files = [...new Set(out.files)];
  return out;
}

// 前台轮询闸参数:单条 sleep ≥ POLL_SINGLE_SECS 或「循环 + sleep」估算总等待 > POLL_LOOP_OK_SECS 算前台长等待。
const POLL_SINGLE_SECS = 30;
const POLL_LOOP_OK_SECS = 60;
const POLL_REASON = '前台轮询会卡住整个会话。改用 run_in_background: true 跑这条命令(完成会自动通知),或用 Monitor 等条件;等的时候先做别的活。';

// 去掉不会被执行的文本(heredoc 正文、PS here-string、-m "提交说明"),免得提交说明里写了 sleep 被误拦。
function stripInert(cmd) {
  return cmd
    .replace(/<<-?\s*(['"]?)(\w+)\1[^\n]*\n[\s\S]*?\n[ \t]*\2[ \t]*(?=\r?\n|$)/g, '<<EOF')
    .replace(/@'[\s\S]*?\n'@/g, "''").replace(/@"[\s\S]*?\n"@/g, '""')
    .replace(/(\s-m\s+)("(?:[^"\\]|\\.)*"|'[^']*')/g, '$1""');
}

// 文本里所有 sleep 的秒数:[{secs}],secs=null 表示估不出(sleep $x 之类)。
// 认 sleep N[smhd] / Start-Sleep [-Seconds|-Milliseconds] N / timeout /t N。
function sleepsIn(text) {
  const out = [];
  let m;
  const SLEEP_RE = /(^|[^\w.-])(start-sleep|sleep)\b([^;&|\r\n})]*)/gi;
  while ((m = SLEEP_RE.exec(text))) {
    const a = m[3].trim();
    let secs = null, x;
    if ((x = a.match(/^-m\w*[\s:]+(\d+(?:\.\d+)?)(?!\S)/i))) secs = parseFloat(x[1]) / 1000;
    else if ((x = a.match(/^-s\w*[\s:]+(\d+(?:\.\d+)?)(?!\S)/i))) secs = parseFloat(x[1]);
    else if ((x = a.match(/^(\d+(?:\.\d+)?)([smhd]?)(?!\S)/i))) secs = parseFloat(x[1]) * { '': 1, s: 1, m: 60, h: 3600, d: 86400 }[x[2].toLowerCase()];
    out.push({ secs });
  }
  const TIMEOUT_RE = /\btimeout(?:\.exe)?\s+\/t\s+(-?\d+)/gi;
  while ((m = TIMEOUT_RE.exec(text))) out.push({ secs: +m[1] < 0 ? Infinity : +m[1] });
  return out;
}

// 计数器循环的迭代次数:条件里 `$t -lt 570` / `i<60`,循环里 t=$((t+15)) / t+=15 / $t = $t + 15 / i++;估不出返回 null。
function counterIters(cond, body, before) {
  const c = cond.match(/\$?\{?([A-Za-z_]\w*)\}?\s*(-lt|-le|-ne|-gt|-ge|<=|>=|<|>)\s*(\d+)/i);
  if (!c) return null;
  const v = c[1], limit = +c[3], hay = cond + '\n' + body;
  let step = null, x;
  if ((x = hay.match(new RegExp(`\\b${v}\\s*=\\s*\\$\\(\\(\\s*\\$?${v}\\s*([+-])\\s*(\\d+)\\s*\\)\\)`)))
    || (x = hay.match(new RegExp(`\\$?\\b${v}\\s*=\\s*\\$?${v}\\s*([+-])\\s*(\\d+)`)))
    || (x = hay.match(new RegExp(`\\$?\\b${v}\\s*([+-])=\\s*(\\d+)`)))) step = (x[1] === '-' ? -1 : 1) * +x[2];
  else if ((x = hay.match(new RegExp(`\\$?\\b${v}(\\+\\+|--)|(\\+\\+|--)\\$?${v}\\b`)))) step = (x[1] || x[2]) === '--' ? -1 : 1;
  if (!step) return null;
  const inits = [...(before + '\n' + cond).matchAll(new RegExp(`\\$?\\b${v}\\s*=\\s*(-?\\d+)(?![\\d.])`, 'g'))];
  const init = inits.length ? +inits[inits.length - 1][1] : 0;
  const n = (limit - init) / step;
  return n > 0 ? Math.ceil(n) + (/^(-le|-ge|<=|>=)$/i.test(c[2]) ? 1 : 0) : null;
}

// for x in LIST 的元素个数:$(seq ..) / {a..b} / 纯字面词表;含通配或变量估不出返回 null。
function listIters(list) {
  let x;
  if ((x = list.match(/\$\(\s*seq\s+(-?\d+)(?:\s+(-?\d+))?(?:\s+(-?\d+))?\s*\)/))) {
    const [a, b, c] = [x[1], x[2], x[3]].map(s => (s === undefined ? undefined : +s));
    const n = c !== undefined ? Math.floor((c - a) / b) + 1 : b !== undefined ? b - a + 1 : a;
    return n > 0 ? n : null;
  }
  if ((x = list.match(/\{(-?\d+)\.\.(-?\d+)(?:\.\.(\d+))?\}/))) return Math.floor(Math.abs(+x[2] - +x[1]) / (+x[3] || 1)) + 1;
  const words = list.replace(/;\s*$/, '').trim();
  if (!words || /[$`*?[{]/.test(words)) return null;
  return words.split(/\s+/).length;
}

// 前台长等待判定。Bash 用 do…done 配循环体,PowerShell 用 {…}。任何异常 → false(宁可漏拦,不误伤)。
function isForegroundWait(cmd, isPs) {
  try {
    if (!cmd || typeof cmd !== 'string' || !/sleep|timeout/i.test(cmd)) return false;
    const text = stripInert(cmd);
    if (sleepsIn(text).some(s => s.secs !== null && s.secs >= POLL_SINGLE_SECS)) return true;
    const LOOP_RE = /\b(?:while|until)\b|\bfor\s+[A-Za-z_]\w*\s+in\b|\bfor\s*\(|\bforeach\b|\bdo\s*\{/gi;
    let m;
    while ((m = LOOP_RE.exec(text))) {
      const kw = m[0].toLowerCase();
      const kwEnd = m.index + m[0].length;
      let head = text.slice(kwEnd), body = '', tail = '';
      if (!isPs) {
        const re = /\b(do|done)\b/g; re.lastIndex = kwEnd;
        let depth = 0, at = -1, d;
        while ((d = re.exec(text))) {
          if (d[1] === 'do') { if (at < 0) at = d.index; depth++; }
          else if (depth > 0 && --depth === 0) { body = text.slice(at, d.index); break; }
        }
        if (at >= 0) { head = text.slice(kwEnd, at); if (!body) body = text.slice(at); }
      } else {
        const open = text.indexOf('{', kw.startsWith('do') ? m.index : kwEnd);
        if (open >= 0) {
          let depth = 0, i = open;
          for (; i < text.length; i++) {
            if (text[i] === '{') depth++;
            else if (text[i] === '}' && --depth === 0) break;
          }
          head = text.slice(kwEnd, open);
          body = text.slice(open + 1, i);
          tail = text.slice(i + 1).split(/[;\r\n]/)[0];
        }
      }
      const sleeps = sleepsIn(head + '\n' + body + '\n' + tail);
      if (!sleeps.length) continue;
      if (sleeps.some(s => s.secs === null)) return true;
      const per = sleeps.reduce((a, s) => a + s.secs, 0);
      const before = text.slice(0, m.index);
      let iters = null;
      if (/^for\s+\w+\s+in$/.test(kw)) iters = listIters(head);
      else if (kw === 'foreach') {
        const seg = before.slice(Math.max(before.lastIndexOf(';'), before.lastIndexOf('\n')) + 1);
        const r = (head.match(/(-?\d+)\s*\.\.\s*(-?\d+)/) || seg.match(/(-?\d+)\s*\.\.\s*(-?\d+)/));
        if (r) iters = Math.abs(+r[2] - +r[1]) + 1;
      } else iters = counterIters(kw.startsWith('do') ? tail : head, body, before);
      if (iters === null || iters * per > POLL_LOOP_OK_SECS) return true;
    }
    return false;
  } catch { return false; }
}

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

// 这些 git 子命令既有只读查询形态、也有写形态 → 需按参数细分(见 isSafeBash)。
const GIT_WRITE_SUBS = new Set(['config', 'branch', 'tag', 'remote', 'reflog']);
// 显式写标志(即便没有位置参数也算写):删除/移动/复制/增改配置/改上游/清理等。
const GIT_WRITE_FLAGS = /^(-d|-D|--delete|-m|-M|--move|-c|-C|--copy|--add|--unset|--unset-all|--replace-all|-e|--edit|--edit-description|-u|--set-upstream-to|--unset-upstream|--create-reflog|--rename-section|--remove-section|-f|--force|--prune|--expire)$/;

function emit(decision, reason) {
  // Codex 不支持不带 updatedInput 的裸 allow(实测判 hook Failed);放行在 Codex 下就静默 defer,
  // 交给 Codex 自己的审批策略。deny 两边协议相同,照常输出。
  if (decision === 'allow' && host.isCodex()) process.exit(0);
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
  const segs = cmd.split(/\r?\n|\||&&|\|\||;|&(?!&)/).map(s => s.trim()).filter(Boolean);
  if (!segs.length) return false;
  for (const seg of segs) {
    const toks = seg.split(/\s+/).filter(Boolean);
    let i = 0;
    while (i < toks.length && /^\w+=/.test(toks[i])) i++;  // 跳过 VAR=val 前缀赋值
    const verb = toks[i];
    if (!verb || !safe.has(verb)) return false;
    const rest = toks.slice(i + 1);
    // find/sort 在白名单里,但它们有写形态:find -delete/-exec/-ok/-fprint*/-fls、sort -o(写文件)→ 回落审批
    if (verb === 'find' && rest.some(t => /^-delete$|^-exec|^-ok|^-fprint|^-fls$/.test(t))) return false;
    if (verb === 'sort' && rest.some(t => t === '-o' || /^-o./.test(t) || /^--output/.test(t))) return false;
    if (verb === 'git') {
      let j = i + 1;
      while (j < toks.length && toks[j].startsWith('-')) { if (toks[j] === '-C' || toks[j] === '-c') j++; j++; } // 跳过全局选项(-C/-c 带参)
      const sub = toks[j];
      if (!sub || !gitSafe.has(sub)) return false;
      // 可写子命令(config/branch/tag/remote/reflog)只在"纯查询"时放行:出现位置参数(分支名/配置值/tag 名/remote 名)
      // 或显式写标志 → 回落审批(git branch <名> 会建分支,撞红线⑧)。
      if (GIT_WRITE_SUBS.has(sub)) {
        for (let k = j + 1; k < toks.length; k++) {
          const t = toks[k];
          if (!t.startsWith('-')) return false;      // 位置参数 = 写形态(create/set/rename/delete)
          if (GIT_WRITE_FLAGS.test(t)) return false; // 显式写标志(-d/-m/--add/--unset…)
        }
      }
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

// MCP 安全判定:
//   deny 用子串匹配(过拦=defer,安全,故保留 set_/add_/run_command 等前缀语义);
//   allow 必须按 `_` 分词整词命中 —— 否则 'get' 会误命中 forget/budget 把危险工具放行。
function isSafeMcp(tool, conf) {
  const name = String(tool).toLowerCase();
  if ((conf.mcpDeny || []).some(d => name.includes(d))) return false;
  const toks = new Set(name.split('_').filter(Boolean));
  return (conf.mcpAllow || []).some(a => toks.has(a));
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
    // Codex 改文件只有 apply_patch(补丁信封在 tool_input.command):当作 Write/Edit/MultiEdit 匹配,
    // file_path/notebook_path 取补丁里涉及的全部文件 —— 否则按 Write/Edit 写的红线在 Codex 下全部落空。
    const patch = tool === 'apply_patch' ? host.parseApplyPatch(ti.command) : null;
    const aliases = patch ? ['apply_patch', 'Write', 'Edit', 'MultiEdit'] : [tool];
    const fieldVal = k => (patch && (k === 'file_path' || k === 'notebook_path'))
      ? patch.files.join('\n')
      : (typeof ti[k] === 'string' ? ti[k] : '');
    for (const r of rules) {
      if (!r || !r.pattern) continue;
      const tools = Array.isArray(r.tools) && r.tools.length ? r.tools : ['*'];
      if (!tools.includes('*') && !aliases.some(t => tools.includes(t))) continue;
      let re; try { re = new RegExp(r.pattern); } catch { continue; }
      // fields:只对 tool_input 里这些键的字符串值匹配(如 ["file_path"]),不写则匹配全部字符串值(blob)
      const target = Array.isArray(r.fields) && r.fields.length
        ? r.fields.map(fieldVal).join('\n')
        : blob;
      if (re.test(target)) emit('deny', '🗡️ 翼德拦截:' + (r.reason || ('命中规则 ' + r.pattern)));
    }
  }

  // 1b) Codex 改写闸:一个补丁大面积删改既有代码,而本回合用户没要求重构 → 拦下要它先说明。
  //     治"Codex 不尊重既有开发逻辑、推倒重写"。只数删掉的旧行(新增不算),阈值宽松,只拦明显的推倒。
  if (host.isCodex() && tool === 'apply_patch') {
    const r = rewriteSize(ti.command, input.cwd);
    if (r.removed >= REWRITE_LINES) {
      const turn = readCodexTurn(input.transcript_path);
      const asked = turn && REWRITE_OK_RE.test(turn.userPrompt);
      if (!asked) {
        emit('deny', `🗡️ 翼德改写闸:这个补丁要删掉/改写 ${r.removed} 行既有代码(${r.files.slice(0, 4).join('、')}),本回合用户没要求重构或重写。` +
          '先读懂现有实现为什么这样写(git log -p、调用方、记忆里的相关拍板),能在原逻辑上增量改就增量改;' +
          '确实需要推倒,停下来向用户说明现有逻辑哪里不能沿用、打算怎么改,等用户同意后再动。');
      }
    }
  }

  // 1c) 前台轮询闸:Bash/PowerShell 前台跑「循环 + sleep」或长 sleep 会卡死整个会话(10-26~29 审计约 600 分钟耗在这)。
  //     run_in_background: true 的一律放行;估算总等待 ≤ 60 秒的短重试放行。
  if ((tool === 'Bash' || tool === 'PowerShell') && ti.run_in_background !== true
    && isForegroundWait(ti.command, tool === 'PowerShell')) {
    emit('deny', '🗡️ 翼德拦截:' + POLL_REASON);
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
