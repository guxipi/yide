#!/usr/bin/env node
// 翼德 Stop/SubagentStop hook(收尾审计)。三道闸门,治两个正交病根:
//
//   ① 覆盖度闸门(scope):本会话登记过 scope 且仍有 open/fail 条目 → block 并列出未完成项。
//      这是唯一把"完成"从 AI 自评变成外部可证伪的地方(见 scope.js 抬头)。
//   ② 留尾闸门(兜底):没登记 scope,但最终汇报把"还要不要继续"甩回用户 → block 一次,
//      要它要么做完、要么登记 scope 说清楚为什么停。调过 AskUserQuestion 的正当拍板豁免。
//   ③ 诚实度闸门:本回合改了文件 + 汇报含完成/通过声明 + 本回合零验证工具调用 → block。
//      (改动:验证证据的扫描范围从"全会话"收窄到"本回合" —— 否则会话早期跑过一次 Play,
//       后面每个回合都白嫖那次证据直接放行。)
//
// 防死循环:Claude Code 对 Stop hook 有连续 8 次 block 的硬上限,撞满是最糟的失败形态。
//   - 按 session 计数,连续 block 达 MAX_BLOCKS 次后放行(最后一次 block 的 reason 里预告"下次放行,如实报告卡在哪")。
//   - 两次 block 之间未完成签名没变(= 空转)也提前退化。
//   - 闸门全过 → 计数清零。
// 安全模型:任何异常(读不到/解析失败)一律静默放行,绝不误伤。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const scope = require(path.join(__dirname, 'scope.js'));
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));

// 完成/通过声明(保守强匹配,中英)。(?<!un)verified:UNVERIFIED 是合规的"未验证"标注,不算完成声明。
const CLAIM_RE = /(已接通|接通了|部署完成|部署成功|已部署|测试通过|全部通过|验证通过|验收通过|已验证|修复完成|已修复并验证|(?<!un)verified|all tests pass(ed)?|tests? pass(ed)?|deployed successfully|works as expected)/i;
// 把"还要不要干下去"的判断甩回用户的措辞。收得紧,只匹配疑问式 + 指向继续工作。
const TAIL_RE = /((要不要|需不需要|是否需要|用不用)(我)?(继续|接着|再|把|做|改|加|补|实现|处理)|(还要|下一步|剩下的|其余的|另外那些?)[^。\n]{0,12}(要不要|需不需要|是否需要|吗[??])|需要我(继续|接着|再)[^。\n]{0,10}吗|should I (continue|proceed|keep going)|want me to (continue|proceed|keep going|do)|let me know if you (want|need))/i;
// Bash/PowerShell command 里算"跑过验证"的形态。
const CMD_RE = /(npm (run )?test|node .*test|dotnet (test|build)|pytest|go test|cargo test|ugs |deploy|curl |Invoke-RestMethod|Invoke-WebRequest)/i;
// coplay 里的只读工具(不算"改了东西")。
const COPLAY_READONLY_RE = /^mcp__coplay[^_]*__(get_|list_|search_|read_|check_|capture_)/i;

const BLOCKS_FILE = 'stop-blocks.json';
const MAX_BLOCKS = 3;          // 硬上限 8,留足余量
const MAX_LIST = 8;            // reason 里最多列几条未完成项

const HONESTY_REASON = '🗡️ 翼德审计:本回合改了文件、汇报含完成/通过声明,但本回合没有任何运行时验证工具调用(没跑过 Play/测试/部署/请求)。要么现在验证并贴证据,要么把相应结论改标 UNVERIFIED 并说明原因——不许维持无证据的完成声明。';

const SCOPE_USAGE = '登记/收敛 scope(node "<plugin>/scripts/scope.js"):\n' +
  '  set --session <sid> --json \'[{"what":"做什么","verify":"能判定成败的命令(可省)"}]\'\n' +
  '  check --session <sid>            跑 verify,退出码 0 才算 pass\n' +
  '  attest --session <sid> --id <id> --evidence "<具体证据:日志行/截图路径/实测结果>"   没命令可跑时的自证出口\n' +
  '  waive --session <sid> --id <id> --reason "<为什么不做了>"';

