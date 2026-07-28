# ABOUTME: Specifies the W3-W5 controller's generation declaration and receipt chain.
# ABOUTME: Keeps orchestration evidence content-addressed without making research paths canonical.

from pathlib import Path

import run_w3_w5
from certifier import boundary as certifier_boundary
from generator import boundary as generator_boundary
from generator import request
from lineage import receipts

B5_ROOT = Path(__file__).parents[2]
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"
W2_CATALOGUE = B5_ROOT / "declarations" / "w2-case-catalogue.json"
W2_W4_REPAIR = B5_ROOT / "declarations" / "w2-w4-engine-mapping-repair.json"
C_R07_AMENDMENT = B5_ROOT / "declarations" / "w4-c-r07-composition-amendment.json"
W4_AMENDMENT = B5_ROOT / "declarations" / "w4-c-r08-ceiling-amendment.json"
C_R02_AMENDMENT = (
    B5_ROOT / "declarations" / "w4-c-r02-routing-integration-amendment.json"
)
SOLVER_CONVERGENCE = (
    B5_ROOT / "declarations" / "solver-convergence-amendment.json"
)
CONTROL_EDGE_AMENDMENT = (
    B5_ROOT / "declarations" / "control-edge-trajectory-amendment.json"
)
FAMILY_SELECTION_AMENDMENT = (
    B5_ROOT
    / "declarations"
    / "family-member-selection-amendment.json"
)
V1_GENERATION = (
    B5_ROOT / "results" / "v3-refusal" / "generation-declaration.json"
)
V2_GENERATION = (
    B5_ROOT
    / "results"
    / "v3-c-r02-refusal"
    / "generation-declaration.json"
)


def _engine_identity() -> dict[str, str]:
    return {
        "build_receipt_sha256": "1" * 64,
        "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
        "executable_sha256": "2" * 64,
        "output_library_sha256": "3" * 64,
        "patch_sha256": ("522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894"),
        "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
        "settings_id": "asw-0b5.swmm-settings.v3",
        "solver_library_sha256": "4" * 64,
        "version": "5.2.4",
    }


def test_generation_declaration_is_accepted_by_both_independent_readers() -> None:
    raw = run_w3_w5.build_generation_declaration(
        authority_bytes=W1_DECLARATION.read_bytes(),
        c_r02_amendment_bytes=C_R02_AMENDMENT.read_bytes(),
        c_r07_amendment_bytes=C_R07_AMENDMENT.read_bytes(),
        c_r08_amendment_bytes=W4_AMENDMENT.read_bytes(),
        catalogue_bytes=W2_CATALOGUE.read_bytes(),
        control_edge_amendment_bytes=CONTROL_EDGE_AMENDMENT.read_bytes(),
        family_selection_amendment_bytes=(
            FAMILY_SELECTION_AMENDMENT.read_bytes()
        ),
        repair_bytes=W2_W4_REPAIR.read_bytes(),
        solver_convergence_bytes=SOLVER_CONVERGENCE.read_bytes(),
        engine_identity=_engine_identity(),
        generator_source_id="5" * 64,
        certifier_source_id="6" * 64,
        sensitivity_source_id="7" * 64,
    )

    generator_value = generator_boundary.read_generation_declaration(raw)
    certifier_value = certifier_boundary.read_generation_declaration(raw)

    assert generator_value == certifier_value
    assert generator_boundary.world_generation_id(raw) == (certifier_boundary.world_generation_id(raw))
    assert (
        generator_value["member_content_id"] == request.anchor_member(W1_DECLARATION.read_bytes())["member_content_id"]
    )
    assert generator_value["schema_id"] == "asw-0b5.generation-declaration.v5"
    assert generator_value["authorities"][-6:] == [
        {
            "role": "w4-c-r07-amendment",
            "sha256": (
                "488c82d09696472533669f21017c19cd4156952f4d075b278de91b580bf2cbf2"
            ),
        },
        {
            "role": "w4-c-r08-amendment",
            "sha256": (
                "047576621781aa294b8251be433b9dba7c2efd66ffe759e633d67f26960d9a65"
            ),
        },
        {
            "role": "w4-c-r02-routing-integration-amendment",
            "sha256": (
                "d6ada0600f06d5aedd3298882f4e1fdab815eeddc15edc06eb3bc222d60979c5"
            ),
        },
        {
            "role": "solver-convergence-amendment",
            "sha256": (
                "583efcc11501bbe4a07dce8de5c50ae2c6c8dd72d9af76a29eff7ebc47f39859"
            ),
        },
        {
            "role": "control-edge-trajectory-amendment",
            "sha256": (
                "161ae844049b6f7956b122827c693b59b68f99adc574af8f54454270f66ccc2a"
            ),
        },
        {
            "role": "family-member-selection-amendment",
            "sha256": (
                "594e507ee5e8e783c80137512bfb918bbc91e5a00692465be0a5c5739b2b1ba5"
            ),
        },
    ]


def test_predecessor_generation_declarations_remain_reloadable() -> None:
    for path in (V1_GENERATION, V2_GENERATION):
        raw = path.read_bytes()

        assert generator_boundary.read_generation_declaration(raw) == (
            certifier_boundary.read_generation_declaration(raw)
        )


def test_rejected_receipt_chain_is_complete_connected_and_stage_ordered() -> None:
    chain = run_w3_w5.build_rejection_receipt_chain(
        generation_id="0" * 64,
        engine_build_content_id="1" * 64,
        generator_bundle_content_id="2" * 64,
        certifier_result_content_id="3" * 64,
        composition_result_content_id="4" * 64,
        analytical_inventory_content_id="5" * 64,
        family_result_content_id="6" * 64,
        promotion_decision_content_id="7" * 64,
    )

    receipts.validate_receipt_graph(chain)
    assert [item.envelope["receipt_kind"] for item in chain] == [
        "generation-declaration",
        "engine-build",
        "generator-case",
        "certifier-case",
        "w4-case",
        "sensitivity-member",
        "family-decision",
        "promotion-decision",
    ]
    assert chain[-1].envelope["terminal_state"] == ("promotion-generation-reject")
    assert all(item.envelope["promotable"] is False for item in chain)
