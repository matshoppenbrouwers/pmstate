# Process flow agent framework — design snapshot

*Working document. Review complete (Q1–Q7). Event bus requirements locked in; specific protocol choice deliberately left open pending real use.*

---

## Concept in one sentence

A tree is a process. Each node owns a piece of state on disk. An LLM agent navigates the tree to reason over what's happening. The runtime underneath is swappable.

## Motivating example

A project lifecycle pipeline:

```
Pipeline: project lifecycle
├── Proposal
├── Won
├── Onboarding
├── Active
│   ├── Procurement
│   │   └── Vendor quotes, LPO events, approvals
│   ├── Invoicing
│   │   └── QB sync log
│   ├── Team LOE
│   │   └── Timesheet roll
│   ├── Fieldwork
│   │   └── Enum log, DQ checks
│   └── Quality
├── Closing
└── Done
```

Each node owns a piece of state on disk. Changes at leaves propagate upward. An agent navigates the tree to answer questions at any level of granularity.

---

## Architecture (four layers)

1. **Deep agent** — reads state via tools, guides the user. One agent, not many. Observer, not actor.
2. **Event bus** — carries `state.updated`, `step.entered`, `notify.parent`. Contract between the tree and the harnesses.
3. **Process tree** — hierarchical nodes, each with its own state file on disk. Rolls up on read.
4. **Harness adapters** — shell speaks the event protocol; the runtime underneath is pluggable (Claude SDK, OpenClaw, Hermes, custom).

The tree is the data. The event bus is the contract. The agent and the harnesses are independent consumers of that contract.

---

## Design decisions so far

### Q1 — How does the agent navigate? **Lazy, Claude Code-style.**

The agent does not receive the whole tree as context. It uses tools to explore.

**Tool surface:**

- `list_tree(path, depth=1)` — returns node names + one-line descriptions. Cheap. Like `ls` with skill-style frontmatter.
- `get_state(path)` — returns the view for one node. The committed step.
- `find_state(query, path_glob=None)` — pattern search across state files. Grep-style.

**Eager baseline:** agent always sees the root's summary plus names of direct children, so it can orient without calling any tool.

**Design constraint this creates:** every node must have a cheap, summarizable one-line descriptor used by `list_tree`. This is a feature (forces meaningful naming) but a real constraint.

**Deferred to v0.2:** `summarize_branch(path)` — spawns a subagent to summarize a subtree without filling the main agent's context. Powerful but adds harness complexity. Revisit after v0.1 ships.

### Q2 — How do parents roll up from children? **Generic dump by default, reducers optional, lazy via content hashing.**

Three commitments:

1. **Generic children dump as default.** A parent with no rollup code returns a bundle of its children's views when read. Zero user code required — the framework works out of the box.
2. **Optional reducers.** When an author wants smarter aggregation (health flags, weighted averages, custom logic), they write a function that takes children's views and returns a parent view. The framework uses it instead of the generic dump.
3. **Lazy computation with content hashing.** Rollups don't run eagerly on change. Each parent stores a fingerprint of its children at last rollup. On read, fresh fingerprint vs stored — match = cached view is valid, mismatch = recompute. Self-healing, crash-safe (no sticky-note flag to drop).

**User experience:**

- Day 1: Define the tree. No rollup code. Agent navigates, sees raw children.
- Later: Add reducers to the ~20% of nodes where they genuinely help.
- Rest stay generic. Tree still works end to end.

### Q3 — What is this thing, actually? **Its own category.**

Not CrewAI (that's multi-agent orchestration, we have one agent over structured data). Not XState alone (that's in-memory state machines with no disk persistence, no agent interface, and no rollup semantics). Not Make/Bazel (those produce outputs, we observe process).

We borrow from all of them:

- **XState:** hierarchical state machine vocabulary, state actors, events-as-transitions
- **Event sourcing:** append-only logs for time-shaped data, time-travel queries where it fits
- **Build systems:** content hashing, lazy recompute, invalidation as cheap propagation
- **Claude Code:** agent tool surface, lazy navigation, cheap-to-expensive tool progression

The combination is novel. Frame it as its own thing: "a persistent, hierarchical process state framework that LLM agents can navigate and reason over." No pre-existing-tool analogy.

