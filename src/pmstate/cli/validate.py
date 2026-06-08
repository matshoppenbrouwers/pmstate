"""``pmstate validate``: structural + semantic checks against a project."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

import attrs

from pmstate.backends import StorageBackend
from pmstate.backends.filesystem import FilesystemBackend
from pmstate.cli._discovery import find_project_root
from pmstate.cli._spec import SpecError, parse_spec
from pmstate.cli.run import RunError, _build_tree
from pmstate.rollup import compute_view_at
from pmstate.tree import Tree

Level = Literal["error", "warn"]


@attrs.define(frozen=True, slots=True)
class Issue:
    """A single validation finding. Plain data; safe to JSON-serialize."""

    file: str
    line: int | None
    level: Level
    msg: str

    def as_dict(self) -> dict[str, Any]:
        return attrs.asdict(self)


def cmd_validate(args: argparse.Namespace) -> int:
    """Run all validation checks and emit issues. Exit 1 iff any error."""
    root = find_project_root(Path.cwd())
    if root is None:
        print("not in a pmstate project — run `pmstate init` first", file=sys.stderr)
        return 1
    backend = FilesystemBackend(root)
    issues: list[Issue] = []
    spec_issues = check_spec_parses(root)
    issues.extend(spec_issues)
    tree: Tree | None = None
    if not _has_errors(spec_issues):
        tree_issues, tree = check_tree_imports(root)
        issues.extend(tree_issues)
        if tree is not None:
            issues.extend(check_compute_view_at_root(root, tree, backend))
    issues.extend(check_agents_md_present(root))
    if args.strict:
        issues.extend(_run_strict_checks(root))
    return _emit(issues, as_json=bool(args.json))


def check_spec_parses(root: Path) -> list[Issue]:
    spec_path = root / "pmstate.yaml"
    try:
        parse_spec(spec_path)
    except SpecError as exc:
        return [Issue(file=str(exc.file), line=exc.line, level="error", msg=exc.msg)]
    return []


def check_tree_imports(root: Path) -> tuple[list[Issue], Tree | None]:
    try:
        return [], _build_tree(root)
    except RunError as exc:
        msg = str(exc)
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
    return [Issue(file=str(root / "tree.py"), line=None, level="error", msg=msg)], None


def check_compute_view_at_root(
    root: Path, tree: Tree, backend: StorageBackend
) -> list[Issue]:
    try:
        compute_view_at(tree, "/", backend)
    except Exception as exc:
        return [
            Issue(
                file=str(root / "views.py"),
                line=None,
                level="error",
                msg=f"compute_view_at('/') raised {type(exc).__name__}: {exc}",
            )
        ]
    return []


def check_agents_md_present(root: Path) -> list[Issue]:
    agents = root / "AGENTS.md"
    if not agents.is_file():
        return [Issue(file=str(agents), line=None, level="warn", msg="AGENTS.md is missing")]
    if not agents.read_text(encoding="utf-8").strip():
        return [Issue(file=str(agents), line=None, level="error", msg="AGENTS.md is empty")]
    return []


def _run_strict_checks(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    for tool in ("mypy", "ruff"):
        if shutil.which(tool) is None:
            issues.append(
                Issue(
                    file=str(root),
                    line=None,
                    level="warn",
                    msg=f"--strict skipped: {tool} not on PATH",
                )
            )
            continue
        argv = [tool, "check", str(root)] if tool == "ruff" else [tool, str(root)]
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            output = result.stdout.strip() or result.stderr.strip()
            issues.append(
                Issue(
                    file=str(root),
                    line=None,
                    level="error",
                    msg=f"{tool} reported issues:\n{output}",
                )
            )
    return issues


def _emit(issues: list[Issue], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps([i.as_dict() for i in issues]))
    else:
        for issue in issues:
            line = issue.line if issue.line is not None else "-"
            print(f"{issue.file}:{line}: {issue.level}: {issue.msg}")
        if not _has_errors(issues):
            print("OK")
    return 1 if _has_errors(issues) else 0


def _has_errors(issues: list[Issue]) -> bool:
    return any(i.level == "error" for i in issues)
