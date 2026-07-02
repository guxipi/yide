#!/usr/bin/env node
// 翼德 · GUID 反查:给一个 asset 路径或 32 位 GUID,找出项目里所有引用它的资产(谁在用它)。
// 换/删资产前先查引用面,免留 missing 引用。自实现递归扫描,不依赖 rg。
//   node scripts/guid-find.js <asset路径 或 GUID> [项目根]
//   项目根缺省取 YIDE_UNITY_PROJECT / CLAUDE_PROJECT_DIR。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');

// Unity 序列化里 GUID 引用出现在这些文本资产/元文件中。
const SCAN_EXT = new Set(['.unity', '.prefab', '.asset', '.mat', '.controller', '.anim', '.overridecontroller', '.playable', '.mask', '.spriteatlas', '.shadervariants', '.preset', '.lighting', '.rendertexture', '.guiskin', '.meta']);
const SKIP_DIR = new Set(['Library', 'Temp', 'obj', 'Build', 'Builds', 'Logs', '.git', 'node_modules']);

// 从 input 解析出 GUID:input 本身是 32 位 hex → 直接用;否则当 asset 路径,读同名 .meta 的 guid。
function resolveGuid(input, root) {
  if (/^[0-9a-fA-F]{32}$/.test(input)) return input.toLowerCase();
  let meta = input.endsWith('.meta') ? input : input + '.meta';
  if (!path.isAbsolute(meta)) meta = path.join(root || '.', meta);
  let txt = '';
  try { txt = fs.readFileSync(meta, 'utf8'); } catch { return null; }
  const m = txt.match(/guid:\s*([0-9a-fA-F]{32})/);
  return m ? m[1].toLowerCase() : null;
}

function walk(dir, out = []) {
  let ents = [];
  try { ents = fs.readdirSync(dir, { withFileTypes: true }); } catch { return out; }
  for (const e of ents) {
    if (e.isDirectory()) { if (!SKIP_DIR.has(e.name)) walk(path.join(dir, e.name), out); }
    else if (SCAN_EXT.has(path.extname(e.name).toLowerCase())) out.push(path.join(dir, e.name));
  }
  return out;
}

// 返回引用了 guid 的文件相对路径清单(不含 guid 自己的 .meta)。
function findReferencers(guid, root) {
  const g = String(guid).toLowerCase();
  const assets = path.join(root, 'Assets');
  const hits = [];
  for (const f of walk(fs.existsSync(assets) ? assets : root)) {
    let txt = '';
    try { txt = fs.readFileSync(f, 'utf8'); } catch { continue; }
    // 跳过 guid 自身所属 .meta(那是"定义"不是"引用")
    if (f.endsWith('.meta') && new RegExp('^guid:\\s*' + g, 'm').test(txt)) continue;
    if (txt.toLowerCase().includes(g)) hits.push(path.relative(root, f));
  }
  return hits;
}

module.exports = { resolveGuid, findReferencers };

if (require.main === module) {
  const input = process.argv[2];
  const root = process.argv[3] || process.env.YIDE_UNITY_PROJECT || process.env.CLAUDE_PROJECT_DIR || '';
  if (!input) { process.stdout.write('用法:node scripts/guid-find.js <asset路径 或 GUID> [项目根]\n'); process.exit(2); }
  if (!root || !fs.existsSync(path.join(root, 'Assets'))) { process.stdout.write(`ERR\t项目根无效(需含 Assets/):${root || '(空)'}\n`); process.exit(2); }
  const guid = resolveGuid(input, root);
  if (!guid) { process.stdout.write(`ERR\t解析不出 GUID:${input}(路径对吗?有 .meta 吗?)\n`); process.exit(2); }
  const hits = findReferencers(guid, root);
  process.stdout.write(`GUID ${guid} —— ${hits.length} 处引用:\n`);
  for (const h of hits) process.stdout.write('  - ' + h + '\n');
  if (!hits.length) process.stdout.write('  (无引用 —— 换/删相对安全)\n');
  process.exit(0);
}
