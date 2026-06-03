from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Optional


KIMI_MODEL_REPO_ID = "moonshotai/Kimi-Audio-7B-Instruct"
KIMI_HF_CACHE_DIRNAME = "models--moonshotai--Kimi-Audio-7B-Instruct"
KIMI_REQUIRED_MODEL_FILES = ("modeling_moonshot_kimia.py", "configuration_moonshot_kimia.py")
DEFAULT_ROPE_THETA = 10000.0

_MODEL_CACHE: dict[tuple[str, bool], Any] = {}
_AUTOCONFIG_PATCHED = False
_AUTOMODEL_PATCHED = False


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def kimi_load_detokenizer_default() -> bool:
    return _env_flag("KIMI_AUDIO_LOAD_DETOKENIZER", False)


def kimi_rope_theta_default() -> float:
    raw = os.getenv("KIMI_AUDIO_ROPE_THETA", "")
    if raw.strip():
        return float(raw)
    return DEFAULT_ROPE_THETA


def ensure_kimi_paths() -> None:
    """Make server-configured Kimi code paths importable."""

    paths = []
    for env_name in ("PROJECT_HOME", "KIMI_CODE", "KIMI_INFER"):
        raw = os.getenv(env_name)
        if raw:
            paths.append(Path(raw).expanduser())

    kimi_code = os.getenv("KIMI_CODE")
    if kimi_code and not os.getenv("KIMI_INFER"):
        paths.append(Path(kimi_code).expanduser() / "kimia_infer")

    for path in reversed(paths):
        if path.exists():
            value = str(path)
            if value not in sys.path:
                sys.path.insert(0, value)


def _has_required_remote_code(path: Path) -> bool:
    return all((path / name).exists() for name in KIMI_REQUIRED_MODEL_FILES)


def _snapshot_candidates(slm_root: Path) -> list[Path]:
    snapshots_dir = slm_root / "cache" / "huggingface" / "hub" / KIMI_HF_CACHE_DIRNAME / "snapshots"
    if not snapshots_dir.exists():
        return []
    candidates = [path for path in snapshots_dir.iterdir() if path.is_dir() and _has_required_remote_code(path)]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def resolve_kimi_model_path(model_path: Optional[str] = None) -> str:
    """Resolve the Kimi checkpoint using env-configured server paths.

    Existing local paths must include the remote-code files needed by
    `trust_remote_code=True`. If no explicit path is provided, prefer the
    Hugging Face cache snapshot under SLM_ROOT, then the model directory.
    """

    explicit = model_path or os.getenv("KIMI_AUDIO_MODEL_PATH")
    if explicit:
        explicit_path = Path(explicit).expanduser()
        if explicit_path.exists():
            if _has_required_remote_code(explicit_path):
                return str(explicit_path)
            raise ValueError(
                "Kimi-Audio model path is missing required remote-code files "
                f"{KIMI_REQUIRED_MODEL_FILES}: {explicit_path}. Set KIMI_AUDIO_MODEL_PATH "
                "to the Hugging Face snapshot path under $SLM_ROOT/cache/huggingface/hub."
            )
        return explicit

    slm_root_raw = os.getenv("SLM_ROOT")
    if slm_root_raw:
        slm_root = Path(slm_root_raw).expanduser()
        snapshots = _snapshot_candidates(slm_root)
        if snapshots:
            return str(snapshots[0])
        model_dir = slm_root / "models" / "Kimi-Audio-7B-Instruct"
        if model_dir.exists() and _has_required_remote_code(model_dir):
            return str(model_dir)

    raise ValueError(
        "Kimi-Audio model path is required. Set KIMI_AUDIO_MODEL_PATH to a local "
        "checkpoint snapshot, or set SLM_ROOT so the HF cache snapshot can be discovered."
    )


def apply_kimi_config_compat(config: Any, rope_theta: Optional[float] = None) -> Any:
    """Patch loaded Kimi config objects for remote-code/version compatibility."""

    if config is None:
        return config

    theta = kimi_rope_theta_default() if rope_theta is None else rope_theta
    class_name = type(config).__name__
    is_kimi_config = class_name == "KimiAudioConfig" or any(
        hasattr(config, attr) for attr in ("kimia_token_offset", "kimia_mimo_audiodelaytokens")
    )
    if is_kimi_config and not hasattr(config, "rope_theta"):
        setattr(config, "rope_theta", theta)
        try:
            setattr(type(config), "rope_theta", theta)
        except Exception:
            pass

    for attr in ("text_config", "audio_config", "model_config"):
        child = getattr(config, attr, None)
        if child is not None and child is not config:
            apply_kimi_config_compat(child, theta)
    return config


