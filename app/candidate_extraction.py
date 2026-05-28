from __future__ import annotations

import re
from typing import Any, Dict, List

from app.dataset import sanitize_runtime_sample

QUESTION_FAMILY_MCQ = "mcq"
QUESTION_FAMILY_YES_NO_UNKNOWN = "yes_no_unknown"
QUESTION_FAMILY_OPEN_ENDED = "open_ended"

_OPEN_ENDED_PREFIX_RE = re.compile(
    r"^\s*(what|which|who|whom|whose|when|where|why|how|explain|describe|summarize)\b",
    re.IGNORECASE,
)
_YES_NO_PREFIX_RE = re.compile(
    r"^\s*(is|are|am|was|were|do|does|did|can|could|should|would|will|has|have|had|may|might|must)\b",
    re.IGNORECASE,
)
_UNKNOWN_STYLE_RE = re.compile(
    r"\b(enough information|sufficient information|can we conclude|can be concluded|can be determined|whether)\b",
    re.IGNORECASE,
)


def classify_question_family(question: str) -> str:
    options = _extract_inline_mcq_candidates(question or "")
    if options:
        return QUESTION_FAMILY_MCQ

    text = (question or "").strip()
    if _YES_NO_PREFIX_RE.match(text) or _UNKNOWN_STYLE_RE.search(text):
        return QUESTION_FAMILY_YES_NO_UNKNOWN
    if _OPEN_ENDED_PREFIX_RE.match(text):
        return QUESTION_FAMILY_OPEN_ENDED
    return QUESTION_FAMILY_OPEN_ENDED


def _base_question_text(question: str) -> str:
    lines = (question or "").splitlines()
    kept: List[str] = []
    for line in lines:
        if re.match(r"^\s*[A-D]\.\s+", line):
            continue
        kept.append(line)
    return " ".join(part.strip() for part in kept if part.strip()).strip()


def _extract_inline_mcq_candidates(question: str) -> List[Dict[str, str]]:
    lines = (question or "").splitlines()
    candidates: List[Dict[str, str]] = []
    current_label = None
    current_chunks: List[str] = []
    expected_idx = 0

    def flush() -> None:
        nonlocal current_label, current_chunks
        if current_label is None:
            return
        text = "\n".join(chunk.rstrip() for chunk in current_chunks if chunk.strip()).strip()
        candidates.append({"label": current_label, "text": text})
        current_label = None
        current_chunks = []

    for raw_line in lines:
        line = raw_line.rstrip()
        matched = re.match(r"^\s*([A-D])\.\s*(.*)$", line)
        if matched:
            label = matched.group(1)
            label_idx = ord(label) - ord("A")
            if label_idx != expected_idx:
                return []
            flush()
            current_label = label
            current_chunks = [matched.group(2)]
            expected_idx += 1
            continue
        if current_label is not None:
            current_chunks.append(line)

    flush()
    if [c["label"] for c in candidates] != ["A", "B", "C", "D"]:
        return []
    return candidates


def _extract_claim_text(question: str) -> str:
    text = _base_question_text(question).rstrip(" ?")
    if not text:
        return ""

    lowered = text.lower()
    if " whether " in lowered:
        idx = lowered.find(" whether ")
        clause = text[idx + len(" whether ") :].strip()
        return clause.rstrip(" ?.")

    prefix_patterns = (
        r"^is it true that\s+",
        r"^is it correct that\s+",
        r"^is there enough information to conclude that\s+",
        r"^can we conclude that\s+",
        r"^can we infer that\s+",
        r"^does this mean that\s+",
    )
    for pattern in prefix_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()

    if _YES_NO_PREFIX_RE.match(text):
        text = re.sub(_YES_NO_PREFIX_RE, "", text, count=1).strip()

    return text.rstrip(" ?.")


def extract_question_candidates(runtime_sample: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    errors: List[str] = []

    try:
        safe_sample = sanitize_runtime_sample(runtime_sample, include_local_ids=True)
    except Exception as exc:  # pragma: no cover - explicit error path test exists
        return {
            "question_family": None,
            "candidates": [],
            "warnings": [],
            "errors": [f"candidate_extraction_error: {exc}"],
            "debug_summary": {
                "question_family": None,
                "candidate_count": 0,
                "labels": [],
                "warnings": [],
                "extraction_errors": [f"candidate_extraction_error: {exc}"],
            },
        }

    question = safe_sample["question"]
    family = classify_question_family(question)
    candidates: List[Dict[str, Any]] = []

    if family == QUESTION_FAMILY_MCQ:
        options = _extract_inline_mcq_candidates(question)
        for option in options:
            candidates.append(
                {
                    "label": option["label"],
                    "candidate_label": option["label"],
                    "text": option["text"],
                    "source_text": option["text"],
                }
            )
    elif family == QUESTION_FAMILY_YES_NO_UNKNOWN:
        claim_text = _extract_claim_text(question)
        if not claim_text:
            errors.append("candidate_extraction_error: unable to derive claim text")
        else:
            candidates.append(
                {
                    "label": "claim",
                    "candidate_label": "claim",
                    "text": claim_text,
                    "source_text": _base_question_text(question),
                    "supports_explicit_negation_check": True,
                }
            )
            if _UNKNOWN_STYLE_RE.search(question):
                warnings.append("insufficient_evidence_style_question")
    else:
        candidates.append(
            {
                "label": "open_claim",
                "candidate_label": "open_claim",
                "text": _base_question_text(question),
                "source_text": _base_question_text(question),
                "policy": "synthesize_from_proof_trace_or_return_unknown",
            }
        )
        warnings.append("open_ended_best_effort")

    debug_summary = {
        "question_family": family,
        "candidate_count": len(candidates),
        "labels": [candidate["label"] for candidate in candidates],
        "warnings": warnings,
        "extraction_errors": errors,
    }

    return {
        "question_family": family,
        "candidates": candidates,
        "warnings": warnings,
        "errors": errors,
        "debug_summary": debug_summary,
    }
