---
name: cloud-code-deploy
description: How to CHANGE, BUILD, and DEPLOY Extraction's UGS Cloud Code server module — the deploy mechanics + the discipline for working with server code. Trigger on "改服务器" / "服务端代码" / "加个 cloud code 端点" / "部署服务器" / "deploy cloud code" / "服务端要改" / "CloudCode 报错" / "server endpoint" / "服务侧" or ANY change touching the CloudCode/ folder. Covers: the silent-fallback trap (every CloudSave endpoint can compile/deploy/return-data while writing nothing — because IGameApiClient is null and try-catch hides it), the mandatory ModuleConfig:ICloudCodeSetup registration of IGameApiClient, CloudSave write must be string (JsonHelper.Serialize) not JsonElement (SerializeToElement), new-endpoint trinity (Endpoints + Models + client wrapper), client/server model field parity, dotnet build, `ugs deploy .` (NOT hand-zipped .ccm; "Up to date" status is unreliable — check module DateModified), and read-back post-deploy verification. The service ARCHITECTURE pattern (server-first vs optimistic, queues, version tracking) lives in server-service-pattern.md — THIS skill is the deploy + iteration layer on top.
---

# Cloud Code: Change & Deploy (Extraction · UGS C# module)

把服务端代码改对、编对、部署上,且知道"怎么和服务器代码协作"。两次实战蒸馏:① RaidEndpoints(FindRaidTarget/CompleteRaid/GetDefenseLog)→ 编译 → 部署 → 端点有响应;② clan 多人(create/donate/leave)→ 才发现①的"端点有响应"**只证明端点跑了、没证明 CloudSave 真持久化**——整个 module 的 `IGameApiClient` 是 null、所有 CloudSave 端点一直假成功走 fallback(详见下「血泪前提」)。所以先读那一节,它是 cloud 到底有没有真工作的根。

