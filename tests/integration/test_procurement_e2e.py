"""End-to-end procurement test with a fake LLM that exercises all four tools."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
import pytest

import examples.procurement.seed_data as seed_module
import examples.procurement.tree as tree_module
from pmstate import compute_view_at
from pmstate.adapters.claude_sdk import Harness, _make_tool_functions

pytestmark = pytest.mark.integration


def _seed(target_root: Path) -> None:
    state_dir = target_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(seed_module, "STATE_DIR", state_dir):
        seed_module.main()


def _build_tree(target_root: Path) -> Any:
    state_dir = target_root / "state"
    with patch.object(tree_module, "_S", state_dir):
        importlib.reload(tree_module)
        return tree_module.build_tree()


def test_all_four_tools_get_called(tmp_path: Path) -> None:
    _seed(tmp_path)
    tree = _build_tree(tmp_path)

    tools = {t.name: t for t in _make_tool_functions(tree, tmp_path)}
    assert set(tools) == {"list_tree", "get_state", "find_state", "read_log"}

    list_out = anyio.run(tools["list_tree"].handler, {"path": "/", "depth": 2})
    assert "procurement" in list_out["content"][0]["text"]

    state_out = anyio.run(tools["get_state"].handler, {"path": "/procurement"})
    assert "open_quotes" in state_out["content"][0]["text"]

    find_out = anyio.run(
        tools["find_state"].handler,
        {"query": "open_quotes", "path_glob": "*procurement*", "max_results": 5},
    )
    assert "procurement" in find_out["content"][0]["text"]

    log_out = anyio.run(
        tools["read_log"].handler,
        {"path": "/procurement/quotes", "limit": 5},
    )
    assert "pmstate.quote.received" in log_out["content"][0]["text"]


def test_rolled_up_view_matches_seed_distribution(tmp_path: Path) -> None:
    _seed(tmp_path)
    tree = _build_tree(tmp_path)
    view = compute_view_at(tree, "/procurement", tmp_path)
    assert view == {"open_quotes": 15, "open_lpos": 10, "blocked": True}


def test_harness_run_with_fake_sdk(tmp_path: Path) -> None:
    _seed(tmp_path)
    tree = _build_tree(tmp_path)

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
            yield _FakeMessage([_FakeBlock("15 pending quotes; 10 LPOs issued; blocked.")])

    with (
        patch("pmstate.adapters.claude_sdk.ClaudeSDKClient", _FakeClient),
        patch("pmstate.adapters.claude_sdk.AssistantMessage", _FakeMessage),
        patch("pmstate.adapters.claude_sdk.TextBlock", _FakeBlock),
    ):
        harness = Harness(tree=tree, root_dir=tmp_path, watch=False)
        result = harness.run("status?")

    assert result == "15 pending quotes; 10 LPOs issued; blocked."
