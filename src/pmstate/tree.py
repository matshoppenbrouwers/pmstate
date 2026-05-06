"""Tree wrapper providing runtime spawn/prune over an immutable Node graph."""

from __future__ import annotations

import attrs

from pmstate._paths import NodePathError, parse
from pmstate.node import Node


@attrs.define(frozen=True, slots=True)
class Tree:
    """Named, immutable wrapper around a root :class:`Node` with spawn/prune."""

    name: str
    root: Node

    def get(self, path: str) -> Node:
        """Return the node at ``path``. Delegates to :meth:`Node.find`."""
        return self.root.find(path)

    def spawn(self, parent_path: str, child: Node) -> Tree:
        """Return a new ``Tree`` with ``child`` added under ``parent_path``."""
        parts = parse(parent_path)
        new_root = _add_child(self.root, parts, child)
        return Tree(name=self.name, root=new_root)

    def prune(self, path: str) -> Tree:
        """Return a new ``Tree`` with the node at ``path`` removed."""
        parts = parse(path)
        if not parts:
            raise NodePathError(path, "cannot prune the root")
        new_root = _remove_child(self.root, parts)
        return Tree(name=self.name, root=new_root)


def _add_child(node: Node, parts: tuple[str, ...], new_child: Node) -> Node:
    if not parts:
        existing_names = {c.name for c in node.children}
        if new_child.name in existing_names:
            raise ValueError(f"duplicate sibling name {new_child.name!r}")
        return attrs.evolve(node, children=(*node.children, new_child))
    head, *tail = parts
    for i, child in enumerate(node.children):
        if child.name == head:
            new_descendant = _add_child(child, tuple(tail), new_child)
            new_children = (*node.children[:i], new_descendant, *node.children[i + 1 :])
            return attrs.evolve(node, children=new_children)
    raise NodePathError("/" + "/".join(parts), f"no child named {head!r} under {node.name!r}")


def _remove_child(node: Node, parts: tuple[str, ...]) -> Node:
    head, *tail = parts
    for i, child in enumerate(node.children):
        if child.name != head:
            continue
        if not tail:
            new_children = (*node.children[:i], *node.children[i + 1 :])
            return attrs.evolve(node, children=new_children)
        new_descendant = _remove_child(child, tuple(tail))
        new_children = (*node.children[:i], new_descendant, *node.children[i + 1 :])
        return attrs.evolve(node, children=new_children)
    raise NodePathError("/" + "/".join(parts), f"no child named {head!r} under {node.name!r}")
