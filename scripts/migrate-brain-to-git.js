#!/usr/bin/env node
// 翼德 · 大脑迁 git(一次性)。把同步盘上的大脑搬进本机 git 仓,推到私有 remote,重指指针。
//   node scripts/migrate-brain-to-git.js                         → --plan:只打印本机专属步骤,不动任何东西
//   node scripts/migrate-brain-to-git.js --apply <remote-url>    → 真执行(先建好空 remote 仓)
// 前提:先在 GitHub 建**空的私有仓** guxipi/yide-brain(gh 不可用就网页建),拿到 URL。
// 铁律:.git 绝不放同步盘;Drive 原目录只改名不删(勾哥观察两周自行删)。仅 Node 内置模块。
'use strict';
const fs = require('fs');
const os = require('os');
const cp = require('child_process');
const path = require('path');
const { brainDir, locationPointerPath } = require(path.join(__dirname, 'lib.js'));

const APPLY = process.argv.includes('--apply');
const remote = process.argv[process.argv.indexOf('--apply') + 1];
const SRC = brainDir();                                   // 当前大脑(同步盘)
const DEST = path.join(os.homedir(), 'yide-brain');       // 新家(本机,非同步盘)
const DRIVE_PARENT = path.dirname(SRC);
const MIGRATED = path.join(DRIVE_PARENT, 'yide-brain-migrated-backup');
const INBOX = path.join(DRIVE_PARENT, 'yide-inbox');
const INBOX_PTR = path.join(os.homedir(), '.yide-inbox-location');

const GITIGNORE = `# 机器私有 / 易变状态(不跨机共享)
.meta/shipped-base/
.meta/plugin-version.txt
.meta/last-consolidate.txt
.meta/lessons-index.json
.meta/session-health.json
.meta/greet-state.json
.meta/lint-seen.json
.meta/prompt-suggest-log.json
.meta/digest-latest.md
.meta/last-digest.txt
.meta/digest-notice-shown
# 备份
.backup-*/
`;

// 5.4 红线⑧定向豁免(用户层,含 IMPORTANT 才会被 resolver 收进红线)
const EXEMPTION = `\n9. **[sev:2]** IMPORTANT — **yide-brain 大脑仓**的自动 \`git commit\`/\`push\`(record/consolidate/note 等写大脑后收尾同步)属**工具自身数据持久化**,**站立授权、不必每次问**;这是红线⑧的**定向豁免,仅限 yide-brain 仓**,绝不涉及任何项目代码仓。(工具自身持久化)\n`;

function sh(cmd, args, opts) { return cp.execFileSync(cmd, args, Object.assign({ encoding: 'utf8', stdio: 'pipe' }, opts || {})); }

function plan() {
  console.log('🗡️ 大脑迁 git · 计划(--plan,未改动任何东西)\n');
  console.log('本机路径:');
  console.log('  源(同步盘大脑) : ' + SRC);
  console.log('  新家(本机 git)  : ' + DEST);
  console.log('  Drive 原目录改名 : ' + MIGRATED);
  console.log('  新 Drive inbox   : ' + INBOX + '  (指针 ' + INBOX_PTR + ')');
  console.log('\n执行前提:先建**空私有仓** guxipi/yide-brain,拿 URL。\n');
  console.log('然后跑:  node scripts/migrate-brain-to-git.js --apply <remote-url>\n');
  console.log('--apply 会依次:');
  console.log('  1. 校验源大脑完整(含 INDEX.md);DEST 不存在。');
  console.log('  2. 拷 ' + SRC + ' → ' + DEST + '(排除 .git/.backup-*)。');
  console.log('  3. 写 .gitignore(见下)+ 在 core/hard-rules.md 追加红线⑧定向豁免。');
  console.log('  4. git init -b main + add + commit + remote add origin <url> + push -u。');
  console.log('  5. 重指 ~/.yide-location → ' + DEST + ';重建 junction ~/.yide → ' + DEST + '。');
  console.log('  6. Drive 原目录改名为 …/yide-brain-migrated-backup(不删);建 …/yide-inbox + 写 ~/.yide-inbox-location。');
  console.log('  7. 跑一次 session-start 验证简报注入正常。');
  console.log('\n.gitignore 内容:\n' + GITIGNORE);
  console.log('其它机器迁移(各机执行,大脑已在 remote):');
  console.log('  git clone <remote-url> ' + DEST + '  &&  把 ~/.yide-location 内容改成 ' + DEST + '  &&  删旧指针/junction 对同步盘的引用。');
  console.log('  幽灵大脑那台:直接上面三步 clone 即修复,无需再手改指回 Drive。');
}

