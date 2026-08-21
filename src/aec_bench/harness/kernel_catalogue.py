# ABOUTME: Defines the trusted host-side runtime catalogue for fixed adaptive-harness kernel K.
# ABOUTME: Maps content-pinned capabilities to closed runtime data without agent-controlled import hooks.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_instance import prohibited_retry_safe_error_codes
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityKind,
    KernelCapabilityRef,
    KernelCapabilitySpec,
    KernelExecutorImplementationIdentity,
    KernelImplementationIdentity,
    KernelManifest,
    KernelPortCardinality,
    KernelPortSpec,
    KernelSourceDigest,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr


class KernelRuntimeRegistryError(ValueError):
    """Raised when a capability does not resolve against the trusted fixed kernel."""


DEFAULT_KERNEL_ID = "aec-bench.adaptive-harness"
DEFAULT_KERNEL_VERSION = "1.7.0"
DEFAULT_KERNEL_OPERATION_IDS: frozenset[str] = frozenset(
    {
        "check_subtask_contract",
        "enumerate_tasks",
        "finalize_proposed_plan",
        "finalize_task",
        "run_batch",
        "run_proposal_session",
        "run_semantic_subtask",
        "run_stage",
    }
)

_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS = (
    "aec_bench/experimentation/proposals/program_compilation/__init__.py",
    "aec_bench/experimentation/proposals/program_compilation/candidate.py",
    "aec_bench/experimentation/proposals/program_compilation/compilation.py",
    "aec_bench/experimentation/proposals/program_compilation/constants.py",
    "aec_bench/experimentation/proposals/program_compilation/contracts.py",
    "aec_bench/experimentation/proposals/program_compilation/errors.py",
    "aec_bench/experimentation/proposals/program_compilation/lowering.py",
    "aec_bench/experimentation/proposals/program_compilation/profile.py",
    "aec_bench/experimentation/proposals/program_compilation/profile_validation.py",
)

_COMPILATION_SOURCE_PATHS = (
    "aec_bench/harness/compilation/__init__.py",
    "aec_bench/harness/compilation/bindings.py",
    "aec_bench/harness/compilation/bundle.py",
    "aec_bench/harness/compilation/declared_stages.py",
    "aec_bench/harness/compilation/diagnostics.py",
    "aec_bench/harness/compilation/harness.py",
    "aec_bench/harness/compilation/operations.py",
    "aec_bench/harness/compilation/profile.py",
    "aec_bench/harness/compilation/program.py",
    "aec_bench/harness/compilation/task_surfaces.py",
)

_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS = (
    "aec_bench/experimentation/proposals/session_runtime/__init__.py",
    "aec_bench/experimentation/proposals/session_runtime/child_evidence.py",
    "aec_bench/experimentation/proposals/session_runtime/contracts.py",
    "aec_bench/experimentation/proposals/session_runtime/kernel.py",
    "aec_bench/experimentation/proposals/session_runtime/node_execution.py",
    "aec_bench/experimentation/proposals/session_runtime/preparation.py",
    "aec_bench/experimentation/proposals/session_runtime/receipts.py",
    "aec_bench/experimentation/proposals/session_runtime/session.py",
    "aec_bench/experimentation/proposals/session_runtime/transport.py",
)

_HARBOR_PROPOSAL_IMPORT_SOURCE_PATHS = (
    "aec_bench/experimentation/proposals/harbor_import/__init__.py",
    "aec_bench/experimentation/proposals/harbor_import/api.py",
    "aec_bench/experimentation/proposals/harbor_import/artifacts.py",
    "aec_bench/experimentation/proposals/harbor_import/boundary.py",
    "aec_bench/experimentation/proposals/harbor_import/configuration.py",
    "aec_bench/experimentation/proposals/harbor_import/contracts.py",
    "aec_bench/experimentation/proposals/harbor_import/orchestration.py",
    "aec_bench/experimentation/proposals/harbor_import/seal.py",
)

_MOTIF_LIBRARY_SOURCE_PATHS = (
    "aec_bench/experimentation/governance/motifs/__init__.py",
    "aec_bench/experimentation/governance/motifs/contracts.py",
    "aec_bench/experimentation/governance/motifs/promotion.py",
    "aec_bench/experimentation/governance/motifs/selection.py",
    "aec_bench/experimentation/governance/motifs/store.py",
)

_PROGRAM_EXECUTION_SOURCE_PATHS = (
    "aec_bench/harness/program_execution/__init__.py",
    "aec_bench/harness/program_execution/budget.py",
    "aec_bench/harness/program_execution/contracts.py",
    "aec_bench/harness/program_execution/executor.py",
    "aec_bench/harness/program_execution/registry.py",
)

_PROPOSAL_FREEZE_SOURCE_PATHS = (
    "aec_bench/experimentation/proposals/freezing/__init__.py",
    "aec_bench/experimentation/proposals/freezing/contracts.py",
    "aec_bench/experimentation/proposals/freezing/evidence.py",
    "aec_bench/experimentation/proposals/freezing/issuance.py",
    "aec_bench/experimentation/proposals/freezing/replay.py",
    "aec_bench/experimentation/proposals/freezing/validation.py",
)

_STANDING_MONITOR_SOURCE_PATHS = (
    "aec_bench/experimentation/governance/standing_monitors/__init__.py",
    "aec_bench/experimentation/governance/standing_monitors/assertions.py",
    "aec_bench/experimentation/governance/standing_monitors/evaluation.py",
    "aec_bench/experimentation/governance/standing_monitors/models.py",
    "aec_bench/experimentation/governance/standing_monitors/replay.py",
)

# These modules execute by module name rather than through a statically visible
# Python import and therefore require an explicit fixed-K ownership declaration.
DEFAULT_KERNEL_DYNAMIC_EXECUTION_SOURCE_PATHS = (
    "aec_bench/harness/execution_entrypoint.py",
    "aec_bench/harness/model_execution/operation_model_runner.py",
    "aec_bench/harness/provider_broker_bootstrap.py",
)

