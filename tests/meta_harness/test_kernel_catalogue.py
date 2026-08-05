# ABOUTME: Tests the trusted host-side registry behind the fixed adaptive-harness kernel K.
# ABOUTME: Verifies exact capability pinning, real runtime mappings, and rejection of arbitrary hooks.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

import aec_bench.meta_harness.kernel_catalogue as kernel_catalogue
from aec_bench.contracts.harness_kernel import (
    KernelCapabilityRef,
    KernelExecutorImplementationIdentity,
    KernelImplementationIdentity,
    KernelManifest,
    KernelSourceDigest,
)
from aec_bench.meta_harness.kernel_catalogue import (
    DEFAULT_KERNEL_DYNAMIC_EXECUTION_SOURCE_PATHS,
    DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS,
    AgentAdapterRuntime,
    KernelOperationArgumentPolicy,
    KernelOperationArgumentSource,
    KernelOperationDefinition,
    KernelOperationEffect,
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
    ProgramOperationRuntime,
    default_kernel_registry,
    verify_kernel_implementation_identity,
)
from tests.support.kernel_source_closure import internal_source_closure

_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS = (
    "aec_bench/meta_harness/program_proposal_compilation/__init__.py",
    "aec_bench/meta_harness/program_proposal_compilation/candidate.py",
    "aec_bench/meta_harness/program_proposal_compilation/compilation.py",
    "aec_bench/meta_harness/program_proposal_compilation/constants.py",
    "aec_bench/meta_harness/program_proposal_compilation/contracts.py",
    "aec_bench/meta_harness/program_proposal_compilation/errors.py",
    "aec_bench/meta_harness/program_proposal_compilation/lowering.py",
    "aec_bench/meta_harness/program_proposal_compilation/profile.py",
    "aec_bench/meta_harness/program_proposal_compilation/profile_validation.py",
)

_COMPILATION_SOURCE_PATHS = (
    "aec_bench/meta_harness/compilation/__init__.py",
    "aec_bench/meta_harness/compilation/bindings.py",
    "aec_bench/meta_harness/compilation/bundle.py",
    "aec_bench/meta_harness/compilation/declared_stages.py",
    "aec_bench/meta_harness/compilation/diagnostics.py",
    "aec_bench/meta_harness/compilation/harness.py",
    "aec_bench/meta_harness/compilation/operations.py",
    "aec_bench/meta_harness/compilation/profile.py",
    "aec_bench/meta_harness/compilation/program.py",
    "aec_bench/meta_harness/compilation/task_surfaces.py",
    "aec_bench/meta_harness/compiler.py",
)

_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS = (
    "aec_bench/harness/proposal_session_runtime/__init__.py",
    "aec_bench/harness/proposal_session_runtime/child_evidence.py",
    "aec_bench/harness/proposal_session_runtime/contracts.py",
    "aec_bench/harness/proposal_session_runtime/kernel.py",
    "aec_bench/harness/proposal_session_runtime/node_execution.py",
    "aec_bench/harness/proposal_session_runtime/preparation.py",
    "aec_bench/harness/proposal_session_runtime/receipts.py",
    "aec_bench/harness/proposal_session_runtime/session.py",
    "aec_bench/harness/proposal_session_runtime/transport.py",
)

_HARBOR_PROPOSAL_IMPORT_SOURCE_PATHS = (
    "aec_bench/harness/harbor_importing/proposal_evidence/__init__.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/api.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/artifacts.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/boundary.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/configuration.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/contracts.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/orchestration.py",
    "aec_bench/harness/harbor_importing/proposal_evidence/seal.py",
)

_MOTIF_LIBRARY_SOURCE_PATHS = (
    "aec_bench/meta_harness/motif_library.py",
    "aec_bench/meta_harness/motifs/__init__.py",
    "aec_bench/meta_harness/motifs/contracts.py",
    "aec_bench/meta_harness/motifs/promotion.py",
    "aec_bench/meta_harness/motifs/selection.py",
    "aec_bench/meta_harness/motifs/store.py",
)

_PROGRAM_EXECUTION_SOURCE_PATHS = (
    "aec_bench/meta_harness/program_execution/__init__.py",
    "aec_bench/meta_harness/program_execution/budget.py",
    "aec_bench/meta_harness/program_execution/contracts.py",
    "aec_bench/meta_harness/program_execution/executor.py",
    "aec_bench/meta_harness/program_execution/registry.py",
    "aec_bench/meta_harness/program_runtime.py",
)

