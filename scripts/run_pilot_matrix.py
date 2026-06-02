#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.clients import SUPPORTED_MITIGATION_MODELS


DEFAULT_TASKS = [
    "Safety-tier2/Child_voice",
    "Safety-tier2/Impaired_capacity",
    "Safety-tier2/Unsafe_ambient",
    "Safety-tier2/Overlap_instruction_injection",
]

DEFAULT_WORKFLOWS = ["baseline", "caption", "caption_verifier"]
DEFAULT_EXPERIMENT_DIR = "experiments/pilot50_gemini3_flash_tier2_v1"


def metadata_path(input_root: Path, task: str) -> Path:
    return input_root / task / "metadata.jsonl"


def run_command(args: List[str], dry_run: bool) -> int:
    print(" ".join(args))
    if dry_run:
        return 0
    completed = subprocess.run(args, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a VoxSafeBench Tier 2 mitigation pilot matrix.")
    parser.add_argument("--model", required=True, choices=SUPPORTED_MITIGATION_MODELS)
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--input-root", default="pilot_subsets/pilot_50")
    parser.add_argument("--experiment-dir", default=DEFAULT_EXPERIMENT_DIR)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    parser.add_argument("--workflows", nargs="+", default=DEFAULT_WORKFLOWS)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    script = Path(__file__).resolve().parent / "run_mitigation_inference.py"
    input_root = Path(args.input_root)
    output_dir = args.output_dir or str(Path(args.experiment_dir) / "raw_outputs")
    missing: List[str] = []
    failures: List[str] = []

    for task in args.tasks:
        task_metadata = metadata_path(input_root, task)
        if not task_metadata.exists():
            missing.append(str(task_metadata))
            print(f"skip missing metadata: {task_metadata}")
            continue
        for workflow in args.workflows:
            command = [
                sys.executable,
                str(script),
                "--model",
                args.model,
                "--workflow",
                workflow,
                "--task",
                task,
                "--input-metadata",
                str(task_metadata),
                "--output-dir",
                output_dir,
                "--max-workers",
                str(args.max_workers),
            ]
            if args.model_name:
                command.extend(["--model-name", args.model_name])
            if args.limit is not None:
                command.extend(["--limit", str(args.limit)])
            if args.resume:
                command.append("--resume")
            code = run_command(command, args.dry_run)
            if code != 0:
                failures.append(f"{task} / {workflow}: exit {code}")

    if missing:
        print("\nMissing metadata files:")
        for item in missing:
            print(f"  {item}")
    if failures:
        print("\nFailed runs:")
        for item in failures:
            print(f"  {item}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
