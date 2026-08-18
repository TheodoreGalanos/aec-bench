# ABOUTME: Tests deterministic compilation of a matched four-cell harness-program candidate set.
# ABOUTME: Proves factor integrity and executes every real RunBundle through the Harbor workflow seam.

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessContractEnforcement,
    HarnessContractKind,
    HarnessContractSpec,
    HarnessRecipe,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    MaterializedHarnessProgramCandidateSet,
    ProgramFactorTemplate,
    harness_runtime_semantics,
    materialize_harness_program_candidates,
)
from aec_bench.experimentation.qualification.harness_program_study.plan import HarnessProgramCell
from aec_bench.experimentation.qualification.run_bundle_runtime import MetaHarnessStudyContext, execute_run_bundle
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry, default_kernel_registry
from aec_bench.harness.program_execution import ProgramExecutionStatus
from aec_bench.ledger.reader import read_trial_record
from tests.support.adaptive_harness import (
    runtime_attestation_for_harbor_agent,
    write_adaptive_task,
)


class WritingHarborExecutor:
    """Write real Harbor-shaped result trees at the jobs directory selected by lowering."""

    def __init__(self) -> None:
        self.calls = 0
        self._lock = threading.Lock()

    def execute(self, *, command: list[str], cwd: Path) -> int:
        del cwd
        with self._lock:
            self.calls += 1
            call_index = self.calls
        config = yaml.safe_load(Path(command[-1]).read_text(encoding="utf-8"))
        assert len(config["tasks"]) == 1
        task_path = str(config["tasks"][0]["path"])
        jobs_dir = Path(config["jobs_dir"])
        repetitions = int(config["n_attempts"])
        for repetition in range(1, repetitions + 1):
            trial_name = f"trial-harness-program-{call_index}-{repetition}"
            trial_dir = jobs_dir / f"job-harness-program-{call_index}" / trial_name
            (trial_dir / "artifacts" / "agent").mkdir(parents=True)
            (trial_dir / "verifier").mkdir(parents=True)
            (trial_dir / "artifacts" / "agent" / "output.md").write_text("42\n", encoding="utf-8")
            (trial_dir / "artifacts" / "agent" / "agent_result.json").write_text(
                json.dumps(
                    {
                        "status": "completed",
                        "usage_model_calls": 1,
                        "input_tokens": 10,
                        "output_tokens": 2,
                        "usage_cache_read_tokens": 0,
                        "usage_cache_write_tokens": 0,
                    }
                ),
                encoding="utf-8",
            )
            (trial_dir / "verifier" / "reward.json").write_text(
                json.dumps({"reward": 1.0}),
                encoding="utf-8",
            )
            (trial_dir / "result.json").write_text(
                json.dumps(
                    {
                        "trial_name": trial_name,
                        "task_checksum": "sha256-task",
                        "config": {
                            "task": {"path": task_path},
                            "agent": config["agents"][0],
                            "environment": {"type": "docker", "kwargs": {}},
                            "job_id": f"harbor-job-harness-program-{call_index}",
                        },
                        "agent_info": {"name": "entrypoint", "version": "1.0.0"},
                        "agent_result": {
                            "cost_usd": 0.001,
                            "metadata": {
                                "runtime_execution_attestation": runtime_attestation_for_harbor_agent(
                                    config["agents"][0]
                                )
                            },
                        },
                        "started_at": "2026-07-22T00:00:00Z",
                        "finished_at": "2026-07-22T00:00:01Z",
                    }
                ),
                encoding="utf-8",
            )
        return 0