_PROPOSAL_FREEZE_SOURCE_PATHS = (
    "aec_bench/meta_harness/proposal_freeze.py",
    "aec_bench/meta_harness/proposal_freezing/__init__.py",
    "aec_bench/meta_harness/proposal_freezing/contracts.py",
    "aec_bench/meta_harness/proposal_freezing/evidence.py",
    "aec_bench/meta_harness/proposal_freezing/issuance.py",
    "aec_bench/meta_harness/proposal_freezing/replay.py",
    "aec_bench/meta_harness/proposal_freezing/validation.py",
)

_STANDING_MONITOR_SOURCE_PATHS = (
    "aec_bench/meta_harness/monitors.py",
    "aec_bench/meta_harness/standing_monitors/__init__.py",
    "aec_bench/meta_harness/standing_monitors/assertions.py",
    "aec_bench/meta_harness/standing_monitors/evaluation.py",
    "aec_bench/meta_harness/standing_monitors/models.py",
    "aec_bench/meta_harness/standing_monitors/replay.py",
)


def test_default_kernel_catalogue_exposes_real_execution_drivers_and_harbor_backends() -> None:
    registry = default_kernel_registry()

    adapters = {
        primitive.runtime.adapter_kind
        for primitive in registry.primitives
        if isinstance(primitive.runtime, AgentAdapterRuntime)
    }
    capability_ids = {capability.capability_id for capability in registry.manifest.capabilities}

    assert adapters == {"direct", "tool_loop", "rlm", "lambda-rlm"}
    assert {
        "aecbench.backend.harbor.docker",
        "aecbench.backend.harbor.modal",
        "aecbench.backend.harbor.morph",
        "aecbench.operation.harbor.run-batch",
        "aecbench.operation.harbor.run-stage",
        "aecbench.operation.harbor.finalize-task",
        "aecbench.operation.tasks.enumerate",
        "aecbench.context.workspace-system-prompt",
        "aecbench.tools.task-declared",
        "aecbench.verifier.task",
        "aecbench.results.trial-record",
    }.issubset(capability_ids)

    operation_runtimes = tuple(
        primitive.runtime for primitive in registry.primitives if isinstance(primitive.runtime, ProgramOperationRuntime)
    )
    assert operation_runtimes
    assert all(runtime.retry_safe_error_codes == () for runtime in operation_runtimes)


def test_stage_operations_expose_closed_content_addressed_abis() -> None:
    registry = default_kernel_registry()

    run_stage = registry.capability("aecbench.operation.harbor.run-stage")
    assert tuple((port.name, port.schema_ref, port.cardinality.value) for port in run_stage.inputs) == (
        ("task_ref", "aecbench://task-ref/v1", "one"),
        ("stage_id", "aecbench://declared-stage-id/v1", "one"),
        ("upstream_receipts", "aecbench://stage-execution-receipt-ref-or-set/v1", "optional"),
    )
    assert tuple((port.name, port.schema_ref) for port in run_stage.outputs) == (
        ("stage_receipt", "aecbench://stage-execution-receipt-ref/v1"),
    )
    run_stage_runtime = registry.resolve(run_stage.ref).runtime
    assert isinstance(run_stage_runtime, ProgramOperationRuntime)
    assert run_stage_runtime.operation == "harbor_run_stage"

    finalize = registry.capability("aecbench.operation.harbor.finalize-task")
    assert tuple((port.name, port.schema_ref, port.cardinality.value) for port in finalize.inputs) == (
        ("task_ref", "aecbench://task-ref/v1", "one"),
        ("stage_receipts", "aecbench://stage-execution-receipt-set/v1", "many"),
    )
    assert tuple((port.name, port.schema_ref) for port in finalize.outputs) == (
        ("result", "aecbench://harbor-run-result/v1"),
        ("trials", "aecbench://trial-record-set/v1"),
    )
    finalize_runtime = registry.resolve(finalize.ref).runtime
    assert isinstance(finalize_runtime, ProgramOperationRuntime)
    assert finalize_runtime.operation == "harbor_finalize_task"


