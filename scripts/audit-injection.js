#!/usr/bin/env node
'use strict';
// 翼德 · 开场注入"称重器"(维护者工具,运行时不跑)。守住"轻"的承诺:别让常驻注入慢慢变胖。
// 两种模式:
//   (默认)  node scripts/audit-injection.js        → 量"模板基线"(可复现,只 core 三件),对比软预算。
//   --real  node scripts/audit-injection.js --real → 量真实大脑的实际注入(复制到临时目录,只读不动 live),
//                                                     按 ER 会话稳态分节报字数/估 tokens —— 看真身有多重。
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

const ROOT = path.resolve(__dirname, '..');
const BUDGET_TOKENS = 900;     // 软预算:模板基线常驻注入上限(超了该精简;真实大脑会再叠加用户身份/项目档案)
const CHARS_PER_TOKEN = 2.2;   // 中文粗估
const REAL = process.argv.includes('--real');

function pluginVer() {
  try { return JSON.parse(fs.readFileSync(path.join(ROOT, '.claude-plugin', 'plugin.json'), 'utf8')).version || '0.0.0'; }
  catch { return '0.0.0'; }
}

// "模板基线"临时大脑:core 三件 + INDEX.md(过完整性哨兵)+ 冻结版本戳/整理戳(量稳态,不触发 migrate/consolidate 提醒)。
function buildTemplateBrain(tmp) {
  const brain = path.join(tmp, '.yide');
  fs.mkdirSync(path.join(brain, 'core'), { recursive: true });
  fs.mkdirSync(path.join(brain, '.meta'), { recursive: true });
  for (const f of ['identity.md', 'hard-rules.md', 'charter.md']) fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', f), path.join(brain, 'core', f));
  fs.writeFileSync(path.join(brain, 'INDEX.md'), '# index');
  fs.writeFileSync(path.join(brain, '.meta', 'last-consolidate.txt'), String(Date.now()));
  fs.writeFileSync(path.join(brain, '.meta', 'plugin-version.txt'), pluginVer());
  return brain;
}

// 真实大脑副本:整目录复制到临时(绝不动 live),冻结版本戳/整理戳 → 量稳态。
function buildRealBrainCopy(tmp) {
  const brain = path.join(tmp, '.yide');
  fs.cpSync(brainDir(), brain, { recursive: true });
  fs.mkdirSync(path.join(brain, '.meta'), { recursive: true });
  fs.writeFileSync(path.join(brain, '.meta', 'last-consolidate.txt'), String(Date.now()));
  fs.writeFileSync(path.join(brain, '.meta', 'plugin-version.txt'), pluginVer());
  return brain;
}

function measure(brain, projectDir) {
  const out = execFileSync('node', [path.join(ROOT, 'scripts', 'session-start.js')], {
    input: '{}', encoding: 'utf8',
    env: Object.assign({}, process.env, {
      YIDE_HOME: brain, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: projectDir,
      YIDE_NO_OPEN: '1', YIDE_LOCAL: path.join(brain, '.yide-local-audit'),
    }),
  });
  return (JSON.parse(out).hookSpecificOutput.additionalContext) || '';
}

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'yide-audit-'));
let ctx = '';
try {
  if (REAL) {
    const brain = buildRealBrainCopy(TMP);
    ctx = measure(brain, path.join(TMP, 'extraction-raiders')); // ER 项目路径 → 含 extraction 专属注入(最重)
  } else {
    const brain = buildTemplateBrain(TMP);
    ctx = measure(brain, TMP);
  }
} finally { try { fs.rmSync(TMP, { recursive: true, force: true }); } catch {} }

const sections = ctx.split(/\n(?=## )/).map(s => {
  const title = ((s.match(/^#+\s*(.+)/m) || [, s.slice(0, 24)])[1] || '').trim().slice(0, 34);
  return { title, chars: s.length };
}).sort((a, b) => b.chars - a.chars);

const total = ctx.length;
const tokens = Math.round(total / CHARS_PER_TOKEN);
if (REAL) {
  console.log('翼德 · 开场注入称重(真实大脑副本 · ER 会话稳态,只读不动 live)\n');
  for (const s of sections) console.log(`  ${String(s.chars).padStart(5)} 字   ${s.title}`);
  console.log(`\n  合计 ${total} 字 ≈ ${tokens} tokens(真实注入;默认 npm run audit 只量模板基线)`);
} else {
  console.log('翼德 · 开场常驻注入称重(模板基线,不含真实用户身份/项目内容)\n');
  for (const s of sections) console.log(`  ${String(s.chars).padStart(5)} 字   ${s.title}`);
  console.log(`\n  合计 ${total} 字 ≈ ${tokens} tokens`);
  console.log(`  软预算 ${BUDGET_TOKENS} tokens → ${tokens <= BUDGET_TOKENS ? '✅ 在预算内' : '⚠️ 超预算,该精简常驻注入(挪去懒加载 action 或砍字)'}`);
}
