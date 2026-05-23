# ABOUTME: Computes interior task uniformity and adjacent-area illuminance ratios.
# ABOUTME: Uses task, surround, and background illuminance values.


def _validate_inputs(
    task_min_illuminance_lux: float,
    task_average_illuminance_lux: float,
    surround_average_illuminance_lux: float,
    background_average_illuminance_lux: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if task_average_illuminance_lux <= 0:
        msg = "task_average_illuminance_lux must be > 0"
        raise ValueError(msg)
    for name, value in {
        "task_min_illuminance_lux": task_min_illuminance_lux,
        "surround_average_illuminance_lux": surround_average_illuminance_lux,
        "background_average_illuminance_lux": background_average_illuminance_lux,
    }.items():
        if value < 0:
            msg = f"{name} must be >= 0"
            raise ValueError(msg)


def compute(
    task_min_illuminance_lux: float,
    task_average_illuminance_lux: float,
    surround_average_illuminance_lux: float,
    background_average_illuminance_lux: float,
) -> dict[str, float]:
    """Compute task uniformity and adjacent illuminance ratios."""
    _validate_inputs(
        task_min_illuminance_lux,
        task_average_illuminance_lux,
        surround_average_illuminance_lux,
        background_average_illuminance_lux,
    )

    task_uniformity_uo = task_min_illuminance_lux / task_average_illuminance_lux
    surround_to_task_ratio = surround_average_illuminance_lux / task_average_illuminance_lux
    background_to_task_ratio = background_average_illuminance_lux / task_average_illuminance_lux

    return {
        "task_uniformity_uo": round(task_uniformity_uo, 2),
        "surround_to_task_ratio": round(surround_to_task_ratio, 2),
        "background_to_task_ratio": round(background_to_task_ratio, 2),
    }
