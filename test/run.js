#!/usr/bin/env node
'use strict';
// 翼德 · 自检套件(纯 Node,无依赖)。跑:`node test/run.js` 或 `npm test`。
// 覆盖逻辑最重、最容易回归的几块:glob 匹配、索引自愈、PreToolUse allow/deny/defer、会话健康度、charter 注入。
// 教训(§10):以前全靠手动 node 试,bug 漏到很晚。改完先跑这个。
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const SCRIPTS = path.join(ROOT, 'scripts');

// 临时大脑(隔离,不碰真实 ~/.yide)
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'yide-test-'));
const BRAIN = path.join(TMP, '.yide');
fs.mkdirSync(path.join(BRAIN, '.meta'), { recursive: true });
fs.mkdirSync(path.join(BRAIN, 'core'), { recursive: true });
process.env.YIDE_HOME = BRAIN; // 给本进程内 require 的模块用

let pass = 0, fail = 0;
const fails = [];
function t(name, fn) {
  try { fn(); pass++; console.log('  ✓ ' + name); }
  catch (e) { fail++; fails.push(name); console.log('  ✗ ' + name + '  → ' + (e && e.message)); }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assert failed'); }

// 用 PreToolUse hook 跑一条输入,返回 'allow'|'deny'|'defer'
function preToolDecision(input, env) {
  const out = execFileSync('node', [path.join(SCRIPTS, 'pre-tool-use.js')], {
    input: JSON.stringify(input),
    env: Object.assign({}, process.env, env || {}),
    encoding: 'utf8',
  }).trim();
  if (!out) return 'defer';
  try { return JSON.parse(out).hookSpecificOutput.permissionDecision; } catch { return 'defer'; }
}

console.log('翼德自检:');

// === 1. globToRe(教训 scope 匹配)===
const { globToRe } = require(path.join(SCRIPTS, 'lessons.js'));
t('glob **/*.cs 命中嵌套与根', () => {
  const re = globToRe('**/*.cs');
  assert(re.test('Assets/A/B.cs'), '应命中嵌套');
  assert(re.test('Foo.cs'), '应命中根');
  assert(!re.test('Foo.js'), '不应命中 .js');
});
t('glob Assets/** 命中目录下任意', () => {
  const re = globToRe('Assets/**');
  assert(re.test('Assets/Scripts/Player.cs'), '应命中');
  assert(!re.test('Packages/x.cs'), '不应命中别的目录');
});
t('glob ? 单字符', () => {
  const re = globToRe('Foo?.cs');
  assert(re.test('FooX.cs') && !re.test('Foo.cs'), '? 应恰好一个字符');
});

// === 2. index-util 自愈 ===
const { makeIndex } = require(path.join(SCRIPTS, 'index-util.js'));
t('index-util 构建 + 源变更后自愈重建', () => {
  const dir = path.join(TMP, 'idx');
  fs.mkdirSync(dir, { recursive: true });
  const ip = path.join(dir, 'index.json');
  fs.writeFileSync(path.join(dir, 'a.md'), 'A');
  const idx = makeIndex({
    sourceDir: () => dir, indexPath: () => ip,
    fileFilter: n => /\.md$/.test(n), parse: (f) => ({ name: path.basename(f) }), key: 'items',
  });
  assert(idx.getIndex().length === 1, '初次应 1 条');
  // 把索引 mtime 调到过去,再加一个源文件 → 应重建
  const past = new Date(Date.now() - 60000);
  fs.utimesSync(ip, past, past);
  fs.writeFileSync(path.join(dir, 'b.md'), 'B');
  assert(idx.getIndex().length === 2, '源变更后应自愈到 2 条');
});

// === 3. PreToolUse allow / defer / deny ===
t('allow:只读 bash(git status)', () => assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git status' } }) === 'allow'));
t('allow:只读 MCP(read_console)', () => assert(preToolDecision({ tool_name: 'mcp__unity__read_console', tool_input: {} }) === 'allow'));
t('defer:危险 bash(rm -rf)', () => assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'rm -rf /tmp/x' } }) === 'defer'));
t('defer:写重定向', () => assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'echo hi > f.txt' } }) === 'defer'));
t('defer:Write 工具仍审批', () => assert(preToolDecision({ tool_name: 'Write', tool_input: { file_path: '/a', content: 'x' } }) === 'defer'));
t('defer:mutate MCP(manage_scene)', () => assert(preToolDecision({ tool_name: 'mcp__unity__manage_scene', tool_input: {} }) === 'defer'));
t('deny:命中 hook-rules 且优先于 allow', () => {
  const dbrain = path.join(TMP, 'denybrain', '.yide');
  fs.mkdirSync(path.join(dbrain, '.meta'), { recursive: true });
  fs.writeFileSync(path.join(dbrain, '.meta', 'hook-rules.json'), JSON.stringify({ rules: [{ pattern: 'SECRET_KEY', reason: '密钥', tools: ['*'] }] }));
  const d = preToolDecision({ tool_name: 'Bash', tool_input: { command: 'cat SECRET_KEY.txt' } }, { YIDE_HOME: dbrain });
  assert(d === 'deny', '应 deny(即便 cat 在 allow 白名单)');
});

