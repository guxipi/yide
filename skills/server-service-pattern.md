# Server-Integrated Service Pattern

This skill documents the standard pattern for creating Unity services that integrate with UGS CloudCode for server-validated operations with offline support.

## Overview

When building game services that require server validation (e.g., inventory, economy, progression), use this pattern to:
- Maintain server authority for critical operations (currency, item deletion)
- Provide optimistic updates for UX-critical operations (equipment changes)
- Support offline play with queued sync on reconnect
- Handle conflicts gracefully with rollback capabilities

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
| `[Domain]Endpoints.cs` | `CloudCode/ExtractionCloudCode/Endpoints/` | Server endpoints |
| `[Domain]Models.cs` | `CloudCode/ExtractionCloudCode/Models/` | Request/response types |
| `CloudCodeManager.cs` | Modify | Add wrapper methods |
| `BootSequencer.cs` | Modify | Add sync phase |
| `GameEvents.cs` | Modify | Add service events |
| `PlayerDataSchema.cs` | Modify | Add version tracking fields |

## Example: PersistentInventoryService

Reference implementation:
- `Assets/Scripts/Core/Services/Items/PersistentInventoryService.cs`
- `Assets/Scripts/Core/Services/Items/InventoryOperationQueue.cs`
- `CloudCode/ExtractionCloudCode/Endpoints/InventoryEndpoints.cs`
- `CloudCode/ExtractionCloudCode/Models/InventoryModels.cs`
