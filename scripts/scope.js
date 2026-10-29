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
//   node scope.js set    --session <sid> --json '[{"what":"...","verify":"npm test","gate":"visual"}]'   覆盖登记
//                        gate 可省;"visual" = 玩家可见的改动,attest 时必须附本轮新截图(见 checkEvidence)
//   node scope.js add    --session <sid> --json '[{"what":"..."}]'                       追加
//   node scope.js check  --session <sid> [--cwd <dir>]                                   跑 verify,按退出码写状态
//   node scope.js attest --session <sid> --id <id> --evidence "<证据串>"                  无命令可跑时的自证出口
//   node scope.js waive  --session <sid> --id <id> --reason "<理由>"                      显式放弃
//   node scope.js status --session <sid>                                                 打印当前状态(JSON)
//   node scope.js clear  --session <sid>                                                 清空
//   node scope.js help                                                                   打印用法
//
// attest 证据闸门(2026-10-29 勾哥拍板:玩家可见的改动交付前必须真在 Play 里点一遍,证据写截图路径 + dump 结果):
//   ① 证据里出现的每个本地文件路径都必须真实存在;② gate=visual 的条目必须附至少一张存在、且 mtime 不早于登记时间的图片;
//   ③ 除路径外只剩「已完成 / done / 验过」这类空话的一律拒绝。
//
// 落 ~/.yide-local(本机私有、不同步):这是会话级易变状态,进同步盘会 lost update。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const os = require('os');
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

