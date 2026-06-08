"""Streaming JSONL reader with byte-cursor replay and optional upcaster registry."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from pmstate.backends.filesystem import FilesystemBackend, ReaderError
from pmstate.upcasters import UpcasterRegistry, default_registry

__all__ = ["ReaderError", "read_events"]


def read_events(
    log_path: Path,
    *,
    start: int | None = None,
    end: int | None = None,
    limit: int | None = None,
    filter: Callable[[dict[str, Any]], bool] | None = None,
    registry: UpcasterRegistry | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream decoded events from a JSONL log. ``start``/``end`` are byte offsets.

    Lines are streamed one at a time; the file is never fully buffered. Blank lines
    are skipped silently. A malformed line raises :class:`ReaderError` with line
    context. ``filter`` is applied after decoding (and after upcasting). When
    ``registry`` is ``None``, the module-level ``default_registry`` is used.
    """
    active_registry = registry if registry is not None else default_registry
    after = str(start) if start is not None else None
    until = str(end) if end is not None else None
    backend = FilesystemBackend(log_path.parent)
    yielded = 0
    for raw_event in backend.read(log_path.name, after=after, until=until):
        decoded = active_registry.upcast(raw_event)
        if filter is not None and not filter(decoded):
            continue
        if limit is not None and yielded >= limit:
            return
        yield decoded
        yielded += 1
