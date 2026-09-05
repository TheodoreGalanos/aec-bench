# ABOUTME: Declares deterministic comparison policies for the engineering decision experiments.
# ABOUTME: Policies use only public observations and make no model-performance claim.

from collections.abc import Callable

from aec_bench.worlds.monitoring.dam_seepage.world import InstrumentCondition, SeepageAction, SeepageObservation


def evidence_first_action(observation: SeepageObservation) -> SeepageAction:
    """Choose from released evidence only; never read the scenario or verifier."""
    if observation.instrument_condition is None:
        return SeepageAction.CHECK_MEASUREMENT_SYSTEM
    if observation.instrument_condition is InstrumentCondition.UNRELIABLE:
        return SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW
    if observation.scheduled_readings_remaining:
        return SeepageAction.RECORD_CONFIRMATION_READING
    if observation.readings[-1].downstream_condition is None:
        return SeepageAction.INSPECT_DOWNSTREAM_AREA
    if observation.readings[-1].downstream_condition in observation.visual_alert_conditions:
        return SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW
    consecutive = 0
    for reading in observation.readings:
        consecutive = consecutive + 1 if reading.measured_flow_l_min >= reading.alert_flow_l_min else 0
        if consecutive >= observation.required_consecutive_alert_readings:
            return SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW
    return SeepageAction.CONTINUE_ROUTINE_SURVEILLANCE


def dam_policy(name: str) -> Callable[[SeepageObservation], SeepageAction]:
    """Build a fresh policy so action-sequence state cannot cross trial boundaries."""
    if name == "evidence_first":
        return evidence_first_action
    if name == "unsupported":
        return lambda _: SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW
    if name == "late":
        actions = iter((SeepageAction.RECORD_CONFIRMATION_READING, SeepageAction.CHECK_MEASUREMENT_SYSTEM))
        return lambda _: next(actions, SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW)
    raise ValueError(f"unknown dam policy: {name}")
