#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.io import read_jsonl, write_jsonl


KEEP_META_KEYS = {
    "id", "sample_id", "system_prompt", "system", "query", "task_type", "task", "tier", "label", "sub_label",
    "language", "Language", "lang", "response_type", "transcript", "audio_transcript", "source_text",
    "harmful_sentence", "foreground_transcript", "audio_file_name", "audio_path", "category", "dimension",
    "note", "paralinguistic", "acoustic", "expected_behavior", "conversations", "GT", "secret_text",
}


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-results", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--converted-model-name", default=None)
    parser.add_argument("--output-field", default=None)
    parser.add_argument("--results-root", default="results")
    args = parser.parse_args()

    converted_model = args.converted_model_name or sanitize(f"{args.model}_{args.workflow}")
    output_field = args.output_field or sanitize(f"{args.model}_{args.workflow}")
    rows = []
    for row in read_jsonl(Path(args.input_results)):
        converted: Dict[str, Any] = {key: row[key] for key in row if key in KEEP_META_KEYS}
        response = row.get("response")
        error = row.get("error")
        converted[output_field] = response if response and not error else f"ERROR: {error or 'missing response'}"
        rows.append(converted)
    out_path = Path(args.results_root) / converted_model / args.task / "results.jsonl"
    write_jsonl(out_path, rows)
    print(f"Wrote {len(rows)} rows -> {out_path}")
    print(f"Run evaluation with: python run_evaluation.py --model {converted_model} --task {args.task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
