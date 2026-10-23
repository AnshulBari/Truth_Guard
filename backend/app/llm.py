"""Small OpenAI-compatible JSON client.

The provider is deliberately generic: OpenAI, OpenRouter, Groq or a local
Ollama server can be used by changing LLM_BASE_URL and LLM_MODEL. Any failure
is surfaced as LLMError so the pipeline can fall back visibly instead of
fabricating model output.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from .config import Settings


class LLMError(RuntimeError):
    """Raised for transport errors, non-2xx responses or malformed JSON."""


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not self.configured:
            raise LLMError("No LLM_API_KEY is configured")
        url = f"{self.settings.llm_base_url}/chat/completions"
        base_payload: dict[str, Any] = {
            "model": self.settings.llm_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        try:
            response = httpx.post(
                url,
                headers=headers,
                json={**base_payload, "response_format": {"type": "json_object"}},
                timeout=self.settings.llm_timeout,
            )
            if response.status_code == 400:
                # Some compatible providers reject response_format. Retry once
                # without it; strict parsing below still protects the pipeline.
                response = httpx.post(
                    url,
                    headers=headers,
                    json=base_payload,
                    timeout=self.settings.llm_timeout,
                )
        except httpx.HTTPError as exc:
            raise LLMError(f"Model request failed: {type(exc).__name__}") from exc
        if response.status_code >= 400:
            detail = response.text[:240].replace("\n", " ")
            raise LLMError(f"Model request returned HTTP {response.status_code}: {detail}")
        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("Model response did not contain a chat completion") from exc
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Model returned empty content")
        return _parse_json_object(content)


def _parse_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Model response was not valid JSON")
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("Model response was not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMError("Model response JSON was not an object")
    return parsed