# This is an exact reviewed allowlist. The independent closure test rejects an
# internal import or dynamic execution edge that is not part of fixed K.
DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS: tuple[str, ...] = (
    "aec_bench/__init__.py",
    "aec_bench/adapters/__init__.py",
    "aec_bench/adapters/advisor.py",
    "aec_bench/adapters/advisor_usage.py",
    "aec_bench/adapters/base.py",
    "aec_bench/adapters/config.py",
    "aec_bench/adapters/constitutional.py",
    "aec_bench/adapters/direct.py",
    "aec_bench/adapters/direct_providers.py",
    "aec_bench/adapters/lambda_rlm/__init__.py",
    "aec_bench/adapters/lambda_rlm/adapter.py",
    "aec_bench/adapters/lambda_rlm/combinators.py",
    "aec_bench/adapters/lambda_rlm/compose_bridge.py",
    "aec_bench/adapters/lambda_rlm/config.py",
    "aec_bench/adapters/lambda_rlm/consistency.py",
    "aec_bench/adapters/lambda_rlm/criteria.py",
    "aec_bench/adapters/lambda_rlm/executor.py",
    "aec_bench/adapters/lambda_rlm/grounding.py",
    "aec_bench/adapters/lambda_rlm/initialiser.py",
    "aec_bench/adapters/lambda_rlm/planner.py",
    "aec_bench/adapters/lambda_rlm/prompts.py",
    "aec_bench/adapters/lambda_rlm/review.py",
    "aec_bench/adapters/lambda_rlm/sandbox.py",
    "aec_bench/adapters/lambda_rlm/sandbox_tools.py",
    "aec_bench/adapters/lambda_rlm/state.py",
    "aec_bench/adapters/lambda_rlm/structure_validator.py",
    "aec_bench/adapters/lambda_rlm/synthesis.py",
    "aec_bench/adapters/lambda_rlm/task_handlers.py",
    "aec_bench/adapters/lambda_rlm/uncertainty.py",
    "aec_bench/adapters/local_registry.py",
    "aec_bench/adapters/prime_agent.py",
    "aec_bench/adapters/pydantic_ai_runtime.py",
    "aec_bench/adapters/rlm/__init__.py",
    "aec_bench/adapters/rlm/adapter.py",
    "aec_bench/adapters/rlm/client.py",
    "aec_bench/adapters/rlm/compaction.py",
    "aec_bench/adapters/rlm/compaction_runtime.py",
    "aec_bench/adapters/rlm/config.py",
    "aec_bench/adapters/rlm/context_filter.py",
    "aec_bench/adapters/rlm/engine.py",
    "aec_bench/adapters/rlm/errors.py",
    "aec_bench/adapters/rlm/execution_lifecycle.py",
    "aec_bench/adapters/rlm/fill_parallel.py",
    "aec_bench/adapters/rlm/guardrails.py",
    "aec_bench/adapters/rlm/initialiser.py",
    "aec_bench/adapters/rlm/metadata.py",
    "aec_bench/adapters/rlm/output_commit.py",
    "aec_bench/adapters/rlm/parallel.py",
    "aec_bench/adapters/rlm/prompt_surface.py",
    "aec_bench/adapters/rlm/providers.py",
    "aec_bench/adapters/rlm/repl_runtime.py",
    "aec_bench/adapters/rlm/request_runtime.py",
    "aec_bench/adapters/rlm/runtime_contracts.py",
    "aec_bench/adapters/rlm/scaffolding.py",
    "aec_bench/adapters/rlm/scratchpad.py",
    "aec_bench/adapters/rlm/subcall_log.py",
    "aec_bench/adapters/rlm/subcall_registry.py",
    "aec_bench/adapters/rlm/subcalls.py",
    "aec_bench/adapters/rlm/template.py",
    "aec_bench/adapters/rlm/template_parser.py",
    "aec_bench/adapters/rlm/tokens.py",
    "aec_bench/adapters/rlm/turn_execution.py",
    "aec_bench/adapters/rlm/turn_runtime.py",
    "aec_bench/adapters/runtime_limits.py",
    "aec_bench/adapters/tool_loop.py",
    "aec_bench/adapters/tool_loop_local.py",
    "aec_bench/adapters/tools/__init__.py",
    "aec_bench/adapters/tools/bash.py",
    "aec_bench/adapters/tools/codes_search.py",
    "aec_bench/adapters/tools/registry.py",
    "aec_bench/agents/__init__.py",
    "aec_bench/agents/env.py",
    "aec_bench/agents/providers.py",
    "aec_bench/agents/results.py",
    "aec_bench/agents/tools.py",
    "aec_bench/config.py",
    "aec_bench/contracts/__init__.py",
    "aec_bench/contracts/adaptation.py",
    "aec_bench/contracts/adapter_execution.py",
    "aec_bench/contracts/advisor.py",
    "aec_bench/contracts/agent_output.py",
    "aec_bench/contracts/authority.py",
    "aec_bench/contracts/behavioral_types.py",
    "aec_bench/contracts/constitution.py",
    "aec_bench/contracts/continual_world.py",
    "aec_bench/contracts/dataset.py",
    "aec_bench/contracts/evaluation_generation/__init__.py",
    "aec_bench/contracts/evaluation_generation/cohort.py",
    "aec_bench/contracts/evaluation_outcome.py",
    "aec_bench/contracts/evaluation_plane.py",
    "aec_bench/contracts/evaluation_result.py",
    "aec_bench/contracts/evidence_lifecycle.py",
    "aec_bench/contracts/execution_environment.py",
    "aec_bench/contracts/execution_program.py",
    "aec_bench/contracts/experiment_manifest.py",
    "aec_bench/contracts/grounding_report.py",
    "aec_bench/contracts/harness_instance.py",
    "aec_bench/contracts/harness_kernel.py",
    "aec_bench/contracts/interactive_world.py",
    "aec_bench/contracts/jsonl.py",
    "aec_bench/contracts/lifecycle_evaluation.py",
    "aec_bench/contracts/output_completion.py",
    "aec_bench/contracts/pricing.py",
    "aec_bench/contracts/program_proposal/__init__.py",
    "aec_bench/contracts/program_proposal/_canonical.py",
    "aec_bench/contracts/program_proposal/candidate.py",
    "aec_bench/contracts/program_proposal/freeze.py",
    "aec_bench/contracts/program_proposal/problem.py",
    "aec_bench/contracts/program_proposal/study.py",
    "aec_bench/contracts/program_proposal/types.py",
    "aec_bench/contracts/proposal_compilation_verifier.py",
    "aec_bench/contracts/proposal_execution/__init__.py",
    "aec_bench/contracts/proposal_execution/_canonical.py",
    "aec_bench/contracts/proposal_execution/compilation.py",
    "aec_bench/contracts/proposal_execution/graph.py",
    "aec_bench/contracts/proposal_execution/session.py",
    "aec_bench/contracts/proposal_execution_budget.py",
    "aec_bench/contracts/proposal_execution_context.py",
    "aec_bench/contracts/proposal_execution_profile.py",
    "aec_bench/contracts/proposal_execution_types.py",
    "aec_bench/contracts/proposal_graph_verifier.py",
    "aec_bench/contracts/proposal_session_verifier.py",
    "aec_bench/contracts/provider_broker.py",
    "aec_bench/contracts/repl.py",
    "aec_bench/contracts/report_template.py",
    "aec_bench/contracts/rubric.py",
    "aec_bench/contracts/run_bundle.py",
    "aec_bench/contracts/stage_execution.py",
    "aec_bench/contracts/synthesis.py",
    "aec_bench/contracts/task_definition.py",
    "aec_bench/contracts/task_review.py",
    "aec_bench/contracts/trajectory.py",
    "aec_bench/contracts/trial_record.py",
    "aec_bench/contracts/validators.py",
    "aec_bench/contracts/world_interface.py",
    "aec_bench/contracts/world_session.py",
    "aec_bench/dataset/__init__.py",
    "aec_bench/dataset/storage.py",
    "aec_bench/evaluation/__init__.py",
    "aec_bench/evaluation/aggregation.py",
    "aec_bench/evaluation/behavioral.py",
    "aec_bench/evaluation/confidence.py",
    "aec_bench/evaluation/lifecycle.py",
    "aec_bench/evaluation/llm_judge.py",
    "aec_bench/evaluation/logic_profile.py",
    "aec_bench/evaluation/pipeline.py",
    "aec_bench/evaluation/rubric_scorer.py",
    "aec_bench/evaluation/stats.py",
    "aec_bench/evaluation/task_review.py",
    "aec_bench/evaluation/trace_summary.py",
    "aec_bench/experimentation/__init__.py",
    "aec_bench/experimentation/governance/__init__.py",
    "aec_bench/experimentation/governance/applicability.py",
    "aec_bench/experimentation/governance/authority_ledger.py",
    "aec_bench/experimentation/governance/authority_validation/__init__.py",
    "aec_bench/experimentation/governance/authority_validation/promotion.py",
    "aec_bench/experimentation/governance/motifs/__init__.py",
    "aec_bench/experimentation/governance/motifs/contracts.py",
    "aec_bench/experimentation/governance/motifs/promotion.py",
    "aec_bench/experimentation/governance/motifs/selection.py",
    "aec_bench/experimentation/governance/motifs/store.py",
    "aec_bench/experimentation/governance/standing_monitors/__init__.py",
    "aec_bench/experimentation/governance/standing_monitors/assertions.py",
    "aec_bench/experimentation/governance/standing_monitors/evaluation.py",
    "aec_bench/experimentation/governance/standing_monitors/models.py",
    "aec_bench/experimentation/governance/standing_monitors/replay.py",
    "aec_bench/experimentation/proposals/__init__.py",
    "aec_bench/experimentation/proposals/environment_pool.py",
    "aec_bench/experimentation/proposals/freezing/__init__.py",
    "aec_bench/experimentation/proposals/freezing/contracts.py",
    "aec_bench/experimentation/proposals/freezing/evidence.py",
    "aec_bench/experimentation/proposals/freezing/issuance.py",
    "aec_bench/experimentation/proposals/freezing/replay.py",
    "aec_bench/experimentation/proposals/freezing/validation.py",
    "aec_bench/experimentation/proposals/harbor_import/__init__.py",
    "aec_bench/experimentation/proposals/harbor_import/api.py",
    "aec_bench/experimentation/proposals/harbor_import/artifacts.py",
    "aec_bench/experimentation/proposals/harbor_import/boundary.py",
    "aec_bench/experimentation/proposals/harbor_import/configuration.py",
    "aec_bench/experimentation/proposals/harbor_import/contracts.py",
    "aec_bench/experimentation/proposals/harbor_import/orchestration.py",
    "aec_bench/experimentation/proposals/harbor_import/seal.py",
    "aec_bench/experimentation/proposals/morph/__init__.py",
    "aec_bench/experimentation/proposals/morph/async_ops.py",
    "aec_bench/experimentation/proposals/morph/boundary.py",
    "aec_bench/experimentation/proposals/morph/cleanup.py",
    "aec_bench/experimentation/proposals/morph/confinement.py",
    "aec_bench/experimentation/proposals/morph/constants.py",
    "aec_bench/experimentation/proposals/morph/environment.py",
    "aec_bench/experimentation/proposals/morph/evidence.py",
    "aec_bench/experimentation/proposals/morph/operations.py",
    "aec_bench/experimentation/proposals/morph/provisioning.py",
    "aec_bench/experimentation/proposals/morph_cloud.py",
    "aec_bench/experimentation/proposals/node_context.py",
    "aec_bench/experimentation/proposals/node_contract.py",
    "aec_bench/experimentation/proposals/problem_view.py",
    "aec_bench/experimentation/proposals/program_compilation/__init__.py",
    "aec_bench/experimentation/proposals/program_compilation/candidate.py",
    "aec_bench/experimentation/proposals/program_compilation/compilation.py",
    "aec_bench/experimentation/proposals/program_compilation/constants.py",
    "aec_bench/experimentation/proposals/program_compilation/contracts.py",
    "aec_bench/experimentation/proposals/program_compilation/errors.py",
    "aec_bench/experimentation/proposals/program_compilation/lowering.py",
    "aec_bench/experimentation/proposals/program_compilation/profile.py",
    "aec_bench/experimentation/proposals/program_compilation/profile_validation.py",
    "aec_bench/experimentation/proposals/runtime_archive.py",
    "aec_bench/experimentation/proposals/scheduler.py",
    "aec_bench/experimentation/proposals/session_config.py",
    "aec_bench/experimentation/proposals/session_evidence.py",
    "aec_bench/experimentation/proposals/session_output.py",
    "aec_bench/experimentation/proposals/session_runtime/__init__.py",
    "aec_bench/experimentation/proposals/session_runtime/child_evidence.py",
    "aec_bench/experimentation/proposals/session_runtime/contracts.py",
    "aec_bench/experimentation/proposals/session_runtime/kernel.py",
    "aec_bench/experimentation/proposals/session_runtime/node_execution.py",
    "aec_bench/experimentation/proposals/session_runtime/preparation.py",
    "aec_bench/experimentation/proposals/session_runtime/receipts.py",
    "aec_bench/experimentation/proposals/session_runtime/session.py",
    "aec_bench/experimentation/proposals/session_runtime/transport.py",
    "aec_bench/experimentation/proposals/session_serialization.py",
    "aec_bench/experimentation/proposals/structural_corpus.py",
    "aec_bench/experimentation/proposals/task_package.py",
    "aec_bench/experimentation/proposals/task_packaging/__init__.py",
    "aec_bench/experimentation/proposals/task_packaging/build_context.py",
    "aec_bench/experimentation/proposals/task_packaging/contracts.py",
    "aec_bench/experimentation/proposals/task_packaging/file_io.py",
    "aec_bench/experimentation/qualification/__init__.py",
    "aec_bench/experimentation/qualification/adaptive_cycle_corpus.py",
    "aec_bench/experimentation/qualification/run_bundle_evidence.py",
    "aec_bench/experimentation/qualification/run_bundle_runtime.py",
    "aec_bench/experimentation/qualification/run_bundle_scored_attempt.py",
    "aec_bench/experimentation/qualification/run_bundle_scored_plan.py",
    "aec_bench/experimentation/qualification/run_bundle_stage_attempt.py",
    "aec_bench/harness/__init__.py",
    "aec_bench/harness/budget.py",
    "aec_bench/harness/compilation/__init__.py",
    "aec_bench/harness/compilation/bindings.py",
    "aec_bench/harness/compilation/bundle.py",
    "aec_bench/harness/compilation/declared_stages.py",
    "aec_bench/harness/compilation/diagnostics.py",
    "aec_bench/harness/compilation/harness.py",
    "aec_bench/harness/compilation/operations.py",
    "aec_bench/harness/compilation/profile.py",
    "aec_bench/harness/compilation/program.py",
    "aec_bench/harness/compilation/task_snapshot.py",
    "aec_bench/harness/compilation/task_surface.py",
    "aec_bench/harness/compilation/task_surfaces.py",
    "aec_bench/harness/contract_enforcement.py",
    "aec_bench/harness/declared_stage.py",
    "aec_bench/harness/execution_entrypoint.py",
    "aec_bench/harness/execution_payload.py",
    "aec_bench/harness/experiment_runner.py",
    "aec_bench/harness/governed_attempt/__init__.py",
    "aec_bench/harness/governed_attempt/chain_validation.py",
    "aec_bench/harness/governed_attempt/contracts.py",
    "aec_bench/harness/governed_attempt/lifecycle.py",
    "aec_bench/harness/governed_attempt/ports.py",
    "aec_bench/harness/governed_attempt/repository.py",
    "aec_bench/harness/governed_attempt/trial_usage.py",
    "aec_bench/harness/harbor_contract.py",
    "aec_bench/harness/harbor_dispatch.py",
    "aec_bench/harness/harbor_importing/__init__.py",
    "aec_bench/harness/harbor_importing/artifact_io.py",
    "aec_bench/harness/harbor_importing/contracts.py",
    "aec_bench/harness/harbor_importing/core.py",
    "aec_bench/harness/harbor_importing/output_commit.py",
    "aec_bench/harness/harbor_lowering.py",
    "aec_bench/harness/harbor_task_export.py",
    "aec_bench/harness/harbor_task_exporting/__init__.py",
    "aec_bench/harness/harbor_task_exporting/bridge.py",
    "aec_bench/harness/harbor_task_exporting/constants.py",
    "aec_bench/harness/harbor_task_exporting/runtime_wheel.py",
    "aec_bench/harness/harbor_task_exporting/stable_io.py",
    "aec_bench/harness/harbor_task_exporting/surfaces.py",
    "aec_bench/harness/harbor_workflow.py",
    "aec_bench/harness/kernel_catalogue.py",
    "aec_bench/harness/lifecycle_local.py",
    "aec_bench/harness/model_execution/__init__.py",
    "aec_bench/harness/model_execution/llm_reviewer.py",
    "aec_bench/harness/model_execution/model_runner.py",
    "aec_bench/harness/model_execution/operation_model_runner.py",
    "aec_bench/harness/process_runtime/__init__.py",
    "aec_bench/harness/process_runtime/harbor_task.py",
    "aec_bench/harness/process_runtime/operation_orchestrator.py",
    "aec_bench/harness/process_runtime/operation_profile.py",
    "aec_bench/harness/process_runtime/problem_model_process.py",
    "aec_bench/harness/program_execution/__init__.py",
    "aec_bench/harness/program_execution/budget.py",
    "aec_bench/harness/program_execution/contracts.py",
    "aec_bench/harness/program_execution/executor.py",
    "aec_bench/harness/program_execution/registry.py",
    "aec_bench/harness/progress_tracker.py",
    "aec_bench/harness/provider_broker.py",
    "aec_bench/harness/provider_broker_bootstrap.py",
    "aec_bench/harness/provider_broker_runtime.py",
    "aec_bench/harness/pump_station_harbor/__init__.py",
    "aec_bench/harness/pump_station_harbor/export.py",
    "aec_bench/harness/pump_station_harbor/importing.py",
    "aec_bench/harness/pump_station_harbor/session.py",
    "aec_bench/harness/pump_station_harbor/verifier.py",
    "aec_bench/harness/scheduler.py",
    "aec_bench/harness/trial_record_builder.py",
    "aec_bench/harness/verifier_artifacts.py",
    "aec_bench/ledger/__init__.py",
    "aec_bench/ledger/durability.py",
    "aec_bench/ledger/immutable_artifact_store.py",
    "aec_bench/ledger/immutable_byte_store.py",
    "aec_bench/ledger/local_lock.py",
    "aec_bench/ledger/process_log.py",
    "aec_bench/ledger/writer.py",
    "aec_bench/lifecycles/__init__.py",
    "aec_bench/lifecycles/application.py",
    "aec_bench/lifecycles/catalogue.py",
    "aec_bench/lifecycles/compiled.py",
    "aec_bench/lifecycles/recording.py",
    "aec_bench/lifecycles/runtime/__init__.py",
    "aec_bench/lifecycles/runtime/episode.py",
    "aec_bench/lifecycles/runtime/lifecycle.py",
    "aec_bench/lifecycles/runtime/operation_protocol.py",
    "aec_bench/lifecycles/runtime/operation_snapshot.py",
    "aec_bench/lifecycles/runtime/operation_store.py",
    "aec_bench/lifecycles/runtime/request_protocol.py",
    "aec_bench/lifecycles/runtime/request_store.py",
    "aec_bench/lifecycles/runtime/state.py",
    "aec_bench/lifecycles/session_records.py",
    "aec_bench/lifecycles/stormwater_design/__init__.py",
    "aec_bench/lifecycles/stormwater_design/design_response.py",
    "aec_bench/lifecycles/stormwater_design/design_response_operations.py",
    "aec_bench/lifecycles/stormwater_design/design_response_smoke.py",
    "aec_bench/lifecycles/stormwater_design/design_response_verifier.py",
    "aec_bench/lifecycles/stormwater_design/drainage_model.py",
    "aec_bench/lifecycles/stormwater_design/drainage_variants.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_evidence.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_operations.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_review.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_review_smoke.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_review_variants.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_review_verifier.py",
    "aec_bench/lifecycles/stormwater_design/hydraulic_smoke.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/__init__.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/calculation.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/identity.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/interventions.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/models.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/package.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/report.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/revisions.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/source.py",
    "aec_bench/lifecycles/stormwater_design/hydraulics/verifier.py",
    "aec_bench/lifecycles/structural_review/__init__.py",
    "aec_bench/lifecycles/structural_review/facade_submittal.py",
    "aec_bench/lifecycles/trial_record.py",
    "aec_bench/lifecycles/values.py",
    "aec_bench/model_routing.py",
    "aec_bench/prime_agent/__init__.py",
    "aec_bench/prime_agent/batch.py",
    "aec_bench/prime_agent/events.py",
    "aec_bench/providers/__init__.py",
    "aec_bench/providers/behavioral_llm.py",
    "aec_bench/providers/morph_cloud.py",
    "aec_bench/synthesis/__init__.py",
    "aec_bench/synthesis/engine.py",
    "aec_bench/synthesis/prompts.py",
    "aec_bench/synthesis/tool_loop.py",
    "aec_bench/synthesis/tools.py",
    "aec_bench/tasks/__init__.py",
    "aec_bench/tasks/loader.py",
    "aec_bench/tasks/registry.py",
    "aec_bench/tasks/selector.py",
    "aec_bench/templates/__init__.py",
    "aec_bench/templates/builtin/__init__.py",
    "aec_bench/templates/builtin/structural/__init__.py",
    "aec_bench/templates/builtin/structural/facade_submittal_source_policy_package/__init__.py",
    "aec_bench/templates/builtin/structural/facade_submittal_source_policy_package/engine.py",
    "aec_bench/templates/contracts.py",
    "aec_bench/templates/report/__init__.py",
    "aec_bench/templates/report/composer.py",
    "aec_bench/trajectory/__init__.py",
    "aec_bench/trajectory/writer.py",
    "aec_bench/trials.py",
    "aec_bench/worlds/__init__.py",
    "aec_bench/worlds/catalogue.py",
    "aec_bench/worlds/monitoring/__init__.py",
    "aec_bench/worlds/monitoring/dam_seepage/__init__.py",
    "aec_bench/worlds/monitoring/dam_seepage/definition.py",
    "aec_bench/worlds/monitoring/dam_seepage/world.py",
    "aec_bench/worlds/runtime/__init__.py",
    "aec_bench/worlds/runtime/branch_port.py",
    "aec_bench/worlds/runtime/definition.py",
    "aec_bench/worlds/runtime/episode.py",
    "aec_bench/worlds/runtime/world_logic.py",
    "aec_bench/worlds/stewardship/__init__.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/__init__.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/actor_interface.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/continual_definition.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/continual_rollout_adapter.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/coupled_runtime.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/coupled_work.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/episode_runtime.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/evaluation.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/evidence_health.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/physical_kernel.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/physical_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/reference_controller.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/reference_package_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/reference_package_reader.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/reference_system.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/rollout_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/stewardship_identity.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/stewardship_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/stewardship_verifier.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/stewardship_views.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/__init__.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/access_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/corpus.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/gateway.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/repository.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/temporal_evidence/verification.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/time_presentation.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/world_control.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/world_run.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/world_run_models.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/world_run_repository.py",
    "aec_bench/worlds/stewardship/wastewater_pump_station/world_run_serialization.py",
    "agents/__init__.py",
    "agents/entrypoint_agent.py",
)


