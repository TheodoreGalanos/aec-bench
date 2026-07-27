# ABOUTME: Dispatches typed repair patches through independently registered application rules.
# ABOUTME: Keeps the paired repair loop generic while unregistered or ambiguous patch types fail closed.

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RepairRuleRegistration[ContextT, ResultT]:
    """One exact patch type and its phase-neutral application function."""

    rule_id: str
    patch_type: type[Any]
    apply: Callable[[ContextT, Any], ResultT]

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("repair rule id must not be empty")


class RepairRuleRegistry[ContextT, ResultT]:
    """Closed exact-type dispatcher for one configured repair rule set."""

    def __init__(
        self,
        registrations: Iterable[RepairRuleRegistration[ContextT, ResultT]],
    ) -> None:
        ordered = tuple(sorted(registrations, key=lambda registration: registration.rule_id))
        rule_ids = tuple(registration.rule_id for registration in ordered)
        patch_types = tuple(registration.patch_type for registration in ordered)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("repair rule registry contains duplicate rule ids")
        if len(patch_types) != len(set(patch_types)):
            raise ValueError("repair rule registry contains duplicate patch types")
        self._registrations = ordered
        self._by_patch_type = {registration.patch_type: registration for registration in ordered}

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return configured rule ids in deterministic order."""

        return tuple(registration.rule_id for registration in self._registrations)

    def apply(self, context: ContextT, patch: object) -> ResultT:
        """Apply the sole rule registered for the patch's exact runtime type."""

        registration = self._by_patch_type.get(type(patch))
        if registration is None:
            raise ValueError(f"unregistered repair patch type: {type(patch).__name__}")
        return registration.apply(context, patch)


@dataclass(frozen=True)
class RepairDiagnosisRuleRegistration[ResultT]:
    """One exact diagnosis-rule type and its runtime binding function."""

    rule_id: str
    rule_type: type[Any]
    bind: Callable[[Any], ResultT]

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("repair diagnosis rule id must not be empty")


class RepairDiagnosisRuleRegistry[ResultT]:
    """Closed exact-type dispatcher for one configured diagnosis rule set."""

    def __init__(
        self,
        registrations: Iterable[RepairDiagnosisRuleRegistration[ResultT]],
    ) -> None:
        ordered = tuple(sorted(registrations, key=lambda registration: registration.rule_id))
        rule_ids = tuple(registration.rule_id for registration in ordered)
        rule_types = tuple(registration.rule_type for registration in ordered)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("repair diagnosis rule registry contains duplicate rule ids")
        if len(rule_types) != len(set(rule_types)):
            raise ValueError("repair diagnosis rule registry contains duplicate diagnosis rule types")
        self._registrations = ordered
        self._by_rule_type = {registration.rule_type: registration for registration in ordered}

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return configured diagnosis rule ids in deterministic order."""

        return tuple(registration.rule_id for registration in self._registrations)

    def bind(self, rule: object) -> ResultT:
        """Bind the sole handler registered for the rule's exact runtime type."""

        registration = self._by_rule_type.get(type(rule))
        if registration is None:
            raise ValueError(f"unregistered repair diagnosis rule type: {type(rule).__name__}")
        return registration.bind(rule)


@dataclass(frozen=True)
class RepairFeasibilityRuleRegistration[ContextT]:
    """One exact diagnosis-rule type and its static feasibility validator."""

    rule_id: str
    rule_type: type[Any]
    validate: Callable[[ContextT, Any], None]

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("repair feasibility rule id must not be empty")


class RepairFeasibilityRuleRegistry[ContextT]:
    """Closed exact-type dispatcher for configured feasibility validators."""

    def __init__(
        self,
        registrations: Iterable[RepairFeasibilityRuleRegistration[ContextT]],
    ) -> None:
        ordered = tuple(sorted(registrations, key=lambda registration: registration.rule_id))
        rule_ids = tuple(registration.rule_id for registration in ordered)
        rule_types = tuple(registration.rule_type for registration in ordered)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("repair feasibility registry contains duplicate rule ids")
        if len(rule_types) != len(set(rule_types)):
            raise ValueError("repair feasibility registry contains duplicate feasibility rule types")
        self._registrations = ordered
        self._by_rule_type = {registration.rule_type: registration for registration in ordered}

    @property
    def rule_ids(self) -> tuple[str, ...]:
        """Return configured feasibility rule ids in deterministic order."""

        return tuple(registration.rule_id for registration in self._registrations)

    def validate(self, context: ContextT, rule: object) -> None:
        """Validate one rule through its exact registered feasibility function."""

        registration = self._by_rule_type.get(type(rule))
        if registration is None:
            raise ValueError(f"unregistered repair feasibility rule type: {type(rule).__name__}")
        registration.validate(context, rule)
