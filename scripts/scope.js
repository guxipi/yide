#!/usr/bin/env node
// 翼德 scope 契约:把"这回合要做完什么"从自然语言变成机器可读、可证伪的清单。
//
// 为什么要有它:AI 留尾巴有两个正交病根 —— 覆盖度(该做的没做完)和诚实度(没做完却说做完)。
// 诚实度由 stop-audit 的证据闸门管;覆盖度管不了,因为"完成"只活在自然语言里,只能靠 AI 自评,
// 而自评天然偏向"已完成"(reward hacking:训练里改 checklist 让未完成看起来完成)。
// 解法是把 checklist 移到进程外:**条目由 AI 登记(此时没有完成压力),状态由验收命令的退出码写**。
//
// 状态机(单向收敛,除 set/add 外没有回到 open 的路径):
//   open      刚登记,未处理
//   pass      verify 命令退出码 0 —— 唯一的硬证据状态
//   fail      verify 命令非 0(仍算未完成,会被闸门拦)
//   attested  没有可执行 verify(如 Play Mode 目测),AI 自证 + 必须留下具体证据串
//   waived    显式放弃,必须带理由(勾哥改主意 / 阻塞了)
//
// CLI(hook 与 AI 都用这个;所有子命令读 --session,缺省 nosid):
//   node scope.js set    --session <sid> --json '[{"what":"...","verify":"npm test"}]'   覆盖登记
//   node scope.js add    --session <sid> --json '[{"what":"..."}]'                       追加
//   node scope.js check  --session <sid> [--cwd <dir>]                                   跑 verify,按退出码写状态
//   node scope.js attest --session <sid> --id <id> --evidence "<证据串>"                  无命令可跑时的自证出口
//   node scope.js waive  --session <sid> --id <id> --reason "<理由>"                      显式放弃
//   node scope.js status --session <sid>                                                 打印当前状态(JSON)
//   node scope.js clear  --session <sid>                                                 清空
//
// 落 ~/.yide-local(本机私有、不同步):这是会话级易变状态,进同步盘会 lost update。仅 Node 内置模块。
'use strict';
const path = require('path');
const { execSync } = require('child_process');
const { readLocalJson, writeLocalJson } = require(path.join(__dirname, 'store.js'));

const FILE = 'scope.json';
const MAX_SESSIONS = 20;      // 防无界增长:只留最近 20 个会话
const MAX_ITEMS = 40;         // 单会话条目上限,防刷屏
const VERIFY_TIMEOUT = 180000;
const OUT_CAP = 400;          // 单条 verify 输出截断,别把 hook reason 撑爆

// open + fail 都算"未处理" —— fail 尤其重要:跑了但没过,不能算交付。
const UNRESOLVED = new Set(['open', 'fail']);

function loadAll() { return readLocalJson(FILE, {}) || {}; }

function saveAll(all) {
  const keys = Object.keys(all);
  if (keys.length > MAX_SESSIONS) for (const k of keys.slice(0, keys.length - MAX_SESSIONS)) delete all[k];
  return writeLocalJson(FILE, all, true);
}

function sidOf(sid) { return sid || 'nosid'; }

// 读某会话的 scope;没有/结构不对 → null(调用方据此判断"根本没登记")。
function getScope(sid) {
  const s = loadAll()[sidOf(sid)];
  return s && Array.isArray(s.items) ? s : null;
}

function unresolved(sid) {
  const s = getScope(sid);
  return s ? s.items.filter(i => UNRESOLVED.has(i.state)) : [];
}

// 未处理条目的签名:用来判断两次 stop 之间有没有真进展(签名不变 = 空转)。
function signature(sid) {
  return unresolved(sid).map(i => i.id + ':' + i.state).join('|');
}

