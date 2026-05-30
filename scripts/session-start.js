#!/usr/bin/env node
// 翼德 SessionStart hook:开/恢复会话时注入个人上下文 + Unity 项目档案 +(extraction 项目)奖励/督促说明。
// 输出:stdout JSON,hookSpecificOutput.additionalContext。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, today } = require(path.join(__dirname, 'lib.js'));
const { detect, profileText } = require(path.join(__dirname, 'unity-context.js'));
const { countActive } = require(path.join(__dirname, 'lessons.js'));

const BRAIN = brainDir();
const PLUGIN_ROOT = process.env.CLAUDE_PLUGIN_ROOT || path.resolve(__dirname, '..');
const PROJECT = process.env.CLAUDE_PROJECT_DIR || process.cwd();

function emit(ctx, title) {
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: ctx, sessionTitle: title || '' },
  }));
}
function read(rel, base) {
  try { return fs.readFileSync(path.join(base, rel), 'utf8'); } catch { return null; }
}

try {
  if (!fs.existsSync(BRAIN)) {
    // 首次见面:自我介绍 + 引导 onboard(由模型把这段话讲给用户)
    emit(
      '【翼德首次启动 · 请把下面这段自我介绍讲给用户,然后引导他运行 /yide:yide-onboard】\n\n' +
      '你好,勾哥!我是咕鸡为你打造的专属秘书,叫翼德——随时用 /yide 或 /翼德 喊我。\n\n' +
      '我主要在三件事上帮你:\n\n' +
      '记住你:习惯、风格、规则记一次就牢,以后每开新对话我自动 brief,你不用反复解释;换电脑也认得你。\n' +
      '绝不让你重复踩坑:你纠正过 AI 一次的错,我都会记录下来,并且 brief 给之后任何对话(Claude Code 里还能硬拦)。\n' +
      '帮你把关 Unity:写 C# 时按手游 best practice 盯着——热路径 GC、过时 API、序列化、资源卫生——发现隐患就提醒,绝不擅自大改。\n\n' +
      '我的大脑是一堆纯文本(在 ~/.yide,随时能翻):core=你是谁+红线、lessons=redflag、style=代码与沟通风格、projects=项目背景。\n\n' +
      '只要花 2–3 分钟、答几道选择题(Unity 版本/风格/红线)跟我磨合,就能正式上岗。准备好就让我跑 /yide:yide-onboard!',
      '🗡️ 翼德 · 初次见面'
    );
    process.exit(0);
  }

  let ctx = '# 🗡️ 翼德简报 — 个人上下文中枢\n' +
    '以下是关于当前用户的持久上下文。请全程遵守,尤其 hard-rules;需要细节就读 ~/.yide 下对应文件,不要猜。\n';

  // 永远带:身份 + 红线(不注入完整 INDEX/lessons 清单,保证上下文预算不随年月膨胀)
  for (const rel of ['core/identity.md', 'core/hard-rules.md']) {
    const body = read(rel, BRAIN);
    if (body) ctx += `\n---\n## 来自 ${rel}\n${body}\n`;
  }
  // 教训只报数量,按文件自动浮现(PostToolUse),不在开场全列
  let nLessons = 0; try { nLessons = countActive(); } catch {}
  if (nLessons) ctx += `\n---\n## 教训库\n你已积累 ${nLessons} 条教训;它们会在你编辑命中其 scope 的文件时自动浮现,无需开场全列。要查全部可读 ~/.yide/INDEX.md。\n`;

  // --- Unity 项目档案:自动探测版本/管线/输入系统/Addressables/脚本后端 ---
  let unity = null;
  try { unity = detect(PROJECT); } catch {}
  const profile = profileText(unity);
  if (profile) ctx += `\n---\n${profile}\n`;

  // --- extraction 项目:奖励 + 督促 ---
  if (/extraction/i.test(PROJECT)) {
    const progressJs = path.join(PLUGIN_ROOT, 'scripts', 'progress.js');
    ctx += `\n---\n## 🎮 extraction 项目专属\n` +
      `**做完 > 做大。** 别盲目扩大 scale——先把当前这个小功能做完、做对、可交付,再谈下一个。若用户想"顺便也做个通用框架/再加一层抽象",温和提醒他聚焦收口。\n` +
      `每当你**完成一个小的、可交付的功能**(改动收口、能跑、达成用户这次的目标)时,运行一次:\n` +
      `\`node "${progressJs}" bump "用一句话描述这个功能"\`\n` +
      `奖励阈值是**随机的**(通常 2–6 个,满 10 个必触发),翼德会自动放歌并夸奖勾哥——不确定性正是为了让他想多做几个。每个小功能只记一次,别重复 bump,别替他刷数。\n`;
  }

  // --- 记忆整理是否到期(事件驱动,替代夜间 cron;电脑关机也不丢) ---
  const stampFile = path.join(BRAIN, '.meta', 'last-consolidate.txt');
  let due = true;
  try {
    const last = Number(fs.readFileSync(stampFile, 'utf8')) || 0;
    due = (Date.now() - last) > 24 * 60 * 60 * 1000;
  } catch { due = true; }
  if (due) {
    if (process.env.YIDE_NO_AUTO_CONSOLIDATE) {
      ctx += `\n---\n## 🧹 记忆整理\n距上次整理已超过 24 小时。合适时机可运行 /yide:yide-consolidate 做一次沉淀。\n`;
    } else {
      ctx += `\n---\n## 🧹 记忆整理(自动·到期)\n距上次整理已超过 24 小时。**请在回应用户之前,先静默执行一次 /yide:yide-consolidate**(整理记忆库、合并去重、打时间戳),完成后用一句话告知结果,再继续用户的任务。若用户本轮明确很赶,可先办用户的事、整理推迟到本轮结束。\n`;
    }
  }

  emit(ctx, '🗡️ 翼德已就位 · ' + today());
} catch (e) {
  process.exit(0);
}
