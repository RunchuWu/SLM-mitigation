#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.mitigation.io import (
    find_metadata,
    is_probable_audio_key,
    language_key_for,
    read_jsonl,
    resolve_audio_path,
    stable_sample_id,
    write_json,
    write_jsonl,
)


DEFAULT_TASKS = [
    "Safety-tier2/Child_voice",
    "Safety-tier2/Impaired_capacity",
    "Safety-tier2/Child_presence",
    "Privacy-tier2/Audio_conditioned_privacy",
]


def stratified_sample(rows: List[Dict[str, Any]], n: int, seed: int, lang_key: str | None) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    if n >= len(rows):
        sampled = list(rows)
        rng.shuffle(sampled)
        return sampled
    if not lang_key:
        return rng.sample(rows, n)
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row.get(lang_key, "")).strip() or "<empty>"].append(row)
    for group in groups.values():
        rng.shuffle(group)
    names = sorted(groups)
    selected: List[Dict[str, Any]] = []
    while len(selected) < n and names:
        next_names = []
        for name in names:
            if len(selected) >= n:
                break
            if groups[name]:
                selected.append(groups[name].pop())
            if groups[name]:
                next_names.append(name)
        names = next_names
    rng.shuffle(selected)
    return selected


def rewrite_audio_paths(row: Dict[str, Any], source_metadata_path: Path) -> None:
    for key, value in list(row.items()):
        if key.startswith("_"):
            continue
        if is_probable_audio_key(key, value):
            resolved = resolve_audio_path(source_metadata_path, value)
            if resolved:
                row[key] = str(resolved)
    conversations = row.get("conversations")
    if isinstance(conversations, list):
        for turn in conversations:
            if not isinstance(turn, dict):
                continue
            for key, value in list(turn.items()):
                if is_probable_audio_key(key, value):
                    resolved = resolve_audio_path(source_metadata_path, value)
                    if resolved:
                        turn[key] = str(resolved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", default="./datasets")
    parser.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    parser.add_argument("--n-per-task", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="./pilot_subsets/default")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    manifest = {"dataset_root": args.dataset_root, "output_dir": str(output_dir), "n_per_task": args.n_per_task, "seed": args.seed, "tasks": []}
    for task in args.tasks:
        metadata_path = find_metadata(Path(args.dataset_root), task)
        if not metadata_path:
            manifest["tasks"].append({"task": task, "status": "missing_metadata"})
            print(f"{task}: missing metadata")
            continue
        rows = read_jsonl(metadata_path)
        lang_key = language_key_for(rows)
        sampled = [dict(row) for row in stratified_sample(rows, args.n_per_task, args.seed, lang_key)]
        for idx, row in enumerate(sampled):
            row.setdefault("sample_id", stable_sample_id(task, row, idx))
            row["_source_metadata_path"] = str(metadata_path)
            rewrite_audio_paths(row, metadata_path)
        out_path = output_dir / task / "metadata.jsonl"
        write_jsonl(out_path, sampled)
        counts = Counter(str(row.get(lang_key, "")).strip() or "<empty>" for row in sampled) if lang_key else Counter()
        manifest["tasks"].append(
            {
                "task": task,
                "status": "created",
                "source_metadata_path": str(metadata_path),
                "pilot_metadata_path": str(out_path),
                "source_count": len(rows),
                "pilot_count": len(sampled),
                "language_key": lang_key,
                "language_counts": dict(sorted(counts.items())),
            }
        )
        print(f"{task}: wrote {len(sampled)} rows -> {out_path}")
    write_json(output_dir / "manifest.json", manifest)
    print(f"Wrote manifest: {output_dir / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
