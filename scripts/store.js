'use strict';
// 翼德 · 大脑状态前台:统一 .meta/ 下状态文件的读写,单一真相源(以前 14 个脚本各自拼 .meta 路径 + 各写 try/catch)。
// 只碰 .meta(派生状态/配置);用户内容(lessons/notes/core...)不走这里。仅 Node 内置模块。
//
// 两类落点:
//   metaDir()  = <brain>/.meta   —— 随大脑走(可能在同步盘)。放耐久/需跨机可见的状态(game-state 战绩)。
//   localDir() = ~/.yide-local   —— 本机私有、不同步。放会话级易变状态(health/greet/lint-seen/prompt-log),
//                                    否则两机同天活跃 → Google Drive lost update / conflicted copy。
// 迁移:readLocal* 本机无值时,一次性回退读旧的共享 .meta 副本(平滑过渡);共享侧旧文件由 migrate 清理清单删除。
const fs = require('fs');
const os = require('os');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function metaDir() { return path.join(brainDir(), '.meta'); }
function metaPath(name) { return path.join(metaDir(), name); }
function exists(name) { try { return fs.existsSync(metaPath(name)); } catch { return false; } }

// 本机私有状态目录(不同步)。YIDE_LOCAL 可覆盖(测试隔离用)。
function localDir() { return process.env.YIDE_LOCAL || path.join(os.homedir(), '.yide-local'); }
function localPath(name) { return path.join(localDir(), name); }

// 原子写:先写 .tmp 再 rename,避免读到写一半的文件 / 两进程互相截断。
function atomicWrite(file, data) {
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, data);
  fs.renameSync(tmp, file);
}

// JSON:读失败/不存在 → 返回 fallback(默认 null)。写:自动建目录;pretty=true 时缩进 2(给人看的状态)。
function readJson(name, fallback) {
  try { const o = JSON.parse(fs.readFileSync(metaPath(name), 'utf8')); return o == null ? def(fallback) : o; }
  catch { return def(fallback); }
}
function writeJson(name, obj, pretty) {
  try { fs.mkdirSync(metaDir(), { recursive: true }); atomicWrite(metaPath(name), JSON.stringify(obj, null, pretty ? 2 : 0)); return true; }
  catch { return false; }
}
// 纯文本(时间戳之类):读失败 → fallback;写自动建目录。
function readText(name, fallback) {
  try { return fs.readFileSync(metaPath(name), 'utf8'); } catch { return def(fallback); }
}
function writeText(name, text) {
  try { fs.mkdirSync(metaDir(), { recursive: true }); atomicWrite(metaPath(name), String(text)); return true; }
  catch { return false; }
}

// ── 本机私有(local)读写:与上面同形，但落 localDir();读时若本机无而共享 .meta 有 → 一次性回退取旧值。──
function readLocalJson(name, fallback) {
  try { const o = JSON.parse(fs.readFileSync(localPath(name), 'utf8')); return o == null ? def(fallback) : o; } catch {}
  try { const o = JSON.parse(fs.readFileSync(metaPath(name), 'utf8')); return o == null ? def(fallback) : o; } catch { return def(fallback); }
}
function writeLocalJson(name, obj, pretty) {
  try { fs.mkdirSync(localDir(), { recursive: true }); atomicWrite(localPath(name), JSON.stringify(obj, null, pretty ? 2 : 0)); return true; }
  catch { return false; }
}
function readLocalText(name, fallback) {
  try { return fs.readFileSync(localPath(name), 'utf8'); } catch {}
  try { return fs.readFileSync(metaPath(name), 'utf8'); } catch { return def(fallback); }
}
function writeLocalText(name, text) {
  try { fs.mkdirSync(localDir(), { recursive: true }); atomicWrite(localPath(name), String(text)); return true; }
  catch { return false; }
}
function def(v) { return v === undefined ? null : v; }

module.exports = {
  metaDir, metaPath, exists, readJson, writeJson, readText, writeText,
  localDir, localPath, readLocalJson, writeLocalJson, readLocalText, writeLocalText,
};
