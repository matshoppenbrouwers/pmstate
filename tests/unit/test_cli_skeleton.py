"""Skeleton tests for the pmstate CLI dispatch."""

from __future__ import annotations

import pytest

from pmstate import __version__
from pmstate.cli import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert __version__ in out


def test_help_lists_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for verb in ("init", "validate", "seed", "run"):
        assert verb in out


def test_no_verb_returns_2(capsys: pytest.CaptureFixture[str]) -> None:
    rc = main([])
    assert rc == 2
    assert "init" in capsys.readouterr().out


def test_unknown_verb_argparse_exits_2() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["bogus"])
    assert excinfo.value.code == 2
