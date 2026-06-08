"""Shared backend test fixtures and an in-memory fake backend.

``FakeMemoryBackend`` is a dict-backed :class:`~pmstate.backends.StorageBackend`
implementation used to prove the storage seam is real: it touches no disk yet
satisfies the same contract suite as :class:`FilesystemBackend`. Cursors are
1-based post-write indices — ``after`` is exclusive, ``until`` is inclusive,
mirroring the byte-offset semantics of the filesystem backend.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from typing import Any

from pmstate.backends.base import Cursor


class FakeMemoryBackend:
    """In-memory StorageBackend: events, docs, and rollup caches in plain dicts."""

    def __init__(self) -> None:
        self._streams: dict[str, list[dict[str, Any]]] = {}
        self._docs: dict[str, Any] = {}
        self._caches: dict[str, tuple[str, dict[str, Any]]] = {}

    def append(self, stream: str, event: dict[str, Any]) -> Cursor:
        events = self._streams.setdefault(stream, [])
        events.append(copy.deepcopy(event))
        return str(len(events))

    def read(
        self,
        stream: str,
        *,
        after: Cursor | None = None,
        until: Cursor | None = None,
        limit: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        start = int(after) if after is not None else 0
        end = int(until) if until is not None else None
        yielded = 0
        for index, event in enumerate(self._streams.get(stream, [])):
            position = index + 1  # 1-based post-write cursor
            if position <= start:
                continue
            if end is not None and position > end:
                break
            if limit is not None and yielded >= limit:
                break
            yield copy.deepcopy(event)
            yielded += 1

    def read_doc(self, stream: str) -> Any:
        try:
            return copy.deepcopy(self._docs[stream])
        except KeyError as exc:
            raise KeyError(f"no document at {stream!r}") from exc

    def write_doc(self, stream: str, doc: Any) -> None:
        self._docs[stream] = copy.deepcopy(doc)

    def read_cache(self, node_path: str) -> tuple[str, dict[str, Any]] | None:
        cached = self._caches.get(node_path)
        if cached is None:
            return None
        key, view = cached
        return key, copy.deepcopy(view)

    def write_cache(self, node_path: str, key: str, view: dict[str, Any]) -> None:
        self._caches[node_path] = (key, copy.deepcopy(view))
