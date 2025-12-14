"""
Sync providers for Claude Goblin.

Each provider implements the SyncProvider interface for cross-device sync.
"""
#region Imports
from src.sync.providers.base import SyncProvider
from src.sync.providers.syncthing import SyncthingProvider
from src.sync.providers.onedrive import OneDriveProvider
from src.sync.providers.onelake import OneLakeProvider
from src.sync.providers.motherduck import MotherDuckProvider
#endregion


__all__ = [
    "SyncProvider",
    "SyncthingProvider",
    "OneDriveProvider",
    "OneLakeProvider",
    "MotherDuckProvider",
]
