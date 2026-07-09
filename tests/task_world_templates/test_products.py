# ABOUTME: Tests composite task-world template contracts and catalogue coverage.
# ABOUTME: Pins compilation into existing task-world payloads before implementation code exists.

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

from aec_bench.task_world_templates.catalogue import get_template, list_templates


def test_builtin_catalogue_covers_composite_task_world_templates() -> None:
    templates = list_templates()

    assert [template.template_id for template in templates] == [
        "stormwater-drainage-package",
        "pump-station-duty-package",
        "fire-water-supply-sprinkler-demand",
        "road-rail-alignment-package",
        "wind-facade-structural-package",
        "civil-ground-retaining-interface",
        "treatment-aeration-power-package",
        "pv-storage-feeder-package",
        "earthing-arc-flash-package",
        "rail-braking-signalling-package",
        "road-visual-operations-package",
        "road-low-point-issue-review-package",
        "intersection-signal-safety-issue-review-package",
        "road-visual-operations-issue-review-package",
        "emergency-detour-device-issue-review-package",
        "bus-priority-cabinet-issue-review-package",
        "driveway-access-safety-issue-review-package",
        "roadside-cabinet-serviceability-issue-review-package",
        "corridor-comment-response-issue-review-package",
    ]
    assert all(template.data_gaps for template in templates)
    assert all(template.verifier_gates for template in templates)
    assert all(template.source_artifacts for template in templates)


def test_composite_template_compiles_to_meta_harness_payload() -> None:
    template = get_template("pump-station-duty-package")

    payload = template.compile_task_world_payload()

    assert payload["template_id"] == "pump-station-duty-package"
    assert payload["world_id"] == "aec.task_world.composite.pump-station-duty-package"
    assert payload["task_unit"] == "composite-task-world-template"
    assert payload["logic_profile"]["closure_gates"][0]["evidence_key"].startswith("gates.")
    assert "source_pack" in payload["operation_profile"]["projection_axes"]
    assert "handoff_chain" in payload["operation_profile"]["product_axes"]
    assert payload["operation_handles"]["source_pack"]["paths"] == ["source_artifacts"]
    assert payload["operation_handles"]["handoff_chain"]["paths"] == ["handoffs"]


def test_composite_template_profile_remains_inside_existing_contract_boundary() -> None:
    template = get_template("stormwater-drainage-package")

    profile = template.compile_task_world_profile()

    assert profile.world_id == "aec.task_world.composite.stormwater-drainage-package"
    assert profile.task_unit == "composite-task-world-template"
    assert profile.operation_profile.product_axes == ["handoff_chain", "discipline_interface"]
    assert [gate.id for gate in profile.logic_profile.closure_gates] == [
        "source_values",
        "peak_flow_handoff",
        "detention_volume",
        "outlet_capacity",
        "pipe_velocity_hgl",
        "final_compliance",
    ]


def test_long_horizon_is_not_a_standalone_package_or_runtime() -> None:
    assert importlib.util.find_spec("aec_bench.long_horizon") is None
    assert not Path("src/aec_bench/long_horizon").exists()


def test_road_visual_operations_template_matches_task_owned_source_pack() -> None:
    template = get_template("road-visual-operations-package")
    source_pack = Path(
        "docs/task-world-opportunities/real-world-grounding/"
        "lighting-visual-its-cctv-communications-package/road_visual_operations_source_pack"
    )
    ledger = yaml.safe_load((source_pack / "handoff-ledger.yaml").read_text(encoding="utf-8"))
    source_handoffs = {item["id"]: item["value"] for item in ledger["handoffs"]}

    assert template.template_id == "road-visual-operations-package"
    assert template.discipline_scope == ["electrical", "transport", "communications", "security"]
    assert template.example_handoffs() == {
        "scene_id": source_handoffs["H_SCENE_ID"],
        "average_illuminance_lux": source_handoffs["H_LIGHT_AVG_LUX"],
        "minimum_illuminance_lux": source_handoffs["H_LIGHT_MIN_LUX"],
        "min_to_average_uniformity": source_handoffs["H_LIGHT_U0"],
        "minimum_camera_ppm": source_handoffs["H_CCTV_MIN_PPM"],
        "cctv_storage_tb": source_handoffs["H_CCTV_STORAGE_TB"],
        "vms_message_policy_id": source_handoffs["H_VMS_POLICY_ID"],
        "network_load_mbps": source_handoffs["H_NETWORK_LOAD_MBPS"],
        "poe_load_w": source_handoffs["H_POE_LOAD_W"],
        "fibre_loss_db": source_handoffs["H_FIBRE_LOSS_DB"],
        "ups_energy_kwh": source_handoffs["H_UPS_ENERGY_KWH"],
    }


