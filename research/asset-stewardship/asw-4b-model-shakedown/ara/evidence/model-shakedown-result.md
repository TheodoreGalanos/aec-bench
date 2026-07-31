# ASW-4B model shakedown result

The one authorized H2 structured-handover trajectory completed on 2026-07-31.
It is a shakedown result only and is not eligible for the confirmatory result.

## Bound execution

| Item | Recorded value |
| --- | --- |
| Provider | Amazon Bedrock, Australian geographic route |
| Model | `au.anthropic.claude-sonnet-4-6` |
| Adapter | `tool_loop` |
| Execution | Direct host session |
| Cache | Disabled; zero read and write tokens |
| Advisor | Disabled; zero calls |
| Bash | Disabled |
| Fresh handovers | 1 |
| Stage provider requests | 4 |
| Denied preflight requests | 1 |
| Model inference requests | 3 |
| Model decisions | 3 |
| Input tokens | 17,510 |
| Output tokens | 1,245 |
| Largest input count in one request | 7,751 |
| Largest output count in one request | 592 |
| Exact spend | USD 0.078326 |
| Host commands | 3 |
| Agent proposals | 1 |

All recorded values are within the approved limits.

## Stewardship result

The model used two read-only host commands to snapshot and observe the station.
It then made one permitted proposal to request independent post-maintenance
verification for `pump-a`. The host scheduled
`process-0012-post_maintenance_verification` for completion at 8,470,800
calendar seconds.

The model stopped at 8,442,000 calendar seconds. It did not use
`continue_operation` to reach the completion event. The final state therefore
contains:

- one open duty, `obligation-0009-verification`;
- one active limit, `restriction-0009-run-in`; and
- one verification process in progress.

The observation records `continuity_failure: true`, `failure_kind: none`, and
`study_outcome_eligible: false`. The model selected the correct next action,
but it treated a scheduled future process as completed stewardship.

## Evidence identities

| Artifact | Content identity |
| --- | --- |
| Manifest | `2aa4956663fab02a21b7c8971fa44dbe007adecdb42dbcf6b8f242de3110d9bf` |
| Plan | `8e87b5632a0dc9c4d4309fe51372e388ae61fc98580cb4a7b600865b413c341d` |
| Treatment delivery | `804648bdea2aec49bd868aeb0da3ac8098a0d9c570cedfb96a8657cf82648b55` |
| Structured handover | `d112815b80a1f9f59b5588e16dac02b2c4f442394eb0a50efc7f2c45611bf5aa` |
| Start state | `76cdecd7eed4ee2214463898837b50bfb1219eb7fb6511408f5bca3a8a504f2e` |
| Final state | `da6582c75fd0ee24d0225fc2b2cfe646406e485932829f107f011cdece6dbdac` |
| Observation | `38fa1ed36a6766a8d217de3bb8895fe026cc5ff29b266a4ef2e8102937050767` |
| Execution | `bbb895adf25c31a786f2f6e3f4e343a047db8fea7e34f8f0b018ecf3187a1ad9` |
| Report | `7caa21421db08a154f8820a0d5a7c24421aa6c2a04945118282106de5115a000` |

Durable world verification passed. The host-side credential scan passed. A
separate execution-record reload returned the same execution identity, and
independent report recomputation returned the same report identity.

The report conclusion is `shakedown`. It contains zero study outcomes and zero
task-reward changes.
