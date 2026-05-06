# pmstate — external validation

**Date:** 2026-05-06
**Status:** Research complete; 8 open decisions resolved (see §6). Synthesizes three parallel research streams (prior art, event envelope, Python ergonomics) against the v1 internal design.
**Companion docs:**
- `2026-05-06-pmstate-internal-design.md` — internal v1 design (Q1–Q7 resolved)
- `_scratch/2026-05-06-prior-art.md` — full prior-art survey
- `_scratch/2026-05-06-event-envelope.md` — full envelope research
- `_scratch/2026-05-06-python-ergonomics.md` — full ergonomics research

---

## 1. Headline

The v1 design holds up against external validation. Three concrete refinements, one positioning correction, one borrowable interop win:

1. **Envelope:** adopt CloudEvents JSON attribute names (rename pass; no SDK dep). Free interop, stable vocabulary.
2. **Ergonomic template:** model `Node(...)` after Pydantic-AI's `Agent(...)` shape (positional name + progressive kwargs). Internally implement as `attrs.@define`. Drop the explicit `Tree` wrapper for small examples — a `Node` is a valid root.
3. **Schema evolution:** fold `version` into `type` as `.vN` suffix (Greg Young pattern + CloudEvents idiom in one). Upcaster registry on the reader.
4. **Positioning correction:** "filesystem is the substrate" is **not novel** in 2026 (Backlog.md, Letta Filesystem, Anthropic Skills, deepagents all on this train). Pmstate's actual novel claim is the *combination*: tree-of-nodes-with-per-leaf-JSONL-where-rows-ARE-events-with-content-hash-parent-rollup-readable-by-one-observing-agent. Genuinely unoccupied territory.
5. **Free interop bridge:** Hamilton's cache-key shape is structurally identical to pmstate's rollup-invalidation mechanic — borrow it verbatim.

No part of the v1 design needs to be reopened.

---

## 2. Prior art landscape

### Closest neighbors

- **Apache Hamilton** (closest by mechanics, 5/10 matrix). Cache key = `(node_name, code_version, dependencies_data_versions)`; small `data_version` strings pass through the dataflow rather than actual data. **This IS pmstate's content-hash rollup, applied to dataflow rather than process state.** Cribbable verbatim. Source: <https://hamilton.apache.org/concepts/caching/>.
- **`langchain-ai/deepagents`** (closest by vibe, 22k stars). Claude-Code-inspired harness, 4-tool surface (planning + filesystem + execute + task subagent). Generic harness; no hierarchical state, no rollup, no per-leaf log. Different framing, same lineage. Source: <https://github.com/langchain-ai/deepagents>.
- **LangGraph** (5/10 matrix). The `BaseCheckpointSaver` interface (`.put`, `.get_tuple`, `.list`, `.get_next_version()`) is the strongest existing contract in the agent space. Future v0.2+ interop opportunity: a `pmstate.LangGraphCheckpointer` adapter mapping `(thread_id, checkpoint_id) -> (node_path, jsonl_byte_offset)`. Source: <https://reference.langchain.com/python/langgraph/checkpoints>.

### Comparison matrix (compressed)

No surveyed tool checks more than 5 of pmstate's 10 dimensions. Hamilton (5) and LangGraph (5) tie on mechanics. Full matrix in `_scratch/2026-05-06-prior-art.md` §3.

| Dimension | pmstate | closest contender |
|---|---|---|
| Hierarchical state + persistent + agent-native + log-primitive + parent-rollup + content-hash + filesystem + harness-pluggable + library-not-platform + 15-50 LOC | All ✓ | None |

### Genuinely novel claims

- **Structural context-bound via views-not-raw-logs.** No surveyed tool has this as a stated principle. Claude Code's paginated `Read` is a tool implementation detail; pmstate makes it an architectural commitment.
- **Agent as observer, not actor, over a structured tree.** Most agent frameworks (CrewAI, AutoGen, OpenAI Agents SDK, even deepagents) frame the agent as actor. The deliberate single-observer constraint is unusual.
- **The combination matrix.** No tool combines hierarchical state + JSONL log primitive + content-hash rollup + view-bounded reads + observing agent.

### Not novel — adjust positioning

- **Filesystem-substrate.** Backlog.md, Letta Filesystem (74% LoCoMo), Anthropic Skills, deepagents all do this. Pmstate is *riding* the zeitgeist, not inventing it. Marketing claim: not "filesystem-first," but "filesystem-first **process state**."
- **Content-hash caching.** Hamilton, Bazel, Make. Decades old. Borrow shamelessly.
- **Library not platform.** Common stance.
- **Recursive composability.** Common pattern.

