"""
Base class for sync providers.

Defines the interface that all sync providers must implement.
"""
#region Imports
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
#endregion


#region Base Class


class SyncProvider(ABC):
    """
    Abstract base class for sync providers.

    All sync providers must implement these methods to provide
    consistent sync functionality across different backends.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        pass

    @property
    @abstractmethod
    def requires_account(self) -> bool:
        """Whether this provider requires an account."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is available on this system.

        Returns:
            True if the provider can be used
        """
        pass

    @abstractmethod
    def is_authenticated(self) -> bool:
        """
        Check if the provider is authenticated/configured.

        Returns:
            True if ready to sync
        """
        pass

    @abstractmethod
    def get_status(self) -> dict:
        """
        Get provider status information.

        Returns:
            Dict with status details (varies by provider)
        """
        pass

    @abstractmethod
    def push(self, local_path: Path) -> tuple[bool, str]:
        """
        Push local data to remote sync target.

        Args:
            local_path: Path to local database file

        Returns:
            Tuple of (success, message)
        """
        pass

    @abstractmethod
    def pull(self, local_dir: Path) -> tuple[bool, str]:
        """
        Pull remote data to local directory.

        Args:
            local_dir: Directory to store pulled data

        Returns:
            Tuple of (success, message)
        """
        pass

    def get_remote_devices(self) -> list[dict]:
        """
        Get list of remote devices (if supported).

        Returns:
            List of device info dicts with keys: id, name, last_sync
        """
        return []


#endregion