> 架构怎么设计(server-first / optimistic / operation queue / version tracking)读同目录 `../server-service-pattern.md`。本 skill 只管:**改了之后怎么编、怎么部、怎么确认部上了(且没在假成功)。**

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
│       └── Models/*.cs              # 请求/响应 DTO + 数据模型
└── tests/ExtractionCloudCode.Tests.sln  # 测试 solution(隔离,不部署)
```
客户端侧:`Assets/Scripts/Core/Services/UGS/CloudCodeManager.cs` 是唯一的客户端→服务端桥(wrapper 方法 + response 内部类 + 离线 fallback)。
- 模块名常量 `MODULE_NAME`;每端点一个 `FUNC_*` 名字常量。
- 端点类被 `[CloudCodeFunction("Name")]` 自动发现 + 实例化,构造注入 `ILogger`、方法参数注入 `IExecutionContext`;但 **`IGameApiClient` 不会被自动注入**,必须自己在 `ModuleConfig:ICloudCodeSetup` 注册(见下「血泪前提」),否则 null。构造函数签名照 `BaseEndpoints` 抄。

---

## ⚠️ 血泪前提:cloud 端点默认在「假工作」(2026-06 clan 多人踩穿)

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
> 一个 ModuleConfig 管整个 module 的所有端点。前人漏了它,全项目 cloud 持久化(Shop/LoginReward/Base/Clan...)从没真工作过、全靠 fallback,没人发现。加这一个类,所有端点的 CloudSave 一起活。

**坑B — CloudSave 写 value 必须用 JSON `string`,不能用 `JsonElement`。** `new SetItemBody(key, JsonHelper.Serialize(obj))`(string,对齐能工作的 `ShopEndpoints`)。用 `SerializeToElement(obj)`(JsonElement)写进去**读不回**——下次请求 `Deserialize` 失败→空对象→字段全丢(表现:create 成功但下一次读 player state 是空、ClanId 没了)。

**怎么确认真工作(别被假成功骗,这是部署后验证的核心):**
- **必须另起一次请求读回**。create/save 的返回值是**内存**序列化,不证明写进了 CloudSave。要 create 后用**另一个端点调用**去 read,确认读到刚写的字段。
- 现成诊断端点:调 `GetLoginRewardState`,它 `Error` 字段里有 `api?{_gameApiClient==null} cs?{...}` 诊断(前人留的);`api?True` = IGameApiClient 没注册。
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
- 推送/跨端点调用:`new NotificationEndpoints(_gameApiClient, NullLoggerFactory...)` 直接 new(无 DI 也能手动构)。

### 2) 模型 `Models/<Domain>Models.cs`
请求/响应 DTO + 服务端镜像的数据类。

### 3) 客户端 wrapper `CloudCodeManager.cs`
```csharp
#if UNITY_SERVICES_CLOUDCODE
    var resp = await UnityCloudCode.Instance.CallModuleEndpointAsync<CompleteRaidResponse>(
        MODULE_NAME, FUNC_COMPLETE_RAID, args);
#endif
    // 任何分支失败/离线 → 走本地 fallback(模拟结果),保证不卡 UX
```
- response 内部类字段名**必须 camelCase 精确匹配服务端 JSON 序列化出来的字段**(实战 response 类全用 `success/goldStolen/stolenCore...`)。对不上 = 字段静默为默认值。
- 每个新端点:加 `FUNC_*` 常量 + wrapper 方法 + `[Serializable] private class XxxResponse`。

---

## 第二步:两个会咬人的硬坑(实战踩过)

1. **客户端缺 wrapper 方法 → 卡死整个 Unity 编译**。客户端别处(如 ClanService)调了 `cloudCode.FooAsync()` 但 CloudCodeManager 没这方法 → CS1061 → 整个项目编译红 → Play 进不去。**改服务端前先 `check_compile_errors`**,有这种残留先补齐 wrapper(可先写本地 fallback 占位)。

2. **客户端/服务端 model 字段必须全对齐**。服务端 `LoadBaseDataAsync → mutate → SaveBaseDataAsync` 是**整对象 round-trip**。服务端 model 缺了客户端 `PlayerBaseData` 的某个字段(如 `OwnedCores`/`DefenseLog`/`ProductionSlots`),反序列化丢字段 → save 回去时**静默清空玩家数据**。加端点前先比对两边 model,服务端要镜像客户端**每一个**字段。

---

## 第三步:编译验证(部署前必过)

```bash
cd CloudCode/src
dotnet build ExtractionCloudCode.sln --configuration Release
```
看到 `Build succeeded.` 才继续(warning CS8618 nullable 一堆是既有噪音,忽略;只看 error)。输出很长,grep `error|Build succeeded|FAILED`。

---

## 第四步:部署(`ugs deploy .` 让 ugs 自己编译,**别手动 zip .ccm**)

**🚫 红线(勾哥 2026-06-13):手动部署一律只到 `development`,绝不 `-e production`。** 客户端 Boot `_environment: development`,玩家/测试连 dev——手动只需部 dev。**prod 由 build job 迁移,不手动碰**(误部 prod = 白部 + 污染发布环境 + 留 stray);误部到 prod 的残留也别手动 delete prod,留给 build job,要破例先问勾哥。详见记忆 `cloud-deploy-dev-only`。

凭据:全局 `ugs` CLI 已认证(`ugs env list --json` 能列出环境就行;project-id `ugs config get project-id`)。Unity 内 `Deploy/Cloud Code` 窗口(`CloudCodeDeployWindow.cs`)用 EditorPrefs 凭据 `CloudCode_ProjectId/ServiceKeyId/ServiceSecretKey`,是另一条路。

**正路 —— 目录形式,让 ugs 读 `.ccmr` 编译 `.sln` 生成正确 `.ccm`**:
```powershell
cd CloudCode/src
ugs deploy . -e development --json    # Result 里 path 是 .sln 才对
```

**部署的坑(全踩过,血泪)**:
- **`ugs deploy .` 的 `"Up to date"` 状态不可信**——它有本地缓存,删了远端 module 它还说 up-to-date。**用 module DateModified 核实**:`ugs cloud-code modules list -e development --json` 看时间戳是不是刚刚(对比 `(Get-Date).ToUniversalTime()`)。这是唯一可信的"部上了"信号。
- **src 里别留手动 zip 的 `ExtractionCloudCode.ccm`**——它会和 ugs 编译产物冲突报 `was found duplicated`。删掉,让 ugs 自己生成。
- 改了代码 `ugs deploy .` 仍 `"Up to date"` → 删 temp 缓存 `Remove-Item "$env:TEMP\ExtractionCloudCode" -Recurse -Force`;还不行就**强制**:`ugs cloud-code modules delete ExtractionCloudCode -e development` 再 `ugs deploy .`(delete 后 DateModified 必然刷新 = 真部署了)。
- `ugs deploy <.ccmr文件>`(直接指文件)Result 空、不生效——必须**目录**形式 `ugs deploy .`。
- 手动 `publish → zip .ccm → ugs deploy <.ccm文件>` 这条**老路能让 DateModified 刷新但缺正确 manifest/会留冲突 .ccm**,已弃用——除非 `ugs deploy .` 彻底跑不通才回退。`dotnet build -c Release` 仍可单独用来验证编译(不部署)。

---

## 第五步:部署后验证(部署成功 ≠ 端点真工作)

**最大陷阱:cloud 端点「假成功」**——返回 success、看到数据,但可能是 try-catch 后的空默认或客户端 fallback(见血泪前提)。必须验证**服务端真读写了 CloudSave**:
- **另起一次请求读回**:create/save 后用**另一个端点调用**去 read,确认读到刚写的字段。create 的返回值是内存序列化,不算。**实战:CREATE 返回 clan 数据 ✅ 但紧接 DONATE 报 "Not in a clan" —— 就是坑B(写进去读不回)被读回验证暴露的。**
- **验证 server-authoritative 副作用真发生**:donate 后看 GOLD 真的被**服务端** Economy 扣了(不是客户端扣)、fund 真加了。
- 端点写死一个可识别特征字符串,进游戏看到它 = 新代码在跑(不是旧版/fallback)。

**MCP(Coplay)驱动 play 验证 cloud 的坑**:
- play 必须从 **Boot** 起,否则 services 全 null。Coplay `play_game` 不保证从 active scene 起——先 `EditorSceneManager.playModeStartScene = AssetDatabase.LoadAssetAtPath<SceneAsset>("Assets/Scenes/Meta/Boot.unity")` 再 `play_game`;写个一次性脚本查 `SceneManager.GetActiveScene().name` + `GameObject.Find("ServiceRoot")` 确认真从 Boot 起来了(`activeScene=HomeScreen` + `ServiceRoot=null` = 没从 Boot 起)。
- **domain reload 会杀掉 play session 的 services**(跑外部命令让 Unity 失焦 / asset refresh 都可能触发,ClanService 突然变 NULL)。别分多次 `execute_script` 慢慢测——用**一个自等待脚本**一口气跑完:`for(int i=0;i<50;i++){ svc=ClanService.Instance; if(svc!=null&&svc.IsReady) break; await Task.Delay(400);}` 然后顺着 create→donate→leave,在一个稳定窗口内做完。
- 完整 Play 验证纪律见 `playmode-verify-iterate`。

---

## 第六步:收尾

- 改了端点 → 更新 `CloudCode/README.md` 对应段落(参数/返回/行为)。
- `.ccm` 是构建产物,别纠结它的 git 状态;手动 zip 出来的那个该删(见第四步,会和 ugs 编译冲突)。
- 红线提醒:**不主动 commit/push**,除非勾哥明说。

---

## 速查表

| 要做的 | 命令/位置 |
|---|---|
| **IGameApiClient 注册** | `ModuleConfig:ICloudCodeSetup` → `config.Dependencies.AddSingleton<IGameApiClient>(GameApiClient.Create())`(没它全端点 null) |
| **CloudSave 写** | `new SetItemBody(key, JsonHelper.Serialize(obj))`(string,**别** `SerializeToElement` JsonElement) |
| **🚫 数据安全红线** | 改 Cloud Save 端点绝不能丢玩家数据:model 字段与客户端全对齐(round-trip 缺字段=静默清空)、改结构向后兼容、写前自问会不会盖掉没加载的字段。备份/snapshot 回滚见记忆 `server-data-safety`,建前先对齐方案 |
| 编译服务端 | `cd CloudCode/src && dotnet build ExtractionCloudCode.sln -c Release` |
| 客户端编译 | Coplay `check_compile_errors` + grep logs `error CS` |
| 部署 | `cd CloudCode/src && ugs deploy . -e development`(先删 src 里手动 zip 的 .ccm) |
| 强制重部署 | `ugs cloud-code modules delete ExtractionCloudCode -e development` 再 `ugs deploy .` |
| **核实部上了** | `ugs cloud-code modules list -e development --json` 看 DateModified(**别信 "Up to date"**) |
| 验证真工作 | **另起请求读回**写的字段 / 调 `GetLoginRewardState` 读 Error 诊断(`api?True`=没注册) |
| MCP play 验证 | `EditorSceneManager.playModeStartScene=Boot` + 自等待脚本一口气跑(domain reload 杀 services) |
| 架构怎么设计 | 读 `../server-service-pattern.md` |
