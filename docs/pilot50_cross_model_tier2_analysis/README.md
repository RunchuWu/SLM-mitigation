# Pilot50 Cross-Model Tier-2 Analysis

Public-facing pilot analysis artifacts for advisor discussion. This folder intentionally excludes raw JSONL outputs and bulk CSV data.

## Summary Files

- `combined_pilot50_metrics.md`: model/workflow/subgroup metric table.
- `workflow_delta_summary.md`: key takeaways, workflow deltas, model comparison, transition counts, and design implications.
- `case_studies.md`: selected representative cases for discussion.

## Charts

- `charts/aware_heatmap.svg`: Aware % heatmap.
- `charts/workflow_delta_bars.svg`: caption+verifier vs baseline Aware % deltas.
- `charts/transition_counts.svg`: sample-level transition counts.

Metric: `Aware % = (WAR + RtA) / non-SKIP`; `RtA %` is the stricter secondary metric.

Interpret these results as Pilot50 diagnostics for workflow design, not final benchmark claims.
