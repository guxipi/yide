#!/usr/bin/env node
// 翼德 Stop/SubagentStop hook(收尾审计:完成声明 vs 验证证据)。
// 回合收尾时,若 AI 的最终汇报里含"完成/通过/部署成功/已验证"这类声明,
// 但本会话通篇没有跑过任何运行时验证工具(Play/测试/部署/请求),
//   → block 一次并质询,逼它要么补验证贴证据、要么把结论改标 UNVERIFIED。
// 安全模型:
//   - stop_hook_active===true(本次 stop 已是被 block 后的续跑)→ 直接放行,防死循环。
//   - 只在"有完成声明 且 零验证证据"时 block;任何异常(读不到/解析失败)一律静默放行,绝不误伤。
// 仅用 Node 内置模块。
'use strict';
const fs = require('fs');

// 完成/通过声明(保守强匹配,中英)。(?<!un)verified:UNVERIFIED 是合规的"未验证"标注,不算完成声明。
const CLAIM_RE = /(已接通|接通了|部署完成|部署成功|已部署|测试通过|全部通过|验证通过|验收通过|已验证|修复完成|已修复并验证|(?<!un)verified|all tests pass(ed)?|tests? pass(ed)?|deployed successfully|works as expected)/i;
// Bash/PowerShell command 里算"跑过验证"的形态。
const CMD_RE = /(npm (run )?test|node .*test|dotnet (test|build)|pytest|go test|cargo test|ugs |deploy|curl |Invoke-RestMethod|Invoke-WebRequest)/i;

const REASON = '🗡️ 翼德审计:最终汇报含完成/通过声明,但本会话没有任何运行时验证工具调用(没跑过 Play/测试/部署/请求)。要么现在验证并贴证据,要么把相应结论改标 UNVERIFIED 并说明原因——不许维持无证据的完成声明。';

// 读 transcript;>20MB 时只读末尾 5MB(返回 truncated=true 让上游丢掉第一个不完整行)。
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

// 单个 tool_use 是否算运行时验证。
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

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');

  // 1) 被 block 后的续跑 → 直接放行,防死循环。
  if (input.stop_hook_active === true) process.exit(0);

  const fp = input.transcript_path;
  if (!fp || typeof fp !== 'string' || !fs.existsSync(fp)) process.exit(0);

  // 2) 读 transcript(带 tail 上限)。
  const { text, truncated } = readTranscriptTail(fp);
  const lines = text.split(/\r?\n/);
  if (truncated && lines.length) lines.shift();  // 丢掉第一个可能不完整的行
  const entries = [];
  for (const line of lines) {
    const s = line.trim();
    if (!s) continue;
    try { entries.push(JSON.parse(s)); } catch {}
  }

  // 3) 最后一条 assistant 文本消息,拼接其全部 text 块 → 匹配完成声明。
  let lastText = null;
  for (const e of entries) {
    if (!isAssistant(e)) continue;
    const texts = contentBlocks(e)
      .filter(b => b && b.type === 'text' && typeof b.text === 'string')
      .map(b => b.text);
    if (texts.length) lastText = texts.join('\n');
  }
  if (!lastText || !CLAIM_RE.test(lastText)) process.exit(0);

  // 4) 扫全部已读 entry 的 tool_use → 是否存在验证类调用。
  let hasVerification = false;
  for (const e of entries) {
    for (const b of contentBlocks(e)) {
      if (b && b.type === 'tool_use' && isVerificationTool(b.name, b.input)) { hasVerification = true; break; }
    }
    if (hasVerification) break;
  }

  // 5) 有声明 + 零验证 → block;否则放行。
  if (!hasVerification) process.stdout.write(JSON.stringify({ decision: 'block', reason: REASON }));
  process.exit(0);
} catch (e) { process.exit(0); }
