# ABOUTME: Executes canonical W1 cases through fresh pinned-SWMM workspaces and assembles semantic candidates.
# ABOUTME: Owns real-engine orchestration, G70 carry, artifact identities, and exact two-workspace replay only.

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, cast

from generator import (
    diagnostics,
    engine,
    output,
    rendering,
    request,
    semantic,
    solver,
)

CASE_RESULT_DOMAIN = b"asw-0b5.generator-case-result.v1\0"
RUN_SET_DOMAIN = b"asw-0b5.generator-run-set.v1\0"
CARRY_DOMAIN = b"asw-0b4.g70-carry.v1\0"
HEAD_QUANTUM = Decimal("0.000000001")


class ExecutionError(RuntimeError):
    """Raised when a real W1 generation or replay gate fails."""


@dataclass(frozen=True)
class _EnginePaths:
    output_library: Path
    solver_library: Path


def _verified_engine_paths(receipt_path: Path) -> _EnginePaths:
    receipt_path = receipt_path.resolve()
    receipt = engine.verify_build_receipt(receipt_path)
    artifacts = cast(dict[str, dict[str, str]], receipt["artifacts"])
    return _EnginePaths(
        output_library=receipt_path.parent
        / artifacts["output_library"]["relative_path"],
        solver_library=receipt_path.parent
        / artifacts["solver_library"]["relative_path"],
    )


