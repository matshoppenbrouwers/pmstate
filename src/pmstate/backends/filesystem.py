"""FilesystemBackend — JSONL logs on disk with byte-offset cursors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pmstate.backends.base import Cursor


class ReaderError(ValueError):
    """Raised when a JSONL line cannot be decoded."""

    def __init__(self, path: Path, line_number: int, raw_line: str) -> None:
        super().__init__(f"failed to decode {path} line {line_number}: {raw_line!r}")
        self.path = path
        self.line_number = line_number
        self.raw_line = raw_line


class FilesystemBackend:
    """StorageBackend backed by the local filesystem. Cursors are byte offsets."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def _resolve(self, stream: str) -> Path:
        """Map a logical stream to its on-disk path under ``root``."""
        return self.root / stream

    def append(self, stream: str, event: dict[str, Any]) -> Cursor:
        """Append one event as a JSONL line; return the post-write byte offset."""
        path = self._resolve(stream)
        payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n"
        encoded = payload.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as f:
            f.write(encoded)
            return str(f.tell())

    def read(
        self,
        stream: str,
        *,
        after: Cursor | None = None,
        until: Cursor | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield events from the JSONL log between byte-offset cursors."""
        path = self._resolve(stream)
        start = int(after) if after is not None else None
        end = int(until) if until is not None else None
        yielded = 0
        line_number = 0
        if not path.exists():
            return
        with path.open("rb") as f:
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
                    raise ReaderError(path, line_number, text) from exc
                yield decoded
                yielded += 1
