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

    Returns:
        Dictionary with keys: session_pct, week_pct, opus_pct,
        session_reset, week_reset, opus_reset, or None if capture failed
    """
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
        session_match = re.search(r'Current session.*?(\d+)%\s+used.*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)
        week_match = re.search(r'Current week \(all models\).*?(\d+)%\s+used.*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)
        opus_match = re.search(r'Current week \(Opus\).*?(\d+)%\s+used.*?Resets\s+(.+?)(?:\n|$)', clean_output, re.DOTALL)

        if session_match and week_match and opus_match:
            return {
                "session_pct": int(session_match.group(1)),
                "week_pct": int(week_match.group(1)),
                "opus_pct": int(opus_match.group(1)),
                "session_reset": session_match.group(2).strip(),
                "week_reset": week_match.group(2).strip(),
                "opus_reset": opus_match.group(2).strip(),
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

    Uses Python's pty module to create a pseudo-terminal for capturing
    TUI output from `claude /usage`, then strips ANSI codes and extracts
    percentage values.

    Args:
        console: Rich console for output
    """
    try:
        limits = capture_limits()

        console.print()

        if limits:
            # Check if it's an error response
            if "error" in limits:
                console.print(f"[yellow]{limits['message']}[/yellow]")
            else:
                console.print(f"[bold]Session:[/bold] [#ff8800]{limits['session_pct']}%[/#ff8800] (resets [not bold cyan]{limits['session_reset']}[/not bold cyan])")
                console.print(f"[bold]Week:[/bold]    [#ff8800]{limits['week_pct']}%[/#ff8800] (resets [not bold cyan]{limits['week_reset']}[/not bold cyan])")
                console.print(f"[bold]Opus:[/bold]    [#ff8800]{limits['opus_pct']}%[/#ff8800] (resets [not bold cyan]{limits['opus_reset']}[/not bold cyan])")
        else:
            console.print("[yellow]Could not parse usage data from 'claude /usage'[/yellow]")

        console.print()

    except FileNotFoundError:
        console.print("[red]Error: 'claude' command not found[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()


#endregion