**Ergonomics target:** few lines of code to a working system. A user should be able to define a small tree, attach a Claude-SDK harness, and have a working agent over their process in roughly 15–50 lines of Python. Growth should be linear — one new `Node(...)` per node added, no config objects or boilerplate.

### Q3 follow-up — Storage: log-shaped or mutable? **Both, with logs as default.**

Most process flow data is genuinely event-shaped — things change because *something happened*. Default to append-only logs.

Mutable files are the escape hatch for:

- Reference data (enumerator rosters, country lists)
- Current-state snapshots nobody treats historically (configs)
- Externally-owned data you're pointing at (a Google Sheet, a live QB report)

Each leaf declares its shape. Parents don't care — they read the child's view through a single interface.

**Consequence worth naming:** time travel works for log-shaped leaves, not mutable ones. Be explicit about this in docs rather than pretend everything is time-travelable.

### Q3 follow-up — The context-bloat problem. **Solved structurally, not by agent discipline.**

A naive log-shaped leaf with 12,000 events destroys the agent's context window on a single `get_state` call. This would be the framework's silent killer if not addressed.

**Three structural commitments:**

1. **Log-shaped leaves always have a view.** Either author-defined or a sensible default (`{count, latest, first}`). The view is what `get_state` returns. Raw logs are never returned by default navigation tools.
2. **Raw log access is a separate, bounded tool.**
   - `read_log(path, start=None, end=None, limit=100, filter=None)`
   - The agent must explicitly opt in, with bounds. Mirrors Claude Code's paginated `Read`.
3. **Rollups compute from views, not raw logs.** When Active aggregates fieldwork, it sees fieldwork's view (50 tokens), not the 12,000-row log. Cost is bounded at every tree level.

**The underlying principle:** the cheap tools can't accidentally be expensive. That's a property of the *tools*, not the *agent*. Context discipline that depends on the model choosing to be careful will fail. Enforce it structurally.

**Sensible defaults for views:**

- Tables (mutable): file contents, truncated to ~100 rows / ~2KB
- Logs (JSONL): `{count, latest, first}`

Most leaves get by with defaults. Authors override when they want richer views. Keeps initial setup light.

### Q4 — The event bus: what the framework needs from it. **Requirements locked in; specific protocol choice left open.**

The original brief suggested reusing CommandLane's event protocol. Worth exploring as inspiration, and possibly unifying into a single protocol that works for both. But we can't commit to that without checking the fit honestly — CommandLane was built for local desktop UI events, which is a different job from long-running process state with an observing agent. Rather than pick a protocol prematurely, we lock in what the framework *needs* from whatever bus it eventually uses.

**The six requirements:**

1. **Persistence across process restarts.** Projects run for months; the agent process will restart many times. A `state.updated` event firing while the agent is down must not vanish — otherwise parent rollups silently go stale. The bus (or its storage substrate) must survive process death.

2. **Ordering within a node's event stream.** If two events fire close together on the same leaf — "vendor quote added," then "quote withdrawn" — consumers must process them in order, or the resulting state is wrong. Global ordering isn't required; per-node ordering is.

3. **At-least-once delivery with idempotency.** Exactly-once is a myth in distributed systems. The realistic target is at-least-once with idempotency — an event may be delivered twice, and consumers handle that because events carry stable unique IDs (ULIDs).

4. **Replay from a point in time.** "What happened to fieldwork since last Tuesday?" or "recompute Active's rollup from scratch" both require replaying event history. Fire-and-forget buses can't do this. The bus must retain history or be backed by something that does.

5. **Schema evolution.** Event shapes will change over the framework's life. Every event carries a `version` field per type. Consumers must be able to read old versions (via upcasters, defaults, or similar). No breaking changes via silent shape drift.

6. **Cross-process, possibly cross-machine.** The agent may run in a different process from whatever writes state. A field team might write from a tablet; the agent might read on a server. The bus cannot assume shared memory.

**Event envelope (target shape):**

```
Event {
  id: ULID            // sortable, unique, stable for idempotency
  type: string        // "state.updated", "step.entered", "notify.parent"
  source: path        // "/active/fieldwork/enum_log"
  version: int        // schema version for this event type
  timestamp: ISO8601
  payload: { ... }    // type-specific
  causation_id?: ULID // the event that caused this one, for tracing
}
```

