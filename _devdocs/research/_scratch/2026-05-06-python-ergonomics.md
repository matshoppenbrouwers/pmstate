# Python ergonomics research for pmstate

**Date:** 2026-05-06
**Scope:** 9 Python frameworks surveyed (CrewAI, LangGraph, OpenAI Agents SDK, Prefect, Hamilton, Pydantic-AI, pytransitions/python-statemachine, Marvin, attrs/dataclasses/msgspec). Goal: refine pmstate's target API and stress-test the 15-50 LOC budget.

## 1. TL;DR

- **The closest ergonomic target is Pydantic-AI**, not LangGraph or CrewAI. Pydantic-AI hits "6 lines to a working agent" because it leans on positional model id + kwargs and inherits Pydantic's "declare-a-class, get-introspection-free" magic. pmstate should crib that shape for `Node`.
- **Crib `Node` from `attrs` `@define` (or msgspec `Struct`), not from CrewAI's `@CrewBase`.** Decorator-on-class is cheap and navigable; CrewAI's `@CrewBase` + `@agent`/`@task`/`@crew` + dual YAML configs balloons a "minimal" crew to ~65 LOC. Avoid that pattern entirely.
- **Reject the LangGraph builder/compile split.** LangGraph's `StateGraph` cannot be mutated after `.compile()` — the framework's "answer" to runtime mutation is `Send` (dynamic routing within a fixed graph) or rebuild-and-recompile. pmstate's `spawn`/`prune` are a genuine differentiator; nothing in this survey does it cleanly.
- **Hamilton's "edges-from-parameter-names" is genuinely novel but wrong for pmstate.** Implicit wiring is great for pure dataflow; it is hostile to a tree where the same node name appears under many parents. Steal Hamilton's discipline (functions are units; module is the registry), not its mechanism.
- **15-50 LOC is achievable** if `Tree` is optional (`Node` can be a root) and `children=[...]` accepts both positional `Node`s and the result of helper functions. The procurement v0.1 example fits in ~28 LOC of pmstate code (see Section 4).

---

## 2. Per-library capsules

### 2.1 CrewAI (`@CrewBase` style)

```python
@CrewBase
class ResearchCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @agent
    def researcher(self) -> Agent:
        return Agent(config=self.agents_config["researcher"])

    @task
    def research_task(self) -> Task:
        return Task(config=self.tasks_config["research_task"])

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks,
                    process=Process.hierarchical, manager_llm="gpt-4o")
```

**LOC:** ~30 Python + ~15 YAML = ~45 honest minimum, ~65 for non-trivial.

**Right:** decorators give navigable structure (`grep -n '@task'`). YAML separation lets non-engineers edit prompts.
**Wrong:** four ceremony layers (decorator class, two YAML files, `manager_llm`, `process=`) before any work happens. Hierarchical mode is widely reported as broken (Towards Data Science, Markaicode). Class-as-namespace hides node identity behind method names.
**Applicability:** **anti-pattern.** Do not require a wrapper class.

### 2.2 LangGraph

```python
class State(TypedDict):
    messages: list

g = StateGraph(State)
g.add_node("a", node_a)
g.add_node("b", node_b)
g.add_edge(START, "a")
g.add_edge("a", "b")
g.add_edge("b", END)
app = g.compile(checkpointer=InMemorySaver())
app.invoke({"messages": []}, config={"configurable": {"thread_id": "1"}})
```

**LOC:** ~18 for agent + 3 nodes + checkpointer.