def _member_values(member: dict[str, Any]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if not isinstance(value, bool):
            values[parameter["identity"]] = Decimal(str(value))
    return values


def _curve_evidence(segment: rendering.RenderedSegment) -> dict[str, str]:
    return {
        "pump_a_engine_curve_sha256": segment.pump_a_engine_curve_sha256,
        "pump_a_original_curve_sha256": segment.pump_a_original_curve_sha256,
        "pump_b_engine_curve_sha256": segment.pump_b_engine_curve_sha256,
        "pump_b_original_curve_sha256": segment.pump_b_original_curve_sha256,
    }


def _write_curve_evidence(
    workspace: Path,
    segment: rendering.RenderedSegment,
) -> None:
    artifacts = (
        ("pump-a-engine-curve.json", segment.pump_a_engine_curve_bytes),
        ("pump-a-original-curve.json", segment.pump_a_original_curve_bytes),
        ("pump-b-engine-curve.json", segment.pump_b_engine_curve_bytes),
        ("pump-b-original-curve.json", segment.pump_b_original_curve_bytes),
    )
    for name, raw in artifacts:
        path = workspace / name
        engine.require_absent(path)
        path.write_bytes(raw)


def _validate_setting_trace(
    *,
    case: dict[str, Any],
    segment: rendering.RenderedSegment,
    run: solver.SolverRun,
) -> dict[str, list[int]]:
    full_pump_a = list(run.pump_a_settings)
    full_pump_b = list(run.pump_b_settings)
    expected_steps = segment.horizon_s // segment.routing_step_s
    if (
        len(full_pump_a) != expected_steps
        or len(full_pump_b) != expected_steps
    ):
        raise ExecutionError("setting trace and routing grid differ")
    if any(
        a and b
        for a, b in zip(full_pump_a, full_pump_b, strict=True)
    ):
        raise ExecutionError("simultaneous pumping is forbidden")
    selected = segment.selected_pump
    mode = case["control_mode"]
    if selected == "none":
        if any(full_pump_a) or any(full_pump_b):
            raise ExecutionError("forced-off case contains an active pump")
    elif selected == "pump-a":
        if any(full_pump_b):
            raise ExecutionError("Pump B is active under Pump A assignment")
        if mode != "automatic" and full_pump_a != [1] * expected_steps:
            raise ExecutionError("forced Pump A setting trace differs")
        if mode == "automatic" and not any(full_pump_a):
            raise ExecutionError("automatic Pump A never starts")
    elif selected == "pump-b":
        if any(full_pump_a):
            raise ExecutionError("Pump A is active under Pump B assignment")
        if mode != "automatic" and full_pump_b != [1] * expected_steps:
            raise ExecutionError("forced Pump B setting trace differs")
        if mode == "automatic" and not any(full_pump_b):
            raise ExecutionError("automatic Pump B never starts")
    else:
        raise ExecutionError(f"unknown segment assignment {selected!r}")
    ratio = segment.report_step_s // segment.routing_step_s
    if (
        segment.report_step_s % segment.routing_step_s != 0
        or ratio <= 0
    ):
        raise ExecutionError("report and routing grids do not align")
    return {
        "pump_a": full_pump_a[ratio - 1 :: ratio],
        "pump_b": full_pump_b[ratio - 1 :: ratio],
    }


def _semantic_series(
    *,
    extracted: dict[str, Any],
    request_value: dict[str, Any],
    setting_trace: dict[str, list[int]],
) -> dict[str, dict[str, Any]]:
    raw = cast(dict[str, list[float]], extracted["series"])
    pump_a_m3_s = [
        semantic.scale_lps_to_m3_s(value) for value in raw["pump_a_flow_lps"]
    ]
    pump_b_m3_s = [
        semantic.scale_lps_to_m3_s(value) for value in raw["pump_b_flow_lps"]
    ]
    force_main = [
        semantic.round_binary32(a + b)
        for a, b in zip(pump_a_m3_s, pump_b_m3_s, strict=True)
    ]
    period_count = cast(int, extracted["period_count"])
    report_step_s = cast(int, extracted["report_step_seconds"])
    z_d = float(_member_values(request_value["member"])["system.z_d"])
    available: dict[str, dict[str, Any]] = {
        "time_s": semantic.integer_series(
            range(
                report_step_s,
                report_step_s * period_count + 1,
                report_step_s,
            ),
            source="independent-report-grid",
            unit="s",
        ),
        "wet_well_depth_m": semantic.binary32_series(
            raw["wet_well_depth_m"],
            source="WW_B4:SMO_invert_depth",
            unit="m",
        ),
        "wet_well_volume_m3": semantic.binary32_series(
            raw["wet_well_volume_m3"],
            source="WW_B4:SMO_stored_ponded_volume",
            unit="m³",
        ),
        "wet_well_inflow_m3_s": semantic.binary32_series(
            raw["wet_well_inflow_lps"],
            source="WW_B4:SMO_lateral_inflow",
            unit="m³/s",
            scale_lps=True,
        ),
        "wet_well_overflow_m3_s": semantic.binary32_series(
            raw["wet_well_overflow_lps"],
            source="WW_B4:SMO_flooding_losses",
            unit="m³/s",
            scale_lps=True,
        ),
        "pump_a_flow_m3_s": semantic.binary32_series(
            raw["pump_a_flow_lps"],
            source="L_PA:SMO_flow_rate_link",
            unit="m³/s",
            scale_lps=True,
        ),
        "pump_b_flow_m3_s": semantic.binary32_series(
            raw["pump_b_flow_lps"],
            source="L_PB:SMO_flow_rate_link",
            unit="m³/s",
            scale_lps=True,
        ),
        "force_main_flow_m3_s": semantic.binary32_series(
            force_main,
            source="derived:binary32-pump-flow-sum",
            unit="m³/s",
        ),
        "pump_a_setting": semantic.integer_series(
            setting_trace["pump_a"],
            source="solver-step:L_PA:swmm_LINK_SETTING",
            unit="1",
        ),
        "pump_b_setting": semantic.integer_series(
            setting_trace["pump_b"],
            source="solver-step:L_PB:swmm_LINK_SETTING",
            unit="1",
        ),
        "wet_well_head_m": semantic.binary32_series(
            raw["wet_well_head_m"],
            source="WW_B4:SMO_hydraulic_head",
            unit="m",
        ),
        "discharge_head_m": semantic.binary32_series(
            [z_d] * period_count,
            source="derived:fixed-HGL:system.z_d",
            unit="m",
        ),
    }
    ordered: dict[str, dict[str, Any]] = {}
    for identity in request_value["outputs"]:
        if identity not in available:
            raise ExecutionError(f"semantic output {identity!r} has no extraction rule")
        ordered[identity] = available[identity]
    return ordered


def _execute_segment(
    *,
    request_value: dict[str, Any],
    segment: rendering.RenderedSegment,
    paths: _EnginePaths,
    workspace: Path,
    carry: dict[str, Any] | None,
) -> dict[str, Any]:
    workspace = workspace.resolve()
    engine.require_absent(workspace)
    workspace.mkdir(parents=True)
    input_path = workspace / "case.inp"
    report_path = workspace / "case.rpt"
    output_path = workspace / "case.out"
    input_path.write_bytes(segment.input_bytes)
    _write_curve_evidence(workspace, segment)
    solver_run = solver.run_lifecycle(
        input_path=input_path,
        report_path=report_path,
        output_path=output_path,
        solver_library=paths.solver_library,
        expected_steps=segment.horizon_s // segment.routing_step_s,
    )
    normalized_diagnostics = diagnostics.parse_report_bytes(report_path.read_bytes())
    extracted = output.extract_output(
        output_path=output_path,
        output_library=paths.output_library,
        expected_periods=segment.horizon_s // segment.report_step_s,
        expected_report_step_s=segment.report_step_s,
    )
    setting_trace = _validate_setting_trace(
        case=request_value["case"],
        segment=segment,
        run=solver_run,
    )
    setting_trace_bytes = request.canonical_json_bytes(setting_trace)
    setting_trace_path = workspace / "pump-settings.json"
    setting_trace_path.write_bytes(setting_trace_bytes)
    curve_evidence = _curve_evidence(segment)
    semantic_value: dict[str, Any] = {
        "authority": {
            "profile_id": request_value["authority"]["profile_id"],
            "protocol_id": request_value["authority"]["protocol_id"],
            "repair_declaration_sha256": request.MAPPING_REPAIR_SHA256,
            "scope": "research-private",
        },
        "carry": [] if carry is None else [carry],
        "case_content_id": request_value["case"]["case_content_id"],
        "curve_evidence": curve_evidence,
        "diagnostics": normalized_diagnostics,
        "engine": request_value["engine"],
        "engine_output": {
            "flow_units_code": extracted["flow_units_code"],
            "link_names": extracted["link_names"],
            "node_names": extracted["node_names"],
            "output_api_version": extracted["output_api_version"],
            "project_size": extracted["project_size"],
            "report_step_seconds": extracted["report_step_seconds"],
        },
        "lifecycle_return_codes": solver_run.lifecycle_return_codes,
        "member_content_id": request_value["member"]["member_content_id"],
        "period_count": extracted["period_count"],
        "promotable": False,
        "rendered_input_sha256": segment.input_sha256,
        "schema_id": "asw-0b5.semantic-output.v1",
        "segment_id": segment.segment_id,
        "series": _semantic_series(
            extracted=extracted,
            request_value=request_value,
            setting_trace=setting_trace,
        ),
        "setting_trace_sha256": hashlib.sha256(setting_trace_bytes).hexdigest(),
        "status": "candidate-only",
    }
    semantic_bytes = semantic.semantic_bytes(semantic_value)
    semantic_path = workspace / "semantic.json"
    semantic_path.write_bytes(semantic_bytes)
    return {
        "curve_bytes": {
            "pump-a-engine": segment.pump_a_engine_curve_bytes,
            "pump-a-original": segment.pump_a_original_curve_bytes,
            "pump-b-engine": segment.pump_b_engine_curve_bytes,
            "pump-b-original": segment.pump_b_original_curve_bytes,
        },
        "curve_evidence": curve_evidence,
        "diagnostics": normalized_diagnostics,
        "input_sha256": segment.input_sha256,
        "period_count": extracted["period_count"],
        "raw_binary_sha256": engine.sha256_file(output_path),
        "raw_report_sha256": engine.sha256_file(report_path),
        "segment_id": segment.segment_id,
        "semantic": semantic_value,
        "semantic_bytes": semantic_bytes,
        "semantic_output_sha256": semantic.semantic_sha256(semantic_value),
        "setting_trace": setting_trace,
        "setting_trace_sha256": hashlib.sha256(setting_trace_bytes).hexdigest(),
    }


def _carry_record(segment_a: dict[str, Any]) -> tuple[dict[str, Any], str]:
    depth_series = segment_a["semantic"]["series"]["wet_well_depth_m"]
    carry_hex = depth_series["values"][-1]
    carry_value = semantic.binary32_from_hex(carry_hex)
    carried_text = format(
        Decimal.from_float(carry_value).quantize(
            HEAD_QUANTUM,
            rounding=ROUND_HALF_EVEN,
        ),
        ".9f",
    )
    if semantic.binary32_hex(float(carried_text)) != carry_hex:
        raise ExecutionError("G70 carried depth cannot be rendered without binary32 drift")
    record: dict[str, Any] = {
        "representation": "ieee754-binary32-be-hex",
        "source": "segment-a:wet_well_depth_m:last",
        "value": carry_hex,
    }
    record["sha256"] = hashlib.sha256(
        CARRY_DOMAIN + request.canonical_json_bytes(record)
    ).hexdigest()
    return record, carried_text


def _case_result_identity(
    *,
    case_id: str,
    segments: list[dict[str, Any]],
    carry: dict[str, Any] | None,
) -> str:
    payload = {
        "carry": [] if carry is None else [carry],
        "case_id": case_id,
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "semantic_output_sha256": segment["semantic_output_sha256"],
            }
            for segment in segments
        ],
    }
    return hashlib.sha256(
        CASE_RESULT_DOMAIN + request.canonical_json_bytes(payload)
    ).hexdigest()


