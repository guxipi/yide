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
process.env.YIDE_LOCAL = path.join(TMP, '.yide-local'); // 本机私有状态隔离到临时目录(别碰真实 ~/.yide-local)

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
  fs.writeFileSync(path.join(sb, 'INDEX.md'), '# index'); // 健康大脑要过完整性哨兵
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
  fs.writeFileSync(path.join(vb, 'INDEX.md'), '# index'); // 健康大脑要过完整性哨兵
  if (brainVerOrNull) fs.writeFileSync(path.join(vb, '.meta', 'plugin-version.txt'), brainVerOrNull);
  const out = execFileSync('node', [path.join(SCRIPTS, 'session-start.js')], {
    input: '{}', encoding: 'utf8',
    env: Object.assign({}, process.env, { YIDE_HOME: vb, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP }),
  });
  return JSON.parse(out).hookSpecificOutput.additionalContext || '';
}
t('版本落后→一行"已更新"提示;不落后/无文件→不提示', () => {
  assert(/已更新到 v/.test(startCtx('0.1.0')), '落后应提示已自动更新');
  assert(!/已更新到 v/.test(startCtx('99.0.0')), '领先不该提示');
  assert(!/已更新到 v/.test(startCtx(null)), '无版本文件(新用户)不该提示');
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

t('闭环造鸭:plan 四阶段 + 路由', () => {
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/闭环造鸭/.test(p), 'plan 应叫闭环造鸭');
  for (const ph of ['对齐', '造', '验', '交付']) assert(p.includes('· ' + ph) || p.includes('阶段'), '缺阶段 ' + ph);
  assert(/run_tests/.test(p) && /自动验到全绿/.test(p), '应有 oracle 验证到全绿');
  const skill = fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8');
  assert(/actions\/plan\.md/.test(skill) && /闭环造鸭/.test(skill), 'SKILL 缺 plan 路由/闭环造鸭触发词');
});
t('闭环造鸭:producer 改进 8 条都在', () => {
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/验收分层|逻辑·自动测/.test(p) && /手感·试玩/.test(p), '缺验收分三层(治假绿)');
  assert(/接口盘点/.test(p), '缺接口盘点(治集成屎山)');
  assert(/竖切|垂直切片/.test(p), '缺垂直切片优先(治失控/早反馈)');
  assert(/隔离|additive/.test(p), '缺隔离开发');
  assert(/掉线/.test(p) && /(上限|卡住)/.test(p), '缺循环护栏(掉线降级/上限/卡住)');
  assert(/可调参数|config/.test(p), '缺可调参数集中(治试玩回流)');
  assert(/试玩清单/.test(p), '缺试玩清单(治不信绿)');
  assert(/\[假设\]|智能默认/.test(p), '缺智能默认(治几句话太模糊)');
  assert(/借皮/.test(p), '缺 prefab 只借皮');
});

t('闭环造鸭:开造前检查点 + 失败回滚(归 plan,不另起动作)', () => {
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/检查点/.test(p) && /git stash/.test(p) && /专用分支|yide\/闭环/.test(p), '缺"开造前问勾哥建检查点(stash+专用分支)"');
  assert(/回滚/.test(p) && /一个单位/.test(p) && /\.checkpoint/.test(p), '缺失败回滚(整段一次撤 + 读 checkpoint)');
  assert(/回滚/.test(fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8')), 'SKILL plan 路由应含回滚触发词');
});

t('测试分工:玩法以 PlayMode 为真值(plan + unity.md)', () => {
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/PlayMode 为真值|玩法以 PlayMode/.test(p) && !/EditMode 优先/.test(p), 'plan 应改成按层分工、玩法以 PlayMode 为真值');
  const u = fs.readFileSync(path.join(ROOT, 'templates', 'brain', 'style', 'unity.md'), 'utf8');
  assert(/EditMode/.test(u) && /PlayMode/.test(u) && /真值/.test(u), 'unity.md 应有 EditMode/PlayMode 分工知识');
});

t('resolve:发货默认+用户层 读取时合并(去重不拆 + 自定义 + 禁用)', () => {
  const { resolve } = require(path.join(SCRIPTS, 'resolve.js'));
  const rb = path.join(TMP, 'resolvebrain', '.yide');
  fs.mkdirSync(path.join(rb, 'core'), { recursive: true });
  fs.mkdirSync(path.join(rb, '.meta'), { recursive: true });
  // 模拟"旧大脑":用户层 = 发货 6 条默认(原样) + 1 条自定义
  const shipped = fs.readFileSync(path.join(ROOT, 'templates', 'brain', 'core', 'hard-rules.md'), 'utf8');
  fs.writeFileSync(path.join(rb, 'core', 'hard-rules.md'), shipped + '\n7. **[sev:7]** IMPORTANT — 测试自定义规则。(防测试)\n');

  let out = resolve('hard-rules', ROOT, rb);
  assert(/防测试/.test(out), '应保留用户自定义红线');
  assert((out.match(/防"hackfix"/g) || []).length === 1, '默认红线不该因"旧大脑也有"而重复(去重不拆)');

  // 禁用某条默认
  fs.writeFileSync(path.join(rb, '.meta', 'redline-suppress.json'), JSON.stringify(['防"hackfix"']));
  out = resolve('hard-rules', ROOT, rb);
  assert(!/防"hackfix"/.test(out), '被 suppress 的默认应消失');
  assert(/防测试/.test(out), 'suppress 不影响自定义');

  // charter 读发货
  assert(/工作准则/.test(resolve('charter', ROOT, rb)), 'charter 应能从插件读到');
});

t('adb 只读取证放行;adb shell/install 仍审批', () => {
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'adb logcat -d' } }) === 'allow', 'adb logcat 应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'adb devices' } }) === 'allow', 'adb devices 应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'adb pull /sdcard/x .' } }) === 'allow', 'adb pull 应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'adb shell rm -rf /sdcard' } }) === 'defer', 'adb shell 应回落审批');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'adb install app.apk' } }) === 'defer', 'adb install 应回落审批');
});
t('安卓真机 QA:全绿才惊动勾哥、真机可选、adb+SOP', () => {
  const q = fs.readFileSync(path.join(ROOT, 'actions', 'qa.md'), 'utf8');
  assert(/安卓真机/.test(q) && /adb pull/.test(q) && /EvidenceCapture/.test(q), 'qa 缺安卓真机取证流程');
  assert(/全绿/.test(q) && /可选/.test(q), 'qa 缺"全绿才惊动勾哥、真机可选"');
  const p = fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8');
  assert(/真机实测.*可选|可选.*真机/.test(p) && /全绿.*惊动勾哥/.test(p), 'plan 阶段四缺"全绿才惊动、真机可选"');
  assert(fs.existsSync(path.join(ROOT, 'integrations', 'android', 'SETUP.md')), '缺 integrations/android/SETUP.md');
});

