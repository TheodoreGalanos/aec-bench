# ABOUTME: Tests deterministic meta-harness logic-profile evaluation inside AEC-Bench.
# ABOUTME: Covers closure, construction, containment, review, and event candidate semantics.

from __future__ import annotations

from aec_bench.meta_harness.logic_profile import evaluate_logic_profile


def test_logic_profile_certifies_complete_evidence() -> None:
    profile = {
        "closure_gates": [
            {
                "id": "verifier_available",
                "evidence_key": "verifier.reward_available",
                "expected": True,
            }
        ],
        "construction_gates": [
            {
                "id": "claim_has_witnesses",
                "construction_required": [
                    "agent.output_md",
                    "verifier.reward",
                    "verifier.details",
                ],
            }
        ],
        "containment_gates": [
            {
                "id": "artifact_disagreement",
                "when": {"key": "contradictions.artifact_disagreement", "exists": True},
                "record_key": "contradictions.artifact_disagreement",
                "required_record": ["sources", "affected_claims"],
            }
        ],
        "agentic_review": {
            "required": True,
            "review_modes": ["verifier_result", "output_artifacts"],
        },
    }
    evidence = {
        "agent": {"output_md": "Complete answer"},
        "verifier": {
            "reward_available": True,
            "reward": {"reward": 1.0},
            "details": {"passed": True},
        },
        "agentic_review": {
            "status": "complete",
            "reviewed_modes": ["verifier_result", "output_artifacts"],
            "findings": [],
        },
    }

    evaluation = evaluate_logic_profile(profile, evidence).to_dict()

    assert evaluation["overall_status"] == "certified"
    assert evaluation["closure_results"][0]["status"] == "certified"
    assert evaluation["construction_results"][0]["status"] == "proven"
    assert evaluation["containment_results"][0]["status"] == "inactive"
    assert evaluation["agentic_review_result"]["status"] == "complete"


def test_logic_profile_promotes_review_finding_to_event_candidate() -> None:
    profile = {
        "closure_gates": [],
        "construction_gates": [],
        "containment_gates": [],
        "event_triggers": [],
        "agentic_review": {"required": True, "review_modes": ["verifier_result"]},
    }
    evidence = {
        "agentic_review": {
            "status": "complete",
            "reviewed_modes": ["verifier_result"],
            "findings": [
                {
                    "id": "verifier_bug",
                    "category": "verifier_language_gap",
                    "evidence_refs": ["verifier.details"],
                    "affected_claims": ["reward"],
                    "confidence": 0.91,
                    "proposed_next_action": "Repair verifier schema.",
                }
            ],
        }
    }

    evaluation = evaluate_logic_profile(profile, evidence).to_dict()

    assert evaluation["overall_status"] == "event_candidate"
    assert evaluation["event_candidates"] == [
        {
            "id": "verifier_bug",
            "repair_targets": ["verifier", "world_schema"],
            "classification": "verifier_language_gap",
            "source": "agentic_review",
            "evidence_refs": ["verifier.details"],
            "affected_claims": ["reward"],
            "confidence": 0.91,
            "proposed_next_action": "Repair verifier schema.",
        }
    ]


def test_logic_profile_requires_complete_review_modes() -> None:
    profile = {
        "closure_gates": [],
        "construction_gates": [],
        "containment_gates": [],
        "agentic_review": {
            "required": True,
            "review_modes": ["verifier_result", "trace"],
        },
    }
    evidence = {
        "agentic_review": {
            "status": "complete",
            "reviewed_modes": ["verifier_result"],
            "findings": [],
        }
    }

    evaluation = evaluate_logic_profile(profile, evidence).to_dict()

    assert evaluation["overall_status"] == "review_required"
    assert evaluation["agentic_review_result"]["missing_modes"] == ["trace"]
