ABOUTME: Example LLM reviewer response for the AEC-Bench-shaped verifier event fixture.
ABOUTME: Shows the structured JSON expected by the provider-neutral review CLI.

```json
{
  "status": "complete",
  "reviewed_modes": [
    "verifier_result",
    "output_artifacts",
    "trace",
    "source_authority",
    "contradiction_ledger"
  ],
  "findings": [
    {
      "id": "agentic_review_verifier_language_gap",
      "category": "verifier_language_gap",
      "evidence_refs": [
        "score.passed",
        "artifacts.rewrite_integrity_report",
        "validator.rewrite_integrity_report",
        "contradictions.score_artifact_contradiction"
      ],
      "affected_claims": [
        "task_outcome",
        "verifier_correctness",
        "world_success_semantics"
      ],
      "confidence": 0.95,
      "proposed_next_action": "repair_verifier_and_replay_world",
      "repair_targets": [
        "verifier",
        "world_schema",
        "evidence_profile"
      ]
    }
  ]
}
```
