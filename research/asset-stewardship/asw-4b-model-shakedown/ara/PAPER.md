---
ara_schema_version: "0.1"
title: ASW-4B single-model stewardship continuity shakedown
---

# Research continuation summary

ASW-4B is one small model shakedown of the frozen stewardship-continuity
study. It uses one H2 worsening-verification history and the structured-handover
treatment. It tests the production execution and evidence path. It is not part
of the confirmatory result.

## Approved run

| Item | Approved value |
| --- | --- |
| Sample | Exactly one H2 structured-handover trajectory |
| Outcome authority | Ineligible for the confirmatory result |
| Provider | Amazon Bedrock, Australian geographic route |
| Model | `au.anthropic.claude-sonnet-4-6` |
| Adapter | `tool_loop` |
| Execution | Direct host session |
| Cache | Disabled |
| Advisor | Disabled |
| Bash | Disabled |
| Provider calls | At most 16 |
| Input tokens per call | At most 500,000 |
| Output tokens per call | At most 2,048 |
| Total tokens | At most 500,000 |
| Spend | At most USD 2.50 |
| Model decisions | At most 16 |
| Agent proposals | At most 12 |
| Host commands | At most 32 |
| Fresh handovers | Exactly one |

Theo approved these exact values on 2026-07-31 before any ASW-4B provider call.
The authority is phase-specific and bound to the exact model configuration.

## Price gate

The approved Bedrock price basis is USD 3.00 per million input tokens and USD
15.00 per million output tokens, with the Australian geographic-route premium
of 10 percent. The enforced prices are therefore USD 3.30 and USD 16.50.

The most expensive token mix allowed by the combined limits is 467,232 input
tokens and 32,768 output tokens. Its exact ceiling is USD 2.082538. This is
below the approved USD 2.50 limit.

## Real history and treatment

The history constructor uses the promoted station data, physical kernel,
operating rules, durable run repository, and direct host session. It drives the
station through inspection, obstruction clearance, functional checks,
provisional return, and provisional work-order closure.

A neutral hidden decision event then advances the station clock to exactly half
one diagnostic period after provisional closure. It changes no operating
record. At handover:

- the post-maintenance run-in limit is active;
- the independent verification duty is open;
- the work order is provisionally closed;
- the duty is 1.5 diagnostic periods from its calendar trigger; and
- one fresh tenure receives the same live current state plus bounded history.

The model does not receive the hidden evaluation-window position or future
events.

## Evidence boundary

The manifest, plan, treatment delivery, handover, world run, adapter evidence,
observation, execution record, and report are written under a host-private
evidence root. The report is recomputed from immutable evidence. The run must
record zero cache use, zero advisor calls, zero task-reward changes, and no
credential material.

The shakedown conclusion can only be `shakedown`. It cannot support, refute, or
otherwise enter the confirmatory hypothesis test.

## Current status

The provider-free controls and focused unit, integration, and end-to-end tests
pass. A Bedrock `CountTokens` preflight was denied before model inference. That
provider request is retained in the stage call account. The unsupported
preflight was disabled before the one approved model trajectory ran.

The trajectory completed with three model inference requests. Together with
the denied preflight, ASW-4B used four of the approved 16 provider requests. It
used 17,510 input tokens and 1,245 output tokens. The largest single request
used 7,751 input tokens and 592 output tokens. Exact spend was USD 0.078326.

The model read the structured handover, checked the live state, and requested
independent post-maintenance verification. It then stopped while that timed
process was still in progress. It did not advance the station to the
verification-completion event. The final state therefore has one open
verification duty and one active run-in limit. This is recorded as a
continuity failure, with no host or provider failure.

Durable world verification, the credential scan, the execution-record reload,
and independent report recomputation pass. The report conclusion is
`shakedown`; it contains zero study outcomes and zero task-reward changes. The
run does not enter the confirmatory result.
