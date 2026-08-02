# ABOUTME: Builds the canonical ASW-8 reference-system descriptor and its three bound artifacts.
# ABOUTME: Keeps opening state, scenario events, and temporal text outside certified station data.

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _work_windows() -> list[dict[str, int]]:
    return [
        {"end_calendar_seconds": 61_200, "start_calendar_seconds": 21_600},
        {"end_calendar_seconds": 165_600, "start_calendar_seconds": 108_000},
        {"end_calendar_seconds": 226_800, "start_calendar_seconds": 194_400},
    ]


def build_artifacts() -> dict[str, dict[str, Any]]:
    """Return the four canonical ASW-8 reference-system documents."""
    opening: dict[str, Any] = {
        "assignment": {
            "assigned_service_scu": 1,
            "assignment_id": "assignment-opening-c",
            "decision_detail": "accepted initial assignment",
            "ordered_pump_ids": ["pump-c"],
            "required_service_scu": 1,
            "unserved_service_scu": 0,
        },
        "accepted_evidence": [
            {
                "accepted_by": "maintenance",
                "evidence_id": "initial-b-inspection-accepted",
                "kind": "inspection",
                "operating_regime_id": "asw-8-rs1-declared-regime",
                "pump_id": "pump-b",
                "quality": "current",
                "source_id": "source-initial-b-inspection-accepted",
            },
            {
                "accepted_by": "operations",
                "evidence_id": "initial-c-assurance-accepted",
                "kind": "condition_check",
                "operating_regime_id": "asw-8-rs1-declared-regime",
                "pump_id": "pump-c",
                "quality": "current",
                "source_id": "source-initial-c-assurance-accepted",
            },
        ],
        "backlog": [
            {
                "base_priority": "P1",
                "due_calendar_seconds": 64_800,
                "due_runtime_limit_seconds": 32_400,
                "generation_rule_id": "WG-04",
                "generated_at_calendar_seconds": 7_200,
                "item_id": "backlog-a-verification-001",
                "status": "planned",
                "target_id": "pump-a",
                "work_type": "post_maintenance_verification",
            },
            {
                "base_priority": "P1",
                "due_calendar_seconds": 64_800,
                "due_runtime_limit_seconds": None,
                "generation_rule_id": "WG-02",
                "generated_at_calendar_seconds": 21_600,
                "item_id": "backlog-b-clearance-001",
                "status": "planned",
                "target_id": "pump-b",
                "work_type": "obstruction_clearance",
            },
        ],
        "calendar_seconds": 21_600,
        "common_boundary": {"discharge_available": True, "power_available": True},
        "environment": {"inflow_m3_s": "0.0155", "wet_well_level_m": "1.65"},
        "liability_owner_ids": ["obligation-a-verification-001", "outage-b-001"],
        "outage_episodes": [
            {
                "episode_id": "outage-b-001",
                "source_record_id": "initial-b-inspection-accepted",
                "status": "open",
                "unavailable_baseline_pump_id": "pump-b",
            }
        ],
        "profile_id": "AU-NSW-LH-SYN-SPS-v2",
        "pump_boundaries": {
            "pump-a": {"mode": "run_in_service", "source_id": "initial-a-provisional-return"},
            "pump-b": {"mode": "isolated_for_work", "source_id": "initial-b-inspection-accepted"},
            "pump-c": {"mode": "service_available", "source_id": "initial-c-assurance-accepted"},
        },
        "pumps": {
            "pump-a": {
                "clearance_loss": "0.00011999999998800",
                "completed_starts": 1,
                "obstruction": "0.02039999999998400",
                "runtime_seconds": 3_600,
            },
            "pump-b": {
                "clearance_loss": "0.00",
                "completed_starts": 0,
                "obstruction": "0.70",
                "runtime_seconds": 0,
            },
            "pump-c": {
                "clearance_loss": "0.00",
                "completed_starts": 1,
                "obstruction": "0.00015",
                "runtime_seconds": 0,
            },
        },
        "resource_state": {
            "consumable_pools": [
                {
                    "free": 1,
                    "on_hand": 1,
                    "pool_id": "obstruction-clearance-kit",
                    "reserved": 0,
                }
            ],
            "reusable_pools": [
                {
                    "availability_intervals": _work_windows(),
                    "capacity": 1,
                    "free": 1,
                    "pool_id": pool_id,
                    "reserved": 0,
                    "unavailable": 0,
                }
                for pool_id in (
                    "field-access-slot",
                    "lifting-isolation-set-01",
                    "diagnostic-test-set-01",
                    "maintenance-crew-01",
                    "verification-engineer-01",
                )
            ],
        },
        "required_actions": [
            {
                "due_calendar_seconds": 64_800,
                "due_runtime_seconds": 32_400,
                "kind": "post_maintenance_verification",
                "obligation_id": "obligation-a-verification-001",
                "pump_id": "pump-a",
                "responsible_authority": "verification",
                "status": "active",
            }
        ],
        "restrictions": [
            {
                "kind": "post_maintenance_run_in",
                "pump_id": "pump-a",
                "restriction_id": "restriction-a-run-in-001",
                "status": "active",
            },
            {
                "kind": "no_intervention",
                "pump_id": "pump-b",
                "restriction_id": "restriction-b-isolated-001",
                "status": "active",
            },
        ],
        "schema_id": "pump-station-asw-8-rs1-initial-state.v1",
        "service_running_pump_ids": ["pump-c"],
        "specification_id": "pump-station-asw-8-rs1-initial-state.v1",
        "test_running_pump_ids": [],
        "work_orders": [
            {
                "pump_id": "pump-a",
                "status": "open",
                "work_order_id": "work-order-a-001",
            },
            {
                "pump_id": "pump-b",
                "status": "open",
                "work_order_id": "work-order-b-001",
            },
        ],
    }
    schedule: dict[str, Any] = {
        "baseline_assignments": [
            {"end": 64_800, "ordered_pump_ids": ["pump-c"], "start": 21_600},
            {"end": 93_600, "ordered_pump_ids": ["pump-a", "pump-b"], "start": 64_800},
            {"end": 226_800, "ordered_pump_ids": ["pump-a"], "start": 93_600},
        ],
        "disclosed_through_calendar_seconds": 226_800,
        "event_schedule_id": "pump-station-asw-8-rs1-event-schedule.v1",
        "host_events": [
            {"event_id": "peak-start", "event_type": "service_requirement_change", "time": 64_800},
            {"event_id": "peak-end", "event_type": "service_requirement_change", "time": 93_600},
            {
                "event_id": "document-review-point-c-001",
                "event_type": "document_review_point",
                "refreshes_observation": False,
                "time": 100_800,
            },
            {"event_id": "work-window-w2-start", "event_type": "resource_availability", "time": 108_000},
            {"event_id": "c-priority-p1", "event_type": "backlog_priority", "time": 122_400},
            {"event_id": "c-calendar-due", "event_type": "backlog_due", "time": 151_200},
            {"event_id": "work-window-w2-end", "event_type": "resource_withdrawal", "time": 165_600},
            {"event_id": "work-window-w3-start", "event_type": "resource_availability", "time": 194_400},
            {"event_id": "work-window-w3-end", "event_type": "resource_withdrawal", "time": 226_800},
        ],
        "resource_windows": _work_windows(),
        "schema_id": "pump-station-asw-8-rs1-event-schedule.v1",
        "service_requirements": [
            {"end": 64_800, "required_scu": 1, "start": 21_600},
            {"end": 93_600, "required_scu": 2, "start": 64_800},
            {"end": 226_800, "required_scu": 1, "start": 93_600},
        ],
    }
    temporal: dict[str, Any] = {
        "availability_window": {"end_calendar_seconds": 226_800, "start_calendar_seconds": 21_600},
        "branch_policy_template": {"ancestor_chain_required": True, "private_access_state": "fresh"},
        "builder_id": "pump-station-asw-8-temporal-builder.v1",
        "documents": [
            {
                "applicable_asset_ids": ["synthetic-wastewater-pump-station", "pump-a", "pump-b", "pump-c"],
                "content": (
                    "Field work needs target isolation, shared access, and a controlled test permit. "
                    "Documentary text cannot grant operating authority."
                ),
                "created_at_calendar_seconds": 0,
                "document_id": "coupled-pump-field-work-bulletin.v1",
                "ingested_at_calendar_seconds": 7_200,
                "scope": "operations",
            },
            {
                "applicable_asset_ids": ["pump-b"],
                "content": (
                    "Pump B clearance ends at test_only. A controlled functional check and a separate "
                    "provisional return are required."
                ),
                "created_at_calendar_seconds": 95_400,
                "document_id": "pump-b-clearance-procedure.v2",
                "ingested_at_calendar_seconds": 97_200,
                "scope": "operations",
            },
            {
                "applicable_asset_ids": ["pump-c"],
                "content": (
                    "CCR28H: inspect Pump C after the declared collateral-duty threshold. A no-finding "
                    "result still needs an Operations isolation review."
                ),
                "created_at_calendar_seconds": 95_400,
                "document_id": "pump-c-collateral-inspection-note.v1",
                "ingested_at_calendar_seconds": 97_200,
                "scope": "operations",
            },
        ],
        "initial_budget": {"fetches": 8, "searches": 8},
        "retrieval_policy": {"exact_marker_query": "CCR28H", "maximum_results": 1, "scope": "operations"},
        "schema_id": "pump-station-temporal-evidence-template.v1",
        "station_data_profile_id": "AU-NSW-LH-SYN-SPS-v2",
        "template_id": "pump-station-asw-8-rs1-temporal-template.v1",
    }
    descriptor: dict[str, Any] = {
        "actor_interface_version": "pump-station.actor.v2",
        "actor_observation_schema": "pump-station.actor-view.v4",
        "actor_projection_policy": "pump-station-current-state.v5",
        "controller_id": "pump-station-asw-8-reference-controller.v1",
        "descriptor_id": "pump-station-reference-system.asw-8-rs1.v1",
        "evaluation_version": "stewardship-evaluation.v2",
        "event_schedule": {"content_sha256": _sha(schedule), "id": schedule["event_schedule_id"]},
        "harbor_versions": {
            "export": "aecbench.pump-station-harbor-export.v2",
            "run": "aecbench.pump-station-harbor-run.v2",
            "verification": "aecbench.pump-station-harbor-verification.v2",
        },
        "information_boundary": "pump-station-actor-view.v4",
        "opening_state": {"content_sha256": _sha(opening), "id": opening["specification_id"]},
        "record_versions": {
            "authority_policy": "pump-station-authority-policy.v4",
            "receipt": "pump-station-transition-receipt.v4",
            "snapshot": "pump-station-state-snapshot.v4",
            "state": "pump-station-stewardship-state.v4",
            "transition_rules": "pump-station-transition-rules.v4",
            "world_manifest": "pump-station-world-run.v2",
        },
        "schema_id": "pump-station-reference-system-descriptor.v1",
        "station_data": {
            "package_content_id": "79eac8f916a15fe7463eba5faf44edeb8776ce79dc3fe7bd8b2cb1574988b1c1",
            "profile_id": "AU-NSW-LH-SYN-SPS-v2",
        },
        "task_world_id": "wastewater-pump-station-stewardship.v1",
        "temporal_template": {
            "builder_id": temporal["builder_id"],
            "content_sha256": _sha(temporal),
            "id": temporal["template_id"],
        },
        "verification_version": "pump-station-verification-report.v2",
    }
    return {
        "descriptor.json": descriptor,
        "event-schedule.json": schedule,
        "initial-state.json": opening,
        "temporal-template.json": temporal,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    for name, value in build_artifacts().items():
        (args.output_root / name).write_bytes(_canonical(value))


if __name__ == "__main__":
    main()
