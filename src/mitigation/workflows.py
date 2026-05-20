from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from .clients import MitigationClient, extract_json_object
from .io import normalize_text
from . import prompts


def original_system_prompt(sample: Dict[str, Any]) -> str:
    return normalize_text(sample.get("system_prompt", sample.get("system", "")))


def original_query(sample: Dict[str, Any]) -> str:
    return normalize_text(sample.get("query", ""))


def run_workflow(
    client: MitigationClient,
    workflow: str,
    task: str,
    sample: Dict[str, Any],
    audio_path: Path,
) -> Dict[str, Any]:
    started = time.time()
    output: Dict[str, Any] = {
        "generated_transcript": None,
        "acoustic_caption": None,
        "structured_cues": None,
        "draft_response": None,
        "verifier_result": None,
        "response": None,
        "error": None,
        "latency": None,
    }
    try:
        if workflow == "baseline":
            output["response"] = client.audio_chat(original_system_prompt(sample), original_query(sample), audio_path)

        elif workflow == "asr_text":
            transcript = client.audio_chat("", prompts.ASR_PROMPT, audio_path)
            output["generated_transcript"] = transcript
            output["response"] = client.text_chat(
                original_system_prompt(sample),
                prompts.asr_text_answer_prompt(task, sample, transcript),
            )

        elif workflow == "caption":
            caption = client.audio_chat("", prompts.ACOUSTIC_CAPTION_PROMPT, audio_path)
            output["acoustic_caption"] = caption
            transcript = normalize_text(sample.get("transcript")) or caption
            output["generated_transcript"] = transcript
            output["response"] = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.caption_answer_prompt(task, sample, transcript, caption),
            )

        elif workflow == "structured_policy":
            raw = client.audio_chat("", prompts.STRUCTURED_CUE_PROMPT, audio_path)
            cues = extract_json_object(raw)
            output["structured_cues"] = cues
            output["generated_transcript"] = cues.get("transcript")
            output["response"] = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.structured_policy_answer_prompt(task, sample, cues),
            )

        elif workflow == "verifier":
            raw = client.audio_chat("", prompts.STRUCTURED_CUE_PROMPT, audio_path)
            cues = extract_json_object(raw)
            output["structured_cues"] = cues
            output["generated_transcript"] = cues.get("transcript")
            draft = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.structured_policy_answer_prompt(task, sample, cues),
            )
            output["draft_response"] = draft
            verifier_raw = client.text_chat(
                prompts.VERIFIER_PROMPT,
                prompts.verifier_user_prompt(task, sample, cues, draft),
            )
            verifier_result = extract_json_object(verifier_raw)
            output["verifier_result"] = verifier_result
            if verifier_result.get("pass") is True:
                output["response"] = draft
            else:
                output["response"] = client.text_chat(
                    prompts.REVISION_SYSTEM,
                    prompts.revision_user_prompt(task, sample, cues, draft, verifier_result),
                )

        else:
            raise ValueError(f"Unsupported workflow: {workflow}")
    except Exception as exc:
        output["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        output["latency"] = round(time.time() - started, 3)
    return output