class TaskSourceRuntime(FrozenStrictModel):
    runtime_kind: Literal["task_registry"] = "task_registry"


AdapterKind = Literal["direct", "tool_loop", "rlm", "lambda-rlm"]
HarborBackend = Literal["docker", "modal", "e2b", "daytona", "morph"]
AgentCompletionPolicy = Literal[
    "explicit_final",
    "task_output_contract",
    "task_output_commit",
]


class AgentAdapterRuntime(FrozenStrictModel):
    runtime_kind: Literal["agent_adapter"] = "agent_adapter"
    adapter_kind: AdapterKind
    completion_policy: AgentCompletionPolicy = "explicit_final"
    prompt_cache: bool = True

    @model_validator(mode="after")
    def validate_completion_policy(self) -> Self:
        if self.completion_policy == "task_output_contract" and self.adapter_kind != "rlm":
            raise ValueError("task output-contract completion is supported only by the RLM adapter")
        if self.completion_policy == "task_output_commit" and self.adapter_kind != "rlm":
            raise ValueError("task output-commit completion is supported only by the RLM adapter")
        return self


class HarborBackendRuntime(FrozenStrictModel):
    runtime_kind: Literal["harbor_backend"] = "harbor_backend"
    backend: HarborBackend


class ContextProviderRuntime(FrozenStrictModel):
    runtime_kind: Literal["context_provider"] = "context_provider"
    source: Literal["workspace_system_prompt"] = "workspace_system_prompt"


