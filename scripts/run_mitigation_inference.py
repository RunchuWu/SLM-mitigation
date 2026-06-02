#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock, local
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.clients import SUPPORTED_MITIGATION_MODELS, create_client
from src.mitigation.io import append_jsonl, first_audio_path, read_jsonl, stable_sample_id
from src.mitigation.workflows import run_workflow


WORKFLOWS = ["baseline", "asr_text", "caption", "caption_verifier", "structured_policy", "verifier"]


def output_path(output_dir: Path, model: str, workflow: str, task: str) -> Path:
    return output_dir / model / workflow / task / "results.jsonl"


def load_completed(path: Path) -> Dict[str, Dict[str, Any]]:
    if not path.exists():
        return {}
    completed = {}
    for row in read_jsonl(path):
        sid = str(row.get("sample_id", ""))
        if sid and row.get("response") and not row.get("error"):
            completed[sid] = row
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, choices=SUPPORTED_MITIGATION_MODELS)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--workflow", required=True, choices=WORKFLOWS)
    parser.add_argument("--task", required=True)
    parser.add_argument("--input-metadata", required=True)
    parser.add_argument("--output-dir", default="experiments/ad_hoc/raw_outputs")
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    metadata_path = Path(args.input_metadata)
    rows = read_jsonl(metadata_path)
    if args.limit is not None:
        rows = rows[: args.limit]
    out_path = output_path(Path(args.output_dir), args.model, args.workflow, args.task)
    completed = load_completed(out_path) if args.resume else {}
    lock = Lock()
    thread_state = local()
    client_error = None
    try:
        create_client(args.model, args.model_name)
    except Exception as exc:
        client_error = f"{type(exc).__name__}: {exc}"

    work: List[tuple[int, Dict[str, Any]]] = []
    for idx, row in enumerate(rows):
        sid = stable_sample_id(args.task, row, idx)
        if sid in completed:
            continue
        work.append((idx, row))

    print(f"Input: {metadata_path}")
    print(f"Output: {out_path}")
    print(f"Workflow: {args.workflow}; pending {len(work)}/{len(rows)}")

    def process(item: tuple[int, Dict[str, Any]]) -> Dict[str, Any]:
        idx, sample = item
        sid = stable_sample_id(args.task, sample, idx)
        audio_path = first_audio_path(sample, metadata_path)
        base = dict(sample)
        base.update(
            {
                "model": args.model,
                "workflow": args.workflow,
                "task": args.task,
                "sample_id": sid,
                "audio_path": str(audio_path) if audio_path else None,
            }
        )
        if client_error:
            base.update(
                {
                    "generated_transcript": None,
                    "acoustic_caption": None,
                    "structured_cues": None,
                    "policy_decision": None,
                    "draft_response": None,
                    "verifier_result": None,
                    "response": None,
                    "error": client_error,
                    "latency": 0,
                }
            )
            return base
        if not audio_path:
            base.update({"response": None, "error": "No audio path found", "latency": 0})
            return base
        if not hasattr(thread_state, "client"):
            thread_state.client = create_client(args.model, args.model_name)
        result = run_workflow(thread_state.client, args.workflow, args.task, sample, audio_path)
        base.update(result)
        return base

    if args.max_workers <= 1:
        for item in work:
            result = process(item)
            append_jsonl(out_path, result)
            status = "ok" if result.get("response") and not result.get("error") else "error"
            print(f"{result['sample_id']}: {status}")
    else:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(process, item) for item in work]
            for future in as_completed(futures):
                result = future.result()
                with lock:
                    append_jsonl(out_path, result)
                status = "ok" if result.get("response") and not result.get("error") else "error"
                print(f"{result['sample_id']}: {status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