t('手感反馈表(交互)+ 联合优化回流', () => {
  const ff = fs.readFileSync(path.join(ROOT, 'templates', 'qa', 'feel-form.html'), 'utf8');
  assert(/yd-feel/.test(ff) && /提交反馈给翼德/.test(ff) && /还行/.test(ff) && /要改/.test(ff), 'feel-form 缺交互选项/提交按钮');
  const q = fs.readFileSync(path.join(ROOT, 'actions', 'qa.md'), 'utf8');
  assert(/feel-form/.test(q) && /art-director/.test(q) && /ui-ux/.test(q) && /定夺/.test(q), 'qa 缺"交互手感表 + 联合优化(数值/设计+PM)供勾哥定夺"');
});

t('项目文档管理:docs + 自动加载用 CLAUDE.md(非 AGENTS.md)+ SETUP + 模板', () => {
  const d = fs.readFileSync(path.join(ROOT, 'actions', 'docs.md'), 'utf8');
  assert(/CLAUDE\.md/.test(d) && /\.cache\/confluence/.test(d) && /导出/.test(d), 'docs 缺三层(源/镜像/CLAUDE.md)');
  assert(/不是 `AGENTS\.md`|不读 `AGENTS\.md`|不是 AGENTS\.md/.test(d) || /自动加载的是.*CLAUDE\.md/.test(d), 'docs 应写明自动加载的是 CLAUDE.md 不是 AGENTS.md');
  assert(/7\s*天|懒同步/.test(d) && /增量/.test(d), 'docs 缺 7 天懒同步/增量');
  const skill = fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8');
  assert(/actions\/docs\.md/.test(skill) && /项目文档/.test(skill), 'SKILL 缺 docs 路由');
  assert(fs.existsSync(path.join(ROOT, 'integrations', 'confluence', 'SETUP.md')), '缺 confluence SETUP');
  assert(/CLAUDE\.md/.test(fs.readFileSync(path.join(ROOT, 'actions', 'plan.md'), 'utf8')), 'plan 读 context 应含 CLAUDE.md');
  assert(/项目文档/.test(fs.readFileSync(path.join(ROOT, 'templates', 'brain', 'projects', '_TEMPLATE.md'), 'utf8')), '项目模板缺 项目文档 段');
});

t('playtest 冻帧标注:action + 路由 + Unity 工具 + 处理脚本 + Google STT + SETUP', () => {
  // action:冻帧标注 / 转写 / 带定位问题清单 / 回流 / 降级 / 铁律
  const a = fs.readFileSync(path.join(ROOT, 'actions', 'playtest.md'), 'utf8');
  assert(/冻帧标注/.test(a) && /转写/.test(a), 'playtest action 缺 冻帧标注 / 转写');
  assert(/命中.*元素|hitPath|带定位/.test(a), 'playtest action 缺 命中元素/带定位(直通代码的卖点)');
  assert(/联合优化回流|art-director/.test(a) && /降级/.test(a), 'playtest action 缺 回流 / 降级');
  assert(/playtest\.js/.test(a) && /F8/.test(a) && /铁律/.test(a), 'playtest action 缺 跑脚本 / F8 / 铁律');
  // SKILL 路由
  const skill = fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8');
  assert(/actions\/playtest\.md/.test(skill) && /playtest/.test(skill), 'SKILL 缺 playtest 路由');
  // Unity 工具(运行时 + 编辑器窗口)+ Google STT 流式转写 + SETUP
  const cs = fs.readFileSync(path.join(ROOT, 'templates', 'qa', 'PlaytestMarker.cs'), 'utf8');
  // 录音已移到编辑器侧 Python 持麦(流式),运行时只管冻帧/截图/命中射线 + 三段状态机
  assert(/Time\.timeScale/.test(cs) && /RaycastAll/.test(cs), 'PlaytestMarker.cs 缺 冻帧/命中射线');
  assert(/UNITY_EDITOR \|\| DEVELOPMENT_BUILD/.test(cs), 'PlaytestMarker.cs 应只在编辑器/Dev包编译,不进正式包');
  assert(/MarkPhase/.test(cs) && /StopRecord/.test(cs), 'PlaytestMarker.cs 缺 三段状态机/停录(停录后转写回填)');
  assert(fs.existsSync(path.join(ROOT, 'templates', 'qa', 'Editor', 'PlaytestMarkerWindow.cs')), '缺 编辑器停靠窗口(不挡游戏)');
  const asr = fs.readFileSync(path.join(ROOT, 'templates', 'qa', 'Editor', 'PlaytestAsrServer.cs'), 'utf8');
  assert(/BeginStream/.test(asr) && /EndStream/.test(asr), 'PlaytestAsrServer.cs 缺 流式转写驱动(BeginStream/EndStream)');
  assert(fs.existsSync(path.join(ROOT, 'integrations', 'playtest-capture', 'stt_google.py')), '缺 Google STT 转写脚本(双模式:Unity stdin 常驻 + playtest.js 批量)');
  const stt = fs.readFileSync(path.join(ROOT, 'integrations', 'playtest-capture', 'stt_google.py'), 'utf8');
  assert(/chirp_3/.test(stt) && /speech_v2/.test(stt) && /__READY__/.test(stt), 'stt_google.py 缺 Chirp3/v2/常驻就绪标记');
  assert(fs.existsSync(path.join(ROOT, 'integrations', 'playtest-capture', 'SETUP.md')), '缺 playtest SETUP');
});
t('playtest 脚本:--help 正常退出并打印用法(冻帧标注模式)', () => {
  const out = execFileSync('node', [path.join(SCRIPTS, 'playtest.js'), '--help'], { encoding: 'utf8' });
  assert(/playtest/.test(out) && /no-asr/.test(out), '--help 应打印用法(含 --no-asr)');
});
t('playtest 跨项目护栏:Unity 写来源项目 + 混项目告警 + 单项目显示来源', () => {
  // Unity 端:context.json 写来源项目 + ProjectId helper(工程文件夹名)
  const cs = fs.readFileSync(path.join(ROOT, 'templates', 'qa', 'PlaytestMarker.cs'), 'utf8');
  assert(/\\"project\\"/.test(cs) && /ProjectId\(\)/.test(cs), 'PlaytestMarker.cs 应把来源项目写进 context.json');
  assert(/Directory\.GetParent\(Application\.dataPath\)/.test(cs), 'ProjectId 应取工程文件夹名(天然每工程唯一)');
  // 处理端:构造 session 跑 playtest.js,验告警/显示
  function runPlaytest(projects) {
    const proj = path.join(TMP, 'ptproj-' + projects.join('_'));
    const sess = path.join(proj, 'QA', 'playtest', 'session-20260101-000000');
    fs.mkdirSync(sess, { recursive: true });
    projects.forEach((p, i) => {
      const md = path.join(sess, 'marker-' + String(i + 1).padStart(2, '0'));
      fs.mkdirSync(md, { recursive: true });
      fs.writeFileSync(path.join(md, 'context.json'), JSON.stringify({ index: i + 1, scene: 'S', project: p, typedNote: 'x' }));
    });
    return execFileSync('node', [path.join(SCRIPTS, 'playtest.js'), '--no-asr'], {
      encoding: 'utf8', env: Object.assign({}, process.env, { CLAUDE_PROJECT_DIR: proj }),
    });
  }
  const mixed = runPlaytest(['ER', 'OtherGame']);
  assert(/文件串项目/.test(mixed) && /ER/.test(mixed) && /OtherGame/.test(mixed), '混入多项目应告警并列出两者');
  assert(/SessionRoot/.test(mixed) && /留空/.test(mixed), '告警应给修复路径(SessionRoot 留空)');
  const single = runPlaytest(['SoloGame']);
  assert(/来源项目:SoloGame/.test(single) && !/文件串项目/.test(single), '单项目应显示来源且不告警');
});

