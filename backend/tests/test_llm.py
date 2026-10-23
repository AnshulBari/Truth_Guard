from __future__ import annotations

from datetime import date

import httpx
import pytest

from app.config import Settings
from app.db import Database
from app.llm import LLMClient, LLMError, _parse_json_object
from app.retrieval import retrieve
from app.synthesizer import synthesize


class ExplodingClient:
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        raise LLMError("simulated upstream failure")


class MalformedClient:
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {"answer": 7, "claims": "not-a-list"}


class ValidClient:
    def complete_json(self, system_prompt: str, user_prompt: str) -> dict:
        return {
            "answer": "The expense limit is ₹8,000.",
            "claims": [
                {
                    "text": "The expense reimbursement limit is ₹8,000 per employee per calendar year.",
                    "support_passage_ids": ["doc-finance-circular-2025-07-p2"],
                }
            ],
            "assumptions": [],
            "missing_information": [],
        }


def test_json_fence_is_parsed() -> None:
    payload = _parse_json_object('```json\n{"answer": "ok"}\n```')
    assert payload == {"answer": "ok"}


def test_malformed_json_raises_llm_error() -> None:
    with pytest.raises(LLMError):
        _parse_json_object("this is not json")


def test_http_error_raises_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*args, **kwargs):
        return httpx.Response(
            500,
            text="upstream error",
            request=httpx.Request("POST", "https://example.invalid/chat/completions"),
        )

    monkeypatch.setattr("app.llm.httpx.post", fake_post)
    client = LLMClient(Settings(llm_api_key="test-key"))
    with pytest.raises(LLMError, match="HTTP 500"):
        client.complete_json("system", "user")


def test_llm_synthesis_valid_response(db: Database) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="stub-model")
    retrieval = retrieve(db, "What is the expense reimbursement limit for client entertainment?")
    result = synthesize(
        "What is the expense reimbursement limit for client entertainment?",
        date(2026, 10, 1),
        retrieval,
        settings,
        client=ValidClient(),
    )
    assert result.used_llm is True
    assert result.method == "llm"
    assert len(result.claims) == 1
    assert result.claims[0].support_ids == ["doc-finance-circular-2025-07-p2"]


def test_llm_transport_failure_falls_back_visibly(db: Database) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="stub-model")
    question = "What is the expense reimbursement limit for client entertainment?"
    retrieval = retrieve(db, question)
    result = synthesize(
        question,
        date(2026, 10, 1),
        retrieval,
        settings,
        client=ExplodingClient(),
    )
    assert result.used_llm is False
    assert result.method == "rules"
    assert result.error and "upstream failure" in result.error
    assert "fell back" in result.note


def test_malformed_llm_schema_falls_back(db: Database) -> None:
    settings = Settings(llm_api_key="test-key", llm_model="stub-model")
    question = "What is the expense reimbursement limit for client entertainment?"
    retrieval = retrieve(db, question)
    result = synthesize(
        question,
        date(2026, 10, 1),
        retrieval,
        settings,
        client=MalformedClient(),
    )
    assert result.used_llm is False
    assert result.error and "schema validation" in result.error
    assert result.claims  # deterministic fallback still produced evidence claims
