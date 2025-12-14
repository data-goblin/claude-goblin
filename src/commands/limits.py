#region Imports
import subprocess
import re
import os
import pty
import select
import time
import shutil
from rich.console import Console
#endregion


#region Functions


def _strip_ansi(text: str) -> str:
    """
    Remove ANSI escape codes from text.

    Args:
        text: Text with ANSI codes

    Returns:
        Clean text without ANSI codes
    """
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def capture_limits() -> dict | None:
    """
    Capture usage limits from `claude /usage` without displaying output.

    NOTE: This feature is temporarily disabled due to changes in Claude Code's
    output format. Will be re-enabled in a future release.

    Returns:
        Dictionary with error key indicating feature is disabled
    """
    # Feature temporarily disabled
    return {
        "error": "feature_disabled",
        "message": "Limits tracking temporarily disabled. Run 'claude /usage' directly."
    }

    # --- DISABLED CODE BELOW ---
    # Check if claude CLI is available
    if not shutil.which('claude'):
        return {
            "error": "claude_not_found",
            "message": "Claude Code CLI not found in PATH. Please install Claude Code or ensure 'claude' is available in your PATH."
        }

    try:
        # Create a pseudo-terminal pair
        master, slave = pty.openpty()

        # Start claude /usage with the PTY
        process = subprocess.Popen(
            ['claude', '/usage'],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            close_fds=True
        )

        # Close slave in parent process (child keeps it open)
        os.close(slave)

        # Read output until we see complete data
        output = b''
        start_time = time.time()
        max_wait = 10

        while time.time() - start_time < max_wait:
            # Check if data is available to read
            ready, _, _ = select.select([master], [], [], 0.1)

            if ready:
                try:
                    chunk = os.read(master, 4096)
                    if chunk:
                        output += chunk

                        # Check if we hit trust prompt early - no point waiting
                        if b'Do you trust the files in this folder?' in output:
                            # We got the trust prompt, stop waiting
                            time.sleep(0.5)  # Give it a bit more time to finish rendering
                            break

                        # Check if we have complete data
                        # Look for the usage screen's exit message, not the loading screen's "esc to interrupt"
                        if b'Current week (Opus)' in output and b'Esc to exit' in output:
                            # Wait a tiny bit more to ensure all data is flushed
                            time.sleep(0.2)
                            # Try to read any remaining data
                            try:
                                while True:
                                    ready, _, _ = select.select([master], [], [], 0.05)
                                    if not ready:
                                        break
                                    chunk = os.read(master, 4096)
                                    if chunk:
                                        output += chunk
                            except:
                                pass
                            break
                except OSError:
                    break

        # Send ESC to exit cleanly
        try:
            os.write(master, b'\x1b')
            time.sleep(0.1)
        except:
            pass

        # Clean up
        try:
            process.terminate()
            process.wait(timeout=1)
        except:
            process.kill()

        os.close(master)

        # Decode output
        output_str = output.decode('utf-8', errors='replace')

        # Strip ANSI codes
        clean_output = _strip_ansi(output_str)

        # Check if we hit the trust prompt
        if 'Do you trust the files in this folder?' in clean_output:
            return {
                "error": "trust_prompt",
                "message": "Claude prompted for folder trust. Please run 'claude' in a trusted folder first, or cd to a project directory."
            }

        # Parse for percentages and reset times
        # Note: Reset time might not be shown when usage is 0%
        session_pct_match = re.search(r'Current session.*?(\d+)%\s+used', clean_output, re.DOTALL)
        session_reset_match = re.search(r'Current session.*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)

        week_pct_match = re.search(r'Current week \(all models\).*?(\d+)%\s+used', clean_output, re.DOTALL)
        week_reset_match = re.search(r'Current week \(all models\).*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)

        opus_pct_match = re.search(r'Current week \(Opus\).*?(\d+)%\s+used', clean_output, re.DOTALL)
        opus_reset_match = re.search(r'Current week \(Opus\).*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)

        # If we found at least the percentages, return what we have
        if session_pct_match and week_pct_match and opus_pct_match:
            return {
                "session_pct": int(session_pct_match.group(1)),
                "week_pct": int(week_pct_match.group(1)),
                "opus_pct": int(opus_pct_match.group(1)),
                "session_reset": session_reset_match.group(1).strip() if session_reset_match else "N/A",
                "week_reset": week_reset_match.group(1).strip() if week_reset_match else "N/A",
                "opus_reset": opus_reset_match.group(1).strip() if opus_reset_match else "N/A",
            }

        return None

    except FileNotFoundError:
        # This shouldn't happen since we check above, but handle it gracefully
        return {
            "error": "claude_not_found",
            "message": "Claude Code CLI not found. Please install Claude Code."
        }
    except Exception as e:
        # Silent failure for other errors (network issues, parsing errors, etc.)
        # Returning None allows the app to continue without limits data
        return None


def run(console: Console) -> None:
    """
    Show current usage limits by parsing `claude /usage` output.

    NOTE: This feature is temporarily disabled due to changes in Claude Code's
    output format. Will be re-enabled in a future release.

    Args:
        console: Rich console for output
    """
    console.print()
    console.print("[yellow]Limits tracking is temporarily unavailable.[/yellow]")
    console.print("[dim]Claude Code's /usage output format has changed.[/dim]")
    console.print("[dim]This feature will be restored in a future release.[/dim]")
    console.print()
    console.print("[dim]In the meantime, run 'claude /usage' directly to view your limits.[/dim]")
    console.print()


#endregion