const GATES = new Set(['visual']);
const IMAGE_EXT = /\.(png|jpe?g|webp|gif)$/i;
// 本地文件路径:Windows 盘符(C:\… / C:/…)、Git Bash 风格(/c/…)、~/…;必须以已知后缀结尾。
// 路径体允许空格和中文(本机常见 "My Drive"、"013 美术"),但不跨引号/冒号/逗号句号/括号,防把两段路径或整句话吞进来。
const PATH_RE = /(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![\w:/\\.~])\/[A-Za-z]\/|(?<![\w/\\.])~[\\/])[^:"'\`<>|*?\r\n,;,。;、()()\[\]【】「」]*?\.(?:png|jpe?g|webp|gif|json|txt|log|md)(?![A-Za-z0-9_])/gi;
// 空话词表(大小写不敏感)。证据去掉路径、空白、标点后,如果全由这些词拼成 → 不算证据。
const FILLER = ['已完成', '完成了', '完成', '做完了', '做完', '搞定', '已验证', '验证过', '验证通过', '验证', '已验', '验过', '已测', '测过',
  '测试通过', '测试', '已通过', '通过', '没问题', '正常', '好了', '可以', '已修复', '修好了', '都', '全部', '均', '已', '了', '过', '并', '和',
  'play', 'done', 'ok', 'okay', 'pass', 'passed', 'verified', 'tested', 'tests', 'test', 'works', 'fixed', 'lgtm', 'all', 'and'];
const FILLER_RE = new RegExp(FILLER.slice().sort((a, b) => b.length - a.length).join('|'), 'gi');
const PUNCT_RE = /[\s\p{P}\p{S}]+/gu;

const USAGE = [
  'scope 契约用法(node scope.js <子命令> --session <sid> ...):',
  '  set    --json \'[{"what":"做什么","verify":"能判定成败的命令(可省)","gate":"visual(可省)"}]\'   覆盖登记',
  '  add    --json \'[...]\'                                     追加登记(字段同 set)',
  '  check  [--cwd <dir>]                                        跑 verify,退出码 0 才算 pass',
  '  attest --id <id> --evidence "<具体证据:日志行/截图路径/dump 结果>"   没命令可跑时的自证出口',
  '  waive  --id <id> --reason "<为什么不做了>"',
  '  status / clear / help',
  '字段 gate(可省):"visual" = 玩家可见的改动(UI/画面/手感/交互)。这类条目 attest 时证据里必须有一张',
  '  存在、且在本条 set 之后生成的截图(png/jpg/jpeg/webp/gif,Play 里真点过的),可再附 state dump(.json/.txt/.log)。',
  'attest 证据规则(所有条目):证据里写的每个本地路径都必须真实存在;除路径外只写「已完成 / done / 验过」这类空话一律拒绝。',
].join('\n');

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

// 登记。replace=true 覆盖,false 追加。items:[{what, verify?, shell?, gate?}]
// 每条记 setAt(登记时间),gate=visual 的 attest 用它判截图是不是本轮新拍的。旧数据没有 setAt/gate,读写照常。
function register(sid, items, replace) {
  if (!Array.isArray(items) || !items.length) throw new Error('items 必须是非空数组');
  const all = loadAll();
  const key = sidOf(sid);
  const prev = (!replace && all[key] && Array.isArray(all[key].items)) ? all[key].items : [];
  let seq = prev.reduce((m, i) => Math.max(m, parseInt(i.id, 10) || 0), 0);
  const added = items.slice(0, MAX_ITEMS).map(raw => {
    const what = String((raw && raw.what) || '').trim();
    if (!what) throw new Error('每条必须有 what');
    const gate = raw.gate ? String(raw.gate).trim().toLowerCase() : null;
    if (gate && !GATES.has(gate)) throw new Error('gate 只支持 "visual"(玩家可见的改动),收到:' + raw.gate);
    return {
      id: String(++seq),
      what,
      verify: raw.verify ? String(raw.verify) : null,
      shell: raw.shell ? String(raw.shell) : null,
      state: 'open',
      note: '',
      gate,
      setAt: new Date().toISOString(),
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
      if (item.gate === 'visual' && item.state !== 'attested') {
        // 玩家可见条目:命令过了只算一半,还得 attest 本轮截图才收敛(10-29 交付门)。
        item.note = 'verify 已过;玩家可见条目(gate=visual)还要 attest 附本轮新截图才算收敛';
      } else {
        item.state = 'pass'; item.note = '';
      }
    } catch (e) {
      // Codex 的 Windows 沙箱禁止沙箱内进程再起子进程(cmd.exe / powershell.exe 都是 spawnSync EPERM,2026-10-15 实测)。
      // 这不是验证失败:条目保持原状,提示改走"自己跑 verify → attest 贴退出码和输出"。
      if (/EPERM/.test(String(e && (e.code || e.message)))) {
        item.note = '沙箱禁止起子进程(EPERM),check 跑不了:请直接用你的 shell 工具跑 `' + item.verify + '`,再 attest 贴退出码和关键输出';
        results.push({ id: item.id, state: item.state, note: item.note });
        continue;
      }
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

// 从证据串里抽本地文件路径,返回 [{raw, abs}]。/c/… 在 Windows 上换成 C:/…,~ 展开成 home。
function extractPaths(text) {
  const out = [];
  for (const m of String(text || '').matchAll(PATH_RE)) {
    const raw = m[0];
    let abs = raw;
    if (raw[0] === '~') abs = path.join(os.homedir(), raw.slice(2));
    else if (raw[0] === '/' && process.platform === 'win32') abs = raw[1].toUpperCase() + ':' + raw.slice(2);
    out.push({ raw, abs });
  }
  return out;
}

function statFile(p) { try { const st = fs.statSync(p); return st.isFile() ? st : null; } catch { return null; } }

// attest 证据闸门。不过 → 抛错(CLI 非 0 退出,stderr 带原因)。没有 gate/setAt 的旧条目照样走 ①③,② 只对 gate=visual。
function checkEvidence(item, text) {
  const paths = extractPaths(text);
  const missing = paths.filter(p => !statFile(p.abs));
  if (missing.length) {
    throw new Error('证据里的路径不存在:' + missing.map(p => p.raw + (p.abs !== p.raw ? '(→ ' + p.abs + ')' : '')).join('、') +
      '。截图/dump 要先真生成再贴路径;路径含空格时别跟别的词连写');
  }
  let rest = String(text);
  for (const p of paths) rest = rest.split(p.raw).join(' ');
  rest = rest.replace(PUNCT_RE, '');
  let bare = rest, prev;
  do { prev = bare; bare = bare.replace(FILLER_RE, ''); } while (bare !== prev);
  if (!bare && (rest || !paths.length)) {
    throw new Error('证据只有空话(「' + String(text).trim() + '」)。写具体证据:跑了什么、看到什么——日志行、截图路径、state dump 结果、测试输出末行');
  }
  if (item.gate === 'visual') {
    const since = item.setAt ? Date.parse(item.setAt) : NaN;
    const images = paths.filter(p => IMAGE_EXT.test(p.abs));
    const fresh = images.filter(p => Number.isNaN(since) || statFile(p.abs).mtimeMs >= since);
    if (!fresh.length) {
      const why = !images.length ? '证据里没有图片路径' :
        '图片都早于本条登记时间 ' + item.setAt + ':' + images.map(p => p.raw + ' @ ' + new Date(statFile(p.abs).mtimeMs).toISOString()).join('、');
      throw new Error('条目 #' + item.id + ' 是玩家可见条目(gate=visual):玩家可见条目要附本轮新截图路径(Play 里真点过的),可再附 state dump。(' + why + ')');
    }
  }
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
  if (state === 'attested') checkEvidence(item, t);
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
    if (!raw) throw new Error('缺 --json\n' + USAGE);
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
    default: throw new Error('未知子命令:' + cmd + '\n' + USAGE);
  }
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  if (!argv[0] || argv[0] === 'help' || argv[0] === '--help' || argv[0] === '-h') { process.stdout.write(USAGE + '\n'); process.exit(0); }
  try {
    process.stdout.write(JSON.stringify(main(argv), null, 2) + '\n');
    process.exit(0);
  } catch (e) {
    process.stderr.write('scope: ' + ((e && e.message) || e) + '\n');
    process.exit(1);
  }
}

module.exports = { getScope, unresolved, signature, register, check, mark, clear, extractPaths, checkEvidence, UNRESOLVED, USAGE };