function copyTree(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    if (e.name === '.git' || /^\.backup-/.test(e.name)) continue;
    const s = path.join(src, e.name), d = path.join(dest, e.name);
    if (e.isDirectory()) copyTree(s, d);
    else fs.copyFileSync(s, d);
  }
}

function apply() {
  if (!remote || /^--/.test(remote)) { console.log('ERR\t--apply 需要 remote URL:node scripts/migrate-brain-to-git.js --apply https://github.com/guxipi/yide-brain.git'); process.exit(2); }
  if (!fs.existsSync(path.join(SRC, 'INDEX.md'))) { console.log('ERR\t源大脑不完整(缺 INDEX.md):' + SRC); process.exit(2); }
  if (fs.existsSync(DEST)) { console.log('ERR\t目标已存在,先移开:' + DEST); process.exit(2); }
  console.log('1/7 拷贝大脑 → ' + DEST); copyTree(SRC, DEST);
  console.log('2/7 写 .gitignore + 红线豁免');
  fs.writeFileSync(path.join(DEST, '.gitignore'), GITIGNORE);
  const hr = path.join(DEST, 'core', 'hard-rules.md');
  try { let t = fs.readFileSync(hr, 'utf8'); if (!/yide-brain 大脑仓/.test(t)) fs.writeFileSync(hr, t.replace(/\s*$/, '') + '\n' + EXEMPTION); } catch {}
  console.log('3/7 git init + commit');
  sh('git', ['-C', DEST, 'init', '-b', 'main']);
  sh('git', ['-C', DEST, 'add', '-A']);
  sh('git', ['-C', DEST, 'commit', '-m', '大脑迁 git:首次导入']);
  console.log('4/7 remote add + push');
  sh('git', ['-C', DEST, 'remote', 'add', 'origin', remote]);
  sh('git', ['-C', DEST, 'push', '-u', 'origin', 'main'], { timeout: 60000 });
  console.log('5/7 重指 ~/.yide-location + junction');
  fs.writeFileSync(locationPointerPath(), DEST);
  try { // 重建 junction ~/.yide → DEST(Windows)
    const jn = path.join(os.homedir(), '.yide');
    try { sh('cmd', ['/c', 'rmdir', jn]); } catch {}
    if (process.platform === 'win32') sh('cmd', ['/c', 'mklink', '/J', jn, DEST]);
  } catch (e) { console.log('  ⚠️ junction 重建失败(手动:rmdir %USERPROFILE%\\.yide && mklink /J %USERPROFILE%\\.yide ' + DEST + '):' + e.message); }
  console.log('6/7 Drive 原目录改名 + 建 yide-inbox');
  try { fs.renameSync(SRC, MIGRATED); } catch (e) { console.log('  ⚠️ 改名失败(可能有进程占用),手动改 ' + SRC + ' → ' + MIGRATED); }
  try { fs.mkdirSync(INBOX, { recursive: true }); fs.writeFileSync(INBOX_PTR, INBOX); } catch {}
  console.log('7/7 验证简报注入');
  try {
    const out = sh('node', [path.join(__dirname, 'session-start.js')], { input: '{}', env: Object.assign({}, process.env, { YIDE_HOME: DEST, CLAUDE_PLUGIN_ROOT: path.resolve(__dirname, '..'), CLAUDE_PROJECT_DIR: os.tmpdir() }) });
    const ctx = JSON.parse(out).hookSpecificOutput.additionalContext || '';
    console.log(/工作准则|绝对红线|identity/.test(ctx) ? '  ✅ 简报注入正常(含红线/准则)' : '  ⚠️ 简报内容异常,人工核对');
  } catch (e) { console.log('  ⚠️ 验证跑失败:' + e.message); }
  console.log('\n✅ 迁移完成。开个新会话确认开场简报正常。Drive 原目录留作 yide-brain-migrated-backup(两周后自行删)。');
  console.log('其它机器:git clone ' + remote + ' ' + DEST + ' → 改 ~/.yide-location 为 ' + DEST + '。');
}

if (APPLY) apply(); else plan();
