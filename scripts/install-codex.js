#!/usr/bin/env node
// 翼德 · 装进 Codex(每台机器跑一次;重复跑安全,已有的项跳过)。
//
//   node scripts/install-codex.js [--trust <项目目录>]... [--dry-run]
//
// 做四件事:
//   1) 把本仓注册为 Codex 本地 marketplace(guji-tools),并安装 yide@guji-tools
//      → 翼德 hooks(简报/记忆桥/把关/Stop 闸)+ skills 进 Codex。
//   2) config.toml 顶层加 project_doc_fallback_filenames = ["CLAUDE.md"]
//      → Codex 在没有 AGENTS.md 的目录读 CLAUDE.md,和 Claude Code 共用同一份项目说明。
//   3) sandbox_workspace_write.writable_roots 补上 翼德大脑 / ~/.yide-local / Claude 项目记忆
//      → Codex 能登记 scope、写回共用记忆(否则沙箱拦写)。
//   4) --trust 给的目录标 trusted(项目级 .codex 层和 hooks 才生效)。
// 改 config.toml 前先备份为 config.toml.bak-yide-<时间戳>。
// 最后一步只能人做:Codex 里打 /hooks,逐条信任翼德的 hooks(Codex 按 hook 内容哈希记信任,
// hooks.codex.json 不改就只需信任一次)。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execSync } = require('child_process');
const { brainDir } = require(path.join(__dirname, 'lib.js'));
const { localDir } = require(path.join(__dirname, 'store.js'));

const REPO = path.resolve(__dirname, '..');
const MARKET = 'guji-tools';
const PLUGIN = `yide@${MARKET}`;
const CODEX_HOME = process.env.CODEX_HOME || path.join(os.homedir(), '.codex');
const CONFIG = path.join(CODEX_HOME, 'config.toml');

const args = process.argv.slice(2);
const DRY = args.includes('--dry-run');
const trust = [];
for (let i = 0; i < args.length; i++) if (args[i] === '--trust' && args[i + 1]) trust.push(path.resolve(args[++i]));

