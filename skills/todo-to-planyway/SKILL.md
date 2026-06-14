---
name: todo-to-planyway
description: Use to bulk-import a todo list into Jira project KAN so the issues show up in Planyway for scheduling — no manual one-by-one pasting. ALSO trigger on the user's Chinese requests, e.g. "翼德 发 Planyway" / "发到 Planyway" / "导入 todo 到 Planyway" / "把 todo 进 Jira" / "把这些 todo 建成 Jira issue" / "整理 inbox 发 Planyway" / 涉及 Planyway、Jira KAN、批量建 issue、把清单/笔记变成看板卡 的任务. ALSO handles single "mark-done" uploads after finishing one feature/bugfix (status set to Done, Epic auto-picked): triggers "上传 Planyway 吗" / "这个传 Planyway" / "传一下 Planyway" / "标记完成发 Planyway" / 完成功能后确认上传. Planyway has NO public API — it is just a view of Jira issues; add = create Jira issues via the browser's logged-in session. REQUIRES Chrome MCP connected to a tab already on duckgames.atlassian.net. Invoke BEFORE creating any KAN issues.
---

# Todo → Planyway (Jira KAN bulk import)

Planyway 没有公开 API，它只是 Jira 数据的视图。**加 todo = 建 Jira issue**，issue 自动出现在 Planyway 面板里。本 skill 是把已实跑通的 workflow 固化成的**执行流程 + 纪律**。

## 两种用法
- **模式 A — 批量导入 todo**：把清单/inbox 一次性建成 issue，状态留默认 To Do，进 Planyway 左侧 Unscheduled 让用户排期。见下方「模式 A」。
- **模式 B — 单条「已完成」上传**：勾哥完成一个小功能 / 修完 bug 后确认上传，建**一条** issue、自动挑 Epic、直接 transition 到「已完成」。见下方「模式 B」。
- 前置条件、查元数据（issue type id）、ADF 描述、踩坑记录两种模式**共用**。

## 前置条件 —— 先确认，缺了别硬上
1. **Chrome MCP 已连接**，且有一个标签页**已登录 `duckgames.atlassian.net`**。所有 Jira REST 调用靠这个标签页的 session cookie（`credentials:'same-origin'`），**不需要 API token**。
2. 若本会话**没有 Chrome MCP**：不要假装能建 issue。退路二选一告诉用户：
   - 把整理好的清单导出成 Jira CSV importer 能吃的 CSV（summary 必填列），用户在 Jira 项目设置里手动一次导入；或
   - 把下面第 3–4 步的 JS 整理好交给用户，自己粘到浏览器 DevTools 控制台跑（控制台原生支持顶层 await，可去掉 `.then()` 链）。

## 输入来源（两种）
- **A. 用户直接贴清单** —— 任意格式文本。
- **B. 从 yide Telegram inbox 拉** —— `G:\My Drive\yide\yide-brain\notes\inbox\telegram-2026-MM.md`（手机 Telegram bot 落点）。**靠显式标记筛，不靠猜**：勾哥在 Telegram 写笔记时会带「**planyway**」字样（如"重构 Clan，上传 planyway"/"发 planyway"/"#planyway"）。规则：**条目正文含 `planyway`（不分大小写）= 要上传**，其余一律跳过。匹配到的条目把 `planyway` 标记词从标题里剥掉再建 issue。推送成功后，把处理过的条目移到 `notes/inbox/_done/`（保留原时间戳头），避免下次重复导入。

## 模式 A — 批量导入 todo（严格按序，预览确认这步绝不省）

### 1. 整理清单 → 预览 → 等用户确认
把原始 dump 整理成「**Epic 分组 + issue 标题 + 描述**」的 markdown 表格给用户看。矛盾项标注在描述里，不擅自取舍。用户点头后才动 Jira。整理结果存档到项目（如 `QA/` 或 feature doc 下），方便对账。

