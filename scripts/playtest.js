'use strict';
// 翼德 · playtest 冻帧标注处理流水线(纯 Node,无第三方依赖)。
//   勾哥在 Unity 里按 F8 标注 → 每条一个 marker 文件夹(shot.png + context.json + voice.wav? + note.txt?)。
//   本脚本:批量本地转写语音(SenseVoice)+ 把 打字补充 / 转写 / 上下文 合成一份清单 → 翼德据此出问题清单。
//
// 设计(诚实):
//   · 扫 marker、读 context、合并文本、出 manifest —— 确定性,可单测。
//   · 语音转写走本地 SenseVoice(integrations/playtest-capture/asr_sensevoice.py),离线免费、中文强、不上云。
//     没装 Python/funasr → 不报错,降级:有打字就用打字,没有就标"仅截图+上下文"。
//
// 用法:
//   node scripts/playtest.js [session目录]     # 不给=自动取 QA/playtest 最新一场
//   node scripts/playtest.js --no-asr [目录]   # 跳过语音转写(只用打字+上下文)
//   node scripts/playtest.js --help

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function die(m) { console.error('[翼德 playtest] ' + m); process.exit(1); }
function log(m) { console.log('[翼德 playtest] ' + m); }

function findPython() {
  // 显式指定优先(用了 venv / py 启动器 / 非默认 python 时设 YIDE_PYTHON)
  if (process.env.YIDE_PYTHON) return process.env.YIDE_PYTHON;
  for (const p of ['python', 'python3', 'py']) {
    try { if (spawnSync(p, ['--version'], { encoding: 'utf8' }).status === 0) return p; } catch {}
  }
  return null;
}

// 调本地 SenseVoice 批量转写,返回 { wavAbsPath: text }
function transcribeAll(wavs, skillDir) {
  const out = {};
  if (!wavs.length) return out;
  const py = findPython();
  const script = path.join(skillDir, 'integrations', 'playtest-capture', 'asr_sensevoice.py');
  if (!py || !fs.existsSync(script)) {
    log('⚠️ 未找到 Python 或 asr_sensevoice.py → 跳过语音转写(降级:用打字/上下文)。装法见 SETUP.md');
    return out;
  }
  log(`本地 SenseVoice 转写 ${wavs.length} 段(首次会拉模型,稍候)…`);
  const r = spawnSync(py, [script, ...wavs], { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (r.status !== 0) {
    log('⚠️ 转写失败(降级):' + ((r.stderr || '').split('\n').find(Boolean) || 'unknown'));
    return out;
  }
  for (const line of (r.stdout || '').split('\n')) {
    const s = line.trim(); if (!s) continue;
    try { const o = JSON.parse(s); if (o.wav) out[o.wav] = o.text || ''; } catch {}
  }
  return out;
}

function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    console.log([
      '翼德 playtest 冻帧标注处理',
      '  node scripts/playtest.js [session目录]   自动取 QA/playtest 最新一场',
      '  node scripts/playtest.js --no-asr [目录]  跳过语音转写',
    ].join('\n'));
    return;
  }
  const noAsr = args.includes('--no-asr');
  const positional = args.filter(a => !a.startsWith('--'));
  const projectDir = process.env.CLAUDE_PROJECT_DIR || process.cwd();
  const skillDir = process.env.CLAUDE_SKILL_DIR || path.resolve(__dirname, '..');

  // 定位 session
  let session = positional[0];
  const ptDir = path.join(projectDir, 'QA', 'playtest');
  if (!session) {
    if (!fs.existsSync(ptDir)) die('没找到 QA/playtest,先在 Unity 里按 F8 标注几条。');
    const sessions = fs.readdirSync(ptDir)
      .filter(f => /^session-/.test(f) && fs.statSync(path.join(ptDir, f)).isDirectory())
      .map(f => ({ f, t: fs.statSync(path.join(ptDir, f)).mtimeMs }))
      .sort((a, b) => b.t - a.t);
    if (!sessions.length) die('QA/playtest 里没有标注 session。');
    session = path.join(ptDir, sessions[0].f);
  }
  if (!fs.existsSync(session)) die('session 不存在:' + session);
  log('处理 session:' + path.relative(projectDir, session));

  // 收集 marker
  const markers = fs.readdirSync(session)
    .filter(f => /^marker-/.test(f) && fs.statSync(path.join(session, f)).isDirectory())
    .sort()
    .map(f => {
      const dir = path.join(session, f);
      const ctxPath = path.join(dir, 'context.json');
      let ctx = {}; try { ctx = JSON.parse(fs.readFileSync(ctxPath, 'utf8')); } catch {}
      const wav = fs.existsSync(path.join(dir, 'voice.wav')) ? path.join(dir, 'voice.wav') : null;
      let typed = ''; try { typed = fs.readFileSync(path.join(dir, 'note.txt'), 'utf8').trim(); } catch {}
      return { name: f, dir, ctx, wav, typed };
    });
  if (!markers.length) die('这一场没有 marker 文件夹。');
  log(`收集到 ${markers.length} 条标注。`);

  // 转写:只补转"录制时没当场确认过文字"的(有 note.txt = 勾哥在 Unity 里已转写+确认,直接用,不重转免重复)
  const wavs = noAsr ? [] : markers.filter(m => m.wav && !m.typed).map(m => m.wav);
  const trans = transcribeAll(wavs, skillDir);
  if (!noAsr && markers.some(m => m.typed)) log(`其中 ${markers.filter(m => m.typed).length} 条已在 Unity 里当场转写确认,直接采用。`);

  // 合成清单
  const items = markers.map(m => {
    const said = m.wav ? (trans[m.wav] || '') : '';
    const note = [said, m.typed].filter(Boolean).join(' / ');
    return {
      marker: m.name,
      shot: path.relative(projectDir, path.join(m.dir, 'context.json')).replace(/context\.json$/, 'shot.png'),
      scene: m.ctx.scene || '?',
      hitPath: m.ctx.hitPath || '',
      hitSource: m.ctx.hitSource || '',
      resolution: m.ctx.resolution || '',
      fps: m.ctx.fps,
      version: m.ctx.version || '',
      timeInGame: m.ctx.timeInGame,
      said,           // 语音转写
      typed: m.typed, // 打字补充
      note,           // 合并后的"勾哥说的"
    };
  });

  const manifest = { session: path.relative(projectDir, session), count: items.length, items };
  fs.writeFileSync(path.join(session, 'manifest.json'), JSON.stringify(manifest, null, 2), 'utf8');

  // 给翼德的速览(它再 Read 每张 shot.png 出问题清单)
  console.log('\n──────── 翼德请按此处理 ────────');
  console.log('session:' + path.relative(projectDir, session) + '  ·  ' + items.length + ' 条标注');
  for (const it of items) {
    console.log(`\n[${it.marker}] 场景 ${it.scene} · ${it.hitPath || '(无命中)'}${it.hitSource ? ' ← ' + it.hitSource : ''}`);
    console.log('  截图:' + it.shot);
    console.log('  勾哥:' + (it.note || '(无语音/打字 — 仅截图+上下文)'));
  }
  console.log('\n下一步:逐条 Read shot.png 看画面,结合"勾哥说的 + 命中元素路径"出带定位的问题清单 → 映射脚本/Prefab → 走联合优化回流。');
}

main();
