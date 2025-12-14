---
description: Review current changes for issues and improvements
arguments:
  - name: scope
    description: What to review (staged, unstaged, all)
    default: staged
---

# Code Review

Review the current changes and provide feedback.

## Scope: $ARGUMENTS.scope

Based on the scope, analyze the appropriate changes:
- **staged**: Review `git diff --cached`
- **unstaged**: Review `git diff`
- **all**: Review both staged and unstaged changes

## Review Checklist

For each changed file, check:

### Code Quality
- [ ] Code follows project conventions and style
- [ ] No obvious bugs or logic errors
- [ ] Error handling is appropriate
- [ ] No hardcoded values that should be configurable

### Security
- [ ] No secrets or credentials committed
- [ ] No SQL injection, XSS, or other OWASP vulnerabilities
- [ ] Input validation where needed
- [ ] Safe handling of user data

### Performance
- [ ] No unnecessary loops or redundant operations
- [ ] Appropriate data structures used
- [ ] No obvious memory leaks

### Maintainability
- [ ] Code is readable and self-documenting
- [ ] Complex logic has comments
- [ ] Functions have single responsibilities
- [ ] No dead code or unused imports

## Output Format

Provide feedback in this structure:

```
## Summary
Brief overview of changes

## Issues Found
- [SEVERITY] file:line - Description

## Suggestions
- file:line - Improvement idea

## Approved
Yes/No with reasoning
```

Severity levels: CRITICAL, HIGH, MEDIUM, LOW, INFO
