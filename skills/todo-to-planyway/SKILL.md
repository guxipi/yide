---
name: todo-to-planyway
description: Use to bulk-import a todo list into Jira project KAN so the issues show up in Planyway for scheduling — no manual one-by-one pasting. ALSO trigger on the user's Chinese requests, e.g. "翼德 发 Planyway" / "发到 Planyway" / "导入 todo 到 Planyway" / "把 todo 进 Jira" / "把这些 todo 建成 Jira issue" / "整理 inbox 发 Planyway" / 涉及 Planyway、Jira KAN、批量建 issue、把清单/笔记变成看板卡 的任务. ALSO handles single "mark-done" uploads after finishing one feature/bugfix (status → Done, Epic auto-picked) — "上传 Planyway 吗" / "这个传 Planyway" / "传一下 Planyway" / "标记完成发 Planyway" / 完成功能后确认上传. Planyway has no public API, it is just a view of Jira issues. Preferred channel — the official Atlassian Rovo MCP (claude.ai) reads/writes duckgames Jira directly, no browser / Chrome-MCP / API-token; a Chrome MCP tab logged in to duckgames.atlassian.net is the fallback. Invoke BEFORE creating any KAN issues.
---

# Todo → Planyway (Jira KAN bulk import)

Planyway 没有公开 API，它只是 Jira 数据的视图。**加 todo = 建 Jira issue**，issue 自动出现在 Planyway 面板里。本 skill 是把已实跑通的 workflow 固化成的**执行流程 + 纪律**。

## 两种用法
- **模式 A — 批量导入 todo**：把清单/inbox 一次性建成 issue，状态留默认 To Do，进 Planyway 左侧 Unscheduled 让用户排期。见下方「模式 A」。
- **模式 B — 单条「已完成」上传**：勾哥完成一个小功能 / 修完 bug 后确认上传，建**一条** issue、自动挑 Epic、直接 transition 到「已完成」。见下方「模式 B」。
- 前置条件、查元数据（issue type id）、ADF 描述、踩坑记录两种模式**共用**。

## 必填字段（两模式共用，建完必补齐再收尾）
每条 issue 都要写齐 **Assignee / Label / Parent / Due date**，别只建标题。建完用 `getJiraIssue({fields:['assignee','labels','parent','duedate','status']})` 核一遍。
- **Assignee —— 按机器分（重要，别写死全局默认）**：Planyway 上传的归属看**当前在哪台机器**完成的：
  - **changhui 的开发机**（本机标志：Unity 项目根 `F:\GitManagedUnityProjects\Extraction`、Google 账号 krystalxch）→ 全算 **Changhui xu** 完成 → assignee accountId `70121:0946dac6-5c4b-4690-8891-b4a4d3355b00`（email krystalxch@gmail.com；查用户按 `changhui` 或 email，**`changhuixu` 查不到**）。
  - **其他设备** → 算**勾哥**完成 → assignee = duck games，accountId `5ed9bc8f570e860a984e1afb`（email militarypineapple@gmail.com）。
  - 拿不准在哪台机 → 读**本机 Claude 记忆**里的 planyway 上传约定（per-machine memory，如 `planyway-upload-fields-this-machine`）；没有则默认勾哥。account/盘符按机器私有，别把某台机的 accountId 当全局默认。
  - 写法：`createJiraIssue` 用 `assignee_account_id`；`editJiraIssue`/`transitionJiraIssue` 用 `fields:{assignee:{accountId:'…'}}`。
- **Label** = **类型 + 模块各一个**：类型 ∈ bug/feature/polish/tool；模块 ∈ hud/combat/loot/meta/server… 按内容自拟。Jira label 不能带空格。
- **Parent** = 贴最合适的 Epic（读现有 Epic 自动判断；关卡内/核心战斗循环 → `KAN-69 🎮 core loop`；贴不上才留空）。
- **Due date**（`fields.duedate` = `YYYY-MM-DD`）：模式 B 已完成的填**上传当天**；模式 A 待排期的可留空（进 Planyway 左侧 Unscheduled 由用户排）。

## 通道 —— 按优先级，能用上面那条就别用下面（缺了别硬上）
1. **通道①·官方 Atlassian Rovo MCP（首选）** —— `mcp__claude_ai_Atlassian_Rovo__*` 工具**直读直写 duckgames Jira，不需要浏览器 / Chrome MCP / API token**。先 `getAccessibleAtlassianResources` 拿 duckgames 的 `cloudId`（当前 `5c8b1014-3b9a-4b07-a050-0f9b3980a628`，每次以查到的为准），之后所有 Jira 操作都带这个 cloudId。建卡 / 查 / transition 的工具映射见下方「通道① 操作映射」。**模式 A/B 的逻辑步骤（整理 → 预览 → 确认 → 建 → 验证）一字不变，只是把 `fetch(...)` 换成对应 MCP 工具。**
2. **通道②·Chrome MCP（退路）** —— 仅当有 Chrome MCP 且有标签页**已登录 `duckgames.atlassian.net`** 时用。所有 Jira REST 靠该标签页 session cookie（`credentials:'same-origin'`），不需要 API token。即模式 A/B 正文里的 `fetch(...)` 写法。
3. **两条都没有** —— 不要假装能建 issue。退路二选一告诉用户：把清单导出成 Jira CSV importer 能吃的 CSV（summary 必填列）手动一次导入；或把模式 A 第 3–4 步的 JS 交给用户自己粘到浏览器 DevTools 控制台跑（控制台支持顶层 await，可去掉 `.then()` 链）。

