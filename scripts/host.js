'use strict';
// 翼德 · host 适配层:收口 Claude Code / Codex CLI 两个宿主之间的差异,
// 让 scripts/*.js 一份代码同时喂两个 host。差异只有三类:
//   1) 插件根目录:Claude Code=CLAUDE_PLUGIN_ROOT,Codex=PLUGIN_ROOT,裸跑=脚本上一级。
//   2) 项目目录:  Claude Code=CLAUDE_PROJECT_DIR;Codex hook 以 session cwd 运行,payload 亦带 cwd。
//   3) 工具事件输入形状:Claude Code 的 Write/Edit/MultiEdit(tool_input.file_path)
//      vs Codex 的 apply_patch(tool_input.command 里是一段 apply_patch 信封文本)。
// 注入/拦截的 stdout JSON 协议两 host 字节相同(hookSpecificOutput.additionalContext /
// permissionDecision),故不在此收口——各脚本原样 emit 即可。
// 仅用 Node 内置模块。
const path = require('path');

// 插件根目录(带 Codex + 裸跑兜底)。
function pluginRoot() {
  return process.env.CLAUDE_PLUGIN_ROOT || process.env.PLUGIN_ROOT || path.resolve(__dirname, '..');
}

// 项目/仓库目录。Codex hook 以 session cwd 运行,payload 也带 cwd 字段,统一回落 cwd。
function projectDir(input) {
  return process.env.CLAUDE_PROJECT_DIR || (input && typeof input.cwd === 'string' && input.cwd) || process.cwd();
}

// 解析 Codex apply_patch 的命令文本(OpenAI apply_patch 信封格式),抽出 { file_path, files, content }。
// 信封:*** Begin Patch / *** Update File: <p> / *** Add File: <p> / *** Delete File: <p> / 以 + 起头的新增行。
// ⚠️ 此格式据 OpenAI apply_patch 公开文档;Codex hook 传的 tool_input 精确子字段官方未列全,
//    真实 payload 待 Codex 装机后端到端校验(以官方为准)。解析不出文件名即返回 null → 上游 no-op,永不误判。
function parseApplyPatch(command) {
  if (typeof command !== 'string') return null;
  const files = [];
  const added = [];
  for (const line of command.split(/\r?\n/)) {
    const m = line.match(/^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s+(.+?)\s*$/);
    if (m) { files.push(m[1]); continue; }
    // 新增行(+ 起头),排除统一 diff 的 +++ 文件头
    if (/^\+/.test(line) && !/^\+\+\+/.test(line)) added.push(line.replace(/^\+/, ''));
  }
  if (!files.length) return null;
  return { file_path: files[0], files, content: added.join('\n') };
}

// 把任意 host 的工具事件输入,归一成 post-tool-use.js 已认识的形状:
//   tool_input.file_path(改了哪个文件)+ tool_input.content(本次新增文本,供 clean-as-you-code 只报改动行)。
// Claude Code(已有 tool_input.file_path)原样透传;Codex apply_patch 走解析。都不认得就原样返回(上游按无 file_path 处理→no-op)。
function normalizeToolEvent(input) {
  if (!input || typeof input !== 'object') return input;
  const ti = input.tool_input || {};
  if (ti.file_path) return input; // Claude Code Write/Edit/MultiEdit,已是目标形状
  const looksLikePatch = typeof ti.command === 'string' && /\*\*\*\s+Begin Patch/.test(ti.command);
  if (input.tool_name === 'apply_patch' || looksLikePatch) {
    const parsed = parseApplyPatch(ti.command);
    if (parsed) {
      return Object.assign({}, input, {
        tool_input: Object.assign({}, ti, { file_path: parsed.file_path, content: parsed.content, _yideFiles: parsed.files }),
      });
    }
  }
  return input;
}

module.exports = { pluginRoot, projectDir, parseApplyPatch, normalizeToolEvent };
