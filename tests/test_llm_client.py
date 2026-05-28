from __future__ import annotations

import pytest

from app.config import LLMConfig
from app.llm_client import LLMError, LLMPermanentError, LLMTimeoutError, LLMTransientError, OpenAICompatibleClient


def _cfg() -> LLMConfig:
    return LLMConfig(
        base_url="https://example.com/v1",
        api_key="secret",
        model="qwen2.5-7b-instruct",
        temperature=0.0,
        max_tokens=64,
        timeout_seconds=1.0,
        max_retries=2,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
        max_concurrency=2,
    )


def test_success() -> None:
    def transport(url, payload, headers, timeout):
        return {"choices": [{"message": {"content": "OK"}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = client.complete("hi")
    assert out.text == "OK"


def test_timeout_retry_then_fail() -> None:
    count = {"n": 0}

    def transport(url, payload, headers, timeout):
        count["n"] += 1
        raise LLMTimeoutError("timeout")

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    with pytest.raises(LLMTimeoutError):
        client.complete("hi")
    assert count["n"] == 3


def test_transient_retry_then_success() -> None:
    count = {"n": 0}

    def transport(url, payload, headers, timeout):
        count["n"] += 1
        if count["n"] < 2:
            raise LLMTransientError("busy")
        return {"choices": [{"message": {"content": "OK"}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = client.complete("hi")
    assert out.text == "OK"
    assert count["n"] == 2


def test_permanent_no_retry() -> None:
    count = {"n": 0}

    def transport(url, payload, headers, timeout):
        count["n"] += 1
        raise LLMPermanentError("bad key")

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    with pytest.raises(LLMPermanentError):
        client.complete("hi")
    assert count["n"] == 1


def test_malformed_response() -> None:
    def transport(url, payload, headers, timeout):
        return {"choices": []}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    with pytest.raises(LLMError):
        client.complete("hi")