def test_task_enumeration_has_one_phase_neutral_kernel_operation_definition() -> None:
    registry = default_kernel_registry()

    definition = registry.operation_definition("enumerate_tasks.v1")
    capability = registry.capability("aecbench.operation.tasks.enumerate")
    primitive = registry.resolve(capability.ref)

    assert definition is not None
    assert definition.version == "1.0.0"
    assert definition.capability == capability
    assert definition.capability.content_sha256 == "22a89e39a543dde827bb04071ac4a624b8e6c1fb03e6d2a8ef961696f11c9af2"
    assert definition.runtime == primitive.runtime
    assert definition.input_schema_ref == "aecbench://empty/v1"
    assert definition.output_schema_ref == "aecbench://task-ref-set/v1"
    assert definition.argument_policy is KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION
    assert definition.handler_key is KernelOperationHandlerKey.ENUMERATE_TASK_REFS
    assert definition.effect is KernelOperationEffect.NO_EXTERNAL_EFFECT
    assert tuple(source.path for source in definition.implementation.sources) == (
        *_COMPILATION_SOURCE_PATHS,
        "aec_bench/meta_harness/kernel_catalogue.py",
        *_PROGRAM_EXECUTION_SOURCE_PATHS,
        "aec_bench/meta_harness/run_bundle_runtime.py",
    )


def test_three_low_effect_operations_have_phase_neutral_kernel_definitions() -> None:
    registry = default_kernel_registry()

    expected = {
        "check_subtask_contract.v1": {
            "capability_id": "aecbench.operation.proposal.check-subtask-contract",
            "capability_sha256": "2ff31de8a2a65fe1b4004597c641934eb2882aad2fdc14577b27eb492b32f1da",
            "input_schema_ref": "aecbench://subtask-contract-check-selection/v1",
            "output_schema_ref": "aecbench://subtask-contract-check-ref/v1",
            "argument": (
                "subject",
                KernelOperationArgumentSource.OUTPUT,
                ("result",),
                False,
            ),
            "handler_key": KernelOperationHandlerKey.CHECK_SUBTASK_CONTRACT,
            "effect": KernelOperationEffect.NO_EXTERNAL_EFFECT,
            "implementation_paths": (
                "aec_bench/harness/proposal_node_contract.py",
                "aec_bench/harness/proposal_session.py",
                *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
            ),
            "allow_monolithic_without_arguments": False,
        },
        "finalize_proposed_plan.v1": {
            "capability_id": "aecbench.operation.proposal.finalize-proposed-plan",
            "capability_sha256": "a61139d9bb994e3caec7d81d7b45b604ff0dd3c2d8464c88f9aa891d7d86ef7b",
            "input_schema_ref": "aecbench://finalize-proposed-plan-selection/v1",
            "output_schema_ref": "aecbench://trial-record-set/v1",
            "argument": (
                "findings",
                KernelOperationArgumentSource.OUTPUT,
                ("result",),
                False,
            ),
            "handler_key": KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN,
            "effect": KernelOperationEffect.MODEL_EXECUTION,
            "implementation_paths": (
                "aec_bench/harness/proposal_node_contract.py",
                "aec_bench/harness/proposal_session.py",
                *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
            ),
            "allow_monolithic_without_arguments": True,
        },
        "finalize_task.v1": {
            "capability_id": "aecbench.operation.harbor.finalize-task",
            "capability_sha256": "4d966b725c0fd89818b8bac592e98e9456c31d225e5ba9fd4ffaefbb16ff1748",
            "input_schema_ref": "aecbench://finalize-task-selection/v1",
            "output_schema_ref": "aecbench://trial-record-set/v1",
            "argument": (
                "task_ref",
                KernelOperationArgumentSource.LITERAL_STRING,
                (),
                True,
            ),
            "handler_key": KernelOperationHandlerKey.FINALIZE_TASK,
            "effect": KernelOperationEffect.SCORED_EXECUTION,
            "implementation_paths": (
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/declared_stage_runtime.py",
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_EXECUTION_SOURCE_PATHS,
                "aec_bench/meta_harness/run_bundle_runtime.py",
            ),
            "allow_monolithic_without_arguments": False,
        },
    }

    for operation_id, details in expected.items():
        definition = registry.operation_definition(operation_id)
        capability_id = details["capability_id"]
        assert isinstance(capability_id, str)
        capability = registry.capability(capability_id)

        assert definition is not None
        assert definition.version == "1.0.0"
        assert definition.capability == capability
        assert definition.capability.content_sha256 == details["capability_sha256"]
        assert definition.runtime == registry.resolve(capability.ref).runtime
        assert definition.input_schema_ref == details["input_schema_ref"]
        assert definition.output_schema_ref == details["output_schema_ref"]
        assert definition.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION
        argument = definition.arguments[0]
        assert (
            argument.name,
            argument.source,
            argument.output_ports,
            argument.restrict_to_allowed_task_refs,
        ) == details["argument"]
        assert definition.handler_key is details["handler_key"]
        assert definition.effect is details["effect"]
        assert definition.allow_monolithic_without_arguments is details["allow_monolithic_without_arguments"]
        assert tuple(source.path for source in definition.implementation.sources) == details["implementation_paths"]

    finalize_task = registry.operation_definition("finalize_task.v1")
    assert finalize_task is not None
    assert tuple(argument.name for argument in finalize_task.arguments) == (
        "task_ref",
        "stage_receipts",
    )
    assert finalize_task.arguments[1].source is KernelOperationArgumentSource.OUTPUT
    assert finalize_task.arguments[1].output_ports == ("stage_receipt", "result")


