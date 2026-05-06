# pmstate v0.1 Implementation

**Date:** 2026-05-06
**Status:** Planned, pending review
**Goal:** Ship a working pmstate v0.1 that supports one real Laterite process (procurement) end-to-end, in a separate Laterite implementation repo, on the public `pmstate` repo as the dependency.  
**Research:** `_devdocs/research/2026-05-06-pmstate-internal-design.md` (v1 design), `_devdocs/research/2026-05-06-pmstate-external-validation.md` (locked decisions)

---

## Context

pmstate is a Python ≥3.11 framework where a process is modeled as a tree of nodes. Each leaf owns state on disk (append-only JSONL or mutable JSON). One observing LLM agent navigates the tree via four lazy tools. Parents roll up children's *views* (not raw logs) via author reducers, with build-system-style content-hash invalidation. CloudEvents-shaped envelope; ULID-keyed events; `watchfiles`-driven harness; `attrs`-backed `Node` with Pydantic-AI-style positional+kwargs API.

v0.1 success: **one real Laterite procurement process runs end-to-end on the framework.** Framework code lives in the public OSS repo `matshoppenbrouwers/pmstate`; Laterite-specific node definitions, reducers, and Badger harness config live in a *separate* (not-yet-existing) Laterite implementation repo that imports pmstate as a dependency.

### Architecture decision

Four-layer architecture from the v1 design:

1. **Process tree** — hierarchical `Node` values, each with optional `state` (Log/Table) on disk.
2. **Event bus** — JSONL log rows ARE events (CloudEvents-shaped). Filesystem is the substrate.
3. **Deep agent** — observer with four tools (`list_tree`/`get_state`/`find_state`/`read_log`), no spawn/prune.
4. **Harness adapter** — Claude Agent SDK first; protocol explicit so OpenClaw/Hermes/custom can plug in later.

Discipline: library not platform; recursive composability; single `Node` primitive; `Log` and `Table` only.

---

## Code quality standard (applies to every phase)

**Every line of code in this repo is expert-quality, production-grade, and intuitive.** This is OSS infrastructure that other people will read; first impressions are load-bearing. The principles below override "just make it work" when they conflict.

### Mandatory principles

1. **Simpler-but-equally-effective wins.** If a piece of code can be written simpler or more efficiently while remaining *equally or more effective*, take the simpler form. Always. No exceptions for "I already wrote it the other way."
2. **Minimum code necessary, no premature abstraction.** Three similar lines is better than a premature abstraction. No interfaces designed for hypothetical future implementations. No config objects when constructor kwargs work. No registries when a dict works. No factories when `Cls(...)` works. Add abstraction only when a *second* concrete need shows up.
3. **No half-finished implementations.** Either a function does its job completely or it doesn't ship. No `# TODO: handle case X` left in merged code without an issue link AND a passing test that locks in the current behaviour.
4. **Trust internal code; validate at boundaries only.** Validate user-facing inputs (`Node(name=...)`, file paths, event payloads). Don't validate internal-to-internal calls — type hints + tests are the contract.
5. **No defensive programming for impossible cases.** No `if x is None: raise` for values the type system already says aren't `None`. No try/except around code that can't fail. The codebase is small enough that we can read it.
6. **Default to no comments.** Names carry meaning. Add a comment only when it explains *why* something non-obvious is true (a hidden invariant, a workaround, a subtle ordering requirement). Never `# WHAT this code does` — the code already says that. Never `# added for the procurement flow` — git blame says that.
7. **No backwards-compatibility shims, no feature flags, no `_legacy` paths.** It's v0.1. Break things cleanly. Aggressive 0.x versioning is the permission slip.
8. **Type hints are mandatory.** Use modern syntax: `X | None` not `Optional[X]`, `list[T]` not `List[T]`, PEP 695 `type X = ...` aliases when they help. `mypy --strict` (or close to it) on every PR.
9. **Functions ≤ 30 lines (preferred), ≤ 50 lines (hard cap).** Cognitive complexity ≤ 10 (preferred), ≤ 15 (cap). Guard clauses over nested conditionals. Early returns over `else`-stairs.
10. **Specific exception types, never bare `except:`.** Each exception class earns its name (e.g., `EventTooLargeError`, `NodePathError`). Catch the narrowest type that makes sense.

### Style + tooling

