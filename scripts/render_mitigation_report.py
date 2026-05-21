#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


COUNT_RE = re.compile(r"^\s*(DAR|WAR|RtA|SKIP|Total evaluated):\s+(\d+)\s*$")
PCT_RE = re.compile(r"^\s*(DAR %|Aware %|RtA %).*?:\s+(-?\d+(?:\.\d+)?)%\s*$")
FIELD_RE = re.compile(r"^--- Field: (.+?) ---$")
SPLIT_RE = re.compile(r"^\s*\[(.+?)\]\s+\((\d+) rows with responses\)")


WORKFLOW_ORDER = ["baseline", "asr_text", "caption", "structured_policy", "verifier"]
WORKFLOW_LABELS = {
    "baseline": "E2E Baseline",
    "asr_text": "ASR Transcript",
    "caption": "Acoustic Caption",
    "structured_policy": "Structured Cue + Policy",
    "verifier": "Verifier Revision",
}


def parse_log(path: Path, model: str, workflow: str, task: str) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    field: Optional[str] = None
    split: Optional[str] = None
    current: Optional[Dict[str, object]] = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        field_match = FIELD_RE.match(line)
        if field_match:
            field = field_match.group(1)
            split = None
            current = None
            continue
        split_match = SPLIT_RE.match(line)
        if split_match and field:
            split = split_match.group(1)
            current = {
                "model": model,
                "workflow": workflow,
                "workflow_label": WORKFLOW_LABELS.get(workflow, workflow),
                "task": task,
                "field": field,
                "split": split,
                "rows_with_responses": int(split_match.group(2)),
                "DAR": 0,
                "WAR": 0,
                "RtA": 0,
                "SKIP": 0,
                "Total evaluated": 0,
                "DAR %": None,
                "Aware %": None,
                "RtA %": None,
            }
            records.append(current)
            continue
        if not current:
            continue
        count_match = COUNT_RE.match(line)
        if count_match:
            current[count_match.group(1)] = int(count_match.group(2))
            continue
        pct_match = PCT_RE.match(line)
        if pct_match:
            current[pct_match.group(1)] = float(pct_match.group(2))
    return records


def collect_records(eval_root: Path, model_filter: Optional[str], task_filter: Optional[str]) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for log_path in eval_root.rglob("log.txt"):
        rel = log_path.relative_to(eval_root)
        if len(rel.parts) < 4:
            continue
        model = rel.parts[0]
        workflow = rel.parts[1]
        task = "/".join(rel.parts[2:-1])
        if model_filter and model != model_filter:
            continue
        if task_filter and task != task_filter:
            continue
        records.extend(parse_log(log_path, model, workflow, task))
    return records