// === 4. session-health 重开提醒(阈值 + 只发一次)===
const { sessionNudge } = require(path.join(SCRIPTS, 'session-health.js'));
t('session-health:纠正满 3 次才提醒,且只一次', () => {
  const sid = 'test-sess';
  assert(!sessionNudge({ prompt: '不对', session_id: sid }), '第1次不该提醒');
  assert(!sessionNudge({ prompt: '又错了', session_id: sid }), '第2次不该提醒');
  assert(/新会话/.test(sessionNudge({ prompt: '怎么又改坏了', session_id: sid }) || ''), '第3次应提醒重开');
  assert(!sessionNudge({ prompt: '还是不行啊', session_id: sid }), '第4次不该重复提醒');
});

// === 5. charter 注入(SessionStart)===
t('SessionStart 注入 charter + 红线', () => {
  // 用模板大脑跑一次
  const sb = path.join(TMP, 'startbrain', '.yide');
  fs.mkdirSync(path.join(sb, 'core'), { recursive: true });
  for (const f of ['identity.md', 'hard-rules.md', 'charter.md']) {
    fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', f), path.join(sb, 'core', f));
  }
  const out = execFileSync('node', [path.join(SCRIPTS, 'session-start.js')], {
    input: '{}', encoding: 'utf8',
    env: Object.assign({}, process.env, { YIDE_HOME: sb, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP }),
  });
  const ctx = JSON.parse(out).hookSpecificOutput.additionalContext || '';
  assert(ctx.includes('工作准则'), '应含 charter');
  assert(ctx.includes('红线') || ctx.includes('hard-rules'), '应含红线');
});

// === 6. 版本落后提醒(Fix6)===
function startCtx(brainVerOrNull) {
  const vb = path.join(TMP, 'verbrain-' + (brainVerOrNull || 'none'), '.yide');
  fs.mkdirSync(path.join(vb, 'core'), { recursive: true });
  fs.mkdirSync(path.join(vb, '.meta'), { recursive: true });
  for (const f of ['identity.md', 'hard-rules.md', 'charter.md']) fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', f), path.join(vb, 'core', f));
  if (brainVerOrNull) fs.writeFileSync(path.join(vb, '.meta', 'plugin-version.txt'), brainVerOrNull);
  const out = execFileSync('node', [path.join(SCRIPTS, 'session-start.js')], {
    input: '{}', encoding: 'utf8',
    env: Object.assign({}, process.env, { YIDE_HOME: vb, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP }),
  });
  return JSON.parse(out).hookSpecificOutput.additionalContext || '';
}
t('版本落后→提醒 update;不落后/无文件→不提醒', () => {
  assert(/插件已更新/.test(startCtx('0.1.0')), '落后应提醒');
  assert(!/插件已更新/.test(startCtx('99.0.0')), '领先不该提醒');
  assert(!/插件已更新/.test(startCtx(null)), '无版本文件(新用户)不该提醒');
});

