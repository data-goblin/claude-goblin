# 010: Cross-Device Usage Sync

## Summary
Enable usage data synchronization across multiple devices via various backends: OneLake, Syncthing, OneDrive, or MotherDuck.

**Important:** Only aggregate data is synced - no sensitive conversation history.

## Sync Options

### 1. OneLake (Microsoft Fabric)
- Write Parquet files to OneLake
- Notebook transforms to Delta tables
- DirectLake semantic model for Power BI
- Best for: Enterprise users with Fabric

### 2. DuckDB + Syncthing
- Local DuckDB database
- Syncthing for P2P sync
- Best for: Privacy-focused users

### 3. DuckDB + OneDrive
- Local DuckDB in OneDrive folder
- Automatic cloud sync
- Best for: Personal Microsoft 365 users

### 4. MotherDuck
- Cloud-native DuckDB
- Built-in sync and sharing
- Best for: Simplicity

## Data Schema (Aggregate Only)
```sql
CREATE TABLE daily_usage (
    device_id TEXT,
    date DATE,
    total_tokens BIGINT,
    input_tokens BIGINT,
    output_tokens BIGINT,
    cache_read_tokens BIGINT,
    cache_write_tokens BIGINT,
    session_count INTEGER,
    prompt_count INTEGER,
    response_count INTEGER,
    -- NO conversation content, session IDs, or file paths
    PRIMARY KEY (device_id, date)
);
```

## Interactive Setup
```
+------------------------------------------+
|     Cross-Device Sync Setup              |
+------------------------------------------+
| Select sync method:                      |
|                                          |
| [1] OneLake (Microsoft Fabric)           |
|     - Requires Fabric workspace          |
|     - Creates Delta tables + model       |
|                                          |
| [2] DuckDB + Syncthing                   |
|     - P2P sync, no cloud                 |
|     - Requires Syncthing installed       |
|                                          |
| [3] DuckDB + OneDrive                    |
|     - Uses OneDrive folder               |
|     - Automatic cloud backup             |
|                                          |
| [4] MotherDuck                           |
|     - Cloud DuckDB                       |
|     - Requires MotherDuck account        |
|                                          |
| [5] Skip (local only)                    |
+------------------------------------------+
```

## Implementation

### OneLake Flow
1. User provides workspace connection
2. Create Lakehouse if not exists
3. Write daily Parquet files
4. Notebook creates Delta table
5. Script generates DirectLake model

### DuckDB Flow
1. Create shared DuckDB file
2. Configure sync folder
3. Merge data from multiple devices
4. Handle conflicts (latest wins per device+date)

## Tasks
- [ ] Design aggregate-only data schema
- [ ] Implement OneLake writer
- [ ] Create Fabric notebook template
- [ ] Create DirectLake model generator
- [ ] Implement DuckDB sync logic
- [ ] Implement Syncthing configuration
- [ ] Implement OneDrive folder detection
- [ ] Implement MotherDuck integration
- [ ] Create interactive setup wizard
- [ ] Add device ID generation
- [ ] Document each sync option