## 通道① 操作映射（官方 MCP，首选走这套）
所有调用都带 `cloudId`（duckgames，见上）。逻辑/纪律照模式 A/B，工具按下表换：
- **查项目元数据 / issue type**：`getVisibleJiraProjects({cloudId, searchString:'KAN', action:'create'})` → 返回 `issueTypes` 按 `hierarchyLevel` 认：`0`=任务、`1`=长篇故事(Epic)、`-1`=子任务（**别按名字硬编码，每次查**）。
- **建 issue**：`createJiraIssue({cloudId, projectKey:'KAN', issueTypeName:'任务', summary, description, contentFormat:'markdown'})`
  - 挂 Epic：加 `parent:'KAN-67'`（team-managed 直接传 Epic key，同 REST 的 parent 字段）。
  - 描述：传纯文本字符串 + `contentFormat:'markdown'`，**不用手搓 ADF**。
  - 建 Epic：`issueTypeName:'长篇故事'`，建完记下返回的 `KAN-xx` key 当 parent。
  - **无 bulk**：官方 MCP 逐条建，循环 `createJiraIssue`（不像通道② 有 `/issue/bulk`）。
- **建时一步置完成**（模式 B 一气呵成）：`createJiraIssue` 直接带 `transition:{id:'DID'}`（DID 先用 `getTransitionsForJiraIssue` 查）。
- **查现有 Epic（模式 B 挑 Epic）**：`searchJiraIssuesUsingJql({cloudId, jql:"project=KAN AND issuetype=长篇故事 ORDER BY created DESC", fields:['summary'], maxResults:100})`。
- **transition 到已完成**：`getTransitionsForJiraIssue({cloudId, issueIdOrKey:'KAN-XX'})` 拿「已完成」的 id → `transitionJiraIssue({cloudId, issueIdOrKey:'KAN-XX', transition:{id:'DID'}})`。
- **验证**：`getJiraIssue({cloudId, issueIdOrKey:'KAN-XX', fields:['summary','status','parent','assignee','labels','duedate']})` —— 必填字段（见上「必填字段」）逐项核齐。
- **查 assignee accountId**：`lookupJiraAccountId({cloudId, searchString:'changhui' 或 email})`（注意 `changhuixu` 查不到，用 `changhui`/email）。

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
**建时把「必填字段」一并带上**（见上方共用「必填字段」section）：`assignee`（按机器分！本机=Changhui xu / 其他机=勾哥）、`labels`（类型+模块各一）、`parent`（Epic）、`duedate`（当天）。通道① 用 `createJiraIssue({assignee_account_id, additional_fields:{labels:[...]}, parent, ...})` + 建后 `editJiraIssue` 补 duedate；通道② fetch 写法如下：
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
fetch('/rest/api/3/issue/KAN-XX?fields=summary,status,parent,assignee,labels,duedate',{headers:{'Accept':'application/json'},credentials:'same-origin'})
  .then(r=>r.json()).then(j=>JSON.stringify({key:j.key, status:j.fields.status.name, parent:j.fields.parent&&j.fields.parent.key, assignee:j.fields.assignee&&j.fields.assignee.displayName, labels:j.fields.labels, duedate:j.fields.duedate, summary:j.fields.summary}))
```
确认 `status` 已完成、`parent` 是预期 Epic（或 null）、**`assignee` 按机器对（本机=Changhui xu）、`labels` 类型+模块齐、`duedate` 是当天**。把 issue key + 状态报给勾哥。

## 踩坑记录（都是实跑遇到的）
1. Chrome MCP 的 JS 工具**不支持顶层 `await`**，全用 `.then()` 链，最后一个表达式即返回值。（浏览器 DevTools 控制台则支持 await。）
2. description 必须是 **ADF 格式**（v3 API），纯字符串报错；用上面的 `adf()` helper。
3. `/rest/api/3/issue/bulk` 单次**上限 50 条**，超过分批。
4. `/rest/api/3/search/jql` 的 `maxResults=0` 会报错（须 1–5000），数数用 `issues.length`。
5. team-managed 项目挂 Epic 用 `parent:{key:'KAN-67'}` 字段，**不是**旧的 epic link 字段。
6. Epic 的 issue type 名称随站点语言变（中文站"长篇故事"），按 `hierarchyLevel===1` 找。
7. Planyway iframe 页面 CDP 截图会超时，视觉验证留给人工。
8. issue 不填日期 → 自动落 Planyway 左侧 Unscheduled 面板，符合预期（让用户排期）。

### 通道① 官方 MCP 注意点（getAccessibleAtlassianResources / getVisibleJiraProjects 已接通实测；createJiraIssue / transition 的细节首次实跑时回填校正）
9. `createJiraIssue` 用 **`issueTypeName`（类型名，不是 id）**；本站是中文站，传中文名「任务」/「长篇故事」/「子任务」（英文 Task/Story 不一定被接受，以 `getVisibleJiraProjects` 查到的 `name` 为准）。
10. 描述用 `description` 纯文本 + `contentFormat:'markdown'`，**不必手搓 ADF**（只有通道② 的 fetch 才需要 `adf()` helper）。
11. 官方 MCP **没有 bulk 接口**，批量导入靠循环 `createJiraIssue` 逐条建；条数多时悠着点别一次发太猛。
12. 挂 Epic 同样用 `parent` 传 Epic key（team-managed，与通道② 一致）。
13. duckgames `cloudId` 当前 `5c8b1014-3b9a-4b07-a050-0f9b3980a628`、KAN project id `10000`（team-managed / next-gen）；cloudId 仍每次用 `getAccessibleAtlassianResources` 查一遍兜稳。
