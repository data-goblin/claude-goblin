# 004: Dynamic Model Cost Tracking

## Summary
Fix Opus and other model cost tracking by maintaining an up-to-date pricing file that can be automatically updated via scraping Anthropic's pricing page.

## Problem
- Opus 4.5 and newer models may have incorrect or missing pricing
- Hardcoded prices become stale as Anthropic updates pricing
- Manual updates are error-prone

## Solution
Create a static markdown/JSON file with model pricing that can be:
1. Manually edited
2. Automatically updated via a scraper script

## Implementation

### Pricing File Format
`data/model_pricing.json`:
```json
{
  "last_updated": "2025-12-14",
  "source": "https://www.anthropic.com/pricing",
  "models": {
    "claude-opus-4-5-20251101": {
      "input_per_million": 15.00,
      "output_per_million": 75.00,
      "cache_write_per_million": 18.75,
      "cache_read_per_million": 1.50
    },
    "claude-sonnet-4-20250514": {
      "input_per_million": 3.00,
      "output_per_million": 15.00
    }
  }
}
```

### Scraper Script
`scripts/update_pricing.py`:
- Fetches Anthropic pricing page
- Parses pricing table
- Updates `model_pricing.json`
- Can be run manually or via cron/scheduled task

### Integration
- Load pricing from JSON file at startup
- Fall back to hardcoded defaults if file missing
- Log warning for unknown models
- Calculate costs using loaded pricing

### Cron Setup (Optional)
```bash
# Daily update at midnight
0 0 * * * cd /path/to/claude-goblin && python scripts/update_pricing.py
```

## Tasks
- [ ] Create model_pricing.json with current known prices
- [ ] Update cost calculation to use JSON file
- [ ] Create pricing scraper script
- [ ] Add fallback to hardcoded prices
- [ ] Document manual and automated update methods
- [ ] Add `ccg update pricing` command
