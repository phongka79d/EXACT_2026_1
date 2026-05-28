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
    extract_candidate_frame,
    extract_frame_with_repair,
    extract_premise_frame,
)
from app.premise_cache import PremiseFrameCache, build_api_premise_cache_key, build_local_premise_cache_key
from scripts.smoke_test_llm_parse_frame import validate_live_parse_frame_result


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
    premise_prompt = build_premise_prompt("Mai has GPA 7.2.", 9)
    candidate_prompt = build_candidate_prompt("Mai can change major.", "A")
    assert "premises-FOL" not in premise_prompt
    assert "answer" not in candidate_prompt
    assert "A" in candidate_prompt
    assert '"kind":"rule"' in premise_prompt
    assert '"kind":"fact"' in premise_prompt
    assert "If a student has GPA at least 7.0 then the student can change majors." not in premise_prompt
    assert "Linh has GPA 8.1." not in premise_prompt
    assert "premise_0001" not in premise_prompt
    assert "premise_0002" not in premise_prompt
    assert "A numeric_value slot must include entity, attribute, and value." in premise_prompt
    assert "numeric_condition op must be exactly one of: =, !=, >, <, >=, <=" in premise_prompt
    assert "Do not use kind values such as conditional" in premise_prompt
    assert '"kind":"claim"' in candidate_prompt
    assert "A numeric_value slot must include entity, attribute, and value." in candidate_prompt
    assert "numeric_condition op must be exactly one of: =, !=, >, <, >=, <=" in candidate_prompt


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


def test_extractor_repairs_invalid_frame_kind_with_schema_prompt() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "kind": "conditional",
                                    "source_id": "premise_0001",
                                    "source_text": "If Mai has GPA at least 7.0 then Mai can change majors.",
                                    "premise_id": 1,
                                    "warnings": [],
                                }
                            )
                        }
                    }
                ]
            }
        assert "kind must be exactly one of: rule, fact, compound, ambiguous" in prompt
        frame = {
            "kind": "rule",
            "source_id": "premise_0001",
            "source_text": "If Mai has GPA at least 7.0 then Mai can change majors.",
            "premise_id": 1,
            "if": [{"type": "numeric_condition", "entity": "Mai", "attribute": "gpa", "op": ">=", "value": 7.0}],
            "then": [{"type": "predicate", "name": "can_change_majors", "args": ["Mai"]}],
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_frame_with_repair(client=client, prompt="x", source_id="premise_0001", repair_attempts=1)
    assert calls["n"] == 2
    assert out["frame"]["kind"] == "rule"


def test_invalid_frame_kind_is_rejected_when_repair_unavailable() -> None:
    def transport(url, payload, headers, timeout):
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "kind": "conditional",
                                "source_id": "premise_0002",
                                "source_text": "If Linh submits the form, Linh is eligible.",
                                "premise_id": 2,
                                "warnings": [],
                            }
                        )
                    }
                }
            ]
        }

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    with pytest.raises(ParseFrameExtractionError, match="repair_exhausted"):
        extract_frame_with_repair(
            client=client,
            prompt=build_premise_prompt("If Linh submits the form, Linh is eligible.", 2),
            source_id="premise_0002",
            repair_attempts=0,
        )


