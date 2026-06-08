"""StorageBackend Protocol — the single seam between pmstate and storage."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, runtime_checkable

Cursor = str  # opaque, backend-defined ordering token (FS: byte offset; stores: last ULID)


class StorageError(Exception):
    """Raised when a storage backend operation fails."""


@runtime_checkable
class StorageBackend(Protocol):
    """Structural contract every storage backend satisfies."""

    def append(self, stream: str, event: dict[str, Any]) -> Cursor:
        """Append an event to the stream; return the post-write cursor."""
        ...

    def read(
        self,
        stream: str,
        *,
        after: Cursor | None = None,
        until: Cursor | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield events from the stream within the optional cursor bounds."""
        ...

    def read_doc(self, stream: str) -> Any:
        """Read the JSON document stored at the stream."""
        ...

    def write_doc(self, stream: str, doc: Any) -> None:
        """Write the JSON document to the stream."""
        ...

    def read_cache(self, node_path: str) -> tuple[str, dict[str, Any]] | None:
        """Return the cached ``(key, view)`` for the node, or None on miss."""
        ...

    def write_cache(self, node_path: str, key: str, view: dict[str, Any]) -> None:
        """Store the ``(key, view)`` rollup cache for the node."""
        ...
