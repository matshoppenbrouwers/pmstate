"""Shared project loader: importing ``tree.py`` and building a :class:`Tree`."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from pmstate.tree import Tree


class RunError(RuntimeError):
    """Raised when a project cannot be loaded; message is shown to the user."""


def _load_tree_module(root: Path) -> ModuleType:
    tree_path = root / "tree.py"
    if not tree_path.is_file():
        raise RunError(f"missing tree.py at {tree_path}")
    spec = importlib.util.spec_from_file_location("_pmstate_user_tree", tree_path)
    if spec is None or spec.loader is None:
        raise RunError(f"could not load tree.py at {tree_path}")
    module = importlib.util.module_from_spec(spec)
    root_str = str(root)
    added = False
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
        added = True
    for cached in ("tree", "views", "reducers", "_pmstate_user_tree"):
        sys.modules.pop(cached, None)
    try:
        spec.loader.exec_module(module)
    finally:
        if added:
            sys.path.remove(root_str)
    return module


def _build_tree(root: Path) -> Tree:
    module = _load_tree_module(root)
    builder = getattr(module, "build_tree", None)
    if builder is None:
        raise RunError("tree.py does not define build_tree()")
    tree = builder()
    if not isinstance(tree, Tree):
        raise RunError(f"build_tree() returned {type(tree).__name__}, not Tree")
    return tree
