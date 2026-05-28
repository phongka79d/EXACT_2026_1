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

PREMISE_FRAME_SCHEMA = (
    "Schema:\n"
    "- Return exactly one JSON object.\n"
    "- kind must be exactly one of: rule, fact, compound, ambiguous.\n"
    "- Required common keys: kind, source_id, source_text, premise_id, warnings.\n"
    "- For rule: include if and then arrays of slot objects.\n"
    "- For fact: include facts array of slot objects.\n"
    "- Supported slot types: predicate, entity_relation, numeric_value, numeric_condition, and, or, not.\n"
    "- A numeric_condition slot must include entity, attribute, op, and value.\n"
    "- numeric_condition op must be exactly one of: =, !=, >, <, >=, <=. Use >= for at least/or higher and <= for at most/or lower.\n"
    "- Numeric threshold requirements such as at least, higher than, no more than, within, before, or after must use numeric_condition, not numeric_value.\n"
    "- A numeric_value slot must include entity, attribute, and value.\n"
    "- A predicate slot must include name and args.\n"
    "- Do not use kind values such as conditional, condition, implication, premise, or statement.\n"
)

CANDIDATE_FRAME_SCHEMA = (
    "Schema:\n"
    "- Return exactly one JSON object.\n"
    "- kind must be exactly one of: claim, ambiguous.\n"
    "- Required common keys: kind, source_id, source_text, candidate_label, warnings.\n"
    "- For claim: include claim as one slot object.\n"
    "- Supported slot types: predicate, entity_relation, numeric_value, numeric_condition, and, or, not.\n"
    "- A numeric_condition slot must include entity, attribute, op, and value.\n"
    "- numeric_condition op must be exactly one of: =, !=, >, <, >=, <=. Use >= for at least/or higher and <= for at most/or lower.\n"
    "- Numeric threshold requirements such as at least, higher than, no more than, within, before, or after must use numeric_condition, not numeric_value.\n"
    "- A numeric_value slot must include entity, attribute, and value.\n"
    "- A predicate slot must include name and args.\n"
    "- Do not use kind values such as option, candidate, response, statement, or assertion.\n"
)

THRESHOLD_OPERATOR_TEXT = {
    ">=": ("at least", "or higher", "minimum", "no less than"),
    ">": ("greater than", "higher than", "more than", "above", "after"),
    "<=": ("at most", "or lower", "maximum", "no more than", "within"),
    "<": ("less than", "lower than", "fewer than", "below", "before"),
    "=": ("exactly", "equal to", "equals"),
}


class ParseFrameExtractionError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


@dataclass(frozen=True)
class ExtractorConfig:
    repair_attempts: int = 2


@dataclass(frozen=True)
class ExtractionContext:
    allowed_kinds: frozenset[str]
    source_id: str
    source_text: str
    premise_id: Optional[int] = None
    candidate_label: Optional[str] = None


def build_premise_prompt(premise_text: str, premise_id: int) -> str:
    source_id = f"premise_{premise_id:04d}"
    return (
        "Return exactly one compact JSON parse frame object for this premise. "
        "No markdown, no commentary.\n"
        f"source_id must be {source_id} and premise_id must be {premise_id}.\n"
        f"{PREMISE_FRAME_SCHEMA}"
        "Example for a conditional numeric rule:\n"
        '{"kind":"rule","source_id":"example_premise_9001","source_text":"If learners complete orientation then learners may register for the seminar.","premise_id":9001,"if":[{"type":"predicate","name":"complete_orientation","args":["learners"]}],"then":[{"type":"predicate","name":"may_register_seminar","args":["learners"]}],"warnings":[]}\n'
        "Example for a numeric fact:\n"
        '{"kind":"fact","source_id":"example_premise_9002","source_text":"Ravi completed 18 credits.","premise_id":9002,"facts":[{"type":"numeric_value","entity":"Ravi","attribute":"completed_credits","value":18}],"warnings":[]}\n'
        "The examples show shape only; use the required source_id, source_text, and premise_id for the actual premise.\n"
        f"Premise: {premise_text}"
    )


