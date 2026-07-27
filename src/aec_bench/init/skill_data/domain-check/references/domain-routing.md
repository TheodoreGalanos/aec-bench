# ABOUTME: Domain routing table for the domain-check skill.
# ABOUTME: Maps domains to their design guide docs and Python package paths.

# Domain Routing

## Domain → Guide Mapping

| Domain | Design Guide | Package Path |
|---|---|---|
| Contracts | `docs/CONTRACTS.md` | `src/aec_bench/contracts/` |
| Tasks | `https://aecbench.com/docs/core/tasks` | `src/aec_bench/tasks/` |
| Templates | `https://aecbench.com/docs/core/templates` | `src/aec_bench/templates/` |
| Generation | `https://aecbench.com/docs/core/templates` | `src/aec_bench/generation/` |
| Agents | `docs/AGENTS.md` (agent contract section) | `src/aec_bench/agents/` |
| Adapters | `https://aecbench.com/docs/agents/harnesses` | `src/aec_bench/adapters/` |
| Harness | `https://aecbench.com/docs/advanced/backends` | `src/aec_bench/harness/` |
| Evaluation | `https://aecbench.com/docs/evaluation/scoring` | `src/aec_bench/evaluation/` |
| Communication | `https://aecbench.com/docs/evaluation/reviewing` | `src/aec_bench/communication/` |
| Feedback | `https://aecbench.com/docs/evaluation/reviewing` | `src/aec_bench/feedback/` |

## Cross-Cutting

| Concern | Location | Notes |
|---|---|---|
| Architecture overview | `docs/ARCHITECTURE.md` | 7 domains, dependency rules, objective stack |
| Invariants | `docs/INVARIANTS.md` | 10 non-negotiable rules |
| Contracts (logical) | `docs/CONTRACTS.md` | 5 data shapes at every boundary |
| Project structure | `docs/PROJECT_STRUCTURE.md` | Module layout |
| Agent guide | `docs/AGENTS.md` | Package overview, dependency rule, shared utilities, conventions |

## Additional Domains (not in the original 7)

These were added during the generation framework and agent contract phases:

| Domain | Depends On | Purpose |
|---|---|---|
| Templates | Nothing | Pure computation templates for task generation |
| Generation | Contracts, Templates | Template engine, scaffolder, dataset composer |
| Agents | Contracts | Agent protocol, ScriptAgent, ToolLoopAgent, provider routing |
| CLI | Generation, Evaluation, Tasks | Typer CLI commands |
| TUI | Tasks, Evaluation, Communication | Textual TUI screens |
| Web | Communication, Feedback | FastAPI routes and templates |
| Ledger | Contracts | Append-only trial persistence (cross-cutting) |
| Providers | Nothing | Vendor integrations (no internal dependencies) |

## When Multiple Domains Are Touched

If a change touches files in 2+ domains:
1. Read ALL relevant domain guides
2. Pay special attention to the boundary between those domains
3. Check that data crosses boundaries only through contract-defined shapes
4. Verify dependency direction is downward (never import upward)
5. Check the known violation patterns listed in the SKILL.md Step 5
