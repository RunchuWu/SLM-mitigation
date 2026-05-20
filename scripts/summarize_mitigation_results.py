#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List


METRIC_RE = re.compile(r"^\s*([^:#][^:]*?)\s*[:=]\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_metrics(log_path: Path) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    if not log_path.exists():
        return metrics
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = METRIC_RE.match(line)
        if match:
            metrics[match.group(1).strip()] = float(match.group(2))
    return metrics


def iter_logs(root: Path) -> Iterable[Path]:
    yield from root.rglob("log.txt")


def parts_from_log(root: Path, log_path: Path) -> Dict[str, str]:
    rel = log_path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 5:
        return {"model": parts[0], "workflow": parts[1], "task": "/".join(parts[2:-1])}
    if len(parts) >= 4:
        model_workflow = parts[0].split("_", 1)
        return {
            "model": model_workflow[0],
            "workflow": model_workflow[1] if len(model_workflow) > 1 else "unknown",
            "task": "/".join(parts[1:-1]),
        }
    return {"model": "unknown", "workflow": "unknown", "task": str(rel.parent)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-root", default="final_eval_results_mitigation")
    parser.add_argument("--fallback-eval-root", default="final_eval_results")
    parser.add_argument("--output-csv", default="analysis_outputs/mitigation_summary.csv")
    parser.add_argument("--output-md", default="analysis_outputs/mitigation_summary.md")
    args = parser.parse_args()

    root = Path(args.eval_root)
    if not root.exists():
        root = Path(args.fallback_eval_root)
    records: List[Dict[str, object]] = []
    baseline: Dict[tuple[str, str, str], float] = {}
    parsed = []
    for log_path in iter_logs(root):
        info = parts_from_log(root, log_path)
        for metric, value in parse_metrics(log_path).items():
            row = {**info, "metric_name": metric, "metric_value": value}
            parsed.append(row)
            if info["workflow"] == "baseline":
                baseline[(info["model"], info["task"], metric)] = value
    for row in parsed:
        base = baseline.get((str(row["model"]), str(row["task"]), str(row["metric_name"])))
        value = float(row["metric_value"])
        row["baseline_value"] = base
        row["absolute_improvement"] = None if base is None else value - base
        row["relative_improvement"] = None if not base else (value - base) / abs(base)
        records.append(row)

    out_csv = Path(args.output_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["model", "workflow", "task", "metric_name", "metric_value", "baseline_value", "absolute_improvement", "relative_improvement"]
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = ["| model | workflow | task | metric | value | baseline | abs imp | rel imp |", "|---|---|---|---|---:|---:|---:|---:|"]
    for row in records:
        lines.append(
            f"| {row['model']} | {row['workflow']} | {row['task']} | {row['metric_name']} | "
            f"{row['metric_value']} | {row['baseline_value']} | {row['absolute_improvement']} | {row['relative_improvement']} |"
        )
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_csv}")
    print(f"Wrote {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

