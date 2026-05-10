"""Shared validation core for ``pmstate append`` and the agent write tool."""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import attrs

from pmstate.cli._spec import Spec, coerce_field
from pmstate.cli.validate import Issue
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log, Table
from pmstate.tree import Tree
from pmstate.writer import _EVENT_BYTE_CEILING  # single-source the ceiling

_TYPE_PREFIX = "pmstate."
_STATE_LABELS: dict[type, str] = {Log: "log", Table: "table"}


def normalise_type(type_: str) -> str:
    """Prefix ``type_`` with ``pmstate.`` if not already prefixed."""
    if type_.startswith(_TYPE_PREFIX):
        return type_
    return f"{_TYPE_PREFIX}{type_}"


@attrs.define(frozen=True, slots=True)
class AppendPlan:
    """Outcome of :func:`prepare_append`. Either a writable plan or a list of issues."""

    log_path: Path | None
    event: Event | None
    issues: tuple[Issue, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "log_path": str(self.log_path) if self.log_path is not None else None,
            "event": self.event.to_dict() if self.event is not None else None,
            "issues": [i.as_dict() for i in self.issues],
        }


def _issue(msg: str) -> Issue:
    return Issue(file="<append>", line=None, level="error", msg=msg)


def _resolve_node(tree: Tree, path: str) -> tuple[Node | None, list[Issue]]:
    try:
        node = tree.get(path)
    except (KeyError, ValueError) as exc:
        return None, [_issue(f"unknown path {path!r}: {exc}")]
    return node, []


def _check_log_leaf(node: Node, path: str) -> list[Issue]:
    if not isinstance(node.state, Log):
        state_label = _STATE_LABELS.get(type(node.state), "none")
        return [
            _issue(
                f"node {path} has state={state_label}; append targets state=log leaves"
            )
        ]
    return []


def _resolve_event_key(spec: Spec, type_: str) -> tuple[str | None, list[Issue]]:
    full = normalise_type(type_)
    bare = full[len(_TYPE_PREFIX):]
    if bare in spec.events:
        return bare, []
    suggestions = difflib.get_close_matches(bare, list(spec.events.keys()), n=1)
    suffix = f"; did you mean {suggestions[0]!r}?" if suggestions else ""
    return None, [_issue(f"unknown event type {type_!r}{suffix}")]


def _check_data_keys(data: dict[str, Any], fields: dict[str, str]) -> list[Issue]:
    issues: list[Issue] = []
    for key in data:
        if key not in fields:
            issues.append(_issue(f"unknown data key {key!r}"))
    for key in fields:
        if key not in data:
            issues.append(_issue(f"missing required data key {key!r}"))
    return issues


def _coerce_data(
    data: dict[str, Any], fields: dict[str, str]
) -> tuple[dict[str, Any], list[Issue]]:
    coerced: dict[str, Any] = {}
    issues: list[Issue] = []
    for key, ftype in fields.items():
        if key not in data:
            continue
        try:
            coerced[key] = coerce_field(data[key], ftype)
        except TypeError as exc:
            issues.append(_issue(f"data field {key!r}: {exc}"))
    return coerced, issues


def _build_event(
    evt_key: str,
    coerced: dict[str, Any],
    *,
    path: str,
    source: str | None,
    subject: str | None,
    causationid: str | None,
) -> Event:
    return Event.new(
        type=normalise_type(evt_key),
        source=source if source is not None else path,
        data=coerced,
        subject=subject,
        causationid=causationid,
    )


def _check_event_size(event: Event) -> list[Issue]:
    payload = json.dumps(event.to_dict(), separators=(",", ":"), ensure_ascii=False) + "\n"
    size = len(payload.encode("utf-8"))
    if size > _EVENT_BYTE_CEILING:
        return [_issue(f"event size {size} bytes exceeds {_EVENT_BYTE_CEILING}-byte ceiling")]
    return []


def prepare_append(
    spec: Spec,
    tree: Tree,
    path: str,
    type_: str,
    data: dict[str, Any],
    *,
    source: str | None = None,
    subject: str | None = None,
    causationid: str | None = None,
) -> AppendPlan:
    """Validate inputs and return an :class:`AppendPlan` ready to write or with issues.

    Pure function: no IO. Errors-as-data via the ``issues`` field.
    """
    node, issues = _resolve_node(tree, path)
    if issues or node is None:
        return AppendPlan(log_path=None, event=None, issues=tuple(issues))

    leaf_issues = _check_log_leaf(node, path)
    evt_key, type_issues = _resolve_event_key(spec, type_)
    if leaf_issues or type_issues:
        return AppendPlan(log_path=None, event=None, issues=tuple(leaf_issues + type_issues))

    assert evt_key is not None  # narrowed by type_issues check above
    fields = spec.events[evt_key].fields
    key_issues = _check_data_keys(data, fields)
    coerced, coerce_issues = _coerce_data(data, fields)
    if key_issues or coerce_issues:
        return AppendPlan(
            log_path=None, event=None, issues=tuple(key_issues + coerce_issues)
        )

    event = _build_event(
        evt_key,
        coerced,
        path=path,
        source=source,
        subject=subject,
        causationid=causationid,
    )
    size_issues = _check_event_size(event)
    if size_issues:
        return AppendPlan(log_path=None, event=None, issues=tuple(size_issues))

    assert isinstance(node.state, Log)  # narrowed by _check_log_leaf above
    return AppendPlan(log_path=node.state.path.resolve(), event=event, issues=())
