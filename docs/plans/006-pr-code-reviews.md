# 006: Automated PR Code Reviews

## Summary
Set up automated code reviews on PRs using multiple AI models: GitHub Copilot (GPT), Claude (Opus 4.5), and Gemini/Jules.

**Note:** This is a Ways of Working (WoW) enhancement - do not include in user-facing release notes.

## Implementation

### GitHub Copilot Code Review
- Native GitHub feature
- Enable in repository settings
- Automatically reviews PRs

### Claude Code Review
Use Claude API via GitHub Action:
```yaml
- name: Claude Review
  uses: anthropics/claude-code-action@v1  # or custom action
  with:
    model: claude-opus-4-5-20251101
    prompt: "Review this PR for code quality, security, and best practices"
```

### Gemini/Jules Code Review
- Google Jules for code review (if available)
- Or Gemini API via custom action
- Focus on different aspects than Claude

### Review Workflow
1. PR opened/updated triggers workflow
2. Each AI reviews in parallel
3. Comments posted as review comments
4. Summary posted as PR comment

### Configuration
`.github/claude-review.yml`:
```yaml
review:
  enabled: true
  models:
    - copilot  # GitHub native
    - claude   # Anthropic
    - gemini   # Google
  focus_areas:
    - security
    - performance
    - code_style
    - test_coverage
```

## Secrets Required
- `ANTHROPIC_API_KEY`
- `GOOGLE_API_KEY`
- GitHub Copilot (org setting)

## Tasks
- [ ] Enable GitHub Copilot code review
- [ ] Create Claude review GitHub Action
- [ ] Create Gemini review GitHub Action
- [ ] Configure review triggers
- [ ] Test on sample PR
- [ ] Document review process
