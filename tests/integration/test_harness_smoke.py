"""Smoke test for the Claude SDK harness with a faked SDK client."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
import pytest

from pmstate.adapters.claude_sdk import (
    Harness,
    _build_system_prompt,
    _make_tool_functions,
)
from pmstate.envelope import Event
from pmstate.node import Node
from pmstate.storage import Log
from pmstate.tree import Tree
from pmstate.writer import append_event

pytestmark = pytest.mark.integration


def _make_tree(tmp_path: Path) -> Tree:
    log = tmp_path / "active" / "procurement" / "quotes" / "log.jsonl"
    for i in range(3):
        append_event(log, Event.new(type="pmstate.q.r", source="/x", data={"i": i}))
    return Tree(
        "alpha",
        root=Node(
            "active",
            children=[
                Node(
                    "procurement",
                    children=[Node("quotes", state=Log(log))],
                ),
            ],
        ),
    )


def test_system_prompt_includes_tools_and_agents_md(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text(
        "# Procurement context\nVendor terms here.\n", encoding="utf-8"
    )
    tree = _make_tree(tmp_path)
    prompt = _build_system_prompt(tree, tmp_path, override="Be terse.")
    assert "list_tree" in prompt
    assert "get_state" in prompt
    assert "find_state" in prompt
    assert "read_log" in prompt
    assert "Procurement context" in prompt
    assert "Be terse." in prompt
    assert "alpha" in prompt


def test_system_prompt_works_without_agents_md(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    prompt = _build_system_prompt(tree, tmp_path, override=None)
    assert "list_tree" in prompt
    assert "AGENTS.md" not in prompt


def test_four_tools_registered(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    tools = _make_tool_functions(tree, tmp_path)
    assert len(tools) == 4
    names = {getattr(t, "name", None) for t in tools}
    assert names == {"list_tree", "get_state", "find_state", "read_log"}


def test_tool_callable_get_state(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)
    tools = _make_tool_functions(tree, tmp_path)
    by_name = {t.name: t for t in tools}
    out = anyio.run(by_name["get_state"].handler, {"path": "/procurement/quotes"})
    payload = json.loads(out["content"][0]["text"])
    assert payload["count"] == 3


def test_run_with_fake_sdk_client(tmp_path: Path) -> None:
    tree = _make_tree(tmp_path)

    class _FakeBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _FakeMessage:
        def __init__(self, content: list[Any]) -> None:
            self.content = content

    class _FakeClient:
        def __init__(self, options: Any) -> None:
            self.options = options

        async def __aenter__(self) -> _FakeClient:
            return self

        async def __aexit__(self, *_: Any) -> None:
            return None

        async def query(self, prompt: str) -> None:
            self.received = prompt

        async def receive_response(self) -> Any:
            yield _FakeMessage([_FakeBlock("3 pending quotes.")])

    with (
        patch("pmstate.adapters.claude_sdk.ClaudeSDKClient", _FakeClient),
        patch("pmstate.adapters.claude_sdk.AssistantMessage", _FakeMessage),
        patch("pmstate.adapters.claude_sdk.TextBlock", _FakeBlock),
    ):
        harness = Harness(tree=tree, root_dir=tmp_path, watch=False)
        result = harness.run("what's pending?")

    assert result == "3 pending quotes."