def _looks_like_kimi_model(value: Any) -> bool:
    text = str(value)
    path = Path(text).expanduser()
    return (
        KIMI_MODEL_REPO_ID in text
        or KIMI_HF_CACHE_DIRNAME in text
        or "Kimi-Audio" in text
        or (path.exists() and _has_required_remote_code(path))
    )


def patch_transformers_autoconfig() -> None:
    """Patch AutoConfig so Kimi config has rope_theta before model construction."""

    global _AUTOCONFIG_PATCHED
    if _AUTOCONFIG_PATCHED:
        return

    from transformers import AutoConfig

    original = AutoConfig.from_pretrained
    if getattr(original, "_kimi_compat_wrapped", False):
        _AUTOCONFIG_PATCHED = True
        return

    def from_pretrained_with_kimi_compat(cls: type, *args: Any, **kwargs: Any) -> Any:
        config = original(*args, **kwargs)
        return apply_kimi_config_compat(config)

    from_pretrained_with_kimi_compat._kimi_compat_wrapped = True  # type: ignore[attr-defined]
    from_pretrained_with_kimi_compat._kimi_compat_original = original  # type: ignore[attr-defined]
    AutoConfig.from_pretrained = classmethod(from_pretrained_with_kimi_compat)  # type: ignore[method-assign]
    _AUTOCONFIG_PATCHED = True


def patch_transformers_automodel() -> None:
    """Inject a patched Kimi config into AutoModelForCausalLM construction."""

    global _AUTOMODEL_PATCHED
    if _AUTOMODEL_PATCHED:
        return

    from transformers import AutoConfig, AutoModelForCausalLM

    original = AutoModelForCausalLM.from_pretrained
    if getattr(original, "_kimi_compat_wrapped", False):
        _AUTOMODEL_PATCHED = True
        return

    def from_pretrained_with_kimi_compat(
        cls: type,
        pretrained_model_name_or_path: Any,
        *model_args: Any,
        **kwargs: Any,
    ) -> Any:
        if _looks_like_kimi_model(pretrained_model_name_or_path):
            if kwargs.get("config") is None:
                config_kwargs = {
                    key: kwargs[key]
                    for key in (
                        "cache_dir",
                        "force_download",
                        "local_files_only",
                        "proxies",
                        "revision",
                        "subfolder",
                        "token",
                    )
                    if key in kwargs
                }
                config_kwargs["trust_remote_code"] = kwargs.get("trust_remote_code", True)
                kwargs["config"] = apply_kimi_config_compat(
                    AutoConfig.from_pretrained(pretrained_model_name_or_path, **config_kwargs)
                )
            else:
                kwargs["config"] = apply_kimi_config_compat(kwargs["config"])
        return original(pretrained_model_name_or_path, *model_args, **kwargs)

    from_pretrained_with_kimi_compat._kimi_compat_wrapped = True  # type: ignore[attr-defined]
    from_pretrained_with_kimi_compat._kimi_compat_original = original  # type: ignore[attr-defined]
    AutoModelForCausalLM.from_pretrained = classmethod(from_pretrained_with_kimi_compat)  # type: ignore[method-assign]
    _AUTOMODEL_PATCHED = True


def load_official_kimi_audio(model_path: Optional[str] = None, load_detokenizer: Optional[bool] = None) -> Any:
    """Load the official KimiAudio class with path and config compatibility."""

    ensure_kimi_paths()
    resolved_model_path = resolve_kimi_model_path(model_path)
    resolved_load_detokenizer = kimi_load_detokenizer_default() if load_detokenizer is None else load_detokenizer
    cache_key = (resolved_model_path, resolved_load_detokenizer)
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    patch_transformers_autoconfig()
    patch_transformers_automodel()
    try:
        from kimia_infer.api.kimia import KimiAudio
    except ImportError as exc:
        raise ImportError(
            "Kimi-Audio package is missing. Set KIMI_CODE to the official Kimi-Audio repo "
            "and include $KIMI_CODE on PYTHONPATH."
        ) from exc

    model = KimiAudio(model_path=resolved_model_path, load_detokenizer=resolved_load_detokenizer)
    apply_kimi_config_compat(getattr(getattr(model, "alm", None), "config", None))
    _MODEL_CACHE[cache_key] = model
    return model
