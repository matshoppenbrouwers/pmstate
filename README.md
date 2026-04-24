# per-pmstate — PM State Framework

Generic, modular framework for deep agents to own and navigate hierarchical process-flow state.

## Concept

- An AI deep agent (e.g., Badger) owns, maintains, and manages a process flow.
- Each flow step (e.g., `active`) and subprocess step (e.g., `procurement`) holds its own state, stored in a flexible format (data, csv, md, json, or other).
- State updates propagate upward: top-level states are notified/updated when substates change.
- The deep agent can navigate through all levels, understand what happened where, and provide the user with info and guidance.
- The framework should feel like an agent SDK (crewai-style): beautiful, elegant, modular — users compose flows with processes and subprocesses, and the agent navigates the result.
- Built as a **shell** using a common event protocol (CommandLane-style) so different harnesses can drive it: custom, Claude Agent SDK, openclaw, hermes, etc.

## Open design questions

- State schema: strictly-typed vs. free-form per node? Versioning/migration strategy?
- Propagation rules: pull (agent recomputes on read) vs. push (substate emits event to parent) vs. hybrid?
- Event protocol: reuse CommandLane events directly, or extend? What's the minimal surface?
- Persistence: file-system layout mirroring the flow tree, or single event log + materialized views?
- Harness adapter contract: what does a harness need to implement to plug in?
- Relationship to `cl-app` (CommandLane) — shared event schema? Shared primitives?

## Status

Greenfield. Registered in `../INDEX.md`. No code yet.

## Repo

- GitHub: https://github.com/matshoppenbrouwers/pm-state-framework
