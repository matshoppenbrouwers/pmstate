# Changelog

All notable changes to `pmstate` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html) loosely
during the 0.x phase: **breaking changes may ship in any release without
warning until 1.0**.

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
