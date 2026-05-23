# ABOUTME: AS 1668.2 heat load calculation CLI tool for HVAC benchmarks.
# ABOUTME: Embeds ventilation lookup table and computes full cooling load chain.

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Literal

# ---------------------------------------------------------------------------
# AS 1668.2 Table A1 — Ventilation requirements by room type
# Each entry: (area_per_person m², OA_per_person L/s, min_OA_rate L/s/m²,
#              classification)
# For occupied spaces: OA = num_people × OA_per_person
# For unoccupied spaces (area_per_person == 0): OA = floor_area × min_OA_rate
# ---------------------------------------------------------------------------

AS1668_TABLE: dict[str, dict[str, float | str]] = {
    "Office Areas": {
        "area_per_person": 10.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Conference Rooms": {
        "area_per_person": 2.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Meeting Rooms": {
        "area_per_person": 3.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Reception / Lobby": {
        "area_per_person": 5.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Corridors": {
        "area_per_person": 0.0,
        "oa_per_person": 0.0,
        "min_oa_rate": 0.5,
        "classification": "Class B",
    },
    "Retail Shops": {
        "area_per_person": 5.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Supermarkets": {
        "area_per_person": 5.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Restaurants": {
        "area_per_person": 1.5,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Cafeteria / Break Rooms": {
        "area_per_person": 2.5,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Kitchens (Commercial)": {
        "area_per_person": 5.0,
        "oa_per_person": 15.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Hotel Bedrooms": {
        "area_per_person": 10.0,
        "oa_per_person": 12.5,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Hotel Suites": {
        "area_per_person": 15.0,
        "oa_per_person": 12.5,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Classrooms": {
        "area_per_person": 2.0,
        "oa_per_person": 12.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Lecture Theatres": {
        "area_per_person": 1.0,
        "oa_per_person": 12.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Libraries": {
        "area_per_person": 5.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Hospital Wards": {
        "area_per_person": 10.0,
        "oa_per_person": 10.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Gymnasiums": {
        "area_per_person": 5.0,
        "oa_per_person": 15.0,
        "min_oa_rate": 0.0,
        "classification": "Class A",
    },
    "Data Centres / Server Rooms": {
        "area_per_person": 0.0,
        "oa_per_person": 0.0,
        "min_oa_rate": 1.0,
        "classification": "Class B",
    },
    "Storage / Warehouses": {
        "area_per_person": 0.0,
        "oa_per_person": 0.0,
        "min_oa_rate": 0.5,
        "classification": "Class B",
    },
    "Car Parks (Enclosed)": {
        "area_per_person": 0.0,
        "oa_per_person": 0.0,
        "min_oa_rate": 2.5,
        "classification": "Class C",
    },
}

# Sensible and latent gains per person (W)
PEOPLE_SENSIBLE_W = 75.0
PEOPLE_LATENT_W = 55.0

# Air density × specific heat for sensible calcs (kW/m³·°C → W/L/s·°C)
# Standard: 1.21 W per (L/s)·°C
AIR_SENSIBLE_FACTOR = 1.21

# Conversion factor for latent ventilation: divide enthalpy difference (kJ/kg)
# by 0.833 to get W per L/s. Derived from air density 1.2 kg/m³ ÷ 1000 L/m³.
AIR_LATENT_DIVISOR = 0.833


@dataclass(frozen=True)
class HeatLoadResult:
    """Complete heat load calculation result."""

    room_type: str
    floor_area: float
    ceiling_height: float
    volume: float
    area_per_person: float
    oa_per_person: float
    min_oa_rate: float
    classification: str
    num_people: float
    total_outside_air: float
    people_sensible_w: float
    people_latent_w: float
    lighting_w: float
    small_power_w: float
    conduction_w: float
    ventilation_sensible_w: float
    ventilation_latent_w: float
    total_sensible_w: float
    total_latent_w: float
    total_cooling_w: float

    def to_dict(self) -> dict[str, float | str]:
        """Convert to dict with rounded numeric values."""
        result: dict[str, float | str] = {}
        for key, val in self.__dict__.items():
            if isinstance(val, float):
                result[key] = round(val, 2)
            else:
                result[key] = val
        return result


