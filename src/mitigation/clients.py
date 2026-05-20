from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .io import load_dotenv_if_present


MODEL_DEFAULTS = {
    "gpt_4o_audio": "gpt-4o-audio-preview-2025-06-03",
    "gemini_3_flash": "gemini-3-flash-preview",
    "gemini_3_pro": "gemini-3-pro-preview",
}


def is_placeholder_key(value: str) -> bool:
    stripped = value.strip()
    return not stripped or stripped.lower().startswith("your_") or "your_" in stripped.lower()


def extract_json_object(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    try:
        value = json.loads(stripped)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            value = json.loads(stripped[start : end + 1])
            return value if isinstance(value, dict) else {"value": value}
        raise


class MitigationClient:
    def audio_chat(self, system_prompt: str, user_text: str, audio_path: Path) -> str:
        raise NotImplementedError

    def text_chat(self, system_prompt: str, user_text: str) -> str:
        raise NotImplementedError


class OpenAIMitigationClient(MitigationClient):
    def __init__(self, model_name: str) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai package is missing. Install with: pip install openai") from exc
        load_dotenv_if_present()
        key = os.getenv("OPENAI_API_KEY", "")
        if is_placeholder_key(key):
            raise ValueError("OPENAI_API_KEY is missing or still a placeholder in .env")
        self.client = OpenAI(api_key=key)
        self.model_name = model_name

    @staticmethod
    def _audio_format(path: Path) -> str:
        ext = path.suffix.lower()
        if ext == ".wav":
            return "wav"
        if ext == ".mp3":
            return "mp3"
        raise ValueError(f"Unsupported audio format for OpenAI audio input: {ext}")

    @staticmethod
    def _b64(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    @staticmethod
    def _text_from_response(response: Any) -> str:
        content = response.choices[0].message.content
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: List[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
            return "\n".join(parts).strip()
        return "" if content is None else str(content).strip()

    def audio_chat(self, system_prompt: str, user_text: str, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        content: List[Dict[str, Any]] = []
        if user_text:
            content.append({"type": "text", "text": user_text})
        content.append(
            {
                "type": "input_audio",
                "input_audio": {"data": self._b64(audio_path), "format": self._audio_format(audio_path)},
            }
        )
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": content})
        response = self.client.chat.completions.create(
            model=self.model_name,
            modalities=["text"],
            messages=messages,
        )
        return self._text_from_response(response)

    def text_chat(self, system_prompt: str, user_text: str) -> str:
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_text})
        response = self.client.chat.completions.create(model=self.model_name, messages=messages)
        return self._text_from_response(response)


class GeminiMitigationClient(MitigationClient):
    def __init__(self, model_name: str) -> None:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise ImportError("google-genai package is missing. Install with: pip install google-genai") from exc
        load_dotenv_if_present()
        key = os.getenv("GEMINI_API_KEY", "")
        if is_placeholder_key(key):
            raise ValueError("GEMINI_API_KEY is missing or still a placeholder in .env")
        self.genai = genai
        self.types = types
        self.client = genai.Client(api_key=key)
        self.model_name = model_name

    def _upload_audio(self, audio_path: Path) -> Any:
        mime_type = "audio/wav" if audio_path.suffix.lower() == ".wav" else "audio/mpeg"
        with audio_path.open("rb") as f:
            audio_file = self.client.files.upload(file=f, config={"mime_type": mime_type})
        while audio_file.state.name == "PROCESSING":
            time.sleep(1)
            audio_file = self.client.files.get(name=audio_file.name)
        if audio_file.state.name == "FAILED":
            raise RuntimeError(f"Audio processing failed for {audio_path}")
        return audio_file

    def audio_chat(self, system_prompt: str, user_text: str, audio_path: Path) -> str:
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        uploaded = []
        try:
            audio_file = self._upload_audio(audio_path)
            uploaded.append(audio_file)
            config = self.types.GenerateContentConfig()
            if system_prompt:
                config.system_instruction = [self.types.Part.from_text(text=system_prompt)]
            parts = [self.types.Part.from_uri(file_uri=audio_file.uri, mime_type=audio_file.mime_type)]
            if user_text:
                parts.append(self.types.Part.from_text(text=user_text))
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[self.types.Content(role="user", parts=parts)],
                config=config,
            )
            return "" if not getattr(response, "text", None) else str(response.text).strip()
        finally:
            for item in uploaded:
                try:
                    self.client.files.delete(name=item.name)
                except Exception:
                    pass

    def text_chat(self, system_prompt: str, user_text: str) -> str:
        config = self.types.GenerateContentConfig()
        if system_prompt:
            config.system_instruction = [self.types.Part.from_text(text=system_prompt)]
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=[self.types.Content(role="user", parts=[self.types.Part.from_text(text=user_text)])],
            config=config,
        )
        return "" if not getattr(response, "text", None) else str(response.text).strip()


def create_client(model: str, model_name: Optional[str] = None) -> MitigationClient:
    resolved = model_name or MODEL_DEFAULTS.get(model, model)
    if model == "gpt_4o_audio":
        return OpenAIMitigationClient(resolved)
    if model in {"gemini_3_flash", "gemini_3_pro"}:
        return GeminiMitigationClient(resolved)
    raise ValueError(f"Unsupported mitigation model: {model}")

