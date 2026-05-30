'use strict';
// 翼德 · Unity / C# 静态把关器(纯文本启发式,无需 Editor)。
// 覆盖四类(研究实证的高频痛点):
//   1) 性能热路径(Update/FixedUpdate/LateUpdate 内的分配/查找)
//   2) 过时 / 幻觉 API
//   3) 序列化 / 生命周期
//   4) 资源 / git 卫生
// 输出:[{line, rule, severity, msg}],按行排序。启发式,宁可少报也别误导。

const HOT_METHODS = /\b(void|IEnumerator)\s+(Update|FixedUpdate|LateUpdate)\s*\(/;

// 在热路径方法体内才报的项:token 正则 → 提示
const HOT_PATTERNS = [
  [/\bGetComponent(?:s|InChildren|InParent)?\s*</, 'perf', '热路径里调用 GetComponent:请在 Awake/Start 缓存引用'],
  [/\bGameObject\.Find\b|\bTransform\.Find\b|\bFindObjects?OfType\b|\bFindFirstObjectByType\b|\bFindAnyObjectByType\b/, 'perf', '热路径里做场景查找(Find*):请缓存引用'],
  [/\bCamera\.main\b/, 'perf', '热路径里用 Camera.main(内部按 tag 全场景搜):请缓存 Camera 引用'],
  [/\bInstantiate\s*\(|\bDestroy\s*\(/, 'perf', '热路径里 Instantiate/Destroy:高频生成请用对象池 UnityEngine.Pool.ObjectPool<T>'],
  [/\.(Where|Select|First|FirstOrDefault|Any|ToList|ToArray|OrderBy|Count)\s*\(/, 'perf', '热路径里用 LINQ(分配+装箱):改用 for 循环并缓存 .Count'],
  [/"\s*\+|\+\s*"/, 'perf', '热路径里字符串拼接(每帧分配):改用 StringBuilder 或缓存'],
];

// 全文件级:token 正则 → [rule, severity, 提示]
const FILE_PATTERNS = [
  // 2) 过时 / 幻觉 API
  [/\bnew\s+WWW\s*\(|\bWWW\s+\w+\s*=/, 'deprecated', '`WWW` 已弃用(2018.3+):改用 UnityWebRequest'],
  [/\.isNetworkError\b|\.isHttpError\b/, 'deprecated', '`isNetworkError/isHttpError` 已弃用:改判 `result == UnityWebRequest.Result.ConnectionError` 等'],
  [/\bFindObjectOfType\s*</, 'deprecated', '`FindObjectOfType` 在 Unity 2023+/6 弃用:改用 FindFirstObjectByType / FindAnyObjectByType'],
  // 4) 资源 / git 卫生
  [/\bResources\.Load\b/, 'asset', '`Resources.Load`:整个 /Resources 会被强制打包且同步加载,改用 Addressables'],
];

function lint(source) {
  const findings = [];
  const lines = source.split(/\r?\n/);

  // --- 热路径扫描:进入 Update/FixedUpdate/LateUpdate 后按花括号深度判断方法体 ---
  let inHot = false, depth = 0, started = false;
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.replace(/\/\/.*$/, ''); // 去行尾注释,降误报
    if (!inHot && HOT_METHODS.test(line)) { inHot = true; depth = 0; started = false; }
    if (inHot) {
      for (const ch of line) { if (ch === '{') { depth++; started = true; } else if (ch === '}') depth--; }
      if (started) {
        for (const [re, rule, msg] of HOT_PATTERNS) {
          if (re.test(line)) findings.push({ line: i + 1, rule, severity: 7, msg });
        }
      }
      if (started && depth <= 0) inHot = false; // 方法体结束
    }
  }

  // --- 全文件扫描 ---
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].replace(/\/\/.*$/, '');
    for (const [re, rule, msg] of FILE_PATTERNS) {
      if (re.test(line)) findings.push({ line: i + 1, rule, severity: 6, msg });
    }
    // 3) 序列化 / 生命周期
    if (/\basync\s+void\s+\w+\s*\(/.test(line) && !/On\w+|Awaitable/.test(line)) {
      findings.push({ line: i + 1, rule: 'lifecycle', severity: 7, msg: 'MonoBehaviour 里 `async void`:用 async Task 并绑定 OnDestroy 的 CancellationToken(或用 Awaitable/UniTask),否则对象销毁后任务仍在跑' });
    }
    // public 字段(非方法、非属性):疑似只为露在 Inspector
    if (/^\s*public\s+[\w<>\[\],.\s]+?\s+\w+\s*;\s*$/.test(lines[i]) && !/\bconst\b|\bstatic\b\s+readonly|=>/.test(lines[i])) {
      findings.push({ line: i + 1, rule: 'serialize', severity: 5, msg: 'public 字段:若只为在 Inspector 显示,改用 `[SerializeField] private`(保住封装)' });
    }
  }

  // 同一行去重 + 按行排序
  const seen = new Set();
  return findings
    .filter(f => { const k = f.line + '|' + f.msg; if (seen.has(k)) return false; seen.add(k); return true; })
    .sort((a, b) => a.line - b.line);
}

module.exports = { lint };
