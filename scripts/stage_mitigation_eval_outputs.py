#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--converted-model-name", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--source-root", default="final_eval_results")
    parser.add_argument("--output-root", default="final_eval_results_mitigation")
    args = parser.parse_args()

    src = Path(args.source_root) / args.converted_model_name / args.task
    dst = Path(args.output_root) / args.model / args.workflow / args.task
    if not src.exists():
        raise FileNotFoundError(f"Evaluation output not found: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    print(f"Copied {src} -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

