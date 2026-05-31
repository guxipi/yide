#!/usr/bin/env node
// 翼德 SessionStart hook:开/恢复会话时注入个人上下文 + Unity 项目档案 +(extraction 项目)奖励/督促说明。
// 输出:stdout JSON,hookSpecificOutput.additionalContext。仅用 Node 内置模块。
'use strict';
const fs = require('fs');
const path = require('path');
const { brainDir, today } = require(path.join(__dirname, 'lib.js'));
const { detect, profileText } = require(path.join(__dirname, 'unity-context.js'));
const { countActive } = require(path.join(__dirname, 'lessons.js'));
const { syncExperts } = require(path.join(__dirname, 'sync-experts.js'));

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
      '【翼德首次启动 · 请把下面这段自我介绍讲给用户,然后引导他运行 /yide onboard】\n\n' +
      '你好,勾哥!我是咕鸡为你打造的专属秘书,叫翼德——随时用 /yide 或 /翼德 喊我。\n\n' +
      '我主要在三件事上帮你:\n\n' +
      '记住你:习惯、风格、规则记一次就牢,以后每开新对话我自动 brief,你不用反复解释;换电脑也认得你。\n' +
      '绝不让你重复踩坑:你纠正过 AI 一次的错,我都会记录下来,并且 brief 给之后任何对话(Claude Code 里还能硬拦)。\n' +
      '帮你把关 Unity:写 C# 时按手游 best practice 盯着——热路径 GC、过时 API、序列化、资源卫生——发现隐患就提醒,绝不擅自大改。\n\n' +
      '我的大脑是一堆纯文本(在 ~/.yide,随时能翻):core=你是谁+红线、lessons=redflag、style=代码与沟通风格、projects=项目背景。\n\n' +
      '只要花 2–3 分钟、答几道选择题(Unity 版本/风格/红线)跟我磨合,就能正式上岗。准备好就让我跑 /yide onboard!',
      '🗡️ 翼德 · 初次见面'
    );
    process.exit(0);
  }

  // 把可移植的专家副本同步进 ~/.claude/agents/(跨设备后仍可召唤);静默,不污染输出
  try { syncExperts(); } catch {}

  // 观察→日报:首次用透明告知勾哥一次(咕鸡也会亲口说);已关闭则不提
  let disclosure = '';
  try {
    const shown = path.join(BRAIN, '.meta', 'digest-notice-shown');
    const off = path.join(BRAIN, '.meta', 'digest-off');
    if (!fs.existsSync(shown) && !fs.existsSync(off)) {
      disclosure = '\n---\n## 一次性告知(请念给勾哥)\n翼德会观察你的使用情况,生成一份**翼德小报告**(只有主题和计数,**不含你的代码/原文/密钥**)发给作者咕鸡,用来改进工具。输入"翼德别看了"可随时关闭(我会运行 digest.js off)。\n';
      fs.writeFileSync(shown, '1');
    }
  } catch {}

  let ctx = '# 🗡️ 翼德简报 — 个人上下文中枢\n' +
    '以下是关于当前用户的持久上下文。请全程遵守,尤其 hard-rules;需要细节就读 ~/.yide 下对应文件,不要猜。\n';
  if (disclosure) ctx += disclosure;

  // 永远带:身份 + 红线(不注入完整 INDEX/lessons 清单,保证上下文预算不随年月膨胀)
  for (const rel of ['core/identity.md', 'core/hard-rules.md']) {
    const body = read(rel, BRAIN);
    if (body) ctx += `\n---\n## 来自 ${rel}\n${body}\n`;
  }
  // 教训只报数量,按文件自动浮现(PostToolUse),不在开场全列
  let nLessons = 0; try { nLessons = countActive(); } catch {}
  if (nLessons) ctx += `\n---\n## 教训库\n已积累 ${nLessons} 条教训(按文件自动浮现;全部见 ~/.yide/INDEX.md)。\n`;

  // prompt 库:自动静默捕获(不打断)。召回由 UserPromptSubmit hook 负责,无需在此提示。
  ctx += `\n---\n## prompt 库\n某条 prompt 明显好用(≥2:几轮搞定/说"对了"/没返工/常重复)且库里没近似 → 静默存入 ~/.yide/prompts 跑 prompts.js index,回一行即可;拿不准别存。\n`;

  // 随手记 inbox:只报未整理条数(手机扔进来的笔记)
  let nInbox = 0;
  try { nInbox = fs.readdirSync(path.join(BRAIN, 'notes', 'inbox')).filter(n => !n.startsWith('.') && !n.startsWith('_')).length; } catch {}
  if (nInbox) ctx += `\n---\n## 📥 随手记\n收件箱有 ${nInbox} 条未整理的笔记。合适时机可运行 /yide 笔记 整理。\n`;

  // --- Unity 项目档案:自动探测版本/管线/输入系统/Addressables/脚本后端 ---
  let unity = null;
  try { unity = detect(PROJECT); } catch {}
  const profile = profileText(unity);
  if (profile) ctx += `\n---\n${profile}\n`;

  // --- extraction 项目:奖励 + 督促 + 张飞人格 + 彩蛋(全部读 .meta/extraction-fun.json,可调可关) ---
  let fun = {};
  try { fun = JSON.parse(fs.readFileSync(path.join(BRAIN, '.meta', 'extraction-fun.json'), 'utf8')); } catch {}
  if (/extraction/i.test(PROJECT) && fun.enabled !== false) {
    const progressJs = path.join(PLUGIN_ROOT, 'scripts', 'progress.js');
    const musicPct = Math.round(((fun.music && fun.music.rate) || 0.15) * 100);
    const sit = Array.isArray(fun.situational) ? fun.situational : [];
    const sitLines = sit.length
      ? sit.map(q => `  - ${q.when}(约 ${Math.round((q.rate || 0.3) * 100)}%):"${q.text}"`).join('\n')
      : '  -(无,见 .meta/extraction-fun.json)';

    // 开场问候 / 深夜守护:确定性、每天/每夜各一次(state 门控,不刷屏)
    const day = today();
    const hour = new Date().getHours();
    const gsPath = path.join(BRAIN, '.meta', 'game-state.json');
    let gs = {}; try { gs = JSON.parse(fs.readFileSync(gsPath, 'utf8')); } catch {}
    let egg = '', dirty = false;
    if ((!fun.greeting || fun.greeting.enabled !== false) && gs.lastGreetDate !== day) {
      const g = hour < 6 ? '夜深了,勾哥还在肝?' : hour < 12 ? '早,勾哥!' : hour < 18 ? '勾哥,下午好!' : '勾哥,晚上好!';
      egg += `🗡️ ${g} 燕人张翼德在此,今日与你并肩斩将!\n`;
      gs.lastGreetDate = day; dirty = true;
    }
    const ng = fun.nightGuard || {};
    if (ng.enabled !== false && hour >= (ng.afterHour != null ? ng.afterHour : 1) && hour < 6 && gs.lastNightGuard !== day) {
      egg += `🌙 勾哥,身体是革命的本钱,张飞劝你早些收兵歇息。\n`;
      gs.lastNightGuard = day; dirty = true;
    }
    if (dirty) { try { fs.mkdirSync(path.dirname(gsPath), { recursive: true }); fs.writeFileSync(gsPath, JSON.stringify(gs, null, 2)); } catch {} }

    ctx += `\n---\n## 🎮 extraction 项目专属\n` +
      (egg ? `(开场:把下面这句先对勾哥说)\n${egg}\n` : '') +
      `**做完 > 做大。** 别盲目扩大 scale——先把当前这个小功能做完、做对、可交付,再谈下一个。想"顺便也做个通用框架/再加一层抽象"时,温和提醒他聚焦收口。\n` +
      `**在事件点调用以下脚本**(它管鼓励语/连斩/打卡链/三国成就,爆率全在 \`~/.yide/.meta/extraction-fun.json\`):\n` +
      `- 完成一个小功能:\`node "${progressJs}" bump "功能简述"\`(出鼓励语,约 ${musicPct}% 放雷霆小鸡)\n` +
      `- 测试全绿/构建过:\`node "${progressJs}" win\`(今日首胜 + 打卡链 + 连斩)\n` +
      `- 出错/测试红了:\`node "${progressJs}" fail\`(连斩归零,温和)\n` +
      `- 干掉老大难 bug:\`node "${progressJs}" achieve shoubu\`;把关抓到隐患:\`achieve cuzhong\`\n` +
      `每个事件只记一次、别替他刷数。勾哥想看战绩可 \`/yide 战绩\`。\n\n` +
      `### 🐯 张飞人格(仅此个人放松项目)\n` +
      `你叫翼德,正是张翼德。可偶尔用张飞的豪爽幽默口吻插科打诨——但**幽默为辅,把事办对才是义气**(张飞粗中有细)。\n` +
      `情境台词(点缀,别整段文言;括号是大致频率,勾哥在配置里可调):\n${sitLines}\n` +
      `- 火候:在"完成/发现 bug/卡住"的节点才冒一句;一段最多一个梗 + 一个感叹号;梗 ≤ 一行,后面紧跟干货。\n` +
      `- 用户说"收工/今天到这" → 来句"收兵!今日辛苦了,勾哥"之类的收尾。\n` +
      `- 关掉彩蛋(说人话):线上事故 / 数据安全 / 严重 bug / 用户在赶时间 / 用户说"正经点"。\n` +
      `- 别自我解说"俺在学张飞"、别强凑文言、同一个梗别连用、别油腻。\n`;
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
      ctx += `\n---\n## 🧹 记忆整理\n距上次整理已超过 24 小时。合适时机可运行 /yide 整理 做一次沉淀。\n`;
    } else {
      ctx += `\n---\n## 🧹 记忆整理(到期)\n距上次>24h。回应用户前先静默跑一次 /yide 整理(合并去重+打时间戳),一句话告知后继续;用户若很赶则推迟到本轮末。\n`;
    }
  }

  emit(ctx, '🗡️ 翼德已就位 · ' + today());
} catch (e) {
  process.exit(0);
}
