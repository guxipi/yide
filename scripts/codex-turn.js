'use strict';
// 翼德 · 读 Codex rollout(transcript_path),拿"本回合"的用户原话和工具调用。
// rollout 是 jsonl:session_meta(含 source:exec / 桌面端等)、event_msg.user_message(用户发言)、
// response_item 里的 custom_tool_call / function_call(工具调用;代码模式下是一个 exec,
// input 是一段 JS,里面 tools.apply_patch(...) / tools.exec_command(...) / tools.mcp__…(...))。
// 格式不是 Codex 承诺的稳定接口:任何解析失败都返回 null,调用方一律放行,只会漏拦不会误拦。
// 仅用 Node 内置模块。
const fs = require('fs');

function readTail(fp, max) {
  const st = fs.statSync(fp);
  if (st.size <= max) return { text: fs.readFileSync(fp, 'utf8'), truncated: false };
  const fd = fs.openSync(fp, 'r');
  try {
    const buf = Buffer.alloc(max);
    const n = fs.readSync(fd, buf, 0, max, st.size - max);
    return { text: buf.toString('utf8', 0, n), truncated: true };
  } finally { fs.closeSync(fd); }
}

// 返回 { source, userPrompt, calls:[{ name, text }] } 或 null。
function readCodexTurn(fp) {
  try {
    if (!fp || typeof fp !== 'string' || !fs.existsSync(fp)) return null;
    // session_meta 永远在第一行;尾部另读 8MB 找本回合。
    let source = '';
    try {
      const fd = fs.openSync(fp, 'r');
      const buf = Buffer.alloc(64 * 1024);
      const n = fs.readSync(fd, buf, 0, buf.length, 0);
      fs.closeSync(fd);
      const first = buf.toString('utf8', 0, n).split(/\r?\n/)[0];
      const meta = JSON.parse(first);
      // 实测取值:exec(codex exec,多为 Claude 派单)、vscode(桌面端/IDE 的交互会话)、对象(子 agent)。
      if (meta && meta.type === 'session_meta') {
        const s = meta.payload && (meta.payload.source || meta.payload.originator);
        source = s && typeof s === 'object' ? 'subagent' : String(s || '');
      }
    } catch {}
    const { text, truncated } = readTail(fp, 8 * 1024 * 1024);
    const lines = text.split(/\r?\n/);
    if (truncated) lines.shift();
    const entries = [];
    for (const l of lines) { const s = l.trim(); if (!s) continue; try { entries.push(JSON.parse(s)); } catch {} }
    let start = -1;
    for (let i = entries.length - 1; i >= 0; i--) {
      const e = entries[i];
      const p = e && e.type === 'event_msg' ? e.payload : null;
      // 真实用户发言 = item_completed 里 item.type 为 UserMessage(hook 注入的续跑提示不走这里)。
      if (p && ((p.type === 'item_completed' && p.item && p.item.type === 'UserMessage') || p.type === 'user_message')) { start = i; break; }
    }
    if (start < 0) return null;
    const sp = entries[start].payload;
    const userPrompt = sp.type === 'user_message'
      ? String(sp.message || '')
      : (Array.isArray(sp.item.content) ? sp.item.content.map(c => (c && c.text) || '').join('\n') : '');
    const calls = [];
    for (let i = start + 1; i < entries.length; i++) {
      const p = entries[i] && entries[i].type === 'response_item' ? entries[i].payload : null;
      if (!p) continue;
      if (p.type !== 'custom_tool_call' && p.type !== 'function_call' && p.type !== 'local_shell_call') continue;
      if (p.name === 'wait') continue;  // 代码模式的轮询,不算一次工具调用
      const body = typeof p.input === 'string' ? p.input : (typeof p.arguments === 'string' ? p.arguments : JSON.stringify(p.action || p.arguments || ''));
      calls.push({ name: String(p.name || p.type), text: body });
    }
    return { source, userPrompt, calls };
  } catch { return null; }
}

module.exports = { readCodexTurn };