def _execute_case_with_paths(
    request_value: dict[str, Any],
    *,
    paths: _EnginePaths,
    workspace: Path,
    configuration: rendering.EngineConfiguration = (
        rendering.DEFAULT_ENGINE_CONFIGURATION
    ),
) -> dict[str, Any]:
    workspace = workspace.resolve()
    engine.require_absent(workspace)
    workspace.mkdir(parents=True)
    case_id = cast(str, request_value["case"]["case_id"])
    rendered = rendering.render_case(
        request_value,
        configuration=configuration,
    )
    segments = [
        _execute_segment(
            request_value=request_value,
            segment=rendered[0],
            paths=paths,
            workspace=workspace / rendered[0].segment_id,
            carry=None,
        )
    ]
    carry: dict[str, Any] | None = None
    if request_value["case"]["family"] == "transfer-sequence":
        carry, carried_text = _carry_record(segments[0])
        complete = rendering.render_case(
            request_value,
            carried_depth_m=carried_text,
            configuration=configuration,
        )
        if len(complete) != 2 or complete[0].input_sha256 != rendered[0].input_sha256:
            raise ExecutionError("G70 segment-A replay changed while rendering carry")
        segments.append(
            _execute_segment(
                request_value=request_value,
                segment=complete[1],
                paths=paths,
                workspace=workspace / complete[1].segment_id,
                carry=carry,
            )
        )
    else:
        for segment in rendered[1:]:
            segments.append(
                _execute_segment(
                    request_value=request_value,
                    segment=segment,
                    paths=paths,
                    workspace=workspace / segment.segment_id,
                    carry=None,
                )
            )
    return {
        "carry": carry,
        "case_id": case_id,
        "case_result_sha256": _case_result_identity(
            case_id=case_id,
            segments=segments,
            carry=carry,
        ),
        "request_bytes": request.canonical_json_bytes(request_value),
        "segments": segments,
    }


