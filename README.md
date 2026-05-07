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

## Example: a procurement flow in 28 lines

```python
from pmstate import Node, Log, Table, Tree
from pmstate import ClaudeHarness

def quote_view(events):
    """Vendor quotes received and pending approval."""
    pending = [e for e in events if e["type"] == "quote.received"
               and not any(a["data"]["quote_id"] == e["id"]
                           for a in events if a["type"] == "quote.approved")]
    return {"pending_count": len(pending), "latest": pending[-1] if pending else None}

def procurement_rollup(children):
    return {
        "open_quotes": children["quotes"]["pending_count"],
        "open_lpos":   children["lpos"]["count"],
        "blocked":     children["quotes"]["pending_count"] > 5,
    }

procurement = Node(
    "procurement",
    description="Vendor quotes, LPOs, approvals.",
    reducer=procurement_rollup,
    children=[
        Node("quotes", state=Log("state/quotes.jsonl"), view=quote_view),
        Node("lpos",   state=Log("state/lpos.jsonl")),
        Node("vendors", state=Table("state/vendors.json")),
    ],
)

tree = Tree("project_alpha", root=Node("active", children=[procurement]))
ClaudeHarness(tree).run()
```

That is the full procurement flow. One custom view, one reducer, three leaves.
The agent gets four tools (`list_tree`, `get_state`, `find_state`,
`read_log`), discovers the structure on its own, and answers questions like
*"what's blocking us?"* by reading the rolled-up state.

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
scratch (no procurement domain knowledge required). Layman-friendly: every
concept is explained inline, every step has runnable code.

Already comfortable? A larger end-to-end example lives at
[`examples/procurement/`](examples/procurement/). After installing the
`claude-sdk` extra and setting `ANTHROPIC_API_KEY`:

```bash
git clone https://github.com/matshoppenbrouwers/pmstate
cd pmstate
uv sync --all-extras
uv run python -m examples.procurement.seed_data
uv run python examples/procurement/run.py "what is pending in procurement?"
```

The agent navigates the procurement subtree, calls the four pmstate tools,
and answers from the rolled-up view. Costs a few cents per run.

## Status

v0.1 alpha. Open but not supported. One user (Laterite). API will break
without warning. PRs not yet accepted. Stars welcome.

## License

MIT.
