# Experiments

Each experiment should keep its generated artifacts under one directory so runs are reproducible and easy to compare.

Recommended layout:

```text
experiments/<experiment_id>/
  config/                 # frozen commands, task lists, prompt/model notes
  raw_outputs/            # raw workflow traces from run_mitigation_inference.py
  raw_outputs_clean_50/   # optional clean reruns or archived raw traces not used by final evaluator inputs
  evaluator_inputs/       # converted VoxSafeBench-compatible results.jsonl files
  evaluator_outputs_raw/  # direct outputs from run_evaluation.py before staging
  evaluator_outputs/      # staged outputs grouped as model/workflow/task
  analysis/               # CSV, Markdown, SVG summaries and failure-case reports
  logs/                   # long run logs, terminal captures, API/debug notes
  manifests/              # conversion manifests and dataset inventories
```

For the current pilot, use:

```text
experiments/pilot50_gemini3_flash_tier2_v1/
```

Typical flow:

1. Run baseline and mitigation workflows into `raw_outputs/`.
2. Convert workflow traces into evaluator-compatible JSONL under `evaluator_inputs/`.
3. Run `run_evaluation.py --results-dir <experiment>/evaluator_inputs --output-dir <experiment>/evaluator_outputs_raw`.
4. Stage evaluator outputs by workflow under `evaluator_outputs/`.
5. Generate summaries and failure-case reports into `analysis/`.
