# Example Experiment Configs

Four patterns covering common experiment shapes. Copy and adapt as needed.

## 1. Quick Test — Single Discipline, One Agent

The simplest useful experiment. Good for verifying your setup works before running a full benchmark.

```yaml
experiment_id: electrical-sonnet-quick
name: Quick electrical test
tasks:
  domains: [electrical]
  difficulties: [easy, medium]
agents:
  - name: sonnet-tool-loop
    adapter: tool_loop
    model: claude-sonnet-4-20250514
compute:
  backend: modal
  resource_limits:
    n_concurrent_trials: 4
repetitions: 1
```

**When to use:** first experiment in a new project, smoke-testing after task changes, quick iteration.

## 2. Model Comparison — Two Agents, Same Tasks

Pit two models against each other on the same tasks. Use 3+ repetitions for statistical significance.

```yaml
experiment_id: ground-comparison-2026-03-21
name: Ground tasks — Sonnet vs GPT-4o
tasks:
  domains: [ground]
agents:
  - name: sonnet-tool-loop
    adapter: tool_loop
    model: claude-sonnet-4-20250514
  - name: gpt4o-tool-loop
    adapter: tool_loop
    model: gpt-4o
compute:
  backend: modal
  resource_limits:
    n_concurrent_trials: 4
repetitions: 3
```

**When to use:** evaluating which model performs better on a discipline, preparing comparison reports.

## 3. Focused Template Sweep — One Template, All Difficulties

Drill into a single task family across all difficulty levels with high repetitions. Good for understanding difficulty calibration.

```yaml
experiment_id: voltage-drop-sweep
name: Voltage drop difficulty sweep
tasks:
  include_patterns: [electrical/voltage-drop/*]
agents:
  - name: sonnet-tool-loop
    adapter: tool_loop
    model: claude-sonnet-4-20250514
    parameters:
      max_turns: 20
compute:
  backend: modal
repetitions: 5
```

**When to use:** validating a new template, calibrating difficulty levels, deep-diving into one task family.

## 4. Full Benchmark — All Disciplines, Multi-Agent

Comprehensive run across all available tasks with multiple agents. This is the "real" benchmark.

```yaml
experiment_id: full-benchmark-2026-03-21
name: Full AEC benchmark — March 2026
description: Complete benchmark run across all disciplines with two leading models
tasks:
  domains: [civil, electrical, ground]
  difficulties: [easy, medium, hard]
agents:
  - name: sonnet-pydantic
    adapter: pydantic_ai
    model: claude-sonnet-4-20250514
  - name: gpt4o-tool-loop
    adapter: tool_loop
    model: gpt-4o
compute:
  backend: modal
  resource_limits:
    n_concurrent_trials: 8
  timeout_override: 900
repetitions: 3
```

**When to use:** quarterly benchmark runs, preparing results for publication, comprehensive model evaluation.

**Note:** large experiments can take hours. Monitor progress via the TUI (`aec-bench tui`) or check the ledger for imported results.
