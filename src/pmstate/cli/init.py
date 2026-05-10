"""``pmstate init``: scaffold a new project from ``pmstate.yaml``."""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Callable
from importlib import resources
from pathlib import Path
from string import Template

from pmstate.cli._discovery import find_project_root
from pmstate.cli._io import write_file_safe
from pmstate.cli._spec import EventSchema, NodeSpec, Spec, parse_spec

_TEMPLATES_PKG = "pmstate.cli._templates"
_STATE_GITIGNORE = "*\n!.gitignore\n"
_NO_STUBS = "# no stubs declared in pmstate.yaml"

StubFn = Callable[[str], str]


def _read_template(name: str) -> str:
    return (resources.files(_TEMPLATES_PKG) / name).read_text(encoding="utf-8")


def _render_node(node: NodeSpec) -> str:
    name = node.name
    if node.state == "log":
        state_arg = f'state=Log(_S / "{name}.jsonl")'
    elif node.state == "table":
        state_arg = f'state=Table(_S / "{name}.json")'
    else:
        state_arg = ""
    parts = [f'"{name}"']
    if state_arg:
        parts.append(state_arg)
    if node.view:
        parts.append(f"view={node.view}")
    if node.reducer:
        parts.append(f"reducer={node.reducer}")
    return f"Node({', '.join(parts)})"


def _render_tree(spec: Spec) -> str:
    if len(spec.nodes) != 1:
        raise NotImplementedError("multi-subtree specs are not yet supported")
    tree = spec.nodes[0]
    parts = tree.path.lstrip("/").split("/")
    if len(parts) < 2 or parts[0] != spec.root:  # noqa: PLR2004 — root + child minimum
        raise ValueError(
            f"path {tree.path!r} must start with root segment '/{spec.root}/...'"
        )
    parent_name = parts[-1]
    inner_lines = [
        f"                Node(\n"
        f'                    "{parent_name}",\n'
        f"                    children=["
    ]
    for child in tree.children:
        inner_lines.append(f"                        {_render_node(child)},")
    inner_lines.append("                    ],")
    if tree.reducer:
        inner_lines.append(f"                    reducer={tree.reducer},")
    inner_lines.append("                ),")
    nodes_block = "\n".join(inner_lines)
    template = Template(_read_template("tree.py.tmpl"))
    return template.substitute(
        tree_name=spec.name,
        root_name=spec.root,
        nodes_block=nodes_block,
        views_imports=_views_import_line(spec),
        reducers_imports=_reducers_import_line(spec),
    )


def _views_import_line(spec: Spec) -> str:
    names = sorted(_unique_views(spec))
    if not names:
        return "# no view stubs declared"
    return f"from views import {', '.join(names)}"


def _reducers_import_line(spec: Spec) -> str:
    names = sorted(_unique_reducers(spec))
    if not names:
        return "# no reducer stubs declared"
    return f"from reducers import {', '.join(names)}"


def _unique_views(spec: Spec) -> set[str]:
    return {c.view for t in spec.nodes for c in t.children if c.view}


def _unique_reducers(spec: Spec) -> set[str]:
    direct = {c.reducer for t in spec.nodes for c in t.children if c.reducer}
    parents = {t.reducer for t in spec.nodes if t.reducer}
    return direct | parents


def _render_views(spec: Spec) -> str:
    stubs = "\n\n".join(_view_stub(name) for name in sorted(_unique_views(spec))) or _NO_STUBS
    return Template(_read_template("views.py.tmpl")).substitute(
        tree_name=spec.name, view_stubs=stubs
    )


def _render_reducers(spec: Spec) -> str:
    stubs = "\n\n".join(
        _reducer_stub(name) for name in sorted(_unique_reducers(spec))
    ) or _NO_STUBS
    return Template(_read_template("reducers.py.tmpl")).substitute(
        tree_name=spec.name, reducer_stubs=stubs
    )


def _view_stub(name: str) -> str:
    return (
        f"def {name}(events: Iterable[dict[str, Any]]) -> dict[str, Any]:\n"
        f'    """Auto-generated view stub. Replace with real logic."""\n'
        f"    rows = list(events)\n"
        f'    return {{"count": len(rows), "latest": rows[-1] if rows else None}}'
    )