### Naming

`pmstate` / `pm-state` / `pm-state-framework` are unclaimed on PyPI and GitHub. Adjacents (`pystates`, `pm-brain`, `pysm`) are different domains. **Action:** grab the PyPI name early to prevent squatting.

---

## 3. Event envelope — recommended v1.0

Adopt CloudEvents v1.0.2 attribute names. Skip the SDK. Pmstate writes JSONL rows, never speaks CloudEvents over the wire — this is a vocabulary borrow, not a runtime dependency.

### Envelope shape

```jsonc
{
  "specversion": "1.0",
  "id": "01J9X8KQZP5M3T7VW2NXBQRGFA",
  "source": "/active/procurement/quotes",
  "type": "pmstate.quote.received",
  "time": "2026-05-06T14:23:11.482Z",
  "subject": "quote_id:Q-2026-0184",
  "data": { "vendor": "...", "amount": 1250 },
  "causationid": "01J9X8KK7H6E2RD8YJF1NW5VBT"
}
```

| Field | Required | Notes |
|---|---|---|
| `specversion` | Yes | Fixed `"1.0"` |
| `id` | Yes | ULID (26-char Crockford base32) |
| `source` | Yes | Pmstate node path (URI-reference) |
| `type` | Yes | `pmstate.<domain>.<verb>[.vN]`; absence of `.vN` means v1 |
| `time` | Yes (CE optional) | RFC 3339, UTC, ms precision, trailing `Z` |
| `subject` | No | Free-form discriminator (e.g., entity ID) |
| `data` | Required for non-marker events | Type-specific payload, JSON |
| `causationid` | No | Causing event's `id`. Lowercase per CE extension naming rule. |

### Writer constraints

- Total serialized line ≤ **4000 bytes** (3 KiB practical ceiling for `data`; reference larger payloads via `subject` + external file).
- `O_APPEND` + single `write()` of `serialized + "\n"`. POSIX-atomic for ≤ 4096 B on Linux ext4/xfs/btrfs/tmpfs and WSL2 in-WSL filesystems. Documented as "not supported" on `/mnt/c/...`, NFS, SMB.
- `Table(path)` mutable files use `os.replace()` on a sibling temp file (POSIX-atomic everywhere).

### IDs: ULID via `python-ulid` (mdomke)

UUIDv7 (`uuid.uuid7()`, stdlib in Python 3.14) is the more "correct" 2026 pick if pmstate lived in a UUID/Postgres world — it doesn't. ULID's 26-char Crockford-base32 is shorter, grep-friendlier, and already specified. Single-writer-per-leaf preserves per-node ordering without cross-machine clock sync. Library: <https://github.com/mdomke/python-ulid>.

### Filesystem watcher: `watchfiles`

Rust-backed (`notify` under the hood), tiny API, async + sync, used by uvicorn's reloader. Linux/macOS/Windows native APIs — same coverage as `watchdog`, smaller surface. Source: <https://github.com/samuelcolvin/watchfiles>.