class ToolProviderRuntime(FrozenStrictModel):
    runtime_kind: Literal["tool_provider"] = "tool_provider"
    source: Literal["task_definition"] = "task_definition"
    supported_tool_ids: tuple[Literal["bash"], ...] = ("bash",)


class VerifierRuntime(FrozenStrictModel):
    runtime_kind: Literal["task_verifier"] = "task_verifier"


class ResultImporterRuntime(FrozenStrictModel):
    runtime_kind: Literal["trial_record_importer"] = "trial_record_importer"


class ProgramOperationRuntime(FrozenStrictModel):
    runtime_kind: Literal["program_operation"] = "program_operation"
    operation: Literal[
        "harbor_run_batch",
        "harbor_run_stage",
        "harbor_finalize_task",
        "enumerate_task_refs",
        "proposal_run_session",
        "proposal_run_semantic_subtask",
        "proposal_check_subtask_contract",
        "proposal_finalize_plan",
    ] = "harbor_run_batch"
    retry_safe_error_codes: tuple[NonEmptyStr, ...] = ()

    @field_validator("retry_safe_error_codes")
    @classmethod
    def validate_retry_safe_error_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("program operation retry-safe error codes must be unique")
        if "*" in value:
            raise ValueError("wildcard retry-safe error codes are not permitted")
        prohibited = prohibited_retry_safe_error_codes(value)
        if prohibited:
            raise ValueError("prohibited retry-safe error codes: " + ", ".join(prohibited))
        return value


class KernelOperationArgumentPolicy(StrEnum):
    """Closed compiler-side argument policies owned by kernel definitions."""

    NO_ARGUMENTS_ACTION = "no_arguments_action"
    DECLARED_ARGUMENTS_ACTION = "declared_arguments_action"
    DECLARED_ARGUMENTS_ACTION_OR_FANOUT = "declared_arguments_action_or_fanout"


class KernelOperationArgumentSource(StrEnum):
    """Closed value sources permitted by a kernel operation argument."""

    LITERAL_STRING = "literal_string"
    OUTPUT = "output"
    PROGRAM_VALUE = "program_value"


class KernelOperationArgumentSpec(FrozenStrictModel):
    """One phase-neutral argument in a fixed-kernel operation ABI."""

    name: NonEmptyStr
    source: KernelOperationArgumentSource
    output_ports: tuple[NonEmptyStr, ...] = ()
    required: bool = True
    restrict_to_allowed_task_refs: bool = False

    @model_validator(mode="after")
    def validate_argument_source(self) -> Self:
        if len(self.output_ports) != len(set(self.output_ports)):
            raise ValueError("kernel operation argument output ports must be unique")
        if self.source is KernelOperationArgumentSource.OUTPUT and not self.output_ports:
            raise ValueError("output-derived kernel operation arguments require an output port")
        if self.source is KernelOperationArgumentSource.LITERAL_STRING and self.output_ports:
            raise ValueError("literal kernel operation arguments cannot declare output ports")
        if self.source is KernelOperationArgumentSource.PROGRAM_VALUE and self.output_ports:
            raise ValueError("generic program-value arguments cannot declare output ports")
        if self.restrict_to_allowed_task_refs and self.source is not KernelOperationArgumentSource.LITERAL_STRING:
            raise ValueError("only literal kernel operation arguments may be restricted to task refs")
        return self


