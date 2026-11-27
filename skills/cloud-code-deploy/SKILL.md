---
name: cloud-code-deploy
description: Change/build/deploy Extraction's UGS Cloud Code server module — deploy + discipline. Trigger on "改服务器" / "服务端代码" / "加个 cloud code 端点" / "部署服务器" / "deploy cloud code" / "服务端要改" / "CloudCode 报错" / "server endpoint" / "服务侧", also on silent-write symptoms "存档没保存" / "数据没存上服务器" / "进度/排行榜没更新" / "CloudSave 没写进去" / "云端数据没生效", or ANY change touching CloudCode/. Guards silent-fallback trap (endpoints write nothing when IGameApiClient is null). server-service-pattern.md = architecture; THIS = deploy layer.
---

# Cloud Code: Change & Deploy (Extraction · UGS C# module)

把服务端代码改对、编对、部署上,且知道"怎么和服务器代码协作"。"端点有响应"**只证明端点跑了、没证明 CloudSave 真持久化**(详见下「血泪前提」),先读那一节,它是 cloud 到底有没有真工作的根。

> 架构怎么设计(server-first / optimistic / operation queue / version tracking)读同目录 `../server-service-pattern.md`。本 skill 只管:**改了之后怎么编、怎么部、怎么确认部上了(且没在假成功)。** 服务端这块勾哥定的规矩(部署红线和部署树、玩家数据安全、禁写策略、服务端权威和防作弊、发版热更)全文在 vault `01 - 星际拓荒重构/025_服务器运维手册/AI记忆/现行口径_服务端与发版.md`,改服务端前读全文;下面只写操作步骤,规矩只留一句加指针。

---

## 第〇步:服务端代码长在哪(项目地形)

```
CloudCode/
├── README.md                         # 端点文档(每加端点补一段)
├── src/
│   ├── ExtractionCloudCode.sln       # 部署用 solution(只主项目)
│   ├── ExtractionCloudCode.ccmr      # module 引用(指向 .sln,ugs deploy 读它)
│   ├── ExtractionCloudCode.ccm       # ⚠️ 手动 zip 的旧产物——会和 ugs 编译冲突,见血泪前提/第四步,别留
│   └── ExtractionCloudCode/
│       ├── ModuleConfig.cs           # ICloudCodeSetup:注册 IGameApiClient(没它 = 整个 module 假死,见血泪前提)
│       ├── Endpoints/*.cs            # [CloudCodeFunction] 端点(BaseEndpoints, RaidEndpoints, ClanEndpoints, ...)
│       ├── Models/*.cs              # 请求/响应 DTO + 数据模型
│       └── <Domain>/                 # 按系统分的目录(Alliance / Base / Raid / Shop …),新端点先看同系统目录里有没有现成的
└── tests/ExtractionCloudCode.Tests.sln  # 测试 solution(隔离,不部署)
```
客户端侧:`Assets/Scripts/Core/Services/UGS/CloudCodeManager.cs` 是唯一的客户端→服务端桥(wrapper 方法 + response 内部类 + 离线 fallback)。
- 模块名常量 `MODULE_NAME`;每端点一个 `FUNC_*` 名字常量。
- 端点类被 `[CloudCodeFunction("Name")]` 自动发现 + 实例化,构造注入 `ILogger`、方法参数注入 `IExecutionContext`;但 **`IGameApiClient` 不会被自动注入**,必须自己在 `ModuleConfig:ICloudCodeSetup` 注册(见下「血泪前提」),否则 null。构造函数签名照 `BaseEndpoints` 抄。

---

## ⚠️ 血泪前提:cloud 端点默认在「假工作」

这个 module 的端点能**编译过、部署过、create 返回数据、单测绿**,而 CloudSave 实际一个字没写进去——每个端点的 `LoadXxxAsync` 都有 try-catch 吞掉 NRE 返回空默认值,表面全成功,真相是一直走客户端 local fallback。加/改端点前必须确认两件事,否则白干:

