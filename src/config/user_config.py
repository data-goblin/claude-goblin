#region Imports
import json
import platform
import re
import uuid
from pathlib import Path
from typing import Any

#endregion


#region Types
VALID_STORAGE_FORMATS = ["sqlite", "duckdb"]
VALID_SYNC_PROVIDERS = ["quack", "onedrive", "onelake", "motherduck", "none"]
VALID_DEVICE_TYPES = ["macos", "windows", "linux"]

# UUID shape for onelake workspace/lakehouse/tenant/model ids
UUID_PATTERN = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')

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
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
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

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
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


def get_device_id() -> str | None:
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


def get_device_name() -> str | None:
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


def get_device_type_config() -> str | None:
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


def get_extra_sources() -> list[dict]:
    """
    Get extra JSONL source directories with their device attribution.

    Reads the "extra_sources" config list. Each entry must have:
    - path: directory scanned recursively for *.jsonl
    - device_id: valid device identifier for records from this source
    - device_name: human-readable device name
    - device_type: one of "macos", "windows", "linux"
    - format: one of "claude", "codex", "hermes" (defaults to "claude")

    Returns:
        List of validated source dicts; invalid entries are skipped
    """
    config = load_config()
    sources = []
    for entry in config.get("extra_sources", []):
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        device_id = entry.get("device_id", "")
        device_name = entry.get("device_name", "")
        device_type = entry.get("device_type", "")
        if (
            not path
            or not validate_device_id(device_id)
            or not validate_device_name(device_name)
            or device_type not in VALID_DEVICE_TYPES
        ):
            continue
        source_format = entry.get("format", "claude")
        if source_format not in ("claude", "codex", "hermes"):
            source_format = "claude"
        source = {
            "path": str(Path(path).expanduser()),
            "device_id": device_id,
            "device_name": device_name,
            "device_type": device_type,
            "format": source_format,
        }
        account = entry.get("account")
        if isinstance(account, dict):
            source["account"] = account
        sources.append(source)
    return sources


def _is_nested_sync_config(sync_config: dict[str, Any]) -> bool:
    """True when every key is a provider name mapping to a dict (nested layout)."""
    if not sync_config:
        return False
    return all(
        key in VALID_SYNC_PROVIDERS and isinstance(value, dict)
        for key, value in sync_config.items()
    )


def get_sync_config(provider: str) -> dict[str, Any]:
    """
    Get sync configuration for one provider.

    Handles both layouts: nested ({provider: {...}}) and legacy flat (a single
    provider's settings at the top level). A flat layout is returned only when
    the requested provider matches the configured sync_provider; any other
    provider gets {} so one provider's settings are never mislabeled as
    another's.

    Args:
        provider: Provider name from VALID_SYNC_PROVIDERS

    Returns:
        Dictionary of that provider's settings ({} if unconfigured)
    """
    config = load_config()
    sync_config: dict[str, Any] = config.get("sync_config", {})
    if _is_nested_sync_config(sync_config):
        entry = sync_config.get(provider, {})
        return entry if isinstance(entry, dict) else {}
    if provider == config.get("sync_provider", "none"):
        return sync_config
    return {}


def validate_sync_config(sync_config: dict, provider: str) -> tuple[bool, str | None]:
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

    if provider == "quack":
        host = sync_config.get("host", "")
        if not host:
            return False, "Quack host is required"
        port = sync_config.get("port", 9494)
        if not isinstance(port, int) or port < 1 or port > 65535:
            return False, "Quack port must be 1-65535"
        token_source = sync_config.get("token_source", "keychain")
        if token_source not in ("keychain", "env", "file"):
            return False, "token_source must be 'keychain', 'env', or 'file'"

    elif provider == "onelake":
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
        for id_field in ("workspace_id", "lakehouse_id", "tenant_id", "semantic_model_id"):
            value = sync_config.get(id_field)
            if value is not None and (not isinstance(value, str) or not UUID_PATTERN.match(value)):
                return False, f"OneLake {id_field} must be a UUID"
        device_filter = sync_config.get("device_filter")
        if device_filter is not None:
            if not isinstance(device_filter, list) or not all(
                isinstance(d, str) and validate_device_id(d) for d in device_filter
            ):
                return False, "OneLake device_filter must be a list of valid device ids"
        for int_field in ("min_push_interval", "compact_every"):
            value = sync_config.get(int_field)
            if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value < 1):
                return False, f"OneLake {int_field} must be a positive integer"
        user_upn = sync_config.get("user_upn")
        if user_upn is not None and (
            not isinstance(user_upn, str) or "@" not in user_upn or len(user_upn) > 256
        ):
            return False, "OneLake user_upn must be an email address"

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


def set_sync_config(provider: str, sync_config: dict[str, Any]) -> None:
    """
    Set one provider's sync configuration, preserving other providers.

    A legacy flat layout is first nested under the configured sync_provider so
    no existing settings are lost, then the given provider's entry is replaced.

    Args:
        provider: Provider name from VALID_SYNC_PROVIDERS
        sync_config: Dictionary of that provider's settings
    """
    if provider not in VALID_SYNC_PROVIDERS:
        raise ValueError(f"Invalid sync provider: {provider}. Must be one of {VALID_SYNC_PROVIDERS}")

    config = load_config()
    current = config.get("sync_config", {})
    if current and not _is_nested_sync_config(current):
        legacy_provider = config.get("sync_provider", "none")
        current = {legacy_provider: current} if legacy_provider != provider else {}
    config["sync_config"] = {**current, provider: sync_config}
    save_config(config)


def get_sync_providers() -> list[str]:
    """
    Get the list of active sync providers.

    Returns the explicit "sync_providers" list (invalid entries dropped) when
    present, else falls back to the singular sync_provider ([] when "none").
    """
    config = load_config()
    providers = config.get("sync_providers")
    if isinstance(providers, list):
        return [p for p in providers if p in VALID_SYNC_PROVIDERS and p != "none"]
    single = config.get("sync_provider", "none")
    return [single] if single in VALID_SYNC_PROVIDERS and single != "none" else []


def set_sync_providers(providers: list[str]) -> None:
    """
    Set the list of active sync providers.

    Args:
        providers: Provider names; each must be a valid provider, "none" excluded

    Raises:
        ValueError: If any entry is invalid
    """
    for provider in providers:
        if provider not in VALID_SYNC_PROVIDERS or provider == "none":
            raise ValueError(f"Invalid sync provider: {provider}")
    config = load_config()
    config["sync_providers"] = providers
    save_config(config)


def get_device_accounts() -> dict[str, dict[str, str]]:
    """
    Map device_id -> account metadata ({email, organization, subscription}).

    Collects the top-level "account" block (attributed to the main device_id)
    and each extra_source's "account" block. Devices without an account block
    are omitted.
    """
    config = load_config()
    accounts: dict[str, dict[str, str]] = {}

    main_id = config.get("device_id")
    main_account = config.get("account")
    if main_id and isinstance(main_account, dict):
        accounts[main_id] = main_account

    for entry in config.get("extra_sources", []):
        if not isinstance(entry, dict):
            continue
        device_id = entry.get("device_id", "")
        account = entry.get("account")
        if validate_device_id(device_id) and isinstance(account, dict):
            accounts[device_id] = account

    return accounts


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