def execute_case(
    request_value: dict[str, Any],
    *,
    receipt_path: Path,
    workspace: Path,
) -> dict[str, Any]:
    """Execute one validated canonical W1 case in a new real-engine workspace."""
    return _execute_case_with_paths(
        request_value,
        paths=_verified_engine_paths(receipt_path),
        workspace=workspace,
    )


def _flatten(
    replay: dict[str, Any],
    case_ids: tuple[str, ...],
) -> list[dict[str, Any]]:
    return [
        segment
        for case_id in case_ids
        for segment in replay["cases"][case_id]["segments"]
    ]


def _run_set_sha256(
    cases: dict[str, Any],
    case_ids: tuple[str, ...],
) -> str:
    payload = {
        "case_ids": list(case_ids),
        "case_results": [
            {
                "case_id": case_id,
                "case_result_sha256": cases[case_id]["case_result_sha256"],
            }
            for case_id in case_ids
        ],
    }
    return hashlib.sha256(
        RUN_SET_DOMAIN + request.canonical_json_bytes(payload)
    ).hexdigest()


def _validate_case_ids(case_ids: tuple[str, ...]) -> None:
    if (
        not case_ids
        or len(set(case_ids)) != len(case_ids)
        or tuple(
            case_id
            for case_id in request.CASE_IDS
            if case_id in case_ids
        )
        != case_ids
    ):
        raise ExecutionError(
            "case map must be a non-empty W2-ordered subset"
        )


