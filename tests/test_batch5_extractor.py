from __future__ import annotations

import asyncio
import json

import pytest

from app.config import LLMConfig
from app.frame_artifacts import build_frame_event, serialize_frame_events_jsonl
from app.llm_client import OpenAICompatibleClient
from app.parse_frame_extractor import (
    COMPILER_VERSION,
    PROMPT_VERSION,
    ParseFrameExtractionError,
    build_candidate_prompt,
    build_premise_prompt,
    extract_frame_with_repair,
)
from app.premise_cache import PremiseFrameCache, build_api_premise_cache_key, build_local_premise_cache_key


def _cfg() -> LLMConfig:
    return LLMConfig(
        base_url="https://example.com/v1",
        api_key="secret-key",
        model="oss-model",
        temperature=0.0,
        max_tokens=64,
        timeout_seconds=1.0,
        max_retries=0,
        retry_base_delay_seconds=0.0,
        retry_max_delay_seconds=0.0,
        max_concurrency=2,
    )


def test_prompts_are_compact_and_runtime_safe() -> None:
    premise_prompt = build_premise_prompt("Mai has GPA 7.2.", 1)
    candidate_prompt = build_candidate_prompt("Mai can change major.", "A")
    assert "premises-FOL" not in premise_prompt
    assert "answer" not in candidate_prompt
    assert "A" in candidate_prompt


def test_extractor_repairs_code_fence_json() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        frame = {
            "kind": "fact",
            "facts": [{"type": "numeric_value", "entity": "Mai", "attribute": "gpa", "value": 7.2}],
            "source_id": "premise_0001",
            "source_text": "Mai has GPA 7.2.",
            "premise_id": 1,
            "warnings": [],
        }
        return {"choices": [{"message": {"content": f"```json\n{json.dumps(frame)}\n```"}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_frame_with_repair(client=client, prompt="x", source_id="premise_0001", repair_attempts=1)
    assert out["frame"]["kind"] == "fact"
    assert any(event["event_type"] == "raw_response" for event in out["events"])


def test_extractor_repair_exhaustion() -> None:
    def transport(url, payload, headers, timeout):
        return {"choices": [{"message": {"content": "{bad json"}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    with pytest.raises(ParseFrameExtractionError, match="repair_exhausted"):
        extract_frame_with_repair(client=client, prompt="x", source_id="premise_0001", repair_attempts=1)


def test_cache_keys_and_singleflight() -> None:
    assert build_local_premise_cache_key(12) == "record:12"
    api_key = build_api_premise_cache_key(
        [" A ", "B "],
        model="m1",
        prompt_version=PROMPT_VERSION,
        compiler_version=COMPILER_VERSION,
    )
    assert api_key.startswith("premises_hash:")

    async def run() -> None:
        cache = PremiseFrameCache()
        calls = {"n": 0}

        async def factory():
            calls["n"] += 1
            await asyncio.sleep(0.01)
            return {"ok": True}

        out = await asyncio.gather(
            cache.get_or_create("record:1", factory),
            cache.get_or_create("record:1", factory),
            cache.get_or_create("record:1", factory),
        )
        assert calls["n"] == 1
        assert all(item["ok"] for item in out)

    asyncio.run(run())


def test_artifacts_redact_secret_like_content() -> None:
    event = build_frame_event(
        "raw_response",
        "premise_1",
        {"text": "Authorization: Bearer abc123 api_key=supersecret https://x.test?q=1&token=abc"},
    )
    blob = serialize_frame_events_jsonl([event])
    assert "supersecret" not in blob
    assert "abc123" not in blob
    assert "***REDACTED***" in blob
