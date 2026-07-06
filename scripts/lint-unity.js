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

// honesty(诚实性):AI 写占位/假实现常配欺骗性注释、或 catch 静默吞错。任何 expertLevel 都必须点破(always:true,不受档过滤)。
const HONESTY_FAKE_RE = /\b(simulat(e|ed|es|ing|ion)|pretend(s|ing)?|fake[ds]?|placeholder|stub(bed|s)?|dummy|for now|in a real (implementation|app|game|build|world)|would (normally|actually|really)|not (actually|really) (call|connect|send|save|write|hit))\b/i;
const HONESTY_FAKE_MSG = "注释疑似声明假实现/占位(simulate/fake/for now)。若确是占位,必须在最终交付的'偏离与欠账'里明列;若代码是真实现,删掉误导性注释。";
const HONESTY_CATCH_MSG = 'catch 静默吞错/返回默认值=把失败伪装成成功;至少记一条日志或 rethrow。';

function clean(raw) {
  return raw.replace(/\/\/.*$/, '').replace(/"(?:\\.|[^"\\])*"/g, '""').replace(/'(?:\\.|[^'\\])*'/g, "''");
}
function majorOf(v) { const m = String(v || '').match(/(\d{4,})/); return m ? parseInt(m[1], 10) : null; }
function hasInlineOk(raw) { return /\byide-ok\b|\byide-disable\b/.test(raw); } // 行内豁免:这是故意的

// 按档过滤:expert=只非显而易见;balanced=非显而易见 + 显而易见但高severity;novice=全要
function passLevel(level, f) {
  if (f.always) return true;             // honesty 等欺骗指纹:任何档都必须报,豁免过滤
  if (level === 'novice') return true;
  if (level === 'expert') return f.obvious === false;
  return f.obvious === false || f.severity >= 7; // balanced
}

// 结构性抹白:把字符串字面量与注释替换成等长空格(保长度/换行),用于定位 catch 与括号配对而不被串/注释里的 {}// 干扰。
function blankStructural(src) {
  let out = '', i = 0, n = src.length, mode = 0; // 0 code · 1 行注释 · 2 块注释 · 3 " · 4 '
  while (i < n) {
    const c = src[i], c2 = src[i + 1];
    if (mode === 0) {
      if (c === '/' && c2 === '/') { out += '  '; i += 2; mode = 1; }
      else if (c === '/' && c2 === '*') { out += '  '; i += 2; mode = 2; }
      else if (c === '"') { out += '"'; i++; mode = 3; }
      else if (c === "'") { out += "'"; i++; mode = 4; }
      else { out += c; i++; }
    } else if (mode === 1) {
      if (c === '\n') { out += '\n'; i++; mode = 0; } else { out += ' '; i++; }
    } else if (mode === 2) {
      if (c === '*' && c2 === '/') { out += '  '; i += 2; mode = 0; } else { out += (c === '\n' ? '\n' : ' '); i++; }
    } else if (mode === 3) {
      if (c === '\\' && i + 1 < n) { out += '  '; i += 2; } else if (c === '"') { out += '"'; i++; mode = 0; } else { out += ' '; i++; }
    } else {
      if (c === '\\' && i + 1 < n) { out += '  '; i += 2; } else if (c === "'") { out += "'"; i++; mode = 0; } else { out += ' '; i++; }
    }
  }
  return out;
}

// 每行的注释文本(块注释跨行携带状态;串内 // 不算)。用于 fake-comment 只看注释内容,不误伤同名代码标识符。
function commentsByLine(src) {
  const lines = src.split(/\r?\n/);
  const res = new Array(lines.length).fill('');
  let inBlock = false;
  for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    let i = 0, buf = '', inStr = false, strCh = '';
    while (i < line.length) {
      const c = line[i], c2 = line[i + 1];
      if (inBlock) {
        if (c === '*' && c2 === '/') { inBlock = false; i += 2; } else { buf += c; i++; }
      } else if (inStr) {
        if (c === '\\') i += 2; else if (c === strCh) { inStr = false; i++; } else i++;
      } else {
        if (c === '/' && c2 === '/') { buf += line.slice(i + 2); i = line.length; }
        else if (c === '/' && c2 === '*') { inBlock = true; i += 2; }
        else if (c === '"' || c === "'") { inStr = true; strCh = c; i++; }
        else i++;
      }
    }
    res[li] = buf;
  }
  return res;
}

// 扫 catch 静默吞错:块体为空/只注释/只 return 默认值,且体内无任何 log 调用即命中(1-based line)。
// 简单括号配对;嵌套 catch 内再开 try 等极端情况可能扫不准,宁可漏报不误报。
function scanSwallowedCatch(src) {
  const struct = blankStructural(src);
  const hits = [];
  const catchRe = /\bcatch\b/g;
  let m;
  while ((m = catchRe.exec(struct))) {
    let j = m.index + 5, ok = true;
    while (j < struct.length && struct[j] !== '{') {
      const ch = struct[j];
      if (ch === '(') { let d = 0; while (j < struct.length) { if (struct[j] === '(') d++; else if (struct[j] === ')') { d--; if (d === 0) { j++; break; } } j++; } continue; }
      if (!/\s/.test(ch)) { ok = false; break; }
      j++;
    }
    if (!ok || j >= struct.length || struct[j] !== '{') continue;
    let depth = 0, k = j;
    for (; k < struct.length; k++) { if (struct[k] === '{') depth++; else if (struct[k] === '}') { depth--; if (depth === 0) break; } }
    if (k >= struct.length) continue;
    const body = struct.slice(j + 1, k).replace(/\s+/g, ' ').trim(); // 注释/串已抹白
    if (/\blog/i.test(body)) continue; // 体内有日志调用(Log/Logger/log)即算有交代
    const swallow = body === '' || /^return\s*(;|(null|false|true|0|default)\b[^;]*;)$/.test(body);
    if (swallow) hits.push({ line: src.slice(0, m.index).split(/\r?\n/).length });
  }
  return hits;
}

function lint(source, opts = {}) {
  const level = opts.expertLevel || 'balanced';
  const major = majorOf(opts.unityVersion);
  const lines = source.split(/\r?\n/);
  const raw = lines;
  const out = [];
  const push = (i, rule, severity, msg, obvious, always) => {
    if (hasInlineOk(raw[i])) return;               // 行内 // yide-ok 豁免
    const f = { line: i + 1, rule, severity, msg, obvious, always };
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

  // honesty(诚实性):欺骗指纹任何档都报(always),但 Mock/测试路径的 fake/stub 是正当的 → 跳过
  const fp = String(opts.filePath || '').replace(/\\/g, '/');
  if (!/(test|mock|coplaytemp)/i.test(fp)) {
    const comm = commentsByLine(source);
    for (let i = 0; i < comm.length; i++) if (HONESTY_FAKE_RE.test(comm[i])) push(i, 'honesty-fake-comment', 7, HONESTY_FAKE_MSG, false, true);
    for (const c of scanSwallowedCatch(source)) push(c.line - 1, 'honesty-swallowed-catch', 7, HONESTY_CATCH_MSG, false, true);
  }

  const seen = new Set();
  return out.filter(f => { const k = f.line + '|' + f.msg; if (seen.has(k)) return false; seen.add(k); return true; }).sort((a, b) => a.line - b.line);
}

module.exports = { lint };
