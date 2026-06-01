'use strict';
// 翼德 · 大脑状态前台:统一 .meta/ 下状态文件的读写,单一真相源(以前 14 个脚本各自拼 .meta 路径 + 各写 try/catch)。
// 只碰 .meta(派生状态/配置);用户内容(lessons/notes/core...)不走这里。仅 Node 内置模块。
const fs = require('fs');
const path = require('path');
const { brainDir } = require(path.join(__dirname, 'lib.js'));

function metaDir() { return path.join(brainDir(), '.meta'); }
function metaPath(name) { return path.join(metaDir(), name); }
function exists(name) { try { return fs.existsSync(metaPath(name)); } catch { return false; } }

// JSON:读失败/不存在 → 返回 fallback(默认 null)。写:自动建目录;pretty=true 时缩进 2(给人看的状态)。
function readJson(name, fallback) {
  try { const o = JSON.parse(fs.readFileSync(metaPath(name), 'utf8')); return o == null ? def(fallback) : o; }
  catch { return def(fallback); }
}
function writeJson(name, obj, pretty) {
  try { fs.mkdirSync(metaDir(), { recursive: true }); fs.writeFileSync(metaPath(name), JSON.stringify(obj, null, pretty ? 2 : 0)); return true; }
  catch { return false; }
}
// 纯文本(时间戳之类):读失败 → fallback;写自动建目录。
function readText(name, fallback) {
  try { return fs.readFileSync(metaPath(name), 'utf8'); } catch { return def(fallback); }
}
function writeText(name, text) {
  try { fs.mkdirSync(metaDir(), { recursive: true }); fs.writeFileSync(metaPath(name), String(text)); return true; }
  catch { return false; }
}
function def(v) { return v === undefined ? null : v; }

module.exports = { metaDir, metaPath, exists, readJson, writeJson, readText, writeText };
