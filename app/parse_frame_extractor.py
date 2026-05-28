from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.ast_contracts import validate_ast
from app.frame_artifacts import build_frame_event
from app.frame_compiler import FrameCompileError, compile_frame_to_ast
from app.llm_client import LLMError, LLMResponse, OpenAICompatibleClient
from app.parse_frames import FrameValidationError, validate_parse_frame

PROMPT_VERSION = "batch5.v1"
COMPILER_VERSION = "batch4.v1"


class ParseFrameExtractionError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ExtractorConfig:
    repair_attempts: int = 2


def build_premise_prompt(premise_text: str, premise_id: int) -> str:
    return (
        "Return exactly one compact JSON parse frame object for this premise. "
        "No markdown, no commentary.\n"
        "Allowed kinds: rule,fact,compound,ambiguous.\n"
        "Required keys: kind,source_id,source_text,premise_id,warnings.\n"
        f"source_id must be premise_{premise_id:04d} and premise_id must be {premise_id}.\n"
        f"Premise: {premise_text}"
    )


def build_candidate_prompt(candidate_text: str, candidate_label: str) -> str:
    return (
        "Return exactly one compact JSON parse frame object for this candidate claim. "
        "No markdown, no commentary.\n"
        "Allowed kinds: claim,ambiguous.\n"
        "Required keys: kind,source_id,source_text,candidate_label,warnings.\n"
        f"candidate_label must be {candidate_label}.\n"
        f"Candidate: {candidate_text}"
    )


def _parse_frame_json(text: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        cleaned = _strip_code_fence(text)
        if cleaned == text:
            raise ParseFrameExtractionError("llm_frame_error", "Malformed JSON from extractor")
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ParseFrameExtractionError("llm_frame_error", "Malformed JSON from extractor") from exc
    if not isinstance(parsed, dict):
        raise ParseFrameExtractionError("frame_validation_error", "Frame payload must be a JSON object")
    return parsed


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _repair_prompt(raw_response: str, error_message: str) -> str:
    return (
        "Your previous output was invalid. Return only one valid compact JSON parse frame object. "
        "No markdown and no extra text.\n"
        f"Validation error: {error_message}\n"
        f"Previous output:\n{raw_response}"
    )


def _extract_once(client: OpenAICompatibleClient, prompt: str) -> LLMResponse:
    try:
        return client.complete(prompt)
    except LLMError as exc:
        raise ParseFrameExtractionError("llm_frame_error", str(exc)) from exc


def extract_frame_with_repair(
    *,
    client: OpenAICompatibleClient,
    prompt: str,
    source_id: str,
    repair_attempts: int,
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    current_prompt = prompt
    last_error: Optional[ParseFrameExtractionError] = None

    for _ in range(max(1, repair_attempts + 1)):
        response = _extract_once(client, current_prompt)
        events.append(build_frame_event("raw_response", source_id, {"text": response.text}))
        try:
            frame = _parse_frame_json(response.text)
            events.append(build_frame_event("normalized_frame", source_id, frame))
            validated = validate_parse_frame(frame)
            events.append(build_frame_event("validated_frame", source_id, validated))
            ast = compile_frame_to_ast(validated)
            validate_ast(ast)
            events.append(build_frame_event("compiled_ast", source_id, ast))
            return {"frame": validated, "ast": ast, "events": events}
        except ParseFrameExtractionError as exc:
            last_error = exc
            events.append(build_frame_event("rejected", source_id, {"text": response.text}, reason=exc.category))
            current_prompt = _repair_prompt(response.text, str(exc))
        except (FrameValidationError, FrameCompileError) as exc:
            category = "frame_validation_error" if isinstance(exc, FrameValidationError) else "frame_compile_error"
            last_error = ParseFrameExtractionError(category, str(exc))
            events.append(build_frame_event("rejected", source_id, {"frame": _strip_code_fence(response.text)}, reason=category))
            current_prompt = _repair_prompt(response.text, str(exc))

    assert last_error is not None
    raise ParseFrameExtractionError(last_error.category, f"repair_exhausted: {last_error}")
