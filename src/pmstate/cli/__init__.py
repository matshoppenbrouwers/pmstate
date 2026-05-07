"""pmstate CLI: argparse dispatch for ``init``, ``validate``, ``seed``, ``run``."""

from __future__ import annotations

import argparse
from collections.abc import Callable

from pmstate import __version__

Handler = Callable[[argparse.Namespace], int]


def _build_parser() -> tuple[argparse.ArgumentParser, dict[str, Handler]]:
    parser = argparse.ArgumentParser(
        prog="pmstate",
        description="Filesystem-shaped agent processes. The directory tree IS the state.",
    )
    parser.add_argument("--version", action="version", version=f"pmstate {__version__}")
    sub = parser.add_subparsers(dest="verb", metavar="{init,validate,seed,run}")

    _add_init(sub)
    _add_validate(sub)
    _add_seed(sub)
    _add_run(sub)

    from pmstate.cli.init import cmd_init  # noqa: PLC0415 — keep imports local
    from pmstate.cli.run import cmd_run  # noqa: PLC0415 — lazy: optional dep
    from pmstate.cli.seed import cmd_seed  # noqa: PLC0415 — keep imports local
    from pmstate.cli.validate import cmd_validate  # noqa: PLC0415 — keep imports local

    handlers: dict[str, Handler] = {
        "init": cmd_init,
        "validate": cmd_validate,
        "seed": cmd_seed,
        "run": cmd_run,
    }
    return parser, handlers


def _add_init(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("init", help="Scaffold a new pmstate project from pmstate.yaml.")
    p.add_argument("dir", nargs="?", default=".", help="Target directory (default: cwd).")
    p.add_argument("--from-spec", metavar="PATH", help="Generate from this pmstate.yaml.")
    p.add_argument("--upgrade", action="store_true", help="Refresh generated files in place.")
    p.add_argument("--force", action="store_true", help="Overwrite existing files.")


def _add_validate(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("validate", help="Check that the project builds and views compute.")
    p.add_argument("--strict", action="store_true", help="Also run mypy and ruff if available.")
    p.add_argument("--json", action="store_true", help="Emit JSON-formatted issues.")


def _add_seed(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("seed", help="Generate deterministic seed events into Log leaves.")
    p.add_argument("--n", type=int, default=30, help="Total events to emit (default: 30).")
    p.add_argument("--seed", type=int, default=None, help="RNG seed (default: 42).")
    p.add_argument("--force", action="store_true", help="Overwrite non-empty state/.")


def _add_run(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p = sub.add_parser("run", help="Run the harness against the project tree.")
    p.add_argument("prompt", nargs="?", default=None, help="Prompt (or read from stdin).")
    watch = p.add_mutually_exclusive_group()
    watch.add_argument("--watch", dest="watch", action="store_true", help="Enable watcher.")
    watch.add_argument("--no-watch", dest="watch", action="store_false", help="Disable watcher.")
    p.set_defaults(watch=False)


def main(argv: list[str] | None = None) -> int:
    """Entry point. Returns process exit code."""
    parser, handlers = _build_parser()
    args = parser.parse_args(argv)
    if args.verb is None:
        parser.print_help()
        return 2
    return handlers[args.verb](args)


if __name__ == "__main__":
    raise SystemExit(main())