// === 8b. store 本机私有状态 + 原子写(2026-07-02 audit Phase 1)===
t('1.1 writeLocal 落 localDir 而非 .meta;readLocal 本机无值时回退共享(平滑迁移)', () => {
  const sbrain = path.join(TMP, 'storebrain', '.yide');
  const slocal = path.join(TMP, 'storelocal');
  fs.mkdirSync(path.join(sbrain, '.meta'), { recursive: true });
  fs.mkdirSync(slocal, { recursive: true });
  // 用独立 env 加载一份 store(隔离,不污染全局 process.env)
  delete require.cache[require.resolve(path.join(SCRIPTS, 'store.js'))];
  delete require.cache[require.resolve(path.join(SCRIPTS, 'lib.js'))];
  const savedHome = process.env.YIDE_HOME, savedLocal = process.env.YIDE_LOCAL;
  process.env.YIDE_HOME = sbrain; process.env.YIDE_LOCAL = slocal;
  const store = require(path.join(SCRIPTS, 'store.js'));
  // 旧共享副本存在、本机还没有 → readLocal 应回退取到旧值
  fs.writeFileSync(path.join(sbrain, '.meta', 'greet-state.json'), JSON.stringify({ lastGreetDate: '2020-01-01' }));
  assert(store.readLocalJson('greet-state.json', {}).lastGreetDate === '2020-01-01', '本机无值应回退读共享旧副本');
  // 写:落 localDir,不再碰共享
  store.writeLocalJson('greet-state.json', { lastGreetDate: '2026-07-02' });
  assert(fs.existsSync(path.join(slocal, 'greet-state.json')), '应写到 localDir');
  assert(store.readLocalJson('greet-state.json', {}).lastGreetDate === '2026-07-02', '之后应优先读本机值');
  assert(JSON.parse(fs.readFileSync(path.join(sbrain, '.meta', 'greet-state.json'), 'utf8')).lastGreetDate === '2020-01-01', 'writeLocal 不该改共享旧副本(留 migrate 清理)');
  // 恢复
  process.env.YIDE_HOME = savedHome; process.env.YIDE_LOCAL = savedLocal;
  delete require.cache[require.resolve(path.join(SCRIPTS, 'store.js'))];
  delete require.cache[require.resolve(path.join(SCRIPTS, 'lib.js'))];
});
t('1.2 原子写:写后无残留 .tmp;并发覆盖不产生半截文件', () => {
  const abrain = path.join(TMP, 'atomicbrain', '.yide');
  fs.mkdirSync(path.join(abrain, '.meta'), { recursive: true });
  delete require.cache[require.resolve(path.join(SCRIPTS, 'store.js'))];
  delete require.cache[require.resolve(path.join(SCRIPTS, 'lib.js'))];
  const savedHome = process.env.YIDE_HOME;
  process.env.YIDE_HOME = abrain;
  const store = require(path.join(SCRIPTS, 'store.js'));
  store.writeJson('game-state.json', { streak: 3 }, true);
  assert(!fs.existsSync(path.join(abrain, '.meta', 'game-state.json.tmp')), '不该留 .tmp 残留');
  assert(store.readJson('game-state.json', {}).streak === 3, '原子写内容应正确');
  process.env.YIDE_HOME = savedHome;
  delete require.cache[require.resolve(path.join(SCRIPTS, 'store.js'))];
  delete require.cache[require.resolve(path.join(SCRIPTS, 'lib.js'))];
});