def _reducer_stub(name: str) -> str:
    return (
        f"def {name}(children: dict[str, dict[str, Any]]) -> dict[str, Any]:\n"
        f'    """Auto-generated reducer stub. Replace with real logic."""\n'
        f"    return {{'children': dict(children)}}"
    )


def _render_chat(spec: Spec) -> str:
    return Template(_read_template("chat.py.tmpl")).substitute(tree_name=spec.name)


def _render_agents_md(spec: Spec) -> str:
    return Template(_read_template("agents_md.tmpl")).substitute(tree_name=spec.name)


def _log_leaf_names(spec: Spec) -> list[str]:
    return [c.name for t in spec.nodes for c in t.children if c.state == "log"]


def _render_leaves_dict(spec: Spec) -> str:
    leaves = _log_leaf_names(spec)
    if not leaves:
        return "{}"
    body = "\n".join(f'    "{name}": "state/{name}.jsonl",' for name in leaves)
    return "{\n" + body + "\n}"


def _render_event_subparser(evt_name: str, schema: EventSchema) -> str:
    cmd = evt_name.replace(".", "-")
    var = "_p_" + cmd.replace("-", "_")
    help_str = f'"Append a pmstate.{evt_name} event."'
    out = [
        f'    {var} = sub.add_parser(',
        f'        "{cmd}", help={help_str},',
        '    )',
        f'    {var}.add_argument("--leaf", required=True, choices=list(LEAVES))',
    ]
    for field, ftype in schema.fields.items():
        if ftype == "bool":
            out.append(
                f'    {var}.add_argument('
                f'"--{field}", action=argparse.BooleanOptionalAction, required=True)'
            )
        elif ftype in ("int", "float"):
            out.append(f'    {var}.add_argument("--{field}", required=True, type={ftype})')
        else:
            out.append(f'    {var}.add_argument("--{field}", required=True)')
    out.append(f'    {var}.add_argument("--causationid", default=None)')
    out.append(f'    {var}.add_argument("--subject", default=None)')
    return "\n".join(out)


def _render_event_dispatch(evt_name: str, schema: EventSchema) -> str:
    cmd = evt_name.replace(".", "-")
    # Use getattr so Python keywords (from, class, …) work as schema field names.
    fields_dict = ", ".join(f'"{f}": getattr(args, "{f}")' for f in schema.fields)
    return (
        f'    if args.cmd == "{cmd}":\n'
        f"        append_event(Path(LEAVES[args.leaf]), Event.new(\n"
        f'            type="pmstate.{evt_name}",\n'
        f'            source=f"/manual/{{args.leaf}}",\n'
        f"            data={{{fields_dict}}},\n"
        f"            causationid=args.causationid,\n"
        f"            subject=args.subject,\n"
        f"        ))\n"
        f'        print(f"appended pmstate.{evt_name} to {{args.leaf}}")\n'
        f"        return"
    )


def _render_add_py(spec: Spec) -> str:
    leaves = _log_leaf_names(spec)
    events = list(spec.events.items())
    if not leaves or not events:
        subparsers_block = (
            '    raise SystemExit("nothing to append: '
            'pmstate.yaml needs `events:` and at least one `state: log` leaf")'
        )
        dispatch_block = "    return"
    else:
        subparsers_block = "\n".join(_render_event_subparser(n, s) for n, s in events)
        dispatch_block = "\n".join(_render_event_dispatch(n, s) for n, s in events)
    return Template(_read_template("add.py.tmpl")).substitute(
        tree_name=spec.name,
        leaves_dict=_render_leaves_dict(spec),
        subparsers=subparsers_block,
        dispatch=dispatch_block,
    )


def _generated_files(spec: Spec) -> dict[str, str]:
    return {
        "tree.py": _render_tree(spec),
        "views.py": _render_views(spec),
        "reducers.py": _render_reducers(spec),
        "chat.py": _render_chat(spec),
        "add.py": _render_add_py(spec),
        "AGENTS.md": _render_agents_md(spec),
    }


def _write_all(target: Path, files: dict[str, str], *, force: bool) -> None:
    for relpath, contents in files.items():
        write_file_safe(target / relpath, contents, force=force)


def _write_state_gitignore(target: Path, *, force: bool) -> None:
    state_dir = target / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    gitignore = state_dir / ".gitignore"
    if gitignore.exists() and not force:
        return
    write_file_safe(gitignore, _STATE_GITIGNORE, force=True)


