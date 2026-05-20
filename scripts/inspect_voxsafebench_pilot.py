#!/usr/bin/env python3
"""Inspect VoxSafeBench task metadata for pilot-study planning."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_TASKS = [
    "Safety-tier2/Child_voice",
    "Safety-tier2/Impaired_capacity",
    "Safety-tier2/Child_presence",
    "Privacy-tier2/Audio_conditioned_privacy",
]

TEXT_PREVIEW_KEYS = [
    "id",
    "language",
    "Language",
    "lang",
    "system_prompt",
    "system",
    "query",
    "transcript",
    "audio_transcript",
    "foreground_transcript",
    "source_text",
    "harmful_sentence",
    "expected_behavior",
    "GT",
]

AUDIO_KEY_HINTS = ("audio", "wav", "mp3", "flac", "file_name", "path")
LANGUAGE_KEYS = ("language", "Language", "lang")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            raw = line.strip()
            if not raw:
                continue
            try:
                item = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_no}: {exc}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"Expected object in {path}:{line_no}, got {type(item).__name__}")
            rows.append(item)
    return rows


def task_metadata_path(dataset_root: Path, task: str) -> Path:
    return dataset_root / task / "metadata.jsonl"


def find_matching_metadata(dataset_root: Path, task: str) -> Optional[Path]:
    expected = task_metadata_path(dataset_root, task)
    if expected.exists():
        return expected
    if not dataset_root.exists():
        return None

    suffix = Path(task) / "metadata.jsonl"
    matches = [p for p in dataset_root.rglob("metadata.jsonl") if Path(*p.parts[-len(suffix.parts):]) == suffix]
    if matches:
        return sorted(matches)[0]

    task_name = Path(task).name
    matches = [p for p in dataset_root.rglob("metadata.jsonl") if p.parent.name == task_name]
    return sorted(matches)[0] if matches else None


def resolve_audio_path(metadata_path: Path, raw_path: Any) -> Optional[Path]:
    raw = str(raw_path).strip() if raw_path is not None else ""
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (metadata_path.parent / candidate).resolve()


def is_probable_audio_key(key: str, value: Any) -> bool:
    lower = key.lower()
    if any(hint in lower for hint in AUDIO_KEY_HINTS):
        return isinstance(value, str) and bool(value.strip())
    if isinstance(value, str):
        return value.lower().strip().endswith((".wav", ".mp3", ".flac", ".m4a", ".ogg"))
    return False


def iter_audio_refs(row: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for key, value in row.items():
        if is_probable_audio_key(key, value):
            yield key, str(value).strip()
    conversations = row.get("conversations")
    if isinstance(conversations, list):
        for idx, turn in enumerate(conversations):
            if not isinstance(turn, dict):
                continue
            for key, value in turn.items():
                if is_probable_audio_key(key, value):
                    yield f"conversations[{idx}].{key}", str(value).strip()


def language_key_for(rows: List[Dict[str, Any]]) -> Optional[str]:
    for key in LANGUAGE_KEYS:
        if any(key in row for row in rows):
            return key
    return None


def short_value(value: Any, limit: int = 300) -> Any:
    if isinstance(value, str):
        collapsed = " ".join(value.split())
        return collapsed if len(collapsed) <= limit else collapsed[: limit - 3] + "..."
    return value


def preview_row(row: Dict[str, Any]) -> Dict[str, Any]:
    preview: Dict[str, Any] = {}
    for key in TEXT_PREVIEW_KEYS:
        if key in row and row[key] not in (None, ""):
            preview[key] = short_value(row[key])
    audio_refs = {key: value for key, value in iter_audio_refs(row)}
    if audio_refs:
        preview["audio_refs"] = audio_refs
    if "conversations" in row and "conversations" not in preview:
        preview["conversations"] = short_value(row["conversations"])
    return preview


def inspect_task(dataset_root: Path, task: str, examples_per_task: int) -> Dict[str, Any]:
    metadata_path = find_matching_metadata(dataset_root, task)
    result: Dict[str, Any] = {
        "task": task,
        "expected_metadata_path": str(task_metadata_path(dataset_root, task)),
        "metadata_path": str(metadata_path) if metadata_path else None,
        "exists": bool(metadata_path and metadata_path.exists()),
    }
    if not metadata_path or not metadata_path.exists():
        result.update(
            {
                "row_count": 0,
                "keys": [],
                "language_key": None,
                "language_counts": {},
                "audio": {"references": 0, "existing": 0, "missing": 0, "missing_examples": []},
                "examples": [],
            }
        )
        return result

    rows = read_jsonl(metadata_path)
    keys = sorted({key for row in rows for key in row.keys()})
    lang_key = language_key_for(rows)
    language_counts = Counter(str(row.get(lang_key, "")).strip() or "<empty>" for row in rows) if lang_key else Counter()

    audio_total = 0
    audio_existing = 0
    missing_examples: List[Dict[str, str]] = []
    audio_keys = Counter()
    for row_idx, row in enumerate(rows):
        for key, raw_path in iter_audio_refs(row):
            audio_total += 1
            audio_keys[key] += 1
            resolved = resolve_audio_path(metadata_path, raw_path)
            if resolved and resolved.exists():
                audio_existing += 1
            elif len(missing_examples) < 10:
                missing_examples.append(
                    {
                        "row": str(row_idx),
                        "field": key,
                        "raw_path": raw_path,
                        "resolved_path": str(resolved) if resolved else "",
                    }
                )

    result.update(
        {
            "row_count": len(rows),
            "keys": keys,
            "language_key": lang_key,
            "language_counts": dict(sorted(language_counts.items())),
            "audio": {
                "fields": dict(sorted(audio_keys.items())),
                "references": audio_total,
                "existing": audio_existing,
                "missing": audio_total - audio_existing,
                "missing_examples": missing_examples,
            },
            "examples": [preview_row(row) for row in rows[:examples_per_task]],
        }
    )
    return result


def print_task(result: Dict[str, Any]) -> None:
    print("\n" + "=" * 80)
    print(f"Task: {result['task']}")
    print(f"Metadata: {result.get('metadata_path') or 'MISSING'}")
    if not result["exists"]:
        print(f"Expected: {result['expected_metadata_path']}")
        return
    print(f"Rows: {result['row_count']}")
    print(f"Keys: {', '.join(result['keys'])}")
    if result.get("language_key"):
        print(f"Language field: {result['language_key']}")
        print(f"Language counts: {json.dumps(result['language_counts'], ensure_ascii=False)}")
    else:
        print("Language field: not found")
    audio = result["audio"]
    print(
        "Audio refs: "
        f"{audio['references']} total, {audio['existing']} existing, {audio['missing']} missing"
    )
    if audio.get("fields"):
        print(f"Audio fields: {json.dumps(audio['fields'], ensure_ascii=False)}")
    if audio["missing_examples"]:
        print("Missing audio examples:")
        for item in audio["missing_examples"][:5]:
            print(f"  row {item['row']} {item['field']}: {item['resolved_path']}")
    print("Examples:")
    for idx, example in enumerate(result["examples"], start=1):
        print(f"  Example {idx}:")
        print(json.dumps(example, ensure_ascii=False, indent=4))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default="./datasets", help="Dataset root directory")
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS, help="Task paths under dataset root")
    parser.add_argument("--examples-per-task", type=int, default=2, help="Readable examples to print per task")
    parser.add_argument(
        "--summary-json",
        default="outputs/pilot_inspection/summary.json",
        help="Path to write JSON summary. Use an empty string to disable.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_root = Path(args.dataset_root)
    results = [inspect_task(dataset_root, task, args.examples_per_task) for task in args.tasks]
    for result in results:
        print_task(result)

    summary = {"dataset_root": str(dataset_root), "tasks": results}
    if args.summary_json:
        out_path = Path(args.summary_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote summary JSON: {out_path}")

    missing = [result["task"] for result in results if not result["exists"]]
    if missing:
        print(f"\nMissing metadata for {len(missing)} task(s): {', '.join(missing)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
