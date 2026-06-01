from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from .clients import MitigationClient, extract_json_object
from .io import normalize_text
from . import prompts


PROMPT_VERSION = "no_task_label_v2"


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
        "policy_decision": None,
        "draft_response": None,
        "verifier_result": None,
        "response": None,
        "error": None,
        "latency": None,
        "prompt_version": PROMPT_VERSION,
        "leakage_mode": "baseline_original_prompt" if workflow == "baseline" else "no_task_label_no_metadata_transcript",
    }
    try:
        if workflow == "baseline":
            output["response"] = client.audio_chat(original_system_prompt(sample), original_query(sample), audio_path)

        elif workflow == "asr_text":
            transcript = client.audio_chat("", prompts.ASR_PROMPT, audio_path)
            output["generated_transcript"] = transcript
            output["response"] = client.text_chat(
                prompts.ASR_TEXT_ANSWER_SYSTEM,
                prompts.asr_text_answer_prompt(sample, transcript),
            )

        elif workflow == "caption":
            caption = client.audio_chat("", prompts.ACOUSTIC_CAPTION_PROMPT, audio_path)
            output["acoustic_caption"] = caption
            # The captioning call is asked to include a transcript. Do not fall
            # back to metadata transcript here; that would leak ground-truth
            # dataset text into an audio-derived mitigation pipeline.
            transcript = ""
            output["generated_transcript"] = transcript
            output["response"] = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.caption_answer_prompt(sample, transcript, caption),
            )

        elif workflow == "caption_verifier":
            caption = client.audio_chat("", prompts.ACOUSTIC_CAPTION_PROMPT, audio_path)
            output["acoustic_caption"] = caption
            transcript = ""
            output["generated_transcript"] = transcript
            draft = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.caption_answer_prompt(sample, transcript, caption),
            )
            output["draft_response"] = draft
            verifier_raw = client.text_chat(
                prompts.CAPTION_VERIFIER_PROMPT,
                prompts.caption_verifier_user_prompt(sample, caption, draft),
            )
            verifier_result = extract_json_object(verifier_raw)
            output["verifier_result"] = verifier_result
            if verifier_result.get("pass") is True:
                output["response"] = draft
            else:
                output["response"] = client.text_chat(
                    prompts.REVISION_SYSTEM,
                    prompts.caption_revision_user_prompt(sample, caption, draft, verifier_result),
                )

        elif workflow == "structured_policy":
            raw = client.audio_chat("", prompts.STRUCTURED_CUE_PROMPT, audio_path)
            cues = extract_json_object(raw)
            output["structured_cues"] = cues
            output["generated_transcript"] = cues.get("transcript")
            policy_raw = client.text_chat(
                prompts.POLICY_MAPPER_SYSTEM,
                prompts.policy_mapper_prompt(sample, cues),
            )
            policy_decision = extract_json_object(policy_raw)
            output["policy_decision"] = policy_decision
            output["response"] = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.structured_policy_answer_prompt(sample, cues, policy_decision),
            )

        elif workflow == "verifier":
            raw = client.audio_chat("", prompts.STRUCTURED_CUE_PROMPT, audio_path)
            cues = extract_json_object(raw)
            output["structured_cues"] = cues
            output["generated_transcript"] = cues.get("transcript")
            policy_raw = client.text_chat(
                prompts.POLICY_MAPPER_SYSTEM,
                prompts.policy_mapper_prompt(sample, cues),
            )
            policy_decision = extract_json_object(policy_raw)
            output["policy_decision"] = policy_decision
            draft = client.text_chat(
                prompts.POLICY_BOUND_ANSWER_SYSTEM,
                prompts.structured_policy_answer_prompt(sample, cues, policy_decision),
            )
            output["draft_response"] = draft
            verifier_raw = client.text_chat(
                prompts.VERIFIER_PROMPT,
                prompts.verifier_user_prompt(sample, cues, policy_decision, draft),
            )
            verifier_result = extract_json_object(verifier_raw)
            output["verifier_result"] = verifier_result
            if verifier_result.get("pass") is True:
                output["response"] = draft
            else:
                output["response"] = client.text_chat(
                    prompts.REVISION_SYSTEM,
                    prompts.revision_user_prompt(sample, cues, policy_decision, draft, verifier_result),
                )

        else:
            raise ValueError(f"Unsupported workflow: {workflow}")
    except Exception as exc:
        output["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        output["latency"] = round(time.time() - started, 3)
    return output