// ── transcript 读取(>20MB 只读末尾 5MB)──
function readTranscriptTail(fp) {
  const st = fs.statSync(fp);
  const MAX = 20 * 1024 * 1024;
  const TAIL = 5 * 1024 * 1024;
  if (st.size <= MAX) return { text: fs.readFileSync(fp, 'utf8'), truncated: false };
  const fd = fs.openSync(fp, 'r');
  try {
    const buf = Buffer.alloc(TAIL);
    const n = fs.readSync(fd, buf, 0, TAIL, st.size - TAIL);
    return { text: buf.toString('utf8', 0, n), truncated: true };
  } finally { fs.closeSync(fd); }
}

// entry.message.content 归一成块数组(content 为字符串时包成单个 text 块)。
function contentBlocks(entry) {
  const msg = entry && typeof entry === 'object' ? entry.message : null;
  if (!msg || typeof msg !== 'object') return [];
  const c = msg.content;
  if (typeof c === 'string') return [{ type: 'text', text: c }];
  if (Array.isArray(c)) return c;
  return [];
}
function isAssistant(entry) {
  if (!entry || typeof entry !== 'object') return false;
  if (entry.type === 'assistant') return true;
  return !!(entry.message && entry.message.role === 'assistant');
}
// 真正的用户发言(tool_result 也以 user role 出现,不算)。
function isRealUserTurn(entry) {
  if (!entry || typeof entry !== 'object') return false;
  const isUser = entry.type === 'user' || (entry.message && entry.message.role === 'user');
  if (!isUser) return false;
  return !contentBlocks(entry).some(b => b && b.type === 'tool_result');
}
// 本回合 = 最后一条真实用户发言之后的 entries;找不到则退回全部(短 transcript / 测试场景)。
function currentTurn(entries) {
  for (let i = entries.length - 1; i >= 0; i--) if (isRealUserTurn(entries[i])) return entries.slice(i + 1);
  return entries;
}

function toolUses(entries) {
  const out = [];
  for (const e of entries) for (const b of contentBlocks(e)) if (b && b.type === 'tool_use') out.push(b);
  return out;
}
function isVerificationTool(name, input) {
  const n = String(name || '');
  if (/^mcp__coplay/i.test(n)) return true;                 // play_game/execute_script/get_unity_logs/check_compile_errors…
  if (/^mcp__claude-in-chrome__/i.test(n)) return true;     // 浏览器驱动
  if (/playwright|puppeteer/i.test(n)) return true;         // 其它浏览器驱动
  if (/^(Bash|PowerShell)$/i.test(n)) {
    const cmd = input && typeof input.command === 'string' ? input.command : '';
    if (CMD_RE.test(cmd)) return true;
  }
  return false;
}
function isMutationTool(name) {
  const n = String(name || '');
  if (/^(Write|Edit|MultiEdit|NotebookEdit|apply_patch)$/i.test(n)) return true;
  if (/^mcp__coplay/i.test(n)) return !COPLAY_READONLY_RE.test(n);
  return false;
}

// ── 连续 block 计数(本机私有;按 session)──
function readBlocks(sid) {
  const all = readLocalJson(BLOCKS_FILE, {}) || {};
  const st = all[sid];
  return st && typeof st === 'object' ? { n: st.n || 0, sig: st.sig || '' } : { n: 0, sig: '' };
}
function writeBlocks(sid, st) {
  let all = readLocalJson(BLOCKS_FILE, {}) || {};
  if (st === null) delete all[sid]; else { delete all[sid]; all[sid] = st; }
  const keys = Object.keys(all);
  if (keys.length > 40) { const trimmed = {}; for (const k of keys.slice(-40)) trimmed[k] = all[k]; all = trimmed; }
  writeLocalJson(BLOCKS_FILE, all);
}