function codex(argv) {
  // Windows 上 npm 装的 codex 是 .cmd 包装,必须走 shell;参数自己加引号(路径可能带空格)。
  const cmd = ['codex', ...argv.map(a => (/[\s"&|<>^]/.test(a) ? `"${a.replace(/"/g, '\\"')}"` : a))].join(' ');
  return execSync(cmd, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}
function log(s) { process.stdout.write(s + '\n'); }

// ── 1) marketplace + plugin ──
function installPlugin() {
  let listed = '';
  try { listed = codex(['plugin', 'marketplace', 'list']); } catch (e) { listed = String(e.stdout || ''); }
  if (listed.includes(MARKET)) log(`· marketplace ${MARKET} 已在`);
  else if (DRY) log(`[dry] codex plugin marketplace add ${REPO}`);
  else { codex(['plugin', 'marketplace', 'add', REPO]); log(`✓ marketplace ${MARKET} ← ${REPO}`); }

  if (DRY) { log(`[dry] codex plugin add ${PLUGIN}`); return; }
  try { log(codex(['plugin', 'add', PLUGIN]).trim() || `✓ ${PLUGIN} 已安装`); }
  catch (e) {
    const msg = String(e.stderr || e.stdout || e.message);
    if (/already/i.test(msg)) log(`· ${PLUGIN} 已安装`); else throw new Error(`codex plugin add 失败:${msg}`);
  }
}

// ── 2-4) config.toml(不引入 TOML 解析库:只做"缺则插入",不改已有键)──
const tomlStr = p => `'${p}'`;  // TOML 字面量字符串,Windows 反斜杠不用转义
function realOrSelf(p) { try { return fs.realpathSync(p); } catch { return p; } }

function patchConfig() {
  let src = fs.existsSync(CONFIG) ? fs.readFileSync(CONFIG, 'utf8') : '';
  const eol = src.includes('\r\n') ? '\r\n' : '\n';
  let lines = src.split(/\r?\n/);
  const changes = [];

  // 2) 顶层键必须出现在第一个 [table] 之前。
  if (!/^\s*project_doc_fallback_filenames\s*=/m.test(src)) {
    const firstTable = lines.findIndex(l => /^\s*\[/.test(l));
    const at = firstTable < 0 ? lines.length : firstTable;
    lines.splice(at, 0, 'project_doc_fallback_filenames = ["CLAUDE.md"]  # 翼德:没有 AGENTS.md 的目录读 CLAUDE.md,与 Claude Code 共用', '');
    changes.push('project_doc_fallback_filenames = ["CLAUDE.md"]');
  } else if (!/^\s*project_doc_fallback_filenames\s*=.*CLAUDE\.md/m.test(src)) {
    log('⚠ project_doc_fallback_filenames 已存在但不含 CLAUDE.md,未自动改,请手动加上');
  }

  // 3) writable_roots
  const want = [...new Set([
    path.join(os.homedir(), '.yide'), brainDir(), realOrSelf(brainDir()), localDir(), path.join(os.homedir(), '.claude', 'projects'),
  ].map(p => path.resolve(p)))];
  const secIdx = lines.findIndex(l => /^\s*\[sandbox_workspace_write\]\s*(#.*)?$/.test(l));
  if (secIdx < 0) {
    lines.push('', '[sandbox_workspace_write]  # 翼德:scope 状态 / 大脑 / 共用记忆要能写',
      `writable_roots = [${want.map(tomlStr).join(', ')}]`);
    changes.push(`[sandbox_workspace_write] writable_roots += ${want.length} 项`);
  } else {
    let end = lines.findIndex((l, i) => i > secIdx && /^\s*\[/.test(l)); if (end < 0) end = lines.length;
    const wrIdx = lines.findIndex((l, i) => i > secIdx && i < end && /^\s*writable_roots\s*=/.test(l));
    if (wrIdx < 0) {
      lines.splice(secIdx + 1, 0, `writable_roots = [${want.map(tomlStr).join(', ')}]`);
      changes.push(`writable_roots += ${want.length} 项`);
    } else if (/\]\s*(#.*)?$/.test(lines[wrIdx])) {
      const have = new Set([...lines[wrIdx].matchAll(/'([^']*)'|"((?:[^"\\]|\\.)*)"/g)]
        .map(m => (m[1] !== undefined ? m[1] : m[2].replace(/\\\\/g, '\\')).toLowerCase()));
      const add = want.filter(p => !have.has(p.toLowerCase()));
      if (add.length) {
        lines[wrIdx] = lines[wrIdx].replace(/\]\s*(#.*)?$/, m => `${/\[\s*$/.test(lines[wrIdx].split(']')[0]) ? '' : ', '}${add.map(tomlStr).join(', ')}${m}`);
        changes.push(`writable_roots += ${add.join(' ; ')}`);
      }
    } else log('⚠ writable_roots 是多行数组,未自动改;请手动补:' + want.join(' ; '));
  }

  // 4) trust
  for (const dir of trust) {
    const key = dir.toLowerCase();
    if (lines.some(l => l.toLowerCase().includes(`[projects.'${key}']`) || l.toLowerCase().includes(`[projects."${key.replace(/\\/g, '\\\\')}"]`))) continue;
    lines.push('', `[projects.${tomlStr(key)}]`, 'trust_level = "trusted"');
    changes.push(`trusted: ${key}`);
  }

  if (!changes.length) { log('· config.toml 无需改动'); return; }
  if (DRY) { log('[dry] config.toml 将改:\n  ' + changes.join('\n  ')); return; }
  const bak = `${CONFIG}.bak-yide-${Date.now()}`;
  if (src) fs.copyFileSync(CONFIG, bak);
  fs.writeFileSync(CONFIG, lines.join(eol));
  // 写完立刻让 Codex 自己解析一遍;坏了就还原,绝不留一个 Codex 起不来的配置。
  try { codex(['features', 'list']); }
  catch (e) {
    if (src) fs.copyFileSync(bak, CONFIG); else fs.unlinkSync(CONFIG);
    throw new Error('改后的 config.toml Codex 解析失败,已还原。' + String(e.stderr || e.message).split('\n').slice(0, 3).join(' '));
  }
  log('✓ config.toml:\n  ' + changes.join('\n  '));
}

try {
  installPlugin();
  patchConfig();
  log('\n最后一步(只能人做):打开 Codex,输入 /hooks,把翼德的 hooks 逐条 trust。' +
    '\n没 trust 之前 Codex 会跳过它们,简报和共用记忆都不会注入。');
} catch (e) {
  process.stderr.write('✗ ' + (e && e.message || e) + '\n');
  process.exit(1);
}