def test_ssc01_review_first_companions_preserve_formula_baselines() -> None:
    low_point = get_template("road-low-point-issue-review-package")
    intersection = get_template("intersection-signal-safety-issue-review-package")
    visual_ops = get_template("road-visual-operations-issue-review-package")
    detour = get_template("emergency-detour-device-issue-review-package")
    bus_priority = get_template("bus-priority-cabinet-issue-review-package")
    driveway_access = get_template("driveway-access-safety-issue-review-package")
    roadside_cabinet = get_template("roadside-cabinet-serviceability-issue-review-package")
    corridor = get_template("corridor-comment-response-issue-review-package")

    assert low_point.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert intersection.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert visual_ops.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert detour.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert bus_priority.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert driveway_access.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert roadside_cabinet.pattern == "source packet -> issue-readiness review -> gated verifier record"
    assert corridor.pattern == "source packet -> issue-readiness review -> gated verifier record"

    low_point_refs = {ref for stage in low_point.stages for ref in stage.template_refs}
    intersection_refs = {ref for stage in intersection.stages for ref in stage.template_refs}
    visual_ops_refs = {ref for stage in visual_ops.stages for ref in stage.template_refs}
    detour_refs = {ref for stage in detour.stages for ref in stage.template_refs}
    bus_priority_refs = {ref for stage in bus_priority.stages for ref in stage.template_refs}
    driveway_access_refs = {ref for stage in driveway_access.stages for ref in stage.template_refs}
    roadside_cabinet_refs = {ref for stage in roadside_cabinet.stages for ref in stage.template_refs}
    corridor_refs = {ref for stage in corridor.stages for ref in stage.template_refs}

    assert "road-low-point-resilience-package" in low_point_refs
    assert "road-low-point-issue-review-package" in low_point_refs
    assert "intersection-timing-grade-sight-distance-package" in intersection_refs
    assert "intersection-signal-safety-issue-review-package" in intersection_refs
    assert "road-lighting-its-drainage-operations-package" in visual_ops_refs
    assert "road-visual-operations-issue-review-package" in visual_ops_refs
    assert "emergency-detour-roadside-device-continuity-package" in detour_refs
    assert "emergency-detour-device-issue-review-package" in detour_refs
    assert "bus-priority-signal-cabinet-load-package" in bus_priority_refs
    assert "bus-priority-cabinet-issue-review-package" in bus_priority_refs
    assert "culvert-driveway-access-safety-continuity-package" in driveway_access_refs
    assert "driveway-access-safety-issue-review-package" in driveway_access_refs
    assert "roadside-cabinet-flood-heat-backup-energy-package" in roadside_cabinet_refs
    assert "roadside-cabinet-serviceability-issue-review-package" in roadside_cabinet_refs
    assert "multimodal-corridor-review-response-package" in corridor_refs
    assert "corridor-comment-response-issue-review-package" in corridor_refs

    assert low_point.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert intersection.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert visual_ops.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert detour.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert bus_priority.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert driveway_access.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert roadside_cabinet.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert corridor.compile_task_world_profile().task_unit == "composite-task-world-template"
    assert "model_run_evidence" in {gap.id for gap in low_point.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in intersection.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in visual_ops.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in detour.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in bus_priority.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in driveway_access.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in roadside_cabinet.data_gaps}
    assert "model_run_evidence" in {gap.id for gap in corridor.data_gaps}
