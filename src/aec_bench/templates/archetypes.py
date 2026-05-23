# ABOUTME: Soil archetype and Australian site context parameter bundles.
# ABOUTME: Provides correlated min/max ranges for cohesion, friction angle, and unit weight.

from dataclasses import dataclass


@dataclass(frozen=True)
class SoilArchetype:
    """Parameter ranges for a named soil type used in geotechnical templates."""

    description: str
    cohesion_kpa_min: float
    cohesion_kpa_max: float
    friction_angle_deg_min: float
    friction_angle_deg_max: float
    unit_weight_kn_m3_min: float
    unit_weight_kn_m3_max: float


@dataclass(frozen=True)
class SiteContext:
    """Named site context grouping typical soil archetypes for an Australian location."""

    description: str
    typical_archetypes: tuple[str, ...]
    location: str


SOIL_ARCHETYPES: dict[str, SoilArchetype] = {
    "soft_nc_clay": SoilArchetype(
        description="Soft normally consolidated clay",
        cohesion_kpa_min=5.0,
        cohesion_kpa_max=15.0,
        friction_angle_deg_min=0.0,
        friction_angle_deg_max=5.0,
        unit_weight_kn_m3_min=15.0,
        unit_weight_kn_m3_max=17.0,
    ),
    "firm_clay": SoilArchetype(
        description="Firm clay",
        cohesion_kpa_min=20.0,
        cohesion_kpa_max=50.0,
        friction_angle_deg_min=2.0,
        friction_angle_deg_max=8.0,
        unit_weight_kn_m3_min=17.0,
        unit_weight_kn_m3_max=19.0,
    ),
    "stiff_oc_clay": SoilArchetype(
        description="Stiff overconsolidated clay",
        cohesion_kpa_min=50.0,
        cohesion_kpa_max=150.0,
        friction_angle_deg_min=5.0,
        friction_angle_deg_max=15.0,
        unit_weight_kn_m3_min=18.0,
        unit_weight_kn_m3_max=21.0,
    ),
    "loose_sand": SoilArchetype(
        description="Loose sand",
        cohesion_kpa_min=0.0,
        cohesion_kpa_max=0.0,
        friction_angle_deg_min=28.0,
        friction_angle_deg_max=32.0,
        unit_weight_kn_m3_min=15.0,
        unit_weight_kn_m3_max=17.0,
    ),
    "medium_dense_sand": SoilArchetype(
        description="Medium dense sand",
        cohesion_kpa_min=0.0,
        cohesion_kpa_max=0.0,
        friction_angle_deg_min=32.0,
        friction_angle_deg_max=36.0,
        unit_weight_kn_m3_min=17.0,
        unit_weight_kn_m3_max=19.0,
    ),
    "dense_sand": SoilArchetype(
        description="Dense sand",
        cohesion_kpa_min=0.0,
        cohesion_kpa_max=0.0,
        friction_angle_deg_min=36.0,
        friction_angle_deg_max=42.0,
        unit_weight_kn_m3_min=19.0,
        unit_weight_kn_m3_max=21.0,
    ),
    "silty_sand": SoilArchetype(
        description="Silty sand",
        cohesion_kpa_min=0.0,
        cohesion_kpa_max=5.0,
        friction_angle_deg_min=28.0,
        friction_angle_deg_max=34.0,
        unit_weight_kn_m3_min=17.0,
        unit_weight_kn_m3_max=19.0,
    ),
    "residual_weathered_rock": SoilArchetype(
        description="Residual/weathered rock",
        cohesion_kpa_min=10.0,
        cohesion_kpa_max=30.0,
        friction_angle_deg_min=30.0,
        friction_angle_deg_max=40.0,
        unit_weight_kn_m3_min=19.0,
        unit_weight_kn_m3_max=22.0,
    ),
}


SITE_CONTEXTS: dict[str, SiteContext] = {
    "brisbane-alluvial": SiteContext(
        description="Brisbane alluvial clay",
        typical_archetypes=("soft_nc_clay", "firm_clay"),
        location="QLD",
    ),
    "perth-coastal": SiteContext(
        description="Perth coastal sand",
        typical_archetypes=("medium_dense_sand", "dense_sand"),
        location="WA",
    ),
    "sydney-hawkesbury": SiteContext(
        description="Sydney Hawkesbury sandstone residual",
        typical_archetypes=("residual_weathered_rock", "stiff_oc_clay"),
        location="NSW",
    ),
    "melbourne-basalt": SiteContext(
        description="Melbourne basalt clay",
        typical_archetypes=("stiff_oc_clay", "firm_clay"),
        location="VIC",
    ),
    "cairns-coral": SiteContext(
        description="Cairns coral sand",
        typical_archetypes=("dense_sand", "medium_dense_sand"),
        location="QLD",
    ),
    "adelaide-stiff": SiteContext(
        description="Adelaide stiff clay",
        typical_archetypes=("stiff_oc_clay",),
        location="SA",
    ),
    "hunter-valley-alluvial": SiteContext(
        description="Hunter Valley alluvial sand",
        typical_archetypes=("loose_sand", "silty_sand"),
        location="NSW",
    ),
    "darwin-estuarine": SiteContext(
        description="Darwin estuarine clay",
        typical_archetypes=("soft_nc_clay",),
        location="NT",
    ),
}
