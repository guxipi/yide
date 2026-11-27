# Server-Integrated Service Pattern

This skill documents the standard pattern for creating Unity services that integrate with UGS CloudCode for server-validated operations with offline support.

## Overview

When building game services that require server validation (e.g., inventory, economy, progression), use this pattern to:
- Maintain server authority for critical operations (currency, item deletion)
- Provide optimistic updates for UX-critical operations (equipment changes)
- Queue optimistic operations and sync them on reconnect
- Handle conflicts gracefully with rollback capabilities

> **ER 现行规矩以 vault 为准**:`01 - 星际拓荒重构/025_服务器运维手册/AI记忆/现行口径_服务端与发版.md`(「玩家数据安全」「服务端权威和防作弊」两节)。和本文冲突时照它:服务端写入一律 `context.ServiceToken`,客户端不直连写存档 / 货币;背包、任务 / 成就这类以服务端为真源,客户端只发请求和证据;主页 / 基地 / 商店 / 背包断网时全屏转圈挡操作,不做离线排队(下面的 OperationQueue 只适用于已有的乐观路径,新服务别靠它支持离线玩)。部署和验证步骤见 `cloud-code-deploy`。

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Unity Client                          │
├─────────────────────────────────────────────────────────────┤
│  [YourService]                                              │
│    ├── Local state (runtime cache)                          │
│    ├── UnityEvents for UI binding                           │
│    ├── Server-first methods (async, requires online)        │
│    └── Optimistic methods (local + queue for sync)          │
├─────────────────────────────────────────────────────────────┤
│  [OperationQueue]                                           │
│    ├── Persisted to PlayerPrefs                             │
│    ├── Survives app restarts                                │
│    └── Batched sync on reconnect                            │
├─────────────────────────────────────────────────────────────┤
│  [CloudCodeManager]                                         │
│    ├── Wrapper methods for CloudCode calls                  │
│    ├── Online check with network popup                      │
│    └── Response deserialization                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    UGS CloudCode                            │
├─────────────────────────────────────────────────────────────┤
│  [YourEndpoints.cs]                                         │
│    ├── Server-validated operations                          │
│    ├── Version tracking for conflict detection              │
│    └── Cloud Save integration for persistence               │
├─────────────────────────────────────────────────────────────┤
│  [YourModels.cs]                                            │
│    ├── Request/Response DTOs                                │
│    └── Shared data structures                               │
└─────────────────────────────────────────────────────────────┘
```

## Operation Types

### Server-First Operations
Use for operations that MUST be validated:
- Currency transactions (sell, purchase)
- Permanent deletions (discard items)
- Unlocks and progression

```csharp
public async Task<ResultType> OperationAsync(params)
{
    // 1. Check online status (shows popup if offline)
    if (!await EnsureOnlineAsync("Operation Name"))
        return null;

    // 2. Call CloudCode
    var result = await cloudCode.OperationAsync(params);

    // 3. Update local state only on success
    if (result?.Success == true)
    {
        ApplyLocalChanges();
        SaveToPlayerData();
    }

    return result;
}
```

### Optimistic Operations
Use for UX-critical operations that can be rolled back:
- Equipment changes
- UI preferences
- Non-economic state changes

```csharp
public void OperationOptimistic(params)
{
    // 1. Store rollback data
    var previousState = CaptureState();

    // 2. Apply immediately (no await)
    ApplyLocalChanges();

    // 3. Queue for server sync
    _operationQueue.Enqueue(operation);

    // 4. Fire events
    OnOperationComplete?.Invoke();
}
```

## Data Version Tracking

Track server data versions to detect conflicts:

```csharp
// PlayerDataSchema
public long ServiceVersion;        // Server data version
public long LastSyncTimestamp;     // Last sync time

// Service
private long _serverVersion;

// On sync
if (serverVersion > localVersion)
{
    // Accept server data
    ApplyServerState(response);
}
else if (localVersion > serverVersion && hasPendingOps)
{
    // Sync pending operations
    await SyncPendingOperationsAsync();
}
```

## Boot Sequence Integration

Add sync phase to BootSequencer between CloudSaveLoad and EconomySync:

```csharp
public enum BootPhase
{
    // ...
    CloudSaveLoad,
    YourServiceSync,  // New
    EconomySync,
    // ...
}

private async Task<bool> YourServiceSyncAsync()
{
    if (!IsOnline) return false;

    var service = YourService.Instance;
    if (service == null) return true;

    await service.LoadFromPlayerDataAsync();
    return await service.SyncFromServerAsync();
}
```

## GameEvents Integration

Add global events for cross-system communication:

```csharp
// GameEvents.cs
public static readonly UnityEvent OnServiceSynced = new UnityEvent();
public static readonly UnityEvent<string> OnServiceSyncFailed = new UnityEvent<string>();
public static readonly UnityEvent<DataType> OnOperationComplete = new UnityEvent<DataType>();
```

## CloudCode Endpoint Pattern

```csharp
[CloudCodeFunction("OperationName")]
public async Task<ResultType> Operation(IExecutionContext context, params)
{
    // 1. Validate parameters
    if (invalid) return ErrorResult();

    // 2. Load player data
    var playerData = await LoadPlayerDataAsync(context);

    // 3. Validate operation
    if (!CanPerformOperation(playerData))
        return ErrorResult("Reason");

    // 4. Apply changes
    ApplyChanges(playerData);
    playerData.Version++;

    // 5. Save and return
    await SavePlayerDataAsync(context, playerData);
    return SuccessResult();
}
```
- Target player id comes only from `context.PlayerId` or server-side state; every write call passes `context.ServiceToken`.
- Cloud Save values are written as JSON strings (`JsonHelper.Serialize`), and the client calls the endpoint through `CloudCodeManager.CallLenientAsync<T>` (see `cloud-code-deploy`).

## Error Handling

### Network Errors
- Show network popup via CloudCodeManager.EnsureOnlineAsync()
- User can retry or cancel
- Queue operations for later if appropriate

### Conflict Resolution
- Server data is authoritative
- Client state rolls back on conflict
- Fire OnOperationRolledBack event for UI feedback

### Validation Errors
- Return descriptive error messages
- Client shows appropriate UI feedback
- No local state changes on failure

## File Checklist

When implementing a new server-integrated service:

| File | Location | Purpose |
|------|----------|---------|
| `[Service].cs` | `Assets/Scripts/Core/Services/[Domain]/` | Main service with sync methods |
| `[Service]OperationQueue.cs` | Same folder | Offline operation queue |
| `[Domain]Endpoints.cs` | `CloudCode/src/ExtractionCloudCode/Endpoints/` | Server endpoints |
| `[Domain]Models.cs` | `CloudCode/src/ExtractionCloudCode/Models/` | Request/response types |
| `CloudCodeManager.cs` | Modify | Add wrapper methods |
| `BootSequencer.cs` | Modify | Add sync phase |
| `GameEvents.cs` | Modify | Add service events |
| `PlayerDataSchema.cs` | Modify | Add version tracking fields |

## Example: PersistentInventoryService

Reference implementation:
- `Assets/Scripts/Core/Services/Items/PersistentInventoryService.cs`
- `Assets/Scripts/Core/Services/Items/InventoryOperationQueue.cs`
- `CloudCode/src/ExtractionCloudCode/Endpoints/InventoryEndpoints.cs`
- `CloudCode/src/ExtractionCloudCode/Models/InventoryModels.cs`