**Right:** `TypedDict` matches Q5's optional-schema commitment. Checkpointer is a single kwarg.
**Wrong:** **builder/compile split is fatal.** Once compiled, `add_node` is unavailable; the only answer is `Send()` (dispatch within fixed graph) or rebuild (LangChain ref docs, GitHub #5700).
**Applicability:** good vocabulary (`START`/`END`/`add_edge`); wrong structural model — pmstate's `spawn`/`prune` cannot tolerate a compile step.

### 2.3 OpenAI Agents SDK

```python
agent = Agent(name="History Tutor", instructions="You answer history questions.")
result = await Runner.run(agent, "When did the Roman Empire fall?")
```

**LOC:** 9 for single agent, ~17 with handoffs.

**Right:** `Agent(name=..., instructions=..., tools=[...], handoffs=[...])` is the shape pmstate wants. Pure kwargs, no subclassing, no decorator. `handoffs=[other_agent]` composes by passing values.
**Applicability:** **directly cribbable.** `Node(name, state, view, reducer, children)` mirrors `Agent(name, instructions, tools, handoffs)` almost 1:1. Children-as-list = handoffs-as-list.

### 2.4 Prefect 3

```python
@task
def get_ids() -> list[str]: ...

@flow
def main():
    return process.map(get_ids())
```

**LOC:** ~12.

**Right:** Decorator-only, no builder. Subflows are `@flow` functions called from another `@flow` — pure Python composition.
**Wrong:** decorator hides structure. The flow graph is constructed *by execution* — Prefect "dynamically creates a graph" by tracing calls. No static structure to inspect before running.
**Applicability:** **reject decorator-only.** pmstate's `list_tree(path)` must work without running anything; the tree must be a value, not a side effect.

### 2.5 Hamilton

```python
def avg_3wk_spend(spend: pd.Series) -> pd.Series:
    return spend.rolling(3).mean()

def acquisition_cost(avg_3wk_spend: pd.Series, signups: pd.Series) -> pd.Series:
    return avg_3wk_spend / signups

dr = driver.Builder().with_modules(my_functions).build()
df = dr.execute(["acquisition_cost"], inputs={"spend": ..., "signups": ...})
```

**LOC:** ~10 + 3 driver.

**Right:** **functions are nodes, parameter names are edges.** Module *is* the registry. Hamilton 1.26+ has dynamic DAGs (`enable_dynamic_execution`), but only for parallel sub-execution.
**Wrong for pmstate:** identifier-based wiring assumes flat namespace. In a tree, "procurement" lives under multiple projects — can't have two top-level functions named `procurement`. Implicit wiring fights `spawn`/`prune`.
**Applicability:** **steal the principle, reject the mechanism.** Principle: *one node = one line, no registration*. Realize via explicit `Node(...)` values in `children=[...]`, not module scanning.

### 2.6 Pydantic-AI

```python
agent = Agent("anthropic:claude-sonnet-4-6", instructions="Be concise.")
result = agent.run_sync('Where does "hello world" come from?')
```

**LOC:** 4. Typed version (deps + structured output):

```python
support = Agent("openai:gpt-5.2", deps_type=SupportDependencies,
                output_type=SupportOutput, instructions="...")
```

**Right:** positional model id + kwargs that progressively unlock features. `deps_type` and `output_type` are *types*, not config objects — Pydantic introspects them. The 4-LOC version works; the typed version is the *same constructor* with more kwargs. Linear growth.

Deeper Pydantic principle: **declare a class, get validation + JSON schema + introspection free.** Q5's optional-schema commitment is a direct echo.
**Applicability:** **primary template.** `Node(name, state=..., view=..., reducer=..., children=[...])` should feel like `Agent(model_id, deps_type=..., output_type=...)`.

### 2.7 pytransitions / python-statemachine

pytransitions hierarchical:

```python
states = ["standing", "walking",
          {"name": "caffeinated", "children": ["dithering", "running"]}]
```

python-statemachine:

```python
class Journey(StateChart):
    class shire(State.Compound):
        bag_end = State(initial=True)
        green_dragon = State()
        visit_pub = bag_end.to(green_dragon)
```

**Right:** dense, readable nesting. python-statemachine's `class State.Compound:` is the most Pythonic hierarchical syntax in the ecosystem.
**Wrong:** both bake transitions into the structure. pmstate v0.1 has no transitions (Q3: observe, don't drive). Inner-class syntax is class-bound — can't build a tree from a function.
**Applicability:** validates "nested literal" is recognized Python idiom; but our `children=[Node(...)]` is more uniform than mixed strings + dicts.

### 2.8 Marvin

```python
@marvin.fn
def sentiment(text: str) -> float:
    """Return a sentiment score between -1 and 1."""
```

**LOC:** 3. Apex of "minimal ceremony": type hints = schema, docstring = prompt.
**Wrong for pmstate:** single-call abstraction with no inspectable structure.
**Applicability:** validates "type hint = schema, docstring = description" as a recognized Python pattern. pmstate can use view-function docstrings as the source of `list_tree` descriptions (Q1).

### 2.9 attrs / dataclasses / msgspec

All three give "declare a class, get `__init__`/`__repr__`/`__eq__` free." msgspec is 5-60x faster (jcristharif.com/msgspec) with runtime type validation and `__slots__`-equivalent layout.

**Applicability:** users should *not* subclass `Node` — they call `Node("procurement", ...)`. **Internally, implement `Node` as `attrs` `@define`** (or msgspec `Struct` if perf matters). Free repr, equality, slots. Authors see a value constructor, not a class to subclass.

---

## 3. Pattern extraction

**Adopt:**

1. **Positional name + kwargs.** `Node("procurement", state=Log("..."), view=...)`. Like Pydantic-AI's `Agent("model-id", instructions=...)`. No type discriminator, no string-keyed config dict.
2. **Children as list values, not registration calls.** `children=[Node(...), Node(...)]`. Composes by value-passing, like OpenAI Agents SDK's `handoffs=[agent_b]`.
3. **Helper-function templates over a `Template` class.** `def project_subtree(name): return Node(...)`. Q7 already commits to this; LangGraph subgraphs and Hamilton modules confirm it's the right Python idiom.
4. **Type hints as optional schema.** If author annotates a view's return as `TypedDict` or `BaseModel`, framework introspects; otherwise duck-typed. (Pydantic-AI `output_type`; Marvin docstring contract.)
5. **`attrs.@define` as `Node`'s internal implementation.** Free repr, eq, slots. Hide from users.
6. **Docstring or `description=` kwarg as `list_tree` source.** Q1's "one-liner per node" is filled by view docstring or explicit `description=`.

**Reject:**

7. **Decorator-only graph definition (Prefect, Marvin).** Hides structure behind execution. `list_tree(path)` must work without running anything.
8. **Builder + compile split (LangGraph).** Forecloses runtime `spawn`/`prune`. (LangChain ref docs; GitHub #5700.)
9. **Decorator-class + dual YAML (CrewAI `@CrewBase`).** Four layers of ceremony for one crew.

**Defer (revisit at v0.2):**

10. **Hamilton's parameter-name-as-edge.** Novel but assumes flat namespace. Worth revisiting if pmstate ever needs leaf-to-leaf event subscriptions ("procurement listens to invoicing").

---

## 4. Recommended `Tree` / `Node` / `Log` / `Table` shape

Current target API survives almost intact. Two refinements:

1. **`Tree(name)` becomes optional.** A `Node` is a valid root. `Tree` is a thin wrapper adding `spawn`/`prune` bound to a path-resolution context. Saves 1-2 LOC on small examples.
2. **`Node.description` as explicit kwarg, fallback to `view.__doc__`.** First-class kwarg is cheaper than reflective docstring reads.

```python
Node(
    name: str,
    *,
    state: Log | Table | None = None,
    view: Callable[[Any], dict] | None = None,
    reducer: Callable[[list[dict]], dict] | None = None,
    children: list[Node] = (),
    description: str | None = None,   # falls back to view.__doc__
)

Tree(name: str, root: Node)            # optional wrapper
Tree.spawn(path: str, node: Node)
Tree.prune(path: str)

Log(path: str | Path, *, view: Callable | None = None)
Table(path: str | Path, *, view: Callable | None = None)
```

**30-LOC procurement example (the v0.1 target):**

```python
from pmstate import Node, Log, Table, Tree
from claude_agent_sdk import Harness

def quote_view(events):
    """Vendor quotes received and pending approval."""
    pending = [e for e in events if e["type"] == "quote.received"
               and not any(a["quote_id"] == e["id"]
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
    description="Vendor quotes, LPOs, approvals for this project.",
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

**Count:** 28 lines including imports and blank lines. Inside the 15-50 LOC budget with margin.

If we drop the explicit `Tree` wrapper and let `Harness(node)` accept any `Node` as the root, this drops to ~26 LOC.

---

## 5. Runtime mutation (`spawn`/`prune`) precedent

Almost nothing surveyed has it first-class:

| Library | Runtime mutation? | Notes |
|---|---|---|
| LangGraph | No | Rebuild + recompile. `Send` for dispatch within fixed graph. |
| Hamilton | Partial | `enable_dynamic_execution` (1.26+) — parallel sub-tasks, not new named nodes. |
| Prefect | "Yes" by accident | Graph built by execution; no value to introspect. |
| CrewAI | No | Class attributes resolved once. |
| OpenAI Agents SDK | No | `handoffs` fixed at construction. |
| pytransitions | Half | `add_state`/`add_transition` exist; no removal. |
| python-statemachine | No | Inner-class is class-time only. |
| Pydantic-AI | No | Agent fixed at construction. |

pmstate's `spawn`/`prune` are a real differentiator. Three traps:

- **pytransitions trap (half-mutable).** Has add, no remove. Asymmetry leaks dead states. Commit to symmetric `spawn`/`prune` from day one.
- **LangGraph trap (compile step).** Any compile/validate phase makes mutation a rebuild — slow, not `spawn`-shaped. pmstate must avoid an explicit compile step; validate lazily on read (Q2's content hashing already commits to this).
- **Path-as-string identity.** `tree.spawn("/active/procurement/sub", node)` resolves against the current shape. Concurrent mutation = dangling paths. Q4's "one writer per leaf" must extend to "one writer per tree shape."

---

## 6. Honest LOC reality

15-50 LOC is achievable, with caveats.

**Gets us there:**

- Skip explicit `Tree()` for small examples — bare `Node` is a valid root. Saves ~2 LOC.
- `state=`, `view=`, `reducer=` all optional. A leaf can be `Node("vendors", state=Table("vendors.json"))` — one line. Q2's generic dump default means most leaves are exactly this.
- `Log`/`Table` accept just a path. Default views (Q3 follow-up) make minimal leaves one-liners.
- Helper functions for repeated structure (`def project_subtree(name)`) — ~3 LOC for a portfolio of 10 projects in ~12 LOC.

**Pushes past 50 LOC:** custom views (~3-5 LOC each), custom reducers (~3-8 LOC), Pydantic schemas (~5 LOC each).

Procurement example: 28 LOC with two custom views + one reducer. Five leaves + one reducer: ~22 LOC. Five leaves with no custom code: ~12 LOC. **Budget is real.**

**Trade-off:** 15 LOC requires defaults to do the work. Three custom view functions = 35-40 LOC. Linear in user needs, not framework ceremony — acceptable.

---

## 7. Open questions

1. **Where do `spawn`/`prune` live if `Tree` is optional?** Recommend bound methods on `Node` — every node can spawn under itself, symmetric.
2. **Sibling name collisions.** `tree.get("/a/b")` ambiguous if two children share a name. Recommend: require unique sibling names, validate at `add`/`spawn` time.
3. **`Node` validation hooks?** Reject. Validate inline at construction (e.g., `state` must be `Log`/`Table` if present). Hooks = lifecycle ceremony Q3 rejects.
4. **`view`/`reducer` as functions or `Callable` objects?** Functions only for v0.1. Composition via `compose(a, b)` if ever needed.
5. **Async views/reducers?** Sync-default. Q4's filesystem substrate makes this fine. Defer async.
6. **`tree.spawned`/`tree.pruned` events on the bus?** Likely yes so `list_tree` consumers can invalidate. Q4 hasn't decided.

---

## Sources

- CrewAI: docs.crewai.com/quickstart, docs.crewai.com/how-to/hierarchical-process; Towards Data Science critique of hierarchical-mode failure modes.
- LangGraph: docs.langchain.com/oss/python/langgraph/graph-api; reference.langchain.com/python/langgraph/graph/state/StateGraph; GitHub issue langchain-ai/langgraph#5700.
- OpenAI Agents SDK: openai.github.io/openai-agents-python/quickstart/.
- Prefect 3: docs.prefect.io/v3/get-started/quickstart.
- Hamilton: hamilton.dagworks.io/en/latest/get-started/your-first-dataflow/; blog.dagworks.io/p/counting-stars-with-hamilton (dynamic DAGs).
- Pydantic-AI: pydantic.dev/docs/ai/overview/.
- pytransitions: github.com/pytransitions/transitions README; HierarchicalMachine docs.
- python-statemachine: python-statemachine.readthedocs.io/en/latest/states.html.
- Marvin: github.com/PrefectHQ/marvin; askmarvin.ai/api-reference/marvin-fns-fn.
- attrs / dataclasses / msgspec: attrs.org/en/stable/examples.html; jcristharif.com/msgspec/structs.html; msgspec benchmarks gist.
