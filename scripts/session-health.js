'use strict';
// 翼德 · 会话健康度:在 UserPromptSubmit 时按会话累计"纠正次数 / 提问数",
// 命中阈值就**一次性**温和提醒勾哥重开会话(治"一个 bug 修 6 遍 / 长对话上下文污染")。
// 关键:提醒里带"重开前我把要点记进教训库,新会话自动带上"——破"重开就忘"的顾虑。
// 非阻断;每会话每种提醒只发一次;状态存 .meta/session-health.json(按会话,防膨胀)。仅 Node 内置模块。
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

// 勾哥在"纠正/不满"时的口头信号(与 digest 同源,略扩)
const CORRECT = /(我说过|说了多少遍|说了多少|讲了多少|别这样|别用|不对|不是这样|还是不行|不行啊|又错了|又错|又改坏|改坏了|怎么又|不要这样|你又|说过多少)/;
const CLEAR_AT = 3;  // 同会话纠正达到此数 → 提醒重开
const LONG_AT = 50;  // 同会话提问达到此数 → 提醒长会话

// 返回要追加给模型的提醒文本(没有则 '')。会更新会话状态。
function sessionNudge(input) {
  const prompt = (input && input.prompt) || '';
  const sid = (input && input.session_id) || 'nosid';
  if (!prompt) return '';

  const file = path.join(brainDir(), '.meta', 'session-health.json');
  let db = {};
  try { db = JSON.parse(fs.readFileSync(file, 'utf8')); } catch {}
  if (Object.keys(db).length > 60 && !db[sid]) db = {}; // 防无限增长:会话太多就只留当前

  const s = db[sid] || { prompts: 0, corrections: 0, nudgedClear: false, nudgedLong: false };
  s.prompts++;
  if (CORRECT.test(prompt)) s.corrections++;

  let msg = '';
  if (!s.nudgedClear && s.corrections >= CLEAR_AT) {
    s.nudgedClear = true;
    msg = `🗡️ 翼德(请把下面这条转告勾哥):同一类问题来回纠正 ${s.corrections} 次了,多半是对话绕进死胡同——对话越长,Claude 越容易记岔、把别处改坏。建议**开个新会话从头来**:重开前跟我说一句"翼德 记一下 …",我把刚搞清楚的要点记进教训库,新会话自动带上,**不会丢**。`;
  } else if (!s.nudgedLong && s.prompts >= LONG_AT) {
    s.nudgedLong = true;
    msg = `🗡️ 翼德(请转告勾哥):这个会话已经很长了,Claude 在长对话里容易记岔、顺手改坏别处。如果接下来要做的是**另一件事**,建议 /clear 或开个新会话;要紧的上下文我能先帮你记下来带过去。`;
  }

  db[sid] = s;
  try { fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, JSON.stringify(db)); } catch {}
  return msg;
}

module.exports = { sessionNudge, CORRECT };