def test_harbor_execution_operations_have_phase_neutral_kernel_definitions() -> None:
    registry = default_kernel_registry()

    expected = {
        "run_batch.v1": {
            "capability_id": "aecbench.operation.harbor.run-batch",
            "capability_sha256": "7a9fd818388b37dc90c5d2d8456a864e82ed76d21f812c6a66b246e87686115d",
            "input_schema_ref": "aecbench://run-batch-selection/v1",
            "output_schema_ref": "aecbench://trial-record-set/v1",
            "handler_key": KernelOperationHandlerKey.RUN_BATCH,
            "effect": KernelOperationEffect.SCORED_EXECUTION,
            "implementation_paths": (
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/harbor_lowering.py",
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_EXECUTION_SOURCE_PATHS,
                "aec_bench/meta_harness/run_bundle_runtime.py",
            ),
        },
        "run_stage.v1": {
            "capability_id": "aecbench.operation.harbor.run-stage",
            "capability_sha256": "bab615dc0c4c811cfb21129c32475321d0ac4e697affa6efe3fd481227f25765",
            "input_schema_ref": "aecbench://run-stage-selection/v1",
            "output_schema_ref": "aecbench://stage-execution-receipt-ref/v1",
            "handler_key": KernelOperationHandlerKey.RUN_STAGE,
            "effect": KernelOperationEffect.UNSCORED_EXECUTION,
            "implementation_paths": (
                "aec_bench/ledger/immutable_artifact_store.py",
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/declared_stage_runtime.py",
                "aec_bench/meta_harness/governed_attempt_engine/__init__.py",
                "aec_bench/meta_harness/governed_attempt_engine/chain_validation.py",
                "aec_bench/meta_harness/governed_attempt_engine/contracts.py",
                "aec_bench/meta_harness/governed_attempt_engine/lifecycle.py",
                "aec_bench/meta_harness/governed_attempt_engine/ports.py",
                "aec_bench/meta_harness/governed_attempt_engine/repository.py",
                "aec_bench/meta_harness/harbor_lowering.py",
                "aec_bench/meta_harness/immutable_artifact_store.py",
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_EXECUTION_SOURCE_PATHS,
                "aec_bench/meta_harness/run_bundle_runtime.py",
                "aec_bench/meta_harness/run_bundle_stage_attempt.py",
            ),
        },
    }

    for operation_id, details in expected.items():
        definition = registry.operation_definition(operation_id)
        capability_id = details["capability_id"]
        assert isinstance(capability_id, str)
        capability = registry.capability(capability_id)

        assert definition is not None
        assert definition.capability == capability
        assert definition.capability.content_sha256 == details["capability_sha256"]
        assert definition.runtime == registry.resolve(capability.ref).runtime
        assert definition.input_schema_ref == details["input_schema_ref"]
        assert definition.output_schema_ref == details["output_schema_ref"]
        assert definition.handler_key is details["handler_key"]
        assert definition.effect is details["effect"]
        assert tuple(source.path for source in definition.implementation.sources) == details["implementation_paths"]

    run_batch = registry.operation_definition("run_batch.v1")
    assert run_batch is not None
    assert run_batch.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION_OR_FANOUT
    assert tuple(
        (
            argument.name,
            argument.source,
            argument.required,
        )
        for argument in run_batch.arguments
    ) == (
        ("task_ref", KernelOperationArgumentSource.PROGRAM_VALUE, False),
        ("task_refs", KernelOperationArgumentSource.PROGRAM_VALUE, False),
    )
    assert run_batch.maximum_arguments == 1
    assert run_batch.fanout_item_argument == "task_ref"

    run_stage = registry.operation_definition("run_stage.v1")
    assert run_stage is not None
    assert run_stage.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION
    assert tuple(
        (
            argument.name,
            argument.source,
            argument.output_ports,
            argument.required,
            argument.restrict_to_allowed_task_refs,
        )
        for argument in run_stage.arguments
    ) == (
        (
            "task_ref",
            KernelOperationArgumentSource.LITERAL_STRING,
            (),
            True,
            True,
        ),
        (
            "stage_id",
            KernelOperationArgumentSource.LITERAL_STRING,
            (),
            True,
            False,
        ),
        (
            "upstream_receipts",
            KernelOperationArgumentSource.OUTPUT,
            ("stage_receipt", "result"),
            False,
            False,
        ),
    )


