# ASW-4C token-measurement authority amendment

Status: approved by Theo on 2026-07-31 before any provider call after the
fifth started trajectory.

Authorization ID: `asw-4c-theo-token-measurement-2026-07-31`.

## Clarification

Token use is a measured analysis value. It is not a study validity gate or a
runtime stop limit. The initial 40,000-token adapter stop was too small for the
confirmatory task.

The study keeps these hard controls:

- maximum provider calls for the phase: 1,024;
- maximum phase spend: USD 37.00;
- maximum model turns per trajectory: 16;
- maximum output tokens per provider call: 2,048;
- maximum agent proposals per trajectory: 12;
- maximum host commands per trajectory: 32; and
- one fresh handover per trajectory.

Exact input tokens, output tokens, total tokens, provider calls, and estimated
spend must be retained for every trajectory and in the final analysis.

## State before the amendment

- Started trajectories: 5.
- Durable completion records: 4.
- Provider calls: 20.
- Input tokens: 111,321.
- Output tokens: 8,064.
- Total tokens: 119,385.
- Estimated spend: USD 0.500417.
- Outcome direction inspected: no.

The fifth trajectory remains a typed host fault. It will not be repeated or
replaced.
