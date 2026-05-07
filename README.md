# pmstate

[![PyPI](https://img.shields.io/pypi/v/pmstate.svg)](https://pypi.org/project/pmstate/)
[![CI](https://github.com/matshoppenbrouwers/pmstate/actions/workflows/ci.yml/badge.svg)](https://github.com/matshoppenbrouwers/pmstate/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/pmstate.svg)](https://pypi.org/project/pmstate/)

**The directory tree IS the process state.**

A tiny Python library for agent-driven processes that live on the filesystem.
Each node in your process tree owns a slice of state on disk — an append-only
event log or a JSON table. The agent navigates, reads, spawns, and prunes the
same way a human navigates a project folder.

No DSL. No decorators. No compile step. Plain `attrs`-shaped values, plain
JSON on disk, and a four-tool surface any LLM harness can drive.

## Why

Most agent frameworks treat process state as opaque blobs in a vector store
or workflow engine. `pmstate` flips it: the tree of folders and files **is**
the state. That means:

- An agent can `ls`-style introspect what's happening at any depth.
- Branches spawn and die at runtime — no recompile.
- Every event is a CloudEvents-shaped JSON line. Replayable, auditable,
  human-readable.
- A human can `cat` a log file and see exactly what the agent saw.

## Install

```bash
pip install pmstate              # core
pip install pmstate[claude-sdk]  # with the Claude Agent SDK harness
```

## Example: build a hiring tracker in three commands

```bash
# 1. Edit pmstate.yaml to describe your tree (see docs/spec-authoring.md)
pmstate init                                       # writes pmstate.example.yaml
$EDITOR pmstate.example.yaml && mv pmstate.example.yaml pmstate.yaml

# 2. Generate the project (tree.py, views.py, reducers.py, AGENTS.md, …)
pmstate init --from-spec pmstate.yaml my-process
cd my-process

# 3. Seed deterministic events and ask a question
pmstate seed --n 30
pmstate run "what's pending?"
```

That's the full loop. The agent gets four tools (`list_tree`, `get_state`,
`find_state`, `read_log`), reads the rolled-up state, and answers questions
like *"what's blocking us?"*. One custom view, one reducer, the directory
tree on disk **is** the state.

### Driving from Claude Code

`pmstate.yaml` is the source of truth. To translate a natural-language
request into a working tree, point Claude Code (or any orchestrating agent)
at [`docs/spec-authoring.md`](docs/spec-authoring.md). It documents the
schema and includes three worked examples (linear pipeline, kanban, log +
rollup hierarchy) plus a 5-rule recipe.

## Concepts

- **Node** — a named position in the tree. May own `state` (a `Log` or
  `Table`), a `view` (function: events → dict), a `reducer` (function:
  children's views → dict), and `children`.
- **Log** — append-only JSONL of CloudEvents-shaped events.
- **Table** — JSON document for slowly-changing reference data.
- **Tree** — the wrapper that gives you `spawn(parent, child)` and
  `prune(path)` for runtime mutation.
- **Harness** — adapter that wires the four agent tools into an LLM runtime.
  v0.1 ships `ClaudeHarness`; the surface is harness-agnostic.

## Quickstart

**New to pmstate?** Walk through [`QUICKSTART.md`](QUICKSTART.md) — a
10-minute guide that builds a working agent-navigable process tree from
scratch using the CLI. Every concept is explained inline; every step has
runnable code. The original "write the seven files yourself" path is
preserved as an appendix.

The full CLI reference lives at [`docs/cli.md`](docs/cli.md); the
agent-facing spec authoring guide is at
[`docs/spec-authoring.md`](docs/spec-authoring.md).

A larger end-to-end example lives at
[`examples/procurement/`](examples/procurement/). After installing the
`claude-sdk` extra and setting `ANTHROPIC_API_KEY`:

```bash
git clone https://github.com/matshoppenbrouwers/pmstate
cd pmstate
uv sync --all-extras
uv run python -m examples.procurement.seed_data
uv run python examples/procurement/run.py "what is pending in procurement?"
```

## Status

v0.1 alpha. Open but not supported. One user (Laterite). API will break
without warning. PRs not yet accepted. Stars welcome.

## License

MIT.
