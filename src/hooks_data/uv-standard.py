#!/usr/bin/env python3
"""
PreToolUse hook that enforces uv usage over pip/pip3/python -m pip.

This hook intercepts Bash commands and blocks pip usage, suggesting
uv equivalents instead.

Exit codes:
  0 - Allow command to proceed
  1 - Error (will abort with error message)
  2 - Block with feedback to Claude (suggests alternative command)

Author: Claude Code Goblin
Inspired by: awesome-hooks/bundler-standard.ts by boxabirds
"""

#region Imports
import sys
import json
import re
#endregion


#region Functions


def pre_tool_use(event: dict) -> None:
    """
    PreToolUse hook that enforces uv usage over pip.

    Args:
        event: Hook event containing tool_name and tool_input

    Purpose:
        Intercepts Bash commands and blocks pip usage, suggesting uv equivalents.

    Outputs:
        Exits with code 2 if pip is detected (blocks with feedback to Claude).
        Exits with code 0 otherwise (allows command to proceed).

    Failure modes:
        - Invalid JSON input: exits with code 1
        - Non-Bash tool: exits with code 0 (allows to proceed)
    """
    # Only check Bash tool calls
    if event.get('tool_name') != 'Bash':
        return

    command = event.get('tool_input', {}).get('command', '')

    # Skip git commands - we don't want to interfere
    if command.startswith('git '):
        return

    # Skip comments
    if command.strip().startswith('#'):
        return

    # Check for pip, pip3, or python -m pip usage
    # Only match when pip is actually being executed as a command:
    # - At the start of the command
    # - After shell operators: &&, ||, ;, |, etc.
    # - After common command prefixes: sudo, time, env, nice, etc.
    # Not inside quotes
    pip_pattern = r'(?:^|[;&|]\s*|(?:sudo|time|env|nice|nohup)\s+)(pip3?|python3?\s+-m\s+pip)(?:\s+|$)'
    match = re.search(pip_pattern, command)

    # Additional check: if pip appears inside quotes, don't match
    if match:
        # Simple heuristic: count quotes before the match position
        # If odd number of quotes, we're inside a quoted string
        text_before_match = command[:match.start()]
        single_quotes = text_before_match.count("'")
        double_quotes = text_before_match.count('"')

        # If inside quotes, skip
        if single_quotes % 2 == 1 or double_quotes % 2 == 1:
            return

    if match:
        package_manager = match.group(1)

        # Commands that map directly to uv (same subcommand)
        direct_mappings = {
            'install', 'uninstall', 'list', 'show', 'freeze',
            'check', 'search', 'wheel', 'hash', 'download'
        }

        # Special command mappings for uv
        special_mappings = {
            'install -e': 'pip install -e',  # Editable installs work the same
            'install -r': 'pip install -r',  # Requirements files
            'freeze >': 'pip freeze >',      # Freeze to requirements
            'list --outdated': 'pip list --outdated',
            'install --upgrade': 'pip install --upgrade',
        }

        # Parse the command after the package manager
        command_after_pm = command[match.end():].strip()

        # Try to determine the uv equivalent
        uv_equivalent = None

        # Check for special multi-word patterns first
        for pattern, uv_cmd in special_mappings.items():
            if command_after_pm.startswith(pattern):
                uv_equivalent = f"uv {uv_cmd} {command_after_pm[len(pattern):]}"
                break

        if not uv_equivalent:
            # Extract the subcommand
            words = command_after_pm.split()
            subcommand = words[0] if words else ''

            if subcommand in direct_mappings:
                # Direct mapping - replace pip with uv pip
                uv_equivalent = f"uv pip {command_after_pm}"
            elif not subcommand:
                # Just pip alone
                uv_equivalent = "uv pip"
            else:
                # Unknown command - suggest uv pip as fallback
                uv_equivalent = f"uv pip {command_after_pm}"

        # Print error to stderr
        print(f"❌ Blocked: {package_manager} is not recommended in this project.", file=sys.stderr)
        print(f"✅ Please use uv instead: {uv_equivalent.strip()}", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"Run this command instead: {uv_equivalent.strip()}", file=sys.stderr)
        print(f"", file=sys.stderr)
        print(f"Why uv?", file=sys.stderr)
        print(f"  • 10-100x faster than pip", file=sys.stderr)
        print(f"  • Better dependency resolution", file=sys.stderr)
        print(f"  • Modern Python package installer by Astral (creators of ruff)", file=sys.stderr)

        # Exit code 2 = blocked with feedback to Claude
        sys.exit(2)


#endregion


#region Main


def main() -> None:
    """
    Main entry point - reads JSON from stdin and processes the hook event.

    Purpose:
        Reads hook event data from stdin, parses it, and calls pre_tool_use.

    Outputs:
        Calls pre_tool_use which may exit with code 0, 1, or 2.

    Failure modes:
        - Invalid JSON: exits with code 1
        - Missing required fields: handled gracefully (allows to proceed)
    """
    try:
        # Read event data from stdin
        event_data = json.load(sys.stdin)
        pre_tool_use(event_data)
    except json.JSONDecodeError as e:
        print(f"Error parsing event data: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()


#endregion