def test_factory_compiles_a_deterministic_genuine_matched_two_by_two(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)

    first = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    repeated = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)

    assert first == repeated
    assert first.content_sha256 == repeated.content_sha256
    assert tuple(candidate.cell for candidate in first.candidates) == tuple(HarnessProgramCell)
    assert first.references.candidates == tuple(candidate.reference for candidate in first.candidates)

    by_cell = {candidate.cell: candidate for candidate in first.candidates}
    h0_p0 = by_cell[HarnessProgramCell.H0_P0]
    hx_p0 = by_cell[HarnessProgramCell.HX_P0]
    h0_px = by_cell[HarnessProgramCell.H0_PX]
    hx_px = by_cell[HarnessProgramCell.HX_PX]

    assert h0_p0.bundle.harness == h0_px.bundle.harness
    assert hx_p0.bundle.harness == hx_px.bundle.harness
    assert h0_p0.bundle.harness != hx_p0.bundle.harness
    assert h0_p0.reference.program_ref == hx_p0.reference.program_ref == request.fixed_program.ref
    assert h0_px.reference.program_ref == hx_px.reference.program_ref == request.learned_program.ref
    assert h0_p0.bundle.program != hx_p0.bundle.program
    assert h0_px.bundle.program != hx_px.bundle.program
    assert len({candidate.bundle.kernel_ref for candidate in first.candidates}) == 1
    assert all(candidate.bundle.harbor.task_refs == request.task_refs for candidate in first.candidates)
    assert request.repetitions == 2
    assert all(candidate.bundle.harbor.repetitions == 1 for candidate in first.candidates)


