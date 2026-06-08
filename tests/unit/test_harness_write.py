"""Tests for the optional write surface on the Claude SDK harness."""

from __future__ import annotations

import json
from pathlib import Path

import anyio
import pytest

from pmstate.adapters.claude_sdk import (
    Harness,
    _build_system_prompt,
    _compute_allowed_tools,
    _make_tool_functions,
)
from pmstate.cli._spec import EventSchema, Spec
from pmstate.node import Node
from pmstate.storage import Log
from pmstate.tree import Tree


@pytest.fixture
def tree(tmp_path: Path) -> Tree:
    log = tmp_path / "state" / "quotes.jsonl"
    quotes = Node("quotes", state=Log(log))
    procurement = Node("procurement", children=[quotes])
    root = Node("active", children=[procurement])
    return Tree("alpha", root=root)


@pytest.fixture
def spec() -> Spec:
    events = {
        "quote.received": EventSchema(
            fields={"vendor": "str", "amount": "int", "currency": "str"}
        ),
        "quote.cancelled": EventSchema(fields={"reason": "str"}),
    }
    return Spec(name="alpha", pmstate_version="0.3.0", root="active", nodes=(), events=events)


def test_default_harness_registers_four_tools(tree: Tree, tmp_path: Path) -> None:
    tools = _make_tool_functions(tree, tmp_path)
    assert len(tools) == 4
    names = [t.name for t in tools]
    assert names == ["list_tree", "get_state", "find_state", "read_log"]


def test_write_enabled_registers_five_tools(tree: Tree, tmp_path: Path, spec: Spec) -> None:
    tools = _make_tool_functions(tree, tmp_path, spec, write_enabled=True)
    assert len(tools) == 5
    assert tools[-1].name == "append_event"


def test_append_event_handler_writes_jsonl(tree: Tree, tmp_path: Path, spec: Spec) -> None:
    tools = {t.name: t for t in _make_tool_functions(tree, tmp_path, spec, write_enabled=True)}
    out = anyio.run(
        tools["append_event"].handler,
        {
            "path": "/procurement/quotes",
            "type": "quote.received",
            "data": {"vendor": "acme", "amount": 100, "currency": "USD"},
            "causationid": "",
        },
    )
    payload = json.loads(out["content"][0]["text"])
    assert payload["ok"] is True
    assert isinstance(payload["id"], str) and payload["id"]
    log_path = tmp_path / "state" / "quotes.jsonl"
    assert log_path.is_file()
    with log_path.open() as f:
        lines = [line for line in f if line.strip()]
    assert len(lines) == 1
    written = json.loads(lines[0])
    assert written["type"] == "pmstate.quote.received"


def test_append_event_handler_validation_failure(
    tree: Tree, tmp_path: Path, spec: Spec
) -> None:
    tools = {t.name: t for t in _make_tool_functions(tree, tmp_path, spec, write_enabled=True)}
    out = anyio.run(
        tools["append_event"].handler,
        {
            "path": "/nonexistent",
            "type": "quote.received",
            "data": {"vendor": "x", "amount": 1, "currency": "USD"},
            "causationid": "",
        },
    )
    assert out.get("isError") is True
    issues = json.loads(out["content"][0]["text"])
    assert any("/nonexistent" in i["msg"] for i in issues)


def test_system_prompt_lists_event_catalog(tree: Tree, tmp_path: Path, spec: Spec) -> None:
    prompt = _build_system_prompt(
        tree, tmp_path, override=None, spec=spec, write_enabled=True
    )
    for evt in spec.events:
        assert evt in prompt


def test_compute_allowed_tools_default() -> None:
    tools = _compute_allowed_tools(write_enabled=False)
    assert len(tools) == 4
    assert "mcp__pmstate__append_event" not in tools


def test_compute_allowed_tools_write_enabled() -> None:
    tools = _compute_allowed_tools(write_enabled=True)
    assert len(tools) == 5
    assert tools[-1] == "mcp__pmstate__append_event"


def test_harness_default_is_backward_compatible(tree: Tree, tmp_path: Path) -> None:
    h = Harness(tree=tree, root_dir=tmp_path)
    assert h.write_enabled is False
    assert h.spec is None


def test_format_event_catalog_empty() -> None:
    from pmstate.adapters.claude_sdk import _format_event_catalog
    empty = Spec(name="x", pmstate_version="0.3.0", root="r", nodes=(), events={})
    assert "No event types" in _format_event_catalog(empty)


def test_base_tool_handlers_callable(tree: Tree, tmp_path: Path) -> None:
    tools = {t.name: t for t in _make_tool_functions(tree, tmp_path)}
    list_out = anyio.run(tools["list_tree"].handler, {"path": "/", "depth": 1})
    assert "content" in list_out
    state_out = anyio.run(tools["get_state"].handler, {"path": "/procurement/quotes"})
    assert "content" in state_out
    find_out = anyio.run(
        tools["find_state"].handler, {"query": "x", "path_glob": "", "max_results": 5}
    )
    assert "content" in find_out
    log_out = anyio.run(
        tools["read_log"].handler, {"path": "/procurement/quotes", "limit": 10}
    )
    assert "content" in log_out


def test_system_prompt_default_omits_catalog(tree: Tree, tmp_path: Path) -> None:
    prompt = _build_system_prompt(tree, tmp_path, override=None)
    assert "Write tool catalog" not in prompt


def test_system_prompt_with_agents_md_and_override(tree: Tree, tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Project context\nDetails.\n", encoding="utf-8")
    prompt = _build_system_prompt(tree, tmp_path, override="Be terse.")
    assert "Project context" in prompt
    assert "Be terse." in prompt


def test_run_with_fake_sdk_captures_allowed_tools(
    tree: Tree, tmp_path: Path, spec: Spec, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that --write Harness emits 5 allowed_tools through ClaudeAgentOptions."""
    from typing import Any
    from unittest.mock import patch

    captured: dict[str, Any] = {}

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeMessage:
        def __init__(self, content: list[Any]) -> None:
            self.content = content

    class _FakeClient:
        def __init__(self, options: Any) -> None:
            captured["options"] = options

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def query(self, _prompt: str) -> None:
            return None

        async def receive_response(self) -> Any:
            yield _FakeMessage([_FakeBlock("ok")])

    from pmstate.adapters import claude_sdk as mod
    monkeypatch.setattr(mod, "AssistantMessage", _FakeMessage)
    monkeypatch.setattr(mod, "TextBlock", _FakeBlock)
    with patch.object(mod, "ClaudeSDKClient", _FakeClient):
        h = Harness(
            tree=tree, root_dir=tmp_path, watch=False,
            spec=spec, write_enabled=True,
        )
        h.run("hello")
    options = captured["options"]
    assert len(options.allowed_tools) == 5
    assert "mcp__pmstate__append_event" in options.allowed_tools