def test_proposal_execution_operations_have_phase_neutral_kernel_definitions() -> None:
    registry = default_kernel_registry()

    expected = {
        "run_proposal_session.v1": {
            "capability_id": "aecbench.operation.proposal.run-session",
            "capability_sha256": "afda1c7f2673c58171f31c093273685b4db5b64d186e08c8967dbc22b7e1efd1",
            "input_schema_ref": "aecbench://proposal-session-internal/v1",
            "output_schema_ref": "aecbench://proposal-session-receipt/v1",
            "handler_key": KernelOperationHandlerKey.RUN_PROPOSAL_SESSION,
            "effect": KernelOperationEffect.GRAPH_ORCHESTRATION,
            "implementation_paths": (
                "aec_bench/harness/proposal_scheduler.py",
                "aec_bench/harness/proposal_session.py",
                "aec_bench/harness/proposal_session_config.py",
                *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
                "agents/entrypoint_agent.py",
            ),
        },
        "run_semantic_subtask.v1": {
            "capability_id": "aecbench.operation.proposal.run-semantic-subtask",
            "capability_sha256": "3c8287c9d1c6aa7feda394a841ce694d36216b7bde12510ca611e919b5d1b64e",
            "input_schema_ref": "aecbench://semantic-subtask-internal/v1",
            "output_schema_ref": "aecbench://semantic-subtask-result/v1",
            "handler_key": KernelOperationHandlerKey.RUN_SEMANTIC_SUBTASK,
            "effect": KernelOperationEffect.MODEL_EXECUTION,
            "implementation_paths": (
                "aec_bench/harness/proposal_node_context.py",
                "aec_bench/harness/proposal_session.py",
                *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                *_COMPILATION_SOURCE_PATHS,
                "aec_bench/meta_harness/kernel_catalogue.py",
                *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
            ),
        },
    }

    for operation_id, details in expected.items():
        definition = registry.operation_definition(operation_id)
        capability_id = details["capability_id"]
        assert isinstance(capability_id, str)
        capability = registry.capability(capability_id)

        assert definition is not None
        assert definition.capability == capability
        assert definition.capability.content_sha256 == details["capability_sha256"]
        assert definition.runtime == registry.resolve(capability.ref).runtime
        assert definition.input_schema_ref == details["input_schema_ref"]
        assert definition.output_schema_ref == details["output_schema_ref"]
        assert definition.argument_policy is KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION
        assert definition.arguments == ()
        assert definition.handler_key is details["handler_key"]
        assert definition.effect is details["effect"]
        assert tuple(source.path for source in definition.implementation.sources) == details["implementation_paths"]


def test_default_kernel_definitions_cover_every_program_operation_exactly_once() -> None:
    registry = default_kernel_registry()
    operation_capabilities = {
        primitive.spec.capability_id
        for primitive in registry.primitives
        if isinstance(primitive.runtime, ProgramOperationRuntime)
    }

    assert registry.is_legacy_definition_free is False
    assert {
        definition.capability.capability_id for definition in registry.operation_definitions
    } == operation_capabilities

    with pytest.raises(
        KernelRuntimeRegistryError,
        match="must cover every program-operation primitive exactly once",
    ):
        KernelRuntimeRegistry(
            manifest=registry.manifest,
            primitives=registry.primitives,
            package_fingerprint=registry.package_fingerprint,
            operation_definitions=registry.operation_definitions[:-1],
        )

    legacy = KernelRuntimeRegistry(
        manifest=registry.manifest,
        primitives=registry.primitives,
        package_fingerprint=registry.package_fingerprint,
    )
    assert legacy.is_legacy_definition_free is True


def test_default_kernel_registry_rejects_an_omitted_operation_definition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definitions = default_kernel_registry().operation_definitions
    monkeypatch.setattr(
        kernel_catalogue,
        "_default_operation_definitions",
        lambda _sources: definitions[:-1],
    )
    default_kernel_registry.cache_clear()
    try:
        with pytest.raises(
            KernelRuntimeRegistryError,
            match="default kernel registry operation definitions are incomplete",
        ):
            default_kernel_registry()
    finally:
        default_kernel_registry.cache_clear()


