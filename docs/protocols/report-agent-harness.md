# Report agent harness

| Field | Value |
| --- | --- |
| Class | Protocol |
| Status | Current |
| Audience | Task authors, adapter contributors, and experiment authors |
| Owner | Report template and agent runtime maintainers |

## Boundary and ownership

The `rlm` and `lambda-rlm` adapters share report assets, section state, public
writing checks, rubric context, and output assembly under `templates/report/`.
The guided `rlm` agent controls a persistent Python REPL. The `lambda-rlm`
adapter executes an extraction, review, and generation plan. Both use the
normal task, execution bundle, workspace, trial, and verifier paths.

A task declares the report requirements and permitted evidence. The agent
condition declares models, generation strategies, and execution limits.
Public writing checks help the actor prepare an artifact. Evaluation owns
benchmark scoring. A model review or a successful `SUBMIT()` is not a verifier
result. See the [contract index](../CONTRACTS.md) and
[architecture](../ARCHITECTURE.md).

Private verifier inputs, hidden criteria, gold answers, and other attempts'
outputs MUST NOT enter the actor workspace or any actor model request.
Only a rubric explicitly marked `visibility = "public"` is exposed by the
report loader. This filter is an additional check: the Python REPL can read
its workspace, so staging must exclude private material before execution.
The source index is not a filesystem sandbox.

## Report assets

An authored adapter file declares the template and optional asset paths:

```toml
[template]
definition = "report_template.toml"
source_mapping = "sources.toml"
validation_rules = "checks.toml"
```

The template path is relative to the adapter file, or the workspace when the
agent condition supplies configuration without a file. Source mappings,
writing rules, and explicit `[boilerplate].path` values are relative to the
template directory. Resolved paths must stay within the actor workspace;
absolute escapes and symlink escapes fail. No domain-specific filenames are
used to discover boilerplate.

Templates declare section IDs, titles, fields, dependencies, writing guidance,
source references and priorities, and optional compose blocks. Loading rejects
duplicate IDs, missing dependencies, dependency cycles, invalid field types,
malformed field declarations, unknown section or field keys, unknown source
references, and unsupported generation modes. Compose retains
verbatim, source-filled, and generated blocks with composition traces.

A source mapping declares public source IDs:

```toml
[sources.inspection]
path = "documents/inspection.txt"
visibility = "public"

[sections.findings]
sources = ["inspection"]
```

Without an explicit mapping, the loader can discover supported text files in
the actor-staged `documents/` directory. It rejects duplicate source IDs.
Explicit mappings are preferable when source authority matters. Unknown IDs
and ambiguous prefix references fail rather than selecting an arbitrary file.

Writing rules use `visibility = "public"` and a `[[rules]]` list. Each rule has
an `id`, `kind`, `message`, optional `sections` and `field`, and a severity of
`error` or `warning`. Pattern rules use `required_pattern` or
`forbidden_pattern` with a compiled `pattern`. A `prose` rule remains
`unchecked`; it does not silently pass. Required fields and field types are
checked from the template independently of these rules.

## Shared section state and completion

`ReportSession` owns the accepted field values for one report. All mutation
paths call `fill_section()`: direct calls, `FILL()`, `fill_parallel()`, and
lambda finalisation. Validation returns typed errors, warnings, and unchecked
requirements. A rejected fill preserves the prior content. Replacing accepted
content invalidates filled transitive dependants. Dependency context is
copied, and parallel results are committed in template order.

Submission revalidates accepted sections, reports gaps, and renders the
request's `output_path` and `output_format`. Supported formats are `markdown`,
`json`, `jsonl`, and `markdown_final_fenced_json`. JSON contains a section-ID
map; JSONL contains ordered `section_id` and `fields` records. Markdown has
numbered section headings; the fenced format also ends with the section map.

A file alone does not establish completion. Missing sections, failed required
checks, unresolved structural failures, provider errors, and exhausted run
limits produce a partial result with diagnostics. Warnings, unchecked prose,
and advisory review findings remain visible without becoming verifier gates.

For a guided report, `SUBMIT()` writes the artifact. `COMMIT_OUTPUT()` applies
the existing explicit output-completion contract when requested. The artifact
must still match the accepted report state byte for byte. Ordinary report
completion also checks this match. Freeform RLM keeps its existing `FINAL`
and `FINAL_VAR` behaviour. Lambda-RLM rejects explicit commitment contracts;
its automatic submission supplies the validated artifact and completion state.

## Guided report commands

The built-in commands are bound to each session when a template is loaded and
`execution.scaffolding = true`. They need no task-owned Python command module.
Task extensions cannot replace these bindings.

| Command | Result |
| --- | --- |
| `HELP()` | Enabled commands and their use |
| `DOCS()`, `READ(source_id)` | Declared source IDs and source text |
| `STATUS()` | Completed, pending, unlocked, and blocked sections in template order |
| `GUIDANCE(section_id)` | Declared writing guidance |
| `CONTEXT(section_id)` | Accepted dependency content |
| `RULES(section_id)` | Applicable public writing rules |
| `START(section_id)` | Fields, guidance, context, rules, public rubric criteria, and source IDs |
| `VALIDATE(section_id, fields)` | Checks without changing state |
| `FILL(section_id, fields)` | Checks and accepts fields, or returns a typed failure |
| `SUBMIT()` | Writes the assembled artifact and returns completeness and diagnostics |

Python values retain full source text. The agent can inspect types, lengths,
keys, slices, and selected records, use `SHOW_VARS()`, and retain facts with
`NOTE()` and `RECALL()`. Existing search supports keywords, regular
expressions, line numbers, and surrounding lines.