class KernelOperationHandlerKey(StrEnum):
    """Closed runtime-handler lookup keys owned by kernel definitions."""

    ENUMERATE_TASK_REFS = "enumerate_task_refs"
    CHECK_SUBTASK_CONTRACT = "check_subtask_contract"
    FINALIZE_PROPOSED_PLAN = "finalize_proposed_plan"
    FINALIZE_TASK = "finalize_task"
    RUN_BATCH = "run_batch"
    RUN_PROPOSAL_SESSION = "run_proposal_session"
    RUN_SEMANTIC_SUBTASK = "run_semantic_subtask"
    RUN_STAGE = "run_stage"


class KernelOperationEffect(StrEnum):
    """Externally observable effect class for one kernel operation."""

    NO_EXTERNAL_EFFECT = "no_external_effect"
    MODEL_EXECUTION = "model_execution"
    GRAPH_ORCHESTRATION = "graph_orchestration"
    SCORED_EXECUTION = "scored_execution"
    UNSCORED_EXECUTION = "unscored_execution"


class ApplicabilityProfilerRuntime(FrozenStrictModel):
    runtime_kind: Literal["declared_task_surface_profiler"] = "declared_task_surface_profiler"


KernelRuntime = (
    TaskSourceRuntime
    | AgentAdapterRuntime
    | HarborBackendRuntime
    | ContextProviderRuntime
    | ToolProviderRuntime
    | VerifierRuntime
    | ResultImporterRuntime
    | ProgramOperationRuntime
    | ApplicabilityProfilerRuntime
)


class KernelRuntimePrimitive(FrozenStrictModel):
    """One trusted implementation mapping for a content-addressed capability spec."""

    spec: KernelCapabilitySpec
    runtime: KernelRuntime

    @model_validator(mode="after")
    def validate_runtime_kind(self) -> Self:
        expected = _CAPABILITY_KIND_BY_RUNTIME_TYPE[type(self.runtime)]
        if self.spec.kind is not expected:
            raise ValueError(
                f"runtime {self.runtime.runtime_kind!r} requires capability kind {expected.value}, "
                f"found {self.spec.kind.value}"
            )
        return self


class KernelOperationDefinition(LegacyContentAddressedModel):
    """Single registry-owned definition shared by compilation and dispatch."""

    operation_id: NonEmptyStr
    version: NonEmptyStr
    capability: KernelCapabilitySpec
    runtime: ProgramOperationRuntime
    input_schema_ref: NonEmptyStr
    output_schema_ref: NonEmptyStr
    argument_policy: KernelOperationArgumentPolicy
    arguments: tuple[KernelOperationArgumentSpec, ...] = ()
    maximum_arguments: int | None = None
    fanout_item_argument: NonEmptyStr | None = None
    argument_error_message: NonEmptyStr
    allow_monolithic_without_arguments: bool = False
    handler_key: KernelOperationHandlerKey
    effect: KernelOperationEffect
    implementation: KernelExecutorImplementationIdentity

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        _validate_operation_identity(self)
        argument_names = _validate_operation_argument_declarations(self)
        _validate_operation_argument_policy(self, argument_names)
        _validate_operation_handler(self)
        return self

    @property
    def primitive(self) -> KernelRuntimePrimitive:
        return KernelRuntimePrimitive(spec=self.capability, runtime=self.runtime)


def _validate_operation_identity(
    definition: KernelOperationDefinition,
) -> None:
    if definition.capability.kind is not KernelCapabilityKind.PROGRAM_OPERATION:
        raise ValueError("kernel operation definition requires a program-operation capability")
    if definition.capability.version != definition.version:
        raise ValueError("kernel operation definition version must match its capability version")


def _validate_operation_argument_declarations(
    definition: KernelOperationDefinition,
) -> tuple[str, ...]:
    argument_names = tuple(argument.name for argument in definition.arguments)
    if len(argument_names) != len(set(argument_names)):
        raise ValueError("kernel operation definition argument names must be unique")
    if argument_names != tuple(port.name for port in definition.capability.inputs):
        raise ValueError("kernel operation definition arguments must exactly match capability inputs")
    for argument, port in zip(
        definition.arguments,
        definition.capability.inputs,
        strict=True,
    ):
        expected_required = port.cardinality is not KernelPortCardinality.OPTIONAL
        if argument.required is not expected_required:
            raise ValueError("kernel operation argument requiredness must match capability cardinality")
    if definition.maximum_arguments is not None and (
        definition.maximum_arguments < sum(argument.required for argument in definition.arguments)
        or definition.maximum_arguments > len(definition.arguments)
    ):
        raise ValueError("kernel operation maximum arguments is inconsistent with its declared arguments")
    return argument_names


def _validate_operation_argument_policy(
    definition: KernelOperationDefinition,
    argument_names: tuple[str, ...],
) -> None:
    if definition.argument_policy is KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION:
        if definition.arguments:
            raise ValueError("no-argument kernel operation cannot declare arguments")
        if definition.allow_monolithic_without_arguments:
            raise ValueError("no-argument kernel operation cannot declare a monolithic exception")
        if definition.maximum_arguments is not None or definition.fanout_item_argument is not None:
            raise ValueError("no-argument kernel operation cannot declare argument limits or fanout")
    elif not definition.arguments:
        raise ValueError("declared-argument kernel operation requires arguments")
    if definition.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION:
        if definition.fanout_item_argument is not None:
            raise ValueError("action-only kernel operation cannot declare a fanout item argument")
    elif (
        definition.argument_policy is KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION_OR_FANOUT
        and definition.fanout_item_argument not in argument_names
    ):
        raise ValueError("fanout kernel operation requires one declared item argument")
    if (
        definition.allow_monolithic_without_arguments
        and definition.argument_policy is not KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION
    ):
        raise ValueError("monolithic exception is supported only by declared action arguments")


def _validate_operation_handler(
    definition: KernelOperationDefinition,
) -> None:
    expected_runtime_operation = {
        KernelOperationHandlerKey.ENUMERATE_TASK_REFS: "enumerate_task_refs",
        KernelOperationHandlerKey.CHECK_SUBTASK_CONTRACT: ("proposal_check_subtask_contract"),
        KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN: ("proposal_finalize_plan"),
        KernelOperationHandlerKey.FINALIZE_TASK: "harbor_finalize_task",
        KernelOperationHandlerKey.RUN_BATCH: "harbor_run_batch",
        KernelOperationHandlerKey.RUN_PROPOSAL_SESSION: "proposal_run_session",
        KernelOperationHandlerKey.RUN_SEMANTIC_SUBTASK: ("proposal_run_semantic_subtask"),
        KernelOperationHandlerKey.RUN_STAGE: "harbor_run_stage",
    }[definition.handler_key]
    if definition.runtime.operation != expected_runtime_operation:
        raise ValueError("kernel operation definition handler key must match its runtime operation")


_CAPABILITY_KIND_BY_RUNTIME_TYPE: dict[type[FrozenStrictModel], KernelCapabilityKind] = {
    TaskSourceRuntime: KernelCapabilityKind.TASK_SOURCE,
    AgentAdapterRuntime: KernelCapabilityKind.AGENT_ADAPTER,
    HarborBackendRuntime: KernelCapabilityKind.EXECUTION_BACKEND,
    ContextProviderRuntime: KernelCapabilityKind.CONTEXT_PROVIDER,
    ToolProviderRuntime: KernelCapabilityKind.TOOL_PROVIDER,
    VerifierRuntime: KernelCapabilityKind.VERIFIER,
    ResultImporterRuntime: KernelCapabilityKind.RESULT_IMPORTER,
    ProgramOperationRuntime: KernelCapabilityKind.PROGRAM_OPERATION,
    ApplicabilityProfilerRuntime: KernelCapabilityKind.PROFILER,
}