def _execute_replayed_cases(
    *,
    requests: dict[str, dict[str, Any]],
    case_ids: tuple[str, ...],
    configuration: rendering.EngineConfiguration,
    paths: _EnginePaths,
    workspace: Path,
) -> dict[str, Any]:
    replays: list[dict[str, Any]] = []
    for replay_index in range(2):
        replay_root = workspace / f"replay-{replay_index}"
        replay_root.mkdir()
        cases = {
            case_id: _execute_case_with_paths(
                requests[case_id],
                configuration=configuration,
                paths=paths,
                workspace=replay_root / case_id,
            )
            for case_id in case_ids
        }
        replays.append(
            {
                "cases": cases,
                "replay_index": replay_index,
                "run_set_sha256": _run_set_sha256(cases, case_ids),
            }
        )
    first = _flatten(replays[0], case_ids)
    second = _flatten(replays[1], case_ids)
    expected_segments = sum(
        2
        if case_id == "G70_TRANSFER"
        else 4
        if case_id == "G80_NO_MAINTENANCE"
        else 1
        for case_id in case_ids
    )
    if (
        len(first) != expected_segments
        or len(second) != expected_segments
    ):
        raise ExecutionError(
            "case map expanded to an unexpected segment count"
        )
    replay = {
        "normalized_diagnostics_equal": [
            item["diagnostics"] for item in first
        ]
        == [item["diagnostics"] for item in second],
        "raw_binary_outputs_equal": [
            item["raw_binary_sha256"] for item in first
        ]
        == [item["raw_binary_sha256"] for item in second],
        "rendered_inputs_equal": [
            item["input_sha256"] for item in first
        ]
        == [item["input_sha256"] for item in second],
        "run_set_hashes_equal": replays[0]["run_set_sha256"]
        == replays[1]["run_set_sha256"],
        "semantic_outputs_equal": [
            item["semantic_output_sha256"] for item in first
        ]
        == [
            item["semantic_output_sha256"] for item in second
        ],
        "setting_traces_equal": [
            item["setting_trace_sha256"] for item in first
        ]
        == [item["setting_trace_sha256"] for item in second],
    }
    if not all(replay.values()):
        failed = [name for name, passed in replay.items() if not passed]
        raise ExecutionError(f"catalogue replay differs: {failed!r}")
    return {
        "case_ids": list(case_ids),
        "engine_execution_count": 2 * expected_segments,
        "replay": replay,
        "replays": replays,
        "segment_count_per_replay": expected_segments,
    }


