# ABOUTME: Routes domain-check reviews to current AEC-Bench owners and authoritative documents.
# ABOUTME: Uses package paths as navigation signals without freezing a complete dependency inventory.

# Domain Routing

Start with `docs/README.md`. It defines the authority order, document classes,
status, audience, and owner for maintained repository documentation.

## Concern routing

| Concern | Common paths | Read first | Ownership question |
| --- | --- | --- | --- |
| Boundary models and compatibility | `src/aec_bench/contracts/` | `docs/CONTRACTS.md` | Which owner admits and validates this data? |
| Task definitions and revisions | `tasks/`, `src/aec_bench/tasks/` | `docs/CONTRACTS.md`, `docs/ARCHITECTURE.md` | Is task meaning provider-neutral and revision identity explicit? |
| Templates and generation | `src/aec_bench/templates/`, `src/aec_bench/generation/` | `docs/ARCHITECTURE.md` | Is compilation separate from execution and evaluation policy? |
| Task-owned domain logic | Owning task, template, lifecycle, or world package | `docs/ARCHITECTURE.md`, owning tests | Does the benchmark owner keep its calculations and technical verification? |
| Agents, adapters, and backends | `agents/`, `src/aec_bench/agents/`, `src/aec_bench/adapters/`, `src/aec_bench/harness/` | `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md` | Does the code translate or orchestrate without taking task or scoring ownership? |
| Interactive worlds | `src/aec_bench/worlds/` | `docs/world-authoring.md`, `docs/protocols/interactive-world-runtime.md` | Does the registered world own semantics while the episode runtime owns generic machinery? |
| Evidence lifecycles and publication | `src/aec_bench/lifecycles/`, `src/aec_bench/harness/lifecycle_*.py`, `src/aec_bench/experimentation/lifecycle_studies/` | `docs/protocols/staged-evidence-and-publication.md` | Are checkpoint authority, recovery, publication, and study interpretation with their owners? |
| Higher-order experiments | `src/aec_bench/experimentation/` | `docs/ARCHITECTURE.md`, owning protocol | Does the study coordinate ordinary capabilities without taking their authority? |
| Evaluation | `src/aec_bench/evaluation/` and registered evaluators | `docs/ARCHITECTURE.md`, `docs/INVARIANTS.md` | Does evaluation remain the only scoring and invalidity authority? |
| Ledger and artifacts | `src/aec_bench/ledger/` and artifact stores | `docs/CONTRACTS.md`, owning protocol | Does persistence preserve evidence without inventing policy? |
| Reports and review | `src/aec_bench/communication/`, `src/aec_bench/feedback/` | `docs/ARCHITECTURE.md`, `docs/INVARIANTS.md` | Does presentation report established results and structured judgment? |
| CLI, TUI, and web | `src/aec_bench/cli/`, `src/aec_bench/tui/`, `src/aec_bench/web/` | `README.md`, `docs/ARCHITECTURE.md` | Is this composition and presentation, or a duplicate implementation path? |
| Repository layout | top-level directories and package moves | `docs/PROJECT_STRUCTURE.md` | Is the stable map still accurate without copying a volatile inventory? |

Public installation, CLI, integration, and user guides live at
`https://aecbench.com/docs`. Use them when a change affects documented public
behaviour.

## Changes crossing concerns

When a change crosses ownership boundaries:

1. Trace the live call path and persisted artifacts.
2. Identify the producer and consumer of each boundary value.
3. Confirm validation occurs where the consumer admits the value.
4. Check that policy remains with its owner.
5. Read every applicable protocol, not every repository document.
6. Verify the complete affected path with the lowest sufficient tests.

History under `docs/history/` can explain why a boundary exists. It does not
override the current architecture, contract, invariant, protocol, or code.
