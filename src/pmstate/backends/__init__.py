"""Storage backends: the seam between pmstate and its persistence layer."""

from pmstate.backends.base import Cursor, StorageBackend, StorageError
from pmstate.backends.filesystem import FilesystemBackend

__all__ = [
    "Cursor",
    "FilesystemBackend",
    "StorageBackend",
    "StorageError",
]