def test_operation_definition_implementation_must_belong_to_the_kernel_executor_surface() -> None:
    registry = default_kernel_registry()
    definition = registry.operation_definition("enumerate_tasks.v1")
    assert definition is not None
    outside = definition.model_copy(
        update={
            "implementation": KernelExecutorImplementationIdentity(
                sources=(
                    KernelSourceDigest(
                        path="aec_bench/meta_harness/critic_governance.py",
                        sha256="0" * 64,
                    ),
                )
            )
        }
    )

    with pytest.raises(
        KernelRuntimeRegistryError,
        match="implementation is outside the manifest executor surface",
    ):
        KernelRuntimeRegistry(
            manifest=registry.manifest,
            primitives=registry.primitives,
            operation_definitions=(outside,),
        )


def test_operation_definition_rejects_handler_runtime_or_argument_drift() -> None:
    registry = default_kernel_registry()
    definition = registry.operation_definition("check_subtask_contract.v1")
    assert definition is not None
    payload = definition.model_dump(mode="json", exclude={"content_sha256"})

    with pytest.raises(
        ValidationError,
        match="handler key must match its runtime operation",
    ):
        KernelOperationDefinition.model_validate(
            {
                **payload,
                "handler_key": KernelOperationHandlerKey.FINALIZE_TASK,
            }
        )

    arguments = [dict(argument) for argument in payload["arguments"]]
    arguments[0]["name"] = "candidate_controlled"
    with pytest.raises(
        ValidationError,
        match="arguments must exactly match capability inputs",
    ):
        KernelOperationDefinition.model_validate(
            {
                **payload,
                "arguments": arguments,
            }
        )


def test_k9_proposal_operations_expose_closed_content_addressed_abis() -> None:
    registry = default_kernel_registry()

    expected = {
        "aecbench.operation.proposal.run-session": (
            "proposal_run_session",
            (),
            (
                (
                    "session_receipt",
                    "aecbench://proposal-session-receipt/v1",
                    "one",
                ),
            ),
        ),
        "aecbench.operation.proposal.run-semantic-subtask": (
            "proposal_run_semantic_subtask",
            (),
            (
                (
                    "result",
                    "aecbench://semantic-subtask-result/v1",
                    "one",
                ),
            ),
        ),
        "aecbench.operation.proposal.check-subtask-contract": (
            "proposal_check_subtask_contract",
            (
                (
                    "subject",
                    "aecbench://semantic-subtask-result/v1",
                    "one",
                ),
            ),
            (
                (
                    "result",
                    "aecbench://subtask-contract-check-ref/v1",
                    "one",
                ),
            ),
        ),
        "aecbench.operation.proposal.finalize-proposed-plan": (
            "proposal_finalize_plan",
            (
                (
                    "findings",
                    "aecbench://subtask-contract-check-ref-or-set/v1",
                    "one",
                ),
            ),
            (
                ("result", "aecbench://harbor-run-result/v1", "one"),
                ("trials", "aecbench://trial-record-set/v1", "many"),
            ),
        ),
    }

    for capability_id, (runtime_name, inputs, outputs) in expected.items():
        capability = registry.capability(capability_id)
        primitive = registry.resolve(capability.ref)

        assert isinstance(primitive.runtime, ProgramOperationRuntime)
        assert primitive.runtime.operation == runtime_name
        assert primitive.runtime.retry_safe_error_codes == ()
        assert tuple((port.name, port.schema_ref, port.cardinality.value) for port in capability.inputs) == inputs
        assert tuple((port.name, port.schema_ref, port.cardinality.value) for port in capability.outputs) == outputs


def test_kernel_exposes_explicit_contract_and_commit_rlm_completion_capabilities() -> None:
    registry = default_kernel_registry()

    assert registry.manifest.version == "1.6.4"
    cached_explicit = registry.resolve(registry.capability("aecbench.adapter.rlm").ref).runtime
    explicit = registry.resolve(registry.capability("aecbench.adapter.rlm-uncached").ref).runtime
    contract = registry.resolve(registry.capability("aecbench.adapter.rlm-output-contract").ref).runtime
    commit = registry.resolve(registry.capability("aecbench.adapter.rlm-output-commit").ref).runtime

    assert isinstance(cached_explicit, AgentAdapterRuntime)
    assert cached_explicit.prompt_cache is True
    assert isinstance(explicit, AgentAdapterRuntime)
    assert explicit.adapter_kind == "rlm"
    assert explicit.completion_policy == "explicit_final"
    assert explicit.prompt_cache is False
    assert isinstance(contract, AgentAdapterRuntime)
    assert contract.adapter_kind == "rlm"
    assert contract.completion_policy == "task_output_contract"
    assert contract.prompt_cache is False
    assert isinstance(commit, AgentAdapterRuntime)
    assert commit.adapter_kind == "rlm"
    assert commit.completion_policy == "task_output_commit"
    assert commit.prompt_cache is False


