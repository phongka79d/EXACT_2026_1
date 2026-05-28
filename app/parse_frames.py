from __future__ import annotations

from typing import Any, Dict, List

FRAME_KINDS = {"rule", "fact", "claim", "compound", "ambiguous"}


class FrameValidationError(ValueError):
    pass


def validate_parse_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(frame, dict):
        raise FrameValidationError("frame must be an object")

    kind = frame.get("kind")
    if kind not in FRAME_KINDS:
        raise FrameValidationError("invalid frame kind")

    _require_str(frame, "source_id")
    _require_str(frame, "source_text")
    warnings = frame.get("warnings")
    if not isinstance(warnings, list):
        raise FrameValidationError("warnings must be a list")

    candidate_label = frame.get("candidate_label")
    premise_id = frame.get("premise_id")

    if kind == "claim":
        _require_str(frame, "candidate_label")
        if "claim" not in frame:
            raise FrameValidationError("claim frame must include claim payload")

    if kind in {"rule", "fact", "compound"} and candidate_label is None:
        if not isinstance(premise_id, int):
            raise FrameValidationError("premise frame must include integer premise_id")

    if kind == "rule":
        if not isinstance(frame.get("if"), list) or not isinstance(frame.get("then"), list):
            raise FrameValidationError("rule frame must include list if/then")
    if kind == "fact":
        if not isinstance(frame.get("facts"), list):
            raise FrameValidationError("fact frame must include facts list")
    if kind == "compound":
        operator = frame.get("operator")
        if operator not in {"and", "or"}:
            raise FrameValidationError("compound frame operator must be and/or")
        if not isinstance(frame.get("operands"), list):
            raise FrameValidationError("compound frame must include operands list")
    if kind == "ambiguous":
        if not _has_any(frame, "reason", "warnings", "details"):
            raise FrameValidationError("ambiguous frame must include reason/details/warnings")

    return frame


def _require_str(frame: Dict[str, Any], key: str) -> str:
    value = frame.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FrameValidationError(f"{key} must be a non-empty string")
    return value


def _has_any(frame: Dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = frame.get(key)
        if value is None:
            continue
        if isinstance(value, list) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
        if not isinstance(value, (str, list)):
            return True
    return False