- **`ruff` is the formatter and linter.** Settings in `ruff.toml`: line length 100, target-version `py311`, enable `E,F,I,UP,B,SIM,RUF,PL` rule sets (and disable any that fight the framework).
- **`mypy --strict`** in CI. A type error is a build failure, same as a test failure.
- **`pytest`** with `--cov-fail-under=80`. Property tests via `hypothesis` for any code with non-obvious invariants (writer atomicity, ULID uniqueness, cache-key correctness, upcaster chain completion).
- **No top-level `import *`. No wildcard re-exports.** `__init__.py` lists each public name explicitly so navigation tools work.
- **No emojis in code, comments, or commit messages.**

### "Production-grade" check before any phase ships

For each phase, before declaring it Accept-ed, walk through this checklist:

- [ ] Could this be 30% shorter without losing clarity? (If yes, shorten it.)
- [ ] Is every public name self-documenting? (If you wouldn't grok the name in 3 seconds, rename.)
- [ ] Does each public function have a one-line docstring stating the *contract* (input → output, observable side effects)?
- [ ] Is there any code path that's untested? (Either test it or delete it.)
- [ ] Is there any error message a user might see? Does it tell them *what* went wrong AND *what to do*?
- [ ] Does `mypy --strict` pass with zero `# type: ignore`? (Each ignore is a debt; minimise.)
- [ ] If I were a stranger reading this for the first time, would I be impressed or annoyed? (Optimise for impressed.)

If any answer is "no," the phase isn't done. Iterate before merging.

---

## Module Structure

```
pmstate/                                # public OSS repo
├── pyproject.toml                      # uv-managed; Python ≥3.11
├── README.md                           # Backlog.md-style "directory IS product" framing
├── LICENSE                             # MIT (default; see Phase 0 decision)
├── AGENTS.md                           # convention at repo root for OSS users + AI agents
├── .gitignore
├── .session-flow.json                  # already exists
├── _devdocs/                           # already scaffolded
├── src/pmstate/                        # PyPA src-layout: package lives under src/
│   ├── __init__.py                     # __version__, public re-exports
│   ├── node.py                         # Node, attrs-backed
│   ├── tree.py                         # Tree (optional wrapper), spawn/prune
│   ├── storage.py                      # Log, Table, default views
│   ├── envelope.py                     # CloudEvents-shaped Event, ULID gen
│   ├── writer.py                       # append_event, O_APPEND, 4000-byte ceiling
│   ├── reader.py                       # read_events with upcaster chain
│   ├── upcasters.py                    # registry shape + helpers
│   ├── rollup.py                       # cache key, lazy recompute, generic dump
│   ├── tools.py                        # list_tree/get_state/find_state/read_log
│   ├── agents_md.py                    # AGENTS.md loader at tree root
│   └── adapters/
│       ├── __init__.py
│       └── claude_sdk.py               # Harness(tree) using Claude Agent SDK
├── examples/
│   └── procurement/
│       ├── tree.py                     # procurement subtree definition
│       ├── views.py                    # quote_view, lpo_view
│       ├── reducers.py                 # procurement_rollup
│       ├── seed_data.py                # generates synthetic JSONL events
│       └── run.py                      # spawns harness + procurement tree
├── tests/
│   ├── unit/                           # one file per src module
│   ├── integration/
│   │   └── test_procurement_e2e.py     # the v0.1 success-criterion test
│   └── conftest.py                     # tmp_path fixtures, fake-time, etc.
└── .github/workflows/
    └── ci.yml                          # ruff + mypy + pytest on PR + main
```

### Integration points

- **Claude Agent SDK** (`claude-agent-sdk` PyPI): the adapter in `src/pmstate/adapters/claude_sdk.py` consumes the SDK's tool/agent primitives.
- **Filesystem** (`watchfiles`): used by the harness adapter to fire `state.updated` events when leaf JSONL files grow on disk.
- **Public PyPI** (`pmstate` package name): Mats grabs the name in Phase 0 with a 0.0.0 placeholder.
- **Future Laterite repo**: imports `pmstate`, defines procurement-specific node tree + reducers, runs Badger as the harness. **Out of scope for this plan.**

---

## Phase 0: Repo skeleton + PyPI placeholder

Get the foundation right so subsequent phases can iterate fast.

**Files created:**

- `pyproject.toml` — uv-managed, Python ≥3.11, deps: `attrs`, `python-ulid`, `watchfiles`. Dev deps: `pytest`, `pytest-cov`, `hypothesis`, `ruff`, `mypy`, `build`, `twine`.
- `LICENSE` — MIT (default; pushable to Apache 2.0 if Mats prefers patent grant).
- `README.md` — Backlog.md-style framing: lead with "the directory tree IS the process state," show 28-LOC procurement example, end with "open but not supported, one user, API will break, stars welcome." 80–120 lines max.
- `AGENTS.md` — minimal: project overview, build commands, "humans/agents read this first."
- `.github/workflows/ci.yml` — matrix: Python 3.11/3.12/3.13 on Ubuntu; lint + type + test.
- `src/pmstate/__init__.py` — `__version__ = "0.0.1"`, no re-exports yet.
- `tests/conftest.py` — empty for now.
- `ruff.toml`, `mypy.ini` — strict-ish; line length 100.

**Files modified:**

- `.gitignore` — already covers Python; add `_devdocs/research/_scratch/` if we want scratch reports git-ignored (probably keep them tracked for provenance).
- `INDEX.md` (cowork root) — already done.

**Design notes:**

- `pyproject.toml` uses `[project]` table (PEP 621), not Poetry/setup.py. Build backend: `hatchling`.
- LICENSE choice: **MIT**. Most permissive, simplest, OSI-approved. If a v0.2 enterprise user appears with patent concerns, switch to Apache 2.0 then.
- Version starts at `0.0.1` for the placeholder, bumps to `0.1.0` only when Phase 7 succeeds (real procurement runs end-to-end).
- AGENTS.md at the repo root (not just tree root) so contributors and AI tools find it first. Tree-root AGENTS.md is a separate convention added in Phase 4.

**Manual step (Mats):**

- Register `pmstate` on PyPI by uploading the placeholder. Steps:
  1. Create PyPI account at [https://pypi.org/account/register/](https://pypi.org/account/register/) if needed.
  2. From repo root: `uv build` to produce `dist/pmstate-0.0.1.tar.gz` + `.whl`.
  3. `uv publish` (or `twine upload dist/`*) — needs an API token from [https://pypi.org/manage/account/token/](https://pypi.org/manage/account/token/).
  4. Verify at [https://pypi.org/project/pmstate/](https://pypi.org/project/pmstate/).
- Same for TestPyPI first if you want a dry run: `--repository testpypi`.

**Accept:** `pmstate` is reserved on PyPI as version 0.0.1; CI green on a no-op PR; `python -c "import pmstate; print(pmstate.__version__)"` works in a fresh venv after `pip install pmstate`.

**Commit:** `chore: bootstrap pmstate package, CI, and 0.0.1 PyPI placeholder`

---

## Phase 1: Core primitives — `Node`, `Log`, `Table`

The data model. Everything downstream reads from these.

**Files created:**

- `src/pmstate/node.py` — `Node` as `attrs.@define(frozen=True, slots=True)`. Constructor matches the API:
  ```python
  @attrs.define(frozen=True, slots=True)
  class Node:
      name: str
      state: Log | Table | None = None
      view: Callable[[Any], dict] | None = None
      reducer: Callable[[dict[str, dict]], dict] | None = None
      children: tuple[Node, ...] = ()           # tuple for hashability
      description: str | None = None
  ```
  Validators: unique sibling names; `state` must be `Log` or `Table` if set; `view`/`reducer` must be callable if set.
- `src/pmstate/storage.py` — `Log(path, *, view=None)` and `Table(path, *, view=None)`. Both expose `read()` returning the view dict. Default views:
  - `Log` default: `{count, latest, first}`. Reads with bounded buffer.
  - `Table` default: file contents truncated above ~2 KiB or 50 top-level keys.
- `src/pmstate/_paths.py` — internal helpers: `resolve(root, path)` walks `/a/b/c` to a `Node`. Raises `NodePathError` on miss. Slash-separated strings externally; tuple of names internally per Dagster pattern.
- `tests/unit/test_node.py`, `tests/unit/test_storage.py`, `tests/unit/test_paths.py`.

**Files modified:**

- `src/pmstate/__init__.py` — re-export `Node`, `Log`, `Table`.

**Design notes:**

- `Node` is hashable + frozen. Mutation happens via `Tree.spawn`/`prune` (Phase 4) returning a new `Tree` snapshot, not in-place edits. Aligns with Q7's "framework operations, not user-code discipline."
- Wrap user view functions with error capture (Q5 commitment): if view throws, return `{error: str, exception: type, path: str}` instead of raising. The agent sees errors as data.
- Path resolution: `/active/procurement/quotes` is a leading-slash path with name segments. Empty path = root. Root has no name in the path.
- `description` falls back to `view.__doc__` lazily on `list_tree` calls, not at construction time (avoids reading attributes on `view=None` nodes).

**Accept:** Construction of the procurement subtree (just the structure, no data) works in a Python REPL: `Node("procurement", children=[Node("quotes"), Node("lpos"), Node("vendors")])`. `tree.resolve("/procurement/quotes")` returns the right node. Default `Log` view on an empty file returns `{count: 0, latest: None, first: None}`.

**Commit:** `feat(core): Node primitive, Log/Table storage helpers, path resolution`

---

## Phase 2: Event envelope, writer, reader

Lock the wire format. Make events writable + readable safely.

**Files created:**

- `src/pmstate/envelope.py` — `Event` as `attrs.@define`. Fields per the locked envelope (`specversion`, `id`, `source`, `type`, `time`, `subject`, `data`, `causationid`). `Event.new(type, source, data, ...)` factory generates ULID + UTC timestamp. `Event.to_dict()` and `Event.from_dict()` round-trip.
- `src/pmstate/writer.py` — `append_event(log_path: Path, event: Event) -> None`. Enforces 4000-byte serialized line ceiling (raises `EventTooLargeError`). Uses `open(path, "ab")` + single `write()`. Optional `fsync=False` parameter for durability/throughput trade.
- `src/pmstate/reader.py` — `read_events(log_path, *, start=None, end=None, filter=None) -> Iterator[dict]`. Iterates JSONL rows, JSON-decodes, runs each through the upcaster chain (Phase 3 hook), yields. Supports byte-offset cursors for replay.
- `src/pmstate/_ulid.py` — thin wrapper around `python-ulid` so we can swap implementations later.
- `tests/unit/test_envelope.py` — round-trip, ULID uniqueness, time format.
- `tests/unit/test_writer.py` — append, ceiling enforcement, atomicity smoke test (10k single-byte appends, no torn lines).
- `tests/unit/test_reader.py` — iteration, byte-offset replay, idempotency by id.

**Files modified:**

- `src/pmstate/__init__.py` — re-export `Event`, `append_event`, `read_events`, `EventTooLargeError`.

**Design notes:**

- Event factory takes positional `type` and `source`, kwargs for the rest. Mirrors the Pydantic-AI `Agent("model-id", ...)` shape at the event layer.
- ULID provides per-process monotonic ordering inside a millisecond. With one writer per leaf, this gives the per-node ordering requirement (envelope research §3).
- 4000-byte ceiling is a real constraint authors must know about. README + writer docstring document the "reference larger payloads via `subject` + external file" pattern.
- `read_events` returns dicts, not `Event` instances. Reason: upcasters (Phase 3) transform dicts; consumers (rollups, agent tools) expect dicts. Wrapping back into `Event` is a cost without a payoff. Q5's library-not-platform stance.
- Reader supports byte-offset cursors so consumers can resume from exactly where they left off — essential for the future event-bus consumers.

**Accept:** Writing 1000 procurement-shaped events to `quotes.jsonl`, then reading them back, yields 1000 dicts in order with all ULIDs unique. Hypothesis property test: round-trip preserves all fields. Atomicity smoke test: reader never sees partial JSON.

**Commit:** `feat(events): CloudEvents-shaped envelope, ULID-keyed writer, byte-cursor reader`

---

## Phase 3: Schema evolution — upcaster registry

Build the migration discipline before we have any breaking changes.

**Files created:**

- `src/pmstate/upcasters.py` — `Upcaster = Callable[[dict], dict]`. `UpcasterRegistry` with `.register(from_type: str, fn: Upcaster)` and `.upcast(event_dict: dict) -> dict` (chains until current). `default_registry: UpcasterRegistry` module-level singleton; users can also pass a registry to `read_events(registry=...)`.
- `tests/unit/test_upcasters.py` — register one upcaster, read old-type events, verify they emerge as new-type with transformed shape. Multi-step chain test.

**Files modified:**

- `src/pmstate/reader.py` — accepts `registry: UpcasterRegistry | None = None`; defaults to module singleton.
- `src/pmstate/__init__.py` — re-export `UpcasterRegistry`, `default_registry`.
- README — short section: "Schema evolution: additive minor changes need no code; breaking changes register an upcaster." 5 lines + example.

**Design notes:**

- Registry keyed by `type` string. Old-type → new-type transforms are functions; chaining is automatic (loop while `event["type"]` has a registered upcaster).
- No JSON Schema validation as a hard gate (Q5: would fight the duck-typed view philosophy).
- No automatic backward-compat for one release: pmstate v0.1 has no prior versions, so this is the clean-slate point. Future breaking changes register an upcaster; old logs never migrate.

**Accept:** Manual test: write an event with `type="pmstate.quote.received"`, register an upcaster `quote.received → quote.received.v2` adding a new field, read the log, verify all events emerge as v2 with the new field defaulted.

**Commit:** `feat(events): upcaster registry for schema evolution on read`

---

## Phase 4: Rollups, content-hash invalidation, `Tree`, `spawn`/`prune`, AGENTS.md

The framework's most distinctive mechanic + tree mutation + the agent-readable convention file.

**Files created:**

- `src/pmstate/rollup.py`:
  - `compute_view(node: Node, root: Path) -> dict` — returns the node's view. For leaves: reads `state` via its view (default or user-supplied). For internal nodes: collects children's views as a dict `{child_name: child_view}`, applies `node.reducer` if present, else returns the dict directly (generic children dump). Wraps user code with error capture.
  - `cache_key(node, children_view_hashes)` — Hamilton-style: `(node_path, view_fn_code_hash, tuple_of_children_hashes)`. View-fn-code-hash via `hashlib.sha256` of `inspect.getsource(view_fn)` with comments/whitespace stripped; falls back to `id(view_fn)` if source unavailable.
  - `invalidate_on_read(...)` — checks stored fingerprint at `<node>/.pmstate/rollup.json` against a fresh fingerprint; recomputes if mismatch, persists if changed. Self-healing per Q2.
- `src/pmstate/tree.py`:
  - `Tree(name, root)` thin wrapper. Provides `.get(path)`, `.spawn(parent_path, child_node)`, `.prune(path)`. `Tree` operations return a new `Tree` (immutable snapshot pattern), since `Node` is frozen.
  - Validation: spawn refuses duplicate sibling names; prune refuses non-existent paths.
- `src/pmstate/agents_md.py`:
  - `load_agents_md(tree_root: Path) -> str | None` — reads `<root>/AGENTS.md` if present, returns its content. Used by the harness to seed the agent's system prompt.
- `tests/unit/test_rollup.py` — cache hit, cache miss on child change, generic-dump default, reducer happy path, view-error-as-data, nested-call hash gotcha (documented as a known limitation, not a bug).
- `tests/unit/test_tree.py` — get/spawn/prune happy and error paths.

**Files modified:**

- `src/pmstate/__init__.py` — re-export `Tree`, `compute_view`.
- README — note Hamilton-style nested-call hash gotcha; reducer docstring template includes the same warning.

**Design notes:**

- Rollup cache lives at `<node-path>/.pmstate/rollup.json` per node, not in a global cache. Aligns with "filesystem is the substrate, no opaque DB."
- Symmetric `spawn`/`prune` from day one (avoid the pytransitions trap). Both are framework operations on `Tree`; never on `Node` directly (Node is frozen).
- No compile step (avoid the LangGraph trap). Validation happens lazily on `get`/`spawn`/`prune` and on rollup read.
- AGENTS.md content is appended verbatim into the Claude Agent SDK system prompt. No markdown parsing; the LLM reads it raw. Borrows directly from Backlog.md and the broader 2026 industry convention.
- Generic children dump is the default reducer when `node.reducer is None`. Q2 commitment: zero-author-code working tree.

**Accept:** Procurement subtree with one reducer + two custom views: write events to `quotes.jsonl`, call `compute_view` on `procurement` node, get the rolled-up dict. Modify `quotes.jsonl` (append one event), call again, verify cache invalidates and recomputes. `Tree.spawn` adds a node, subsequent `compute_view` includes it. `load_agents_md` returns the file's content when present, `None` when absent.

**Commit:** `feat(rollup): content-hash lazy invalidation, Tree spawn/prune, AGENTS.md loader`

---

## Phase 5: Agent tools surface

The four tools the deep agent uses to navigate the tree.

**Files created:**

- `src/pmstate/tools.py`:
  - `list_tree(tree, path, depth=1) -> list[dict]` — returns `[{name, description, has_state, has_children}, ...]` for direct children. Cheap by construction; never reads state files.
  - `get_state(tree, path) -> dict` — returns the node's view via `compute_view` (Phase 4), with cache invalidation. May trigger rollup recompute.
  - `find_state(tree, query, path_glob=None) -> list[dict]` — grep-style: walks the tree, collects views, returns matches `[{path, snippet}, ...]`. Bounded result size (default 50 hits).
  - `read_log(tree, path, *, start=None, end=None, limit=100, filter=None) -> list[dict]` — bounded raw log access. Mandatory `limit` (max 1000) prevents context blowout. The agent must opt in.
- `tests/unit/test_tools.py` — one test per tool: contract, bounds, error handling.

**Files modified:**

- `src/pmstate/__init__.py` — re-export the four tools.

**Design notes:**

- The "cheap tools can't accidentally be expensive" principle (v1 design Principle 1) materializes here: `list_tree` and `get_state` always return bounded data. `read_log` requires a bounded `limit` and refuses unbounded reads.
- `find_state` walks the tree breadth-first; bound on result count and per-node view size protects context.
- Each tool returns plain dicts/lists, ready to be wrapped by the harness as Claude Agent SDK tools without further translation.

**Accept:** All four tools work against a small in-memory tree. Hypothesis property test: `read_log(limit=N)` never returns more than N rows. Manual test in REPL: `list_tree("/active/procurement")` shows children of procurement; `get_state("/active/procurement")` returns the rolled-up dict; `find_state("blocked")` finds the right nodes.

**Commit:** `feat(tools): list_tree / get_state / find_state / read_log`

---

## Phase 6: Claude Agent SDK harness + filesystem watcher

Wire the agent to a real LLM via the Claude Agent SDK; watch state files for changes.

**Files created:**

- `src/pmstate/adapters/claude_sdk.py`:
  - `Harness(tree, *, model="claude-sonnet-4-6", system=None, watch=True)`.
  - On `Harness(tree).run()`: loads `AGENTS.md` (Phase 4), builds system prompt, registers the four tools as Claude Agent SDK tools, opens an interactive loop or accepts a one-shot prompt.
  - Watcher: `watchfiles.awatch(root)` (or `watch` sync) emits `state.updated` events on file change. Auto-detects `/mnt/c/...` paths and sets `force_polling=True` (envelope research §4).
  - Watcher events trigger cache invalidation in the rollup layer, NOT direct agent prompts. The agent picks them up on its next `get_state` call. (Future: optionally surface as agent context when long-running.)
- `src/pmstate/adapters/__init__.py` — package marker; `Harness` re-exported.
- `tests/integration/test_harness_smoke.py` — instantiate `Harness` with a fake LLM, verify the four tools register and respond. Real-LLM run kept as `examples/`, not test, since it costs money.

**Files modified:**

- `src/pmstate/__init__.py` — `from pmstate.adapters.claude_sdk import Harness as ClaudeHarness` (under a clear name; future adapters get sibling names).
- `pyproject.toml` — add `claude-agent-sdk` as an optional `[project.optional-dependencies]` entry under `claude-sdk`. Keeps the core package SDK-free.

**Design notes:**

- Harness is the FIRST adapter, not the only one. The four tools + the AGENTS.md convention define the pluggable contract; OpenClaw, Hermes, custom harnesses implement against the same surface.
- Watcher runs in a background thread (`watchfiles.watch` sync API in a `threading.Thread`). On change, calls `rollup.invalidate(path)` so the next `get_state` recomputes. No event-stream into the agent for v0.1 — keeps the model simple.
- The `claude-agent-sdk` is an optional extra, not a hard dep. Users on a different harness don't pull it.

**Accept:** Smoke test runs the Harness against a fake LLM and confirms: AGENTS.md is in the system prompt, all four tools are registered, a tool call round-trips. Manual test (run by Mats): real Claude session against a small tree; ask "what's pending in procurement?" and get a coherent answer.

**Commit:** `feat(adapter): Claude Agent SDK harness with watchfiles-based change detection`

---

## Phase 7: Procurement integration smoke + v0.1 release

Prove the framework end-to-end with the v0.1 success-criterion use case.

**Files created:**

- `examples/procurement/tree.py` — the procurement subtree definition (procurement, quotes, lpos, vendors).
- `examples/procurement/views.py` — `quote_view`, `lpo_view`.
- `examples/procurement/reducers.py` — `procurement_rollup`.
- `examples/procurement/seed_data.py` — generates ~50 synthetic events into `examples/procurement/state/quotes.jsonl`, `lpos.jsonl`, `vendors.json`. Reproducible (fixed RNG seed).
- `examples/procurement/run.py` — full end-to-end: builds the tree, runs `Harness(tree).run()`, takes a single prompt argv-style ("what's pending?"), prints the response. Marked "real LLM cost — see README."
- `examples/procurement/AGENTS.md` — describes the procurement domain to the agent (vendor terminology, what "blocked" means, etc.).
- `tests/integration/test_procurement_e2e.py` — runs the example with a fake LLM that exercises all four tools; asserts the rolled-up procurement view matches the expected shape from seeded data.
- `CHANGELOG.md` — `0.1.0 — 2026-MM-DD: First release. Single user (Laterite). API will break. See README for stance.`
- README sections: "Quickstart" (the 28-LOC example, copy-paste runnable from `examples/procurement`), "What's not in v0.1" (defer list from external-validation §6.1).

**Files modified:**

- `src/pmstate/__init__.py` — bump `__version__ = "0.1.0"`.
- `pyproject.toml` — bump version to `0.1.0`.

**Design notes:**

- The `examples/` directory IS the procurement test bed. The Laterite implementation repo, when it later exists, replaces these examples with real Laterite project trees that import pmstate as a dependency.
- The integration test uses a fake LLM (deterministic) so CI stays free. Real-LLM runs are documented manual steps for Mats.
- v0.1.0 release = upload to PyPI. Replaces the 0.0.0 placeholder. Same manual-publish flow as Phase 0.

**Accept:** `pytest tests/integration/test_procurement_e2e.py -v` passes. Manual run of `python examples/procurement/run.py "what is the procurement status?"` against a real Claude session produces a coherent answer that cites at least two of the four tools. `pmstate==0.1.0` installable from PyPI in a fresh venv. README's quickstart is copy-paste runnable.

**Commit:** `release: pmstate 0.1.0 — procurement v0.1 runs end-to-end`

---

## Success Criteria


| Criterion                                    | Measurement                                                                                                             |
| -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| One real Laterite process runs end-to-end    | `examples/procurement/run.py` answers a real question via Claude SDK with all 4 tools in the trace                      |
| Procurement v0.1 example fits the LOC budget | `wc -l examples/procurement/tree.py examples/procurement/views.py examples/procurement/reducers.py` ≤ 50 lines combined |
| Test coverage ≥ 80%                          | `pytest --cov=pmstate --cov-fail-under=80` passes in CI                                                                 |
| `pmstate` reserved on PyPI                   | `pip install pmstate==0.1.0` succeeds in a fresh venv                                                                   |
| Atomic JSONL appends hold under stress       | Hypothesis test: 10k concurrent (in-process) appends, reader sees no torn lines                                         |
| ULID + idempotency holds                     | Property test: writing the same event id twice, reading deduplicates cleanly via the upcaster pipeline                  |
| All 4 tools work + AGENTS.md is loaded       | `tests/integration/test_harness_smoke.py` asserts                                                                       |
| README is approachable                       | A reader can copy-paste the quickstart and have a working tree in <5 minutes                                            |


---

## Explicit non-goals (v0.1)

From external-validation §6.1, recorded for v0.2+ backlog:

- LangGraph checkpointer adapter (`pmstate.adapters.langgraph.LangGraphCheckpointer`).
- `summarize_branch(path)` agent tool (subagent dispatch).
- Brokered transport for sub-second event reactivity.
- `correlation_id` envelope field.
- Concurrent writers per leaf.
- Plugin system / second-user abstractions.
- Stranger-facing docs beyond the README (no docs site, no tutorials).
- Community contributions (PRs declined, issues thanked).

Plus from Phase 7:

- The actual Laterite implementation repo. Lives separately. Imports pmstate. Plan TBD.

---

## References

- Internal v1 design: `_devdocs/research/2026-05-06-pmstate-internal-design.md`
- External validation: `_devdocs/research/2026-05-06-pmstate-external-validation.md`
- Prior-art scratch: `_devdocs/research/_scratch/2026-05-06-prior-art.md`
- Event envelope scratch: `_devdocs/research/_scratch/2026-05-06-event-envelope.md`
- Python ergonomics scratch: `_devdocs/research/_scratch/2026-05-06-python-ergonomics.md`

