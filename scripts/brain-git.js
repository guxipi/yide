#!/usr/bin/env node
// 翼德 · 大脑 git 同步(大脑迁 git 后才生效;非 git 大脑一律 no-op,安全)。
//   pull   —— session-start 用:联网 ff-only 拉最新(失败不阻塞,只报一行)。
//   sync   —— record/consolidate/note/onboard 等写大脑的动作收尾用:add -A + commit + push(push 失败不致命)。
//   status —— doctor 用:dirty / ahead / behind / remote 可达。
// git 自动 commit/push 属"工具自身数据持久化",受 hard-rules 红线⑧定向豁免(见大脑 core/hard-rules.md 用户层)。仅 Node 内置。
'use strict';
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function isGitBrain(dir) { try { return fs.existsSync(path.join(dir, '.git')); } catch { return false; } }
function git(dir, args, timeout) {
  return cp.execFileSync('git', ['-C', dir, ...args], { encoding: 'utf8', timeout: timeout || 8000 });
}
const firstLine = e => String((e && (e.stderr || e.message)) || '').split('\n')[0].trim();

// 联网拉最新(ff-only,不制造 merge)。返回 {git, ok?, msg?}。非 git → {git:false}。
function pull(dir, timeout) {
  if (!isGitBrain(dir)) return { git: false };
  try { git(dir, ['pull', '--ff-only'], timeout || 6000); return { git: true, ok: true }; }
  catch (e) { return { git: true, ok: false, msg: firstLine(e) }; }
}

// add -A + commit + push。无改动 → committed:false。push 失败不致命(committed 仍 true,留下次 sync/联网补推)。
function sync(dir, message) {
  if (!isGitBrain(dir)) return { git: false };
  try {
    git(dir, ['add', '-A']);
    let porcelain = ''; try { porcelain = git(dir, ['status', '--porcelain']); } catch {}
    if (!porcelain.trim()) return { git: true, committed: false, pushed: false };
    git(dir, ['commit', '-m', message || 'yide: 大脑更新']);
    let pushed = false, pushMsg = '';
    try { git(dir, ['push'], 15000); pushed = true; } catch (e) { pushMsg = firstLine(e); }
    return { git: true, committed: true, pushed, pushMsg };
  } catch (e) { return { git: true, error: firstLine(e) }; }
}

function status(dir) {
  if (!isGitBrain(dir)) return { git: false };
  const out = { git: true };
  try { out.dirty = !!git(dir, ['status', '--porcelain']).trim(); } catch {}
  try { const b = git(dir, ['rev-list', '--left-right', '--count', 'HEAD...@{u}']).trim().split(/\s+/); out.ahead = +b[0] || 0; out.behind = +b[1] || 0; } catch { out.noUpstream = true; }
  try { git(dir, ['ls-remote', '--exit-code', 'origin', 'HEAD'], 8000); out.remoteReachable = true; } catch { out.remoteReachable = false; }
  return out;
}

module.exports = { isGitBrain, pull, sync, status };

if (require.main === module) {
  const cmd = process.argv[2];
  const dir = brainDir();
  if (cmd === 'pull') process.stdout.write(JSON.stringify(pull(dir)) + '\n');
  else if (cmd === 'sync') process.stdout.write(JSON.stringify(sync(dir, process.argv[3])) + '\n');
  else if (cmd === 'status') process.stdout.write(JSON.stringify(status(dir)) + '\n');
  else process.stdout.write('用法:node scripts/brain-git.js pull | sync "<信息>" | status\n');
}
