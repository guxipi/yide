'use strict';
// 翼德 · Unity / C# 静态把关器(纯文本启发式,无需 Editor)。
// 覆盖:1) 热路径分配/查找 2) 过时/幻觉 API(按 Unity 版本 gating)3) 序列化/生命周期 4) 资源/git 卫生
// 输出:[{line, rule, severity, msg}]。启发式 —— 已做"去注释+去字符串字面量"降误报、"按版本"避免给过时建议。

const HOT_METHODS = /\b(void|IEnumerator)\s+(Update|FixedUpdate|LateUpdate)\s*\(/;

const HOT_PATTERNS = [
  [/\bGetComponent(?:s|InChildren|InParent)?\s*</, 'perf', '热路径里调用 GetComponent:请在 Awake/Start 缓存引用'],
  [/\bGameObject\.Find\b|\bTransform\.Find\b|\bFindObjects?OfType\b|\bFindFirstObjectByType\b|\bFindAnyObjectByType\b/, 'perf', '热路径里做场景查找(Find*):请缓存引用'],
  [/\bCamera\.main\b/, 'perf', '热路径里用 Camera.main(内部按 tag 全场景搜):请缓存 Camera 引用'],
  [/\bInstantiate\s*\(|\bDestroy\s*\(/, 'perf', '热路径里 Instantiate/Destroy:高频生成请用对象池 UnityEngine.Pool.ObjectPool<T>'],
  [/\.(Where|Select|First|FirstOrDefault|Any|ToList|ToArray|OrderBy|Count)\s*\(/, 'perf', '热路径里用 LINQ(分配+装箱):改用 for 循环并缓存 .Count'],
  [/"\s*\+|\+\s*"/, 'perf', '热路径里字符串拼接(每帧分配):改用 StringBuilder 或缓存'],
];

// 过时 API:minMajor = 该 API 从哪个大版本起才算"弃用/该改"(版本未知或低于它则不报,避免给过时建议)
const DEPRECATED = [
  { re: /\bnew\s+WWW\s*\(|\bWWW\s+\w+\s*=/, minMajor: 2018, msg: '`WWW` 已弃用:改用 UnityWebRequest' },
  { re: /\.isNetworkError\b|\.isHttpError\b/, minMajor: 2020, msg: '`isNetworkError/isHttpError` 已弃用:改判 `result == UnityWebRequest.Result.ConnectionError` 等' },
  { re: /\bFindObjectOfType\s*</, minMajor: 2023, msg: '`FindObjectOfType` 在 Unity 2023+/6 才弃用:改用 FindFirstObjectByType / FindAnyObjectByType' },
];
const ASSET = [
  [/\bResources\.Load\b/, '`Resources.Load`:整个 /Resources 会被强制打包且同步加载,改用 Addressables'],
];

// 去掉行注释 + 字符串字面量内容(降低"注释/字符串里出现关键词"的误报)
function clean(raw) {
  return raw
    .replace(/\/\/.*$/, '')
    .replace(/"(?:\\.|[^"\\])*"/g, '""')
    .replace(/'(?:\\.|[^'\\])*'/g, "''");
}
function majorOf(v) { const m = String(v || '').match(/(\d{4,})/); return m ? parseInt(m[1], 10) : null; }

function lint(source, opts = {}) {
  const findings = [];
  const major = majorOf(opts.unityVersion); // null = 版本未知
  const lines = source.split(/\r?\n/);

  // 热路径扫描
  let inHot = false, depth = 0, started = false;
  for (let i = 0; i < lines.length; i++) {
    const line = clean(lines[i]);
    if (!inHot && HOT_METHODS.test(line)) { inHot = true; depth = 0; started = false; }
    if (inHot) {
      for (const ch of line) { if (ch === '{') { depth++; started = true; } else if (ch === '}') depth--; }
      if (started) for (const [re, rule, msg] of HOT_PATTERNS) if (re.test(line)) findings.push({ line: i + 1, rule, severity: 7, msg });
      if (started && depth <= 0) inHot = false;
    }
  }

  // 全文件扫描
  for (let i = 0; i < lines.length; i++) {
    const line = clean(lines[i]);
    // 过时 API(按版本 gating:版本已知且 < minMajor 则不报)
    for (const d of DEPRECATED) {
      if (!d.re.test(line)) continue;
      if (major == null || major < d.minMajor) continue; // 版本未知 或 该版本还没弃用 → 不给过时建议
      findings.push({ line: i + 1, rule: 'deprecated', severity: 6, msg: d.msg });
    }
    for (const [re, msg] of ASSET) if (re.test(line)) findings.push({ line: i + 1, rule: 'asset', severity: 6, msg });
    if (/\basync\s+void\s+\w+\s*\(/.test(line) && !/On\w+|Awaitable/.test(line)) {
      findings.push({ line: i + 1, rule: 'lifecycle', severity: 7, msg: 'MonoBehaviour 里 `async void`:用 async Task 并绑 OnDestroy 的 CancellationToken(或 Awaitable/UniTask),否则对象销毁后任务仍在跑' });
    }
    if (/^\s*public\s+[\w<>\[\],.\s]+?\s+\w+\s*;\s*$/.test(clean(lines[i])) && !/\bconst\b|\bstatic\b\s+readonly|=>/.test(lines[i])) {
      findings.push({ line: i + 1, rule: 'serialize', severity: 5, msg: 'public 字段:若只为在 Inspector 显示,改用 `[SerializeField] private`(保住封装)' });
    }
  }

  const seen = new Set();
  return findings
    .filter(f => { const k = f.line + '|' + f.msg; if (seen.has(k)) return false; seen.add(k); return true; })
    .sort((a, b) => a.line - b.line);
}

module.exports = { lint };