def _copy_pmstate_yaml(spec_path: Path, target: Path, *, force: bool) -> None:
    dest = target / "pmstate.yaml"
    if dest.resolve() == spec_path.resolve():
        return
    write_file_safe(dest, spec_path.read_text(encoding="utf-8"), force=force)


def _existing_names(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set()
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def _append_missing_views(spec: Spec, target: Path) -> None:
    path = target / "views.py"
    have = _existing_names(path)
    new = [n for n in sorted(_unique_views(spec)) if n not in have]
    _append_stubs(path, new, _view_stub)


def _append_missing_reducers(spec: Spec, target: Path) -> None:
    path = target / "reducers.py"
    have = _existing_names(path)
    new = [n for n in sorted(_unique_reducers(spec)) if n not in have]
    _append_stubs(path, new, _reducer_stub)


def _append_stubs(path: Path, names: list[str], stub_fn: StubFn) -> None:
    if not names:
        return
    blocks = "\n\n".join(stub_fn(n) for n in names)
    existing = path.read_text(encoding="utf-8").rstrip() if path.is_file() else ""
    head = f"{existing}\n\n" if existing else ""
    path.write_text(f"{head}{blocks}\n", encoding="utf-8")


def cmd_init(args: argparse.Namespace) -> int:
    """Run the ``pmstate init`` verb."""
    target = Path(args.dir).resolve()
    target.mkdir(parents=True, exist_ok=True)

    if args.upgrade:
        return _do_upgrade(target, force=bool(args.force))

    if args.from_spec is None:
        return _do_default(target)

    return _do_from_spec(Path(args.from_spec).resolve(), target, force=bool(args.force))


def _do_default(target: Path) -> int:
    dest = target / "pmstate.example.yaml"
    if dest.exists():
        print(f"{dest} already exists — edit it and re-run with --from-spec", file=sys.stderr)
        return 1
    contents = _read_template("pmstate.example.yaml")
    write_file_safe(dest, contents)
    print(
        "wrote pmstate.example.yaml — edit and re-run with "
        "--from-spec pmstate.example.yaml"
    )
    return 0


def _do_from_spec(spec_path: Path, target: Path, *, force: bool) -> int:
    try:
        spec = parse_spec(spec_path)
    except Exception as exc:
        print(f"could not parse spec: {exc}", file=sys.stderr)
        return 1
    files = _generated_files(spec)
    if not force:
        for relpath in (*files, "pmstate.yaml"):
            dest = target / relpath
            if dest.resolve() == spec_path.resolve():
                continue
            if dest.exists():
                print(f"refusing to overwrite {dest} (use --force)", file=sys.stderr)
                return 1
    try:
        _write_all(target, files, force=force)
        _copy_pmstate_yaml(spec_path, target, force=force)
        _write_state_gitignore(target, force=force)
    except FileExistsError as exc:
        print(f"refusing to overwrite {exc.args[0]} (use --force)", file=sys.stderr)
        return 1
    print(f"initialized pmstate project at {target}")
    return 0


def _do_upgrade(start: Path, *, force: bool) -> int:
    root = find_project_root(start)
    if root is None:
        print("not in a pmstate project — run `pmstate init` first", file=sys.stderr)
        return 1
    try:
        spec = parse_spec(root / "pmstate.yaml")
    except Exception as exc:
        print(f"could not parse spec: {exc}", file=sys.stderr)
        return 1
    write_file_safe(root / "tree.py", _render_tree(spec), force=True)
    write_file_safe(root / "add.py", _render_add_py(spec), force=True)
    if force:
        write_file_safe(root / "views.py", _render_views(spec), force=True)
        write_file_safe(root / "reducers.py", _render_reducers(spec), force=True)
    else:
        if not (root / "views.py").exists():
            write_file_safe(root / "views.py", _render_views(spec))
        if not (root / "reducers.py").exists():
            write_file_safe(root / "reducers.py", _render_reducers(spec))
        _append_missing_views(spec, root)
        _append_missing_reducers(spec, root)
    if not (root / "AGENTS.md").exists():
        write_file_safe(root / "AGENTS.md", _render_agents_md(spec))
    if not (root / "chat.py").exists():
        write_file_safe(root / "chat.py", _render_chat(spec))
    _write_state_gitignore(root, force=False)
    print(f"upgraded pmstate project at {root}")
    return 0
