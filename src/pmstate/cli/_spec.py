"""Parser for ``pmstate.yaml`` — the project spec + answers file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import attrs
import yaml

NodeState = Literal["log", "table", "none"]
_VALID_STATES: frozenset[str] = frozenset({"log", "table", "none"})
_VALID_FIELD_TYPES: frozenset[str] = frozenset({"str", "int", "float", "bool"})


class SpecError(ValueError):
    """Raised when ``pmstate.yaml`` is malformed. Carries file + line context."""

    def __init__(self, file: Path, line: int | None, msg: str) -> None:
        self.file = file
        self.line = line
        self.msg = msg
        location = f"{file}:{line}" if line is not None else str(file)
        super().__init__(f"{location}: {msg}")


@attrs.define(frozen=True, slots=True)
class EventSchema:
    """Flat ``field: type`` map for an event-type's payload."""

    fields: dict[str, str]


@attrs.define(frozen=True, slots=True)
class NodeSpec:
    """A single child node in the spec."""

    name: str
    state: NodeState
    view: str | None = None
    reducer: str | None = None


@attrs.define(frozen=True, slots=True)
class TreeSpec:
    """A path in the tree with reducer + child nodes attached."""

    path: str
    reducer: str | None
    children: tuple[NodeSpec, ...]


@attrs.define(frozen=True, slots=True)
class Spec:
    """Top-level pmstate.yaml structure."""

    name: str
    pmstate_version: str
    root: str
    nodes: tuple[TreeSpec, ...]
    events: dict[str, EventSchema]


def parse_spec(path: Path) -> Spec:
    """Parse + validate ``pmstate.yaml`` at ``path``. Raises :class:`SpecError`."""
    if not path.is_file():
        raise SpecError(path, None, "pmstate.yaml not found")
    text = path.read_text(encoding="utf-8")
    try:
        composed = yaml.compose(text)
    except yaml.YAMLError as exc:
        line = _yaml_error_line(exc)
        raise SpecError(path, line, f"invalid YAML: {exc}") from exc
    if composed is None:
        raise SpecError(path, None, "pmstate.yaml is empty")
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise SpecError(path, _node_line(composed), "top-level must be a mapping")
    return _build_spec(path, raw, composed)


def _build_spec(path: Path, raw: dict[str, Any], composed: yaml.Node) -> Spec:
    name = _require_str(path, raw, "name", composed)
    version = _require_str(path, raw, "pmstate_version", composed)
    tree_block = _require_mapping(path, raw, "tree", composed)
    events_block = raw.get("events") or {}
    if not isinstance(events_block, dict):
        raise SpecError(path, _key_line(composed, "events"), "'events' must be a mapping")
    root_name = _require_str(path, tree_block, "root", _key_node(composed, "tree"))
    nodes_raw = tree_block.get("nodes")
    if not isinstance(nodes_raw, list):
        raise SpecError(
            path, _key_line(_key_node(composed, "tree"), "nodes"), "'tree.nodes' must be a list"
        )
    nodes = tuple(
        _build_tree_spec(path, n, _seq_item_node(_key_node(composed, "tree"), "nodes", i))
        for i, n in enumerate(nodes_raw)
    )
    events = {
        evt: _build_event_schema(path, evt, body, _key_node(composed, "events"))
        for evt, body in events_block.items()
    }
    return Spec(name=name, pmstate_version=version, root=root_name, nodes=nodes, events=events)


def _build_tree_spec(path: Path, raw: Any, anchor: yaml.Node | None) -> TreeSpec:
    if not isinstance(raw, dict):
        raise SpecError(path, _node_line(anchor), "tree node must be a mapping")
    node_path = _require_str(path, raw, "path", anchor)
    if not node_path.startswith("/") or node_path == "/":
        raise SpecError(
            path,
            _key_line(anchor, "path"),
            f"path must start with '/' and have a segment: {node_path!r}",
        )
    reducer = raw.get("reducer")
    if reducer is not None and not isinstance(reducer, str):
        raise SpecError(path, _key_line(anchor, "reducer"), "'reducer' must be a string")
    children_raw = raw.get("children")
    if not isinstance(children_raw, list):
        raise SpecError(path, _key_line(anchor, "children"), "'children' must be a list")
    children = tuple(
        _build_node_spec(path, c, _seq_item_node(anchor, "children", i))
        for i, c in enumerate(children_raw)
    )
    _check_unknown_keys(
        path, raw, {"path", "reducer", "children"}, anchor, "tree node"
    )
    return TreeSpec(path=node_path, reducer=reducer, children=children)