// === 7. mockup / 角色镜头 / 战绩判据(本轮新增)===
t('mockup 动作 + 批注层文件齐全', () => {
  assert(fs.existsSync(path.join(ROOT, 'actions', 'mockup.md')), '缺 actions/mockup.md');
  const an = fs.readFileSync(path.join(ROOT, 'templates', 'mockup', 'annotate.html'), 'utf8');
  assert(/复制反馈给翼德/.test(an) && /yd-region/.test(an) && /openPop/.test(an), '批注层应含复制按钮 + 点选组件逻辑');
  assert(!/#yd-ov/.test(an), '批注层不应再有拖拽 overlay');
});
t('4 个角色镜头存在且 frontmatter name 正确', () => {
  for (const n of ['architect', 'ui-ux', 'art-director', 'pm']) {
    const f = path.join(ROOT, 'templates', 'brain', 'experts', n + '.md');
    assert(fs.existsSync(f), '缺镜头 ' + n);
    assert(new RegExp('name:\\s*' + n + '\\b').test(fs.readFileSync(f, 'utf8')), n + ' frontmatter name 不对');
  }
});
t('SKILL 路由含 mockup', () => {
  assert(/actions\/mockup\.md/.test(fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8')), 'SKILL 缺 mockup 路由');
});
t('战绩判据:更新翼德不算、出现于 extraction 注入', () => {
  const eb = path.join(TMP, 'eggbrain', '.yide');
  fs.mkdirSync(path.join(eb, '.meta'), { recursive: true });
  const { extractionContext } = require(path.join(SCRIPTS, 'extraction-context.js'));
  const out = extractionContext(eb, '/some/extraction-raiders', ROOT) || '';
  assert(/战绩判据/.test(out) && /更新翼德/.test(out), '应含"只奖励推进产品、更新翼德不算"的判据');
});

t('项目档案有 UI/UX 预设;mockup 读预设 + 存确认稿文件夹', () => {
  const tpl = fs.readFileSync(path.join(ROOT, 'templates', 'brain', 'projects', '_TEMPLATE.md'), 'utf8');
  assert(/UI\/UX 设计预设/.test(tpl) && /确认线稿文件夹/.test(tpl), '项目模板缺 UI/UX 预设 / 确认稿文件夹');
  const mk = fs.readFileSync(path.join(ROOT, 'actions', 'mockup.md'), 'utf8');
  assert(/UI\/UX 设计预设/.test(mk) && /确认线稿文件夹/.test(mk), 'mockup 应先读预设并存确认稿');
});
t('批注层自动保存(无保存按钮、input 即存)', () => {
  const an = fs.readFileSync(path.join(ROOT, 'templates', 'mockup', 'annotate.html'), 'utf8');
  assert(/addEventListener\('input'/.test(an) && /已自动保存/.test(an), '批注层应边打边自动保存');
  assert(!/id="yd-save"/.test(an), '不应再有"保存"按钮(yd-saved 指示器不算)');
});

t('闭环造鸭:plan 四阶段 + 占位先复用 prefab + 路由', () => {
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/闭环造鸭/.test(p), 'plan 应叫闭环造鸭');
  for (const ph of ['对齐', '造', '验', '交付']) assert(p.includes('· ' + ph) || p.includes('阶段'), '缺阶段 ' + ph);
  assert(/复用\/改造|复用.*prefab|已有的 prefab/.test(p), '占位应先复用项目 prefab 再灰盒');
  assert(/run_tests/.test(p) && /循环到全绿/.test(p), '应有 oracle 验证循环到全绿');
  assert(/actions\/plan\.md/.test(fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8')), 'SKILL 缺 plan 路由');
  assert(/闭环造鸭/.test(fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8')), 'SKILL 应含闭环造鸭触发词');
});

// 清理
try { fs.rmSync(TMP, { recursive: true, force: true }); } catch {}

console.log(`\n结果:${pass} 过 / ${fail} 败` + (fail ? '  →  ' + fails.join(', ') : ''));
process.exit(fail ? 1 : 0);
