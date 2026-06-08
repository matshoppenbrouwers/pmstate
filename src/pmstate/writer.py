"""Append-only event writer. Single-writer-per-leaf contract for v0.1."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pmstate.backends.filesystem import FilesystemBackend
from pmstate.envelope import Event

_EVENT_BYTE_CEILING = 4000


class EventTooLargeError(ValueError):
    """Raised when a serialized event exceeds the 4000-byte ceiling."""

    def __init__(self, size: int) -> None:
        super().__init__(f"event is {size} bytes; max is {_EVENT_BYTE_CEILING}")
        self.size = size


def append_event(log_path: Path, event: Event, *, fsync: bool = False) -> None:
    """Atomically append one event to ``log_path`` as a single JSONL line."""
    data = event.to_dict()
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False) + "\n"
    size = len(payload.encode("utf-8"))
    if size > _EVENT_BYTE_CEILING:
        raise EventTooLargeError(size)
    FilesystemBackend(log_path.parent).append(log_path.name, data)
    if fsync:
        with log_path.open("rb") as f:
            os.fsync(f.fileno())
