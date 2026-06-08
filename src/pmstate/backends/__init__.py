"""Storage backends: the seam between pmstate and its persistence layer."""

from pmstate.backends.base import Cursor, StorageBackend, StorageError

__all__ = [
    "Cursor",
    "StorageBackend",
    "StorageError",
]
