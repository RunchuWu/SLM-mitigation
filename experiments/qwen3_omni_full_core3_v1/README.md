# Qwen3-Omni Full Core3 v1

Curated analytics snapshot for the Qwen3-Omni full-data mitigation evaluation.
Raw local and remote result trees are intentionally not tracked; this directory
stores small derived tables and a reader-facing Markdown summary.

## Main Artifacts

- `analysis/analytics/qwen_analytics_tables.md`: subgroup, metric-family, and task-level summary tables.
- `analysis/analytics/qwen_task_matrix.csv`: one row per task with baseline, caption, caption-verifier rates, and deltas.
- `analysis/analytics/qwen_subgroup_matrix.csv`: weighted subgroup-level overview.
- `analysis/analytics/qwen_metric_family_matrix.csv`: weighted Fairness, Privacy, and Safety overview.
- `analysis/analytics/qwen_metrics_long.csv`: long-form source table for filtering by workflow, task, split, and metric.
- `analysis/analytics/manifest.json`: generation manifest with source and output paths.

## Reproduce

```bash
python3 scripts/build_qwen_analytics_tables.py \
  --experiment-root remote_results/qwen3_omni_full_core3_v1 \
  --output-dir experiments/qwen3_omni_full_core3_v1/analysis/analytics
```

The source evaluator outputs are expected under the ignored local
`remote_results/qwen3_omni_full_core3_v1/evaluator_outputs` tree.
