# Changelog Updater

Update CHANGELOG.md following the Keep a Changelog format.

## When to Use

Activate this skill when:
- User asks to "update the changelog"
- User is preparing a release
- User has completed a feature or fix
- User asks to "document these changes"

## Changelog Format

Follow [Keep a Changelog](https://keepachangelog.com/) specification:

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New features

### Changed
- Changes to existing functionality

### Deprecated
- Features that will be removed

### Removed
- Features that were removed

### Fixed
- Bug fixes

### Security
- Security-related changes

## [1.0.0] - 2025-01-15

### Added
- Initial release features
```

## Instructions

When updating the changelog:

1. **Find or create the Unreleased section**
   - Always add changes under `[Unreleased]` first
   - Create the section if it doesn't exist

2. **Choose the correct category**
   - Added: New features or capabilities
   - Changed: Changes to existing features
   - Deprecated: Features marked for removal
   - Removed: Features that were deleted
   - Fixed: Bug fixes
   - Security: Security-related fixes

3. **Write clear entries**
   - Use imperative mood: "Add" not "Added"
   - Be specific but concise
   - Include issue/PR references if available
   - Group related changes together

4. **For releases**
   - Change `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`
   - Add new `[Unreleased]` section above
   - Update version links at bottom if present

## Example Entry

```markdown
## [Unreleased]

### Added
- Activity heatmap in dashboard showing daily token usage
- Branch breakdown visualization in usage stats
- Dynamic model pricing loaded from JSON configuration
- GitHub Actions CI/CD pipeline for automated testing

### Changed
- Dashboard redesigned with "Warm Data Observatory" aesthetic
- Model pricing now editable via `data/model_pricing.json`

### Fixed
- Incremental parsing now correctly tracks file modifications
- Branch names properly truncated in display
```

## Best Practices

- Update changelog with every meaningful change
- Write for users, not developers
- Don't include internal refactoring unless it affects behavior
- Keep entries brief - link to docs for details
- Use consistent formatting throughout
