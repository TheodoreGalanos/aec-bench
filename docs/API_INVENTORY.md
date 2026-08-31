# AEC-Bench public API inventory

| Field | Value |
| --- | --- |
| Class | Normative |
| Status | Current |

This document is the public surface inventory for the current AEC-Bench
release. The entries below are the import paths and commands that callers may
rely on. The compatibility tests named in each row keep the inventory tied to
the installed code.

## Python imports

Supported Python imports are documented, tested, and stable within the
project's declared version policy. Import the named objects from the listed
module; other modules under `aec_bench` are implementation details unless this
inventory names them.

| Import path | Classification | Public objects | Compatibility test |
| --- | --- | --- | --- |
| `aec_bench` | Supported | `__version__`, `worlds` | `tests/test_public_api_inventory.py` |
| `aec_bench.worlds` | Supported | `WorldInfo`, `WorldProfileInfo`, `WorldTask`, `branch_world`, `find`, `get`, `list`, `load_profile`, `load_world_task`, `profiles`, `task`, `tasks_for_branches` | `tests/test_public_api_inventory.py`, `tests/worlds/test_public_api.py` |
| `aec_bench.trials` | Supported | `PlannedTrial`, `plan_trials` | `tests/test_public_api_inventory.py`, `tests/contracts/test_run_plan.py` |
| `aec_bench.harness.world_trials` | Supported | `run_world_experiment` | `tests/test_public_api_inventory.py`, `tests/deepseek_harness/test_runtime.py` |
| `aec_bench.harness.dam_seepage_trial` | Supported | `run_dam_seepage_trial` | `tests/test_public_api_inventory.py`, `tests/deepseek_harness/test_runtime.py` |
| `aec_bench.harness.prime_world_actor` | Supported | `run_prime_world_actor_session` | `tests/test_public_api_inventory.py`, `tests/deepseek_harness/test_runtime.py` |
| `aec_bench.evolution` | Supported | `CandidateChecks`, `CandidateProposal`, `CandidateProposalRequest`, `ProposalStatus`, `ReportWriter`, `build_avo`, `build_local_checks`, `gate_candidate`, `next_evolution_state`, `run_evolution`, `run_evolution_from_config` | `tests/test_public_api_inventory.py`, `tests/evolution/test_core.py` |
| `aec_bench.experimentation.meta_harness` | Supported | `run_harness_study` | `tests/test_public_api_inventory.py`, `tests/experimentation/test_meta_harness.py` |
| `aec_bench.adapters.deepseek_harness` | Experimental | `DeepSeekHarnessAdapter` | `tests/test_public_api_inventory.py`, `tests/deepseek_harness/test_sdk_integration.py` |

The experimental entries are documented and tested, but their interfaces may
change with a clear changelog entry.

The `aec_bench.experimentation.meta_harness` entry is the runtime-neutral
functional composition API used by the documented candidate study workflow.
Its other module-level names remain implementation details unless listed here.

All other `aec_bench.*` imports, including package implementation modules and
package `__init__` details not listed above, are internal. They may change as
the repository is simplified.

## CLI commands

`aec-bench` is the supported installed command. Its registered command names
are listed here so a new command cannot become public by accident.

| Classification | Command names |
| --- | --- |
| Supported | `init`, `run`, `run-local`, `import`, `import-local`, `import-prime-eval`, `evaluate`, `remediate`, `tui`, `web`, `search`, `report`, `evaluation`, `evidence`, `ledger`, `config`, `catalogue`, `conformance`, `generate`, `dataset`, `evolve`, `swarm`, `task`, `library`, `prime`, `meta-harness` |

Optional integrations keep the same command names and report their required
installation when the relevant extra is not installed.

## Deprecation

Supported Python imports and CLI commands receive a deprecation notice before
removal. A deprecation notice names the replacement and the release or date
that removes the surface.

Experimental surfaces receive a changelog entry when their interface changes.
Legacy surfaces are listed only when a real migration requires them. A legacy
surface must emit a structured deprecation warning and state its removal
condition. Legacy entries are added to this inventory when a migration surface
is part of the supported boundary.
