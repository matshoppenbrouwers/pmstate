"""Lazy rollup with content-hash cache invalidation.

A parent's view is computed from its children's views. To avoid re-running on every
read, each parent caches its view in ``<node-on-disk>/.pmstate/rollup.json`` keyed by
a hash of the node path, the view-fn source, the reducer-fn source, and the children's
hashes. On read we recompute the cache key from current state; match means the cached
view is fresh, mismatch means recompute.

Hamilton nested-call hash gotcha
--------------------------------
Hashing a function via ``inspect.getsource`` only captures the function body itself,
*not* helpers it calls. If a view ``v`` calls a helper ``h``, editing ``h`` will not
change the hash of ``v`` and the cache will not invalidate. Either inline helpers or
include their source in the view's body when correctness depends on it.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pmstate.storage import Log, Table

if TYPE_CHECKING:
    from pmstate.node import Node
    from pmstate.tree import Tree

_CACHE_DIR_NAME = ".pmstate"
_CACHE_FILE_NAME = "rollup.json"
_WS_RE = re.compile(r"\s+")
_COMMENT_RE = re.compile(r"#[^\n]*")


def _fn_hash(fn: Callable[..., Any] | None) -> str:
    if fn is None:
        return "none"
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        return f"id:{id(fn)}"
    stripped = _WS_RE.sub(" ", _COMMENT_RE.sub("", source)).strip()
    return hashlib.sha256(stripped.encode("utf-8")).hexdigest()


def _content_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_key(
    node_path: str,
    view_hash: str,
    reducer_hash: str,
    children_hashes: tuple[str, ...],
) -> str:
    parts = (node_path, view_hash, reducer_hash, *children_hashes)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def _load_cache(cache_path: Path) -> tuple[str, dict[str, Any]] | None:
    try:
        with cache_path.open("r", encoding="utf-8") as f:
            cached = json.load(f)
        return cached["key"], cached["view"]
    except (FileNotFoundError, KeyError, json.JSONDecodeError):
        return None


def _store_cache(cache_path: Path, key: str, view: dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps({"key": key, "view": view}, default=str), encoding="utf-8"
    )


def _on_disk_path(root: Path, node_path: str) -> Path:
    if node_path in {"", "/"}:
        return root
    return root / node_path.lstrip("/")


def _leaf_view(node: Node) -> dict[str, Any]:
    if node.state is None:
        return {}
    if node.view is None:
        return node.state.read()
    if isinstance(node.state, Log):
        return Log(node.state.path, view=node.view).read()
    return Table(node.state.path, view=node.view).read()


def _safe_reduce(
    fn: Callable[[dict[str, dict[str, Any]]], dict[str, Any]],
    children_views: dict[str, dict[str, Any]],
    *,
    node_path: str,
) -> dict[str, Any]:
    try:
        return fn(children_views)
    except Exception as exc:
        return {
            "error": str(exc),
            "exception": type(exc).__name__,
            "where": f"reducer of {node_path}",
        }


def compute_view(node: Node, root: Path, *, node_path: str = "/") -> dict[str, Any]:
    """Compute the rolled-up view for ``node``. Persists per-node cache under ``root``.

    Leaves delegate to their state (or to the node's view applied to that state).
    Internal nodes recurse over children, key the result by child name, then pass
    through ``node.reducer`` if set, otherwise return the children dict directly.
    """
    if not node.children:
        return _leaf_view(node)

    children_views: dict[str, dict[str, Any]] = {}
    children_hashes: list[str] = []
    for child in node.children:
        sub_path = f"{node_path.rstrip('/')}/{child.name}"
        view = compute_view(child, root, node_path=sub_path)
        children_views[child.name] = view
        children_hashes.append(_content_hash(view))

    key = _cache_key(
        node_path,
        _fn_hash(node.view),
        _fn_hash(node.reducer),
        tuple(children_hashes),
    )

    cache_path = _on_disk_path(root, node_path) / _CACHE_DIR_NAME / _CACHE_FILE_NAME
    cached = _load_cache(cache_path)
    if cached is not None and cached[0] == key:
        return cached[1]

    if node.reducer is not None:
        result = _safe_reduce(node.reducer, children_views, node_path=node_path)
    else:
        result = children_views

    _store_cache(cache_path, key, result)
    return result


def compute_view_at(tree: Tree, path: str, root_dir: Path) -> dict[str, Any]:
    """Compute the rolled-up view for the node at ``path`` inside ``tree``."""
    node = tree.get(path)
    return compute_view(node, root_dir, node_path=path or "/")