**Working recommendation (to be validated as the framework takes shape): events ARE leaf logs.**

The event protocol and the leaf log storage are probably the same thing. Log-shaped leaves already persist as append-only JSONL — those files can be the event stream for that leaf directly, with one event per row matching the envelope above. This gives us all six requirements nearly for free:

- **Persistence:** events are files, files persist.
- **Ordering:** the file is a totally ordered log per node.
- **At-least-once + idempotency:** consumers read with cursors (byte offset / line number); ULIDs per row make dedup trivial.
- **Replay:** read the file from line N.
- **Schema evolution:** `version` field per row, consumers handle old versions.
- **Cross-process:** any process that can read files can read events.

The trade-off: no pub/sub across nodes in real-time. Consumers poll file size or use filesystem watches (inotify, FSEvents). For process flow data at human speeds — surveys over days, invoices weekly — polling at seconds-level is fine. If sub-second reactivity is ever needed, a broker transport can be added later without changing the event shape.

**Deliberately left open for now:**

- Whether to extend CommandLane's protocol, unify into a single protocol, or build separately. The requirements above are the stable thing; the protocol choice can be revisited when we have working code to validate against.
- Whether to adopt an existing standard (CloudEvents is the closest candidate) for the envelope shape. Cheap to adopt later if useful for interop.

**Explicitly out of scope for v0.1:**

- Pub/sub brokers, distributed consensus, exactly-once delivery guarantees.
- Concurrent writers to the same leaf. The design assumes one writer per leaf, many readers. If that assumption breaks, filesystem-as-substrate has a ceiling and we'd need a real log service (Kafka, Redpanda, SQLite WAL).

**One concern worth carrying forward.** "Filesystem is the substrate" now shapes Q2 (lazy recompute via content hashing), Q3 (append-only logs as storage), and Q4 (events as log rows). A lot of weight on one principle. Upside: coherence — every decision reinforces every other. Downside: if that principle turns out wrong for a real use case (most plausibly: concurrent writers), a lot of decisions fall together. Worth re-examining at v0.2 with real usage data.

### Q5 — Who knows how to read what? **The framework knows nothing about formats. Authors write view functions.**

The view mechanism from Q3 already implied this, but it's the most important scoping decision in the framework so it's worth stating explicitly.

**The architecture:**

```
disk (any format)
  └── view function (author's code)
      └── dict view (framework's world)
          └── rollups, tools, agent (all deal with dicts)
```

The view function is the parsing boundary. Between disk and view, anything goes. Between view and everything else, everything is dict-shaped. The framework itself never parses, never registers formats, never ships a parser plugin system.

**Four commitments:**

1. **Two storage helpers, no more.**
   - `Log(path)` — append-only JSONL. Default view: `{count, latest, first}`.
   - `Table(path)` — mutable JSON. Default view: the JSON, truncated above a size threshold (e.g. ~2KB or ~50 top-level keys).

   That's the entire format surface. JSONL and JSON cover log-shaped and table-shaped state respectively. Authors who want CSV, YAML, markdown, Parquet, or anything else write a view function — the framework does not ship helpers for them.

   This is deliberate. CSV has too many edge cases (quoting, encoding, type inference) to be first-class. Markdown is a presentation format, not a state format. "Other formats" is an endlessly growing surface that would calcify the framework. Closing off "should we support X format?" with "no, write a view function" is itself valuable.

2. **External data sources live outside the framework.** Google Sheets, QuickBooks, Airtable, etc. are not state formats — they're external systems. An integration layer (outside the framework, in harness adapters or user scripts) mirrors them into JSON state files. The framework reads the JSON; it doesn't talk to the external system. Cleaner separation, and keeps the framework's format vocabulary at two words.

3. **View failures are data, not exceptions.** When a view function throws — malformed row, missing field, file not yet written — the framework catches it and returns a structured error view: `{error: "...", path: ..., exception: ...}`. The agent sees the error as data and can reason about it (skip the node, report to user, try again later) rather than having its tool call derail.

   View function contract: return a dict, whether that dict describes the state or describes an error. Authors don't need to do this themselves — the framework wraps their view function with error capture. But it's worth stating in docs so authors understand why their view might appear to "succeed" even when parsing failed.