**WSL2 caveat (load-bearing for this dev environment):** inotify does not fire for changes made by Windows processes on `/mnt/c/...` ([WSL #4739](https://github.com/microsoft/WSL/issues/4739)). Mitigation: pass `force_polling=True` when the watched path starts with `/mnt/`. Default poll interval 1–2 s; sub-second polling is wasteful for human-speed processes.

### Schema evolution

**Pattern: additive-only fields, breaking changes via `type` suffix, upcaster registry on read.** Greg Young, validated by Marten and event-driven.io.

1. Additive optional fields → no version change. Consumers ignore unknown fields.
2. Renames or semantic changes → new type (`pmstate.state.updated.v2`). Old type continues to exist on disk forever.
3. Reader passes each row through an upcaster registry keyed by `type` until current shape. Old data on disk is never rewritten.

### Causation kept, correlation deferred

`causation_id` (renamed `causationid` per CE) earns its keep — pmstate has a real causation tree (leaf write → parent invalidation → potential rollup recompute event). `correlation_id` (cross-leaf logical flow) has no current use case; reserve the field name, add it the day a real consumer asks.

### What's NOT adopted

- CloudEvents Python SDK (we don't speak HTTP/Kafka)
- AsyncAPI 3.x docs (overkill at v0.1; revisit if pmstate ever publishes over a broker)
- OpenTelemetry semantic conventions (mapping is mechanical if ever needed)

---

## 4. Python ergonomics — refined API

### Primary template: Pydantic-AI

```python
agent = Agent("anthropic:claude-sonnet-4-6", instructions="Be concise.")
```

Positional model id + progressively-unlocked kwargs. The 4-LOC version is the same constructor as the typed version with `deps_type=`, `output_type=`. **Linear growth — exactly pmstate's "one new node = one new line" target.**

### Refined API

```python
Node(
    name: str,
    *,
    state: Log | Table | None = None,
    view: Callable[[Any], dict] | None = None,
    reducer: Callable[[dict[str, dict]], dict] | None = None,
    children: list[Node] = (),
    description: str | None = None,   # falls back to view.__doc__
)

Tree(name: str, root: Node)            # OPTIONAL wrapper
node.spawn(child_path: str, node: Node)
node.prune(child_path: str)

Log(path: str | Path, *, view: Callable | None = None)
Table(path: str | Path, *, view: Callable | None = None)
```

**Two refinements vs the internal-design API:**

1. **`Tree(name)` becomes optional.** A `Node` is a valid root. `Tree` is a thin wrapper adding `spawn`/`prune` bound to a path-resolution context. Saves 1–2 LOC on small examples; a `Harness(node)` accepts any Node.
2. **`description=` kwarg with `view.__doc__` fallback.** First-class kwarg cheaper than reflective docstring reads. Solves Q1's "every node must have a cheap one-liner descriptor" cleanly.

### Internal implementation

`Node` is `attrs.@define` (or `msgspec.Struct` if perf matters later). Free `__init__`/`__repr__`/`__eq__`/slots. **Hide from users** — they call `Node("procurement", ...)`, never subclass.

### Adopt / reject

| Pattern | Source | Adopt? |
|---|---|---|
| Positional name + kwargs | Pydantic-AI | ✓ Adopt |
| Children as list values, not registration | OpenAI Agents SDK `handoffs=[...]` | ✓ Adopt |
| Helper-function templates over `Template` class | Hamilton modules, Q7 | ✓ Adopt |
| Type hints as optional schema | Pydantic-AI `output_type`, Marvin | ✓ Adopt |
| `attrs.@define` internal | attrs / msgspec | ✓ Adopt |
| Docstring as description fallback | Marvin | ✓ Adopt |
| Decorator-only graph (Prefect, Marvin) | — | ✗ Reject (hides structure) |
| Builder + compile split (LangGraph) | — | ✗ Reject (forecloses spawn/prune) |
| Decorator-class + dual YAML (CrewAI `@CrewBase`) | — | ✗ Reject (4 layers of ceremony) |
| Parameter-name-as-edge wiring (Hamilton) | — | ✗ Reject (assumes flat namespace) |

### `spawn`/`prune` is a real differentiator

| Library | Runtime tree mutation? |
|---|---|
| LangGraph | No (recompile required) |
| Hamilton | Partial (parallel sub-tasks only) |
| Prefect | "Yes" by accident (no value to introspect) |
| CrewAI | No |
| OpenAI Agents SDK | No |
| pytransitions | Half (add, no remove) |
| Pydantic-AI | No |

Three traps to avoid:
- **No half-mutability** (pytransitions trap). Symmetric `spawn`/`prune` from day one.
- **No compile step** (LangGraph trap). Validate lazily on read; Q2's content-hashing already commits to this.
- **Path-as-string identity** can dangle under concurrent mutation. Q4's "one writer per leaf" must extend to "one writer per tree shape" for v0.1.

### Procurement v0.1 example (28 LOC including imports + blanks)

```python
from pmstate import Node, Log, Table, Tree
from claude_agent_sdk import Harness

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
Harness(tree).run()
```

**Inside the 15–50 LOC budget.** Linear in user requirements (one custom view + one reducer = +8 LOC), not in framework ceremony. With no custom code: ~12 LOC for five leaves.

---

## 5. Borrowable patterns (concrete crib list)

| Borrow | From | Citation |
|---|---|---|
| Cache-key shape `(path, view_fn_code_hash, children_view_hashes)` for rollup invalidation | Apache Hamilton | <https://hamilton.apache.org/concepts/caching/> |
| Document the nested-call hash gotcha up front | Apache Hamilton | same |
| `BaseCheckpointSaver` interface contract (future v0.2+ interop adapter) | LangGraph | <https://reference.langchain.com/python/langgraph/checkpoints> |
| `FileStatePersistence` API ergonomic | Pydantic-AI | <https://ai.pydantic.dev/api/pydantic_graph/persistence/> |
| CloudEvents JSON envelope shape (without SDK) | CNCF | <https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/formats/json-format.md> |
| README framing: "the directory IS the product" | Backlog.md | <https://github.com/MrLesk/Backlog.md> |
| 4-tool harness surface (`list_tree`/`get_state`/`find_state`/`read_log` ↔ planning/fs/execute/task) | deepagents | <https://github.com/langchain-ai/deepagents> |
| LoCoMo benchmark as social proof for filesystem-substrate principle | Letta | <https://www.letta.com/blog/benchmarking-ai-agent-memory> |
| Hierarchical asset-key path lists (`["active", "fieldwork", "enum_log"]`) | Dagster | <https://docs.dagster.io/api/dagster/assets> |
| Greg Young schema evolution + upcasters | event-sourcing canon | <https://leanpub.com/esversioning/read>, <https://event-driven.io/en/simple_events_versioning_patterns/> |

---

## 6. Decisions resolved

All 8 decisions confirmed by Mats on 2026-05-06.

| # | Decision | Resolved |
|---|---|---|
| 1 | Adopt CloudEvents envelope shape | **Yes** |
| 2 | Schema versioning via `type` suffix (not separate `version` field) | **Yes** |
| 3 | `Tree` wrapper optional (a `Node` can be a valid root) | **Yes** |
| 4 | `description=` kwarg with `view.__doc__` fallback | **Yes** |
| 5 | Grab `pmstate` on PyPI immediately | **Yes** — Mats to do manually (placeholder upload, see implementation plan Phase 0) |
| 6 | `AGENTS.md` convention at tree root | **In v0.1** (industry-standard in agentic apps, minimal effort) |
| 7 | LangGraph checkpointer adapter | **Deferred to v0.2+** (recorded in §6.1 below) |
| 8 | Hamilton-style nested-call hash trap warning | **README + reducer docstring** (no runtime warnings) |

### 6.1 Recorded for v0.2+ backlog

- **LangGraph checkpointer adapter.** Implement `pmstate.adapters.langgraph.LangGraphCheckpointer` subclassing `langgraph.checkpoint.base.BaseCheckpointSaver`. Map `(thread_id, checkpoint_id)` to `(node_path, jsonl_byte_offset)`. Trigger: a real LangGraph user shows up wanting to drive a pmstate tree. Per-leaf vs per-thread model mismatch needs concrete-use-case validation before commit. Reference: <https://reference.langchain.com/python/langgraph/checkpoints>.
- **`summarize_branch(path)` agent tool** (already deferred from internal-design Q1). Spawns subagent to summarize a subtree without filling main agent's context. Mirrors deepagents' `task` tool. Revisit after v0.1 ships.
- **Brokered transport for sub-second event reactivity.** Filesystem polling at 1–2 s is fine for human-speed processes. If a real use case needs sub-second cross-process events, add a broker transport (Redis pub/sub or NATS) without changing the event envelope.
- **`correlation_id` envelope field.** Reserved by convention. Add the day a real consumer asks for cross-leaf logical-flow tracing.
- **Concurrent writers per leaf.** v0.1 assumes one writer per leaf. If broken, filesystem-as-substrate hits a ceiling and we'd need a real log service (SQLite WAL, Kafka, Redpanda). Re-examine at v0.2 with real usage data.

---

## 7. What stays as decided in v1

For the record — none of these were challenged by research:

- Tree-of-nodes-as-process model
- Lazy Claude-Code-style navigation (`list_tree`/`get_state`/`find_state`/`read_log`)
- Generic children dump default + optional reducers
- Content-hash lazy rollup
- Two storage primitives only (`Log`, `Table`); other formats via view functions
- Library-not-platform stance
- Recursive composability (single `Node` primitive, no specialized types)
- One-writer-per-leaf assumption for v0.1
- Two-repo pattern (public framework, separate Laterite implementation)
- Aggressive 0.x versioning
- "Open but not supported" stranger-facing stance for v0.1
- v0.1 success criterion: one real Laterite process (procurement) running end-to-end
- Agent observes; does not get spawn/prune as tools

---

## 8. Sources

Full citation lists in the three scratch docs:

- `_scratch/2026-05-06-prior-art.md` — 27 sources
- `_scratch/2026-05-06-event-envelope.md` — 22 sources
- `_scratch/2026-05-06-python-ergonomics.md` — 10 sources
