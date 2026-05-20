#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.io import find_metadata, iter_audio_refs, language_key_for, read_jsonl, resolve_audio_path, write_json


DEFAULT_TASKS = [
    "Safety-tier2/Child_voice",
    "Safety-tier2/Impaired_capacity",
    "Safety-tier2/Child_presence",
    "Privacy-tier2/Audio_conditioned_privacy",
]


def short(value: Any, limit: int = 240) -> Any:
    if isinstance(value, str):
        text = " ".join(value.split())
        return text if len(text) <= limit else text[: limit - 3] + "..."
    return value


def inspect_task(dataset_root: Path, task: str) -> Dict[str, Any]:
    metadata_path = find_metadata(dataset_root, task)
    result: Dict[str, Any] = {
        "task": task,
        "metadata_path": str(metadata_path) if metadata_path else None,
        "exists": bool(metadata_path and metadata_path.exists()),
    }
    if not metadata_path or not metadata_path.exists():
        result.update({"count": 0, "keys": [], "language_counts": {}, "audio": {}, "preview": []})
        return result

    rows = read_jsonl(metadata_path)
    keys = sorted({key for row in rows for key in row})
    lang_key = language_key_for(rows)
    language_counts = Counter(str(row.get(lang_key, "")).strip() or "<empty>" for row in rows) if lang_key else Counter()
    audio_refs = 0
    audio_existing = 0
    missing: List[Dict[str, Any]] = []
    for idx, row in enumerate(rows):
        for field, raw in iter_audio_refs(row):
            audio_refs += 1
            resolved = resolve_audio_path(metadata_path, raw)
            if resolved and resolved.exists():
                audio_existing += 1
            elif len(missing) < 10:
                missing.append({"row": idx, "field": field, "raw": raw, "resolved": str(resolved)})
    preview = []
    for row in rows[:3]:
        item = {key: short(row[key]) for key in row if key in {"language", "lang", "system_prompt", "query", "transcript", "category", "task_type", "audio_file_name"}}
        preview.append(item)
    result.update(
        {
            "count": len(rows),
            "keys": keys,
            "language_key": lang_key,
            "language_counts": dict(sorted(language_counts.items())),
            "audio": {"references": audio_refs, "existing": audio_existing, "missing": audio_refs - audio_existing, "missing_examples": missing},
            "preview": preview,
        }
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="./datasets")
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    parser.add_argument("--output", default="analysis_outputs/dataset_inventory.json")
    args = parser.parse_args()
    summary = {"dataset_root": args.dataset_root, "tasks": [inspect_task(Path(args.dataset_root), task) for task in args.tasks]}
    write_json(Path(args.output), summary)
    for task in summary["tasks"]:
        print("\n" + "=" * 80)
        print(f"Task: {task['task']}")
        print(f"Metadata: {task['metadata_path']}")
        print(f"Rows: {task['count']}")
        print(f"Keys: {', '.join(task['keys'])}")
        print(f"Language: {json.dumps(task.get('language_counts', {}), ensure_ascii=False)}")
        print(f"Audio: {json.dumps(task.get('audio', {}), ensure_ascii=False)}")
        print("Preview:")
        print(json.dumps(task["preview"], ensure_ascii=False, indent=2))
    print(f"\nWrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
