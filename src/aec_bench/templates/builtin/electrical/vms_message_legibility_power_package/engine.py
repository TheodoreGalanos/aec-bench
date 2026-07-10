# ABOUTME: Computes SSC-13 VMS message legibility and power metrics.
# ABOUTME: Combines sign legibility, read time, network, and power checks.

from __future__ import annotations


def _require_positive(**values: float) -> None:
    for name, value in values.items():
        if value <= 0:
            msg = f"{name} must be > 0"
            raise ValueError(msg)


def compute(
    letter_height_mm: float,
    legibility_factor_m_per_mm: float,
    available_viewing_distance_m: float,
    road_speed_kmh: float,
    required_read_time_s: float,
    display_power_w: float,
    controller_power_w: float,
    modem_power_w: float,
    circuit_capacity_w: float,
    vms_network_mbps: float,
    controller_network_mbps: float,
    network_capacity_mbps: float,
    compliant_message_count: float,
    required_message_count: float,
) -> dict[str, float]:
    _require_positive(
        letter_height_mm=letter_height_mm,
        legibility_factor_m_per_mm=legibility_factor_m_per_mm,
        available_viewing_distance_m=available_viewing_distance_m,
        road_speed_kmh=road_speed_kmh,
        required_read_time_s=required_read_time_s,
        circuit_capacity_w=circuit_capacity_w,
        network_capacity_mbps=network_capacity_mbps,
        required_message_count=required_message_count,
    )

    required_legibility_distance_m = letter_height_mm * legibility_factor_m_per_mm
    legibility_distance_margin_m = available_viewing_distance_m - required_legibility_distance_m
    speed_m_s = road_speed_kmh * 1000.0 / 3600.0
    available_read_time_s = available_viewing_distance_m / speed_m_s
    read_time_margin_s = available_read_time_s - required_read_time_s
    vms_power_load_w = display_power_w + controller_power_w + modem_power_w
    power_headroom_w = circuit_capacity_w - vms_power_load_w
    network_load_mbps = vms_network_mbps + controller_network_mbps
    network_headroom_mbps = network_capacity_mbps - network_load_mbps
    message_policy_match_fraction = compliant_message_count / required_message_count
    overall_pass_score = (
        1.0
        if (
            legibility_distance_margin_m >= 0.0
            and read_time_margin_s >= 0.0
            and power_headroom_w >= 0.0
            and network_headroom_mbps >= 0.0
            and message_policy_match_fraction >= 1.0
        )
        else 0.0
    )

    return {
        "required_legibility_distance_m": round(required_legibility_distance_m, 3),
        "legibility_distance_margin_m": round(legibility_distance_margin_m, 3),
        "available_read_time_s": round(available_read_time_s, 3),
        "read_time_margin_s": round(read_time_margin_s, 3),
        "vms_power_load_w": round(vms_power_load_w, 3),
        "power_headroom_w": round(power_headroom_w, 3),
        "network_load_mbps": round(network_load_mbps, 3),
        "network_headroom_mbps": round(network_headroom_mbps, 3),
        "message_policy_match_fraction": round(message_policy_match_fraction, 3),
        "overall_pass_score": round(overall_pass_score, 3),
    }
