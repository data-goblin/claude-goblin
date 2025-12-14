#region Imports
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional
#endregion

#region Constants
# Valid sound name pattern: alphanumeric, spaces, hyphens, underscores only
VALID_SOUND_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9\s_-]+$')
#endregion


#region Functions


def open_file(file_path: Path) -> None:
    """
    Open a file with the default application (cross-platform).

    Args:
        file_path: Path to the file to open
    """
    system = platform.system()
    try:
        if system == "Darwin":  # macOS
            subprocess.run(["open", str(file_path)], check=False)
        elif system == "Windows":
            subprocess.run(["start", str(file_path)], shell=True, check=False)
        else:  # Linux and others
            subprocess.run(["xdg-open", str(file_path)], check=False)
    except Exception:
        pass  # Silently fail if opening doesn't work


def get_sound_command(sound_name: str) -> Optional[str]:
    """
    Get the command to play a sound (cross-platform).

    Args:
        sound_name: Name of the sound file (without extension).
                    Must contain only alphanumeric characters, spaces, hyphens, underscores.

    Returns:
        Command string to play the sound, or None if:
        - Sound name contains invalid characters (security)
        - Platform is not supported
        - Sound file does not exist (Windows only)
    """
    # Security: Validate sound name to prevent command injection
    if not sound_name or not VALID_SOUND_NAME_PATTERN.match(sound_name):
        return None

    system = platform.system()

    if system == "Darwin":  # macOS
        sound_path = Path(f"/System/Library/Sounds/{sound_name}.aiff")
        if not sound_path.exists():
            return None
        return f"afplay /System/Library/Sounds/{sound_name}.aiff &"

    elif system == "Windows":
        # Map sound names to Windows Media files
        windows_sounds = {
            "Windows Notify": "Windows Notify System Generic.wav",
            "Windows Ding": "Windows Ding.wav",
            "chimes": "chimes.wav",
            "chord": "chord.wav",
            "notify": "notify.wav",
            "tada": "tada.wav",
            "Windows Background": "Windows Background.wav",
        }
        # Only allow mapped sound names on Windows (no arbitrary file access)
        if sound_name not in windows_sounds:
            return None
        sound_file = windows_sounds[sound_name]

        # Validate sound file exists
        sound_path = Path(f"C:\\Windows\\Media\\{sound_file}")
        if not sound_path.exists():
            return None

        # Use Start-Process to run async, -WindowStyle Hidden to suppress window
        return f'powershell -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath powershell -ArgumentList \'-c\',\'(New-Object Media.SoundPlayer \\\"C:\\Windows\\Media\\{sound_file}\\\").PlaySync()\'"'

    else:  # Linux
        # Try to use paplay (PulseAudio) or aplay (ALSA)
        # Most Linux systems have one of these
        return f"(paplay /usr/share/sounds/freedesktop/stereo/{sound_name}.oga 2>/dev/null || aplay /usr/share/sounds/alsa/{sound_name}.wav 2>/dev/null) &"


#endregion