def execute_member_cases(
    *,
    authority_bytes: bytes,
    catalogue_bytes: bytes,
    case_ids: tuple[str, ...],
    member: dict[str, Any],
    receipt_path: Path,
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
    workspace: Path,
) -> dict[str, Any]:
    """Execute an ordered W2 case map twice for one validated W1 member."""
    _validate_case_ids(case_ids)
    workspace = workspace.resolve()
    engine.require_absent(workspace)
    workspace.mkdir(parents=True)
    paths = _verified_engine_paths(receipt_path)
    engine_identity = engine.request_engine_identity(receipt_path)
    requests = {
        case_id: request.read_request(
            request.build_member_request(
                authority_bytes=authority_bytes,
                catalogue_bytes=catalogue_bytes,
                case_id=case_id,
                engine_identity=engine_identity,
                member=member,
                repair_bytes=repair_bytes,
                solver_convergence_bytes=solver_convergence_bytes,
            ),
            authority_bytes=authority_bytes,
            catalogue_bytes=catalogue_bytes,
            repair_bytes=repair_bytes,
            solver_convergence_bytes=solver_convergence_bytes,
        )
        for case_id in case_ids
    }
    result = _execute_replayed_cases(
        requests=requests,
        case_ids=case_ids,
        configuration=rendering.EngineConfiguration(),
        paths=paths,
        workspace=workspace,
    )
    return {
        **result,
        "member_content_id": member["member_content_id"],
    }


def execute_diagnostic_cases(
    *,
    authority_bytes: bytes,
    catalogue_bytes: bytes,
    case_ids: tuple[str, ...],
    configuration: rendering.EngineConfiguration,
    receipt_path: Path,
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
    workspace: Path,
) -> dict[str, Any]:
    """Execute one bounded engine diagnostic twice for the anchor member."""
    _validate_case_ids(case_ids)
    workspace = workspace.resolve()
    engine.require_absent(workspace)
    workspace.mkdir(parents=True)
    paths = _verified_engine_paths(receipt_path)
    engine_identity = engine.request_engine_identity(receipt_path)
    member = request.anchor_member(authority_bytes)
    requests = {
        case_id: request.read_request(
            request.build_member_request(
                authority_bytes=authority_bytes,
                catalogue_bytes=catalogue_bytes,
                case_id=case_id,
                engine_identity=engine_identity,
                member=member,
                repair_bytes=repair_bytes,
                solver_convergence_bytes=solver_convergence_bytes,
            ),
            authority_bytes=authority_bytes,
            catalogue_bytes=catalogue_bytes,
            repair_bytes=repair_bytes,
            solver_convergence_bytes=solver_convergence_bytes,
        )
        for case_id in case_ids
    }
    result = _execute_replayed_cases(
        requests=requests,
        case_ids=case_ids,
        configuration=configuration,
        paths=paths,
        workspace=workspace,
    )
    return {
        **result,
        "configuration": {
            "curve_segments": configuration.curve_segments,
            "report_step_s": configuration.report_step_s,
            "routing_step_s": configuration.routing_step_s,
            "rule_step_s": configuration.rule_step_s,
            "target_mapping": configuration.target_mapping,
        },
        "member_content_id": member["member_content_id"],
    }


def execute_catalogue(
    *,
    authority_bytes: bytes,
    catalogue_bytes: bytes,
    receipt_path: Path,
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
    workspace: Path,
) -> dict[str, Any]:
    """Execute the anchor W2 catalogue twice with exact replay evidence."""
    return execute_member_cases(
        authority_bytes=authority_bytes,
        catalogue_bytes=catalogue_bytes,
        case_ids=request.CASE_IDS,
        member=request.anchor_member(authority_bytes),
        receipt_path=receipt_path,
        repair_bytes=repair_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
        workspace=workspace,
    )
