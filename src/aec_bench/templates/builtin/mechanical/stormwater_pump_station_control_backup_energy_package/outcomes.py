# ABOUTME: Projects named composition outcomes from stormwater pump-station verifier evidence.
# ABOUTME: Keeps component and integration semantics with the task evaluation owner.

from collections.abc import Mapping

_HEADLOSS_COMPONENT_FIELDS = ("hazen_williams_loss_m", "rising_main_velocity_m_s")
_POWER_COMPONENT_FIELDS = ("hydraulic_power_kw", "motor_input_power_kw")
_INTEGRATION_FIELDS = ("total_dynamic_head_m", "hydraulic_power_kw", "motor_input_power_kw")


def component_a_correct(details: Mapping[str, object] | None) -> float | None:
    """Project whether the Hazen-Williams component outputs are all correct."""

    return _all_fields_correct(details, _HEADLOSS_COMPONENT_FIELDS)


def component_b_correct(details: Mapping[str, object] | None) -> float | None:
    """Project whether the hydraulic and motor power component outputs are all correct."""

    return _all_fields_correct(details, _POWER_COMPONENT_FIELDS)


def integration_correct(details: Mapping[str, object] | None) -> float | None:
    """Project whether head loss is carried through total head into pump power."""

    return _all_fields_correct(details, _INTEGRATION_FIELDS)


def composition_outcome(reward: object) -> float | None:
    """Project the complete task reward when it is a bounded numeric value."""

    if isinstance(reward, bool) or not isinstance(reward, int | float):
        return None
    value = float(reward)
    return value if 0.0 <= value <= 1.0 else None


def _all_fields_correct(details: Mapping[str, object] | None, fields: tuple[str, ...]) -> float | None:
    if details is None:
        return None
    scores: list[float] = []
    for field in fields:
        score = details.get(field)
        if isinstance(score, bool) or not isinstance(score, int | float):
            return None
        numeric = float(score)
        if not 0.0 <= numeric <= 1.0:
            return None
        scores.append(numeric)
    return min(scores)


__all__ = (
    "component_a_correct",
    "component_b_correct",
    "composition_outcome",
    "integration_correct",
)
