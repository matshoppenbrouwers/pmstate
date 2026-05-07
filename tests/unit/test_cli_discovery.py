"""Tests for project root discovery."""

from __future__ import annotations

from pathlib import Path

from pmstate.cli._discovery import find_project_root


def test_returns_none_at_filesystem_root() -> None:
    assert find_project_root(Path("/")) is None


def test_finds_marker_in_cwd(tmp_path: Path) -> None:
    (tmp_path / "pmstate.yaml").write_text("name: x\n")
    assert find_project_root(tmp_path) == tmp_path.resolve()


def test_finds_marker_in_parent(tmp_path: Path) -> None:
    (tmp_path / "pmstate.yaml").write_text("name: x\n")
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    assert find_project_root(deep) == tmp_path.resolve()


def test_returns_none_when_not_in_project(tmp_path: Path) -> None:
    assert find_project_root(tmp_path) is None


def test_handles_file_argument(tmp_path: Path) -> None:
    (tmp_path / "pmstate.yaml").write_text("name: x\n")
    f = tmp_path / "anything.txt"
    f.write_text("hi")
    assert find_project_root(f) == tmp_path.resolve()


def test_walks_up_through_symlink(tmp_path: Path) -> None:
    (tmp_path / "pmstate.yaml").write_text("name: x\n")
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    found = find_project_root(link)
    assert found == tmp_path.resolve()