// 登记。replace=true 覆盖,false 追加。items:[{what, verify?, shell?}]
function register(sid, items, replace) {
  if (!Array.isArray(items) || !items.length) throw new Error('items 必须是非空数组');
  const all = loadAll();
  const key = sidOf(sid);
  const prev = (!replace && all[key] && Array.isArray(all[key].items)) ? all[key].items : [];
  let seq = prev.reduce((m, i) => Math.max(m, parseInt(i.id, 10) || 0), 0);
  const added = items.slice(0, MAX_ITEMS).map(raw => {
    const what = String((raw && raw.what) || '').trim();
    if (!what) throw new Error('每条必须有 what');
    return {
      id: String(++seq),
      what,
      verify: raw.verify ? String(raw.verify) : null,
      shell: raw.shell ? String(raw.shell) : null,
      state: 'open',
      note: '',
    };
  });
  const merged = prev.concat(added).slice(-MAX_ITEMS);
  delete all[key];                                   // 删了再插 = 移到最新(saveAll 按插入序裁最旧)
  all[key] = { updatedAt: new Date().toISOString(), items: merged };
  saveAll(all);
  return merged;
}

// 跑 verify:退出码 0 → pass,非 0 → fail(note 记末尾输出)。
// 已 waived 的跳过;没有 verify 命令的保持原状(它们只能走 attest)。
function check(sid, cwd) {
  const all = loadAll();
  const key = sidOf(sid);
  const s = all[key];
  if (!s || !Array.isArray(s.items)) throw new Error('本会话没有登记 scope');
  const results = [];
  for (const item of s.items) {
    if (item.state === 'waived' || !item.verify) { results.push({ id: item.id, state: item.state, skipped: !item.verify }); continue; }
    const opts = { encoding: 'utf8', timeout: VERIFY_TIMEOUT, stdio: ['ignore', 'pipe', 'pipe'], cwd: cwd || process.cwd() };
    if (item.shell) opts.shell = item.shell;
    try {
      execSync(item.verify, opts);
      item.state = 'pass'; item.note = '';
    } catch (e) {
      item.state = 'fail';
      const tail = String((e && (e.stderr || e.stdout)) || (e && e.message) || '').trim();
      item.note = tail.length > OUT_CAP ? tail.slice(-OUT_CAP) : tail;
    }
    results.push({ id: item.id, state: item.state, note: item.note });
  }
  s.updatedAt = new Date().toISOString();
  saveAll(all);
  return results;
}

// 改单条状态的共用路径(attest / waive)。text 是强制的:自证要证据,放弃要理由。
function mark(sid, id, state, text, label) {
  const t = String(text || '').trim();
  if (t.length < 4) throw new Error(label + '不能为空(要具体,不是"已完成")');
  const all = loadAll();
  const s = all[sidOf(sid)];
  if (!s || !Array.isArray(s.items)) throw new Error('本会话没有登记 scope');
  const item = s.items.find(i => i.id === String(id));
  if (!item) throw new Error('找不到条目 id=' + id);
  item.state = state;
  item.note = t;
  s.updatedAt = new Date().toISOString();
  saveAll(all);
  return item;
}

function clear(sid) {
  const all = loadAll();
  delete all[sidOf(sid)];
  return saveAll(all);
}

// ── CLI ──
function argOf(argv, name) {
  const i = argv.indexOf('--' + name);
  return i >= 0 && i + 1 < argv.length ? argv[i + 1] : null;
}

function main(argv) {
  const cmd = argv[0];
  const sid = argOf(argv, 'session');
  const json = () => {
    const raw = argOf(argv, 'json');
    if (!raw) throw new Error('缺 --json');
    return JSON.parse(raw);
  };
  switch (cmd) {
    case 'set':    return register(sid, json(), true);
    case 'add':    return register(sid, json(), false);
    case 'check':  return check(sid, argOf(argv, 'cwd'));
    case 'attest': return mark(sid, argOf(argv, 'id'), 'attested', argOf(argv, 'evidence'), '证据');
    case 'waive':  return mark(sid, argOf(argv, 'id'), 'waived', argOf(argv, 'reason'), '理由');
    case 'status': return getScope(sid) || { items: [] };
    case 'clear':  return { cleared: clear(sid) };
    default: throw new Error('未知子命令:' + cmd + '(set/add/check/attest/waive/status/clear)');
  }
}

if (require.main === module) {
  try {
    process.stdout.write(JSON.stringify(main(process.argv.slice(2)), null, 2) + '\n');
    process.exit(0);
  } catch (e) {
    process.stderr.write('scope: ' + ((e && e.message) || e) + '\n');
    process.exit(1);
  }
}

module.exports = { getScope, unresolved, signature, register, check, mark, clear, UNRESOLVED };
