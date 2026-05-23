<!-- ABOUTME: Scope-filter dropdowns for Analyze (experiment, dataset, model, adapter, task type). -->
<!-- ABOUTME: Emits onScopeChange({field: value|undefined}) for any change. -->
<script lang="ts">
  import type { AnalyzeState, ScopePatch } from "../lib/stores/analyze.svelte";

  type Props = {
    state: AnalyzeState;
    experiments: string[];
    datasets: string[];
    models: string[];
    adapters: string[];
    taskTypes: string[];
    onScopeChange: (patch: ScopePatch) => void;
  };
  let { state, experiments, datasets, models, adapters, taskTypes, onScopeChange }: Props = $props();

  function onChange(field: keyof ScopePatch, e: Event) {
    const v = (e.target as HTMLSelectElement).value;
    onScopeChange({ [field]: v === "" ? undefined : v });
  }
</script>

<div class="scope">
  <label>
    Experiment
    <select value={state.experiment ?? ""} onchange={(e) => onChange("experiment", e)}>
      <option value="">all</option>
      {#each experiments as e (e)}
        <option value={e}>{e}</option>
      {/each}
    </select>
  </label>

  <label>
    Dataset
    <select value={state.dataset ?? ""} onchange={(e) => onChange("dataset", e)}>
      <option value="">all</option>
      {#each datasets as d (d)}
        <option value={d}>{d}</option>
      {/each}
    </select>
  </label>

  <label>
    Model
    <select value={state.model ?? ""} onchange={(e) => onChange("model", e)}>
      <option value="">all</option>
      {#each models as m (m)}
        <option value={m}>{m}</option>
      {/each}
    </select>
  </label>

  <label>
    Adapter
    <select value={state.adapter ?? ""} onchange={(e) => onChange("adapter", e)}>
      <option value="">all</option>
      {#each adapters as a (a)}
        <option value={a}>{a}</option>
      {/each}
    </select>
  </label>

  <label>
    Task type
    <select value={state.task_type ?? ""} onchange={(e) => onChange("task_type", e)}>
      <option value="">all</option>
      {#each taskTypes as t (t)}
        <option value={t}>{t}</option>
      {/each}
    </select>
  </label>
</div>

<style>
  .scope {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-md);
    padding: var(--space-sm) var(--space-lg);
    border-top: 1px solid var(--card-border);
    border-bottom: 1px solid var(--card-border);
  }
  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-xs);
    font-size: 0.78rem;
    color: var(--text-2);
  }
</style>
