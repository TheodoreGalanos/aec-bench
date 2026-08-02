# ABOUTME: Records the authorised ASW-8 Bedrock actor journey and its bounded meaning.
# ABOUTME: Separates model behaviour evidence from provider-free mechanism proof.

# ASW-8 bounded agent journey

Date: 2026-08-02

## Boundary

Theo approved sending the synthetic pump-station projection and closed tool
exchanges to Amazon Bedrock model `au.anthropic.claude-sonnet-4-6`. The run had
a maximum of four model turns and permitted no more than one stewardship
action. It was a behaviour and usability check, not a model study.

No credentials, client data, latent pump condition, hidden events, private
branch data, or verifier expectations entered the model-visible transcript.

## Result

| Measure | Result |
| --- | --- |
| Adapter status | completed |
| Model turns | 3 of 4 |
| Input tokens | 14,154 |
| Output tokens | 1,464 |
| Cache-read tokens | 7,362 |
| Cache-write tokens | 6,787 |
| World transitions | 1 |
| Replay | valid |
| Actor-proposal integrity | valid |
| Host-control integrity | valid |
| Conservation | all four sections valid |
| Model-visible secret and latent-field scan | passed |

The model read the named pump-boundary and pump-availability records. It
correctly distinguished run eligibility from assured outage-planning capacity:
Pump A was run-eligible but restricted, Pump B was isolated, and Pump C was the
only assured pump.

It requested post-maintenance verification for Pump A with the exact pump and
backlog identities. Its natural-language reason linked the active run-in
restriction, the later two-SCU service interval, current resource availability,
and the visible due limits. The host permitted and applied the request.

The durable `RequestVerification` record contains the exact actor tenure,
sequence, actor-view identity, information-set identity, request identity, and
reason. Independent reload and replay reproduced the same transition.

## Evaluation meaning

The task reward is `0.0`, and terminal stewardship is false. This is expected.
The prompt required the model to take at most one action and stop. It started
verification but did not advance time, complete the work, release restrictions,
or close the opening liabilities. The result therefore checks bounded decision
quality and interface usability. It is not a terminal station run.

## Artifacts

The complete evidence set is under
`results/bedrock-agent-journey/`. It includes the trajectory, model output,
token record, immutable actor request, typed proposal, world generations,
verification report, evaluation, semantic outcome, temporal verification, and
artifact inventory.
