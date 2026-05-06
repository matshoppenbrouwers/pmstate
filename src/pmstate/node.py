"""The Node primitive: a named position in the process tree."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import attrs

from pmstate._paths import NodePathError, parse
from pmstate.storage import Log, Table

State = Log | Table
NodeView = Callable[..., dict[str, Any]]
NodeReducer = Callable[[dict[str, dict[str, Any]]], dict[str, Any]]


def _validate_name(_inst: Node, _attr: attrs.Attribute[str], value: str) -> None:
    if not value:
        raise ValueError("Node name must be non-empty")
    if "/" in value:
        raise ValueError(f"Node name {value!r} must not contain '/'")


def _children_converter(value: Iterable[Node] | tuple[Node, ...]) -> tuple[Node, ...]:
    children = tuple(value)
    seen: set[str] = set()
    for child in children:
        if child.name in seen:
            raise ValueError(f"duplicate sibling name {child.name!r}")
        seen.add(child.name)
    return children


def _validate_callable(
    _inst: Node, attr: attrs.Attribute[Any], value: Callable[..., Any] | None
) -> None:
    if value is not None and not callable(value):
        raise TypeError(f"{attr.name} must be callable or None")


@attrs.define(frozen=True, slots=True)
class Node:
    """A named position in the process tree. May own state, a view, a reducer, and children."""

    name: str = attrs.field(validator=_validate_name)
    state: State | None = attrs.field(default=None, kw_only=True)
    view: NodeView | None = attrs.field(default=None, kw_only=True, validator=_validate_callable)
    reducer: NodeReducer | None = attrs.field(
        default=None, kw_only=True, validator=_validate_callable
    )
    children: tuple[Node, ...] = attrs.field(
        default=(), kw_only=True, converter=_children_converter
    )
    description: str | None = attrs.field(default=None, kw_only=True)

    @property
    def effective_description(self) -> str | None:
        """Return ``description`` if set, else ``view.__doc__``'s first line, else ``None``."""
        if self.description is not None:
            return self.description
        if self.view is not None and self.view.__doc__:
            return self.view.__doc__.strip().splitlines()[0].strip()
        return None

    def find(self, path: str) -> Node:
        """Walk the subtree to ``path``. Raises :class:`NodePathError` on miss."""
        parts = parse(path)
        current = self
        for segment in parts:
            for child in current.children:
                if child.name == segment:
                    current = child
                    break
            else:
                raise NodePathError(path, f"no child named {segment!r} under {current.name!r}")
        return current
