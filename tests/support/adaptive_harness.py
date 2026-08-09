# ABOUTME: Builds deterministic fixed-K, Hx, px, RunBundle, and task fixtures for adaptive-harness tests.
# ABOUTME: Keeps cross-layer tests focused on behavior rather than repeated contract construction.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    FanoutNode,
    ProgramLimits,
    ProgramNode,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessRecipe,
    HarnessTopologyRole,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    ToolAccessMode,
    ToolBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.harness.compilation import (
    compile_execution_program,
    compile_harness_instance,
    compile_run_bundle,
)
from aec_bench.harness.execution_payload import (
    RuntimeExecutionAttestation,
    build_entrypoint_execution_bundle,
    execution_request_sha256,
)
from aec_bench.harness.harbor_dispatch import ENTRYPOINT_AGENT_RUNTIME_NAME
from aec_bench.harness.kernel_catalogue import (
    HarborBackend,
    KernelRuntimeRegistry,
    default_kernel_registry,
)

ADAPTIVE_TASK_INSTRUCTION = "Solve the task and write /workspace/output.md.\n"


def build_adaptive_harness_recipe(
    *,
    task_refs: tuple[str, ...],
    model: str,
    backend: HarborBackend,
    budget: HarnessBudget,
    learned: bool,
) -> HarnessRecipe:
    """Build a neutral direct or output-commit RLM harness for contract tests."""

    registry = default_kernel_registry()
    capability = registry.capability
    recipe_kind = "output-commit-rlm" if learned else "direct"
    agent_capability = "aecbench.adapter.rlm-output-commit" if learned else "aecbench.adapter.direct"
    return HarnessRecipe(
        recipe_id=f"adaptive-test-{recipe_kind}-{backend}",
        version="1.0.0",
        summary="Exercise one adaptive-harness contract fixture under fixed K.",
        budget=budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=task_refs),
            ),
            HarnessBindingSpec(
                binding_id="context",
                capability_ref=capability("aecbench.context.workspace-system-prompt").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=ContextBindingConfig(
                    source_ids=("workspace.system_prompt",),
                    max_tokens=4_000,
                ),
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(agent_capability).ref,
                depends_on=("tasks", "context"),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name=f"adaptive-test-{recipe_kind}",
                    model=model,
                    max_turns=32,
                    timeout_seconds=4_800,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability(f"aecbench.backend.harbor.{backend}").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(
                    max_concurrency=2,
                    timeout_override_seconds=5_400,
                ),
            ),
            HarnessBindingSpec(
                binding_id="verify",
                capability_ref=capability("aecbench.verifier.task").ref,
                depends_on=("compute",),
                topology_role=HarnessTopologyRole.GATE,
                configuration=VerificationBindingConfig(
                    enabled=True,
                    required=True,
                ),
            ),
            HarnessBindingSpec(
                binding_id="import",
                capability_ref=capability("aecbench.results.trial-record").ref,
                depends_on=("verify",),
                topology_role=HarnessTopologyRole.SINK,
                configuration=ResultImportBindingConfig(
                    ledger_namespace=f"adaptive-test-{backend}",
                    required_artifacts=("candidate-manifest",),
                ),
            ),
        ),
    )


