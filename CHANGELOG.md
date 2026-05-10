# Changelog

All notable changes to `pmstate` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) loosely
during the 0.x phase: **breaking changes may ship in any release without
warning until 1.0**.

## [0.3.1] — 2026-05-10

Post-implementation polish on the v0.3.0 write surface. No behaviour
changes — the validator and the CLI/harness surfaces are byte-identical
to v0.3.0.

### Internal
- `cli/_append.py` now imports `_EVENT_BYTE_CEILING` from `pmstate.writer`
  instead of redefining it locally — single source of truth.
- Tightened `_resolve_node`'s return type from `tuple[Any, list[Issue]]`
  to `tuple[Node | None, list[Issue]]`. Surfaced (and fixed) a latent
  `node.state.path` mypy gap that the looser typing had hidden.
- Lowercased the state-label in the non-Log error message so it matches
  how users write it in `pmstate.yaml` (`state=table`, not `state=Table`).
- Collapsed `cmd_run`'s if/else around `Harness` construction; the
  defaults already handle the no-write path.

## [0.3.0] — 2026-05-10

The agent write surface. After v0.3 a freshly-init'd project supports
typed event writes from the CLI (`pmstate append`) *and*, opt-in, from
the Claude harness (`pmstate run --write`). Both paths share one
spec-aware validator, so the validation behaviour is byte-identical
across surfaces.

### Added
- `pmstate append PATH --type T --data JSON` — fifth CLI verb. Validates
  the path is a Log leaf, the event type is declared in the spec, the
  payload keys + types match `events.<type>.schema`, and the serialised
  envelope fits the 4000-byte ceiling. Accepts `--data -` to read from
  stdin and `--causationid` / `--subject` / `--source` overrides.
  `--json` mode emits a `{id, path, bytes}` shape on success and the
  same `Issue` array as `pmstate validate --json` on failure.
- `Harness(write_enabled=True, spec=…)` — opt-in fifth tool
  `append_event` whose argument schema is `(path, type, data,
  causationid)` and whose validation reuses the CLI's `prepare_append`
  core. The system prompt under `write_enabled=True` enumerates each
  spec event-name and its field schema so the agent doesn't guess.
- `pmstate run --write` — CLI flag that flips the harness into
  write-enabled mode. Off by default (backward compat); requires a
  parseable `pmstate.yaml` when set.
- `pmstate.cli._append.prepare_append` — shared validation core; pure
  function that returns an `AppendPlan` (errors-as-data, no
  exceptions).

### Fixed
- `_spec.py` field-type parser now rejects unsupported types — the spec
  must use one of `{str, int, float, bool}`. Previously stored any
  string silently, deferring the failure to seed/append time.

### Internal
- Lifted `_build_tree` / `_load_tree_module` from `cli/run.py` to
  `cli/_project.py`; `cli/run.py` keeps a one-line shim so existing
  `from pmstate.cli.run import _build_tree` imports still work.
- MCP server version literal now references `pmstate.__version__` instead
  of a hard-coded string.
- Bumped `pmstate_version` reference in `docs/spec-authoring.md` to
  `"0.3.0"`.

## 0.2.1 - 2026-05-10

Closes the v0.2.0 write-surface gap. After `pmstate init` a project is
now drivable end-to-end without hand-writing helper scripts.

### Added
- Generated `add.py` scaffold — one sub-command per event type declared
  in `pmstate.yaml`, with `--leaf` for destination + one flag per
  `EventSchema` field. Type-aware (`int`, `float`, `bool` → typed
  argparse). Reserved-word-safe (uses `getattr` so `from`, `class`,
  etc. work as field names). Auto-rendered by `init.py` and
  regenerated on `init --upgrade` like `tree.py`.

### Notes
- Empty-spec projects (no events or no Log leaves) get an `add.py`
  that exits with a helpful message.
- Manual edits to `add.py` are overwritten by `init --upgrade` (the
  file is spec-derived; treat it like `tree.py`).

## 0.2.0 - 2026-05-07

First CLI release. The 4-verb `pmstate` command now subsumes the v0.1
hand-written boilerplate. See
[`_devdocs/plans/2026-05-07-pmstate-cli-implementation.md`](./_devdocs/plans/2026-05-07-pmstate-cli-implementation.md)
for the design.

