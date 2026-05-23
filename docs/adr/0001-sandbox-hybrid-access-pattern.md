# Sandbox slice access — hybrid declarative + tool-use

**Status**: accepted (2026-04-25)

For the [sandbox-grounded extraction work](../lambda-rlm/idea-b-sandbox-grounding.md), templates declare each block's slices up-front in TOML *and* the model can fetch additional slices via a four-tool API (`list_labels`, `list_anchors`, `get_slice`, `search`) when `[sandbox] tool_use = true`. Tool-use is off by default in v1, bounded by `tool_use_caps`, and provenance distinguishes template-declared slices from model-fetched ones.

## Why hybrid

We rejected declarative-only because it forces template authors to enumerate every slice every block could possibly need — fine for clean briefs but brittle for messier source shapes such as email threads and references registers. We rejected tool-use-only because it makes provenance "what the model said it used", which is the same trust problem we're trying to solve. The hybrid keeps the deterministic audit (template-declared slices are always known before the LLM runs) and adds an escape hatch for cases the author couldn't predict, with explicit per-block / per-run caps so it can't run away. Tool-use being off by default in v1 lets us validate the declarative path before introducing the discretionary one.
