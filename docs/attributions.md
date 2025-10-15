# Attributions

This project includes code, concepts, and resources from various open source projects and contributors. We are grateful for their work and contributions to the community.

## awesome-hooks

**Author:** boxabirds
**Repository:** https://github.com/boxabirds/awesome-hooks
**License:** Apache-2.0

The following hooks are included from the awesome-hooks repository:
- `bundler-standard.ts` - Enforces Bun usage instead of npm/pnpm/yarn
- `file-name-consistency.sh` - Ensures consistent file naming conventions using AI pattern analysis

These hooks are provided as-is from the original repository with no modifications, except for being packaged with this tool for easier installation.

### Description from awesome-hooks

> A collection of powerful Git hooks for maintaining project consistency and enforcing best practices.

The awesome-hooks repository provides PreToolUse hooks for Claude Code that help enforce development standards and best practices across projects.

## uv-standard.py

**Inspiration:** bundler-standard.ts from awesome-hooks
**Author:** Claude Code Goblin
**License:** MIT (same as this project)

The `uv-standard.py` hook is inspired by the `bundler-standard.ts` hook from awesome-hooks, but reimplemented in Python for enforcing uv usage instead of pip/pip3. This hook was created specifically for this project to provide Python package management enforcement similar to the JavaScript bundler enforcement provided by bundler-standard.

## Other Dependencies

### Python Libraries

- [Rich](https://github.com/Textualize/rich) - Terminal UI framework (MIT License)
- [Pillow](https://python-pillow.org/) - Image processing library (HPND License)
- [CairoSVG](https://cairosvg.org/) - SVG to PNG conversion (LGPL-3.0)
- [Typer](https://github.com/tiangolo/typer) - CLI framework (MIT License)
- [rumps](https://github.com/jaredks/rumps) - macOS menu bar app framework (BSD-3-Clause License)

### Build Tools

- [uv](https://github.com/astral-sh/uv) - Fast Python package installer by Astral

---

If you believe your work should be attributed here or if there are any errors in attribution, please open an issue at https://github.com/data-goblin/claude-goblin/issues.
