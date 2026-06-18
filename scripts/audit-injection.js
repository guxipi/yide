#!/usr/bin/env node
'use strict';
// 翼德 · 开场注入"称重器"(维护者工具,运行时不跑)。守住"轻"的承诺:别让常驻注入慢慢变胖。
// 用模板大脑(可复现基线)跑一次 SessionStart,按 "## " 分节统计字符 + 估算 tokens,对比软预算。
// 跑:node scripts/audit-injection.js(或 npm run audit)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const BUDGET_TOKENS = 900;     // 软预算:模板基线常驻注入上限(超了该精简;真实大脑会再叠加用户身份/项目档案)
const CHARS_PER_TOKEN = 2.2;   // 中文粗估

const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'yide-audit-'));
const BRAIN = path.join(TMP, '.yide');
fs.mkdirSync(path.join(BRAIN, 'core'), { recursive: true });
fs.mkdirSync(path.join(BRAIN, '.meta'), { recursive: true });
for (const f of ['identity.md', 'hard-rules.md', 'charter.md']) {
  fs.copyFileSync(path.join(ROOT, 'templates', 'brain', 'core', f), path.join(BRAIN, 'core', f));
}
// 量"稳态"(每次会话都付的常驻),排除到期才出的 consolidate 提醒
fs.writeFileSync(path.join(BRAIN, '.meta', 'last-consolidate.txt'), String(Date.now()));
const out = execFileSync('node', [path.join(ROOT, 'scripts', 'session-start.js')], {
  input: '{}', encoding: 'utf8',
  env: Object.assign({}, process.env, { YIDE_HOME: BRAIN, CLAUDE_PLUGIN_ROOT: ROOT, CLAUDE_PROJECT_DIR: TMP }),
});
const ctx = (JSON.parse(out).hookSpecificOutput.additionalContext) || '';
try { fs.rmSync(TMP, { recursive: true, force: true }); } catch {}

const sections = ctx.split(/\n(?=## )/).map(s => {
  const title = ((s.match(/^#+\s*(.+)/m) || [, s.slice(0, 24)])[1] || '').trim().slice(0, 34);
  return { title, chars: s.length };
}).sort((a, b) => b.chars - a.chars);

const total = ctx.length;
const tokens = Math.round(total / CHARS_PER_TOKEN);
console.log('翼德 · 开场常驻注入称重(模板基线,不含真实用户身份/项目内容)\n');
for (const s of sections) console.log(`  ${String(s.chars).padStart(5)} 字   ${s.title}`);
console.log(`\n  合计 ${total} 字 ≈ ${tokens} tokens`);
console.log(`  软预算 ${BUDGET_TOKENS} tokens → ${tokens <= BUDGET_TOKENS ? '✅ 在预算内' : '⚠️ 超预算,该精简常驻注入(挪去懒加载 action 或砍字)'}`);
