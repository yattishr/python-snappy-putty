## Strengths
- The codebase has a real control core now. `SessionState` in `src/snappy_putty/session.py` is no longer just a bag of fields; it enforces lifecycle transitions and active-goal exclusivity. That is a meaningful architectural improvement and a necessary base for future milestones.
- Filesystem planning, policy evaluation, and apply are at least conceptually separated. `fs_ops.py`, `rule_hooks.py`, and the render layer are distinct modules with reasonably clear responsibilities.
- The rule system is intentionally narrow. `AgentRuleRegistry`, `evaluate_filesystem_policy()`, and the fixed rule tiers are simple enough to reason about. That simplicity is an asset right now.
- The router is small and understandable. `router.py` does not try to be clever beyond route classification, which keeps command intent selection inspectable.
- The codebase has decent scenario coverage around REPL behavior. There are unit tests, subprocess REPL tests, and smoke tests. That is stronger than many small CLI projects at this stage.
- The project has mostly avoided premature abstraction. There is no sprawling plugin runtime or generic workflow engine yet. For M3, that restraint is good.
- The recent addition of explicit blocked-history/status surfacing was the right call. `blocked` is now treated as a first-class terminal outcome rather than being hidden in `error_message`.

## Weaknesses
- `src/snappy_putty/cli.py` is the architectural center of gravity to an unhealthy degree. It owns routing glue, lifecycle transitions, confirmation handling, follow-up question handling, reflection orchestration, terminal state updates, status rendering input assembly, and REPL loop control. That is too much policy and state logic in one file.
- The lifecycle model is still mixed. The M3 execution loop is formalized, but `CLARIFICATION` remains a side-channel state outside the strict M3 corridor. That is acceptable short term, but it means the system does not have one clean workflow model yet.
- The transition graph in `session.py` is broader than the milestone spec because the existing REPL behaviors forced compatibility edges like `CONFIRMATION -> REFLECTING` and `PLANNING -> CLARIFICATION`. That is pragmatic, but it also means the state machine is partly a formal model and partly a compatibility wrapper.
- The code still uses direct state-field mutation in several continuation paths. The worst examples are the “continue current goal” branches in `cli.py`, where `active_goal`, `last_route`, and `error_message` are reassigned manually instead of going through a higher-level workflow primitive. That is brittle.
- `ExecutionResult` exists, but it is defined in `session.py`. That is not a good long-term home. It is not session state; it is workflow outcome domain data. Putting it in the session module couples workflow result semantics to session storage concerns.
- Ask-mode, safe-inspect, git-read, and filesystem mutation still have inconsistent semantics. Some flows are “plan only”, some are “plan then maybe execute”, some are “execute read-only immediately”, and the state machine is trying to normalize all of them after the fact.
- Agent discovery, rule parsing, memory loading, and mode resolution are bundled into one large module (`agent_discovery.py`). That file is manageable now, but it is already serving too many concerns.

## Improvement Areas
- Split workflow orchestration out of `cli.py`. The immediate target is not a full redesign; it is extracting a small workflow coordinator module that owns:
  - goal start / continue
  - confirmation consumption
  - reflection + terminalization
  - clarification continuation
- Make clarification an explicit design decision. Right now it is a tolerated compatibility state. Before M4, decide whether:
  - `CLARIFICATION` stays as a first-class session state, or
  - clarification becomes “planning with pending input” and disappears from the lifecycle surface
- Move `ExecutionResult` and `ExecutionOperation` into a workflow/domain module. Keeping them in `session.py` will become awkward once memory/continuation needs to persist or replay outcomes.
- Introduce a dedicated workflow context object for active runs. Today the active run is spread across `active_goal`, `pending_question`, `pending_plan`, `awaiting_confirmation`, `pending_context`, and `last_execution_result`. That is workable for M3, but too fragmented for continuation logic.
- Reduce duplication between REPL and non-REPL filesystem handling. `_handle_fs_intent_repl()` and `_handle_fs_intent()` still have overlapping planning / confirmation / apply logic with slightly different behavior.
- Tighten the status model. The current status output is useful, but it is still assembled ad hoc from scattered fields rather than from a coherent “current workflow snapshot”.
- Add targeted invariants around manual continuation paths. The recent incomplete-copy regression happened because clarification continuation re-entered planning and then started a new goal. That kind of bug will recur unless continuation is made more explicit and centralized.

## Risks for Next Milestones
- M4 Workflow Memory + Continuation:
  - Immediate risk: the current active workflow state is fragmented across several fields plus free-form `pending_context`. Persisting and restoring that safely will be awkward and error-prone.
  - Immediate risk: `pending_context` is effectively an untyped transport for control-flow state. That is manageable in memory, but risky if serialized and resumed across sessions.
  - Medium-term debt: `ExecutionResult` is not yet clearly separated from session storage, so continuation/history features may end up mixing workflow log concerns with live session concerns.
  - Medium-term debt: clarification and confirmation are implemented as UI-driven branches, not as durable workflow steps. Continuation will expose that mismatch quickly.
- M5 Active Mode:
  - Immediate risk: the current architecture is still suggestion-first with selective execution paths. Active Mode will multiply the importance of a single authoritative execution pipeline, and `cli.py` is too overloaded for that to remain safe.
  - Immediate risk: policy checks are focused on filesystem mutation and mode change. Active Mode will need broader operation classes and probably richer pre-execution gating than the current fixed rule hooks provide.
  - Medium-term debt: if Active Mode is layered onto current route-specific handlers without unifying execution semantics, the code will become branch-heavy and much harder to trust.
- M6 Workflow Skills:
  - Immediate risk: skills today are mostly discovery/config surface. There is no real workflow composition boundary where a skill can safely plug into planning/execution/reflection.
  - Medium-term debt: `agent_discovery.py` and `cli.py` are already accumulating coordination logic. Skills will make that worse unless there is a cleaner orchestration seam first.
  - Medium-term debt: the narrow rule tier system is fine today, but skills will likely pressure it into becoming a quasi-policy DSL. If that happens inside the current architecture, the code will get over-coupled quickly.

## Recommended Actions Before M4
- Must do now
- Extract a small workflow orchestration layer from `cli.py` for lifecycle transitions, clarification continuation, confirmation handling, and reflection.
- Replace loose `pending_context: dict[str, Any]` branches with a more explicit typed structure or a small set of dataclasses/TaggedDict variants.
- Define where workflow-domain objects live. `ExecutionResult` should move out of `session.py`.
- Add targeted tests for state restoration primitives before actual persistence is introduced. At minimum: “serialize active workflow”, “restore pending confirmation”, and “restore pending clarification” behavior should be thought through before code lands.

- Should do soon
- Decide whether `CLARIFICATION` is a permanent first-class lifecycle state or a temporary compatibility state to be collapsed later.
- Consolidate duplicated filesystem workflow logic between interactive and command modes.
- Add tests around status/history symmetry so all terminal outcomes are surfaced consistently.
- Introduce a single “active workflow snapshot” abstraction instead of scattering run state across multiple top-level session fields.

- Can defer
- Broader modular cleanup of `agent_discovery.py`.
- Generalization of rule tiers beyond the current fixed identifiers.
- More polished UX/state rendering. The current output is serviceable enough for M3 and does not need redesign before M4.
