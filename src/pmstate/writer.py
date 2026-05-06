"""Append-only event writer. Single-writer-per-leaf contract for v0.1."""

from __future__ import annotations

import json
import os
from pathlib import Path

from pmstate.envelope import Event

_EVENT_BYTE_CEILING = 4000


class EventTooLargeError(ValueError):
    """Raised when a serialized event exceeds the 4000-byte ceiling."""

    def __init__(self, size: int) -> None:
        super().__init__(f"event is {size} bytes; max is {_EVENT_BYTE_CEILING}")
        self.size = size


def append_event(log_path: Path, event: Event, *, fsync: bool = False) -> None:
    """Atomically append one event to ``log_path`` as a single JSONL line."""
    payload = json.dumps(event.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n"
    encoded = payload.encode("utf-8")
    if len(encoded) > _EVENT_BYTE_CEILING:
        raise EventTooLargeError(len(encoded))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("ab") as f:
        f.write(encoded)
        if fsync:
            os.fsync(f.fileno())