@dataclass(frozen=True)
class KernelRuntimeRegistry:
    """Exact fixed-K manifest plus its trusted host-side runtime implementations."""

    manifest: KernelManifest
    primitives: tuple[KernelRuntimePrimitive, ...]
    package_fingerprint: KernelImplementationIdentity | None = None
    operation_definitions: tuple[KernelOperationDefinition, ...] = ()

    def __post_init__(self) -> None:
        primitive_ids = [primitive.spec.capability_id for primitive in self.primitives]
        if len(primitive_ids) != len(set(primitive_ids)):
            raise KernelRuntimeRegistryError("runtime primitive capability ids must be unique")
        primitive_specs = tuple(primitive.spec for primitive in self.primitives)
        if self.manifest.capabilities != primitive_specs:
            raise KernelRuntimeRegistryError("manifest capabilities must exactly match runtime primitives")
        definition_ids = tuple(definition.operation_id for definition in self.operation_definitions)
        if len(definition_ids) != len(set(definition_ids)):
            raise KernelRuntimeRegistryError("kernel operation definition ids must be unique")
        implementation_sources = {source.path: source.sha256 for source in self.manifest.implementation.sources}
        for definition in self.operation_definitions:
            if definition.primitive not in self.primitives:
                raise KernelRuntimeRegistryError(
                    "kernel operation definition must exactly match one runtime primitive: " + definition.operation_id
                )
            for source in definition.implementation.sources:
                if implementation_sources.get(source.path) != source.sha256:
                    raise KernelRuntimeRegistryError(
                        "kernel operation implementation is outside the manifest executor surface: "
                        + definition.operation_id
                    )
        if self.operation_definitions:
            program_primitives = tuple(
                primitive for primitive in self.primitives if isinstance(primitive.runtime, ProgramOperationRuntime)
            )
            defined_primitives = tuple(definition.primitive for definition in self.operation_definitions)
            if len(defined_primitives) != len(program_primitives) or set(defined_primitives) != set(program_primitives):
                raise KernelRuntimeRegistryError(
                    "kernel operation definitions must cover every program-operation primitive exactly once"
                )

    @property
    def is_legacy_definition_free(self) -> bool:
        """Whether this explicitly constructed registry uses historical dispatch."""
        return not self.operation_definitions

    def capability(self, capability_id: str) -> KernelCapabilitySpec:
        """Return a trusted capability spec by stable id."""
        for primitive in self.primitives:
            if primitive.spec.capability_id == capability_id:
                return primitive.spec
        raise KernelRuntimeRegistryError(f"unknown kernel capability: {capability_id}")

    def resolve(self, reference: KernelCapabilityRef) -> KernelRuntimePrimitive:
        """Resolve only an exact capability id and version from the fixed manifest."""
        for primitive in self.primitives:
            if primitive.spec.capability_id == reference.capability_id:
                if primitive.spec.ref != reference:
                    raise KernelRuntimeRegistryError(
                        f"capability version does not match fixed K: {reference.capability_id}"
                    )
                return primitive
        raise KernelRuntimeRegistryError(f"unknown kernel capability: {reference.capability_id}")

    def operation_definition(self, operation_id: str) -> KernelOperationDefinition | None:
        """Return the definition, or None only on a legacy definition-free registry."""
        return next(
            (definition for definition in self.operation_definitions if definition.operation_id == operation_id),
            None,
        )


@lru_cache(maxsize=1)
def default_kernel_registry() -> KernelRuntimeRegistry:
    """Return the versioned fixed kernel implemented by the current aec-bench runtime."""
    executor_sources = _kernel_source_inventory()
    operation_definitions = _default_operation_definitions(executor_sources)
    if {definition.operation_id for definition in operation_definitions} != DEFAULT_KERNEL_OPERATION_IDS:
        raise KernelRuntimeRegistryError("default kernel registry operation definitions are incomplete")
    primitives = tuple(
        sorted(
            _default_primitives(operation_definitions=operation_definitions),
            key=lambda primitive: primitive.spec.capability_id,
        )
    )
    manifest = KernelManifest(
        kernel_id=DEFAULT_KERNEL_ID,
        version=DEFAULT_KERNEL_VERSION,
        capabilities=tuple(primitive.spec for primitive in primitives),
        implementation=KernelExecutorImplementationIdentity(
            sources=executor_sources,
        ),
    )
    registry = KernelRuntimeRegistry(
        manifest=manifest,
        primitives=primitives,
        package_fingerprint=KernelImplementationIdentity(
            sources=_package_source_inventory(),
        ),
        operation_definitions=operation_definitions,
    )
    if registry.is_legacy_definition_free:
        raise KernelRuntimeRegistryError("default kernel registry requires complete program-operation definitions")
    return registry


def verify_kernel_implementation_identity(registry: KernelRuntimeRegistry) -> None:
    """Reject dispatch when the installed default-kernel source bytes drift from its manifest."""
    if registry.manifest.kernel_id != DEFAULT_KERNEL_ID:
        return
    if registry.manifest.version != DEFAULT_KERNEL_VERSION:
        raise KernelRuntimeRegistryError(
            "default kernel version does not match the installed fixed K: " + registry.manifest.version
        )
    if isinstance(registry.manifest.implementation, KernelExecutorImplementationIdentity):
        installed_sources = _kernel_source_inventory()
    else:
        installed_sources = _package_source_inventory()
    if registry.manifest.implementation.sources != installed_sources:
        raise KernelRuntimeRegistryError(
            "default kernel implementation source inventory drifted after the registry was created"
        )


