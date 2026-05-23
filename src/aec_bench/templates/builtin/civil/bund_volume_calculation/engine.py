# ABOUTME: Bund volume computation engine per AS/NZS 1940 oil containment requirements.
# ABOUTME: Calculates required bund capacity, net bund volume, and compliance status.


def _validate_inputs(
    num_containers: int,
    largest_container_volume_l: float,
    total_stored_volume_l: float,
    bund_length_m: float,
    bund_width_m: float,
    bund_wall_height_m: float,
    num_equipment_items: int,
    equipment_footprint_area_m2: float,
) -> None:
    """Raise ValueError for invalid input parameters."""
    if num_containers <= 0:
        msg = "num_containers must be > 0"
        raise ValueError(msg)
    if largest_container_volume_l <= 0:
        msg = "largest_container_volume_l must be > 0"
        raise ValueError(msg)
    if total_stored_volume_l <= 0:
        msg = "total_stored_volume_l must be > 0"
        raise ValueError(msg)
    if bund_length_m <= 0:
        msg = "bund_length_m must be > 0"
        raise ValueError(msg)
    if bund_width_m <= 0:
        msg = "bund_width_m must be > 0"
        raise ValueError(msg)
    if bund_wall_height_m < 0.15:
        msg = "bund_wall_height_m must be >= 0.15 (AS/NZS 1940 minimum)"
        raise ValueError(msg)
    if bund_wall_height_m > 1.5:
        msg = "bund_wall_height_m must be <= 1.5 (practical upper limit)"
        raise ValueError(msg)
    if num_equipment_items < 0:
        msg = "num_equipment_items must be >= 0"
        raise ValueError(msg)
    if equipment_footprint_area_m2 < 0:
        msg = "equipment_footprint_area_m2 must be >= 0"
        raise ValueError(msg)
    if num_equipment_items > 0 and equipment_footprint_area_m2 <= 0:
        msg = "equipment_footprint_area_m2 must be > 0 when num_equipment_items > 0"
        raise ValueError(msg)


def compute(
    num_containers: int,
    largest_container_volume_l: float,
    total_stored_volume_l: float,
    bund_length_m: float,
    bund_width_m: float,
    bund_wall_height_m: float,
    num_equipment_items: int = 0,
    equipment_footprint_area_m2: float = 0.0,
) -> dict[str, float]:
    """Compute bund volume requirements per AS/NZS 1940.

    AS/NZS 1940 requires the bund to hold the greater of:
      - 110% of the volume of the largest single container
      - 25% of the total stored volume of all containers

    Net bund volume accounts for displacement by equipment inside the bund:
      gross_bund_volume = length * width * wall_height
      equipment_displacement = num_equipment_items * footprint_area * wall_height
      net_bund_volume = gross_bund_volume - equipment_displacement

    Compliance: net_bund_volume >= required_bund_volume

    All volumes are in m^3 (litres are converted via 1 m^3 = 1000 L).

    Returns a dict with keys: required_bund_volume_m3, net_bund_volume_m3,
    bund_wall_height_m, compliance.
    """
    # Enforce physical constraint: total stored volume must include the largest container.
    # The sampler draws these independently, so clamp total upward when needed.
    if total_stored_volume_l < largest_container_volume_l:
        total_stored_volume_l = largest_container_volume_l

    _validate_inputs(
        num_containers,
        largest_container_volume_l,
        total_stored_volume_l,
        bund_length_m,
        bund_width_m,
        bund_wall_height_m,
        num_equipment_items,
        equipment_footprint_area_m2,
    )

    # Convert volumes from litres to cubic metres
    largest_container_volume_m3 = largest_container_volume_l / 1000.0
    total_stored_volume_m3 = total_stored_volume_l / 1000.0

    # AS/NZS 1940 required bund capacity: greater of 110% largest or 25% total
    capacity_110_pct = 1.10 * largest_container_volume_m3
    capacity_25_pct = 0.25 * total_stored_volume_m3
    required_bund_volume_m3 = max(capacity_110_pct, capacity_25_pct)

    # Gross internal bund volume (rectangular prism)
    gross_bund_volume_m3 = bund_length_m * bund_width_m * bund_wall_height_m

    # Equipment displacement (simplified as rectangular prisms up to wall height)
    equipment_displacement_m3 = num_equipment_items * equipment_footprint_area_m2 * bund_wall_height_m

    # Net bund volume after subtracting equipment displacement
    net_bund_volume_m3 = gross_bund_volume_m3 - equipment_displacement_m3

    # Compliance check: net volume must meet or exceed required volume
    compliance = 1.0 if net_bund_volume_m3 >= required_bund_volume_m3 else 0.0

    return {
        "required_bund_volume_m3": round(required_bund_volume_m3, 2),
        "net_bund_volume_m3": round(net_bund_volume_m3, 2),
        "bund_wall_height_m": round(bund_wall_height_m, 2),
        "compliance": round(compliance, 2),
    }
