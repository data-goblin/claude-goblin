# 005: CI/CD Pipeline

## Summary
Implement comprehensive CI/CD with automated testing, PyPI publishing, and GitHub release management.

**Note:** This is a Ways of Working (WoW) enhancement - do not include in user-facing release notes.

## Implementation

### CI (Every Push/PR)
`.github/workflows/ci.yml`:
- Run on: push to any branch, PRs to master
- Matrix: Python 3.10, 3.11, 3.12, 3.13
- Platforms: ubuntu-latest, macos-latest, windows-latest
- Steps:
  1. Checkout
  2. Setup Python + uv
  3. Install dependencies
  4. Run linting (ruff)
  5. Run type checking (mypy)
  6. Run tests (pytest)
  7. Check formatting (ruff format --check)

### CD (Master Only)
`.github/workflows/release.yml`:
- Trigger: Push to master with version tag (v*)
- Steps:
  1. Build wheel and sdist
  2. Publish to PyPI (trusted publisher)
  3. Create GitHub Release
  4. Generate release notes from CHANGELOG.md
  5. Upload artifacts to release

### Version Management
- Version in `pyproject.toml` is source of truth
- Tag format: `v0.2.0`
- CHANGELOG.md follows Keep a Changelog format

### Secrets Required
- `PYPI_API_TOKEN` (or use trusted publisher)

## Workflow Files

### ci.yml
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        python: ["3.10", "3.11", "3.12", "3.13"]
        os: [ubuntu-latest, macos-latest, windows-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - run: uv sync
      - run: uv run ruff check
      - run: uv run pytest
```

## Tasks
- [ ] Create .github/workflows/ci.yml
- [ ] Create .github/workflows/release.yml
- [ ] Configure PyPI trusted publisher
- [ ] Add ruff configuration
- [ ] Add pytest configuration
- [ ] Test CI on feature branch
- [ ] Document release process