def _kernel_source_inventory() -> tuple[KernelSourceDigest, ...]:
    """Hash only the explicit executable source surface owned by fixed K."""
    package_root = Path(__file__).resolve().parents[1]
    project_root = package_root.parents[1]
    sources: list[KernelSourceDigest] = []
    missing: list[str] = []
    for inventory_path in DEFAULT_KERNEL_EXECUTOR_SOURCE_PATHS:
        if inventory_path.startswith("aec_bench/"):
            path = package_root.parent / inventory_path
        else:
            path = project_root / inventory_path
        if not path.is_file():
            missing.append(inventory_path)
            continue
        sources.append(
            KernelSourceDigest(
                path=inventory_path,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    if missing:
        raise KernelRuntimeRegistryError(
            "default kernel executor source allowlist contains missing files: " + ", ".join(missing)
        )
    return tuple(sources)


def _package_source_inventory() -> tuple[KernelSourceDigest, ...]:
    """Hash the complete package separately for build and replay diagnostics."""
    package_root = Path(__file__).resolve().parents[1]
    source_paths = list(package_root.rglob("*.py"))
    project_root = package_root.parents[1]
    agents_root = project_root / "agents"
    if agents_root.is_dir():
        source_paths.extend(agents_root.rglob("*.py"))

    sources: list[KernelSourceDigest] = []
    for path in source_paths:
        if path.is_relative_to(agents_root):
            inventory_path = f"agents/{path.relative_to(agents_root).as_posix()}"
        else:
            inventory_path = f"aec_bench/{path.relative_to(package_root).as_posix()}"
        sources.append(
            KernelSourceDigest(
                path=inventory_path,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return tuple(sorted(sources, key=lambda source: source.path))


def _default_operation_definitions(
    executor_sources: tuple[KernelSourceDigest, ...],
) -> tuple[KernelOperationDefinition, ...]:
    enumeration_runtime = ProgramOperationRuntime(operation="enumerate_task_refs")
    enumeration_primitive = _primitive(
        capability_id="aecbench.operation.tasks.enumerate",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary="Return the exact task references exported by the compiled harness instance.",
        runtime=enumeration_runtime,
        outputs=(
            KernelPortSpec(
                name="tasks",
                schema_ref="aecbench://task-ref-set/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
    )
    subtask_check_runtime = ProgramOperationRuntime(
        operation="proposal_check_subtask_contract",
    )
    subtask_check_primitive = _primitive(
        capability_id="aecbench.operation.proposal.check-subtask-contract",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=(
            "Check one semantic-subtask result against its compiler-bound evidence "
            "contract without evaluating task quality."
        ),
        runtime=subtask_check_runtime,
        inputs=(
            KernelPortSpec(
                name="subject",
                schema_ref="aecbench://semantic-subtask-result/v1",
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="result",
                schema_ref="aecbench://subtask-contract-check-ref/v1",
            ),
        ),
    )
    proposal_finalizer_runtime = ProgramOperationRuntime(
        operation="proposal_finalize_plan",
    )
    proposal_finalizer_primitive = _primitive(
        capability_id="aecbench.operation.proposal.finalize-proposed-plan",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=("Finalize one proposal-owned evidence plan and emit the sole scored TrialRecord set."),
        runtime=proposal_finalizer_runtime,
        inputs=(
            KernelPortSpec(
                name="findings",
                schema_ref="aecbench://subtask-contract-check-ref-or-set/v1",
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="result",
                schema_ref="aecbench://harbor-run-result/v1",
            ),
            KernelPortSpec(
                name="trials",
                schema_ref="aecbench://trial-record-set/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
    )
    task_finalizer_runtime = ProgramOperationRuntime(
        operation="harbor_finalize_task",
    )
    task_finalizer_primitive = _primitive(
        capability_id="aecbench.operation.harbor.finalize-task",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=(
            "Finalize one task from its complete declared-stage receipt set, run the "
            "task verifier, and import the single scored TrialRecord."
        ),
        runtime=task_finalizer_runtime,
        inputs=(
            KernelPortSpec(
                name="task_ref",
                schema_ref="aecbench://task-ref/v1",
            ),
            KernelPortSpec(
                name="stage_receipts",
                schema_ref="aecbench://stage-execution-receipt-set/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="result",
                schema_ref="aecbench://harbor-run-result/v1",
            ),
            KernelPortSpec(
                name="trials",
                schema_ref="aecbench://trial-record-set/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
    )
    batch_runtime = ProgramOperationRuntime(operation="harbor_run_batch")
    batch_primitive = _primitive(
        capability_id="aecbench.operation.harbor.run-batch",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary="Lower one exact task batch to the synchronous Harbor workflow.",
        runtime=batch_runtime,
        inputs=(
            KernelPortSpec(
                name="task_ref",
                schema_ref="aecbench://task-ref/v1",
                cardinality=KernelPortCardinality.OPTIONAL,
            ),
            KernelPortSpec(
                name="task_refs",
                schema_ref="aecbench://task-ref-set/v1",
                cardinality=KernelPortCardinality.OPTIONAL,
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="trials",
                schema_ref="aecbench://trial-record-set/v1",
                cardinality=KernelPortCardinality.MANY,
            ),
        ),
    )
    stage_runtime = ProgramOperationRuntime(operation="harbor_run_stage")
    stage_primitive = _primitive(
        capability_id="aecbench.operation.harbor.run-stage",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=(
            "Execute one declared task-world stage and persist a content-addressed "
            "intermediate receipt without importing a TrialRecord."
        ),
        runtime=stage_runtime,
        inputs=(
            KernelPortSpec(
                name="task_ref",
                schema_ref="aecbench://task-ref/v1",
            ),
            KernelPortSpec(
                name="stage_id",
                schema_ref="aecbench://declared-stage-id/v1",
            ),
            KernelPortSpec(
                name="upstream_receipts",
                schema_ref="aecbench://stage-execution-receipt-ref-or-set/v1",
                cardinality=KernelPortCardinality.OPTIONAL,
            ),
        ),
        outputs=(
            KernelPortSpec(
                name="stage_receipt",
                schema_ref="aecbench://stage-execution-receipt-ref/v1",
            ),
        ),
    )
    proposal_session_runtime = ProgramOperationRuntime(
        operation="proposal_run_session",
    )
    proposal_session_primitive = _primitive(
        capability_id="aecbench.operation.proposal.run-session",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=(
            "Execute one fixed proposal schedule inside a task-resident Harbor "
            "sandbox and emit its exact session receipt."
        ),
        runtime=proposal_session_runtime,
        outputs=(
            KernelPortSpec(
                name="session_receipt",
                schema_ref="aecbench://proposal-session-receipt/v1",
            ),
        ),
    )
    semantic_subtask_runtime = ProgramOperationRuntime(
        operation="proposal_run_semantic_subtask",
    )
    semantic_subtask_primitive = _primitive(
        capability_id="aecbench.operation.proposal.run-semantic-subtask",
        kind=KernelCapabilityKind.PROGRAM_OPERATION,
        summary=(
            "Execute one compiler-bound semantic subtask using only its host-scoped "
            "public context and upstream receipts."
        ),
        runtime=semantic_subtask_runtime,
        outputs=(
            KernelPortSpec(
                name="result",
                schema_ref="aecbench://semantic-subtask-result/v1",
            ),
        ),
    )
    return (
        KernelOperationDefinition(
            operation_id="enumerate_tasks",
            version=enumeration_primitive.spec.version,
            capability=enumeration_primitive.spec,
            runtime=enumeration_runtime,
            input_schema_ref="aecbench://empty/v1",
            output_schema_ref="aecbench://task-ref-set/v1",
            argument_policy=KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION,
            argument_error_message=("enumerate_tasks accepts no arguments and cannot be a fanout target"),
            handler_key=KernelOperationHandlerKey.ENUMERATE_TASK_REFS,
            effect=KernelOperationEffect.NO_EXTERNAL_EFFECT,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_EXECUTION_SOURCE_PATHS,
                    "aec_bench/experimentation/qualification/run_bundle_runtime.py",
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="run_batch",
            version=batch_primitive.spec.version,
            capability=batch_primitive.spec,
            runtime=batch_runtime,
            input_schema_ref="aecbench://run-batch-selection/v1",
            output_schema_ref="aecbench://trial-record-set/v1",
            argument_policy=(KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION_OR_FANOUT),
            arguments=(
                KernelOperationArgumentSpec(
                    name="task_ref",
                    source=KernelOperationArgumentSource.PROGRAM_VALUE,
                    required=False,
                ),
                KernelOperationArgumentSpec(
                    name="task_refs",
                    source=KernelOperationArgumentSource.PROGRAM_VALUE,
                    required=False,
                ),
            ),
            maximum_arguments=1,
            fanout_item_argument="task_ref",
            argument_error_message=(
                "run_batch accepts one optional task_ref/task_refs selection; fanout must bind exactly task_ref"
            ),
            handler_key=KernelOperationHandlerKey.RUN_BATCH,
            effect=KernelOperationEffect.SCORED_EXECUTION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/harbor_lowering.py",
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_EXECUTION_SOURCE_PATHS,
                    "aec_bench/experimentation/qualification/run_bundle_runtime.py",
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="run_stage",
            version=stage_primitive.spec.version,
            capability=stage_primitive.spec,
            runtime=stage_runtime,
            input_schema_ref="aecbench://run-stage-selection/v1",
            output_schema_ref="aecbench://stage-execution-receipt-ref/v1",
            argument_policy=KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION,
            arguments=(
                KernelOperationArgumentSpec(
                    name="task_ref",
                    source=KernelOperationArgumentSource.LITERAL_STRING,
                    restrict_to_allowed_task_refs=True,
                ),
                KernelOperationArgumentSpec(
                    name="stage_id",
                    source=KernelOperationArgumentSource.LITERAL_STRING,
                ),
                KernelOperationArgumentSpec(
                    name="upstream_receipts",
                    source=KernelOperationArgumentSource.OUTPUT,
                    output_ports=("stage_receipt", "result"),
                    required=False,
                ),
            ),
            argument_error_message=(
                "run_stage requires literal task_ref/stage_id arguments and accepts only "
                "an output-derived upstream_receipts argument"
            ),
            handler_key=KernelOperationHandlerKey.RUN_STAGE,
            effect=KernelOperationEffect.UNSCORED_EXECUTION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    "aec_bench/ledger/immutable_artifact_store.py",
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/declared_stage.py",
                    "aec_bench/harness/governed_attempt/__init__.py",
                    "aec_bench/harness/governed_attempt/chain_validation.py",
                    "aec_bench/harness/governed_attempt/contracts.py",
                    "aec_bench/harness/governed_attempt/lifecycle.py",
                    "aec_bench/harness/governed_attempt/ports.py",
                    "aec_bench/harness/governed_attempt/repository.py",
                    "aec_bench/harness/harbor_lowering.py",
                    "aec_bench/ledger/immutable_byte_store.py",
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_EXECUTION_SOURCE_PATHS,
                    "aec_bench/experimentation/qualification/run_bundle_runtime.py",
                    "aec_bench/experimentation/qualification/run_bundle_stage_attempt.py",
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="run_proposal_session",
            version=proposal_session_primitive.spec.version,
            capability=proposal_session_primitive.spec,
            runtime=proposal_session_runtime,
            input_schema_ref="aecbench://proposal-session-internal/v1",
            output_schema_ref="aecbench://proposal-session-receipt/v1",
            argument_policy=KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION,
            argument_error_message=(
                "run_proposal_session is an argument-free action whose exact context is supplied by the compiler"
            ),
            handler_key=KernelOperationHandlerKey.RUN_PROPOSAL_SESSION,
            effect=KernelOperationEffect.GRAPH_ORCHESTRATION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    "aec_bench/experimentation/proposals/session_config.py",
                    "aec_bench/experimentation/proposals/scheduler.py",
                    *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
                    "agents/entrypoint_agent.py",
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="run_semantic_subtask",
            version=semantic_subtask_primitive.spec.version,
            capability=semantic_subtask_primitive.spec,
            runtime=semantic_subtask_runtime,
            input_schema_ref="aecbench://semantic-subtask-internal/v1",
            output_schema_ref="aecbench://semantic-subtask-result/v1",
            argument_policy=KernelOperationArgumentPolicy.NO_ARGUMENTS_ACTION,
            argument_error_message=(
                "run_semantic_subtask is an argument-free action whose exact context is supplied by the compiler"
            ),
            handler_key=KernelOperationHandlerKey.RUN_SEMANTIC_SUBTASK,
            effect=KernelOperationEffect.MODEL_EXECUTION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    "aec_bench/experimentation/proposals/node_context.py",
                    *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="check_subtask_contract",
            version=subtask_check_primitive.spec.version,
            capability=subtask_check_primitive.spec,
            runtime=subtask_check_runtime,
            input_schema_ref="aecbench://subtask-contract-check-selection/v1",
            output_schema_ref="aecbench://subtask-contract-check-ref/v1",
            argument_policy=KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION,
            arguments=(
                KernelOperationArgumentSpec(
                    name="subject",
                    source=KernelOperationArgumentSource.OUTPUT,
                    output_ports=("result",),
                ),
            ),
            argument_error_message=("check_subtask_contract requires exactly one output-derived subject argument"),
            handler_key=KernelOperationHandlerKey.CHECK_SUBTASK_CONTRACT,
            effect=KernelOperationEffect.NO_EXTERNAL_EFFECT,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    "aec_bench/experimentation/proposals/node_contract.py",
                    *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="finalize_proposed_plan",
            version=proposal_finalizer_primitive.spec.version,
            capability=proposal_finalizer_primitive.spec,
            runtime=proposal_finalizer_runtime,
            input_schema_ref="aecbench://finalize-proposed-plan-selection/v1",
            output_schema_ref="aecbench://trial-record-set/v1",
            argument_policy=KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION,
            arguments=(
                KernelOperationArgumentSpec(
                    name="findings",
                    source=KernelOperationArgumentSource.OUTPUT,
                    output_ports=("result",),
                ),
            ),
            argument_error_message=("finalize_proposed_plan requires exactly one output-derived findings argument"),
            allow_monolithic_without_arguments=True,
            handler_key=KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN,
            effect=KernelOperationEffect.MODEL_EXECUTION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    "aec_bench/experimentation/proposals/node_contract.py",
                    *_PROPOSAL_SESSION_RUNTIME_SOURCE_PATHS,
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_PROPOSAL_COMPILATION_SOURCE_PATHS,
                ),
            ),
        ),
        KernelOperationDefinition(
            operation_id="finalize_task",
            version=task_finalizer_primitive.spec.version,
            capability=task_finalizer_primitive.spec,
            runtime=task_finalizer_runtime,
            input_schema_ref="aecbench://finalize-task-selection/v1",
            output_schema_ref="aecbench://trial-record-set/v1",
            argument_policy=KernelOperationArgumentPolicy.DECLARED_ARGUMENTS_ACTION,
            arguments=(
                KernelOperationArgumentSpec(
                    name="task_ref",
                    source=KernelOperationArgumentSource.LITERAL_STRING,
                    restrict_to_allowed_task_refs=True,
                ),
                KernelOperationArgumentSpec(
                    name="stage_receipts",
                    source=KernelOperationArgumentSource.OUTPUT,
                    output_ports=("stage_receipt", "result"),
                ),
            ),
            argument_error_message=(
                "finalize_task requires a literal task_ref and output-derived stage_receipts argument"
            ),
            handler_key=KernelOperationHandlerKey.FINALIZE_TASK,
            effect=KernelOperationEffect.SCORED_EXECUTION,
            implementation=_operation_implementation_identity(
                executor_sources,
                paths=(
                    *_COMPILATION_SOURCE_PATHS,
                    "aec_bench/harness/declared_stage.py",
                    "aec_bench/harness/kernel_catalogue.py",
                    *_PROGRAM_EXECUTION_SOURCE_PATHS,
                    "aec_bench/experimentation/qualification/run_bundle_runtime.py",
                ),
            ),
        ),
    )


def _operation_implementation_identity(
    executor_sources: tuple[KernelSourceDigest, ...],
    *,
    paths: tuple[str, ...],
) -> KernelExecutorImplementationIdentity:
    source_by_path = {source.path: source for source in executor_sources}
    missing = tuple(path for path in paths if path not in source_by_path)
    if missing:
        raise KernelRuntimeRegistryError(
            "kernel operation implementation paths are outside the executor allowlist: " + ", ".join(missing)
        )
    return KernelExecutorImplementationIdentity(
        sources=tuple(source_by_path[path] for path in sorted(paths)),
    )


def _default_primitives(
    *,
    operation_definitions: tuple[KernelOperationDefinition, ...] = (),
) -> tuple[KernelRuntimePrimitive, ...]:
    adapters: tuple[tuple[str, AdapterKind], ...] = (
        ("direct", "direct"),
        ("tool-loop", "tool_loop"),
        ("rlm", "rlm"),
        ("lambda-rlm", "lambda-rlm"),
    )
    backends: tuple[HarborBackend, ...] = ("docker", "modal", "e2b", "daytona", "morph")
    return (
        _primitive(
            capability_id="aecbench.tasks.registry",
            kind=KernelCapabilityKind.TASK_SOURCE,
            summary="Resolve exact runnable task references from the aec-bench task registry.",
            runtime=TaskSourceRuntime(),
        ),
        *(
            _primitive(
                capability_id=f"aecbench.adapter.{capability_suffix}",
                kind=KernelCapabilityKind.AGENT_ADAPTER,
                summary=f"Execute the trusted {adapter_kind} adapter driver.",
                runtime=AgentAdapterRuntime(adapter_kind=adapter_kind),
            )
            for capability_suffix, adapter_kind in adapters
        ),
        _primitive(
            capability_id="aecbench.adapter.rlm-uncached",
            kind=KernelCapabilityKind.AGENT_ADAPTER,
            summary="Execute the trusted RLM adapter with explicit finalization and prompt caching disabled.",
            runtime=AgentAdapterRuntime(
                adapter_kind="rlm",
                prompt_cache=False,
            ),
        ),
        _primitive(
            capability_id="aecbench.adapter.rlm-output-contract",
            kind=KernelCapabilityKind.AGENT_ADAPTER,
            summary="Execute the trusted RLM adapter with task-declared structural output completion.",
            runtime=AgentAdapterRuntime(
                adapter_kind="rlm",
                completion_policy="task_output_contract",
                prompt_cache=False,
            ),
        ),
        _primitive(
            capability_id="aecbench.adapter.rlm-output-commit",
            kind=KernelCapabilityKind.AGENT_ADAPTER,
            summary=(
                "Execute the trusted RLM adapter with task-declared output validation "
                "and explicit artifact commit attestation."
            ),
            runtime=AgentAdapterRuntime(
                adapter_kind="rlm",
                completion_policy="task_output_commit",
                prompt_cache=False,
            ),
        ),
        *(
            _primitive(
                capability_id=f"aecbench.backend.harbor.{backend}",
                kind=KernelCapabilityKind.EXECUTION_BACKEND,
                summary=f"Execute isolated trials through Harbor's {backend} environment.",
                runtime=HarborBackendRuntime(backend=backend),
            )
            for backend in backends
        ),
        _primitive(
            capability_id="aecbench.context.workspace-system-prompt",
            kind=KernelCapabilityKind.CONTEXT_PROVIDER,
            summary="Load the task-owned workspace system prompt at adapter runtime.",
            runtime=ContextProviderRuntime(),
        ),
        _primitive(
            capability_id="aecbench.tools.task-declared",
            kind=KernelCapabilityKind.TOOL_PROVIDER,
            summary="Expose only a task-declared bash tool through the kernel-owned native runtime.",
            runtime=ToolProviderRuntime(),
        ),
        _primitive(
            capability_id="aecbench.verifier.task",
            kind=KernelCapabilityKind.VERIFIER,
            summary="Run the selected task package's Harbor verifier.",
            runtime=VerifierRuntime(),
        ),
        _primitive(
            capability_id="aecbench.results.trial-record",
            kind=KernelCapabilityKind.RESULT_IMPORTER,
            summary="Import verified Harbor results into the append-only TrialRecord ledger.",
            runtime=ResultImporterRuntime(),
        ),
        _primitive(
            capability_id="aecbench.profiler.declared-task-surface",
            kind=KernelCapabilityKind.PROFILER,
            summary="Classify only reward-blind topology, tools, and evidence declared before execution.",
            runtime=ApplicabilityProfilerRuntime(),
        ),
        *(definition.primitive for definition in operation_definitions),
    )


def _primitive(
    *,
    capability_id: str,
    kind: KernelCapabilityKind,
    summary: str,
    runtime: KernelRuntime,
    inputs: tuple[KernelPortSpec, ...] = (),
    outputs: tuple[KernelPortSpec, ...] = (KernelPortSpec(name="result", schema_ref="aecbench://result/v1"),),
) -> KernelRuntimePrimitive:
    spec = KernelCapabilitySpec(
        capability_id=capability_id,
        version="1.0.0",
        kind=kind,
        summary=summary,
        inputs=inputs,
        outputs=outputs,
        configuration_schema_ref=f"aecbench://kernel/{kind.value}/v1",
    )
    return KernelRuntimePrimitive(spec=spec, runtime=runtime)