def _build_node_spec(path: Path, raw: Any, anchor: yaml.Node | None) -> NodeSpec:
    if not isinstance(raw, dict):
        raise SpecError(path, _node_line(anchor), "child must be a mapping")
    name = _require_str(path, raw, "name", anchor)
    state = raw.get("state", "log")
    if state not in _VALID_STATES:
        raise SpecError(
            path, _key_line(anchor, "state"),
            f"'state' must be one of {sorted(_VALID_STATES)}, got {state!r}",
        )
    view = raw.get("view")
    if view is not None and not isinstance(view, str):
        raise SpecError(path, _key_line(anchor, "view"), "'view' must be a string")
    reducer = raw.get("reducer")
    if reducer is not None and not isinstance(reducer, str):
        raise SpecError(path, _key_line(anchor, "reducer"), "'reducer' must be a string")
    _check_unknown_keys(
        path, raw, {"name", "state", "view", "reducer"}, anchor, "child"
    )
    return NodeSpec(name=name, state=state, view=view, reducer=reducer)


def _build_event_schema(
    path: Path, evt: str, body: Any, anchor: yaml.Node | None
) -> EventSchema:
    if not isinstance(body, dict):
        raise SpecError(path, _key_line(anchor, evt), f"events.{evt} must be a mapping")
    schema = body.get("schema")
    if not isinstance(schema, dict):
        raise SpecError(
            path, _key_line(anchor, evt), f"events.{evt}.schema must be a mapping"
        )
    fields: dict[str, str] = {}
    for fname, ftype in schema.items():
        if not isinstance(fname, str) or not isinstance(ftype, str):
            raise SpecError(
                path, _key_line(anchor, evt),
                f"events.{evt}.schema must map str -> str, got {fname!r}: {ftype!r}",
            )
        if ftype not in _VALID_FIELD_TYPES:
            raise SpecError(
                path, _key_line(anchor, evt),
                f"events.{evt}.schema field {fname!r} has unsupported type {ftype!r}; "
                "valid types: str, int, float, bool",
            )
        fields[fname] = ftype
    return EventSchema(fields=fields)


def coerce_field(value: Any, type_str: str) -> Any:
    """Coerce/validate ``value`` against a spec field type. Pure; no IO.

    Accepts: str, int (rejects bool), float (accepts int), bool (strict).
    Raises ``ValueError`` for unrecognised ``type_str`` and ``TypeError`` for
    type mismatch.
    """
    if type_str == "str":
        if not isinstance(value, str):
            raise TypeError(f"expected {type_str}, got {type(value).__name__}")
        return value
    if type_str == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"expected {type_str}, got {type(value).__name__}")
        return value
    if type_str == "float":
        if isinstance(value, bool):
            raise TypeError(f"expected {type_str}, got {type(value).__name__}")
        if isinstance(value, int):
            return float(value)
        if not isinstance(value, float):
            raise TypeError(f"expected {type_str}, got {type(value).__name__}")
        return value
    if type_str == "bool":
        if not isinstance(value, bool):
            raise TypeError(f"expected {type_str}, got {type(value).__name__}")
        return value
    raise ValueError(f"unsupported field type: {type_str!r}")


def _require_str(path: Path, mapping: dict[str, Any], key: str, anchor: yaml.Node | None) -> str:
    if key not in mapping:
        raise SpecError(path, _node_line(anchor), f"missing required key {key!r}")
    value = mapping[key]
    if not isinstance(value, str) or not value:
        raise SpecError(path, _key_line(anchor, key), f"{key!r} must be a non-empty string")
    return value


def _require_mapping(
    path: Path, mapping: dict[str, Any], key: str, anchor: yaml.Node | None
) -> dict[str, Any]:
    if key not in mapping:
        raise SpecError(path, _node_line(anchor), f"missing required key {key!r}")
    value = mapping[key]
    if not isinstance(value, dict):
        raise SpecError(path, _key_line(anchor, key), f"{key!r} must be a mapping")
    return value


def _check_unknown_keys(
    path: Path, raw: dict[str, Any], allowed: set[str], anchor: yaml.Node | None, what: str
) -> None:
    extras = set(raw) - allowed
    if extras:
        bad = sorted(extras)[0]
        raise SpecError(path, _key_line(anchor, bad), f"unknown {what} key {bad!r}")


def _yaml_error_line(exc: yaml.YAMLError) -> int | None:
    mark = getattr(exc, "problem_mark", None) or getattr(exc, "context_mark", None)
    if mark is None:
        return None
    line: int = mark.line + 1
    return line


def _node_line(node: yaml.Node | None) -> int | None:
    if node is None:
        return None
    line: int = node.start_mark.line + 1
    return line


def _key_node(parent: yaml.Node | None, key: str) -> yaml.Node | None:
    if not isinstance(parent, yaml.MappingNode):
        return parent
    for k, v in parent.value:
        if isinstance(k, yaml.ScalarNode) and k.value == key:
            return v
    return parent


def _key_line(parent: yaml.Node | None, key: str) -> int | None:
    target = _key_node(parent, key)
    return _node_line(target)


def _seq_item_node(parent: yaml.Node | None, key: str, index: int) -> yaml.Node | None:
    seq = _key_node(parent, key)
    if not isinstance(seq, yaml.SequenceNode):
        return seq
    if 0 <= index < len(seq.value):
        return seq.value[index]
    return seq
