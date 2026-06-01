#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.io import read_jsonl, write_json, write_jsonl


KEEP_META_KEYS = {
    "id", "sample_id", "system_prompt", "system", "query", "task_type", "task", "tier", "label", "sub_label",
    "language", "Language", "lang", "response_type", "transcript", "audio_transcript", "source_text",
    "harmful_sentence", "foreground_transcript", "audio_file_name", "audio_path", "category", "dimension",
    "note", "paralinguistic", "acoustic", "expected_behavior", "conversations", "GT", "secret_text",
}
DEFAULT_SMOKE_ROOT = Path("experiments/smoke_child_voice_v1")


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def valid_response(row: Dict[str, Any]) -> bool:
    return bool(row.get("response") and not row.get("error"))


def dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep one row per sample_id, preferring successful rows over stale errors."""
    by_id: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []
    for idx, row in enumerate(rows):
        sample_id = str(row.get("sample_id") or row.get("id") or idx)
        if sample_id not in by_id:
            order.append(sample_id)
            by_id[sample_id] = row
            continue
        current = by_id[sample_id]
        if valid_response(row) and not valid_response(current):
            by_id[sample_id] = row
        elif valid_response(row) == valid_response(current):
            by_id[sample_id] = row
    return [by_id[sample_id] for sample_id in order]


def convert_file(input_path: Path, model: str, workflow: str, task: str, results_root: Path, prefix: str) -> Dict[str, Any]:
    converted_model = sanitize(f"{prefix}_{model}_{workflow}") if prefix else sanitize(f"{model}_{workflow}")
    output_field = sanitize(f"{model}_{workflow}")
    rows = []
    raw_rows = read_jsonl(input_path)
    source_rows = dedupe_rows(raw_rows)
    for row in source_rows:
        converted = {key: row[key] for key in row if key in KEEP_META_KEYS}
        response = row.get("response")
        error = row.get("error")
        converted[output_field] = response if response and not error else f"ERROR: {error or 'missing response'}"
        rows.append(converted)
    out_path = results_root / converted_model / task / "results.jsonl"
    write_jsonl(out_path, rows)
    ok = sum(1 for row in source_rows if row.get("response") and not row.get("error"))
    return {
        "model": model,
        "workflow": workflow,
        "task": task,
        "input_results": str(input_path),
        "converted_model": converted_model,
        "output_field": output_field,
        "output_results": str(out_path),
        "rows": len(source_rows),
        "raw_rows": len(raw_rows),
        "valid_responses": ok,
        "evaluation_command": f"python run_evaluation.py --results-dir {results_root} --model {converted_model} --task {task}",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-convert mitigation JSONL outputs to VoxSafeBench results layout.")
    parser.add_argument("--input-root", default=str(DEFAULT_SMOKE_ROOT / "raw_outputs"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--workflows", nargs="+", default=["baseline", "asr_text", "caption", "structured_policy", "verifier"])
    parser.add_argument("--results-root", default=str(DEFAULT_SMOKE_ROOT / "evaluator_inputs"))
    parser.add_argument("--converted-prefix", default="mitigation")
    parser.add_argument("--manifest", default=str(DEFAULT_SMOKE_ROOT / "analysis" / "mitigation_conversion_manifest.json"))
    args = parser.parse_args()

    records: List[Dict[str, Any]] = []
    missing: List[str] = []
    for workflow in args.workflows:
        input_path = Path(args.input_root) / args.model / workflow / args.task / "results.jsonl"
        if not input_path.exists():
            missing.append(str(input_path))
            continue
        record = convert_file(input_path, args.model, workflow, args.task, Path(args.results_root), args.converted_prefix)
        records.append(record)
        print(f"{workflow}: {record['valid_responses']}/{record['rows']} valid -> {record['output_results']}")
        print(f"  {record['evaluation_command']}")
    manifest = {"records": records, "missing": missing}
    write_json(Path(args.manifest), manifest)
    print(f"Wrote manifest: {args.manifest}")
    if missing:
        print("Missing inputs:")
        for path in missing:
            print(f"  {path}")
    return 0 if records else 2


if __name__ == "__main__":
    raise SystemExit(main())