### Added
- `pmstate init` — scaffold a project from a `pmstate.yaml` spec. Three
  modes: default (writes `pmstate.example.yaml`), `--from-spec PATH`
  (renders `tree.py`, `views.py`, `reducers.py`, `chat.py`, `AGENTS.md`,
  `state/.gitignore`), and `--upgrade` (refresh-in-place, idempotent).
- `pmstate validate [--strict] [--json]` — five baseline checks (spec
  parses, tree imports, `build_tree()` returns `Tree`,
  `compute_view_at("/")` doesn't raise, `AGENTS.md` present). `--strict`
  shells out to `mypy`/`ruff` if available; `--json` emits structured
  issues.
- `pmstate seed [--n N] [--seed K] [--force]` — deterministic event
  generation across all Log leaves, driven by `events:` in the spec.
- `pmstate run [PROMPT] [--watch | --no-watch]` — thin wrapper over the
  Claude Agent SDK harness. Default is `--no-watch`.
- `pmstate.yaml` schema (v1) anchored on `name`, `pmstate_version`,
  `tree.{root,nodes}`, and `events.<type>.schema`. Authored either by
  hand or by an orchestrating agent following
  [`docs/spec-authoring.md`](./docs/spec-authoring.md).
- `docs/cli.md` — CLI reference (verbs, flags, exit codes).
- `docs/spec-authoring.md` — the load-bearing agent guide for
  translating natural language into a valid `pmstate.yaml` (three worked
  examples + the 5-rule recipe + common pitfalls).
- `examples/procurement/pmstate.yaml` — demonstrative spec that *would*
  generate the existing procurement example.
- New top-level dependency: `pyyaml>=6.0`.

### Changed
- `README.md` and `QUICKSTART.md` rewritten around the CLI flow. The
  v0.1 manual flow is preserved as a `QUICKSTART.md` appendix.
- Scaffolded `AGENTS.md` now ships with `## Operating this tree` and
  `## Modifying the tree` sections so any harness reads them
  automatically.

## 0.1.1 - 2026-05-07

Documentation-only release. No code changes.

### Added
- `QUICKSTART.md` — a 10-minute layman-friendly tutorial that builds a
  research-project tracker (todos, notes, decisions) from scratch, with
  six embedded mermaid diagrams: the directory-IS-state mental model,
  the resulting tree shape, the event lifecycle, the agent's tool-call
  sequence, the rollup data flow, and three "how a tree evolves"
  snapshots showing event accumulation and runtime spawn.
- README now points the layman path at `QUICKSTART.md` first; the
  procurement example remains the richer reference.

## 0.1.0 - 2026-05-06

First real release. Single-user alpha (Laterite procurement). API will
break without warning. PRs not yet accepted; stars welcome.

### Added
- `Node`, `Tree` — immutable, attrs-backed process-tree primitives with
  runtime `spawn`/`prune`.
- `Log`, `Table` — append-only JSONL and JSON-document storage with
  default views and errors-as-data.
- `Event` — CloudEvents 1.0-shaped envelope, ms-precision UTC time,
  ULID-based `id`, dotted `type` regex, optional `subject`/`causationid`.
- `append_event` — atomic single-line writer with a 4000-byte ceiling.
- `read_events` — streaming JSONL reader with byte-cursor replay,
  predicate filter, and upcaster-registry hook.
- `UpcasterRegistry` — schema evolution at read time, cycle-detected.
- `compute_view` / `compute_view_at` — lazy rollup with content-hash cache
  invalidation persisted at `<node>/.pmstate/rollup.json`.
- Four agent-facing tools: `list_tree`, `get_state`, `find_state`,
  `read_log`, all bounded and JSON-serialisable.
- `ClaudeHarness` — Claude Agent SDK adapter wiring the four tools as MCP
  tools, building a system prompt from `AGENTS.md` and the tool surface.
- `examples/procurement/` — 49-LOC reference flow with views, reducer,
  tree, AGENTS.md, deterministic seed-data generator, and a real-LLM
  runner.
- 173 tests, ≥ 98 % coverage gate, ruff + mypy strict in CI.