**坑A — `IGameApiClient` 必须显式注册,否则全端点都 null。** 框架只自动给 `ILogger`(构造)+ `IExecutionContext`(方法参数);`IGameApiClient` **要自己注册**,没注册就 null,`_gameApiClient.CloudSaveData.XxxAsync` 全 NRE(被 try-catch 吞)。确认 `CloudCode/src/ExtractionCloudCode/ModuleConfig.cs` 存在:
```csharp
using Microsoft.Extensions.DependencyInjection; // AddSingleton 扩展在这,别漏
using Unity.Services.CloudCode.Apis;
using Unity.Services.CloudCode.Core;
public class ModuleConfig : ICloudCodeSetup {
    public void Setup(ICloudCodeConfig config) =>
        config.Dependencies.AddSingleton<IGameApiClient>(GameApiClient.Create());
}
```
> 一个 ModuleConfig 管整个 module 的所有端点;工程里现在已有这个类,别删、别另起第二个。

**坑B — CloudSave 写 value 必须用 JSON `string`,不能用 `JsonElement`。** `new SetItemBody(key, JsonHelper.Serialize(obj))`(string,对齐能工作的 `ShopEndpoints`)。用 `SerializeToElement(obj)`(JsonElement)写进去**读不回**——下次请求 `Deserialize` 失败→空对象→字段全丢(表现:create 成功但下一次读 player state 是空、ClanId 没了)。

**怎么确认真工作(别被假成功骗,这是部署后验证的核心):**
- **必须另起一次请求读回**。create/save 的返回值是**内存**序列化,不证明写进了 CloudSave。要 create 后用**另一个端点调用**去 read,确认读到刚写的字段。
- 隔离 module 级 vs 端点级:在任一已知端点临时加 `[CloudCodeFunction("Ping")] public async Task<bool> Ping(IExecutionContext c){ await Task.CompletedTask; return _gameApiClient==null; }`,部署后客户端 `CallModuleEndpointAsync<bool>(...,"Ping",...)` 调它。整个 module 共享 ModuleConfig,一个端点 null 基本就是全 null = 没注册;某个端点单独 null 才往别处查。

---

## 第一步:加/改端点 = 三件套(缺一不可)

### 1) 服务端端点 `Endpoints/<Domain>Endpoints.cs`
```csharp
[CloudCodeFunction("CompleteRaid")]
public async Task<CompleteRaidResult> CompleteRaid(IExecutionContext context, string targetPlayerId)
{
    // 校验 → load CloudSave → mutate → save → return
}
```
- CloudSave 读写经 `_gameApiClient.CloudSaveData.GetItemsAsync / SetItemAsync`,key 用常量(`player_base` 等)。写 value 用 `JsonHelper.Serialize(obj)`(**string,不是 `SerializeToElement` 的 JsonElement——写进去读不回**,见血泪前提坑B);读用 `Results[0].Value?.ToString()` + `JsonHelper.Deserialize<T>`。
- **写入 token 一律 `context.ServiceToken`**:dev / staging / production 都开了 UGS 禁写策略,玩家身份(`context.AccessToken`)写 Cloud Save / Economy 一律被拒,`ServerWriteIdentityTests` 扫源码把关;服务身份下 UGS 不查写的是谁的档,目标玩家 id 只取 `context.PlayerId` 或服务端自己存的状态;客户端不许有直连写入。规矩出处见现行口径「玩家数据安全」节。
- 推送/跨端点调用:`new NotificationEndpoints(_gameApiClient, NullLoggerFactory...)` 直接 new(无 DI 也能手动构)。

### 2) 模型 `Models/<Domain>Models.cs`
请求/响应 DTO + 服务端镜像的数据类。

