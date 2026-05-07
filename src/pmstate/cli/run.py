"""``pmstate run``: load tree.py and dispatch a one-shot prompt to the harness."""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from pmstate.cli._discovery import find_project_root
from pmstate.tree import Tree


class RunError(RuntimeError):
    """Raised when ``pmstate run`` cannot proceed; message is shown to the user."""


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


def _resolve_prompt(arg_prompt: str | None) -> str:
    if arg_prompt is not None:
        return arg_prompt
    if sys.stdin.isatty():
        raise RunError("no prompt: pass one as an argument or pipe via stdin")
    text = sys.stdin.read().strip()
    if not text:
        raise RunError("empty prompt on stdin")
    return text


def cmd_run(args: argparse.Namespace) -> int:
    """Dispatch a prompt to ``Harness.run`` against the project tree."""
    root = find_project_root(Path.cwd())
    if root is None:
        print("not in a pmstate project — run `pmstate init` first", file=sys.stderr)
        return 1
    try:
        tree = _build_tree(root)
        prompt = _resolve_prompt(args.prompt)
    except RunError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    from pmstate.adapters.claude_sdk import Harness  # noqa: PLC0415 — lazy: optional dep

    harness = Harness(tree=tree, root_dir=root, watch=bool(args.watch))
    reply = harness.run(prompt)
    if reply:
        print(reply)
    return 0