4. **Schemas are optional and introspectable.**
   - Default: views are duck-typed dicts. Zero ceremony, highest flexibility.
   - Opt-in: authors declare a schema (Pydantic model, TypedDict, or similar) for a view. Framework validates at read time and exposes the schema via a describe-style tool.
   - Benefit when present: the agent can plan "which reads are worth doing" without actually doing them, by introspecting view shapes. The one-line descriptor for `list_tree` (Q1) comes from schema metadata when present; otherwise the author supplies it inline on the node.

   This must stay optional. Required schemas turn process flow definitions into Django models and kill the linear-growth ergonomic.

**The underlying principle being committed to.** This is where the framework chooses to be a *library* (users bring code, framework provides structure) rather than a *platform* (framework provides code, users provide config). Libraries stay small and flexible forever; platforms scale their feature set with user needs and eventually calcify. By making view functions the parsing boundary, we've made the library choice decisively. Future scope debates ("should we support X format?") are resolved by the library-not-platform stance.

### Q6 — Who is this framework for? **Generic-capable framework, Laterite as the sole user for v0.1.**

Architecturally generic (designed as a reusable library), but with disciplined scope: Laterite is the first and only real user for v0.1, and all decisions about "what ships" are made against Laterite's needs, not hypothetical future users'.

**Two-repo pattern:**

- **Public framework repo** — the generic library. Clean API boundary. Visible on GitHub but not marketed as a product.
- **Separate Laterite implementation repo** — node definitions, reducers, integration code, Badger harness config. Imports the framework as a dependency.

The physical separation enforces clean API boundaries. Every time something Laterite-specific wants to creep into the framework, the repo boundary forces the question: "does this really belong in the generic layer?" This is how Rails was extracted from Basecamp and Django from the Lawrence Journal-World — separate repos from the start, even with only one user.

**"Open but not supported" for v0.1:**

- **Minimal README.** One paragraph explaining what it is, one paragraph saying "pre-alpha, one user (me), API unstable, breaking changes without warning." That's the entire stranger-facing documentation burden for v0.1.
- **Aggressive 0.x versioning.** Stay on 0.1, 0.2, 0.3 for a long time. Semver's contract is that 0.x versions can break anything — this is the permission slip to evolve the framework based on what Laterite actually needs.
- **No community contributions accepted for v0.1.** Stars welcome. Issues thanked but declined. PRs politely refused. The framework earns the right to community contributions by first working well for its one user.
- **No content or launch activity** until the framework is running at least one real Laterite process end-to-end. "Hop on the Stack" content can cover CommandLane, Badger, Laterite tooling in abstract — but the framework stays quiet until it ships something real.

**Success criterion for v0.1:** one real Laterite process runs end-to-end on the framework. Not "architecturally complete." Not "attracts users." Not "has great docs." One actual process — ideally a narrow one like procurement tracking on a single project — working in production.

**Scope boundaries for v0.1:**

- No plugin system
- No stranger-facing docs beyond a README
- No second-user abstractions
- No generalization for hypothetical users
- When Laterite needs something, decide honestly where it belongs: generic code in the framework repo, situational code in the Laterite repo.

**Three specific failure modes being guarded against:**

1. **API ossification without users.** Committing to a stable public API before there's a second real user. Prevented by aggressive 0.x versioning and the "open but not supported" stance.
2. **Documentation debt masquerading as scope.** Writing for hypothetical users while Laterite's real needs wait. Prevented by the minimal README rule.
3. **Generalization theatre.** Abstracting Laterite-specific code into generic-looking patterns for benefits that only arrive if a second user shows up. Prevented by the two-repo discipline — Laterite-specific code stays in the Laterite repo.

**Content-before-ship risk.** Specific to this builder's pattern: there's a real temptation to turn the framework into a content artifact (Reddit post, Twitter thread, Show HN) before it's a working tool. The specific failure mode: content provides validation that replaces shipping, so the framework never actually gets finished. The rule is silence until one real Laterite process is running on it.

**Trigger for revisiting B-as-actual-OSS-product:** when a second real user (not hypothetical, not "someone who starred the repo") shows up with a concrete use case and concrete friction. Not before. At that point we revisit docs, stability, contribution policy — as a deliberate decision, not as drift.