def compute_heat_load(
    room_type: str,
    floor_area: float,
    ceiling_height: float,
    outdoor_db: float,
    indoor_db: float,
    outdoor_enthalpy: float,
    indoor_enthalpy: float,
    lighting_density: float,
    small_power_density: float,
    conduction_factor: float,
    ventilation_type: Literal["mechanical", "natural"] = "mechanical",
) -> HeatLoadResult:
    """Compute full cooling load for a single room."""
    if room_type not in AS1668_TABLE:
        print(f"Error: Unknown room type '{room_type}'.", file=sys.stderr)
        print("Use --list-room-types to see available types.", file=sys.stderr)
        sys.exit(1)

    lookup = AS1668_TABLE[room_type]
    area_per_person = float(lookup["area_per_person"])
    oa_per_person = float(lookup["oa_per_person"])
    min_oa_rate = float(lookup["min_oa_rate"])
    classification = str(lookup["classification"])

    volume = floor_area * ceiling_height

    # Occupancy
    if area_per_person > 0:
        num_people = floor_area / area_per_person
    else:
        num_people = 0.0

    # Outside air (L/s)
    if num_people > 0 and oa_per_person > 0:
        total_outside_air = num_people * oa_per_person
    else:
        total_outside_air = floor_area * min_oa_rate

    # People gains (W)
    people_sensible = num_people * PEOPLE_SENSIBLE_W
    people_latent = num_people * PEOPLE_LATENT_W

    # Area-based gains (W)
    lighting = floor_area * lighting_density
    small_power = floor_area * small_power_density
    conduction = floor_area * conduction_factor

    # Ventilation gains (W)
    delta_t = outdoor_db - indoor_db
    ventilation_sensible = delta_t * AIR_SENSIBLE_FACTOR * total_outside_air

    delta_h = outdoor_enthalpy - indoor_enthalpy
    ventilation_latent = delta_h * total_outside_air / AIR_LATENT_DIVISOR

    # Totals
    total_sensible = (
        people_sensible + lighting + small_power + conduction + ventilation_sensible
    )
    total_latent = people_latent + ventilation_latent
    total_cooling = total_sensible + total_latent

    return HeatLoadResult(
        room_type=room_type,
        floor_area=floor_area,
        ceiling_height=ceiling_height,
        volume=volume,
        area_per_person=area_per_person,
        oa_per_person=oa_per_person,
        min_oa_rate=min_oa_rate,
        classification=classification,
        num_people=num_people,
        total_outside_air=total_outside_air,
        people_sensible_w=people_sensible,
        people_latent_w=people_latent,
        lighting_w=lighting,
        small_power_w=small_power,
        conduction_w=conduction,
        ventilation_sensible_w=ventilation_sensible,
        ventilation_latent_w=ventilation_latent,
        total_sensible_w=total_sensible,
        total_latent_w=total_latent,
        total_cooling_w=total_cooling,
    )


def format_table(result: HeatLoadResult) -> str:
    """Format result as a human-readable table."""
    d = result.to_dict()
    lines = ["Heat Load Calculation Results", "=" * 40]
    for key, val in d.items():
        label = key.replace("_", " ").title()
        if isinstance(val, float):
            lines.append(f"{label:30s}  {val:>12.2f}")
        else:
            lines.append(f"{label:30s}  {val!s:>12s}")
    return "\n".join(lines)


def list_room_types() -> None:
    """Print all available room types and their AS 1668.2 parameters."""
    print(f"{'Room Type':<30s}  {'m²/person':>10s}  {'OA L/s/p':>10s}  "
          f"{'Min OA':>10s}  {'Class':>8s}")
    print("-" * 75)
    for name, params in AS1668_TABLE.items():
        print(
            f"{name:<30s}  {params['area_per_person']:>10.1f}  "
            f"{params['oa_per_person']:>10.1f}  "
            f"{params['min_oa_rate']:>10.1f}  "
            f"{params['classification']!s:>8s}"
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="AS 1668.2 Heat Load Calculator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--list-room-types",
        action="store_true",
        help="List available room types and exit",
    )
    parser.add_argument("--room-type", type=str, help="Room type from AS 1668.2 table")
    parser.add_argument("--floor-area", type=float, help="Floor area in m²")
    parser.add_argument("--ceiling-height", type=float, help="Ceiling height in m")
    parser.add_argument("--outdoor-db", type=float, help="Outdoor dry-bulb temp (°C)")
    parser.add_argument("--outdoor-wb", type=float, help="Outdoor wet-bulb temp (°C)")
    parser.add_argument("--indoor-db", type=float, help="Indoor dry-bulb temp (°C)")
    parser.add_argument(
        "--outdoor-enthalpy", type=float, help="Outdoor air enthalpy (kJ/kg)"
    )
    parser.add_argument(
        "--indoor-enthalpy", type=float, help="Indoor air enthalpy (kJ/kg)"
    )
    parser.add_argument(
        "--lighting-density", type=float, help="Lighting power density (W/m²)"
    )
    parser.add_argument(
        "--small-power-density", type=float, help="Small power density (W/m²)"
    )
    parser.add_argument(
        "--conduction-factor", type=float, help="Conduction/transmission factor (W/m²)"
    )
    parser.add_argument(
        "--ventilation-type",
        type=str,
        default="mechanical",
        choices=["mechanical", "natural"],
        help="Ventilation type (default: mechanical)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="json",
        choices=["json", "table"],
        help="Output format (default: json)",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list_room_types:
        list_room_types()
        return

    required = [
        "room_type",
        "floor_area",
        "ceiling_height",
        "outdoor_db",
        "indoor_db",
        "outdoor_enthalpy",
        "indoor_enthalpy",
        "lighting_density",
        "small_power_density",
        "conduction_factor",
    ]
    missing = [f for f in required if getattr(args, f, None) is None]
    if missing:
        flags = [f"--{f.replace('_', '-')}" for f in missing]
        parser.error(f"Missing required arguments: {', '.join(flags)}")

    result = compute_heat_load(
        room_type=args.room_type,
        floor_area=args.floor_area,
        ceiling_height=args.ceiling_height,
        outdoor_db=args.outdoor_db,
        indoor_db=args.indoor_db,
        outdoor_enthalpy=args.outdoor_enthalpy,
        indoor_enthalpy=args.indoor_enthalpy,
        lighting_density=args.lighting_density,
        small_power_density=args.small_power_density,
        conduction_factor=args.conduction_factor,
        ventilation_type=args.ventilation_type,
    )

    if args.format == "json":
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(format_table(result))


if __name__ == "__main__":
    main()
