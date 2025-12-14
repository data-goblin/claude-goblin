# 001: Incremental JSONL Parsing

## Summary
Only parse JSONL files that have changed since the last database update, dramatically improving performance for users with large history.

## Problem
Currently, every `ccg usage` or `ccg stats` command parses ALL JSONL files (~1.5GB for heavy users), taking 4-5 seconds even when no new data exists.

## Solution
Track file modification times (mtime) in the database and only parse files that have been modified since the last run.

## Implementation

### Database Changes
```sql
CREATE TABLE file_metadata (
    file_path TEXT PRIMARY KEY,
    last_modified_time REAL,  -- Unix timestamp with subsecond precision
    last_parsed_time TEXT,
    record_count INTEGER
);
```

### Logic
1. On startup, get list of all JSONL files
2. Query `file_metadata` for each file's `last_modified_time`
3. Compare with current `os.path.getmtime(file)`
4. Only parse files where mtime has changed or file is new
5. After parsing, update `file_metadata` with new mtime

### Edge Cases
- Deleted files: Mark as inactive, don't delete records (historical data)
- Renamed files: Treat as new file (path is primary key)
- Clock skew: Use file mtime, not current time

## Expected Performance
- First run: Same as current (~4-5s for 1.5GB)
- Subsequent runs with no changes: <0.5s
- Subsequent runs with 1-2 new files: <1s

## Tasks
- [ ] Add `file_metadata` table to schema
- [ ] Implement mtime checking logic
- [ ] Update ingestion to only process changed files
- [ ] Add `--force` flag to bypass incremental check
- [ ] Add tests for incremental parsing
