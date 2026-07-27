# ABOUTME: Provides reusable typed output-completion evidence for boundary tests.
# ABOUTME: Keeps serialization and provenance tests aligned on one valid attestation.

from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionEvaluation,
    OutputCompletionReason,
)


def make_output_commit_attestation(
    *,
    output_path: str = "/workspace/output.md",
    commit_turn: int = 3,
) -> OutputCommitAttestation:
    """Build one valid content-addressed output-commit attestation."""
    return OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path=output_path,
        output_sha256="a" * 64,
        output_size_bytes=128,
        completion_contract_sha256="b" * 64,
        completion_evaluation=OutputCompletionEvaluation(
            complete=True,
            reason=OutputCompletionReason.COMPLETE,
            present_top_level_keys=("findings", "summary"),
            final_json_block_count=1,
        ),
        initial_output_sha256=None,
        commit_turn=commit_turn,
    )
