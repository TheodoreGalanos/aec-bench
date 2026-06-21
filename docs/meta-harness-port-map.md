# Meta-Harness Port Map

This map records where each standalone meta-harness surface now lives in AEC-Bench.

## Library Code

| Standalone surface | AEC-Bench surface |
| --- | --- |
| `logic_profile/contract.py` | `aec_bench.meta_harness.logic_profile` |
| `logic_profile/reviewer.py` | `aec_bench.meta_harness.model_runner` review helpers and `aec_bench.evaluation.llm_reviewer` |
| `logic_profile/model_runner.py` | `aec_bench.meta_harness.model_runner` review model functions |
| `operation_profile/contract.py` | `aec_bench.meta_harness.operation_profile` |
| `operation_profile/orchestrator.py` | `aec_bench.meta_harness.operation_orchestrator` |
| `operation_profile/model_runner.py` | `aec_bench.meta_harness.model_runner` operation model functions |
| `operation_profile/harbor_task.py` | `aec_bench.meta_harness.harbor_task` |
| `world_process/contract.py` | `aec_bench.meta_harness.world_process` |
| `world_process/runtime.py` | `aec_bench.meta_harness.world_runtime` |
| `world_process/autonomy.py` | `aec_bench.meta_harness.autonomy` |
| `world_process/model_runner.py` | `aec_bench.meta_harness.model_runner` intake and world-generation functions |
| `world_process/harbor.py` | `aec_bench.meta_harness.harbor` |
| `world_process/aecbench.py` | `aec_bench.meta_harness.aecbench` |
| `world_process/ledger.py` | `aec_bench.meta_harness.ledger` |

## CLI Code

The standalone argparse entry points are consolidated under one native Typer group:

```bash
aec-bench meta-harness
```

The migrated commands are:

- `logic-evaluate`
- `review`
- `review-models`
- `operation-apply`
- `operation-orchestrate`
- `operation-models`
- `harbor-task`
- `intake`
- `intake-models`
- `world-request`
- `world-models`
- `govern`
- `autonomous`
- `process`

The CLI remains an adapter. It parses JSON and endpoint flags, then delegates to `aec_bench.meta_harness` library functions.

## Examples

The standalone example pack now lives under `docs/examples/meta-harness/`:

- `logic-profile/`
- `operation-profile/`
- `world-process/`

The CLI tests consume these files directly so example drift shows up as a test failure.

## Verification

The focused verification surface is:

```bash
uv run ruff check src/aec_bench/meta_harness src/aec_bench/cli/commands/meta_harness.py src/aec_bench/cli/main.py src/aec_bench/evaluation/llm_reviewer.py tests/meta_harness tests/cli/test_meta_harness.py tests/evaluation/test_llm_reviewer.py
uv run pytest tests/cli/test_meta_harness.py tests/meta_harness tests/evaluation/test_llm_reviewer.py
uv run pytest tests/harness/test_harbor_workflow.py tests/harness/test_harbor_import.py tests/harness/test_llm_reviewer_harbor.py tests/cli/test_run.py tests/cli/test_run_local.py tests/evaluation/test_task_world.py tests/evaluation/test_llm_reviewer.py
uv run python -m compileall src/aec_bench/meta_harness src/aec_bench/cli/commands/meta_harness.py src/aec_bench/evaluation/llm_reviewer.py
```

The standalone research notes and journal remain outside AEC-Bench. They are not runtime library surfaces.
