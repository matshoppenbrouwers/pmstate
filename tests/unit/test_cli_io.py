"""Tests for ``write_file_safe``."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pmstate.cli._io import write_file_safe


def test_writes_new_file(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    write_file_safe(p, "hello")
    assert p.read_text() == "hello"


def test_creates_parent_dirs(tmp_path: Path) -> None:
    p = tmp_path / "a" / "b" / "c" / "x.txt"
    write_file_safe(p, "hi")
    assert p.read_text() == "hi"


def test_refuses_on_collision(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("original")
    with pytest.raises(FileExistsError):
        write_file_safe(p, "new")
    assert p.read_text() == "original"


def test_force_overwrites(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("original")
    write_file_safe(p, "new", force=True)
    assert p.read_text() == "new"


def test_mid_write_failure_leaves_original_intact(tmp_path: Path) -> None:
    p = tmp_path / "x.txt"
    p.write_text("original")

    real_replace = __import__("os").replace

    def boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated mid-write failure")

    with patch("pmstate.cli._io.os.replace", side_effect=boom), pytest.raises(OSError):
        write_file_safe(p, "new", force=True)
    assert p.read_text() == "original"
    assert not (tmp_path / "x.txt.tmp").exists()
    assert real_replace is __import__("os").replace
