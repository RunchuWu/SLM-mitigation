from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


AUDIO_KEY_HINTS = ("audio", "wav", "mp3", "flac", "file_name", "path")
LANGUAGE_KEYS = ("language", "Language", "lang")


def load_dotenv_if_present(repo_root: Path | None = None) -> None:
    root = repo_root or Path.cwd()
    env_path = root / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


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


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def task_metadata_path(dataset_root: Path, task: str) -> Path:
    return dataset_root / task / "metadata.jsonl"


def find_metadata(dataset_root: Path, task: str) -> Optional[Path]:
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


def first_audio_path(row: Dict[str, Any], metadata_path: Path) -> Optional[Path]:
    preferred = [
        "audio_file_name",
        "audio_path",
        "clean_audio_file_name",
        "diverse_audio_file_name",
        "turn1_audio_file_name",
    ]
    for key in preferred:
        if key in row:
            resolved = resolve_audio_path(metadata_path, row.get(key))
            if resolved:
                return resolved
    for _, raw in iter_audio_refs(row):
        resolved = resolve_audio_path(metadata_path, raw)
        if resolved:
            return resolved
    return None


def language_key_for(rows: List[Dict[str, Any]]) -> Optional[str]:
    for key in LANGUAGE_KEYS:
        if any(key in row for row in rows):
            return key
    return None


def stable_sample_id(task: str, row: Dict[str, Any], index: int) -> str:
    for key in ("id", "sample_id", "uid"):
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return f"{task}#{index}"


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()

