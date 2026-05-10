"""``pmstate append``: spec-validated append of a single event to a Log leaf."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pmstate.cli._append import AppendPlan, prepare_append
from pmstate.cli._discovery import find_project_root
from pmstate.cli._project import _build_tree
from pmstate.cli._spec import parse_spec
from pmstate.cli.validate import Issue
from pmstate.writer import append_event


def cmd_append(args: argparse.Namespace) -> int:
    """Append a single event to a Log leaf, with spec-aware validation."""
    root = find_project_root(Path.cwd())
    if root is None:
        print("not in a pmstate project — run `pmstate init` first", file=sys.stderr)
        return 1
    try:
        spec = parse_spec(root / "pmstate.yaml")
        tree = _build_tree(root)
    except Exception as exc:
        print(f"could not load project: {exc}", file=sys.stderr)
        return 1

    data, parse_issue = _parse_data(args.data)
    if parse_issue is not None:
        return _emit_issues((parse_issue,), as_json=bool(args.json))

    plan = prepare_append(
        spec, tree, args.path, args.type, data,
        source=args.source, subject=args.subject, causationid=args.causationid,
    )
    if plan.issues:
        return _emit_issues(plan.issues, as_json=bool(args.json))
    return _write_and_emit(plan, as_json=bool(args.json))


def _parse_data(raw: str) -> tuple[dict[str, Any], Issue | None]:
    text = sys.stdin.read() if raw == "-" else raw
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return {}, Issue(
            file="<append>", line=None, level="error",
            msg=f"--data is not valid JSON: {exc}",
        )
    if not isinstance(parsed, dict):
        return {}, Issue(
            file="<append>", line=None, level="error",
            msg=f"--data must be a JSON object, got {type(parsed).__name__}",
        )
    return parsed, None


def _emit_issues(issues: tuple[Issue, ...], *, as_json: bool) -> int:
    if as_json:
        print(json.dumps([i.as_dict() for i in issues]))
    else:
        for issue in issues:
            line = issue.line if issue.line is not None else "-"
            print(f"{issue.file}:{line}: {issue.level}: {issue.msg}", file=sys.stderr)
    return 1


def _write_and_emit(plan: AppendPlan, *, as_json: bool) -> int:
    assert plan.log_path is not None and plan.event is not None
    try:
        append_event(plan.log_path, plan.event)
    except Exception as exc:
        issue = Issue(file="<append>", line=None, level="error", msg=f"write failed: {exc}")
        return _emit_issues((issue,), as_json=as_json)
    payload = json.dumps(plan.event.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n"
    if as_json:
        print(json.dumps({
            "id": plan.event.id,
            "path": str(plan.log_path),
            "bytes": len(payload.encode("utf-8")),
        }))
    else:
        print(f"appended {plan.event.id} to {plan.log_path}")
    return 0