def write_adaptive_task(
    tasks_root: Path,
    *,
    task_id: str = "civil/calculation/adaptive",
    system_prompt: str = "Use the task-owned calculator and cite evidence.\n",
    output_completion_contract: dict[str, Any] | None = None,
) -> Path:
    """Write one real, registry-loadable task package with a declared tool and verifier."""
    task_dir = tasks_root / task_id
    (task_dir / "environment" / "tools").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "task.toml").write_text(
        """
[metadata]
difficulty = "easy"
visibility = "public"
tags = ["adaptive"]

[agent]
timeout_sec = 300

[[environment.tools]]
name = "bash"
source = "environment/tools/bash.sh"
description = "Run task-declared shell commands inside the isolated workspace."
returns_image = false
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(
        ADAPTIVE_TASK_INSTRUCTION,
        encoding="utf-8",
    )
    (task_dir / "environment" / "Dockerfile").write_text(
        "FROM python:3.13-slim\nCOPY system_prompt.md /workspace/system_prompt.md\n"
        "COPY tools/bash.sh /workspace/bash.sh\n",
        encoding="utf-8",
    )
    (task_dir / "environment" / "system_prompt.md").write_text(system_prompt, encoding="utf-8")
    if output_completion_contract is not None:
        (task_dir / "environment" / "output_contract.json").write_text(
            json.dumps(output_completion_contract, sort_keys=True),
            encoding="utf-8",
        )
    (task_dir / "environment" / "tools" / "bash.sh").write_text(
        "# ABOUTME: Provides the deterministic shell entrypoint used by adaptive-harness test tasks.\n"
        "# ABOUTME: Exists so the task snapshot binds the exact declared bash tool source.\n"
        "#!/bin/sh\n",
        encoding="utf-8",
    )
    verifier = task_dir / "tests" / "test.sh"
    verifier.write_text(
        "#!/bin/sh\n"
        "# ABOUTME: Verifies the adaptive-harness fixture produced an output artifact.\n"
        "# ABOUTME: Writes a Harbor reward using only real task filesystem state.\n"
        "mkdir -p /logs/verifier\n"
        "test -s /workspace/output.md\n"
        "printf '{\"reward\": 1.0}\\n' > /logs/verifier/reward.json\n",
        encoding="utf-8",
    )
    verifier.chmod(0o755)
    return task_dir


def runtime_attestation_for_harbor_agent(
    agent: dict[str, Any],
    *,
    instruction: str = ADAPTIVE_TASK_INSTRUCTION,
    resolved_model: str | None = None,
) -> dict[str, Any]:
    """Build trusted-runtime-shaped evidence for Harbor integration test executors."""
    kwargs = agent["kwargs"]
    if not isinstance(kwargs, dict):
        raise TypeError("Harbor agent kwargs must be a mapping")
    context = kwargs.get("meta_harness_context")
    if not isinstance(context, dict):
        raise ValueError("adaptive Harbor agent must carry meta_harness_context")
    model = resolved_model or str(agent["model_name"])
    bundle = build_entrypoint_execution_bundle(
        instruction=instruction,
        adapter_name=ENTRYPOINT_AGENT_RUNTIME_NAME,
        model_name=str(agent["model_name"]),
        harbor_kwargs={**kwargs, "extra_env": kwargs.get("extra_env", {})},
    )
    return RuntimeExecutionAttestation(
        adapter_kind=str(kwargs["adapter"]),
        adapter_name="entrypoint",
        requested_model=str(agent["model_name"]),
        resolved_model=model,
        execution_request_sha256=execution_request_sha256(bundle),
        meta_harness_context=MetaHarnessTrajectoryContext.model_validate(context),
    ).model_dump(mode="json")


def build_adaptive_bundle(
    *,
    tasks_root: Path,
    task_id: str = "civil/calculation/adaptive",
    task_ids: tuple[str, ...] | None = None,
    repetitions: int = 1,
    model: str = "claude-test-model",
    program_kind: Literal["monolithic", "fanout"] = "monolithic",
    registry: KernelRuntimeRegistry | None = None,
    budget: HarnessBudget | None = None,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    include_tool_binding: bool = True,
) -> RunBundle:
    """Compile the complete deterministic K/Hx/px/RunBundle test path."""
    resolved_registry = registry or default_kernel_registry()
    resolved_task_ids = task_ids or (task_id,)
    resolved_budget = budget or HarnessBudget()
    capability = resolved_registry.capability
    recipe = HarnessRecipe(
        recipe_id="adaptive-review",
        version="1.0.0",
        summary="Run one exact task through the fixed Harbor kernel.",
        budget=resolved_budget,
        bindings=(
            HarnessBindingSpec(
                binding_id="tasks",
                capability_ref=capability("aecbench.tasks.registry").ref,
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=TaskSourceBindingConfig(task_refs=resolved_task_ids),
            ),
            HarnessBindingSpec(
                binding_id="context",
                capability_ref=capability("aecbench.context.workspace-system-prompt").ref,
                depends_on=("tasks",),
                topology_role=HarnessTopologyRole.SOURCE,
                configuration=ContextBindingConfig(
                    source_ids=("workspace.system_prompt",),
                    max_tokens=4_000,
                ),
            ),
            *(
                (
                    HarnessBindingSpec(
                        binding_id="tools",
                        capability_ref=capability("aecbench.tools.task-declared").ref,
                        depends_on=("tasks",),
                        topology_role=HarnessTopologyRole.SERVICE,
                        configuration=ToolBindingConfig(
                            tool_ids=("bash",),
                            access_mode=ToolAccessMode.EXECUTE,
                            max_calls=16,
                        ),
                    ),
                )
                if include_tool_binding
                else ()
            ),
            HarnessBindingSpec(
                binding_id="agent",
                capability_ref=capability(agent_capability_id).ref,
                depends_on=("tasks", "context", "tools") if include_tool_binding else ("tasks", "context"),
                topology_role=HarnessTopologyRole.ORCHESTRATOR,
                configuration=AgentBindingConfig(
                    agent_name="adaptive-tool-loop",
                    model=model,
                    max_turns=8,
                    timeout_seconds=300,
                ),
            ),
            HarnessBindingSpec(
                binding_id="compute",
                capability_ref=capability("aecbench.backend.harbor.docker").ref,
                depends_on=("agent",),
                topology_role=HarnessTopologyRole.SERVICE,
                configuration=ComputeBindingConfig(
                    max_concurrency=2,
                    timeout_override_seconds=360,
                ),
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
                    ledger_namespace="adaptive-harness",
                    required_artifacts=("candidate-manifest",),
                ),
            ),
        ),
    )
    harness = compile_harness_instance(
        HarnessCompileRequest(
            request_id="compile-adaptive",
            kernel_ref=resolved_registry.manifest.ref,
            recipe=recipe,
        ),
        registry=resolved_registry,
    )
    nodes: tuple[ProgramNode, ...]
    if program_kind == "monolithic":
        nodes = (
            ActionNode(node_id="run", operation_id="run_batch.v1"),
            StopNode(node_id="stop", depends_on=("run",), outcome=StopOutcome.SUCCEEDED),
        )
    else:
        nodes = (
            ActionNode(node_id="enumerate", operation_id="enumerate_tasks.v1"),
            FanoutNode(
                node_id="run-each",
                depends_on=("enumerate",),
                operation_id="run_batch.v1",
                items=ProgramOutputRef(node_id="enumerate", output_port="tasks"),
                item_argument="task_ref",
                max_parallelism=2,
            ),
            StopNode(
                node_id="stop",
                depends_on=("run-each",),
                outcome=StopOutcome.SUCCEEDED,
                result=ProgramOutputRef(node_id="run-each", output_port="result"),
            ),
        )
    program = compile_execution_program(
        ExecutionProgram(
            program_id=f"px-adaptive-{program_kind}",
            version="1.0.0",
            harness_ref=harness.ref,
            nodes=nodes,
            limits=ProgramLimits(
                max_parallelism=resolved_budget.max_parallelism,
                max_total_attempts=resolved_budget.max_total_attempts,
            ),
        ),
        harness=harness,
        registry=resolved_registry,
    )
    return compile_run_bundle(
        bundle_id="bundle-adaptive",
        harness=harness,
        program=program,
        registry=resolved_registry,
        tasks_root=tasks_root,
        experiment_id="adaptive-experiment",
        repetitions=repetitions,
    )
