"""The four agent-facing tools: list_tree, get_state, find_state, read_log."""

from __future__ import annotations

import fnmatch
import json
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pmstate.backends import FilesystemBackend, StorageBackend
from pmstate.node import Node
from pmstate.rollup import compute_view
from pmstate.storage import Log
from pmstate.tree import Tree
from pmstate.upcasters import default_registry

_LIST_DEPTH_MAX = 3
_FIND_RESULT_MAX = 200
_LOG_LIMIT_MAX = 1000


class ToolError(RuntimeError):
    """Raised by the agent-facing tools for programmer-fault conditions."""


def _as_backend(root: Path | StorageBackend) -> StorageBackend:
    """Accept a ``StorageBackend`` directly, or wrap a ``Path`` as a filesystem one."""
    if isinstance(root, Path):
        return FilesystemBackend(root)
    return root


def list_tree(tree: Tree, path: str = "/", depth: int = 1) -> list[dict[str, Any]]:
    """Return direct children at ``path`` with name/description/state/type metadata.

    ``depth`` ∈ ``[1, 3]`` — depth=1 means just the direct children. Recurses
    breadth-first; deeper subtrees appear with ``"path"`` set to their full
    path under ``path``.
    """
    if depth < 1 or depth > _LIST_DEPTH_MAX:
        raise ValueError(f"depth must be in [1, {_LIST_DEPTH_MAX}]; got {depth}")
    parent = tree.get(path)
    base = path.rstrip("/")

    out: list[dict[str, Any]] = []
    queue: deque[tuple[Node, str, int]] = deque([(parent, base, 0)])
    while queue:
        node, parent_path, level = queue.popleft()
        if level >= depth:
            continue
        for child in node.children:
            child_path = f"{parent_path}/{child.name}"
            out.append(_describe(child, child_path))
            queue.append((child, child_path, level + 1))
    return out


def _describe(node: Node, full_path: str) -> dict[str, Any]:
    return {
        "name": node.name,
        "path": full_path,
        "description": node.effective_description,
        "has_state": node.state is not None,
        "has_children": bool(node.children),
        "type": "internal" if node.children else "leaf",
    }


def get_state(tree: Tree, path: str, root_dir: Path | StorageBackend) -> dict[str, Any]:
    """Return the rolled-up view at ``path``. Errors surface as data."""
    try:
        node = tree.get(path)
        return compute_view(node, _as_backend(root_dir), node_path=path or "/")
    except Exception as exc:
        return {
            "error": str(exc),
            "exception": type(exc).__name__,
            "path": path,
        }


def find_state(
    tree: Tree,
    query: str,
    *,
    root_dir: Path | StorageBackend,
    path_glob: str | None = None,
    max_results: int = 50,
) -> list[dict[str, Any]]:
    """Breadth-first search: match ``query`` (substring) inside each node's view JSON.

    ``path_glob`` (e.g. ``"/active/*/quotes"``) filters which paths get scanned.
    Caps at ``max_results`` (≤ 200). Errors-as-data per node.
    """
    if max_results < 1 or max_results > _FIND_RESULT_MAX:
        raise ValueError(f"max_results must be in [1, {_FIND_RESULT_MAX}]; got {max_results}")
    backend = _as_backend(root_dir)
    matches: list[dict[str, Any]] = []
    queue: deque[tuple[Node, str]] = deque([(tree.root, "/")])
    while queue and len(matches) < max_results:
        node, node_path = queue.popleft()
        if path_glob is None or fnmatch.fnmatchcase(node_path, path_glob):
            view = get_state(tree, node_path, backend)
            blob = json.dumps(view, default=str, ensure_ascii=False)
            if query in blob:
                matches.append({"path": node_path, "snippet": _snippet(blob, query)})
        for child in node.children:
            sub = "/" + child.name if node_path == "/" else f"{node_path}/{child.name}"
            queue.append((child, sub))
    return matches


def _snippet(blob: str, query: str, *, window: int = 80) -> str:
    idx = blob.find(query)
    if idx < 0:
        return blob[:window]
    start = max(0, idx - window // 2)
    end = min(len(blob), idx + len(query) + window // 2)
    return blob[start:end]


def read_log(
    tree: Tree,
    path: str,
    root_dir: Path | StorageBackend,
    *,
    start: int | None = None,
    end: int | None = None,
    limit: int = 100,
    filter: Callable[[dict[str, Any]], bool] | None = None,
) -> list[dict[str, Any]]:
    """Read events from the Log-backed leaf at ``path``.

    Raises :class:`ToolError` when the leaf does not have a Log state. Caps
    ``limit`` at 1000.
    """
    if limit < 1 or limit > _LOG_LIMIT_MAX:
        raise ValueError(f"limit must be in [1, {_LOG_LIMIT_MAX}]; got {limit}")
    node = tree.get(path)
    if not isinstance(node.state, Log):
        raise ToolError(f"node at {path!r} does not have a Log state")
    backend = _as_backend(root_dir)
    after = str(start) if start is not None else None
    until = str(end) if end is not None else None
    rows: list[dict[str, Any]] = []
    for raw_event in backend.read(str(node.state.path), after=after, until=until):
        decoded = default_registry.upcast(raw_event)
        if filter is not None and not filter(decoded):
            continue
        if len(rows) >= limit:
            break
        rows.append(decoded)
    return rows