### 2. 查项目元数据（拿 issue type id —— 每次都查，别硬编码）
在 atlassian.net 标签页执行：
```js
fetch('/rest/api/3/project/KAN', {headers:{'Accept':'application/json'}, credentials:'same-origin'})
  .then(r=>r.json())
  .then(j=>JSON.stringify({style:j.style, issueTypes:j.issueTypes.map(t=>({id:t.id,name:t.name,hierarchyLevel:t.hierarchyLevel}))}))
```
按 `hierarchyLevel` 认类型，**不要按名字**：`hierarchyLevel===0` = Task，`hierarchyLevel===1` = Epic（中文站叫"长篇故事"）。2026-06-11 KAN 的值是 Task=10001 / Epic=10002，但**每个项目可能不同，必须当场查**。

### 3. 批量建 Epic
```js
const adf = t => ({type:'doc',version:1,content:[{type:'paragraph',content:[{type:'text',text:t}]}]});
const epics = ['Epic名1','Epic名2'];
fetch('/rest/api/3/issue/bulk', {
  method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','Accept':'application/json','X-Atlassian-Token':'no-check'},
  body: JSON.stringify({issueUpdates: epics.map(n=>({fields:{
    project:{key:'KAN'}, issuetype:{id:'10002'}, summary:n, description:adf('来源说明')
  }}))})
}).then(r=>r.text())
```
返回里有新建的 KAN-xx key，**记下来**给下一步当 parent。

### 4. 批量建 issue 挂到 Epic
```js
const adf = t => ({type:'doc',version:1,content:[{type:'paragraph',content:[{type:'text',text:t}]}]});
const D = [ // [epicKey, 标题, 描述（可空）]
  ['KAN-67','重构 Clan','有 Figma 图，包含各种要素'],
  // ...
];
fetch('/rest/api/3/issue/bulk', {
  method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','Accept':'application/json','X-Atlassian-Token':'no-check'},
  body: JSON.stringify({issueUpdates: D.map(([p,s,d])=>({fields: Object.assign(
    {project:{key:'KAN'}, issuetype:{id:'10001'}, summary:s, parent:{key:p}},
    d ? {description: adf(d)} : {}
  )}))})
}).then(r=>r.text())
```
不挂 Epic 的散 issue：去掉 `parent` 字段即可。

### 5. 验证（必做，别跳）
```js
Promise.all(['KAN-67','KAN-68'].map(k=>
  fetch('/rest/api/3/search/jql?maxResults=200&fields=summary&jql='+encodeURIComponent('parent = '+k),
    {headers:{'Accept':'application/json'},credentials:'same-origin'})
  .then(r=>r.json()).then(j=>k+': '+j.issues.length)
)).then(a=>a.join(' | '))
```
逐 Epic 数一遍和清单对账。最后让用户打开 Planyway 页面人工看一眼 Unscheduled 面板（Planyway iframe 的 CDP 截图会超时，视觉验证留给人工）。

## 模式 B — 单条「已完成」上传（完成功能/修完 bug 后）

触发：勾哥完成一个推进 ER 的小功能 / 修完一个 bug 后，翼德主动问一句「这个上传 Planyway 吗？」，勾哥点头才走本流程。**口径**：值得问 = 玩家可见的功能/内容、修了影响玩家的 bug；改工具/配置/文档/纯重构这类不问（跟战绩 bump 同一口径）。Epic 由翼德读现有结构**自动决定**，**不让勾哥操心**；找不到合适的就**留空不挂**（不擅自新建 Epic）。

### B-1. 拟标题 + 描述
标题 = 这次功能/修复的一句话；描述（可空）= 做了啥 + 关键文件/commit。先给勾哥扫一眼，点头再建。

### B-2. 查 issue type id
同模式 A 第 2 步（查 `/rest/api/3/project/KAN`，按 `hierarchyLevel` 认 Task=0 / Epic=1，当场查不硬编码）。