// === 8c. 大脑完整性哨兵 + 降级简报(2026-07-02 audit Phase 1.3/1.4)===
function runStart(env) {
  const out = execFileSync('node', [path.join(SCRIPTS, 'session-start.js')], {
    input: '{}', encoding: 'utf8', env: Object.assign({}, process.env, env),
  });
  return JSON.parse(out).hookSpecificOutput;
}
t('1.3 大脑不完整(缺 INDEX.md)→ 报警、不当正常大脑、不 onboard', () => {
  const ib = path.join(TMP, 'incompletebrain', '.yide');
  fs.mkdirSync(path.join(ib, 'core'), { recursive: true });
  fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', 'identity.md'), path.join(ib, 'core', 'identity.md'));
  const o = runStart({ YIDE_HOME: ib, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP });
  assert(/大脑不完整/.test(o.additionalContext), '应报"大脑不完整"');
  assert(!/工作准则/.test(o.additionalContext), '不该继续输出正常简报');
  assert(!/磨合|初次启动/.test(o.additionalContext), '不该走 onboarding');
});
t('1.3 大脑离线(目录不存在但认领过)→ 报离线、绝不重新 onboard', () => {
  const o = runStart({ YIDE_HOME: path.join(TMP, 'no-such-brain-xyz'), CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP });
  assert(/大脑离线/.test(o.additionalContext), '应报"大脑离线"');
  assert(!/磨合|初次启动/.test(o.additionalContext), '认领过就绝不重新 onboarding');
});
t('1.4 顶层 catch 给降级简报而非静默 exit;SessionStart timeout ≥15s', () => {
  const src = fs.readFileSync(path.join(SCRIPTS, 'session-start.js'), 'utf8');
  assert(/降级模式/.test(src) && /catch\s*\(e\)/.test(src), 'catch 分支应 emit 降级简报');
  const h = JSON.parse(fs.readFileSync(path.join(ROOT, 'hooks', 'hooks.json'), 'utf8'));
  assert(h.hooks.SessionStart[0].hooks[0].timeout >= 15, 'SessionStart timeout 应 ≥15s');
});
t('1.5 冲突副本巡检:命中英文/中文/数字去重,跳过 archive', () => {
  const { findConflicts, isConflictName } = require(path.join(SCRIPTS, 'conflict-scan.js'));
  assert(isConflictName('identity (conflicted copy 2026-07-02).md'), '英文冲突副本');
  assert(isConflictName('教训的冲突副本.md'), '中文冲突副本');
  assert(isConflictName('note (1).md'), '数字去重副本');
  assert(!isConflictName('normal.md'), '正常文件不命中');
  const cb = path.join(TMP, 'conflictbrain');
  fs.mkdirSync(path.join(cb, 'lessons', 'archive'), { recursive: true });
  fs.writeFileSync(path.join(cb, 'lessons', 'L-x (1).md'), 'x');
  fs.writeFileSync(path.join(cb, 'lessons', 'L-y.md'), 'y');
  fs.writeFileSync(path.join(cb, 'lessons', 'archive', 'old (conflicted copy).md'), 'z');
  const hits = findConflicts(cb).map(p => path.basename(p));
  assert(hits.includes('L-x (1).md'), '应命中活跃区冲突副本');
  assert(!hits.some(h => /old/.test(h)), 'archive 区应跳过');
});

