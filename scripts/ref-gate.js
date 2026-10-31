// 翼德 · 参考闸(2026-10-31 勾哥:"让这个 gate 发挥真正的作用")。
//
// 治的病(10-31 审计 25 个会话):红线⑥只要求"开过 mo.co 截图",不管开的是哪张、对不对、和上次是不是同一组。结果
//   ① 不同活第一步都打开同样三张整帧;② 同一张水面帧被叫成 r16 / r28,提取结论每次重写、互相矛盾;
//   ③ 出 icon、写派单也去拉 mo.co,联邦人造物挂 mo.co 神殿墙(违反 10-16 拍板 #14)。
// 规则:每一轮用户消息之后,第一次"出图 / 建模动作"前,本轮里必须跑过一次 ref-check.js 登记:
//   lock   —— 写明对象和锁定的图(来自全项目参考登记表 = Sheet「jungle lab」组件清单 I 列),
//             --refs 里的每个文件本会话必须真用 Read 打开过(实看,不靠记忆、不靠转存的 ref/ 拷贝);
//   lock --none —— 登记表和 INDEX 都没有对应帧,写明改按什么做;
//   exempt —— 不涉及 mo.co 质感的活(只导出、图标、UI、Tripo 生成…)。
// "出图 / 建模动作" = 跑 Blender 脚本 / Blender MCP 执行代码、派 codex 出图、Coplay 生成图片或 3D。图标头像框(gemini CLI)不算。
// 读不到 transcript 不拦;Codex 宿主跳过;.meta/skill-gates.json 里 {"refGate":{"enabled":false}} 或 YIDE_REF_GATE=0 可关。
'use strict';
const path = require('path');
const fs = require('fs');
const { validate, refFiles } = require(path.join(__dirname, 'ref-check.js'));

const NOT_A_TURN = /^\s*<(task-notification|side-sessions-event|ci-monitor-event|local-command|command-name|bash-)/;
const CODEX_IMAGE = /image_gen|生图|出图|概念图|四视图|三视图|paint\s*-?over|手绘|mockup|渲染图|重绘/i;

function genAction(tool, ti) {
  if (tool === 'Bash' || tool === 'PowerShell') {
    const c = typeof ti.command === 'string' ? ti.command : '';
    if (/ref-check\.js/.test(c)) return null;
    if (/blender/i.test(c) && /\s-b\s/.test(c) && /\s(-P|--python|--python-expr)\s/.test(c)) return '跑 Blender 脚本';
    if (/\bcodex\s+exec\b|run_codex\.sh/.test(c) && CODEX_IMAGE.test(c)) return '派 codex 出图';
    return null;
  }
  if (tool === 'mcp__blender__execute_blender_code' || tool === 'mcp__blender__execute_blender_code_for_cli') return '在 Blender 里执行代码';
  if (/^mcp__coplay-mcp__(generate_or_edit_images|generate_3d_model_from_image|generate_3d_model_from_text|generate_3d_model_texture)$/.test(tool)) return '用 Coplay 生成图片 / 3D';
  return null;
}

function isUserTurn(o) {
  if (!o || o.type !== 'user' || o.isMeta) return false;
  const c = o.message && o.message.content;
  const texts = typeof c === 'string' ? [c]
    : Array.isArray(c) ? (c.some(x => x && x.type === 'tool_result') ? [] : c.filter(x => x && x.type === 'text').map(x => x.text || ''))
    : [];
  for (const t of texts) {
    const s = String(t).replace(/<system-reminder>[\s\S]*?<\/system-reminder>/g, '').trim();
    if (s && !NOT_A_TURN.test(s)) return true;
  }
  return false;
}

function toolUses(o) {
  const c = o && o.type === 'assistant' && o.message && o.message.content;
  return Array.isArray(c) ? c.filter(x => x && x.type === 'tool_use') : [];
}

// 极简 shell 分词:认双引号、单引号,够解析 ref-check 的参数。
function shellArgs(s) {
  const out = []; let cur = '', q = null, any = false;
  for (const ch of String(s)) {
    if (q) { if (ch === q) q = null; else cur += ch; continue; }
    if (ch === '"' || ch === "'") { q = ch; any = true; continue; }
    if (/\s/.test(ch)) { if (any || cur) { out.push(cur); cur = ''; any = false; } continue; }
    cur += ch;
  }
  if (any || cur) out.push(cur);
  return out;
}