def write_csv(path: Path, records: Iterable[Dict[str, object]]) -> None:
    rows = list(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "model", "workflow", "workflow_label", "task", "field", "split", "rows_with_responses",
        "DAR", "WAR", "RtA", "SKIP", "Total evaluated", "DAR %", "Aware %", "RtA %",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def workflow_sort_key(row: Dict[str, object]) -> tuple:
    workflow = str(row["workflow"])
    return (WORKFLOW_ORDER.index(workflow) if workflow in WORKFLOW_ORDER else 999, workflow)


def official_metric_rows(records: List[Dict[str, object]]) -> List[Dict[str, object]]:
    return sorted(
        [r for r in records if r.get("split") == "Overall"],
        key=lambda r: (str(r["model"]), str(r["task"]), workflow_sort_key(r)),
    )


def fmt_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def write_markdown(path: Path, records: List[Dict[str, object]]) -> None:
    rows = official_metric_rows(records)
    lines = [
        "# VoxSafeBench Mitigation Evaluation Summary",
        "",
        "Official evaluator results parsed from `final_eval_results_mitigation`. Smoke runs are diagnostic only.",
        "",
        "| model | workflow | task | DAR | WAR | RtA | SKIP | Aware % | DAR % | RtA % |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['model']} | {row['workflow_label']} | {row['task']} | "
            f"{row['DAR']} | {row['WAR']} | {row['RtA']} | {row['SKIP']} | "
            f"{fmt_value(row['Aware %'])} | {fmt_value(row['DAR %'])} | {fmt_value(row['RtA %'])} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def svg_text(x: float, y: float, text: str, size: int = 14, weight: str = "400", anchor: str = "middle", fill: str = "#172033") -> str:
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">{html.escape(text)}</text>'
    )


def wrapped_text(x: float, y: float, text: str, width_chars: int, line_height: int = 18, size: int = 13) -> List[str]:
    words = text.split()
    lines: List[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if len(trial) > width_chars and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return [svg_text(x, y + idx * line_height, line, size=size) for idx, line in enumerate(lines)]


def write_workflow_figure(path: Path) -> None:
    width, height = 1600, 980
    colors = {
        "audio": "#28536B",
        "prompt": "#5C677D",
        "model": "#2A9D8F",
        "artifact": "#E9C46A",
        "policy": "#E76F51",
        "verifier": "#7B2CBF",
        "stroke": "#253247",
        "bg": "#F7F9FC",
    }
    rows = [
        ("0", "Baseline", ["Audio", "+ Original task prompt", "Speech model", "Final response"]),
        ("1", "ASR Transcript", ["Audio", "ASR transcript", "Text answer model", "Final response"]),
        ("2", "Acoustic Caption", ["Audio", "Transcript + free-form acoustic caption", "Answer model uses cues", "Final response"]),
        ("3", "Structured Cue + Policy", ["Audio", "Structured cue JSON", "Policy-bound answer prompt", "Final response"]),
        ("4", "Verifier Revision", ["Audio", "Structured cues + draft", "Verifier judgment", "Revised/final response"]),
    ]
    x_positions = [155, 495, 835, 1175, 1450]
    y0, row_gap = 190, 145
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="{colors["bg"]}"/>',
        svg_text(width / 2, 62, "VoxSafeBench Inference-Time Mitigation Workflows", 30, "700"),
        svg_text(width / 2, 98, "Comparing direct audio answering, transcript-only answering, acoustic cue extraction, policy binding, and verifier revision", 16, "400", fill="#4B5563"),
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#253247"/></marker></defs>',
    ]
    for step, label, boxes in rows:
        y = y0 + int(step) * row_gap
        parts.append(f'<line x1="70" y1="{y + 35}" x2="1530" y2="{y + 35}" stroke="#D7DEE8" stroke-width="1"/>')
        parts.append(f'<circle cx="55" cy="{y + 35}" r="24" fill="#172033"/>')
        parts.append(svg_text(55, y + 42, step, 18, "700", fill="#FFFFFF"))
        parts.append(svg_text(145, y + 28, label, 18, "700", anchor="start"))
        for i, box in enumerate(boxes):
            x = x_positions[i + 1] if i > 0 else x_positions[0]
            box_w = 235 if i < 3 else 205
            fill = ["#FFFFFF", colors["artifact"], colors["model"], "#FFFFFF"][min(i, 3)]
            if step == "3" and i == 2:
                fill = "#FDE7DF"
            if step == "4" and i == 2:
                fill = "#EFE4FF"
            parts.append(f'<rect x="{x - box_w/2}" y="{y}" width="{box_w}" height="70" rx="8" fill="{fill}" stroke="{colors["stroke"]}" stroke-width="1.5"/>')
            parts.extend(wrapped_text(x, y + 31, box, 28, size=13))
            if i < len(boxes) - 1:
                next_x = x_positions[i + 2] if i + 1 > 0 else x_positions[1]
                parts.append(f'<line x1="{x + box_w/2 + 12}" y1="{y + 35}" x2="{next_x - 125}" y2="{y + 35}" stroke="{colors["stroke"]}" stroke-width="1.8" marker-end="url(#arrow)"/>')
        if step == "1":
            parts.append(svg_text(495, y + 92, "removes who/how/where acoustic cues by design", 13, "400", fill="#8A4B00"))
        if step == "3":
            parts.append(svg_text(835, y + 92, "cue fields bind speech evidence to response policy", 13, "400", fill="#9A3412"))
        if step == "4":
            parts.append(svg_text(835, y + 92, "post-hoc judge checks ignored cue, unsafe compliance, over-refusal", 13, "400", fill="#5B21B6"))
    parts.append(svg_text(80, 930, "Figure: implementation schematic generated from scripts/render_mitigation_report.py", 12, "400", anchor="start", fill="#667085"))
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def write_metric_chart(path: Path, records: List[Dict[str, object]]) -> None:
    rows = official_metric_rows(records)
    width = 1280
    height = max(560, 160 + len(rows) * 72)
    left, top, bar_w, gap = 300, 95, 760, 26
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#F7F9FC"/>',
        svg_text(width / 2, 44, "Mitigation Evaluation: Overall Awareness Metrics", 26, "700"),
        svg_text(width / 2, 72, "Parsed from VoxSafeBench official evaluator logs; smoke n is small", 14, "400", fill="#4B5563"),
    ]
    for tick in range(0, 101, 25):
        x = left + bar_w * tick / 100
        parts.append(f'<line x1="{x}" y1="{top - 15}" x2="{x}" y2="{height - 55}" stroke="#E0E6EF" stroke-width="1"/>')
        parts.append(svg_text(x, height - 30, f"{tick}%", 12, fill="#667085"))
    for idx, row in enumerate(rows):
        y = top + idx * 72
        label = str(row["workflow_label"])
        parts.append(svg_text(24, y + 20, label, 14, "700", anchor="start"))
        parts.append(svg_text(24, y + 42, str(row["task"]), 11, "400", anchor="start", fill="#667085"))
        aware = float(row.get("Aware %") or 0)
        dar = float(row.get("DAR %") or 0)
        rta = float(row.get("RtA %") or 0)
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w}" height="18" rx="4" fill="#E7ECF3"/>')
        parts.append(f'<rect x="{left}" y="{y}" width="{bar_w * aware / 100:.1f}" height="18" rx="4" fill="#2A9D8F"/>')
        parts.append(svg_text(left + bar_w + 20, y + 14, f"Aware {aware:.1f}%", 12, "700", anchor="start", fill="#1F7A70"))
        parts.append(f'<rect x="{left}" y="{y + 25}" width="{bar_w * dar / 100:.1f}" height="12" rx="3" fill="#E76F51"/>')
        parts.append(f'<rect x="{left}" y="{y + 42}" width="{bar_w * rta / 100:.1f}" height="12" rx="3" fill="#7B2CBF"/>')
        parts.append(svg_text(left + bar_w + 20, y + 36, f"DAR {dar:.1f}%", 11, anchor="start", fill="#A6422B"))
        parts.append(svg_text(left + bar_w + 20, y + 53, f"RtA {rta:.1f}%", 11, anchor="start", fill="#5B21B6"))
    parts.append(svg_text(24, height - 30, "Green = Aware%; orange = DAR%; purple = RtA%.", 12, anchor="start", fill="#667085"))
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render mitigation workflow and evaluation report figures.")
    parser.add_argument("--eval-root", default="final_eval_results_mitigation")
    parser.add_argument("--model")
    parser.add_argument("--task")
    parser.add_argument("--output-dir", default="analysis_outputs/mitigation_report")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    records = collect_records(Path(args.eval_root), args.model, args.task)
    if not records:
        raise FileNotFoundError(f"No evaluation logs found under {args.eval_root}")

    write_csv(output_dir / "evaluation_summary.csv", records)
    write_markdown(output_dir / "evaluation_summary.md", records)
    write_workflow_figure(output_dir / "mitigation_workflows.svg")
    write_metric_chart(output_dir / "evaluation_metrics.svg", records)
    print(f"Wrote {output_dir / 'evaluation_summary.csv'}")
    print(f"Wrote {output_dir / 'evaluation_summary.md'}")
    print(f"Wrote {output_dir / 'mitigation_workflows.svg'}")
    print(f"Wrote {output_dir / 'evaluation_metrics.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
