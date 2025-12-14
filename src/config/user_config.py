#region Imports
import json
import platform
import re
import uuid
from pathlib import Path
from typing import Optional
#endregion


#region Types
VALID_STORAGE_FORMATS = ["sqlite", "duckdb"]
VALID_SYNC_PROVIDERS = ["syncthing", "onedrive", "onelake", "motherduck", "none"]
VALID_DEVICE_TYPES = ["macos", "windows", "linux"]

# Valid device ID pattern: alphanumeric, hyphens, underscores; 1-64 chars
# Used in file paths, so must be filesystem-safe
VALID_DEVICE_ID_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$')

# Valid device name pattern: printable ASCII, 1-128 chars
# More permissive but still safe for display
VALID_DEVICE_NAME_PATTERN = re.compile(r'^[\x20-\x7E]{1,128}$')
#endregion


#region Constants
CONFIG_PATH = Path.home() / ".claude" / "goblin_config.json"
#endregion


#region Functions


def load_config() -> dict:
    """
    Load user configuration from disk.

    Returns:
        Configuration dictionary with user preferences
    """
    if not CONFIG_PATH.exists():
        return get_default_config()

    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return get_default_config()


def save_config(config: dict) -> None:
    """
    Save user configuration to disk.

    Args:
        config: Configuration dictionary to save

    Raises:
        IOError: If config cannot be written
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_default_config() -> dict:
    """
    Get default configuration values.

    Returns:
        Default configuration dictionary
    """
    return {
        "storage_mode": "aggregate",  # "aggregate" or "full"
        "plan_type": "max_20x",  # "pro", "max_5x", or "max_20x"
        "tracking_mode": "both",  # "both", "tokens", or "limits"
        "version": "1.0",
        # Sync configuration
        "storage_format": "sqlite",  # "sqlite" or "duckdb"
        "sync_provider": "none",  # "syncthing", "onedrive", "onelake", "motherduck", "none"
        "device_id": None,  # Auto-generated UUID or Syncthing device ID
        "device_name": None,  # Human-readable device name
        "device_type": None,  # "macos", "windows", "linux"
        "sync_config": {},  # Provider-specific configuration
    }


def get_storage_mode() -> str:
    """
    Get the current storage mode setting.

    Returns:
        Either "aggregate" or "full"
    """
    config = load_config()
    return config.get("storage_mode", "aggregate")


def set_storage_mode(mode: str) -> None:
    """
    Set the storage mode.

    Args:
        mode: Either "aggregate" or "full"

    Raises:
        ValueError: If mode is not valid
    """
    if mode not in ["aggregate", "full"]:
        raise ValueError(f"Invalid storage mode: {mode}. Must be 'aggregate' or 'full'")

    config = load_config()
    config["storage_mode"] = mode
    save_config(config)


def get_plan_type() -> str:
    """
    Get the current Claude Code plan type.

    Returns:
        One of "pro", "max_5x", or "max_20x"
    """
    config = load_config()
    return config.get("plan_type", "max_20x")


def set_plan_type(plan: str) -> None:
    """
    Set the Claude Code plan type.

    Args:
        plan: One of "pro", "max_5x", or "max_20x"

    Raises:
        ValueError: If plan is not valid
    """
    if plan not in ["pro", "max_5x", "max_20x"]:
        raise ValueError(f"Invalid plan type: {plan}. Must be 'pro', 'max_5x', or 'max_20x'")

    config = load_config()
    config["plan_type"] = plan
    save_config(config)


def get_tracking_mode() -> str:
    """
    Get the current tracking mode setting.

    Returns:
        One of "both", "tokens", or "limits"
    """
    config = load_config()
    return config.get("tracking_mode", "both")


def set_tracking_mode(mode: str) -> None:
    """
    Set the tracking mode for data capture and visualization.

    Args:
        mode: One of "both", "tokens", or "limits"

    Raises:
        ValueError: If mode is not valid
    """
    if mode not in ["both", "tokens", "limits"]:
        raise ValueError(f"Invalid tracking mode: {mode}. Must be 'both', 'tokens', or 'limits'")

    config = load_config()
    config["tracking_mode"] = mode
    save_config(config)


#endregion


#region Sync Configuration Functions


def get_device_type() -> str:
    """
    Detect and return the current device type.

    Returns:
        One of "macos", "windows", "linux"
    """
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    return system


def generate_device_id() -> str:
    """
    Generate a unique device identifier.

    Returns:
        UUID string for device identification
    """
    return str(uuid.uuid4())[:8]


def get_storage_format() -> str:
    """
    Get the current storage format setting.

    Returns:
        Either "sqlite" or "duckdb"
    """
    config = load_config()
    return config.get("storage_format", "sqlite")


def set_storage_format(format_type: str) -> None:
    """
    Set the storage format.

    Args:
        format_type: Either "sqlite" or "duckdb"

    Raises:
        ValueError: If format is not valid
    """
    if format_type not in VALID_STORAGE_FORMATS:
        raise ValueError(f"Invalid storage format: {format_type}. Must be one of {VALID_STORAGE_FORMATS}")

    config = load_config()
    config["storage_format"] = format_type
    save_config(config)


def get_sync_provider() -> str:
    """
    Get the current sync provider setting.

    Returns:
        One of "syncthing", "onedrive", "onelake", "motherduck", "none"
    """
    config = load_config()
    return config.get("sync_provider", "none")


def set_sync_provider(provider: str) -> None:
    """
    Set the sync provider.

    Args:
        provider: One of "syncthing", "onedrive", "onelake", "motherduck", "none"

    Raises:
        ValueError: If provider is not valid
    """
    if provider not in VALID_SYNC_PROVIDERS:
        raise ValueError(f"Invalid sync provider: {provider}. Must be one of {VALID_SYNC_PROVIDERS}")

    config = load_config()
    config["sync_provider"] = provider
    save_config(config)


def get_device_id() -> Optional[str]:
    """
    Get the current device identifier.

    Returns:
        Device ID string or None if not set
    """
    config = load_config()
    return config.get("device_id")


def validate_device_id(device_id: str) -> bool:
    """
    Validate that a device ID is safe for use in file paths and database queries.

    Args:
        device_id: Device identifier to validate

    Returns:
        True if valid, False otherwise
    """
    if not device_id:
        return False
    return bool(VALID_DEVICE_ID_PATTERN.match(device_id))


def validate_device_name(device_name: str) -> bool:
    """
    Validate that a device name is safe for display.

    Args:
        device_name: Device name to validate

    Returns:
        True if valid, False otherwise
    """
    if not device_name:
        return False
    return bool(VALID_DEVICE_NAME_PATTERN.match(device_name))


def sanitize_device_id(device_id: str) -> str:
    """
    Sanitize a device ID by removing/replacing invalid characters.

    Args:
        device_id: Device identifier to sanitize

    Returns:
        Sanitized device ID
    """
    if not device_id:
        return generate_device_id()

    # Replace invalid characters with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', device_id)

    # Ensure it starts with alphanumeric
    if sanitized and not sanitized[0].isalnum():
        sanitized = 'x' + sanitized

    # Truncate to max length
    sanitized = sanitized[:64]

    # If empty after sanitization, generate new ID
    if not sanitized or not validate_device_id(sanitized):
        return generate_device_id()

    return sanitized


def set_device_id(device_id: str) -> None:
    """
    Set the device identifier.

    Args:
        device_id: Unique device identifier

    Raises:
        ValueError: If device_id contains invalid characters
    """
    if not validate_device_id(device_id):
        raise ValueError(
            f"Invalid device ID: '{device_id}'. "
            "Must be 1-64 characters, start with alphanumeric, "
            "and contain only letters, numbers, hyphens, and underscores."
        )

    config = load_config()
    config["device_id"] = device_id
    save_config(config)


def get_device_name() -> Optional[str]:
    """
    Get the human-readable device name.

    Returns:
        Device name string or None if not set
    """
    config = load_config()
    return config.get("device_name")


def set_device_name(name: str) -> None:
    """
    Set the human-readable device name.

    Args:
        name: Human-readable device name

    Raises:
        ValueError: If name contains invalid characters
    """
    if not validate_device_name(name):
        raise ValueError(
            f"Invalid device name: '{name}'. "
            "Must be 1-128 printable ASCII characters."
        )

    config = load_config()
    config["device_name"] = name
    save_config(config)


def get_device_type_config() -> Optional[str]:
    """
    Get the stored device type from config.

    Returns:
        Device type string or None if not set
    """
    config = load_config()
    return config.get("device_type")


def set_device_type_config(device_type: str) -> None:
    """
    Set the device type in config.

    Args:
        device_type: One of "macos", "windows", "linux"

    Raises:
        ValueError: If device_type is not valid
    """
    if device_type not in VALID_DEVICE_TYPES:
        raise ValueError(f"Invalid device type: {device_type}. Must be one of {VALID_DEVICE_TYPES}")

    config = load_config()
    config["device_type"] = device_type
    save_config(config)


def get_sync_config() -> dict:
    """
    Get provider-specific sync configuration.

    Returns:
        Dictionary of provider-specific settings
    """
    config = load_config()
    return config.get("sync_config", {})


def validate_sync_config(sync_config: dict, provider: str) -> tuple[bool, Optional[str]]:
    """
    Validate provider-specific sync configuration.

    Args:
        sync_config: Dictionary of provider-specific settings
        provider: The sync provider being configured

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(sync_config, dict):
        return False, "sync_config must be a dictionary"

    if provider == "onelake":
        workspace = sync_config.get("workspace", "")
        lakehouse = sync_config.get("lakehouse", "")
        # OneLake workspace/lakehouse names have specific requirements
        if not workspace or len(workspace) > 256:
            return False, "OneLake workspace name must be 1-256 characters"
        if not lakehouse or len(lakehouse) > 256:
            return False, "OneLake lakehouse name must be 1-256 characters"
        # Disallow path traversal characters
        if ".." in workspace or "/" in workspace or "\\" in workspace:
            return False, "OneLake workspace name contains invalid characters"
        if ".." in lakehouse or "/" in lakehouse or "\\" in lakehouse:
            return False, "OneLake lakehouse name contains invalid characters"

    elif provider == "motherduck":
        token = sync_config.get("token", "")
        if not token:
            return False, "MotherDuck token is required"
        # Basic token format validation (MotherDuck tokens are typically 32+ chars)
        if len(token) < 10 or len(token) > 256:
            return False, "MotherDuck token appears invalid (check length)"

    elif provider == "onedrive":
        path = sync_config.get("path", "")
        if path:
            # Validate path doesn't contain dangerous patterns
            if ".." in path:
                return False, "OneDrive path cannot contain '..'"

    return True, None


def set_sync_config(sync_config: dict) -> None:
    """
    Set provider-specific sync configuration.

    Args:
        sync_config: Dictionary of provider-specific settings
    """
    config = load_config()
    config["sync_config"] = sync_config
    save_config(config)


def initialize_device_info() -> tuple[str, str, str]:
    """
    Initialize device information if not already set.

    Auto-generates device_id, device_name (hostname), and device_type.

    Returns:
        Tuple of (device_id, device_name, device_type)
    """
    config = load_config()
    changed = False

    device_id = config.get("device_id")
    if not device_id:
        device_id = generate_device_id()
        config["device_id"] = device_id
        changed = True

    device_name = config.get("device_name")
    if not device_name:
        device_name = platform.node() or f"device-{device_id}"
        config["device_name"] = device_name
        changed = True

    device_type = config.get("device_type")
    if not device_type:
        device_type = get_device_type()
        config["device_type"] = device_type
        changed = True

    if changed:
        save_config(config)

    return device_id, device_name, device_type


def is_sync_configured() -> bool:
    """
    Check if sync has been configured.

    Returns:
        True if sync provider is set to something other than "none"
    """
    return get_sync_provider() != "none"


#endregion
