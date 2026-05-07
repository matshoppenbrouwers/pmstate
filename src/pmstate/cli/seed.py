"""``pmstate seed``: deterministic event generation for Log leaves."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path
from typing import Any

from pmstate.cli._discovery import find_project_root
from pmstate.cli._spec import EventSchema, Spec, parse_spec
from pmstate.cli.run import _build_tree
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log
from pmstate.tree import Tree
from pmstate.writer import append_event

_DEFAULT_SEED = 42
_FROZEN_TIME = "2026-05-07T00:00:00.000Z"


def cmd_seed(args: argparse.Namespace) -> int:
    """Generate ``args.n`` deterministic events distributed across Log leaves."""
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
    leaves = _collect_log_leaves(tree)
    if not leaves:
        print("no Log leaves to seed")
        return 0
    if not _state_is_writable(root, force=bool(args.force)):
        print(
            f"state/ contains existing files at {root / 'state'} — pass --force to overwrite",
            file=sys.stderr,
        )
        return 1
    if not spec.events:
        print("no event types declared in spec")
        return 0
    seed_value = args.seed if args.seed is not None else _DEFAULT_SEED
    rng = random.Random(seed_value)
    total = _seed_events(rng, spec, leaves, n=int(args.n), force=bool(args.force))
    print(f"seeded {total} events across {len(leaves)} leaves")
    return 0


def _collect_log_leaves(tree: Tree) -> list[tuple[str, Path]]:
    """Walk the tree and return ``(leaf-name, absolute-log-path)`` for each Log leaf."""
    out: list[tuple[str, Path]] = []
    _walk(tree.root, out)
    return out


def _walk(node: Node, out: list[tuple[str, Path]]) -> None:
    if isinstance(node.state, Log):
        out.append((node.name, node.state.path.resolve()))
    for child in node.children:
        _walk(child, out)


def _state_is_writable(root: Path, *, force: bool) -> bool:
    state = root / "state"
    if not state.exists():
        return True
    junk = [
        p
        for p in state.rglob("*")
        if p.is_file() and p.name not in {".gitignore", ".gitkeep"}
    ]
    return force or not junk


def _seed_events(
    rng: random.Random,
    spec: Spec,
    leaves: list[tuple[str, Path]],
    *,
    n: int,
    force: bool,
) -> int:
    if force:
        for _, path in leaves:
            path.unlink(missing_ok=True)
    if n <= 0:
        return 0
    event_types = list(spec.events.items())
    for i in range(n):
        leaf_name, leaf_path = leaves[i % len(leaves)]
        evt_name, schema = _pick_event(rng, leaf_name, event_types)
        append_event(leaf_path, _build_event(rng, evt_name, schema, leaf_name, i))
    return n


def _pick_event(
    rng: random.Random, leaf_name: str, event_types: list[tuple[str, EventSchema]]
) -> tuple[str, EventSchema]:
    matches = [(n, s) for n, s in event_types if n.startswith(f"{leaf_name}.")]
    pool = matches or event_types
    return rng.choice(pool)


def _build_event(
    rng: random.Random, evt_name: str, schema: EventSchema, leaf_name: str, index: int
) -> Event:
    data = {field: _gen_value(rng, field, ftype, index) for field, ftype in schema.fields.items()}
    return Event(
        id=f"seed-{index:06d}",
        source=f"/seed/{leaf_name}",
        type=f"pmstate.{evt_name}",
        time=_FROZEN_TIME,
        data=data,
    )


def _gen_value(rng: random.Random, field: str, ftype: str, index: int) -> Any:
    if ftype == "str":
        return f"{field}-{index}"
    if ftype == "int":
        return rng.randint(0, 100)
    if ftype == "float":
        return round(rng.random() * 100, 4)
    if ftype == "bool":
        return rng.choice([True, False])
    return f"{field}-{index}"
