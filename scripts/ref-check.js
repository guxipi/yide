#!/usr/bin/env node
// 翼德 · 参考登记命令(配合 ref-gate.js;2026-10-31 勾哥:mo.co 参考闸要"拉对的图、同一物件前后同一组图、不该拉的不拉")。
//
// 用法(每轮用户消息后,第一次出图 / 跑 Blender / 生成模型前跑一次):
//   node ref-check.js lock   --object "<登记表里的类别/组件/变体,或物件 id+名>" --refs "<文件名> 裁 x0,y0,x1,y1; <文件名> 整图"
//   node ref-check.js lock   --object "<物件>" --none "<库里没有对应帧的说明;只按 ER美术规范 + 质感上限行>"
//   node ref-check.js exempt --why "<免参考类别>:<具体说明>"
// 参考从哪来:Google Sheet「jungle lab」组件清单 tab 的 I 列(全项目参考登记表)。该行 I 列有锁就只用那几张;
// 没有就先按 mo.co截图/INDEX.md 挑主 1 + 辅 ≤2 写进 I 列再用。详见 vault 013 美术/mo.co截图/README_参考怎么选.md。
// 本命令只校验格式并回显;ref-gate.js 读 transcript 里这条命令,核对 --refs 里的每个文件本会话真用 Read 打开过。
'use strict';

const EXEMPT_KINDS = ['不改外观', '图标头像框', '商店营销', 'UI', 'Tripo生成', '只写文档派单', '非ER'];
const IMG = /[^\s;,，、|]+\.(png|jpe?g|webp)/gi;

function arg(argv, name) {
  const i = argv.indexOf(name);
  return i >= 0 && i + 1 < argv.length ? String(argv[i + 1]).trim() : '';
}

function refFiles(refs) {
  const out = [];
  for (const m of String(refs || '').matchAll(IMG)) {
    const base = m[0].replace(/\\/g, '/').split('/').pop();
    if (!out.includes(base)) out.push(base);
  }
  return out;
}

// 返回错误字符串;合格返回 null。
function validate(argv) {
  const mode = argv[0];
  if (mode === 'exempt') {
    const why = arg(argv, '--why');
    const kind = why.split(/[:：]/)[0].trim();
    if (!EXEMPT_KINDS.includes(kind)) return `--why 要以免参考类别开头:${EXEMPT_KINDS.join(' / ')},再写冒号和具体说明。`;
    if (why.replace(/^[^:：]+[:：]/, '').trim().length < 4) return '--why 冒号后要写具体说明(这次做什么、为什么不涉及 mo.co 质感)。';
    return null;
  }
  if (mode === 'lock') {
    const obj = arg(argv, '--object');
    if (obj.length < 2) return '--object 要写登记表里的「类别/组件/变体」,或物件 id + 名字。';
    const refs = arg(argv, '--refs'), none = arg(argv, '--none');
    if (!refs && !none) return '要么 --refs 写锁定的图(文件名 + 裁区),要么 --none 说明库里没有对应帧。';
    if (refs) {
      const files = refFiles(refs);
      if (!files.length) return '--refs 里要有图片文件名(.png/.jpg/.webp),例:moco_06-16_水面与岛.png 裁 336,500,1920,620';
      if (files.length > 3) return `--refs 最多主 1 + 辅 2,共 3 张;现在 ${files.length} 张。`;
    }
    if (none && none.length < 6) return '--none 要写清楚:查过登记表和 INDEX 都没有对应帧,改按什么做。';
    return null;
  }
  return '用法:ref-check.js lock --object … (--refs … | --none …)  或  ref-check.js exempt --why "<类别>:<说明>"';
}

if (require.main === module) {
  const argv = process.argv.slice(2);
  const err = validate(argv);
  if (err) { console.error('参考登记不合格:' + err); process.exit(1); }
  if (argv[0] === 'lock') {
    const files = refFiles(arg(argv, '--refs'));
    console.log(`已登记参考:${arg(argv, '--object')} → ` + (files.length ? files.join('、') : '无对应帧:' + arg(argv, '--none')));
    if (files.length) console.log('下一步:用 Read 打开上面每一张(按登记的裁区看),再出图 / 建模。只看这几张,不另挑。');
  } else {
    console.log('已登记免参考:' + arg(argv, '--why'));
  }
}

module.exports = { validate, refFiles, EXEMPT_KINDS };