def test_output_commit_completion_policy_is_available_only_to_rlm() -> None:
    runtime = AgentAdapterRuntime.model_validate(
        {
            "adapter_kind": "rlm",
            "completion_policy": "task_output_commit",
            "prompt_cache": False,
        }
    )

    assert runtime.completion_policy == "task_output_commit"

    with pytest.raises(
        ValidationError,
        match="task output-commit completion is supported only by the RLM adapter",
    ):
        AgentAdapterRuntime.model_validate(
            {
                "adapter_kind": "tool_loop",
                "completion_policy": "task_output_commit",
                "prompt_cache": False,
            }
        )


@pytest.mark.parametrize(
    "error_code",
    [
        "harbor_workflow_failed",
        "handler_exception",
        "no_harbor_trials",
        "invalid_harbor_trials",
        "incomplete_harbor_import",
        "runtime_execution_attestation_mismatch",
        "harness_cost_budget_exceeded",
        "global_attempt_budget_exhausted",
        "program_node_failed_without_code",
    ],
)
def test_program_operation_runtime_rejects_effect_unsafe_retry_codes(error_code: str) -> None:
    with pytest.raises(ValidationError, match="prohibited retry-safe error codes"):
        ProgramOperationRuntime(retry_safe_error_codes=(error_code,))


def test_program_operation_runtime_accepts_an_explicit_pre_dispatch_retry_code() -> None:
    runtime = ProgramOperationRuntime(
        retry_safe_error_codes=("pre_dispatch_capacity_timeout",),
    )

    assert runtime.retry_safe_error_codes == ("pre_dispatch_capacity_timeout",)


def test_registry_resolves_only_the_exact_content_pinned_capability() -> None:
    registry = default_kernel_registry()
    capability = registry.capability("aecbench.adapter.lambda-rlm")

    assert registry.resolve(capability.ref).spec == capability

    with pytest.raises(KernelRuntimeRegistryError, match="content-pinned capability"):
        registry.resolve(
            KernelCapabilityRef(
                capability_id=capability.capability_id,
                version=capability.version,
                content_sha256="0" * 64,
            )
        )

    with pytest.raises(KernelRuntimeRegistryError, match="unknown kernel capability"):
        registry.capability("aecbench.adapter.untrusted")


def test_registry_manifest_must_exactly_match_its_runtime_primitives() -> None:
    registry = default_kernel_registry()
    first = registry.primitives[0]

    with pytest.raises(KernelRuntimeRegistryError, match="manifest capabilities must exactly match"):
        KernelRuntimeRegistry(
            manifest=registry.manifest.model_copy(
                update={"capabilities": registry.manifest.capabilities[1:]},
            ),
            primitives=registry.primitives,
        )

    with pytest.raises(KernelRuntimeRegistryError, match="runtime primitive capability ids must be unique"):
        KernelRuntimeRegistry(
            manifest=registry.manifest,
            primitives=(*registry.primitives, first),
        )


def test_runtime_mappings_are_closed_data_not_agent_supplied_import_hooks() -> None:
    runtime = AgentAdapterRuntime(adapter_kind="direct")

    with pytest.raises(ValidationError, match="import_path"):
        AgentAdapterRuntime.model_validate(
            {
                **runtime.model_dump(mode="json"),
                "import_path": "untrusted.module:execute",
            }
        )

    with pytest.raises(ValidationError, match="frozen"):
        runtime.adapter_kind = "rlm"


def test_default_kernel_identity_is_deterministic() -> None:
    first = default_kernel_registry()
    second = default_kernel_registry()

    assert first.manifest == second.manifest
    assert first.manifest.content_sha256 == second.manifest.content_sha256


