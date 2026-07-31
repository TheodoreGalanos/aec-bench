# Confirmatory provider authority proposal

Status: approved by Theo on 2026-07-31 before any ASW-4C provider call.

Authorization ID: `asw-4c-theo-approved-2026-07-31`.

## Fixed provider condition

| Item | Proposed value |
| --- | --- |
| Phase | Confirmatory only |
| Provider | Amazon Bedrock, Australian geographic route |
| Model | `au.anthropic.claude-sonnet-4-6` |
| Adapter | `tool_loop` |
| Execution | Direct host session |
| Cache | Disabled |
| Advisor | Disabled |
| Bash | Disabled |
| Provider `CountTokens` preflight | Disabled |
| Planned trajectories | 64 |
| Model turns per trajectory | At most 16 |
| Proposals per trajectory | At most 12 |
| Host commands per trajectory | At most 32 |
| Fresh handovers per trajectory | Exactly one |
| Provider requests for the phase | At most 1,024 |
| Input tokens per request | At most 500,000 |
| Output tokens per request | At most 2,048 |
| Total tokens per trajectory | At most 40,000 |
| Total tokens for the phase | At most 2,560,000 |
| Spend currency | USD |
| Maximum phase spend | USD 37.00 |

The Bedrock price basis is USD 3.30 per million input tokens and USD 16.50 per
million output tokens. The most expensive token mix allowed by the combined
phase limits is 462,848 input tokens and 2,097,152 output tokens. Its exact
cost is USD 36.130407, below the proposed USD 37.00 ceiling.

The ASW-4B trajectory used three model requests, 17,510 input tokens, 1,245
output tokens, and USD 0.078326. A direct 64-trajectory projection is 192
model requests, 1,120,640 input tokens, 79,680 output tokens, 1,200,320 total
tokens, and USD 5.012864. This projection is not a limit.

The host environment variables for AWS credentials and region are unset. The
standard AWS configuration, credentials, and SSO cache locations are present.
No credential value was read or retained. The runtime uses the standard
host-side AWS credential chain.

Theo accepted all values in the table with the statement: "I approve these
exact ASW-4C values." The approval applies only to this content-bound
confirmatory generation.
