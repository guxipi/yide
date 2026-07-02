#!/usr/bin/env node
// 翼德 · skill 引用体检:skills/**.md 里写死的 Assets/… · CloudCode/… · Packages/… 具体文件路径,
// 对一个真实 Unity 项目根逐个查存在性 —— 抓"文件被移/改名后 skill 还指旧路径"的悬空引用。
//   node scripts/lint-skill-refs.js [项目根]   （项目根缺省取 YIDE_UNITY_PROJECT / CLAUDE_PROJECT_DIR）
// 项目根不存在 / 不是 Unity 工程(无 Assets/)→ 跳过(exit 0,别在别人机器上误报)。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');

// 只查"看起来是具体文件"的引用:带已知扩展名、不含通配/占位。目录引用、`Temp/yide_*.cs` 之类模式跳过。
const REF_RE = /\b(?:Assets|CloudCode|Packages)\/[A-Za-z0-9_.\/-]+\.(?:cs|prefab|unity|asset|mat|shader|hlsl|png|controller|anim)\b/g;

function extractRefs(text) {
  const out = new Set();
  for (const m of text.matchAll(REF_RE)) {
    const p = m[0];
    if (/[*<>{}]|\.\.\./.test(p)) continue; // 通配/占位 → 跳过
    const stem = (p.split('/').pop() || '').replace(/\.[^.]+$/, '');
    if (/^(Name|Foo|Bar|Baz|Xxx?|Example|Your\w*|Some\w*|Scene\d*)$/i.test(stem)) continue; // 元变量占位(如 save_scene 垃圾文件 Assets/Name.unity)→ 跳过
    out.add(p);
  }
  return [...out];
}

// 递归收集 dir 下所有 .md。
function mdFiles(dir, out = []) {
  let ents = [];
  try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of ents) {
    const fp = path.join(dir, e.name);
    if (e.isDirectory()) mdFiles(fp, out);
    else if (e.name.endsWith('.md')) out.push(fp);
  }
  return out;
}

// 返回 { skipped, checked, missing:[{file, ref}] }。projectRoot 无 Assets/ → skipped=true。
function lintRefs(skillsDir, projectRoot) {
  if (!projectRoot || !fs.existsSync(path.join(projectRoot, 'Assets'))) return { skipped: true, checked: 0, missing: [] };
  const missing = [];
  let checked = 0;
  for (const f of mdFiles(skillsDir)) {
    const text = fs.readFileSync(f, 'utf8');
    for (const ref of extractRefs(text)) {
      checked++;
      if (!fs.existsSync(path.join(projectRoot, ref))) missing.push({ file: path.relative(skillsDir, f), ref });
    }
  }
  return { skipped: false, checked, missing };
}

module.exports = { lintRefs, extractRefs };

if (require.main === module) {
  const skillsDir = path.join(__dirname, '..', 'skills');
  const root = process.argv[2] || process.env.YIDE_UNITY_PROJECT || process.env.CLAUDE_PROJECT_DIR || '';
  const r = lintRefs(skillsDir, root);
  if (r.skipped) { process.stdout.write(`SKIP\t无 Unity 项目根(传参或设 YIDE_UNITY_PROJECT);skill 路径引用未校验。\n`); process.exit(0); }
  process.stdout.write(`查了 ${r.checked} 条具体路径引用,项目根:${root}\n`);
  if (!r.missing.length) { process.stdout.write('OK\t全部存在。\n'); process.exit(0); }
  process.stdout.write(`MISSING\t${r.missing.length} 条悬空引用(文件被移/改名?):\n`);
  for (const m of r.missing) process.stdout.write(`  - ${m.ref}   ←   skills/${m.file}\n`);
  process.exit(1);
}