### Q7 — Static or dynamic trees? **A tree is a process. Composition is recursive, primitives are uniform.**

The framing "static vs dynamic vs hybrid" was a false trichotomy. The real answer is that tree composition is recursive and the framework's primitives are uniform at every level.

**A tree is a process.** That's the whole model. The tree can represent a single project's lifecycle (children are stages), a portfolio (children are projects, each itself a tree), a single subprocess (children are leaves), or anything else the user intends. The framework doesn't know or care — it's all just nodes containing nodes.

This dissolves the "one process vs portfolio" question that was on the table. Both are processes. A portfolio-user's tree is structurally identical to a single-project-user's tree, just at a different level of aggregation. Recursive composability means the same navigation tools, rollup semantics, and event mechanics work at every level without special cases.

**API surface for tree construction and modification:**

```python
# Construction time
Tree(name)
Node(name, state=..., view=..., reducer=..., children=[...])
tree.add(node)

# Runtime
tree.spawn(path, node)    # add a node under an existing path
tree.prune(path)          # remove a previously-spawned node
```

`spawn` and `prune` are framework operations, not user-code discipline. The framework tracks all nodes identically regardless of whether they were added at construction or spawned later. No "skeleton vs spawned" runtime distinction.

**Templates are not a framework concept.** Users who want reusable subtree shapes write Python functions that return nodes:

```python
def project_subtree(name):
    return Node(name, children=[
        Stage("proposal"),
        Stage("active", children=[
            Subprocess("procurement"),
            Subprocess("fieldwork"),
        ]),
    ])

portfolio = Tree("laterite_portfolio")
portfolio.add(project_subtree("project_alpha"))
portfolio.add(project_subtree("project_beta"))
portfolio.spawn("project_beta/active/subcontractor", Subprocess)
```

No `Template` class, no `instantiate()`, no registration. Templates are Python functions. This means users who don't need them never encounter them as a concept, and users who do get the full power of the language (parameterization, composition, conditional construction) without learning framework-specific syntax.

**The skeleton-vs-dynamic distinction lives in user code, not the framework.** In Laterite's implementation, "always-there" nodes might be defined in a helper function while "sometimes-there" nodes get spawned at runtime. That's a convention in user code. The framework sees no difference.

**No specialized node types in the framework.** `Pipeline`, `Stage`, `Subprocess` are just names in the examples — they're all `Node`. The framework imposes no type hierarchy. Users who want typing discipline use Python type hints and Pydantic; the runtime treats every node identically.

**Agent permissions (v0.1):** spawn and prune are user-facing API only. The agent does not get spawn or prune as tools — letting the agent create or destroy nodes autonomously opens a trust question we don't need to resolve yet. The agent observes; humans (or application code) structure.

**The underlying discipline being chosen here.** Recursive composability is powerful precisely because it's rigorously uniform, not because it's "flexible" in a permissive sense. Small set of primitives, composable many ways, the same operations at every level — the Unix-pipes model, not the plugin-system model. That uniformity is what keeps the framework small and coherent as use cases multiply. Future scope debates ("should we add a special node type for X?") are resolved by "no — use `Node` and compose."

---

## Principles emerging from the review

1. **The cheap tools can't accidentally be expensive.** Structural bound at every read path.
2. **Generic defaults, opt-in smarts.** Framework works with zero author code; authors add complexity only where it pays off.
3. **Filesystem is the substrate.** State lives on disk in inspectable formats. Humans, git, other tools can read it. No opaque database.
4. **The agent is an observer, not an actor.** No multi-agent orchestration. If users want actors, they compose the framework; we don't build that for them.
5. **Lazy everything.** Navigation, rollup, log reads — all deferred until someone asks. Work happens when it's paid for.
6. **Linear growth.** One new node = one new line. Resist the pull toward config objects, lifecycle hooks, and registration ceremonies.
7. **Library, not platform.** Framework provides structure; users bring code where parsing or integration is needed. "Should we support X format?" is always answered with "no, write a view function."
8. **Recursive composability over specialized types.** A tree is a process. Nodes contain nodes. Same primitives at every level. Resist the pull toward specialized node types or runtime abstractions that privilege one use case over others.
