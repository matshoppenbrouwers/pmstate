"""Loader for ``AGENTS.md`` at the tree root, with mtime-keyed cache."""

from __future__ import annotations

from pathlib import Path

_cache: dict[Path, tuple[float, str]] = {}


def load_agents_md(tree_root: Path) -> str | None:
    """Read ``<tree_root>/AGENTS.md`` if present, ``None`` if missing.

    Caches by absolute path; invalidates when the file's mtime changes. Lets
    :class:`OSError` propagate when the file exists but cannot be read.
    """
    path = (tree_root / "AGENTS.md").resolve()
    if not path.exists():
        _cache.pop(path, None)
        return None
    mtime = path.stat().st_mtime
    cached = _cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    content = path.read_text(encoding="utf-8")
    _cache[path] = (mtime, content)
    return content
