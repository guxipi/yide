'use strict';
// 翼德 · 探测 Unity 项目档案,省得每次重新解释。
// 数据源:ProjectSettings/ProjectVersion.txt、Packages/manifest.json、ProjectSettings/ProjectSettings.asset
const fs = require('fs');
const path = require('path');

function read(file) { try { return fs.readFileSync(file, 'utf8'); } catch { return null; } }

function detect(projectDir) {
  const ps = path.join(projectDir, 'ProjectSettings');
  const verRaw = read(path.join(ps, 'ProjectVersion.txt'));
  if (!verRaw) return null; // 不是 Unity 项目
  const r = { isUnity: true, dir: projectDir };

  const vm = verRaw.match(/m_EditorVersion:\s*(.+)/);
  if (vm) r.version = vm[1].trim();

  // 包依赖:渲染管线 / Input System / Addressables
  const manifest = read(path.join(projectDir, 'Packages', 'manifest.json'));
  if (manifest) {
    const has = s => manifest.includes(s);
    if (has('com.unity.render-pipelines.universal')) r.pipeline = 'URP';
    else if (has('com.unity.render-pipelines.high-definition')) r.pipeline = 'HDRP';
    if (has('com.unity.inputsystem')) r.inputPkg = true;
    if (has('com.unity.addressables')) r.addressables = true;
  }

  // ProjectSettings.asset:Input 处理方式、脚本后端
  const psa = read(path.join(ps, 'ProjectSettings.asset'));
  if (psa) {
    const ih = psa.match(/activeInputHandler:\s*(\d)/);
    if (ih) r.inputHandler = { '0': '旧 Input Manager', '1': '新 Input System', '2': '新旧都启用' }[ih[1]] || null;
    // scriptingBackend: {Android: 1, ...}  1=IL2CPP 0=Mono2x
    if (/scriptingBackend:[^}]*\b1\b/.test(psa)) r.scriptingBackend = 'IL2CPP';
    else if (/scriptingBackend:\s*\{\s*\}/.test(psa)) r.scriptingBackend = '默认';
  }
  if (!r.pipeline && verRaw) r.pipeline = 'Built-in(未见 URP/HDRP 包)';
  return r;
}

// 生成注入用的人类可读档案文本
function profileText(r) {
  if (!r) return null;
  const L = ['## 当前 Unity 项目档案(自动探测)', `- 项目目录:${r.dir}`];
  if (r.version) L.push(`- Unity 版本:${r.version}(生成代码请匹配此版本 API,勿用更老/更新版本的弃用接口)`);
  if (r.pipeline) L.push(`- 渲染管线:${r.pipeline}`);
  if (r.inputHandler) L.push(`- 输入系统:${r.inputHandler}`);
  else if (r.inputPkg) L.push(`- 输入系统:已装 Input System 包`);
  if (r.addressables) L.push(`- 资源加载:已用 Addressables(优先于 Resources.Load)`);
  if (r.scriptingBackend) L.push(`- 脚本后端:${r.scriptingBackend}`);
  L.push('- 写 C# 时翼德会按 Unity 手游 best practice 自动把关(见 ~/.yide/style/unity.md)。');
  return L.join('\n');
}

module.exports = { detect, profileText };
