# ABOUTME: Exercises exact typed dispatch for independently registered repair rules.
# ABOUTME: Proves duplicate registrations and unregistered patch types fail closed.

from __future__ import annotations

from dataclasses import dataclass

import pytest

from aec_bench.meta_harness.adaptive_diagnosis import (
    _ADAPTIVE_DIAGNOSIS_RULE_REGISTRY,
    _ADAPTIVE_FEASIBILITY_RULE_REGISTRY,
    HarnessMaxTurnsDiagnosisRule,
    diagnosis_function_for_rule,
)
from aec_bench.meta_harness.repair_rule_registry import (
    RepairDiagnosisRuleRegistration,
    RepairDiagnosisRuleRegistry,
    RepairFeasibilityRuleRegistration,
    RepairFeasibilityRuleRegistry,
    RepairRuleRegistration,
    RepairRuleRegistry,
)
from aec_bench.meta_harness.repair_runtime import _REPAIR_RULE_REGISTRY


@dataclass(frozen=True)
class _Context:
    prefix: str


@dataclass(frozen=True)
class _FirstPatch:
    value: str


@dataclass(frozen=True)
class _SecondPatch:
    value: str


class _DerivedFirstPatch(_FirstPatch):
    pass


@dataclass(frozen=True)
class _FirstDiagnosisRule:
    value: str


@dataclass(frozen=True)
class _SecondDiagnosisRule:
    value: str


class _DerivedFirstDiagnosisRule(_FirstDiagnosisRule):
    pass


class _DerivedHarnessMaxTurnsDiagnosisRule(HarnessMaxTurnsDiagnosisRule):
    pass


def test_registry_dispatches_by_exact_patch_type_independent_of_registration_order() -> None:
    first = RepairRuleRegistration[_Context, str](
        rule_id="first",
        patch_type=_FirstPatch,
        apply=lambda context, patch: f"{context.prefix}:first:{patch.value}",
    )
    second = RepairRuleRegistration[_Context, str](
        rule_id="second",
        patch_type=_SecondPatch,
        apply=lambda context, patch: f"{context.prefix}:second:{patch.value}",
    )

    registry = RepairRuleRegistry((second, first))

    assert registry.apply(_Context(prefix="repair"), _FirstPatch(value="one")) == "repair:first:one"
    assert registry.apply(_Context(prefix="repair"), _SecondPatch(value="two")) == "repair:second:two"
    assert registry.rule_ids == ("first", "second")


def test_registry_rejects_duplicate_or_unregistered_patch_types() -> None:
    first = RepairRuleRegistration[_Context, str](
        rule_id="first",
        patch_type=_FirstPatch,
        apply=lambda context, patch: f"{context.prefix}:{patch.value}",
    )
    duplicate = RepairRuleRegistration[_Context, str](
        rule_id="duplicate",
        patch_type=_FirstPatch,
        apply=lambda context, patch: f"{patch.value}:{context.prefix}",
    )

    with pytest.raises(ValueError, match="patch type"):
        RepairRuleRegistry((first, duplicate))

    registry = RepairRuleRegistry((first,))
    with pytest.raises(ValueError, match="unregistered repair patch"):
        registry.apply(_Context(prefix="repair"), _SecondPatch(value="two"))
    with pytest.raises(ValueError, match="unregistered repair patch"):
        registry.apply(_Context(prefix="repair"), _DerivedFirstPatch(value="derived"))


def test_diagnosis_registry_binds_by_exact_rule_type_and_fails_closed() -> None:
    first = RepairDiagnosisRuleRegistration[str](
        rule_id="first",
        rule_type=_FirstDiagnosisRule,
        bind=lambda rule: f"first:{rule.value}",
    )
    second = RepairDiagnosisRuleRegistration[str](
        rule_id="second",
        rule_type=_SecondDiagnosisRule,
        bind=lambda rule: f"second:{rule.value}",
    )
    registry = RepairDiagnosisRuleRegistry((second, first))

    assert registry.bind(_FirstDiagnosisRule(value="one")) == "first:one"
    assert registry.bind(_SecondDiagnosisRule(value="two")) == "second:two"
    assert registry.rule_ids == ("first", "second")

    with pytest.raises(ValueError, match="unregistered repair diagnosis rule"):
        registry.bind(_DerivedFirstDiagnosisRule(value="derived"))
    with pytest.raises(ValueError, match="diagnosis rule type"):
        RepairDiagnosisRuleRegistry(
            (
                first,
                RepairDiagnosisRuleRegistration[str](
                    rule_id="duplicate",
                    rule_type=_FirstDiagnosisRule,
                    bind=lambda rule: rule.value,
                ),
            )
        )


def test_feasibility_registry_validates_by_exact_rule_type_and_fails_closed() -> None:
    observed: list[str] = []
    first = RepairFeasibilityRuleRegistration[_Context](
        rule_id="first",
        rule_type=_FirstDiagnosisRule,
        validate=lambda context, rule: observed.append(
            f"{context.prefix}:first:{rule.value}",
        ),
    )
    second = RepairFeasibilityRuleRegistration[_Context](
        rule_id="second",
        rule_type=_SecondDiagnosisRule,
        validate=lambda context, rule: observed.append(
            f"{context.prefix}:second:{rule.value}",
        ),
    )
    registry = RepairFeasibilityRuleRegistry((second, first))

    registry.validate(_Context(prefix="repair"), _FirstDiagnosisRule(value="one"))
    registry.validate(_Context(prefix="repair"), _SecondDiagnosisRule(value="two"))

    assert observed == ["repair:first:one", "repair:second:two"]
    assert registry.rule_ids == ("first", "second")
    with pytest.raises(ValueError, match="unregistered repair feasibility rule"):
        registry.validate(
            _Context(prefix="repair"),
            _DerivedFirstDiagnosisRule(value="derived"),
        )
    with pytest.raises(ValueError, match="feasibility rule type"):
        RepairFeasibilityRuleRegistry(
            (
                first,
                RepairFeasibilityRuleRegistration[_Context](
                    rule_id="duplicate",
                    rule_type=_FirstDiagnosisRule,
                    validate=lambda context, rule: None,
                ),
            ),
        )


def test_runtime_registers_every_closed_v1_patch_rule() -> None:
    assert _REPAIR_RULE_REGISTRY.rule_ids == (
        "harness_agent_capability",
        "harness_agent_max_turns",
        "program_coalesce_task_batch",
        "program_materialize_declared_stage_graph",
        "program_max_total_attempts",
        "program_node_retry",
    )


def test_adaptive_diagnosis_registers_every_closed_v1_rule_and_rejects_subclasses() -> None:
    assert _ADAPTIVE_DIAGNOSIS_RULE_REGISTRY.rule_ids == (
        "harness_agent_capability",
        "harness_max_turns",
        "program_coalesce_task_batch",
        "program_materialize_declared_stage_graph",
        "program_max_total_attempts",
        "program_retry",
    )

    with pytest.raises(ValueError, match="unregistered repair diagnosis rule"):
        diagnosis_function_for_rule(
            _DerivedHarnessMaxTurnsDiagnosisRule(binding_id="agent", max_turns=2),
        )

    assert _ADAPTIVE_FEASIBILITY_RULE_REGISTRY.rule_ids == (
        "harness_agent_capability",
        "harness_max_turns",
        "program_coalesce_task_batch",
        "program_materialize_declared_stage_graph",
        "program_max_total_attempts",
        "program_retry",
    )
