#!/usr/bin/env node
// 翼德 · 体检(doctor):一屏自诊断,把"指针断 / hook 没跑 / 预算没配 / SmartMerge 没配"这些
// 出问题唯一兜底="找咕鸡"的项收敛成本机可自查。`node scripts/doctor.js`。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const os = require('os');
const path = require('path');
const { brainDir, locationPointerPath } = require(path.join(__dirname, 'lib.js'));

const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, '..');
const rows = [];
const add = (status, name, detail) => rows.push({ status, name, detail });
const rd = p => { try { return fs.readFileSync(p, 'utf8'); } catch { return null; } };
const exists = p => { try { return fs.existsSync(p); } catch { return false; } };

// ① 大脑指针链
(function () {
  const ptr = (rd(locationPointerPath()) || '').trim();
  const brain = brainDir();
  if (!exists(brain)) {
    add('❌', '大脑目录', `不存在:${brain}${ptr ? `(指针指向 ${ptr})` : ''} —— 同步盘没挂载?或指针指错。`);
    return;
  }
  const hasIndex = exists(path.join(brain, 'INDEX.md'));
  const hasId = exists(path.join(brain, 'core', 'identity.md'));
  if (hasIndex && hasId) add('✅', '大脑指针链', `${brain}(含 INDEX.md + core/identity.md)`);
  else add('❌', '大脑不完整', `${brain} 缺 ${[!hasIndex ? 'INDEX.md' : '', !hasId ? 'core/identity.md' : ''].filter(Boolean).join(' + ')} —— 常见:指针多写一层(…/yide/yide-brain),应指到含 INDEX.md 那层。`);
})();

// ② hook 是否在跑(代理:大脑 .meta/plugin-version.txt 或本机 ephemeral 状态的最近 mtime)
(function () {
  const cands = [
    path.join(brainDir(), '.meta', 'plugin-version.txt'),
    path.join(os.homedir(), '.yide-local', 'session-health.json'),
    path.join(os.homedir(), '.yide-local', 'greet-state.json'),
  ];
  let newest = 0;
  for (const c of cands) { try { const m = fs.statSync(c).mtimeMs; if (m > newest) newest = m; } catch {} }
  if (!newest) { add('⚠️', 'hook 活动', '没找到任何 hook 写过的状态文件 —— 可能插件没装/没 reload,或从没开过会话。'); return; }
  const days = Math.floor((Date.now() - newest) / 86400000);
  add(days <= 7 ? '✅' : '⚠️', 'hook 活动', `最近一次 hook 写状态在 ${days} 天前${days > 7 ? '(有点久,确认插件已 reload)' : ''}。`);
})();

// ③ 插件版本 vs 大脑版本戳
(function () {
  let pv = ''; try { pv = JSON.parse(rd(path.join(PLUGIN_ROOT, '.claude-plugin', 'plugin.json')) || '{}').version || ''; } catch {}
  const bv = (rd(path.join(brainDir(), '.meta', 'plugin-version.txt')) || '').trim();
  if (!pv) add('⚠️', '插件版本', '读不到 plugin.json 版本。');
  else if (!bv) add('⚠️', '版本戳', `插件 v${pv};大脑还没版本戳(新用户或没跑过 migrate,开次会话即写)。`);
  else if (bv === pv) add('✅', '版本同步', `插件与大脑同为 v${pv}。`);
  else add('⚠️', '版本待迁移', `插件 v${pv} ≠ 大脑 v${bv} —— 下次开会话会自动 migrate;有冲突则跑"翼德 update"。`);
})();