const REC_RE = /^\s*node(?:\.exe)?\s+["']?[^"'\n]*ref-check\.js["']?\s+(lock|exempt)\b/m;

function check(input, opts) {
  const tool = input.tool_name || '';
  const ti = input.tool_input || {};
  const action = genAction(tool, ti);
  if (!action) return null;
  let tx = '';
  try { tx = input.transcript_path ? fs.readFileSync(input.transcript_path, 'utf8') : ''; } catch { tx = ''; }
  if (!tx) return null;

  const rows = [];
  for (const line of tx.split('\n')) { if (!line) continue; try { rows.push(JSON.parse(line)); } catch {} }

  // 本会话所有 Read 过的文件名(实看证据)。
  const readBases = new Set();
  for (const o of rows) for (const u of toolUses(o)) {
    if (u.name === 'Read' && u.input && u.input.file_path) readBases.add(String(u.input.file_path).replace(/\\/g, '/').split('/').pop().toLowerCase());
  }
  // 本轮最后一条登记。
  let rec = null;
  for (let k = rows.length - 1; k >= 0 && !rec; k--) {
    if (isUserTurn(rows[k])) break;
    for (const u of toolUses(rows[k]).reverse()) {
      const c = u.input && u.input.command;
      if ((u.name === 'Bash' || u.name === 'PowerShell') && REC_RE.test(String(c || ''))) { rec = String(c); break; }
    }
  }

  const script = path.join(opts.pluginRoot, 'scripts', 'ref-check.js').split(path.sep).join('/');
  const head = `🗡️ 翼德参考闸:这一轮要「${action}」,先登记这次对标哪几张 mo.co 图(或为什么不用)。\n`;
  const how =
    '① 判断要不要参考:改外观的局内图像 / 模型才要;只导出、图标头像框、商店营销、UI、Tripo 生成、只写派单都不要 → 跑 exempt。\n' +
    '② 要参考:查全项目参考登记表 = Google Sheet「jungle lab」组件清单(1olWlOYGpraTlgkNIUQCYwZVyqGqGdibDeKTmInzX7zk)I 列,找本物件那一行;' +
    '有锁就只用那几张、那几块裁区;没有就按 vault 013 美术/mo.co截图/INDEX.md 挑主 1 + 辅 ≤2 写回 I 列;都没有写 --none。' +
    '人造物(建筑、墙、柱、箱、桥…)外形不挂 mo.co,只挂我们认可的概念图(拍板 #14)。\n' +
    '③ 用 Read 打开登记的每一张原图(不要读转存的 ref/ 拷贝),再登记:\n' +
    `node "${script}" lock --object "<类别/组件/变体 或 物件id+名>" --refs "<文件名> 裁 x0,y0,x1,y1; <文件名> 整图"\n` +
    `node "${script}" lock --object "<物件>" --none "<查过登记表和 INDEX 都没有;改按 …>"\n` +
    `node "${script}" exempt --why "<不改外观|图标头像框|商店营销|UI|Tripo生成|只写文档派单|非ER>:<具体说明>"\n` +
    '规则全文:vault 013 美术/mo.co截图/README_参考怎么选.md。';
  if (!rec) return head + how;
  const args = shellArgs(rec.slice(rec.search(/ref-check\.js/) + 'ref-check.js'.length).replace(/^["']/, ''));
  const err = validate(args);
  if (err) return head + '本轮的登记不合格:' + err + '\n' + how;
  if (args[0] === 'lock') {
    const i = args.indexOf('--refs');
    const files = i >= 0 ? refFiles(args[i + 1]) : [];
    const unread = files.filter(f => !readBases.has(f.toLowerCase()));
    if (unread.length) return head + `登记了 ${unread.join('、')},但本会话还没用 Read 打开过它(们)。先打开原图实看,再继续。`;
  }
  return null;
}

module.exports = { check, genAction, shellArgs };
