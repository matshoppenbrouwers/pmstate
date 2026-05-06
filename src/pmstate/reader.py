"""Streaming JSONL reader with byte-cursor replay and optional upcaster registry."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Protocol


class _UpcasterLike(Protocol):
    def upcast(self, event_dict: dict[str, Any]) -> dict[str, Any]: ...


class ReaderError(ValueError):
    """Raised when a JSONL line cannot be decoded."""

    def __init__(self, path: Path, line_number: int, raw_line: str) -> None:
        super().__init__(f"failed to decode {path} line {line_number}: {raw_line!r}")
        self.path = path
        self.line_number = line_number
        self.raw_line = raw_line


def read_events(
    log_path: Path,
    *,
    start: int | None = None,
    end: int | None = None,
    limit: int | None = None,
    filter: Callable[[dict[str, Any]], bool] | None = None,
    registry: _UpcasterLike | None = None,
) -> Iterator[dict[str, Any]]:
    """Stream decoded events from a JSONL log. ``start``/``end`` are byte offsets.

    Lines are streamed one at a time; the file is never fully buffered. Blank lines
    are skipped silently. A malformed line raises :class:`ReaderError` with line
    context. ``filter`` is applied after decoding (and after upcasting).
    """
    yielded = 0
    line_number = 0
    with log_path.open("rb") as f:
        if start is not None:
            f.seek(start)
        while True:
            if limit is not None and yielded >= limit:
                return
            if end is not None and f.tell() >= end:
                return
            raw = f.readline()
            if not raw:
                return
            line_number += 1
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                decoded: dict[str, Any] = json.loads(stripped)
            except json.JSONDecodeError as exc:
                text = stripped.decode("utf-8", "replace")
                raise ReaderError(log_path, line_number, text) from exc
            if registry is not None:
                decoded = registry.upcast(decoded)
            if filter is not None and not filter(decoded):
                continue
            yield decoded
            yielded += 1
