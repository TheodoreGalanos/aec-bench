# Bedrock agent attempt

Theo approved any required LLM or Bedrock inference for the ASW-7B check. The
host attempted one four-turn tool-loop session with
`au.anthropic.claude-sonnet-4-6` on 2026-08-02.

Amazon Bedrock rejected the first call with HTTP 403 and
`UnrecognizedClientException`. The default security token was invalid. The
separate `BedrockViewer-831926582066` SSO profile was also expired and could not
refresh.

Exact captured usage:

| Measure | Value |
| --- | ---: |
| Provider calls attempted | 1 |
| Model turns completed | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Cache read tokens | 0 |
| Cache write tokens | 0 |

The host had already created the isolated child and applied the declared
treatment. Replay verification remained valid, the parent remained unchanged,
and the five-token privacy scan passed. Because no model inference occurred,
this attempt does not support an agent-behaviour claim.

The captured attempt ran before the final provider-free gate found and repaired
the event-schedule digest profile. Its stored lineage therefore keeps the
version 2 tuple digest. The final implementation binds the complete schedule
with the parent state record profile, and the focused rollout-control tests
prove the corrected version 3 digest. The failed attempt was not regenerated.
