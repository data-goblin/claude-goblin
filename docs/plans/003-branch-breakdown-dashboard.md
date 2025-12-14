# 003: Branch Breakdown in Dashboard

## Summary
Add git branch tracking and breakdown to the dashboard, allowing users to see usage by branch in addition to by project.

## Problem
Users working on multiple branches want to understand token usage per feature branch, not just per project folder.

## Implementation

### Data Collection
The JSONL files already contain `git_branch` field (when available). Need to:
1. Ensure we're parsing and storing `git_branch`
2. Add branch to aggregation groupings

### Database Changes
```sql
-- Add branch column if not exists
ALTER TABLE usage_records ADD COLUMN git_branch TEXT;

-- New aggregation view
CREATE VIEW branch_stats AS
SELECT
    folder,
    git_branch,
    SUM(input_tokens + output_tokens) as total_tokens,
    COUNT(DISTINCT session_id) as sessions
FROM usage_records
GROUP BY folder, git_branch;
```

### Dashboard Changes
- Add "By Branch" section below "By Project"
- Show top N branches by token usage
- Format: `project/branch: tokens (sessions)`
- Toggle between project-only and project+branch view

### TUI Layout
```
+------------------+------------------+
|   By Project     |    By Branch     |
+------------------+------------------+
| project-a: 1.2M  | main: 800K       |
| project-b: 500K  | feature/x: 400K  |
| ...              | fix/bug: 200K    |
+------------------+------------------+
```

## Tasks
- [ ] Verify git_branch is being parsed from JSONL
- [ ] Add git_branch to database schema
- [ ] Create branch aggregation queries
- [ ] Add branch section to dashboard TUI
- [ ] Add `--by-branch` flag for branch-focused view
- [ ] Update stats command with branch breakdown