def test_repair_prompt_preserves_original_source_context_after_malformed_json() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            return {"choices": [{"message": {"content": "{bad json"}}]}
        assert "source_id must be premise_0002 and premise_id must be 2" in prompt
        assert "Premise: Linh has GPA 8.1." in prompt
        frame = {
            "kind": "fact",
            "source_id": "premise_0002",
            "source_text": "Linh has GPA 8.1.",
            "premise_id": 2,
            "facts": [{"type": "numeric_value", "entity": "Linh", "attribute": "gpa", "value": 8.1}],
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_premise_frame(
        client=client,
        premise_text="Linh has GPA 8.1.",
        premise_id=2,
        repair_attempts=1,
    )
    assert out["frame"]["source_id"] == "premise_0002"
    assert out["frame"]["kind"] == "fact"


def test_candidate_repair_uses_candidate_schema() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            return {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "kind": "assertion",
                                    "source_id": "candidate_B",
                                    "source_text": "Linh is eligible.",
                                    "candidate_label": "B",
                                    "warnings": [],
                                }
                            )
                        }
                    }
                ]
            }
        assert "kind must be exactly one of: claim, ambiguous" in prompt
        assert "premise_id" not in prompt
        frame = {
            "kind": "claim",
            "source_id": "candidate_B",
            "source_text": "Linh is eligible.",
            "candidate_label": "B",
            "claim": {"type": "predicate", "name": "eligible", "args": ["Linh"]},
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_candidate_frame(
        client=client,
        candidate_text="Linh is eligible.",
        candidate_label="B",
        repair_attempts=1,
    )
    assert out["frame"]["kind"] == "claim"
    assert out["frame"]["candidate_label"] == "B"


def test_candidate_extraction_repairs_globally_valid_premise_frame() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            frame = {
                "kind": "fact",
                "source_id": "premise_0007",
                "source_text": "Ravi completed orientation.",
                "premise_id": 7,
                "facts": [{"type": "predicate", "name": "completed_orientation", "args": ["Ravi"]}],
                "warnings": [],
            }
            return {"choices": [{"message": {"content": json.dumps(frame)}}]}
        assert "kind must be exactly one of: claim, ambiguous" in prompt
        assert "invalid for this extraction context" in prompt
        frame = {
            "kind": "claim",
            "source_id": "candidate_C",
            "source_text": "Ravi may register.",
            "candidate_label": "C",
            "claim": {"type": "predicate", "name": "may_register", "args": ["Ravi"]},
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_candidate_frame(
        client=client,
        candidate_text="Ravi may register.",
        candidate_label="C",
        repair_attempts=1,
    )
    assert calls["n"] == 2
    assert out["frame"]["kind"] == "claim"


def test_premise_extraction_repairs_globally_valid_candidate_frame() -> None:
    calls = {"n": 0}

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            frame = {
                "kind": "claim",
                "source_id": "candidate_A",
                "source_text": "Ravi may register.",
                "candidate_label": "A",
                "claim": {"type": "predicate", "name": "may_register", "args": ["Ravi"]},
                "warnings": [],
            }
            return {"choices": [{"message": {"content": json.dumps(frame)}}]}
        assert "kind must be exactly one of: rule, fact, compound, ambiguous" in prompt
        assert "invalid for this extraction context" in prompt
        frame = {
            "kind": "fact",
            "source_id": "premise_0004",
            "source_text": "Ravi completed orientation.",
            "premise_id": 4,
            "facts": [{"type": "predicate", "name": "completed_orientation", "args": ["Ravi"]}],
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_premise_frame(
        client=client,
        premise_text="Ravi completed orientation.",
        premise_id=4,
        repair_attempts=1,
    )
    assert calls["n"] == 2
    assert out["frame"]["kind"] == "fact"


def test_threshold_rule_repairs_numeric_value_to_numeric_condition() -> None:
    calls = {"n": 0}
    source_text = "If Chen has GPA at least 6.5 then Chen may enroll."

    def transport(url, payload, headers, timeout):
        calls["n"] += 1
        prompt = payload["messages"][0]["content"]
        if calls["n"] == 1:
            frame = {
                "kind": "rule",
                "source_id": "premise_0006",
                "source_text": source_text,
                "premise_id": 6,
                "if": [{"type": "numeric_value", "entity": "Chen", "attribute": "gpa", "value": 6.5}],
                "then": [{"type": "predicate", "name": "may_enroll", "args": ["Chen"]}],
                "warnings": [],
            }
            return {"choices": [{"message": {"content": json.dumps(frame)}}]}
        assert "numeric threshold requirements must use numeric_condition" in prompt
        frame = {
            "kind": "rule",
            "source_id": "premise_0006",
            "source_text": source_text,
            "premise_id": 6,
            "if": [{"type": "numeric_condition", "entity": "Chen", "attribute": "gpa", "op": ">=", "value": 6.5}],
            "then": [{"type": "predicate", "name": "may_enroll", "args": ["Chen"]}],
            "warnings": [],
        }
        return {"choices": [{"message": {"content": json.dumps(frame)}}]}

    client = OpenAICompatibleClient(_cfg(), transport=transport)
    out = extract_premise_frame(client=client, premise_text=source_text, premise_id=6, repair_attempts=1)
    assert calls["n"] == 2
    assert out["frame"]["if"][0]["type"] == "numeric_condition"
    assert out["frame"]["if"][0]["op"] == ">="
    assert out["ast"]["node"]["if"]["op"] == ">="


def test_live_smoke_validation_rejects_threshold_equality_ast() -> None:
    source_text = "If Chen has GPA at least 6.5 then Chen may enroll."
    result = {
        "frame": {
            "kind": "rule",
            "source_id": "premise_0006",
            "source_text": source_text,
            "premise_id": 6,
            "if": [{"type": "numeric_value", "entity": "Chen", "attribute": "gpa", "value": 6.5}],
            "then": [{"type": "predicate", "name": "may_enroll", "args": ["Chen"]}],
            "warnings": [],
        },
        "ast": {
            "metadata": {"source_id": "premise_0006", "source_text": source_text, "premise_id": 6},
            "node": {
                "type": "implies",
                "if": {
                    "type": "compare",
                    "op": "=",
                    "left": {"type": "num_ref", "entity": "Chen", "attribute": "gpa"},
                    "right": {"type": "number", "value": 6.5},
                },
                "then": {"type": "pred", "name": "may_enroll", "args": ["Chen"]},
            },
            "warnings": [],
        },
        "events": [],
    }
    with pytest.raises(ParseFrameExtractionError, match="threshold semantic validation failed"):
        validate_live_parse_frame_result(result, source_text)


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
