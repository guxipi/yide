#!/usr/bin/env node
// 翼德 · 安全迁移:把插件带来的新默认安全地合并进用户大脑,绝不覆盖用户数据。
// 三方比较(base=上次发货快照 / user=用户当前 / new=本次插件模板):
//   - 用户没有的新文件        → 直接加(additive,安全)
//   - "发货知识"文件且用户没改 → 刷新到新版(安全)
//   - "发货知识"文件且用户改过且上游也变 → 冲突,只报告不动(交给技能问用户)
//   - 用户自有文件(身份/教训/项目/各 style 填写项) → 除非缺失否则绝不碰
//   - hard-rules.md           → 报告"用户缺的默认红线",由技能确认后再加(不在此自动改文件)
// 输出:一段 JSON 报告到 stdout。--apply 才真正写盘安全部分;默认 --plan 只报告。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, '..');
const TEMPLATE = path.join(PLUGIN_ROOT, 'templates', 'brain');
const BRAIN = brainDir();
const BASE = path.join(BRAIN, '.meta', 'shipped-base');
const APPLY = process.argv.includes('--apply');

// "发货知识"文件:可被刷新(非用户私有数据)
const SHIPPED = new Set(['style/unity.md', 'README.md', 'lessons/_TEMPLATE.md', 'projects/_TEMPLATE.md']);
// 永不自动刷新的用户私有文件(只在缺失时新增)
function isUserOwned(rel) {
  return rel === 'core/identity.md' || rel === 'core/hard-rules.md' ||
    rel === 'INDEX.md' || rel === 'style/coding.md' || rel === 'style/communication.md' ||
    rel === 'style/writing.md' || rel.startsWith('lessons/') && rel !== 'lessons/_TEMPLATE.md' ||
    rel.startsWith('projects/') && rel !== 'projects/_TEMPLATE.md' ||
    rel.startsWith('notes/') && rel !== 'notes/README.md' ||
    rel.startsWith('distilled/') && rel !== 'distilled/README.md' ||
    rel.startsWith('experts/') && rel !== 'experts/README.md' ||
    rel.startsWith('prompts/') && rel !== 'prompts/README.md' ||
    rel.startsWith('.meta/');
}

function walk(dir, base = dir, out = []) {
  let ents = [];
  try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of ents) {
    const fp = path.join(dir, e.name);
    const rel = path.relative(base, fp).split(path.sep).join('/');
    if (e.isDirectory()) walk(fp, base, out); else out.push(rel);
  }
  return out;
}
const rd = p => { try { return fs.readFileSync(p, 'utf8'); } catch { return null; } };

const report = { added: [], refreshed: [], conflicts: [], rulesToAdd: [], applied: APPLY };

// 1) 遍历模板文件
for (const rel of walk(TEMPLATE)) {
  if (rel.startsWith('.meta/shipped-base/')) continue;
  const tNew = rd(path.join(TEMPLATE, rel));
  const tUser = rd(path.join(BRAIN, rel));
  const tBase = rd(path.join(BASE, rel));

  if (tUser === null) { // 用户没有 → 新增
    report.added.push(rel);
    if (APPLY) { const dst = path.join(BRAIN, rel); fs.mkdirSync(path.dirname(dst), { recursive: true }); fs.writeFileSync(dst, tNew); }
    continue;
  }
  if (rel === 'core/hard-rules.md') continue; // 单独处理(见下)
  if (isUserOwned(rel)) continue;             // 用户私有且已存在 → 不碰
  if (SHIPPED.has(rel)) {
    if (tUser === tNew) continue;             // 已是最新
    if (tBase !== null && tUser === tBase) {  // 用户没改过 → 安全刷新
      report.refreshed.push(rel);
      if (APPLY) fs.writeFileSync(path.join(BRAIN, rel), tNew);
    } else {                                  // 用户改过(或无基线)且上游变了 → 冲突,交给技能问
      report.conflicts.push({ file: rel, reason: tBase === null ? '无基线快照,无法判断是否被改' : '用户改过且上游也更新' });
    }
  }
}

// 2) hard-rules:找出用户缺的"默认红线",报告(不自动改文件)
(function () {
  const tNew = rd(path.join(TEMPLATE, 'core/hard-rules.md')) || '';
  const tUser = rd(path.join(BRAIN, 'core/hard-rules.md')) || '';
  // 默认红线以 "(防XXX)" 结尾,用这个 tag 作稳定 key
  const re = /\((防[^)）]+)\)/g;
  const userTags = new Set([...tUser.matchAll(re)].map(m => m[1]));
  for (const line of tNew.split(/\n/)) {
    const m = line.match(/\((防[^)）]+)\)/);
    if (m && !userTags.has(m[1])) report.rulesToAdd.push({ tag: m[1], line: line.trim() });
  }
})();

// 3) 应用后刷新基线快照 + 版本(只有 --apply 才更新,保证下次比较基于最新发货)
if (APPLY) {
  try {
    fs.rmSync(BASE, { recursive: true, force: true });
    fs.cpSync(TEMPLATE, BASE, { recursive: true });
    let ver = '0.0.0';
    try { ver = JSON.parse(fs.readFileSync(path.join(PLUGIN_ROOT, '.claude-plugin', 'plugin.json'), 'utf8')).version || ver; } catch {}
    fs.writeFileSync(path.join(BRAIN, '.meta', 'plugin-version.txt'), ver);
  } catch {}
}

process.stdout.write(JSON.stringify(report, null, 2));
