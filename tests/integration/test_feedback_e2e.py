"""End-to-end test for the generic feedback example.

Proves the multi-source rollup at ``/feedback`` aggregates both leaves and that
appending a ``feedback.resolved`` event reactively moves one item from ``open``
to ``resolved`` (cache invalidates via the children content hash).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import anyio
import pytest

import examples.feedback.seed_data as seed_module
import examples.feedback.tree as tree_module
from pmstate import Event, append_event, compute_view_at
from pmstate.adapters.claude_sdk import _make_tool_functions

pytestmark = pytest.mark.integration


def _seed(target_root: Path) -> None:
    state_dir = target_root / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    with patch.object(seed_module, "STATE_DIR", state_dir):
        seed_module.main()


def _build_tree(target_root: Path) -> Any:
    # Patch the module-level state dir (read at call time) so build_tree points
    # at the isolated tmp dir. No importlib.reload: reloading re-runs the module
    # body and resets _S back to the real, gitignored examples/feedback/state.
    state_dir = target_root / "state"
    with patch.object(tree_module, "_S", state_dir):
        return tree_module.build_tree()


def _capture(leaf: str, fid: str, severity: str) -> Event:
    return Event.new(
        type="pmstate.feedback.captured",
        source=f"/feedback/{leaf}",
        data={"feedback_id": fid, "source": leaf, "severity": severity,
              "summary": "x"},
    )


def test_rolled_up_view_matches_seed_distribution(tmp_path: Path) -> None:
    _seed(tmp_path)
    tree = _build_tree(tmp_path)
    view = compute_view_at(tree, "/feedback", tmp_path)
    assert view == {
        "open": 20,
        "triaged": 10,
        "resolved": 0,
        "by_severity": {"low": 5, "medium": 5, "high": 6, "critical": 4},
        "by_source": {"web": 12, "chat": 8},
    }
    assert sum(view["by_severity"].values()) == view["open"]


def test_get_state_tool_returns_rollup(tmp_path: Path) -> None:
    _seed(tmp_path)
    tree = _build_tree(tmp_path)
    tools = {t.name: t for t in _make_tool_functions(tree, tmp_path)}

    out = anyio.run(tools["get_state"].handler, {"path": "/feedback"})
    text = out["content"][0]["text"]
    assert "by_source" in text
    assert "by_severity" in text


def test_resolved_append_moves_one_item_open_to_resolved(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    web_log = state_dir / "web.jsonl"

    n = 5
    ids = [f"f{i}" for i in range(n)]
    for fid in ids:
        append_event(web_log, _capture("web", fid, "high"))

    tree = _build_tree(tmp_path)
    before = compute_view_at(tree, "/feedback", tmp_path)
    assert before["open"] == n
    assert before["resolved"] == 0

    append_event(web_log, Event.new(
        type="pmstate.feedback.resolved",
        source="/feedback/web",
        data={"feedback_id": ids[0], "resolution": "fixed"},
    ))

    tree = _build_tree(tmp_path)
    after = compute_view_at(tree, "/feedback", tmp_path)
    assert after["open"] == n - 1
    assert after["resolved"] == 1
    assert after["by_source"]["web"] == n - 1