def test_materialized_set_rejects_a_valid_bundle_swapped_into_the_wrong_cell(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    materialized = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    payload = materialized.model_dump(mode="python")
    payload.pop("content_sha256")
    payload["candidates"][0]["bundle"] = payload["candidates"][1]["bundle"]

    with pytest.raises(ValidationError, match="materialized candidate harness does not match its RunBundle"):
        MaterializedHarnessProgramCandidateSet.model_validate(payload)


@pytest.mark.parametrize(
    ("leakage", "message"),
    [
        ("tasks", "exact task refs"),
        ("model", "shared model"),
        ("harness_budget", "shared harness budget"),
        ("program_budget", "shared program limits"),
    ],
)
def test_factory_request_rejects_factor_leakage(tmp_path: Path, leakage: str, message: str) -> None:
    registry, _, request = _factory_inputs(tmp_path)
    learned_recipe = request.learned_harness_recipe
    learned_program = request.learned_program
    if leakage == "tasks":
        learned_recipe = _replace_binding_configuration(
            learned_recipe,
            TaskSourceBindingConfig(task_refs=("civil/calculation/other",)),
        )
    elif leakage == "model":
        learned_recipe = _replace_binding_configuration(
            learned_recipe,
            AgentBindingConfig(
                agent_name="harness-program-agent",
                model="different-model",
                max_turns=8,
                timeout_seconds=300,
            ),
        )
    elif leakage == "harness_budget":
        recipe_payload = learned_recipe.model_dump(mode="python")
        learned_recipe = HarnessRecipe.model_validate(
            recipe_payload | {"budget": HarnessBudget(max_total_attempts=request.harness_budget.max_total_attempts - 1)}
        )
    elif leakage == "program_budget":
        program_payload = learned_program.model_dump(mode="python")
        program_payload.pop("content_sha256")
        learned_program = ProgramFactorTemplate.model_validate(
            program_payload
            | {"limits": ProgramLimits(max_total_attempts=request.program_limits.max_total_attempts - 1)}
        )

    payload = request.model_dump(mode="python") | {
        "learned_harness_recipe": learned_recipe,
        "learned_program": learned_program,
    }
    payload.pop("content_sha256")
    with pytest.raises(ValidationError, match=message):
        HarnessProgramCandidateRequest.model_validate(payload)


def test_factory_rejects_seed_repetition_and_kernel_leakage(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    payload = request.model_dump(mode="python") | {"seeds": (17,), "repetitions": 2}
    payload.pop("content_sha256")
    with pytest.raises(ValidationError, match="one unique seed per repetition"):
        HarnessProgramCandidateRequest.model_validate(payload)

    foreign_kernel = KernelRef(kernel_id=request.kernel_ref.kernel_id, version="foreign")
    foreign_payload = request.model_dump(mode="python") | {"kernel_ref": foreign_kernel}
    foreign_payload.pop("content_sha256")
    foreign_request = HarnessProgramCandidateRequest.model_validate(foreign_payload)
    with pytest.raises(ValueError, match="fixed kernel"):
        materialize_harness_program_candidates(foreign_request, registry=registry, tasks_root=tasks_root)


@pytest.mark.parametrize("factor", ["harness", "program"])
def test_factory_request_rejects_cosmetic_factor_differences(tmp_path: Path, factor: str) -> None:
    _, _, request = _factory_inputs(tmp_path)
    payload = request.model_dump(mode="python", exclude={"content_sha256"})
    if factor == "harness":
        cosmetic = request.fixed_harness_recipe.model_dump(mode="python", exclude={"content_sha256"})
        cosmetic["recipe_id"] = "cosmetic-hx"
        cosmetic["summary"] = "Different identity and prose with identical runtime behavior."
        payload["learned_harness_recipe"] = HarnessRecipe.model_validate(cosmetic)
    else:
        cosmetic = request.fixed_program.model_dump(mode="python", exclude={"content_sha256"})
        cosmetic["factor_id"] = "cosmetic-px"
        cosmetic["version"] = "9.9.9"
        payload["learned_program"] = ProgramFactorTemplate.model_validate(cosmetic)

    with pytest.raises(ValidationError, match=f"runtime-effective {factor}"):
        HarnessProgramCandidateRequest.model_validate(payload)


def test_harness_runtime_semantics_ignore_contract_identity_and_prose(tmp_path: Path) -> None:
    _, _, request = _factory_inputs(tmp_path)
    contract = HarnessContractSpec(
        contract_id="answer-contract",
        kind=HarnessContractKind.OUTPUT,
        schema_ref="aecbench://answer/v1",
        enforcement=HarnessContractEnforcement.RUNTIME,
        summary="Require a structured answer.",
    )
    source = request.fixed_harness_recipe.model_dump(mode="python", exclude={"content_sha256"})
    source["contracts"] = (contract,)
    source["bindings"] = tuple(
        binding.model_copy(update={"contract_ids": (contract.contract_id,)})
        for binding in request.fixed_harness_recipe.bindings
    )
    original = HarnessRecipe.model_validate(source)

    renamed_contract = HarnessContractSpec(
        contract_id="renamed-answer-contract",
        kind=contract.kind,
        schema_ref=contract.schema_ref,
        enforcement=contract.enforcement,
        summary="Different prose and identity; identical enforced schema.",
    )
    renamed_source = original.model_dump(mode="python", exclude={"content_sha256"})
    renamed_source["contracts"] = (renamed_contract,)
    renamed_source["bindings"] = tuple(
        binding.model_copy(update={"contract_ids": (renamed_contract.contract_id,)}) for binding in original.bindings
    )
    renamed = HarnessRecipe.model_validate(renamed_source)

    assert harness_runtime_semantics(original) == harness_runtime_semantics(renamed)


def test_all_four_bundles_execute_through_the_real_run_bundle_runtime_seam(tmp_path: Path) -> None:
    registry, tasks_root, request = _factory_inputs(tmp_path)
    materialized = materialize_harness_program_candidates(request, registry=registry, tasks_root=tasks_root)
    workflow = SynchronousHarborWorkflow(
        project_root=tmp_path,
        repo_root=tmp_path,
        tasks_root=tasks_root,
        ledger_root=tmp_path / "ledger",
        jobs_root=tmp_path / "jobs",
    )
    executor = WritingHarborExecutor()

    for candidate in materialized.candidates:
        execution = execute_run_bundle(
            bundle=candidate.bundle,
            registry=registry,
            workflow=workflow,
            artifacts_root=tmp_path / "artifacts",
            study=MetaHarnessStudyContext(
                run_id=f"run.harness-program.{candidate.cell.value}",
                policy_id="policy.harness-program.matched",
                harness_generator_sha256="1" * 64,
                program_generator_sha256="2" * 64,
                split="discovery",
            ),
            executor=executor,
        )

        assert execution.program.status is ProgramExecutionStatus.SUCCEEDED
        records = [
            read_trial_record(path)
            for invocation in execution.harbor_invocations
            for path in invocation.imported_trial_paths
        ]
        assert len(records) == 1
        observed_bundle_ids = {
            record.meta_harness_provenance.bundle_sha256 for record in records if record.meta_harness_provenance
        }
        assert observed_bundle_ids == {canonical_json_sha256(candidate.bundle.model_dump(mode="json"))}

    assert executor.calls == 4


def _factory_inputs(
    tmp_path: Path,
    *,
    task_refs: tuple[str, ...] = ("civil/calculation/harness-program",),
    candidate_set_id: str = "harness-program.stormwater.demo",
    task_set_id: str = "task-set.stormwater.demo",
) -> tuple[KernelRuntimeRegistry, Path, HarnessProgramCandidateRequest]:
    registry = default_kernel_registry()
    tasks_root = tmp_path / "tasks"
    for task_ref in task_refs:
        write_adaptive_task(tasks_root, task_id=task_ref)
    harness_budget = HarnessBudget()
    program_limits = ProgramLimits()
    fixed_recipe = _recipe(
        registry,
        recipe_id="harness-program-h0",
        task_refs=task_refs,
        adapter_capability="aecbench.adapter.tool-loop",
        budget=harness_budget,
    )
    learned_recipe = _recipe(
        registry,
        recipe_id="harness-program-hx",
        task_refs=task_refs,
        adapter_capability="aecbench.adapter.rlm",
        budget=harness_budget,
    )
    fixed_program = ProgramFactorTemplate(
        factor_id="harness-program-p0",
        version="1.0.0",
        nodes=(
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=program_limits,
    )
    learned_program = ProgramFactorTemplate(
        factor_id="harness-program-px",
        version="1.0.0",
        nodes=(
            ActionNode(node_id="enumerate", operation_id="enumerate_tasks.v1"),
            FanoutNode(
                node_id="run-each",
                depends_on=("enumerate",),
                operation_id="run_batch.v1",
                items=ProgramOutputRef(node_id="enumerate", output_port="tasks"),
                item_argument="task_ref",
                max_parallelism=2,
            ),
            StopNode(node_id="stop", depends_on=("run-each",), outcome=StopOutcome.SUCCEEDED),
        ),
        limits=program_limits,
    )
    request = HarnessProgramCandidateRequest(
        candidate_set_id=candidate_set_id,
        task_set_id=task_set_id,
        experiment_id="experiment.harness-program.demo",
        kernel_ref=registry.manifest.ref,
        task_refs=task_refs,
        model="claude-test-model",
        harness_budget=harness_budget,
        program_limits=program_limits,
        seeds=(17, 29),
        repetitions=2,
        fixed_harness_recipe=fixed_recipe,
        learned_harness_recipe=learned_recipe,
        fixed_program=fixed_program,
        learned_program=learned_program,
    )
    return registry, tasks_root, request


def _recipe(
    registry: KernelRuntimeRegistry,
    *,
    recipe_id: str,
    task_refs: tuple[str, ...],
    adapter_capability: str,
    budget: HarnessBudget,
) -> HarnessRecipe:
    capability = registry.capability
    return HarnessRecipe(
        recipe_id=recipe_id,
        version="1.0.0",
        summary="Run one exact task through one explicit harness treatment.",
        budget=budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=task_refs),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(adapter_capability).ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name="harness-program-agent",
                    model="claude-test-model",
                    max_turns=8,
                    timeout_seconds=300,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability("aecbench.backend.harbor.docker").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(max_concurrency=2, timeout_override_seconds=360),
            ),
            HarnessBindingSpec(
                binding_id="verify",
                capability_ref=capability("aecbench.verifier.task").ref,
                depends_on=("compute",),
                topology_role=HarnessTopologyRole.GATE,
                configuration=VerificationBindingConfig(enabled=True, required=True),
            ),
            HarnessBindingSpec(
                binding_id="import",
                capability_ref=capability("aecbench.results.trial-record").ref,
                depends_on=("verify",),
                topology_role=HarnessTopologyRole.SINK,
                configuration=ResultImportBindingConfig(
                    ledger_namespace="harness-program-candidates",
                    required_artifacts=("candidate-manifest",),
                ),
            ),
        ),
    )


def _replace_binding_configuration(
    recipe: HarnessRecipe,
    replacement: TaskSourceBindingConfig | AgentBindingConfig,
) -> HarnessRecipe:
    bindings = tuple(
        binding.model_copy(update={"configuration": replacement})
        if isinstance(binding.configuration, type(replacement))
        else binding
        for binding in recipe.bindings
    )
    payload = recipe.model_dump(mode="python")
    return HarnessRecipe.model_validate(payload | {"bindings": bindings})
