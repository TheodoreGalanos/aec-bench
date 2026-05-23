# ABOUTME: Computes 4-20 mA signal scaling for a process variable.
# ABOUTME: Uses linear span interpolation between lower and upper range values.


def _validate_inputs(
    process_value: float,
    lower_range_value: float,
    upper_range_value: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if upper_range_value <= lower_range_value:
        msg = "upper_range_value must be greater than lower_range_value"
        raise ValueError(msg)
    if process_value < lower_range_value or process_value > upper_range_value:
        msg = "process_value must be within the configured range"
        raise ValueError(msg)


def compute(
    process_value: float,
    lower_range_value: float,
    upper_range_value: float,
) -> dict[str, float]:
    """Compute span percentage, current signal, and reconstructed process value."""
    _validate_inputs(process_value, lower_range_value, upper_range_value)

    span = upper_range_value - lower_range_value
    span_fraction = (process_value - lower_range_value) / span
    span_pct = span_fraction * 100.0
    current_signal_ma = 4.0 + 16.0 * span_fraction
    reconstructed_process_value = lower_range_value + ((current_signal_ma - 4.0) / 16.0) * span

    return {
        "span_pct": round(span_pct, 2),
        "current_signal_ma": round(current_signal_ma, 2),
        "reconstructed_process_value": round(reconstructed_process_value, 2),
    }