function coverageReason(items) {
  const show = items.slice(0, MAX_LIST);
  let msg = `🗡️ 翼德审计(覆盖度):本回合登记的 scope 还有 ${items.length} 条没收敛,不许收工:\n`;
  for (const i of show) msg += `- [${i.id}] ${i.what} — ${i.state}${i.note ? ' :: ' + String(i.note).split('\n')[0].slice(0, 120) : ''}\n`;
  if (items.length > show.length) msg += `- …还有 ${items.length - show.length} 条\n`;
  return msg + '把它们做完并 check 通过;真做不了的走 waive 说明理由,不许留着 open 就结束。\n' + SCOPE_USAGE;
}

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  const sid = input.session_id || 'nosid';

  const fp = input.transcript_path;
  if (!fp || typeof fp !== 'string' || !fs.existsSync(fp)) process.exit(0);

  const { text, truncated } = readTranscriptTail(fp);
  const lines = text.split(/\r?\n/);
  if (truncated && lines.length) lines.shift();  // 丢掉第一个可能不完整的行
  const entries = [];
  for (const line of lines) {
    const s = line.trim();
    if (!s) continue;
    try { entries.push(JSON.parse(s)); } catch {}
  }

  const turn = currentTurn(entries);
  const turnTools = toolUses(turn);

  // 最后一条 assistant 文本消息(拼接其全部 text 块)。
  let lastText = null;
  for (const e of entries) {
    if (!isAssistant(e)) continue;
    const texts = contentBlocks(e).filter(b => b && b.type === 'text' && typeof b.text === 'string').map(b => b.text);
    if (texts.length) lastText = texts.join('\n');
  }

  const reasons = [];

  // ① 覆盖度闸门 —— 登记过 scope 才生效。
  const openItems = scope.unresolved(sid);
  if (openItems.length) reasons.push(coverageReason(openItems));

  // ② 留尾闸门 —— 只在没登记 scope 时兜底;正当拍板(AskUserQuestion/ExitPlanMode)豁免。
  const hasScope = !!scope.getScope(sid);
  if (!hasScope && lastText && TAIL_RE.test(lastText)) {
    const asked = turnTools.some(b => /^(AskUserQuestion|ExitPlanMode|EnterPlanMode)$/i.test(String(b.name || '')));
    if (!asked) {
      reasons.push('🗡️ 翼德审计(留尾):你的收尾把"还要不要继续"的判断甩回给了勾哥,而本回合没登记 scope、也没走 AskUserQuestion。\n' +
        '勾哥的规矩是一口气做完、不留尾巴:要么现在把剩下的做掉;要么登记 scope 把剩余项写清楚再逐条收敛;要么真需要他拍板就用 AskUserQuestion 给选项,而不是在正文里问。\n' + SCOPE_USAGE);
    }
  }

  // ③ 诚实度闸门 —— 本回合改了文件 + 有完成声明 + 本回合零验证。stop_hook_active 续跑时不重复追问。
  if (input.stop_hook_active !== true && lastText && CLAIM_RE.test(lastText)) {
    const mutated = turnTools.some(b => isMutationTool(b.name));
    const verified = turnTools.some(b => isVerificationTool(b.name, b.input));
    if (mutated && !verified) reasons.push(HONESTY_REASON);
  }

  // 全过 → 清零计数,放行。
  if (!reasons.length) { writeBlocks(sid, null); process.exit(0); }

  // 退化保护:达上限、或两次之间毫无进展 → 放行,不再纠缠。
  const st = readBlocks(sid);
  const sig = scope.signature(sid) + '#' + reasons.length;
  if (st.n >= MAX_BLOCKS || (st.n >= 2 && st.sig === sig)) { writeBlocks(sid, null); process.exit(0); }

  writeBlocks(sid, { n: st.n + 1, sig });
  let reason = reasons.join('\n\n');
  if (st.n + 1 >= MAX_BLOCKS) reason += '\n\n(这是最后一次拦截,下次收尾会放行。若确实做不完,如实说清卡在哪、还差什么,不许把没做完的说成做完了。)';
  process.stdout.write(JSON.stringify({ decision: 'block', reason }));
  process.exit(0);
} catch (e) { process.exit(0); }
