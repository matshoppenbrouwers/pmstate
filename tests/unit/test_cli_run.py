"""Tests for ``pmstate run``."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pmstate.cli import main

if TYPE_CHECKING:
    from collections.abc import Generator


_TREE_PY = """\
from pathlib import Path

from pmstate import Node, Tree


def build_tree():
    return Tree("t", root=Node("root"))
"""

_BROKEN_TREE_PY = """\
raise RuntimeError("boom")
"""

_NON_TREE_PY = """\
def build_tree():
    return "not a tree"
"""


def _make_project(tmp_path: Path, tree_src: str = _TREE_PY) -> Path:
    (tmp_path / "pmstate.yaml").write_text("name: t\n")
    (tmp_path / "tree.py").write_text(tree_src)
    return tmp_path


@pytest.fixture
def fake_harness(monkeypatch: pytest.MonkeyPatch) -> Generator[list[str], None, None]:
    captured: list[str] = []

    class _FakeHarness:
        def __init__(self, **kwargs: object) -> None:
            captured.append(f"watch={kwargs.get('watch')}")

        def run(self, prompt: str | None = None) -> str:
            captured.append(f"prompt={prompt}")
            return "fake-reply"

    import pmstate.adapters.claude_sdk as mod

    monkeypatch.setattr(mod, "Harness", _FakeHarness)
    yield captured


def _chdir(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    monkeypatch.chdir(target)


def test_run_happy_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_harness: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path))
    rc = main(["run", "hi"])
    out = capsys.readouterr()
    assert rc == 0
    assert "fake-reply" in out.out
    assert "watch=False" in fake_harness
    assert "prompt=hi" in fake_harness


def test_run_with_watch_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_harness: list[str]
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path))
    rc = main(["run", "--watch", "hi"])
    assert rc == 0
    assert "watch=True" in fake_harness


def test_run_no_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _chdir(monkeypatch, tmp_path)
    rc = main(["run", "hi"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not in a pmstate project" in err


def test_run_broken_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path, _BROKEN_TREE_PY))
    rc = main(["run", "hi"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "RuntimeError" in err
    assert "boom" in err


def test_run_non_tree_return(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path, _NON_TREE_PY))
    rc = main(["run", "hi"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "not Tree" in err


def test_run_missing_prompt_no_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_harness: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    rc = main(["run"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "no prompt" in err


def test_run_prompt_from_stdin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_harness: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    _chdir(monkeypatch, _make_project(tmp_path))
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("piped-prompt\n"))
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    rc = main(["run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "fake-reply" in out
    assert "prompt=piped-prompt" in fake_harness


def test_run_missing_tree_py(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pmstate.yaml").write_text("name: t\n")
    _chdir(monkeypatch, tmp_path)
    rc = main(["run", "hi"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "missing tree.py" in err
