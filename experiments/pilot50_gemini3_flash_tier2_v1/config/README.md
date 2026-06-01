# Pilot50 Gemini 3 Flash Tier 2 V1

Purpose: compare three VoxSafeBench workflows on four Tier 2 audio-conditioned subgroups.

Model:

- `gemini_3_flash`

Workflows:

- `baseline`
- `caption`
- `caption_verifier`
- `verifier`

Tasks:

- `Safety-tier2/Child_voice`
- `Safety-tier2/Impaired_capacity`
- `Safety-tier2/Child_presence`
- `Privacy-tier2/Audio_conditioned_privacy`

Sample size:

- 50 samples per task per workflow
- 800 workflow outputs total across the four stored workflows before evaluator calls
- The main comparison table focuses on `baseline`, `caption`, and `caption_verifier`; the older `verifier` workflow is archived for reference because it uses structured cues and policy mapping rather than caption-only verification.

Artifact notes:

- `raw_outputs/` contains the append traces used to create the final evaluator inputs. Some files contain one duplicate row from resumed runs; conversion scripts dedupe by `sample_id`.
- `evaluator_inputs/` contains VoxSafeBench-compatible JSONL files passed to `run_evaluation.py`.
- `evaluator_outputs/` contains the staged model/workflow/task layout used by summary and failure-analysis scripts.
- `analysis/evaluation_summary.{csv,md}` contains the main official evaluator metric table.
- `analysis/caption_to_verifier_regressions.{csv,md}` contains verifier regression cases for failure analysis.
- `analysis/failure_case_study_plan.md` contains the manual coding protocol for failure cases.
- `archive/` contains reproducibility and diagnostic artifacts that are not needed for day-to-day reading, including direct evaluator outputs, clean raw-output backups, conversion manifests, long metric tables, and report figures.
