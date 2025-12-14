---
description: Run tests and analyze results
arguments:
  - name: path
    description: Specific test file or directory to run
    required: false
  - name: verbose
    description: Show verbose output
    default: "false"
---

# Run Tests

Execute the test suite and analyze results.

## Test Execution

${{#if ARGUMENTS.path}}
Run specific tests: `pytest $ARGUMENTS.path ${{#if ARGUMENTS.verbose == "true"}}-v${{/if}}`
${{else}}
Run full test suite: `pytest ${{#if ARGUMENTS.verbose == "true"}}-v${{/if}}`
${{/if}}

## Analysis Steps

1. **Run the tests** with appropriate flags
2. **Capture output** including any failures
3. **Analyze failures** if any occur

## For Failures

When tests fail:

1. **Identify the failure**
   - Which test failed
   - What was expected vs actual
   - Stack trace analysis

2. **Find the cause**
   - Is it a test bug or code bug?
   - What changed recently?
   - Check related code

3. **Suggest fixes**
   - If test bug: how to fix the test
   - If code bug: how to fix the code
   - Provide code snippets

## Output Format

```
## Test Results

Ran X tests in Y seconds
Passed: N | Failed: N | Skipped: N

${{#if failures}}
## Failures

### test_name (file:line)
**Expected:** ...
**Actual:** ...
**Cause:** Brief analysis
**Fix:** Suggested solution
${{/if}}

## Coverage (if available)
Overall: X%
Uncovered areas: ...
```

## Additional Commands

If helpful, also run:
- `pytest --collect-only` - List available tests
- `pytest -x` - Stop on first failure
- `pytest --lf` - Run last failed tests
- `pytest -k "pattern"` - Run matching tests