Execution captures at most one million characters per stdout stream before
applying the display policy. Character counts describe the full write stream;
capture overflow and display truncation are labelled separately. Errors have
a bounded display. Search has its own threshold. Information-minimality
parameters select metadata, head, or tail previews; previews do not replace
the original Python values.

`execution.context_limit` is an explicit input-context budget. Its default is
128,000 tokens, not a claim about every model's capacity. Configure it for the
chosen model. The runtime requires
`0 < compaction_threshold_pct < hard_ceiling_pct <= 1` and checks the hard
ceiling first. Compaction preserves task instructions, system policy, report
state, bindings, and configured persistent data. Summary requests and returned
summaries are bounded. An immediate repeat threshold crossing stops the run
instead of repeatedly compacting without useful progress.

## Public rubric and review

A public rubric retains dimension IDs, weights, maximum scores, criterion
categories (`essential`, `important`, `optional`), expert personas, section
scope, and reference scope. Empty `eval_sections` means all sections.
Overlapping dimensions all contribute to section guidance. Empty
`eval_references` means all already-permitted references; explicit selectors
use substring matching and each must match. A failed selector never widens
access.

The same criteria are supplied to guided section startup and lambda drafting,
review, and synthesis. Synthesis receives only the references selected from
the permitted source pack. No rubric is also valid: the actor receives the
section guidance with an explicit indication that no public dimensions apply.

Lambda review supports `always`, `uncertainty`, `consistency`, `both`, and
`never`. Consistency triggers require multiple extraction samples. Per-source
retry counts and per-section supplement limits are bounded. Review gaps and
risks inform generation; malformed review output remains unresolved. A final
report review covers public criteria across sections when review is enabled.
Model findings retain dimension IDs and evidence but do not award reward.
Grounding diagnostics remain advisory. Deterministic error-level writing
rules and unresolved structural checks block completion.

## Configuration and optional model work

Use the existing experiment YAML `parameters` mapping for adapter blocks.
Explicit condition values override authored TOML defaults. Host request limits
can only tighten the resulting limits. Unknown adapter-file keys and unsupported block options
fail before model requests. Effective records include the resolved template,
public rules and rubric, source IDs, models, tools, strategy, limits, and
explicit constitutional parameters. Retained task artifacts own source-file
integrity; the report configuration does not add a second set of file hashes.

For guided RLM, the authoring file is `rlm.toml`. For lambda-RLM, the search
order is `lambda-rlm.toml`, then `rlm.toml`, then condition values alone. A
fallback file with incompatible adapter options fails validation. The public
example has separate compatible files for the two execution models.

Optional capabilities are explicit:

| Capability | Configuration and behaviour |
| --- | --- |
| Advice | `[advisor]` sets `enabled`, `model`, `max_uses`, `max_response_tokens`, and `context_window`. Guided RLM exposes `ADVISOR()`; lambda requests advice after review retries leave gaps. Disabled or exhausted advice makes no model request. |
| Constitution | Fixed principle parameters are accepted inline or by declared path. Guided RLM applies information minimality, state persistence, progress, source fidelity, and the initial autonomy mode. Lambda accepts its information-preview and source-fidelity mechanisms; REPL-specific parameter tables fail. Constitutional model inference is rejected. |
| Multiple section drafts | `[fill_section]` uses one generation at `k_candidates = 1`. Larger K requires `tournament_mode = "synthesis"`. Temperature, section allowlist, worker limit, synthesiser model, and synthesis input/output limits are explicit. Candidate IDs and assembly order are stable. |
| Source and anchor access | The lambda document sandbox supports bounded source and anchor access. `sandbox.tool_use = true` is rejected because this pipeline has no model tool execution loop. |
| Synthesis | Uses the existing synthesis engine through the run client. `synthesis_mode = "plain"` is supported. Unsupported tool-loop synthesis fails before execution. |

Advice is guidance, not source evidence or permission to change the task.
External system policy remains a system message; task instructions remain task
messages. Every lambda model phase receives both, including secondary models.

All admitted main and secondary requests participate in run accounting,
including extraction, review, retry, candidate, synthesis, advisor, subcall,
and compaction work. Per-call output limits cannot raise a provider client's
configured maximum. Secondary model names select their declared provider
route, subject to the host provider policy.

`guardrails.token_budget` is an observed total-token stop limit. Once reported
usage reaches it, no further work is admitted. Already admitted parallel calls
finish and are counted, so the limit is not an exact prepaid cap. An overrun
returns partial status with actual usage. Provider errors retain uncertainty;
unknown usage is not reported as zero-cost success. `max_turns` remains a main
iteration limit for RLM and a model-call limit for lambda-RLM. Unsupported
exact context and tool controls follow the existing runtime-limit rejection
contract.

## Synthetic example and local proof

The public [inspection report task](../../tasks/civil/report/synthetic-inspection/instruction.md)
contains synthetic evidence, a dependency template, public rules, weighted
rubric dimensions with all three criterion categories, and an independent
artifact verifier. The alternate source layout in the
[options fixture](../../tests/fixtures/report_harness/options/report.toml)
uses the same report implementation.

Use the normal task loader and execution drivers. Model selection belongs in
the experiment condition. The task environment only supplies report defaults
and public assets. No private repository, task package, or local output folder
is needed.

Deterministic checks cover both adapters, configuration, model-request policy,
source isolation, report state, and output commitment:

```bash
uv run pytest tests/adapters/rlm/ tests/adapters/lambda_rlm/ tests/adapters/test_report_configuration.py tests/templates/test_report_assets.py -q
uv run pytest tests/harness/test_execution_entrypoint.py tests/templates/test_report_example.py tests/evaluation/test_rubric_scorer.py -q
```

Replay conformance proves runtime behaviour. It does not establish report
quality, cost improvement, or hosted provider qualification.