### 3) 客户端 wrapper `CloudCodeManager.cs`
```csharp
#if UNITY_SERVICES_CLOUDCODE
    var resp = await CallLenientAsync<CompleteRaidResponse>(
        MODULE_NAME, FUNC_COMPLETE_RAID, args);
#endif
```
- 解析响应一律走 `CloudCodeManager.CallLenientAsync<T>`(宽松反序列化,服务端多加字段不炸客户端),不直接调 `UnityCloudCode.Instance.CallModuleEndpointAsync<T>`;服务端加字段的同一个提交里镜像客户端 DTO。
- 失败 / 离线怎么处理照同一功能现有 wrapper 的写法和现行口径「服务端权威和防作弊」节(权威操作断网是转圈挡操作,不是本地模拟结果)。
- response 内部类字段名**必须 camelCase 精确匹配服务端 JSON 序列化出来的字段**。对不上 = 字段静默为默认值。
- 每个新端点:加 `FUNC_*` 常量 + wrapper 方法 + `[Serializable] private class XxxResponse`。

---

## 第一步半:写端点前过一遍零信任 checklist

服务端 / 交易经济 / 异步 PvP 结算是**强一致 + 防作弊红线区**,AI 写这类逻辑时最容易默认"信客户端、走 happy path",埋下刷钱/越权/重放/封不掉外挂的坑。按场景过:

**通用(所有端点)**:客户端只是展现层,**所有**传入参数都要校验(ID 存在吗、属于这个玩家吗、数值在范围内吗);要用的余额/战力/状态**重新从 DB 拉最新**,绝不信客户端传来的值;操作前校验前置条件(等级/资源/归属)防越权;字符串参数(昵称/留言)落库或回显前 sanitize;可被脚本刷的接口加 rate limit;失败必记 audit log(who/what/来源去向枚举)并返回明确错误码,方便查账回档。

**交易 / 拍卖行 / 商城扣费**:扣 A 的钱 + 给 B 发货必须原子(要么全成要么全败,不能半成功);校验数量与总价**非负**且不超类型上限(防负数刷钱、溢出绕过);执行前重拉双方最新余额;用唯一 **TradeID/RequestId 判重**,重复请求只生效一次(网络重发是常态)。

**异步 PvP 结算**:战斗核写成纯函数确定性核(防守方快照深拷贝独立存、剥离 UI、不依赖本地时间、随机走 seed、服务端结算或验录像);校验本局 **BattleToken** 合法且未被用过,用过即拒(防重放);做合理性校验(1 秒内打赢 10 万战力对手这种 → 拒绝/标记/封禁),别照单全收;结算用**服务端存的防守方快照**,不信客户端回传的防守方数据。

核心逻辑写边界测试:钱不够 / 并发扣 / 0 血 / 溢出。

详细镜头见 `~/.yide/experts/architect.md` 的「数据纪律 / 安全」段;ER 服务端权威的具体口子(背包、结算、掉落校验怎么复算)见现行口径「服务端权威和防作弊」节。

---

## 第二步:两个会咬人的硬坑(实战踩过)

1. **客户端缺 wrapper 方法 → 卡死整个 Unity 编译**。客户端别处(如 ClanService)调了 `cloudCode.FooAsync()` 但 CloudCodeManager 没这方法 → CS1061 → 整个项目编译红 → Play 进不去。**改服务端前先看客户端编译(`unity command console status` + grep `error CS`)**,有这种残留先补齐 wrapper(可先写本地 fallback 占位)。

2. **客户端/服务端 model 字段必须全对齐**。服务端 `LoadBaseDataAsync → mutate → SaveBaseDataAsync` 是**整对象 round-trip**。服务端 model 缺了客户端 `PlayerBaseData` 的某个字段(如 `OwnedCores`/`DefenseLog`/`ProductionSlots`),反序列化丢字段 → save 回去时**静默清空玩家数据**。加端点前先比对两边 model,服务端要镜像客户端**每一个**字段。

---

## 第三步:编译验证(部署前必过)

```bash
cd CloudCode/src
dotnet build ExtractionCloudCode.sln --configuration Release
```
看到 `Build succeeded.` 才继续(warning CS8618 nullable 一堆是既有噪音,忽略;只看 error)。输出很长,grep `error|Build succeeded|FAILED`。