def build_candidate_prompt(candidate_text: str, candidate_label: str) -> str:
    source_id = f"candidate_{candidate_label}"
    return (
        "Return exactly one compact JSON parse frame object for this candidate claim. "
        "No markdown, no commentary.\n"
        f"source_id must be {source_id} and candidate_label must be {candidate_label}.\n"
        f"{CANDIDATE_FRAME_SCHEMA}"
        "Example for a predicate claim:\n"
        '{"kind":"claim","source_id":"example_candidate_Z","source_text":"Ravi may register for the seminar.","candidate_label":"Z","claim":{"type":"predicate","name":"may_register_seminar","args":["Ravi"]},"warnings":[]}\n'
        "The example shows shape only; use the required candidate_label and actual candidate text.\n"
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


def _repair_prompt(raw_response: str, error_message: str, schema: str, original_prompt: str) -> str:
    return (
        "Your previous output was invalid. Return only one valid compact JSON parse frame object. "
        "No markdown and no extra text.\n"
        f"{schema}"
        "Preserve the required metadata values from the original extraction instructions. "
        "Do not invent unavailable fields.\n"
        f"Validation error: {error_message}\n"
        f"Original extraction instructions and source text:\n{original_prompt}\n"
        f"Previous output:\n{raw_response}"
    )


def _extract_once(client: OpenAICompatibleClient, prompt: str) -> LLMResponse:
    try:
        return client.complete(prompt)
    except LLMError as exc:
        raise ParseFrameExtractionError("llm_frame_error", str(exc)) from exc


def expected_numeric_ops_for_text(text: str) -> frozenset[str]:
    normalized = " ".join(text.lower().split())
    expected: set[str] = set()
    for op, phrases in THRESHOLD_OPERATOR_TEXT.items():
        for phrase in phrases:
            if phrase not in normalized:
                continue
            if phrase == "more than" and "no more than" in normalized:
                continue
            expected.add(op)
            break
    return frozenset(expected)


def validate_threshold_semantics(result: Dict[str, Any], source_text: str) -> Dict[str, Any]:
    expected_ops = expected_numeric_ops_for_text(source_text)
    if not expected_ops:
        return result

    frame = result.get("frame")
    ast = result.get("ast")
    if not isinstance(frame, dict) or not isinstance(ast, dict):
        raise ParseFrameExtractionError("frame_validation_error", "threshold semantic validation failed: missing frame or AST")

    _validate_threshold_frame_semantics(frame, source_text)

    ast_ops = {
        str(node.get("op"))
        for node in _iter_ast_nodes(ast.get("node"))
        if isinstance(node, dict) and node.get("type") == "compare"
    }
    if not ast_ops.intersection(expected_ops):
        allowed = ", ".join(sorted(expected_ops))
        raise ParseFrameExtractionError(
            "frame_validation_error",
            f"threshold semantic validation failed: compiled AST must include compare op one of: {allowed}",
        )
    return result


def _validate_threshold_frame_semantics(frame: Dict[str, Any], source_text: str) -> None:
    expected_ops = expected_numeric_ops_for_text(source_text)
    if not expected_ops:
        return

    frame_ops = {
        str(slot.get("op"))
        for slot in _iter_frame_slots(frame)
        if isinstance(slot, dict) and slot.get("type") == "numeric_condition"
    }
    if not frame_ops.intersection(expected_ops):
        allowed = ", ".join(sorted(expected_ops))
        raise ParseFrameExtractionError(
            "frame_validation_error",
            f"threshold semantic validation failed: numeric threshold requirements must use numeric_condition with op one of: {allowed}",
        )


def _iter_frame_slots(value: Any):
    if isinstance(value, dict):
        if isinstance(value.get("type"), str):
            yield value
        for key in ("if", "then", "facts", "claim", "operands", "values", "value"):
            if key in value:
                yield from _iter_frame_slots(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from _iter_frame_slots(item)


def _iter_ast_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for key in ("if", "then", "value", "values", "operands", "body", "left", "right"):
            if key in value:
                yield from _iter_ast_nodes(value[key])
    elif isinstance(value, list):
        for item in value:
            yield from _iter_ast_nodes(item)


def _validate_extraction_context(frame: Dict[str, Any], context: Optional[ExtractionContext]) -> None:
    if context is None:
        return

    kind = frame.get("kind")
    if kind not in context.allowed_kinds:
        raise ParseFrameExtractionError("frame_validation_error", f"frame kind {kind!r} is invalid for this extraction context")
    if frame.get("source_id") != context.source_id:
        raise ParseFrameExtractionError("frame_validation_error", "frame source_id does not match extraction context")
    if frame.get("source_text") != context.source_text:
        raise ParseFrameExtractionError("frame_validation_error", "frame source_text does not match extraction context")

    if context.premise_id is not None:
        if frame.get("premise_id") != context.premise_id:
            raise ParseFrameExtractionError("frame_validation_error", "frame premise_id does not match extraction context")
        if "candidate_label" in frame:
            raise ParseFrameExtractionError("frame_validation_error", "premise frame must not include candidate_label")

    if context.candidate_label is not None:
        if frame.get("candidate_label") != context.candidate_label:
            raise ParseFrameExtractionError("frame_validation_error", "frame candidate_label does not match extraction context")
        if "premise_id" in frame:
            raise ParseFrameExtractionError("frame_validation_error", "candidate frame must not include premise_id")

    _validate_threshold_frame_semantics(frame, context.source_text)


def extract_frame_with_repair(
    *,
    client: OpenAICompatibleClient,
    prompt: str,
    source_id: str,
    repair_attempts: int,
    schema: str = PREMISE_FRAME_SCHEMA,
    context: Optional[ExtractionContext] = None,
) -> Dict[str, Any]:
    events: List[Dict[str, Any]] = []
    current_prompt = prompt
    original_prompt = prompt
    last_error: Optional[ParseFrameExtractionError] = None

    for _ in range(max(1, repair_attempts + 1)):
        response = _extract_once(client, current_prompt)
        events.append(build_frame_event("raw_response", source_id, {"text": response.text}))
        try:
            frame = _parse_frame_json(response.text)
            events.append(build_frame_event("normalized_frame", source_id, frame))
            validated = validate_parse_frame(frame)
            _validate_extraction_context(validated, context)
            events.append(build_frame_event("validated_frame", source_id, validated))
            ast = compile_frame_to_ast(validated)
            validate_ast(ast)
            events.append(build_frame_event("compiled_ast", source_id, ast))
            return {"frame": validated, "ast": ast, "events": events}
        except ParseFrameExtractionError as exc:
            last_error = exc
            events.append(build_frame_event("rejected", source_id, {"text": response.text}, reason=exc.category))
            current_prompt = _repair_prompt(response.text, str(exc), schema, original_prompt)
        except (FrameValidationError, FrameCompileError) as exc:
            category = "frame_validation_error" if isinstance(exc, FrameValidationError) else "frame_compile_error"
            last_error = ParseFrameExtractionError(category, str(exc))
            events.append(build_frame_event("rejected", source_id, {"frame": _strip_code_fence(response.text)}, reason=category))
            current_prompt = _repair_prompt(response.text, str(exc), schema, original_prompt)

    assert last_error is not None
    raise ParseFrameExtractionError(last_error.category, f"repair_exhausted: {last_error}")


def extract_premise_frame(
    *,
    client: OpenAICompatibleClient,
    premise_text: str,
    premise_id: int,
    repair_attempts: int,
) -> Dict[str, Any]:
    source_id = f"premise_{premise_id:04d}"
    return extract_frame_with_repair(
        client=client,
        prompt=build_premise_prompt(premise_text, premise_id),
        source_id=source_id,
        repair_attempts=repair_attempts,
        schema=PREMISE_FRAME_SCHEMA,
        context=ExtractionContext(
            allowed_kinds=frozenset({"rule", "fact", "compound", "ambiguous"}),
            source_id=source_id,
            source_text=premise_text,
            premise_id=premise_id,
        ),
    )


def extract_candidate_frame(
    *,
    client: OpenAICompatibleClient,
    candidate_text: str,
    candidate_label: str,
    repair_attempts: int,
) -> Dict[str, Any]:
    source_id = f"candidate_{candidate_label}"
    return extract_frame_with_repair(
        client=client,
        prompt=build_candidate_prompt(candidate_text, candidate_label),
        source_id=source_id,
        repair_attempts=repair_attempts,
        schema=CANDIDATE_FRAME_SCHEMA,
        context=ExtractionContext(
            allowed_kinds=frozenset({"claim", "ambiguous"}),
            source_id=source_id,
            source_text=candidate_text,
            candidate_label=candidate_label,
        ),
    )