### B-3. 读现有 Epic 学结构 → 自动挑最匹配的
用 B-2 查到的 Epic type id（设为 `EID`）拉所有 Epic：
```js
fetch('/rest/api/3/search/jql?maxResults=100&fields=summary&jql='+encodeURIComponent('project=KAN AND issuetype='+'EID'+' ORDER BY created DESC'),
  {headers:{'Accept':'application/json'},credentials:'same-origin'})
  .then(r=>r.json()).then(j=>j.issues.map(i=>i.key+': '+i.fields.summary).join('\n'))
```
翼德读这批 Epic 的 summary（必要时再拉某 Epic 下的 issue 看归类习惯），按这次功能内容**自己判断**挂哪个 Epic。语义不够贴近就**留空不挂**，别硬塞。

### B-4. 建单条 issue
```js
const adf = t => ({type:'doc',version:1,content:[{type:'paragraph',content:[{type:'text',text:t}]}]});
fetch('/rest/api/3/issue', {
  method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','Accept':'application/json','X-Atlassian-Token':'no-check'},
  body: JSON.stringify({fields: Object.assign(
    {project:{key:'KAN'}, issuetype:{id:'TASK_ID'}, summary:'功能标题'},
    /*有 Epic 时*/ {parent:{key:'KAN-XX'}},   // 留空不挂就删掉这行
    /*有描述时*/ {description: adf('做了啥')}
  )})
}).then(r=>r.json()).then(j=>j.key)   // 记下新 key
```

### B-5. transition 到「已完成」
建出来默认是 To Do。先查这条 issue 当前可走的 transitions，再 POST 过去：
```js
// 查
fetch('/rest/api/3/issue/KAN-XX/transitions',{headers:{'Accept':'application/json'},credentials:'same-origin'})
  .then(r=>r.json()).then(j=>j.transitions.map(t=>t.id+':'+t.name).join(' | '))
// 走（DID = 上面「完成/Done/已完成」那项的 id）
fetch('/rest/api/3/issue/KAN-XX/transitions',{
  method:'POST', credentials:'same-origin',
  headers:{'Content-Type':'application/json','Accept':'application/json'},
  body: JSON.stringify({transition:{id:'DID'}})
}).then(r=>r.status)   // 204 = 成功
```
若 transition 列表里没有直达「已完成」，说明 workflow 不允许一步到位：先走「进行中/In Progress」，再查一次 transitions 走「已完成」。

### B-6. 验证（必做）
```js
fetch('/rest/api/3/issue/KAN-XX?fields=summary,status,parent',{headers:{'Accept':'application/json'},credentials:'same-origin'})
  .then(r=>r.json()).then(j=>JSON.stringify({key:j.key, status:j.fields.status.name, parent:j.fields.parent&&j.fields.parent.key, summary:j.fields.summary}))
```
确认 `status` 是已完成、`parent` 是预期 Epic（或 null）。把 issue key + 状态报给勾哥。

## 踩坑记录（都是实跑遇到的）
1. Chrome MCP 的 JS 工具**不支持顶层 `await`**，全用 `.then()` 链，最后一个表达式即返回值。（浏览器 DevTools 控制台则支持 await。）
2. description 必须是 **ADF 格式**（v3 API），纯字符串报错；用上面的 `adf()` helper。
3. `/rest/api/3/issue/bulk` 单次**上限 50 条**，超过分批。
4. `/rest/api/3/search/jql` 的 `maxResults=0` 会报错（须 1–5000），数数用 `issues.length`。
5. team-managed 项目挂 Epic 用 `parent:{key:'KAN-67'}` 字段，**不是**旧的 epic link 字段。
6. Epic 的 issue type 名称随站点语言变（中文站"长篇故事"），按 `hierarchyLevel===1` 找。
7. Planyway iframe 页面 CDP 截图会超时，视觉验证留给人工。
8. issue 不填日期 → 自动落 Planyway 左侧 Unscheduled 面板，符合预期（让用户排期）。
