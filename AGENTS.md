# AGENTS.md — pmstate

Humans and AI agents read this first.

`pmstate` is a tiny Python library: **the directory tree IS the process state**.
Each node owns a slice of state on disk (an append-only event log or a JSON
table). An agent navigates the tree the same way a human navigates a project
folder — it reads, writes, spawns child branches, and prunes finished work.

## Build & test

```bash
uv sync --all-extras
uv run pytest
uv run ruff check .
uv run mypy src
uv build
```

Pre-commit (optional):

```bash
uv run pre-commit install
```

## Layout

- `src/pmstate/` — library code
- `tests/` — pytest suite (≥ 80 % coverage gate)
- `examples/procurement/` — the v0.1 reference flow
- `_devdocs/` — design notes, plans, research (for humans + agents working on
  the library itself, not for end users)

## Status

v0.1 alpha. API will break without warning. PRs not
yet accepted; stars welcome.
