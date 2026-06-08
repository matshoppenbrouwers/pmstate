"""FilesystemBackend — JSONL logs on disk with byte-offset cursors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pmstate.backends.base import Cursor

_CACHE_DIR_NAME = ".pmstate"
_CACHE_FILE_NAME = "rollup.json"


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

    def _node_dir(self, node_path: str) -> Path:
        """Map a logical node path to its on-disk directory under ``root``."""
        if node_path in {"", "/"}:
            return self.root
        return self.root / node_path.lstrip("/")

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

    def read_doc(self, stream: str) -> Any:
        """Parse and return the JSON document stored at the stream."""
        with self._resolve(stream).open("r", encoding="utf-8") as f:
            return json.load(f)

    def write_doc(self, stream: str, doc: Any) -> None:
        """Write the JSON document to the stream."""
        path = self._resolve(stream)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, default=str), encoding="utf-8")

    def read_cache(self, node_path: str) -> tuple[str, dict[str, Any]] | None:
        """Return the cached ``(key, view)`` for the node, or None on miss/corruption."""
        cache_path = self._node_dir(node_path) / _CACHE_DIR_NAME / _CACHE_FILE_NAME
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                cached = json.load(f)
            return cached["key"], cached["view"]
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return None

    def write_cache(self, node_path: str, key: str, view: dict[str, Any]) -> None:
        """Store the ``(key, view)`` rollup cache under ``<node>/.pmstate/rollup.json``."""
        cache_path = self._node_dir(node_path) / _CACHE_DIR_NAME / _CACHE_FILE_NAME
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"key": key, "view": view}, default=str), encoding="utf-8"
        )
