# ABOUTME: Typed contracts for deterministic hydraulic source states and run evidence.
# ABOUTME: Validates physical bounds, topology, revisions, hashes, and artifact identities.

from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.task_world_templates.hydraulics.identity import canonical_json_sha256

Sha256 = str
SectionName = Literal["catchments", "scenarios", "basin", "outlet", "network", "criteria"]
ScenarioRole = Literal["design", "major"]
_SECTION_NAMES: tuple[SectionName, ...] = (
    "catchments",
    "scenarios",
    "basin",
    "outlet",
    "network",
    "criteria",
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_PACKAGE_ARTIFACTS = {"README.md", "engine/identity.json", "source/source-state.json"}
_RUN_ARTIFACTS = {"request.json", "results.json", "timeseries.json", "report.md"}
_MAX_SCENARIO_DURATION_S = 7 * 24 * 60 * 60
_MAX_SCENARIO_STEPS = 10_000


def _positive(name: str, value: float) -> None:
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and > 0")


def _nonnegative(name: str, value: float) -> None:
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")


def _validate_sha256(name: str, value: str) -> None:
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256")


class CatchmentSpec(StrictModel):
    catchment_id: NonEmptyStr
    area_ha: float
    runoff_coefficient: float

    @model_validator(mode="after")
    def validate_physical_bounds(self) -> CatchmentSpec:
        _positive("area_ha", self.area_ha)
        if self.area_ha > 80.0:
            raise ValueError("area_ha must be <= 80 for the rational-method screening world")
        if not 0.0 <= self.runoff_coefficient <= 1.0:
            raise ValueError("runoff_coefficient must be between 0 and 1")
        return self


class RainfallScenarioSpec(StrictModel):
    scenario_id: NonEmptyStr
    title: NonEmptyStr
    role: ScenarioRole
    rainfall_intensity_mm_h: float
    climate_factor: float
    storm_duration_s: int
    time_step_s: int

    @model_validator(mode="after")
    def validate_timing(self) -> RainfallScenarioSpec:
        _positive("rainfall_intensity_mm_h", self.rainfall_intensity_mm_h)
        _positive("climate_factor", self.climate_factor)
        if self.storm_duration_s <= 0 or self.time_step_s <= 0:
            raise ValueError("storm duration and time step must be > 0")
        if self.storm_duration_s % self.time_step_s != 0:
            raise ValueError("storm duration must be divisible by the fixed time step")
        if self.storm_duration_s > _MAX_SCENARIO_DURATION_S:
            raise ValueError("storm duration must not exceed seven days")
        if self.storm_duration_s // self.time_step_s > _MAX_SCENARIO_STEPS:
            raise ValueError(f"scenario must contain at most {_MAX_SCENARIO_STEPS} time steps")
        return self


class BasinSpec(StrictModel):
    basin_id: NonEmptyStr
    bottom_elevation_m: float
    crest_elevation_m: float
    bottom_area_m2: float
    top_area_m2: float
    initial_depth_m: float = 0.0

    @property
    def maximum_depth_m(self) -> float:
        return self.crest_elevation_m - self.bottom_elevation_m

    @model_validator(mode="after")
    def validate_geometry(self) -> BasinSpec:
        _nonnegative("bottom_elevation_m", self.bottom_elevation_m)
        _positive("bottom_area_m2", self.bottom_area_m2)
        _positive("top_area_m2", self.top_area_m2)
        if self.top_area_m2 < self.bottom_area_m2:
            raise ValueError("top_area_m2 must be >= bottom_area_m2")
        if self.crest_elevation_m <= self.bottom_elevation_m:
            raise ValueError("crest_elevation_m must exceed bottom_elevation_m")
        if not 0.0 <= self.initial_depth_m <= self.maximum_depth_m:
            raise ValueError("initial_depth_m must be within the basin")
        return self


class OrificeSpec(StrictModel):
    outlet_id: NonEmptyStr
    diameter_m: float
    discharge_coefficient: float
    centre_elevation_m: float

    @model_validator(mode="after")
    def validate_geometry(self) -> OrificeSpec:
        _positive("diameter_m", self.diameter_m)
        if not 0.0 < self.discharge_coefficient <= 1.0:
            raise ValueError("orifice discharge_coefficient must be > 0 and <= 1")
        _nonnegative("centre_elevation_m", self.centre_elevation_m)
        return self


class WeirSpec(StrictModel):
    outlet_id: NonEmptyStr
    crest_elevation_m: float
    length_m: float
    discharge_coefficient: float

    @model_validator(mode="after")
    def validate_geometry(self) -> WeirSpec:
        _nonnegative("crest_elevation_m", self.crest_elevation_m)
        _positive("length_m", self.length_m)
        if not 0.0 < self.discharge_coefficient <= 1.0:
            raise ValueError("weir discharge_coefficient must be > 0 and <= 1")
        return self


class OutletSpec(StrictModel):
    orifice: OrificeSpec
    emergency_weir: WeirSpec


class PitSpec(StrictModel):
    node_id: NonEmptyStr
    rim_elevation_m: float

    @model_validator(mode="after")
    def validate_rim(self) -> PitSpec:
        _nonnegative("rim_elevation_m", self.rim_elevation_m)
        return self


class PipeSpec(StrictModel):
    pipe_id: NonEmptyStr
    upstream_node_id: NonEmptyStr
    downstream_node_id: NonEmptyStr
    diameter_m: float
    length_m: float
    slope_m_per_m: float
    mannings_n: float
    minor_loss_coefficient: float

    @model_validator(mode="after")
    def validate_geometry(self) -> PipeSpec:
        _positive("diameter_m", self.diameter_m)
        _positive("length_m", self.length_m)
        _positive("slope_m_per_m", self.slope_m_per_m)
        _positive("mannings_n", self.mannings_n)
        _nonnegative("minor_loss_coefficient", self.minor_loss_coefficient)
        if self.upstream_node_id == self.downstream_node_id:
            raise ValueError("pipe endpoints must differ")
        return self


class NetworkSpec(StrictModel):
    pits: tuple[PitSpec, ...] = Field(min_length=1, max_length=32)
    pipes: tuple[PipeSpec, ...] = Field(min_length=1, max_length=32)
    tailwater_node_id: NonEmptyStr
    tailwater_elevation_m: float

    @model_validator(mode="after")
    def validate_pipe_chain(self) -> NetworkSpec:
        _nonnegative("tailwater_elevation_m", self.tailwater_elevation_m)
        pit_ids = [pit.node_id for pit in self.pits]
        if len(pit_ids) != len(set(pit_ids)):
            raise ValueError("pit node ids must be unique")
        pipe_ids = [pipe.pipe_id for pipe in self.pipes]
        if len(pipe_ids) != len(set(pipe_ids)):
            raise ValueError("pipe ids must be unique")
        if self.tailwater_node_id in set(pit_ids):
            raise ValueError("tailwater node must be distinct from every upstream pit")
        for index, pipe in enumerate(self.pipes[:-1]):
            if pipe.downstream_node_id != self.pipes[index + 1].upstream_node_id:
                raise ValueError("pipes must form one ordered pipe chain")
        if self.pipes[-1].downstream_node_id != self.tailwater_node_id:
            raise ValueError("pipe chain must terminate at the tailwater node")
        chain_nodes = [self.pipes[0].upstream_node_id, *(pipe.downstream_node_id for pipe in self.pipes)]
        if len(chain_nodes) != len(set(chain_nodes)):
            raise ValueError("pipe chain must not contain repeated nodes or cycles")
        expected_pits = {pipe.upstream_node_id for pipe in self.pipes}
        if set(pit_ids) != expected_pits:
            raise ValueError("pipe chain upstream nodes must match the declared pits")
        return self


class HydraulicCriteriaSpec(StrictModel):
    maximum_design_release_m3_s: float
    minimum_major_weir_flow_m3_s: float
    maximum_pipe_velocity_m_s: float
    minimum_hgl_clearance_m: float
    minimum_freeboard_m: float
    maximum_continuity_error_m3: float
    flow_tolerance_m3_s: float
    level_tolerance_m: float
    velocity_tolerance_m_s: float

    @model_validator(mode="after")
    def validate_criteria(self) -> HydraulicCriteriaSpec:
        for name, value in self.model_dump().items():
            _positive(name, float(value))
        return self


class HydraulicSourcePayload(StrictModel):
    catchments: tuple[CatchmentSpec, ...] = Field(min_length=2, max_length=16)
    scenarios: tuple[RainfallScenarioSpec, ...] = Field(min_length=1, max_length=16)
    basin: BasinSpec
    outlet: OutletSpec
    network: NetworkSpec
    criteria: HydraulicCriteriaSpec

    @model_validator(mode="after")
    def validate_world(self) -> HydraulicSourcePayload:
        catchment_ids = [item.catchment_id for item in self.catchments]
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if len(catchment_ids) != len(set(catchment_ids)):
            raise ValueError("catchment ids must be unique")
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ValueError("scenario ids must be unique")
        roles = {scenario.role for scenario in self.scenarios}
        if roles != {"design", "major"}:
            raise ValueError("hydraulic source state must contain design and major scenario roles")
        if self.outlet.orifice.centre_elevation_m < self.basin.bottom_elevation_m:
            raise ValueError("orifice centre must not be below the basin bottom")
        if (
            not self.basin.bottom_elevation_m
            < self.outlet.emergency_weir.crest_elevation_m
            < self.basin.crest_elevation_m
        ):
            raise ValueError("emergency weir crest must sit within the basin")
        return self


class SourceSectionIdentity(StrictModel):
    section_name: SectionName
    source_id: NonEmptyStr
    revision: NonEmptyStr
    content_sha256: Sha256

    @model_validator(mode="after")
    def validate_hash(self) -> SourceSectionIdentity:
        _validate_sha256("content_sha256", self.content_sha256)
        return self


class HydraulicReferenceSpec(StrictModel):
    source_pack_id: NonEmptyStr
    source_commit: NonEmptyStr
    role: NonEmptyStr


class HydraulicSourceState(StrictModel):
    schema_version: Literal["1"] = "1"
    world_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    claim_boundary: NonEmptyStr
    reference: HydraulicReferenceSpec
    payload: HydraulicSourcePayload
    sections: tuple[SourceSectionIdentity, ...]

    @model_validator(mode="after")
    def validate_section_identities(self) -> HydraulicSourceState:
        by_name = {section.section_name: section for section in self.sections}
        if len(by_name) != len(self.sections) or set(by_name) != set(_SECTION_NAMES):
            raise ValueError("source state must contain one identity for every source section")
        for section_name in _SECTION_NAMES:
            value = getattr(self.payload, section_name)
            if isinstance(value, tuple):
                serialized = [item.model_dump(mode="json") for item in value]
            else:
                serialized = value.model_dump(mode="json")
            if canonical_json_sha256(serialized) != by_name[section_name].content_sha256:
                raise ValueError(f"section hash does not match content: {section_name}")
        return self


def build_source_state_contract(
    *,
    world_id: str,
    title: str,
    description: str,
    claim_boundary: str,
    reference: HydraulicReferenceSpec,
    payload: HydraulicSourcePayload,
    section_revisions: dict[SectionName, tuple[str, str]],
) -> HydraulicSourceState:
    """Build a validated source state with hashes derived from exact section content."""
    if set(section_revisions) != set(_SECTION_NAMES):
        raise ValueError("section revisions must cover every source section")
    sections = []
    for section_name in _SECTION_NAMES:
        value = getattr(payload, section_name)
        if isinstance(value, tuple):
            serialized = [item.model_dump(mode="json") for item in value]
        else:
            serialized = value.model_dump(mode="json")
        source_id, revision = section_revisions[section_name]
        sections.append(
            SourceSectionIdentity(
                section_name=section_name,
                source_id=source_id,
                revision=revision,
                content_sha256=canonical_json_sha256(serialized),
            )
        )
    return HydraulicSourceState(
        world_id=world_id,
        title=title,
        description=description,
        claim_boundary=claim_boundary,
        reference=reference,
        payload=payload,
        sections=tuple(sections),
    )


class HydraulicEngineIdentity(StrictModel):
    engine_id: NonEmptyStr
    engine_version: NonEmptyStr
    source_inventory_sha256: dict[NonEmptyStr, Sha256]
    implementation_sha256: Sha256
    runtime_dependencies: dict[NonEmptyStr, NonEmptyStr]
    runtime_dependency_sha256: Sha256
    fidelity: Literal["bounded_screening_kernel"] = "bounded_screening_kernel"

    @model_validator(mode="after")
    def validate_hash(self) -> HydraulicEngineIdentity:
        if not self.source_inventory_sha256:
            raise ValueError("engine source inventory must not be empty")
        for value in self.source_inventory_sha256.values():
            _validate_sha256("source_inventory_sha256", value)
        _validate_sha256("implementation_sha256", self.implementation_sha256)
        if self.implementation_sha256 != canonical_json_sha256(dict(sorted(self.source_inventory_sha256.items()))):
            raise ValueError("implementation_sha256 does not match engine source inventory")
        if not self.runtime_dependencies:
            raise ValueError("engine runtime dependencies must not be empty")
        _validate_sha256("runtime_dependency_sha256", self.runtime_dependency_sha256)
        if self.runtime_dependency_sha256 != canonical_json_sha256(dict(sorted(self.runtime_dependencies.items()))):
            raise ValueError("runtime_dependency_sha256 does not match runtime dependencies")
        return self


class HydraulicPackageManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    world_id: NonEmptyStr
    artifact_sha256: dict[NonEmptyStr, Sha256]
    package_sha256: Sha256

    @model_validator(mode="after")
    def validate_identity(self) -> HydraulicPackageManifest:
        if set(self.artifact_sha256) != _PACKAGE_ARTIFACTS:
            raise ValueError("package manifest must bind the exact package artifact set")
        for value in self.artifact_sha256.values():
            _validate_sha256("artifact_sha256", value)
        _validate_sha256("package_sha256", self.package_sha256)
        expected = canonical_json_sha256(
            {"world_id": self.world_id, "artifact_sha256": dict(sorted(self.artifact_sha256.items()))}
        )
        if self.package_sha256 != expected:
            raise ValueError("package_sha256 does not match package artifacts")
        return self


class HydraulicRunRequest(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: NonEmptyStr
    world_id: NonEmptyStr
    scenario_id: NonEmptyStr
    package_sha256: Sha256
    source_state_sha256: Sha256
    calculation_input_sha256: Sha256
    engine: HydraulicEngineIdentity

    @model_validator(mode="after")
    def validate_identity(self) -> HydraulicRunRequest:
        for name in ("package_sha256", "source_state_sha256", "calculation_input_sha256"):
            _validate_sha256(name, getattr(self, name))
        expected = hydraulic_run_id(
            world_id=self.world_id,
            scenario_id=self.scenario_id,
            package_sha256=self.package_sha256,
            source_state_sha256=self.source_state_sha256,
            calculation_input_sha256=self.calculation_input_sha256,
            engine=self.engine,
        )
        if self.run_id != expected:
            raise ValueError("run_id does not match the canonical run request")
        return self


def hydraulic_run_id(
    *,
    world_id: str,
    scenario_id: str,
    package_sha256: str,
    source_state_sha256: str,
    calculation_input_sha256: str,
    engine: HydraulicEngineIdentity,
) -> str:
    """Return the content-bound identity for one deterministic world request."""
    digest = canonical_json_sha256(
        {
            "schema_version": "1",
            "world_id": world_id,
            "scenario_id": scenario_id,
            "package_sha256": package_sha256,
            "source_state_sha256": source_state_sha256,
            "calculation_input_sha256": calculation_input_sha256,
            "engine": engine.model_dump(mode="json"),
        }
    )
    return f"hydraulic-{digest}"


class HydraulicTimeStep(StrictModel):
    time_s: int
    total_inflow_m3_s: float
    orifice_flow_m3_s: float
    weir_flow_m3_s: float
    uncontrolled_spill_m3_s: float
    total_outflow_m3_s: float
    storage_m3: float
    water_depth_m: float
    water_surface_elevation_m: float
    node_hgl_m: dict[NonEmptyStr, float]
    pipe_velocity_m_s: dict[NonEmptyStr, float]
    pipe_capacity_m3_s: dict[NonEmptyStr, float]
    outlet_converged: bool


class HydraulicTimeSeries(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: NonEmptyStr
    steps: tuple[HydraulicTimeStep, ...]


class HydraulicRunResult(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: NonEmptyStr
    world_id: NonEmptyStr
    scenario_id: NonEmptyStr
    engine: HydraulicEngineIdentity
    source_state_sha256: Sha256
    calculation_input_sha256: Sha256
    catchment_peak_flows_m3_s: dict[NonEmptyStr, float]
    peak_total_inflow_m3_s: float
    peak_orifice_flow_m3_s: float
    peak_weir_flow_m3_s: float
    peak_structured_outflow_m3_s: float
    peak_total_outflow_m3_s: float
    peak_uncontrolled_spill_m3_s: float
    maximum_storage_m3: float
    maximum_water_surface_elevation_m: float
    minimum_freeboard_m: float
    maximum_pipe_velocity_m_s: dict[NonEmptyStr, float]
    pipe_capacity_m3_s: dict[NonEmptyStr, float]
    maximum_node_hgl_m: dict[NonEmptyStr, float]
    minimum_hgl_clearance_m: float
    continuity_error_m3: float
    criteria: dict[NonEmptyStr, bool]
    warnings: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_hashes(self) -> HydraulicRunResult:
        _validate_sha256("source_state_sha256", self.source_state_sha256)
        _validate_sha256("calculation_input_sha256", self.calculation_input_sha256)
        return self


class HydraulicVerificationGate(StrictModel):
    passed: bool
    diagnostics: tuple[NonEmptyStr, ...] = ()


class HydraulicVerificationRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    verifier_id: NonEmptyStr
    verifier_source_inventory_sha256: dict[NonEmptyStr, Sha256]
    verifier_source_sha256: Sha256
    run_id: NonEmptyStr
    run_manifest_sha256: Sha256
    passed: bool
    gates: dict[NonEmptyStr, HydraulicVerificationGate]

    @model_validator(mode="after")
    def validate_result(self) -> HydraulicVerificationRecord:
        if not self.verifier_source_inventory_sha256:
            raise ValueError("verifier source inventory must not be empty")
        for value in self.verifier_source_inventory_sha256.values():
            _validate_sha256("verifier_source_inventory_sha256", value)
        _validate_sha256("verifier_source_sha256", self.verifier_source_sha256)
        _validate_sha256("run_manifest_sha256", self.run_manifest_sha256)
        if self.verifier_source_sha256 != canonical_json_sha256(
            dict(sorted(self.verifier_source_inventory_sha256.items()))
        ):
            raise ValueError("verifier_source_sha256 does not match verifier source inventory")
        expected = bool(self.gates) and all(gate.passed for gate in self.gates.values())
        if self.passed != expected:
            raise ValueError("verification passed flag must equal all gate results")
        return self


class HydraulicRunManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: NonEmptyStr
    world_id: NonEmptyStr
    scenario_id: NonEmptyStr
    package_sha256: Sha256
    source_state_sha256: Sha256
    calculation_input_sha256: Sha256
    engine: HydraulicEngineIdentity
    artifact_sha256: dict[NonEmptyStr, Sha256]

    @model_validator(mode="after")
    def validate_hashes(self) -> HydraulicRunManifest:
        for name in ("package_sha256", "source_state_sha256", "calculation_input_sha256"):
            _validate_sha256(name, getattr(self, name))
        if set(self.artifact_sha256) != _RUN_ARTIFACTS:
            raise ValueError("run manifest must bind every declared run artifact")
        for value in self.artifact_sha256.values():
            _validate_sha256("artifact_sha256", value)
        return self