// === 8e. 文档一致性 + skill 引用体检(2026-07-02 audit Phase 3)===
t('3.6 动作数一致:actions/*.md == README 动作表行 == 根 SKILL 路由行;路由文件都存在', () => {
  const actions = fs.readdirSync(path.join(ROOT, 'actions')).filter(n => n.endsWith('.md')).length;
  const readme = fs.readFileSync(path.join(ROOT, 'README.md'), 'utf8').split(/\r?\n/).filter(l => /^\|\s*`[a-z]+`\s*\|/.test(l)).length;
  const skill = fs.readFileSync(path.join(ROOT, 'SKILL.md'), 'utf8');
  const routeFiles = [...skill.matchAll(/\|\s*`[^`]+`.*?actions\/([a-z]+)\.md/g)].map(m => m[1]);
  assert(actions === readme, `README 动作表 ${readme} 行 ≠ actions/*.md ${actions} 个`);
  assert(actions === routeFiles.length, `SKILL 路由 ${routeFiles.length} 行 ≠ actions/*.md ${actions} 个`);
  for (const a of routeFiles) assert(fs.existsSync(path.join(ROOT, 'actions', a + '.md')), `SKILL 路由指向不存在的 actions/${a}.md`);
  assert(!/figma[^-]/i.test(skill.split('---')[2] || ''), '根 SKILL description 不应再宣传 figma 动作(figma 是 skill)');
});
t('3.7 lint-skill-refs:命中悬空引用、跳过占位/无根', () => {
  const { lintRefs, extractRefs } = require(path.join(SCRIPTS, 'lint-skill-refs.js'));
  assert(extractRefs('见 Assets/Foo/Real.cs 和 Assets/Name.unity 和 Assets/x/*.cs').length === 1, '应只抽具体非占位路径(Name/通配跳过)');
  // fixture:一个存在、一个缺失
  const sk = path.join(TMP, 'lintskills');
  const pr = path.join(TMP, 'lintproj');
  fs.mkdirSync(path.join(sk, 's1'), { recursive: true });
  fs.mkdirSync(path.join(pr, 'Assets', 'Real'), { recursive: true });
  fs.writeFileSync(path.join(pr, 'Assets', 'Real', 'Exists.cs'), '//');
  fs.writeFileSync(path.join(sk, 's1', 'SKILL.md'), '引用 Assets/Real/Exists.cs 与 Assets/Gone/Moved.prefab');
  const r = lintRefs(sk, pr);
  assert(!r.skipped && r.checked === 2, '应查 2 条');
  assert(r.missing.length === 1 && /Moved\.prefab/.test(r.missing[0].ref), '应只报缺失的 Moved.prefab');
  assert(lintRefs(sk, path.join(TMP, 'no-unity-here')).skipped === true, '无 Assets/ 的根应 skip');
});

// === 8g. brain-git 大脑 git 同步(2026-07-02 audit Phase 5)===
t('5.3 brain-git:非 git no-op;git 仓 sync 提交+推、无改动不提交、status clean', () => {
  const bg = require(path.join(SCRIPTS, 'brain-git.js'));
  const plain = path.join(TMP, 'plainbrain');
  fs.mkdirSync(plain, { recursive: true });
  assert(bg.pull(plain).git === false && bg.sync(plain, 'x').git === false && bg.status(plain).git === false, '非 git 大脑一律 no-op');
  const cp = require('child_process');
  const raw = (...a) => cp.execFileSync('git', a, { encoding: 'utf8' });
  const g = (dir, ...a) => cp.execFileSync('git', ['-C', dir, ...a], { encoding: 'utf8' });
  const origin = path.join(TMP, 'origin.git');
  const work = path.join(TMP, 'workbrain');
  raw('init', '--bare', '-b', 'main', origin);
  fs.mkdirSync(work, { recursive: true });
  g(work, 'init', '-b', 'main');
  g(work, 'config', 'user.email', 't@t'); g(work, 'config', 'user.name', 't');
  fs.writeFileSync(path.join(work, 'a.md'), '1');
  g(work, 'add', '-A'); g(work, 'commit', '-m', 'init');
  g(work, 'remote', 'add', 'origin', origin);
  g(work, 'push', '-u', 'origin', 'main');
  fs.writeFileSync(path.join(work, 'b.md'), '2');
  const r = bg.sync(work, 'add b');
  assert(r.git && r.committed && r.pushed, 'sync 应提交并推送:' + JSON.stringify(r));
  assert(bg.sync(work, 'noop').committed === false, '无改动不提交');
  const s = bg.status(work);
  assert(s.git && !s.dirty && s.ahead === 0 && s.behind === 0 && s.remoteReachable, 'status 应 clean+可达:' + JSON.stringify(s));
});

// === 8f. guid-find(2026-07-02 audit Phase 4)===
t('4.3 guid-find:asset→GUID 解析、反查引用者、跳过自身 .meta', () => {
  const { resolveGuid, findReferencers } = require(path.join(SCRIPTS, 'guid-find.js'));
  const pr = path.join(TMP, 'guidproj');
  const A = path.join(pr, 'Assets');
  fs.mkdirSync(path.join(A, 'Art'), { recursive: true });
  const GUID = 'a1b2c3d4e5f60718293a4b5c6d7e8f90';
  fs.writeFileSync(path.join(A, 'Art', 'Tex.png'), 'PNGDATA');
  fs.writeFileSync(path.join(A, 'Art', 'Tex.png.meta'), `fileFormatVersion: 2\nguid: ${GUID}\n`);
  fs.writeFileSync(path.join(A, 'User.mat'), `Material:\n  m_Texture: {fileID: 2800000, guid: ${GUID}, type: 3}\n`);
  fs.writeFileSync(path.join(A, 'Unrelated.mat'), `Material:\n  m_Texture: {fileID: 0}\n`);
  // 解析:路径 → GUID(读 .meta)
  assert(resolveGuid('Assets/Art/Tex.png', pr) === GUID, '应从 .meta 解析出 GUID');
  assert(resolveGuid(GUID.toUpperCase(), pr) === GUID, '直接给 GUID 应原样(小写)返回');
  // 反查:User.mat 引用,Unrelated.mat 不引用,Tex.png.meta(定义)不算引用
  const refs = findReferencers(GUID, pr).map(p => path.basename(p));
  assert(refs.includes('User.mat'), '应命中引用者 User.mat');
  assert(!refs.includes('Unrelated.mat'), '不引用的不该命中');
  assert(!refs.includes('Tex.png.meta'), 'GUID 自身的 .meta 是定义不算引用');
});

// === 8d. 更新闭环 + 注入瘦身(2026-07-02 audit Phase 2)===
t('2.1/2.2 migrate:干净→stamp true+删废弃;有冲突→stamp false+不打戳', () => {
  const mb = path.join(TMP, 'migbrain', '.yide');
  fs.mkdirSync(path.join(mb, 'core'), { recursive: true });
  fs.mkdirSync(path.join(mb, '.meta'), { recursive: true });
  fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', 'identity.md'), path.join(mb, 'core', 'identity.md'));
  fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', 'hard-rules.md'), path.join(mb, 'core', 'hard-rules.md'));
  fs.writeFileSync(path.join(mb, 'core', 'charter.md'), 'dead dup'); // 废弃残留(REMOVED)
  const mig = (dir, apply) => JSON.parse(execFileSync('node', apply ? [path.join(SCRIPTS, 'migrate.js'), '--apply'] : [path.join(SCRIPTS, 'migrate.js')], { encoding: 'utf8', env: Object.assign({}, process.env, { YIDE_HOME: dir, CLAUDE_PLUGIN_ROOT: ROOT }) }));
  let r = mig(mb, false);
  assert(r.removed.includes('core/charter.md'), 'plan 应报废弃 core/charter.md');
  assert(fs.existsSync(path.join(mb, 'core', 'charter.md')), 'plan 不删文件');
  r = mig(mb, true);
  assert(r.stamped === true, '干净→应打戳');
  assert(!fs.existsSync(path.join(mb, 'core', 'charter.md')), 'apply 应删废弃 core/charter.md');
  assert((fs.readFileSync(path.join(mb, '.meta', 'plugin-version.txt'), 'utf8') || '').trim().length > 0, 'apply 干净应写版本戳');
  // 冲突:SHIPPED 文件被用户改 + 旧 base 与模板不同 → 冲突 → 不打戳
  const cb = path.join(TMP, 'migconf', '.yide');
  fs.mkdirSync(path.join(cb, '.meta', 'shipped-base', 'style'), { recursive: true });
  fs.mkdirSync(path.join(cb, 'style'), { recursive: true });
  fs.writeFileSync(path.join(cb, 'style', 'unity.md'), 'USER MODIFIED UNITY');
  fs.writeFileSync(path.join(cb, '.meta', 'shipped-base', 'style', 'unity.md'), 'OLD BASE DIFFERENT');
  const rc = mig(cb, true);
  assert(rc.conflicts.some(c => c.file === 'style/unity.md'), 'style/unity.md 应判冲突');
  assert(rc.stamped === false, '有冲突→不打戳');
  assert(!fs.existsSync(path.join(cb, '.meta', 'plugin-version.txt')), '有冲突不写版本戳');
});
t('2.4 charter-extra 软上限:超 4000 截断+提示;未超原样', () => {
  const { resolve } = require(path.join(SCRIPTS, 'resolve.js'));
  const rb = path.join(TMP, 'capbrain', '.yide');
  fs.mkdirSync(path.join(rb, 'core'), { recursive: true });
  fs.writeFileSync(path.join(rb, 'core', 'charter-extra.md'), 'x'.repeat(5000));
  let out = resolve('charter', ROOT, rb);
  assert(/已截断/.test(out), '超上限应截断并提示');
  assert(!out.includes('x'.repeat(4500)), '应真的截断到上限');
  fs.writeFileSync(path.join(rb, 'core', 'charter-extra.md'), 'yideShortRule 保留我');
  out = resolve('charter', ROOT, rb);
  assert(/yideShortRule 保留我/.test(out) && !/已截断/.test(out), '未超上限应原样保留');
});
t('2.5 ER 专属常驻只在 ER 会话注入(charter-extra-er)', () => {
  const { extractionContext } = require(path.join(SCRIPTS, 'extraction-context.js'));
  const eb = path.join(TMP, 'erbrain2', '.yide');
  fs.mkdirSync(path.join(eb, 'core'), { recursive: true });
  fs.writeFileSync(path.join(eb, 'core', 'charter-extra-er.md'), '<!-- c -->\n\n**ER 主程 mindset**:ER专属测试标记。');
  const er = extractionContext(eb, '/x/extraction-raiders', ROOT) || '';
  assert(/ER专属测试标记/.test(er), 'ER 会话应注入 charter-extra-er');
  assert(!/<!--/.test(er), '应剥掉文件头注释');
  const non = extractionContext(eb, '/x/some-other-game', ROOT) || '';
  assert(!/ER专属测试标记/.test(non), '非 ER 会话不注入 ER 专属');
});

// === 8. 安全加固(2026-07-02 audit Phase 0)===
t('0.1 换行分段:多行命令第二行的危险命令不放行', () => {
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git status\nrm -rf /tmp/x' } }) === 'defer', 'git status\\nrm -rf 整条应 defer(换行也切段)');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'ls\r\nrm -rf x' } }) === 'defer', 'CRLF 也应切段');
});
t('0.2 find/sort 写形态回落审批;只读形态仍放行', () => {
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'find . -name *.tmp -delete' } }) === 'defer', 'find -delete 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'find . -exec rm {} ;' } }) === 'defer', 'find -exec 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'sort -o victim.txt in.txt' } }) === 'defer', 'sort -o 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'sort -ovictim.txt in.txt' } }) === 'defer', 'sort -o<file> 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'find . -name *.cs' } }) === 'allow', 'find 只读应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'sort in.txt' } }) === 'allow', 'sort 只读应放行');
});
t('0.2 git 可写子命令:纯查询放行、创建/改写回落(撞红线⑧)', () => {
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git branch feature-x' } }) === 'defer', 'git branch <名> 建分支应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git branch -d old' } }) === 'defer', 'git branch -d 删分支应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git config user.email x@y.com' } }) === 'defer', 'git config 写值应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git tag v1.0' } }) === 'defer', 'git tag 建标签应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git remote add o http://x' } }) === 'defer', 'git remote add 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git reflog expire --all' } }) === 'defer', 'git reflog expire 应 defer');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git branch' } }) === 'allow', 'git branch 列表应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git branch -a -v' } }) === 'allow', 'git branch -a 只读应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git config -l' } }) === 'allow', 'git config -l 应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git remote -v' } }) === 'allow', 'git remote -v 应放行');
  assert(preToolDecision({ tool_name: 'Bash', tool_input: { command: 'git tag' } }) === 'allow', 'git tag 列表应放行');
});
t('0.3 hooks.json PreToolUse 覆盖 PowerShell;PS 只走 deny 不自动放行', () => {
  const h = JSON.parse(fs.readFileSync(path.join(ROOT, 'hooks', 'hooks.json'), 'utf8'));
  assert(/\bPowerShell\b/.test(h.hooks.PreToolUse[0].matcher), 'PreToolUse matcher 应含 PowerShell');
  const pb = path.join(TMP, 'psbrain', '.yide');
  fs.mkdirSync(path.join(pb, '.meta'), { recursive: true });
  fs.writeFileSync(path.join(pb, '.meta', 'hook-rules.json'), JSON.stringify({ rules: [{ pattern: 'Remove-Item.*-Recurse', reason: '危险删除', tools: ['*'] }] }));
  assert(preToolDecision({ tool_name: 'PowerShell', tool_input: { command: 'Remove-Item -Recurse -Force x' } }, { YIDE_HOME: pb }) === 'deny', 'PS 危险命令应被 deny 层拦(blob 收集不挑字段名)');
  assert(preToolDecision({ tool_name: 'PowerShell', tool_input: { command: 'Get-ChildItem' } }) === 'defer', 'PS 一律不自动放行,回落审批');
});
t('0.4 MCP allow 整词匹配:forget/budget 不因含 get 被误放', () => {
  assert(preToolDecision({ tool_name: 'mcp__x__forget_cache', tool_input: {} }) === 'defer', 'forget_cache 不该因子串 get 放行');
  assert(preToolDecision({ tool_name: 'mcp__x__budget_report', tool_input: {} }) === 'defer', 'budget_report 不该因子串 get 放行');
  assert(preToolDecision({ tool_name: 'mcp__x__get_state', tool_input: {} }) === 'allow', 'get_state 整词命中应放行');
  assert(preToolDecision({ tool_name: 'mcp__coplay__get_game_object_info', tool_input: {} }) === 'allow', 'get_game_object_info 应放行');
});

// === 9. Stop/SubagentStop 收尾审计(完成声明 vs 验证证据)===
// 跑 stop-audit.js:构造临时 transcript + hook 输入,返回 'block'|'pass'(pass=空输出放行)。
function stopAudit(hookInput) {
  const out = execFileSync('node', [path.join(SCRIPTS, 'stop-audit.js')], {
    input: JSON.stringify(hookInput), encoding: 'utf8',
  }).trim();
  if (!out) return 'pass';
  try { return JSON.parse(out).decision === 'block' ? 'block' : 'pass'; } catch { return 'pass'; }
}
// 把 entry 数组写成 JSONL transcript,返回路径。
function writeTranscript(name, entries) {
  const fp = path.join(TMP, 'transcript-' + name + '.jsonl');
  fs.writeFileSync(fp, entries.map(e => JSON.stringify(e)).join('\n') + '\n');
  return fp;
}
function asstText(text) { return { type: 'assistant', message: { role: 'assistant', content: [{ type: 'text', text }] } }; }
function asstTool(name, input) { return { type: 'assistant', message: { role: 'assistant', content: [{ type: 'tool_use', name, input: input || {} }] } }; }

t('9.1 完成声明 + 无验证 → block', () => {
  const tp = writeTranscript('claim-noverify', [
    { type: 'user', message: { role: 'user', content: '把这个修一下' } },
    asstTool('Edit', { file_path: '/x.cs', new_string: 'y' }),
    asstText('已修复并验证,一切正常。'),
  ]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: false, hook_event_name: 'Stop' }) === 'block', '声明+无验证应 block');
});
t('9.2 完成声明 + coplay tool_use → 放行', () => {
  const tp = writeTranscript('claim-coplay', [
    asstTool('mcp__coplay-mcp__play_game', {}),
    asstText('测试通过,功能正常。'),
  ]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: false }) === 'pass', '有 coplay 验证应放行');
});
t('9.2b 完成声明 + Bash npm test → 放行', () => {
  const tp = writeTranscript('claim-npmtest', [
    asstTool('Bash', { command: 'npm test' }),
    asstText('all tests passed.'),
  ]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: false }) === 'pass', 'npm test 应算验证放行');
});
t('9.3 无完成声明 → 放行', () => {
  const tp = writeTranscript('noclaim', [
    asstText('我改了几个文件,你自己再看看对不对,我没跑过。'),
  ]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: false }) === 'pass', '无声明应放行');
});
t('9.4 stop_hook_active=true → 放行(防死循环)', () => {
  const tp = writeTranscript('active', [asstText('测试通过。')]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: true }) === 'pass', '续跑必须放行');
});
t('9.5 transcript 不存在 → 放行不抛错', () => {
  assert(stopAudit({ transcript_path: path.join(TMP, 'no-such-transcript.jsonl'), stop_hook_active: false }) === 'pass', '读不到应静默放行');
  assert(stopAudit({}) === 'pass', '缺 transcript_path 也应放行');
});
t('9.6 标 UNVERIFIED 是合规出口 → 放行', () => {
  const tp = writeTranscript('unverified', [
    asstTool('Edit', { file_path: '/x.cs', new_string: 'y' }),
    asstText('改动完成,但编译验证做不了,标 UNVERIFIED:Coplay MCP 不可用。'),
  ]);
  assert(stopAudit({ transcript_path: tp, stop_hook_active: false }) === 'pass', 'UNVERIFIED 标注不该被当成完成声明 block');
});

// === 10. honesty(诚实性)lint 规则:欺骗指纹当场点破,不受 expertLevel 过滤,Mock 路径跳过 ===
const { lint } = require(path.join(SCRIPTS, 'lint-unity.js'));
const hasRule = (fs2, rule) => fs2.some(f => f.rule === rule);
t('honesty-fake-comment:命中欺骗性注释', () => {
  const src = 'void Load(){\n    // simulate server call for now\n    var x = 1;\n}';
  assert(hasRule(lint(src, {}), 'honesty-fake-comment'), '应命中 simulate/for now 注释');
  assert(hasRule(lint('/* placeholder — stub for now */\nint N=0;', {}), 'honesty-fake-comment'), '块注释也应命中');
});
t('honesty-fake-comment:正常注释不误报、同名代码标识符不误报', () => {
  assert(!hasRule(lint('// increment the retry counter and clamp\nint c = c + 1;', {}), 'honesty-fake-comment'), '正常注释不该报');
  assert(!hasRule(lint('var placeholder = GetSlot();\nfake(x);', {}), 'honesty-fake-comment'), '代码里的标识符(非注释)不该报');
});
t('honesty-swallowed-catch:空 catch / 只 return 默认值命中', () => {
  assert(hasRule(lint('try { Do(); } catch { }', {}), 'honesty-swallowed-catch'), '空 catch 应命中');
  assert(hasRule(lint('try { Do(); } catch (Exception e) {\n    // ignore\n}', {}), 'honesty-swallowed-catch'), '只含注释的 catch 应命中');
  assert(hasRule(lint('try { Save(); } catch (Exception e) {\n    return null;\n}', {}), 'honesty-swallowed-catch'), 'catch 里只 return null 应命中');
  assert(hasRule(lint('try { Save(); } catch { return false; }', {}), 'honesty-swallowed-catch'), 'catch 里只 return false 应命中');
});
t('honesty-swallowed-catch:有日志/有 rethrow 的 catch 不误报', () => {
  assert(!hasRule(lint('try { Do(); } catch (Exception e) {\n    Debug.Log(e);\n}', {}), 'honesty-swallowed-catch'), '有 Debug.Log 不该报');
  assert(!hasRule(lint('try { Do(); } catch (Exception e) {\n    GameLogger.Error(e);\n}', {}), 'honesty-swallowed-catch'), '有 Logger 调用不该报');
  assert(!hasRule(lint('try { Do(); } catch (Exception e) {\n    Cleanup();\n    throw;\n}', {}), 'honesty-swallowed-catch'), '有实质语句/rethrow 不该报');
});
t('honesty:Mock/测试/CoplayTemp 路径跳过(fake/stub 正当)', () => {
  const src = '// fake server for now\ntry { Do(); } catch { }';
  assert(hasRule(lint(src, { filePath: 'Assets/Scripts/Net/Client.cs' }), 'honesty-fake-comment'), '普通路径应报');
  for (const fp of ['Assets/Tests/ClientTests.cs', 'Assets/Mock/FakeApi.cs', 'Assets/mocks/x.cs', 'Assets/Editor/CoplayTemp/Probe.cs']) {
    const f = lint(src, { filePath: fp });
    assert(!hasRule(f, 'honesty-fake-comment') && !hasRule(f, 'honesty-swallowed-catch'), '路径含 test/mock/coplaytemp 应跳过 honesty:' + fp);
  }
});
t('honesty:expertLevel=expert 仍报(不受档过滤)', () => {
  const src = '// pretend we saved it\ntry { Save(); } catch { return; }';
  const f = lint(src, { expertLevel: 'expert' });
  assert(hasRule(f, 'honesty-fake-comment'), 'expert 档 fake-comment 仍应报');
  assert(hasRule(f, 'honesty-swallowed-catch'), 'expert 档 swallowed-catch 仍应报');
});

// === 11. scope 契约 + 覆盖度/留尾闸门(治"任务不做完就收工")===
const scope = require(path.join(SCRIPTS, 'scope.js'));
function userText(text) { return { type: 'user', message: { role: 'user', content: text } }; }
const OK = 'node -e "process.exit(0)"';
const BAD = 'node -e "process.exit(1)"';

t('11.1 register 登记后 unresolved 列出 open 条目', () => {
  scope.register('s-reg', [{ what: '改 A', verify: OK }, { what: '改 B' }], true);
  assert(scope.unresolved('s-reg').length === 2, '刚登记应两条未处理');
  assert(scope.getScope('s-nope') === null, '没登记的会话应为 null');
});
t('11.2 check:退出码 0 → pass,非 0 → fail(fail 仍算未完成)', () => {
  scope.register('s-chk', [{ what: '好的', verify: OK }, { what: '坏的', verify: BAD }], true);
  scope.check('s-chk');
  const items = scope.getScope('s-chk').items;
  assert(items[0].state === 'pass', '退出 0 应 pass,实为 ' + items[0].state);
  assert(items[1].state === 'fail', '非 0 应 fail,实为 ' + items[1].state);
  assert(scope.unresolved('s-chk').length === 1, 'fail 必须仍算未完成');
});
t('11.3 attest/waive 强制要具体文字,空话拒绝', () => {
  scope.register('s-mark', [{ what: 'Play 目测' }], true);
  let threw = false;
  try { scope.mark('s-mark', '1', 'attested', '', '证据'); } catch { threw = true; }
  assert(threw, '空证据应抛错');
  scope.mark('s-mark', '1', 'attested', 'Editor.log 第 88 行 [WaveDone] 计数 3/3');
  assert(scope.unresolved('s-mark').length === 0, 'attested 应算已处理');
});
t('11.4 覆盖度闸门:有 open 条目 → block;全部收敛 → 放行', () => {
  const tp = writeTranscript('scope-open', [userText('做三件事'), asstText('第一件改好了。')]);
  scope.register('s-gate', [{ what: '改 A', verify: OK }, { what: '改 B', verify: BAD }], true);
  scope.check('s-gate');
  assert(stopAudit({ transcript_path: tp, session_id: 's-gate', stop_hook_active: false }) === 'block', '有 fail 条目应 block');
  scope.mark('s-gate', '2', 'waived', '勾哥说 B 这轮不做了');
  assert(stopAudit({ transcript_path: tp, session_id: 's-gate', stop_hook_active: false }) === 'pass', '全部收敛应放行');
});
t('11.5 覆盖度闸门在 stop_hook_active=true 时仍拦(与诚实度闸门的关键区别)', () => {
  const tp = writeTranscript('scope-active', [userText('做完'), asstText('先到这。')]);
  scope.register('s-active', [{ what: '还没做的事' }], true);
  assert(stopAudit({ transcript_path: tp, session_id: 's-active', stop_hook_active: true }) === 'block', '续跑也要拦,否则一次 block 后闸门失效');
});
t('11.6 空转退化:连拦两次没进展后放行(不撞 8 次硬上限)', () => {
  const tp = writeTranscript('scope-loop', [userText('做'), asstText('还没做完。')]);
  scope.register('s-loop', [{ what: '死活做不完的事' }], true);
  const seq = [1, 2, 3].map(() => stopAudit({ transcript_path: tp, session_id: 's-loop', stop_hook_active: true }));
  assert(seq[0] === 'block' && seq[1] === 'block', '前两次应拦,实为 ' + seq.join(','));
  assert(seq[2] === 'pass', '毫无进展时第三次应退化放行,实为 ' + seq[2]);
});
t('11.7 留尾闸门:把"要不要继续"甩回用户 + 没登记 scope → block', () => {
  const tp = writeTranscript('tail-ask', [userText('把这块做了'), asstTool('Edit', { file_path: '/x.cs', new_string: 'y' }),
    asstText('A 和 B 改好了,C 那块要不要我继续?')]);
  assert(stopAudit({ transcript_path: tp, session_id: 's-tail', stop_hook_active: false }) === 'block', '留尾措辞应 block');
});
t('11.8 留尾闸门:走 AskUserQuestion 的正当拍板 → 放行', () => {
  const tp = writeTranscript('tail-popup', [userText('把这块做了'), asstTool('AskUserQuestion', {}),
    asstText('要不要继续做 C?我给了选项。')]);
  assert(stopAudit({ transcript_path: tp, session_id: 's-popup', stop_hook_active: false }) === 'pass', '弹窗拍板不该被拦');
});
t('11.9 留尾闸门不误伤正常汇报', () => {
  const tp = writeTranscript('tail-clean', [userText('改一下'), asstText('三处都改完了,顺带发现 Foo 有个旧 bug,记在这里没动它。')]);
  assert(stopAudit({ transcript_path: tp, session_id: 's-clean', stop_hook_active: false }) === 'pass', '正常汇报不该被拦');
});
t('11.10 诚实度闸门收窄到本回合:不能白嫖上一回合的验证', () => {
  const tp = writeTranscript('turn-scoped', [
    userText('先做第一件'), asstTool('mcp__coplay-mcp__play_game', {}), asstText('第一件验证过了。'),
    userText('再改一处'), asstTool('Edit', { file_path: '/x.cs', new_string: 'y' }), asstText('已修复并验证。'),
  ]);
  assert(stopAudit({ transcript_path: tp, session_id: 's-turn', stop_hook_active: false }) === 'block', '本回合无验证应 block(旧逻辑会白嫖上回合的 play_game)');
});
t('11.11 诚实度闸门不误伤纯讨论回合(没改文件)', () => {
  const tp = writeTranscript('turn-talk', [
    userText('先做'), asstTool('Edit', { file_path: '/x.cs', new_string: 'y' }), asstText('改了。'),
    userText('解释一下刚才那个改动'), asstText('之前那轮测试通过,原因是 xxx。'),
  ]);
  assert(stopAudit({ transcript_path: tp, session_id: 's-talk', stop_hook_active: false }) === 'pass', '没改文件的讨论回合不该被拦');
});
t('11.12 scope CLI 端到端(set → check → status)', () => {
  const run = (args) => execFileSync('node', [path.join(SCRIPTS, 'scope.js')].concat(args), { encoding: 'utf8', env: process.env });
  run(['set', '--session', 's-cli', '--json', JSON.stringify([{ what: 'CLI 条目', verify: OK }])]);
  run(['check', '--session', 's-cli']);
  const st = JSON.parse(run(['status', '--session', 's-cli']));
  assert(st.items.length === 1 && st.items[0].state === 'pass', 'CLI 走完应为 pass,实为 ' + JSON.stringify(st.items));
});

// 清理
try { fs.rmSync(TMP, { recursive: true, force: true }); } catch {}

console.log(`\n结果:${pass} 过 / ${fail} 败` + (fail ? '  →  ' + fails.join(', ') : ''));
process.exit(fail ? 1 : 0);
