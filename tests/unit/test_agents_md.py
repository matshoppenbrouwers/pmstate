"""Tests for pmstate.agents_md."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from pmstate import agents_md
from pmstate.agents_md import load_agents_md


def test_present_returns_content(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# hello\n", encoding="utf-8")
    assert load_agents_md(tmp_path) == "# hello\n"


def test_absent_returns_none(tmp_path: Path) -> None:
    assert load_agents_md(tmp_path) is None


def test_unreadable_raises(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("chmod-based unreadable check is POSIX-only")
    p = tmp_path / "AGENTS.md"
    p.write_text("x", encoding="utf-8")
    p.chmod(0o000)
    try:
        with pytest.raises(OSError):
            load_agents_md(tmp_path)
    finally:
        p.chmod(0o644)


def test_mtime_change_invalidates_cache(tmp_path: Path) -> None:
    p = tmp_path / "AGENTS.md"
    p.write_text("v1", encoding="utf-8")
    assert load_agents_md(tmp_path) == "v1"
    time.sleep(0.01)
    p.write_text("v2", encoding="utf-8")
    os.utime(p, (time.time(), time.time() + 1))
    assert load_agents_md(tmp_path) == "v2"


def test_repeated_call_uses_cache(tmp_path: Path) -> None:
    p = tmp_path / "AGENTS.md"
    p.write_text("cached", encoding="utf-8")
    load_agents_md(tmp_path)
    p.write_text("after", encoding="utf-8")
    os.utime(p, (p.stat().st_mtime, p.stat().st_mtime))
    assert load_agents_md(tmp_path) == "cached"


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    agents_md._cache.clear()
