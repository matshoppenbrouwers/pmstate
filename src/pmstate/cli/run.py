"""``pmstate run``: load tree.py and dispatch a one-shot prompt to the harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pmstate.backends.filesystem import FilesystemBackend
from pmstate.cli._discovery import find_project_root
from pmstate.cli._project import RunError, _build_tree, _load_tree_module

__all__ = ["RunError", "_build_tree", "_load_tree_module", "cmd_run"]


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

    write_enabled = bool(args.write)
    spec = None
    if write_enabled:
        from pmstate.cli._spec import SpecError, parse_spec  # noqa: PLC0415
        try:
            spec = parse_spec(root / "pmstate.yaml")
        except SpecError as exc:
            print(f"could not load spec: {exc}", file=sys.stderr)
            return 1

    from pmstate.adapters.claude_sdk import Harness  # noqa: PLC0415 — lazy: optional dep

    harness = Harness(
        tree=tree, root_dir=FilesystemBackend(root), watch=bool(args.watch),
        spec=spec, write_enabled=write_enabled,
    )
    reply = harness.run(prompt)
    if reply:
        print(reply)
    return 0