def test_default_kernel_identity_owns_only_the_explicit_executor_surface() -> None:
    registry = default_kernel_registry()

    assert isinstance(registry.manifest.implementation, KernelExecutorImplementationIdentity)
    executor_paths = tuple(source.path for source in registry.manifest.implementation.sources)

    assert executor_paths == DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS
    assert "agents/entrypoint_agent.py" in executor_paths
    assert "aec_bench/meta_harness/kernel_catalogue.py" in executor_paths
    assert "aec_bench/meta_harness/run_bundle_runtime.py" in executor_paths
    assert "aec_bench/harness/execution_entrypoint.py" in executor_paths
    assert "aec_bench/contracts/world_session.py" in executor_paths
    assert "aec_bench/ledger/durability.py" in executor_paths
    assert "aec_bench/ledger/immutable_artifact_store.py" in executor_paths
    assert "aec_bench/ledger/local_lock.py" in executor_paths
    assert set(_COMPILATION_SOURCE_PATHS).issubset(executor_paths)
    assert set(_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS).issubset(executor_paths)
    assert set(_HARBOR_PROPOSAL_IMPORT_SOURCE_PATHS).issubset(executor_paths)
    assert set(_MOTIF_LIBRARY_SOURCE_PATHS).issubset(executor_paths)
    assert set(_PROGRAM_EXECUTION_SOURCE_PATHS).issubset(executor_paths)
    assert set(_PROPOSAL_FREEZE_SOURCE_PATHS).issubset(executor_paths)
    assert set(_STANDING_MONITOR_SOURCE_PATHS).issubset(executor_paths)
    assert "aec_bench/meta_harness/critic_governance.py" not in executor_paths
    assert "aec_bench/meta_harness/motif_learning.py" not in executor_paths


def test_default_kernel_executor_inventory_is_closed_over_internal_imports() -> None:
    project_root = Path(__file__).resolve().parents[2]
    closure = internal_source_closure(
        project_root=project_root,
        seed_paths=DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS,
        dynamic_paths=DEFAULT_KERNEL_DYNAMIC_EXECUTION_SOURCE_PATHS,
    )
    missing = tuple(sorted(set(closure) - set(DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS)))

    assert set(DEFAULT_KERNEL_DYNAMIC_EXECUTION_SOURCE_PATHS).issubset(DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS)
    assert not missing, (
        "fixed K must own every transitively imported internal source and dynamically "
        f"executed kernel module; missing: {', '.join(missing)}"
    )


def test_default_registry_records_whole_package_fingerprint_outside_fixed_kernel_identity() -> None:
    registry = default_kernel_registry()

    assert registry.package_fingerprint is not None
    package_paths = {source.path for source in registry.package_fingerprint.sources}
    executor_paths = {source.path for source in registry.manifest.implementation.sources}

    assert executor_paths < package_paths
    assert "aec_bench/meta_harness/critic_governance.py" in package_paths
    assert "aec_bench/meta_harness/motif_learning.py" in package_paths
    assert registry.package_fingerprint.content_sha256 != registry.manifest.implementation.content_sha256


def test_non_executor_package_drift_does_not_change_fixed_kernel_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = default_kernel_registry()
    assert baseline.package_fingerprint is not None
    changed_package_sources = tuple(
        source
        for source in baseline.package_fingerprint.sources
        if source.path != "aec_bench/meta_harness/critic_governance.py"
    )
    assert changed_package_sources != baseline.package_fingerprint.sources

    monkeypatch.setattr(
        kernel_catalogue,
        "_package_source_inventory",
        lambda: changed_package_sources,
    )
    default_kernel_registry.cache_clear()
    changed = default_kernel_registry()

    assert changed.manifest.ref == baseline.manifest.ref
    assert changed.package_fingerprint != baseline.package_fingerprint
    default_kernel_registry.cache_clear()


def test_default_kernel_identity_rejects_live_source_inventory_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = default_kernel_registry()
    pinned_sources = registry.manifest.implementation.sources
    monkeypatch.setattr(
        kernel_catalogue,
        "_kernel_source_inventory",
        lambda: pinned_sources[:-1],
    )

    with pytest.raises(KernelRuntimeRegistryError, match="implementation source inventory drifted"):
        verify_kernel_implementation_identity(registry)


def test_legacy_whole_package_kernel_identity_remains_verifiable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = default_kernel_registry()
    package_sources = kernel_catalogue._package_source_inventory()
    legacy_manifest = KernelManifest(
        kernel_id=current.manifest.kernel_id,
        version=current.manifest.version,
        capabilities=current.manifest.capabilities,
        implementation=KernelImplementationIdentity(sources=package_sources),
    )
    legacy_registry = KernelRuntimeRegistry(
        manifest=legacy_manifest,
        primitives=current.primitives,
    )

    verify_kernel_implementation_identity(legacy_registry)

    monkeypatch.setattr(
        kernel_catalogue,
        "_package_source_inventory",
        lambda: package_sources[:-1],
    )
    with pytest.raises(KernelRuntimeRegistryError, match="implementation source inventory drifted"):
        verify_kernel_implementation_identity(legacy_registry)
