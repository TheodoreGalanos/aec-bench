# ABOUTME: Computes VMS legibility distance and reading capacity.
# ABOUTME: Uses character height, design speed, and reading rate for a reduced check.


def _validate_inputs(
    character_height_in: float,
    design_speed_mph: float,
    reading_rate_chars_s: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if character_height_in <= 0:
        msg = "character_height_in must be > 0"
        raise ValueError(msg)
    if design_speed_mph <= 0:
        msg = "design_speed_mph must be > 0"
        raise ValueError(msg)
    if reading_rate_chars_s <= 0:
        msg = "reading_rate_chars_s must be > 0"
        raise ValueError(msg)


def compute(
    character_height_in: float,
    design_speed_mph: float,
    reading_rate_chars_s: float,
) -> dict[str, float]:
    """Compute VMS legibility distance and message reading capacity."""
    _validate_inputs(character_height_in, design_speed_mph, reading_rate_chars_s)

    minimum_legibility_distance_ft = character_height_in * 40.0
    design_speed_ft_s = design_speed_mph * 5280.0 / 3600.0
    reading_time_available_s = minimum_legibility_distance_ft / design_speed_ft_s
    message_length_limit_chars = reading_time_available_s * reading_rate_chars_s

    return {
        "minimum_legibility_distance_ft": round(minimum_legibility_distance_ft, 2),
        "design_speed_ft_s": round(design_speed_ft_s, 2),
        "reading_time_available_s": round(reading_time_available_s, 2),
        "message_length_limit_chars": round(message_length_limit_chars, 2),
    }
