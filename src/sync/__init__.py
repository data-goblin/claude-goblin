"""
Sync module for Claude Goblin.

Provides cross-device sync functionality via multiple providers:
- Syncthing: P2P folder sync
- OneDrive: Local folder sync
- OneLake: Microsoft Fabric lakehouse
- MotherDuck: DuckDB cloud service
"""
#region Imports
from src.sync.providers.base import SyncProvider
from src.sync.providers.syncthing import SyncthingProvider
from src.sync.providers.onedrive import OneDriveProvider
from src.sync.providers.onelake import OneLakeProvider
from src.sync.providers.motherduck import MotherDuckProvider
#endregion


#region Factory


def get_provider(provider_name: str, **config) -> SyncProvider | None:
    """
    Get a sync provider instance by name.

    Args:
        provider_name: Provider identifier (syncthing, onedrive, onelake, motherduck)
        **config: Provider-specific configuration

    Returns:
        SyncProvider instance or None if provider is "none"
    """
    providers = {
        "syncthing": SyncthingProvider,
        "onedrive": OneDriveProvider,
        "onelake": OneLakeProvider,
        "motherduck": MotherDuckProvider,
    }

    if provider_name == "none" or provider_name not in providers:
        return None

    return providers[provider_name](**config)


#endregion


__all__ = [
    "SyncProvider",
    "SyncthingProvider",
    "OneDriveProvider",
    "OneLakeProvider",
    "MotherDuckProvider",
    "get_provider",
]
