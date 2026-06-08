"""Filesystem-backed state primitives: Log (append-only JSONL) and Table (JSON document)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import attrs

from pmstate.backends.filesystem import FilesystemBackend

LogView = Callable[[Iterable[dict[str, Any]]], dict[str, Any]]
TableView = Callable[[Any], dict[str, Any]]

_TABLE_BYTE_CEILING = 2048
_TABLE_KEY_CEILING = 50


def _error_view(exc: BaseException, path: Path) -> dict[str, Any]:
    return {
        "error": str(exc),
        "exception": type(exc).__name__,
        "path": str(path),
    }


def _default_log_view(events: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(events)
    return {
        "count": len(rows),
        "first": rows[0] if rows else None,
        "latest": rows[-1] if rows else None,
    }


def _default_table_view(doc: Any) -> dict[str, Any]:
    if not isinstance(doc, dict):
        return {"value": doc}
    serialized_size = len(json.dumps(doc, ensure_ascii=False).encode("utf-8"))
    if serialized_size > _TABLE_BYTE_CEILING or len(doc) > _TABLE_KEY_CEILING:
        keys = list(doc.keys())[:_TABLE_KEY_CEILING]
        return {"_truncated": True, "keys": keys, "size_bytes": serialized_size}
    return doc


@attrs.define(frozen=True, slots=True)
class Log:
    """Append-only JSONL event log. ``read()`` returns the view dict; errors surface as data."""

    path: Path = attrs.field(converter=Path)
    view: LogView | None = attrs.field(default=None, kw_only=True)

    def read(self) -> dict[str, Any]:
        """Return the view applied to all events. Reads the entire file (cost: O(file size))."""
        try:
            if not self.path.exists():
                raise FileNotFoundError(str(self.path))
            backend = FilesystemBackend(self.path.parent)
            events = list(backend.read(self.path.name))
            view = self.view or _default_log_view
            return view(events)
        except Exception as exc:
            return _error_view(exc, self.path)


@attrs.define(frozen=True, slots=True)
class Table:
    """JSON document storing slowly-changing reference data. ``read()`` returns the view dict."""

    path: Path = attrs.field(converter=Path)
    view: TableView | None = attrs.field(default=None, kw_only=True)

    def read(self) -> dict[str, Any]:
        """Return the view applied to the parsed JSON document; errors surface as data."""
        try:
            backend = FilesystemBackend(self.path.parent)
            doc = backend.read_doc(self.path.name)
            view = self.view or _default_table_view
            return view(doc)
        except Exception as exc:
            return _error_view(exc, self.path)
