#!/usr/bin/env python3
"""Create a small VoxSafeBench pilot subset without modifying original data."""

from __future__ import annotations

import argparse
import copy
import json
import os
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEFAULT_TASKS = [
    "Safety-tier2/Child_voice",
    "Safety-tier2/Impaired_capacity",
    "Safety-tier2/Child_presence",
    "Privacy-tier2/Audio_conditioned_privacy",
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
            item = json.loads(raw)
            if not isinstance(item, dict):
                raise ValueError(f"Expected object in {path}:{line_no}, got {type(item).__name__}")
            rows.append(item)
    return rows


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


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


def language_key_for(rows: List[Dict[str, Any]]) -> Optional[str]:
    for key in LANGUAGE_KEYS:
        if any(key in row for row in rows):
            return key
    return None


def language_value(row: Dict[str, Any], lang_key: Optional[str]) -> str:
    if not lang_key:
        return ""
    return str(row.get(lang_key, "")).strip() or "<empty>"


def stratified_sample(
    rows: List[Dict[str, Any]],
    limit: int,
    seed: int,
    lang_key: Optional[str],
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    if limit >= len(rows):
        sampled = list(rows)
        rng.shuffle(sampled)
        return sampled
    if not lang_key:
        return rng.sample(rows, limit)

    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[language_value(row, lang_key)].append(row)
    for group_rows in groups.values():
        rng.shuffle(group_rows)

    selected: List[Dict[str, Any]] = []
    group_names = sorted(groups, key=lambda name: (-len(groups[name]), name))
    while len(selected) < limit and group_names:
        next_names = []
        for name in group_names:
            if len(selected) >= limit:
                break
            if groups[name]:
                selected.append(groups[name].pop())
            if groups[name]:
                next_names.append(name)
        group_names = next_names
    rng.shuffle(selected)
    return selected


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


def iter_audio_locations(row: Dict[str, Any]) -> Iterable[Tuple[List[Any], str]]:
    for key, value in row.items():
        if is_probable_audio_key(key, value):
            yield [key], str(value).strip()
    conversations = row.get("conversations")
    if isinstance(conversations, list):
        for idx, turn in enumerate(conversations):
            if not isinstance(turn, dict):
                continue
            for key, value in turn.items():
                if is_probable_audio_key(key, value):
                    yield ["conversations", idx, key], str(value).strip()


def set_nested(row: Dict[str, Any], location: List[Any], value: str) -> None:
    target: Any = row
    for part in location[:-1]:
        target = target[part]
    target[location[-1]] = value


def unique_audio_name(src: Path, used_names: set[str], row_idx: int, field_name: str) -> str:
    clean_field = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in field_name)
    base = src.name or f"audio_{row_idx}"
    candidate = f"{row_idx:05d}_{clean_field}_{base}"
    while candidate in used_names:
        candidate = f"{row_idx:05d}_{clean_field}_{len(used_names)}_{base}"
    used_names.add(candidate)
    return candidate


def link_or_copy(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() or dst.is_symlink():
        return "exists"
    try:
        os.symlink(src, dst)
        return "symlinked"
    except OSError:
        shutil.copy2(src, dst)
        return "copied"


def materialize_audio_refs(
    rows: List[Dict[str, Any]],
    source_metadata_path: Path,
    output_metadata_path: Path,
    symlink_audio: bool,
) -> Dict[str, Any]:
    counts = Counter()
    used_names: set[str] = set()
    missing_examples: List[Dict[str, str]] = []
    audio_dir = output_metadata_path.parent / "audio_files"

    for row_idx, row in enumerate(rows):
        for location, raw_path in list(iter_audio_locations(row)):
            counts["references"] += 1
            src = resolve_audio_path(source_metadata_path, raw_path)
            if not src or not src.exists():
                counts["missing"] += 1
                if len(missing_examples) < 10:
                    missing_examples.append({"row": str(row_idx), "raw_path": raw_path, "resolved_path": str(src)})
                continue

            counts["existing"] += 1
            if not symlink_audio:
                continue

            field_name = "_".join(str(part) for part in location)
            dst = audio_dir / unique_audio_name(src, used_names, row_idx, field_name)
            action = link_or_copy(src, dst)
            counts[action] += 1
            relative = os.path.relpath(dst, start=output_metadata_path.parent)
            set_nested(row, location, relative)

    return {"counts": dict(counts), "missing_examples": missing_examples}


def create_task_subset(
    dataset_root: Path,
    output_root: Path,
    task: str,
    limit_per_task: int,
    seed: int,
    symlink_audio: bool,
) -> Dict[str, Any]:
    source_metadata_path = find_matching_metadata(dataset_root, task)
    output_metadata_path = output_root / task / "metadata.jsonl"
    result: Dict[str, Any] = {
        "task": task,
        "source_metadata_path": str(source_metadata_path) if source_metadata_path else None,
        "output_metadata_path": str(output_metadata_path),
        "limit_per_task": limit_per_task,
    }
    if not source_metadata_path or not source_metadata_path.exists():
        result.update({"status": "missing_metadata", "source_count": 0, "sampled_count": 0})
        return result

    rows = read_jsonl(source_metadata_path)
    lang_key = language_key_for(rows)
    sampled = stratified_sample(rows, limit_per_task, seed, lang_key)
    pilot_rows = [copy.deepcopy(row) for row in sampled]
    audio = materialize_audio_refs(pilot_rows, source_metadata_path, output_metadata_path, symlink_audio)
    write_jsonl(output_metadata_path, pilot_rows)

    lang_counts = Counter(language_value(row, lang_key) for row in pilot_rows) if lang_key else Counter()
    result.update(
        {
            "status": "created",
            "source_count": len(rows),
            "sampled_count": len(pilot_rows),
            "language_key": lang_key,
            "language_counts": dict(sorted(lang_counts.items())),
            "audio": audio,
            "audio_mode": "symlink_or_copy" if symlink_audio else "original_paths",
        }
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", default="./datasets", help="Original dataset root")
    parser.add_argument("--output-root", default="./datasets_pilot", help="Pilot dataset output root")
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS, help="Task paths under dataset root")
    parser.add_argument("--limit-per-task", type=int, default=100, help="Maximum rows to sample per task")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--manifest-json",
        default="outputs/pilot_inspection/pilot_manifest.json",
        help="Manifest path to write",
    )
    parser.add_argument(
        "--keep-original-audio-paths",
        action="store_true",
        help="Do not symlink/copy audio into the pilot tree; leave metadata paths unchanged",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit_per_task < 1:
        raise SystemExit("--limit-per-task must be positive")

    dataset_root = Path(args.dataset_root)
    output_root = Path(args.output_root)
    symlink_audio = not args.keep_original_audio_paths
    results = [
        create_task_subset(
            dataset_root=dataset_root,
            output_root=output_root,
            task=task,
            limit_per_task=args.limit_per_task,
            seed=args.seed,
            symlink_audio=symlink_audio,
        )
        for task in args.tasks
    ]

    manifest = {
        "dataset_root": str(dataset_root),
        "output_root": str(output_root),
        "limit_per_task": args.limit_per_task,
        "seed": args.seed,
        "tasks": results,
    }
    manifest_path = Path(args.manifest_json)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for result in results:
        print(
            f"{result['task']}: {result['status']} "
            f"({result.get('sampled_count', 0)}/{result.get('source_count', 0)} rows) -> "
            f"{result['output_metadata_path']}"
        )
    print(f"Wrote manifest JSON: {manifest_path}")

    missing = [result["task"] for result in results if result["status"] != "created"]
    if missing:
        print(f"Missing metadata for {len(missing)} task(s): {', '.join(missing)}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