---

## 第四步:部署(默认用工程自带 `CloudCode/deploy-dev.ps1`)

**🚫 红线:手动部署一律只到 `development`,绝不 `-e production`**;prod 只走 CI,prod 的残留也不手动删(规矩全文见现行口径「部署」节)。

**部署前(dev 上全项目只有一个 module,谁最后部谁的树就是 dev 的全部)**:`git fetch`,部署树要同时含 origin/main 和各线已部到 dev 的已提交服务端(逐个 `git merge-base --is-ancestor` / `git cat-file -t <hash>` 核,缺的先合,找不到对象就停下问勾哥);工作区里别人未提交的 CloudCode / UGSConfig 改动不带;部前部后给在用 dev 的线发一句(部署树 id、含什么),部前设 `$env:OWNER`。

**默认路 —— 工程脚本**(在工程根跑):
```powershell
powershell -ExecutionPolicy Bypass -File CloudCode\deploy-dev.ps1 -SkipTests   # -DryRun 只跑部署前的闸
```
- 脚本硬锁 development,用 `BuildDependencies\ugs.exe`;凭据先读环境变量,没有就从编辑器 EditorPrefs(`CloudCode_ServiceKeyId/ServiceSecretKey`,和 Unity 内 `Deploy/Cloud Code` 窗口同一套)读,会话不用碰凭据。本机裸 `ugs` 报 `project-id is not set` / `not logged into any service account` 是正常的,别据此说部不了。
- 自带两道闸:HEAD 不含 origin/main 就拒(`-AllowBehindMain` 放行)、`CloudCode/src` 或 `UGSConfig` 有未提交改动就拒(`-AllowDirty` 放行);「含各线已提交服务端」它拦不了,仍要人核。
- 流程是 `dotnet publish` → 打 `.ccm` → `ugs deploy <ccm>` → 回读模块列表,成功往 `Library/deploy_dev.log` 记一行。
- 不带 `-SkipTests` 会先跑全量 `dotnet test`,一条红就中止;先自己跑和本次改动相关的测试,过了再带 `-SkipTests`。

**备用路 —— `ugs deploy .` 目录形式**(脚本跑不通、裸 ugs 已认证时;让 ugs 读 `.ccmr` 编译 `.sln`):
```powershell
cd CloudCode/src
ugs deploy . -e development --json    # Result 里 path 是 .sln 才对
```
- **`"Up to date"` 状态不可信**——它有本地缓存,删了远端 module 它还说 up-to-date。**用 module DateModified 核实**(两条路都适用):`modules list -e development --json` 看时间戳是不是刚刚(对比 `(Get-Date).ToUniversalTime()`)。这是唯一可信的"部上了"信号。
- 走这条路前删掉 src 里的 `ExtractionCloudCode.ccm`(脚本打的或手动 zip 的),否则和 ugs 编译产物冲突报 `was found duplicated`。
- 改了代码 `ugs deploy .` 仍 `"Up to date"` → 删 temp 缓存 `Remove-Item "$env:TEMP\ExtractionCloudCode" -Recurse -Force`;还不行就**强制**:`ugs cloud-code modules delete ExtractionCloudCode -e development` 再 `ugs deploy .`(delete 后 DateModified 必然刷新 = 真部署了)。
- `ugs deploy <.ccmr文件>`(直接指文件)Result 空、不生效——必须**目录**形式 `ugs deploy .`。

---

## 第五步:部署后验证(部署成功 ≠ 端点真工作)

