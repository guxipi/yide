#!/usr/bin/env node
// 翼德 SessionStart hook:开/恢复会话时注入个人上下文 + Unity 项目档案 +(extraction 项目)奖励/督促说明。
// 输出:stdout JSON,hookSpecificOutput.additionalContext。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const { brainDir, today, locationPointerPath } = require(path.join(__dirname, 'lib.js'));
const { detect, profileText } = require(path.join(__dirname, 'unity-context.js'));
const { countActive } = require(path.join(__dirname, 'lessons.js'));
const { syncExperts } = require(path.join(__dirname, 'sync-experts.js'));
const { extractionContext } = require(path.join(__dirname, 'extraction-context.js'));
const store = require(path.join(__dirname, 'store.js'));
const { resolve } = require(path.join(__dirname, 'resolve.js'));
const host = require(path.join(__dirname, 'host.js'));

// a < b ?(semver,缺位按 0)
function verLt(a, b) {
  const pa = String(a).split('.').map(n => parseInt(n, 10) || 0);
  const pb = String(b).split('.').map(n => parseInt(n, 10) || 0);
  for (let i = 0; i < 3; i++) { if ((pa[i] || 0) < (pb[i] || 0)) return true; if ((pa[i] || 0) > (pb[i] || 0)) return false; }
  return false;
}

const BRAIN = brainDir();
const PLUGIN_ROOT = host.pluginRoot();  // Claude Code / Codex / 裸跑,统一收口在 host.js
const PROJECT = host.projectDir();

function emit(ctx, title) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: ctx, sessionTitle: title || '' },
  }));
}
function read(rel, base) {
  try { return fs.readFileSync(path.join(base, rel), 'utf8'); } catch { return null; }
}
function pointerTarget() {
  try { const s = String(fs.readFileSync(locationPointerPath(), 'utf8')).trim(); if (s) return s; } catch {}
  return process.env.YIDE_HOME || '';
}

