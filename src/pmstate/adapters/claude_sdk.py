"""Claude Agent SDK harness: wires the pmstate tools into ClaudeSDKClient."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import anyio
import attrs
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    TextBlock,
    create_sdk_mcp_server,
    tool,
)

from pmstate import __version__
from pmstate._watcher import watch
from pmstate.agents_md import load_agents_md
from pmstate.cli._append import prepare_append
from pmstate.cli._spec import Spec
from pmstate.tools import find_state, get_state, list_tree, read_log
from pmstate.tree import Tree
from pmstate.writer import append_event as _append_event

_TOOL_DESCRIPTIONS = """
You have four tools for navigating a process-state tree:

- list_tree(path, depth): list direct children at a path. depth in [1, 3].
- get_state(path): read the rolled-up view at a path. Errors-as-data.
- find_state(query, path_glob, max_results): substring search across views.
- read_log(path, limit, start, end): read raw events from a Log-backed leaf.

The tree is on disk; the directory structure IS the process. Treat each node
view as the truth at that level. Always start with list_tree("/") to orient.
""".strip()

_BASE_TOOLS = (
    "mcp__pmstate__list_tree",
    "mcp__pmstate__get_state",
    "mcp__pmstate__find_state",
    "mcp__pmstate__read_log",
)
_WRITE_TOOL = "mcp__pmstate__append_event"


def _format_event_catalog(spec: Spec) -> str:
    if not spec.events:
        return "No event types declared in the spec."
    lines = ["Write tool catalog (from pmstate.yaml events):"]
    for evt_name, schema in sorted(spec.events.items()):
        fields = ", ".join(f"{k}: {v}" for k, v in schema.fields.items()) or "(no fields)"
        lines.append(f"- {evt_name} → {{{fields}}}")
    return "\n".join(lines)


def _build_system_prompt(
    tree: Tree,
    root_dir: Path,
    override: str | None,
    *,
    spec: Spec | None = None,
    write_enabled: bool = False,
) -> str:
    parts = [_TOOL_DESCRIPTIONS, f'\nProcess tree name: "{tree.name}"']
    agents_md = load_agents_md(root_dir)
    if agents_md:
        parts.append(f"\nProject context (from AGENTS.md):\n\n{agents_md}")
    if write_enabled and spec is not None:
        parts.append("\n" + _format_event_catalog(spec))
    if override:
        parts.append(f"\n\n{override}")
    return "\n".join(parts)


def _compute_allowed_tools(*, write_enabled: bool) -> list[str]:
    tools = list(_BASE_TOOLS)
    if write_enabled:
        tools.append(_WRITE_TOOL)
    return tools


def _make_append_tool(tree: Tree, spec: Spec) -> Any:
    @tool(
        "append_event",
        (
            "Append a single event to a Log leaf. path: a /-prefixed tree path "
            "pointing to a state=log node. type: the unprefixed event type from "
            "the spec (e.g. 'candidate.advanced'). data: an object whose keys "
            "match the event schema. causationid: optional. Idempotency is your "
            "responsibility — retries will produce duplicate events."
        ),
        {"path": str, "type": str, "data": dict, "causationid": str},
    )
    async def _append(args: dict[str, Any]) -> dict[str, Any]:
        causationid = args.get("causationid") or None
        plan = prepare_append(
            spec, tree, args["path"], args["type"], args["data"],
            causationid=causationid,
        )
        if plan.issues:
            return {
                "content": [
                    {"type": "text", "text": json.dumps([i.as_dict() for i in plan.issues])}
                ],
                "isError": True,
            }
        assert plan.log_path is not None and plan.event is not None
        _append_event(plan.log_path, plan.event)
        return {
            "content": [
                {"type": "text", "text": json.dumps({"id": plan.event.id, "ok": True})}
            ]
        }

    return _append


def _make_tool_functions(
    tree: Tree, root_dir: Path, spec: Spec | None = None, *, write_enabled: bool = False
) -> list[Any]:
    @tool("list_tree", "List direct children at a path.", {"path": str, "depth": int})
    async def _list_tree(args: dict[str, Any]) -> dict[str, Any]:
        rows = list_tree(tree, args.get("path", "/"), depth=int(args.get("depth", 1)))
        return {"content": [{"type": "text", "text": json.dumps(rows, default=str)}]}

    @tool("get_state", "Get the rolled-up view at a path.", {"path": str})
    async def _get_state(args: dict[str, Any]) -> dict[str, Any]:
        view = get_state(tree, args["path"], root_dir)
        return {"content": [{"type": "text", "text": json.dumps(view, default=str)}]}

    @tool(
        "find_state",
        "Substring search across node views; optional path_glob filter.",
        {"query": str, "path_glob": str, "max_results": int},
    )
    async def _find_state(args: dict[str, Any]) -> dict[str, Any]:
        rows = find_state(
            tree,
            args["query"],
            root_dir=root_dir,
            path_glob=args.get("path_glob") or None,
            max_results=int(args.get("max_results", 50)),
        )
        return {"content": [{"type": "text", "text": json.dumps(rows, default=str)}]}

    @tool(
        "read_log",
        "Read raw events from a Log-backed leaf.",
        {"path": str, "limit": int},
    )
    async def _read_log(args: dict[str, Any]) -> dict[str, Any]:
        rows = read_log(tree, args["path"], root_dir, limit=int(args.get("limit", 100)))
        return {"content": [{"type": "text", "text": json.dumps(rows, default=str)}]}

    tools: list[Any] = [_list_tree, _get_state, _find_state, _read_log]
    if write_enabled and spec is not None:
        tools.append(_make_append_tool(tree, spec))
    return tools


@attrs.define(frozen=True, slots=True)
class Harness:
    """Claude Agent SDK harness wrapping a :class:`Tree` with the pmstate tools."""

    tree: Tree
    root_dir: Path
    model: str = "claude-sonnet-4-6"
    system: str | None = None
    watch: bool = True
    spec: Spec | None = None
    write_enabled: bool = False

    def run(self, prompt: str | None = None) -> str | None:
        """Run a one-shot prompt (or interactive when ``prompt`` is ``None``)."""
        return anyio.run(self._run_async, prompt)

    async def _run_async(self, prompt: str | None) -> str | None:
        tools = _make_tool_functions(
            self.tree, self.root_dir, self.spec, write_enabled=self.write_enabled
        )
        server = create_sdk_mcp_server(name="pmstate", version=__version__, tools=tools)
        system_prompt = _build_system_prompt(
            self.tree, self.root_dir, self.system,
            spec=self.spec, write_enabled=self.write_enabled,
        )
        options = ClaudeAgentOptions(
            mcp_servers={"pmstate": server},
            allowed_tools=_compute_allowed_tools(write_enabled=self.write_enabled),
            system_prompt=system_prompt,
            model=self.model,
        )

        stop_event: threading.Event | None = None
        if self.watch:
            stop_event = threading.Event()
            watch(self.root_dir, _no_op_change_callback, stop_event=stop_event)

        try:
            async with ClaudeSDKClient(options=options) as client:
                if prompt is None:
                    return None
                await client.query(prompt)
                chunks: list[str] = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                chunks.append(block.text)
                return "".join(chunks) if chunks else ""
            return None
        finally:
            if stop_event is not None:
                stop_event.set()


def _no_op_change_callback(_paths: set[Path]) -> None:
    """Default change callback. Rollup self-invalidates via content hashing."""
    return None


__all__ = [
    "Harness",
    "_build_system_prompt",
    "_compute_allowed_tools",
    "_format_event_catalog",
    "_make_tool_functions",
]