// ④ SLASH_COMMAND_TOOL_CHAR_BUDGET(没配 → skill 静默截断风险)
(function () {
  let val = process.env.SLASH_COMMAND_TOOL_CHAR_BUDGET || '';
  if (!val) {
    for (const s of [path.join(os.homedir(), '.claude', 'settings.json'), path.join(process.env.CLAUDE_PROJECT_DIR || '.', '.claude', 'settings.json')]) {
      try { const j = JSON.parse(rd(s) || '{}'); const v = (j.env && j.env.SLASH_COMMAND_TOOL_CHAR_BUDGET) || j.SLASH_COMMAND_TOOL_CHAR_BUDGET; if (v) { val = String(v); break; } } catch {}
    }
  }
  if (val && Number(val) >= 20000) add('✅', 'skill 预算', `SLASH_COMMAND_TOOL_CHAR_BUDGET=${val}(足够)。`);
  else if (val) add('⚠️', 'skill 预算', `SLASH_COMMAND_TOOL_CHAR_BUDGET=${val} 偏小,建议 ≥40000。`);
  else add('⚠️', 'skill 预算', '未配 SLASH_COMMAND_TOOL_CHAR_BUDGET —— 长 skill 描述可能被静默截断(不触发)。在 ~/.claude/settings.json 的 "env" 里加 "SLASH_COMMAND_TOOL_CHAR_BUDGET": "40000"。');
})();

// ⑤ ephemeral 本机目录
(function () {
  const d = process.env.YIDE_LOCAL || path.join(os.homedir(), '.yide-local');
  if (exists(d)) add('✅', '本机私有状态', `${d} 存在。`);
  else add('⚠️', '本机私有状态', `${d} 还没建(首次会话写状态时自动建,正常)。`);
})();

// ⑤b 大脑 git 同步(迁 git 后才有意义;非 git 大脑只提示"还没迁 git")
(function () {
  try {
    const bg = require(path.join(__dirname, 'brain-git.js'));
    const s = bg.status(brainDir());
    if (!s.git) { add('ℹ️', '大脑 git', '大脑还不是 git 仓(仍在同步盘?)—— 迁 git 见报告/迁移脚本。'); return; }
    const parts = [];
    if (s.dirty) parts.push('有未提交改动');
    if (s.noUpstream) parts.push('没配 upstream');
    else { if (s.behind) parts.push(`落后 ${s.behind}`); if (s.ahead) parts.push(`领先 ${s.ahead}(有没推的)`); }
    parts.push(s.remoteReachable ? 'remote 可达' : 'remote 不可达');
    const clean = !s.dirty && !s.behind && !s.noUpstream && s.remoteReachable;
    add(clean ? '✅' : '⚠️', '大脑 git', parts.join('、') + '。');
  } catch { add('⚠️', '大脑 git', '检查失败(git 没装?)。'); }
})();

// ⑥ Unity SmartMerge(.gitconfig 是否配 unityyamlmerge)
(function () {
  const cfg = rd(path.join(os.homedir(), '.gitconfig')) || '';
  if (/unityyamlmerge/i.test(cfg)) add('✅', 'Unity SmartMerge', '.gitconfig 已配 unityyamlmerge(scene/prefab 合并有救)。');
  else add('⚠️', 'Unity SmartMerge', '未配 —— scene/prefab 冲突只能手撕。见 integrations/unity-smartmerge/SETUP.md 一次性配好。');
})();

// ⑦ 可选项(只报未配置,不算错)
(function () {
  const adb = (process.env.PATH || '').split(path.delimiter).some(dir => exists(path.join(dir, 'adb.exe')) || exists(path.join(dir, 'adb')));
  add(adb ? '✅' : 'ℹ️', 'adb(可选)', adb ? '在 PATH。' : '未在 PATH(只有安卓真机 QA 才需要)。');
  add('ℹ️', 'Coplay/STT(可选)', 'MCP/语音转写按需配;此处不自动探测,连不上时查各自 integrations/SETUP.md。');
})();

// 输出
process.stdout.write('🗡️ 翼德体检\n' + '─'.repeat(48) + '\n');
for (const r of rows) process.stdout.write(`${r.status} ${r.name}\n   ${r.detail}\n`);
const bad = rows.filter(r => r.status === '❌').length;
const warn = rows.filter(r => r.status === '⚠️').length;
process.stdout.write('─'.repeat(48) + `\n${bad ? '❌ ' + bad + ' 项要修  ' : ''}${warn ? '⚠️ ' + warn + ' 项注意  ' : ''}${!bad && !warn ? '全部正常 ✅' : ''}\n`);
process.exit(0);