try {
  const brainExists = fs.existsSync(BRAIN);
  // 之前是否认领过大脑(有指针文件或 YIDE_HOME)。认领过 = 老用户,绝不能当新人重新 onboard(那正是幽灵大脑的成因)。
  const claimed = !!pointerTarget();

  // 大脑离线:认领过、但目标目录当前不在(同步盘没挂载 / 盘符没起)→ 提示离线,绝不重新 onboarding。
  if (!brainExists && claimed) {
    emit(
      '⚠️ 【翼德:大脑离线 —— 不要当新用户处理】\n' +
      '你的大脑指针指向的目录当前不存在,多半是 **Google Drive / 同步盘还没挂载**(或盘符没起)。\n' +
      `- 指针指向:${pointerTarget()}\n` +
      '- 请勾哥确认同步盘挂载后**重开会话**;在此之前**不要重新 onboarding、不要新建大脑**(会和真身分裂成幽灵大脑)。\n' +
      '- 应急加载红线:待盘挂上后读该目录下 core/hard-rules.md。',
      '🗡️ 翼德 · 大脑离线'
    );
    process.exit(0);
  }

  if (!brainExists) {
    // 真·首次见面(既没大脑也没指针):自我介绍 + 引导 onboard(由模型把这段话讲给用户)
    emit(
      '【翼德首次启动 · 请把下面这段自我介绍讲给用户,然后引导他说"翼德,磨合一下"来开始 onboarding】\n\n' +
      '你好,勾哥!我是咕鸡为你打造的专属秘书,叫翼德——**直接喊我就行**:跟我说"翼德,…"(如"翼德,磨合一下""翼德 记一下…")。\n\n' +
      '我主要在三件事上帮你:\n\n' +
      '记住你:习惯、风格、规则记一次就牢,以后每开新对话我自动 brief,你不用反复解释;换电脑也认得你。\n' +
      '绝不让你重复踩坑:你纠正过 AI 一次的错,我都会记录下来,并且 brief 给之后任何对话(Claude Code 里还能硬拦)。\n' +
      '帮你把关 Unity:写 C# 时按手游 best practice 盯着——热路径 GC、过时 API、序列化、资源卫生——发现隐患就提醒,绝不擅自大改。\n\n' +
      '我的大脑是一堆纯文本(在 ~/.yide,随时能翻):core=你是谁+红线、lessons=redflag、style=代码与沟通风格、projects=项目背景。\n\n' +
      '只要花 2–3 分钟、答几道选择题(Unity 版本/风格/红线)跟我磨合,就能正式上岗。准备好就说一句"翼德,磨合一下"(或打命令 /yide:yide onboard)!',
      '🗡️ 翼德 · 初次见面'
    );
    process.exit(0);
  }

  // 大脑完整性哨兵:目录存在但缺关键文件(INDEX.md / core/identity.md)= 指针指错一层 / 幽灵大脑。
  // 绝不当正常大脑用、绝不 onboarding —— 只醒目报警,让勾哥修指针。
  const hasIndex = fs.existsSync(path.join(BRAIN, 'INDEX.md'));
  const hasIdentity = fs.existsSync(path.join(BRAIN, 'core', 'identity.md'));
  if (!hasIndex || !hasIdentity) {
    const missing = [!hasIndex ? 'INDEX.md' : null, !hasIdentity ? 'core/identity.md' : null].filter(Boolean).join(' + ');
    emit(
      '⚠️ 【翼德:大脑不完整 —— 极可能指针指错目录,别当正常大脑用】\n' +
      `当前大脑目录存在,但缺少关键文件(${missing}),你的身份 / 红线 / 教训都加载不到。\n` +
      `- 当前指向:${BRAIN}\n` +
      '- **最常见原因:指针多写了一层目录**(如 …/My Drive/yide/yide-brain,正确应为 …/My Drive/yide-brain)。健康大脑的根目录**直接含** INDEX.md 与 core/identity.md。\n' +
      '- 请勾哥把 ~/.yide-location 指回正确的大脑根目录后**重开会话**;修好前**不要 onboarding、不要新建大脑**。可跑"翼德 体检"定位。',
      '🗡️ 翼德 · 大脑不完整'
    );
    process.exit(0);
  }

  // 大脑迁 git 后:开场先 ff-only 拉最新(读大脑文件前),失败不阻塞、只留一行提示。非 git 大脑 no-op。
  let pullWarn = '';
  try { const pr = require(path.join(__dirname, 'brain-git.js')).pull(BRAIN); if (pr.git && !pr.ok) pullWarn = pr.msg || '未知'; } catch {}

  // 把可移植的专家副本同步进 ~/.claude/agents/(跨设备后仍可召唤);静默,不污染输出
  try { syncExperts(); } catch {}

  let ctx = '# 🗡️ 翼德简报 — 个人上下文中枢\n' +
    '以下是关于当前用户的持久上下文。请全程遵守,尤其 hard-rules;需要细节就读 ~/.yide 下对应文件,不要猜。\n';
  if (pullWarn) ctx += `\n---\n## ⚠️ 大脑同步\ngit pull 失败(${pullWarn}),本机大脑可能落后其他机器;联网后手动 \`git -C <大脑目录> pull --ff-only\`。\n`;

  // 永远带:身份(用户层)+ 红线 + 工作准则(发货默认 + 用户层,resolver 在"读取时"合并,不写盘)
  // 顺序:identity(我是谁)→ hard-rules(不许做)→ charter(该怎么做);charter 明确"红线优先"。
  const idBody = read('core/identity.md', BRAIN);
  if (idBody) ctx += `\n---\n## 来自 core/identity.md\n${idBody}\n`;
  try { const rl = resolve('hard-rules', PLUGIN_ROOT, BRAIN); if (rl) ctx += `\n---\n## 绝对红线(默认 + 你的自定义;全程遵守)\n${rl}\n`; } catch {}
  try { const ch = resolve('charter', PLUGIN_ROOT, BRAIN); if (ch) ctx += `\n---\n## 工作准则\n${ch}\n`; } catch {}
  // 教训只报数量,按文件自动浮现(PostToolUse),不在开场全列
  let nLessons = 0; try { nLessons = countActive(); } catch {}
  if (nLessons) ctx += `\n---\n## 教训库\n已积累 ${nLessons} 条教训(按文件自动浮现;全部见 ~/.yide/INDEX.md)。\n`;

  // prompt 库:自动静默捕获(不打断)。召回由 UserPromptSubmit hook 负责,无需在此提示。
  ctx += `\n---\n## prompt 库\n某条 prompt 明显好用(≥2:几轮搞定/说"对了"/没返工/常重复)且库里没近似 → 静默存入 ~/.yide/prompts 跑 prompts.js index,回一行即可;拿不准别存。\n`;

  // 随手记 inbox:只报未整理条数(手机扔进来的笔记)
  let nInbox = 0;
  try { nInbox = fs.readdirSync(path.join(BRAIN, 'notes', 'inbox')).filter(n => !n.startsWith('.') && !n.startsWith('_')).length; } catch {}
  if (nInbox) ctx += `\n---\n## 📥 随手记\n收件箱有 ${nInbox} 条未整理的笔记。合适时机执行一次笔记整理(note 动作:读 actions/note.md),或提醒勾哥说"翼德 整理笔记"。\n`;

  // --- Unity 项目档案:自动探测版本/管线/输入系统/Addressables/脚本后端 ---
  let unity = null;
  try { unity = detect(PROJECT); } catch {}
  const profile = profileText(unity);
  if (profile) ctx += `\n---\n${profile}\n`;

  // --- extraction 个人项目专属(奖励/督促/张飞人格/彩蛋);逻辑已拆到 extraction-context.js ---
  try { ctx += extractionContext(BRAIN, PROJECT, PLUGIN_ROOT); } catch {}

  // --- 记忆整理是否到期(事件驱动,替代夜间 cron;电脑关机也不丢) ---
  let due = true;
  try {
    const last = Number(store.readText('last-consolidate.txt', '0')) || 0;
    due = (Date.now() - last) > 24 * 60 * 60 * 1000;
  } catch { due = true; }
  if (due) {
    if (process.env.YIDE_NO_AUTO_CONSOLIDATE) {
      ctx += `\n---\n## 🧹 记忆整理\n距上次整理已超过 24 小时。合适时机执行一次记忆整理(consolidate 动作:读 actions/consolidate.md)。\n`;
    } else {
      ctx += `\n---\n## 🧹 记忆整理(到期)\n距上次>24h。回应用户前先静默执行一次记忆整理(consolidate 动作:读 actions/consolidate.md,合并去重+打时间戳),一句话告知后继续;用户若很赶则推迟到本轮末。\n`;
    }
  }

  // --- 发货默认跟插件走:版本变了跑一次 migrate,把模板新增/刷新真正落地(以前只打版本戳→快照冻结,模板改进到不了 live) ---
  try {
    const brainVer = String(store.readText('plugin-version.txt', '') || '').trim();
    let pluginVer = '';
    try { pluginVer = JSON.parse(fs.readFileSync(path.join(PLUGIN_ROOT, '.claude-plugin', 'plugin.json'), 'utf8')).version || ''; } catch {}
    if (pluginVer && brainVer !== pluginVer) {
      const behind = !brainVer || verLt(brainVer, pluginVer);
      if (!behind) {
        // 大脑版本领先插件(异常/回退)→ 不迁移(免把 SHIPPED 降级),只打戳消提示
        store.writeText('plugin-version.txt', pluginVer);
      } else {
        // 落后:跑 migrate --apply。安全部分(added/refreshed)立即落盘;有冲突/缺红线则 migrate 不打戳(见 migrate.js)
        let plan = null;
        try {
          const out = execFileSync('node', [path.join(__dirname, 'migrate.js'), '--apply'], {
            encoding: 'utf8',
            env: Object.assign({}, process.env, { CLAUDE_PLUGIN_ROOT: PLUGIN_ROOT, YIDE_HOME: BRAIN }),
          });
          plan = JSON.parse(out);
        } catch {}
        const conflicts = plan ? plan.conflicts.length : 0;
        const rulesToAdd = plan ? plan.rulesToAdd.length : 0;
        if (conflicts || rulesToAdd) {
          // 有需要勾哥裁决的:引导跑"翼德 update";migrate 没打戳,故此提示会持续到裁决完成
          ctx += `\n---\n## 🔄 翼德 v${pluginVer} 有待你确认的更新\n` +
            `有 ${conflicts} 处发货文件冲突` + (rulesToAdd ? ` / ${rulesToAdd} 条新默认红线` : '') +
            ` 待你裁决 —— 跑一次"翼德 update"(读 actions/update.md);裁决前不改你的数据。安全的新增/刷新已自动合并。\n`;
        } else if (brainVer) {
          const added = plan ? plan.added.length : 0;
          const refreshed = plan ? plan.refreshed.length : 0;
          const note = (added || refreshed) ? `(${added} 新增 / ${refreshed} 刷新已自动合并)` : '';
          ctx += `\n---\n## 🔄 翼德已更新到 v${pluginVer}\n发货默认${note}**已自动生效**(没碰你的私有数据)。想看改了啥:README changelog。\n`;
        }
        // migrate --apply 内部已在"干净"时打好版本戳;若失败没打戳,下次开会话会重试,安全。
      }
    }
  } catch {}

  emit(ctx, '🗡️ 翼德已就位 · ' + today());
} catch (e) {
  // 别静默失联:出错也给一条最小降级简报,至少让新会话知道翼德在、红线去哪读,而不是整段消失(H: 盘没挂/超时都会走到这)。
  try {
    emit(
      '🗡️ 翼德简报加载失败(降级模式)\n' +
      `简报生成时出错(${(e && e.message) || '未知错误'}),这轮只给最小提示:\n` +
      '- 我(翼德)仍在;需要身份/红线/风格时,请读 ~/.yide/core/hard-rules.md 与 core/identity.md。\n' +
      '- 若反复出现,多半是大脑目录 / 同步盘异常 —— 让勾哥跑一次"翼德 体检"。',
      '🗡️ 翼德 · 降级简报'
    );
  } catch {}
  process.exit(0);
}
