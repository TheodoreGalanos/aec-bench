# ABOUTME: Specifies deterministic W2 SWMM input rendering from canonical requests and original W1 cases.
# ABOUTME: Verifies exact sections, identifiers, settings, quantization, case expansion, and byte stability.

from __future__ import annotations

from pathlib import Path

from generator import rendering, request

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)
ENGINE_IDENTITY = {
    "build_receipt_sha256": "1" * 64,
    "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
    "executable_sha256": "2" * 64,
    "output_library_sha256": "3" * 64,
    "patch_sha256": "522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894",
    "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
    "settings_id": "asw-0b5.swmm-settings.v3",
    "solver_library_sha256": "4" * 64,
    "version": "5.2.4",
}


def build(case_id: str) -> dict[str, object]:
    raw = request.build_anchor_request(
        authority_bytes=W1_DECLARATION.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        case_id=case_id,
        engine_identity=ENGINE_IDENTITY,
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
    )
    return request.read_request(raw)


def test_forced_case_renders_exact_sections_settings_elements_and_curves() -> None:
    rendered = rendering.render_case(build("G21_OBSTRUCTION_TRIGGER"))

    assert len(rendered) == 1
    segment = rendered[0]
    text = segment.input_bytes.decode("ascii")
    assert rendering.section_names(segment.input_bytes) == rendering.ALLOWED_SECTIONS
    assert "\t" not in text
    assert not any(line.endswith(" ") for line in text.splitlines())
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "FLOW_UNITS LPS" in text
    assert "FLOW_ROUTING DYNWAVE" in text
    assert "FORCE_MAIN_EQUATION D-W" in text
    assert "ROUTING_STEP 00:00:01" in text
    assert "REPORT_STEP 00:00:01" in text
    assert "HEAD_TOLERANCE 0.0000001" in text
    assert "MAX_TRIALS 50" in text
    assert "END_TIME 0.03347222222222222222222222222222222" in text
    assert "THREADS 1" in text
    assert "WW_B4" in text
    assert "O_HGL_A 0.000000000 FIXED 8.400000000 NO" in text
    assert "O_HGL_B 0.000000000 FIXED 8.400000000 NO" in text
    assert "L_PA WW_B4 O_HGL_A C_EA ON 0.000000000 0.000000000" in text
    assert "L_PB WW_B4 O_HGL_B C_EB OFF 0.000000000 0.000000000" in text
    assert sum(line.startswith("C_EA ") for line in text.splitlines()) == 33
    assert sum(line.startswith("C_EB ") for line in text.splitlines()) == 33
    for forbidden in ("J_DIS", "L_FM", "C_PA", "C_PB"):
        assert forbidden not in text
    assert segment.input_sha256 == rendering.sha256_bytes(segment.input_bytes)
    assert (
        segment.pump_a_original_curve_sha256
        != segment.pump_b_original_curve_sha256
    )
    assert segment.pump_a_engine_curve_sha256 != segment.pump_b_engine_curve_sha256


def test_automatic_cases_mirror_labels_without_changing_clean_curve_bytes() -> None:
    pump_a = rendering.render_case(build("G10_CLEAN_A_BASE"))[0]
    pump_b = rendering.render_case(build("G11_CLEAN_B_BASE"))[0]

    assert (
        pump_a.pump_a_original_curve_sha256
        == pump_a.pump_b_original_curve_sha256
    )
    assert (
        pump_a.pump_a_engine_curve_sha256
        == pump_a.pump_b_engine_curve_sha256
    )
    assert (
        pump_a.pump_a_engine_curve_sha256
        == pump_b.pump_a_engine_curve_sha256
    )
    assert b"L_PA WW_B4 O_HGL_A C_EA OFF 1.650000000 0.750000000" in pump_a.input_bytes
    assert b"L_PB WW_B4 O_HGL_B C_EB OFF 0.000000000 0.000000000" in pump_a.input_bytes
    assert b"L_PA WW_B4 O_HGL_A C_EA OFF 0.000000000 0.000000000" in pump_b.input_bytes
    assert b"L_PB WW_B4 O_HGL_B C_EB OFF 1.650000000 0.750000000" in pump_b.input_bytes
    assert sum(line.startswith(b"TS_IN ") for line in pump_a.input_bytes.splitlines()) == 10


def test_catalogue_expands_to_exact_engine_segment_inventory() -> None:
    counts = {
        case_id: len(rendering.render_case(build(case_id), carried_depth_m="1.500000000"))
        for case_id in request.CASE_IDS
    }

    assert counts == {
        **{case_id: 1 for case_id in request.CASE_IDS if case_id not in {"G70_TRANSFER", "G80_NO_MAINTENANCE"}},
        "G70_TRANSFER": 2,
        "G80_NO_MAINTENANCE": 4,
    }


def test_same_request_renders_byte_identically() -> None:
    case = build("G40_COMBINED_HALF")

    first = rendering.render_case(case)[0]
    second = rendering.render_case(case)[0]

    assert first.input_bytes == second.input_bytes
    assert first.input_sha256 == second.input_sha256
    assert (
        first.pump_a_original_curve_sha256
        == second.pump_a_original_curve_sha256
    )
    assert (
        first.pump_b_original_curve_sha256
        == second.pump_b_original_curve_sha256
    )
    assert first.pump_a_engine_curve_sha256 == second.pump_a_engine_curve_sha256
    assert first.pump_b_engine_curve_sha256 == second.pump_b_engine_curve_sha256


def test_diagnostic_configuration_changes_only_declared_engine_inputs() -> None:
    case = build("G21_OBSTRUCTION_TRIGGER")

    coarse = rendering.render_case(
        case,
        configuration=rendering.EngineConfiguration(
            curve_segments=16,
        ),
    )[0]
    report_two = rendering.render_case(
        case,
        configuration=rendering.EngineConfiguration(
            report_step_s=2,
        ),
    )[0]
    route_two = rendering.render_case(
        case,
        configuration=rendering.EngineConfiguration(
            report_step_s=2,
            routing_step_s=2,
            rule_step_s=2,
        ),
    )[0]

    assert sum(
        line.startswith(b"C_EA ")
        for line in coarse.input_bytes.splitlines()
    ) == 17
    assert b"REPORT_STEP 00:00:02" in report_two.input_bytes
    assert b"ROUTING_STEP 00:00:01" in report_two.input_bytes
    assert b"WET_STEP 00:00:01" in report_two.input_bytes
    assert b"REPORT_STEP 00:00:02" in route_two.input_bytes
    assert b"ROUTING_STEP 00:00:02" in route_two.input_bytes
    assert b"WET_STEP 00:00:02" in route_two.input_bytes
    assert report_two.report_step_s == 2
    assert route_two.routing_step_s == 2


def test_outfall_diagnostics_preserve_names_but_change_declared_mapping() -> None:
    case = build("G21_OBSTRUCTION_TRIGGER")

    order_swap = rendering.render_case(
        case,
        configuration=rendering.EngineConfiguration(
            target_mapping="outfall-order-swap",
        ),
    )[0].input_bytes
    target_swap = rendering.render_case(
        case,
        configuration=rendering.EngineConfiguration(
            target_mapping="outfall-target-swap",
        ),
    )[0].input_bytes

    assert order_swap.index(b"O_HGL_B ") < order_swap.index(b"O_HGL_A ")
    assert b"L_PA WW_B4 O_HGL_A C_EA ON" in order_swap
    assert b"L_PA WW_B4 O_HGL_B C_EA ON" in target_swap
    assert b"L_PB WW_B4 O_HGL_A C_EB OFF" in target_swap