**最大陷阱:cloud 端点「假成功」**——返回 success、看到数据,但可能是 try-catch 后的空默认或客户端 fallback(见血泪前提)。必须验证**服务端真读写了 CloudSave**:
- **另起一次请求读回**:create/save 后用**另一个端点调用**去 read,确认读到刚写的字段。create 的返回值是内存序列化,不算。
- 不开 Unity 也能验:匿名玩家 REST 直调 module 端点(新端点空参报业务校验错 = 新代码在跑,报 `code 9029` = 没部上或还在传播),写法见 vault 记忆 `025_服务器运维手册/AI记忆/cloudcode-rest-anon-verify.md`。
- **验证 server-authoritative 副作用真发生**:donate 后看 GOLD 真的被**服务端** Economy 扣了(不是客户端扣)、fund 真加了。
- 端点写死一个可识别特征字符串,进游戏看到它 = 新代码在跑(不是旧版/fallback)。
- 部署后约 30 秒内的请求可能还打到旧实例,半分钟后连测几轮再下结论;除了自己改的端点,至少再调一个和本次无关、会写存档的端点确认没回退。

**驱动 play 验证 cloud 的坑**(Unity CLI 主路,Coplay 兜底):
- play 必须从 **Boot** 起,否则 services 全 null。怎么钉 / 还原 `playModeStartScene` 见 `playmode-verify-iterate` 第〇步;写个一次性脚本查 `SceneManager.GetActiveScene().name` + `GameObject.Find("ServiceRoot")` 确认真从 Boot 起来了(`activeScene=HomeScreen` + `ServiceRoot=null` = 没从 Boot 起)。
- **domain reload 会杀掉 play session 的 services**(跑外部命令让 Unity 失焦 / asset refresh 都可能触发,ClanService 突然变 NULL)。别分多次脚本调用慢慢测——用**一个自等待脚本**一口气跑完:`for(int i=0;i<50;i++){ svc=ClanService.Instance; if(svc!=null&&svc.IsReady) break; await Task.Delay(400);}` 然后顺着 create→donate→leave,在一个稳定窗口内做完。
- 完整 Play 验证纪律见 `playmode-verify-iterate`。

---

## 第六步:收尾

- 改了端点 → 更新 `CloudCode/README.md` 对应段落(参数/返回/行为)。
- `.ccm` 是构建产物(脚本每次重打),别纠结它的 git 状态;走备用路前要删(见第四步,会和 ugs 编译冲突)。

---

## 速查表

| 要做的 | 命令/位置 |
|---|---|
| **IGameApiClient 注册** | `ModuleConfig:ICloudCodeSetup` → `config.Dependencies.AddSingleton<IGameApiClient>(GameApiClient.Create())`(没它全端点 null) |
| **CloudSave 写** | `new SetItemBody(key, JsonHelper.Serialize(obj))`(string,**别** `SerializeToElement` JsonElement) |
| **🚫 数据安全红线** | 改 Cloud Save 端点绝不能丢玩家数据(model 字段与客户端全对齐,round-trip 缺字段 = 静默清空);全文见现行口径「玩家数据安全」节 |
| 编译服务端 | `cd CloudCode/src && dotnet build ExtractionCloudCode.sln -c Release` |
| 客户端编译 | `unity command console status` + grep 日志 `error CS` |
| 部署 | 工程根 `powershell -ExecutionPolicy Bypass -File CloudCode\deploy-dev.ps1 -SkipTests`(部署树含 origin/main + 各线已提交服务端);备用 `cd CloudCode/src && ugs deploy . -e development`(先删 src 里的 .ccm) |
| 强制重部署(备用路) | `ugs cloud-code modules delete ExtractionCloudCode -e development` 再 `ugs deploy .` |
| **核实部上了** | `ugs cloud-code modules list -e development --json` 看 DateModified(**别信 "Up to date"**) |
| 验证真工作 | **另起请求读回**写的字段;半分钟后连测,再调一个无关的写存档端点;不开 Unity 用匿名 REST 直调 |
| 客户端调端点 | `CloudCodeManager.CallLenientAsync<T>`(别直接 `CallModuleEndpointAsync<T>`) |
| Play 验证 | 按 `playmode-verify-iterate` 钉 Boot 起 + 自等待脚本一口气跑(domain reload 杀 services) |
| 架构怎么设计 | 读 `../server-service-pattern.md` |
