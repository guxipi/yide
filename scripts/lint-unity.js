'use strict';
// 翼德 · Unity / C# 静态把关器(纯文本启发式,无需 Editor)。
// 覆盖:热路径分配/查找、过时/幻觉 API(按版本 gating)、序列化/生命周期、资源/git 卫生。
// 专家友好:每条规则标 obvious(资深是否本就会);按 expertLevel 过滤;支持行内 `// yide-ok` 豁免。
// 已做去注释+去字符串字面量降误报。输出 [{line, rule, severity, msg}]。

const HOT_METHODS = /\b(void|IEnumerator)\s+(Update|FixedUpdate|LateUpdate)\s*\(/;

// [re, rule, msg, obvious]  obvious=true:资深本就会(专家档默认不报)
const HOT_PATTERNS = [
  [/\bGetComponent(?:s|InChildren|InParent)?\s*</, 'perf', '热路径里调用 GetComponent:请在 Awake/Start 缓存引用', true],
  [/\bGameObject\.Find\b|\bTransform\.Find\b|\bFindObjects?OfType\b|\bFindFirstObjectByType\b|\bFindAnyObjectByType\b/, 'perf', '热路径里做场景查找(Find*):请缓存引用', true],
  [/\bCamera\.main\b/, 'perf', '热路径里用 Camera.main(内部按 tag 全场景搜):请缓存', true],
  [/\bInstantiate\s*\(|\bDestroy\s*\(/, 'perf', '热路径里 Instantiate/Destroy:高频请用对象池', true],
  [/\.(Where|Select|First|FirstOrDefault|Any|ToList|ToArray|OrderBy|Count)\s*\(/, 'perf', '热路径里 LINQ(分配+装箱):改 for 循环', true],
  [/"\s*\+|\+\s*"/, 'perf', '热路径里字符串拼接(每帧分配):用 StringBuilder', true],
];
// 过时 API:minMajor=从哪个大版本起才弃用;obvious=false(具体版本弃用,资深未必记得)
const DEPRECATED = [
  { re: /\bnew\s+WWW\s*\(|\bWWW\s+\w+\s*=/, minMajor: 2018, msg: '`WWW` 已弃用:改用 UnityWebRequest', obvious: false },
  { re: /\.isNetworkError\b|\.isHttpError\b/, minMajor: 2020, msg: '`isNetworkError/isHttpError` 已弃用:改判 `result == ...ConnectionError`', obvious: false },
  { re: /\bFindObjectOfType\s*</, minMajor: 2023, msg: '`FindObjectOfType` 在 2023+/U6 弃用:改 FindFirstObjectByType', obvious: false },
];
const ASSET = [[/\bResources\.Load\b/, '`Resources.Load`:强制全量打包+同步加载,改 Addressables', true]];

function clean(raw) {
  return raw.replace(/\/\/.*$/, '').replace(/"(?:\\.|[^"\\])*"/g, '""').replace(/'(?:\\.|[^'\\])*'/g, "''");
}
function majorOf(v) { const m = String(v || '').match(/(\d{4,})/); return m ? parseInt(m[1], 10) : null; }
function hasInlineOk(raw) { return /\byide-ok\b|\byide-disable\b/.test(raw); } // 行内豁免:这是故意的

// 按档过滤:expert=只非显而易见;balanced=非显而易见 + 显而易见但高severity;novice=全要
function passLevel(level, f) {
  if (level === 'novice') return true;
  if (level === 'expert') return f.obvious === false;
  return f.obvious === false || f.severity >= 7; // balanced
}

function lint(source, opts = {}) {
  const level = opts.expertLevel || 'balanced';
  const major = majorOf(opts.unityVersion);
  const lines = source.split(/\r?\n/);
  const raw = lines;
  const out = [];
  const push = (i, rule, severity, msg, obvious) => {
    if (hasInlineOk(raw[i])) return;               // 行内 // yide-ok 豁免
    const f = { line: i + 1, rule, severity, msg, obvious };
    if (passLevel(level, f)) out.push(f);
  };

  // 热路径
  let inHot = false, depth = 0, started = false;
  for (let i = 0; i < lines.length; i++) {
    const line = clean(lines[i]);
    if (!inHot && HOT_METHODS.test(line)) { inHot = true; depth = 0; started = false; }
    if (inHot) {
      for (const ch of line) { if (ch === '{') { depth++; started = true; } else if (ch === '}') depth--; }
      if (started) for (const [re, rule, msg, ob] of HOT_PATTERNS) if (re.test(line)) push(i, rule, 7, msg, ob);
      if (started && depth <= 0) inHot = false;
    }
  }
  // 全文件
  for (let i = 0; i < lines.length; i++) {
    const line = clean(lines[i]);
    for (const d of DEPRECATED) { if (!d.re.test(line)) continue; if (major == null || major < d.minMajor) continue; push(i, 'deprecated', 6, d.msg, d.obvious); }
    for (const [re, msg, ob] of ASSET) if (re.test(line)) push(i, 'asset', 6, msg, ob);
    if (/\basync\s+void\s+\w+\s*\(/.test(line) && !/On\w+|Awaitable/.test(line)) push(i, 'lifecycle', 7, 'MonoBehaviour 里 `async void`:绑 OnDestroy 的 CancellationToken(或 Awaitable/UniTask),否则对象销毁后任务仍跑', false);
    if (/^\s*public\s+[\w<>\[\],.\s]+?\s+\w+\s*;\s*$/.test(line.trimEnd()) && !/\bconst\b|\bstatic\b\s+readonly|=>/.test(line)) push(i, 'serialize', 5, 'public 字段:若只为 Inspector 显示,改 `[SerializeField] private`', true);
  }

  const seen = new Set();
  return out.filter(f => { const k = f.line + '|' + f.msg; if (seen.has(k)) return false; seen.add(k); return true; }).sort((a, b) => a.line - b.line);
}

module.exports = { lint };
