# Governance Rules

The meta-harness can propose changes. It must not silently mutate worlds, verifiers, schemas, or generators.

## Continue Automatically

Continue without user approval when:

- the next step only emits a request packet;
- deterministic evaluation reads existing evidence;
- comparison writes local reports;
- a run-only directive is explicitly accepted.

## Stop for Governance

Stop and ask for a decision when:

- an event candidate appears;
- the reviewer identifies a verifier-language gap;
- the operation orchestrator needs a missing handle;
- a world schema or world-generator change is proposed;
- evidence suggests the verifier is wrong even though the model output appears right.

## Decision Shapes

Use `aec-bench meta-harness govern` for explicit decisions:

```bash
aec-bench meta-harness govern \
  --brief brief.json \
  --source-world candidate-world.json \
  --proposal proposal.json \
  --decision decision.json
```

Accepted `run_only` decisions create local directives. Accepted `world_schema` or `world_generator` decisions route back to world generation.
