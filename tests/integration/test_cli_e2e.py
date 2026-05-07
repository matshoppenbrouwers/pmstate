"""End-to-end CLI test: init → validate → seed → (optional) run."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).parent / "fixtures"


def _have_pmstate() -> bool:
    return shutil.which("pmstate") is not None


@pytest.mark.skipif(not _have_pmstate(), reason="pmstate CLI not installed in this venv")
def test_cli_e2e_init_validate_seed(tmp_path: Path) -> None:
    hiring = FIXTURES / "hiring.yaml"
    project = tmp_path / "proj"
    subprocess.run(
        ["pmstate", "init", "--from-spec", str(hiring), str(project)],
        check=True,
    )
    assert (project / "tree.py").is_file()
    assert (project / "AGENTS.md").is_file()

    subprocess.run(["pmstate", "validate"], cwd=project, check=True)

    subprocess.run(
        ["pmstate", "seed", "--n", "30", "--seed", "42"],
        cwd=project,
        check=True,
    )
    total = 0
    for log in (project / "state").rglob("*.jsonl"):
        with log.open() as f:
            total += sum(1 for line in f if line.strip())
    assert total == 30


@pytest.mark.skipif(
    os.environ.get("RUN_LIVE_HARNESS") != "1",
    reason="set RUN_LIVE_HARNESS=1 to invoke the real Claude harness",
)
@pytest.mark.skipif(not _have_pmstate(), reason="pmstate CLI not installed in this venv")
def test_cli_e2e_run_smoke(tmp_path: Path) -> None:
    hiring = FIXTURES / "hiring.yaml"
    project = tmp_path / "proj"
    subprocess.run(
        ["pmstate", "init", "--from-spec", str(hiring), str(project)],
        check=True,
    )
    subprocess.run(["pmstate", "validate"], cwd=project, check=True)
    subprocess.run(
        ["pmstate", "seed", "--n", "30", "--seed", "42"],
        cwd=project,
        check=True,
    )
    result = subprocess.run(
        ["pmstate", "run", "what's in the pipeline?"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip(), "expected non-empty stdout from `pmstate run`"


def test_spec_authoring_sample_parses() -> None:
    """The recorded spec-authoring transcript must parse cleanly."""
    sys.modules.pop("pmstate.cli._spec", None)
    from pmstate.cli._spec import parse_spec

    sample = Path(__file__).parent / "spec_authoring_sample.yaml"
    spec = parse_spec(sample)
    assert spec.name == "hiring-pipeline-q3"
    assert "candidate.added" in spec.events
